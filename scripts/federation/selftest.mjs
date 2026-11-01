#!/usr/bin/env node
// End-to-end check of the federation prototype with no network and nothing written to the repo:
// three runners with their own keys, two nodes that exchange attestations over HTTP, a lying peer,
// a dead peer, and the aggregation rules (quorum over operators, trusted keys, stale, contested).
//
//   node scripts/federation/selftest.mjs

import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { aggregate, claimStatus, fetchFromPeers, handleFederation, loadManifest, loadStore, newIdentity, replicationsTool, saveAttestation, signAttestation, testSubject, verifyAttestation } from "../../mcp/federation.mjs";

process.env.DELPHI_FED_ACCEPT = "1";
const manifest = loadManifest();
const entry = manifest.entries.find((e) => e.kind === "data" && e.script_sha256 && e.result_sha256);
assert.ok(entry, "manifest has a data test with pinned hashes (run npm run claims:manifest)");

const lab1 = newIdentity({ operator: "lab-1", name: "lab-1-laptop" });
const lab1b = newIdentity({ operator: "lab-1", name: "lab-1-server" }); // a second key held by the same party
const lab2 = newIdentity({ operator: "lab-2", name: "lab-2-cluster" });

const attest = (who, outcome = "reproduced", { subject = testSubject(entry), at = new Date().toISOString() } = {}) =>
  signAttestation(who, { claim_id: entry.claim_id, entry_id: entry.id, kind: entry.kind, test: subject, outcome, observed: { numbers_compared: 12, mismatch_count: outcome === "reproduced" ? 0 : 3 }, commit_at_attest: "0".repeat(40), ran_at: at });

const dirs = [];
const tmp = () => { const d = mkdtempSync(join(tmpdir(), "delphi-fed-")); dirs.push(d); return d; };

function serve(dir, { tamper } = {}) {
  const readJson = (req) => new Promise((resolve, reject) => { let b = ""; req.on("data", (c) => (b += c)); req.on("end", () => { try { resolve(JSON.parse(b)); } catch { reject(Object.assign(new Error("bad json"), { status: 400 })); } }); });
  const send = (res, status, body) => { res.writeHead(status, { "Content-Type": "application/json" }); res.end(JSON.stringify(body)); };
  const server = createServer(async (req, res) => {
    const path = new URL(req.url, "http://x").pathname;
    if (tamper && path === "/federation/attestations" && req.method === "GET") return send(res, 200, { attestations: tamper() });
    if (!(await handleFederation(req, res, path, { send, readJson, dir }))) send(res, 404, {});
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve({ server, url: `http://127.0.0.1:${server.address().port}` })));
}

const statusOf = (envs, opts) => claimStatus(aggregate(envs, { manifest, claim: entry.claim_id, ...opts }).claims.get(entry.claim_id));

test("signatures: genuine passes, every kind of tampering fails", () => {
  const good = attest(lab1);
  assert.equal(verifyAttestation(good).ok, true);
  const flipped = structuredClone(good); flipped.payload.outcome = "drifted";
  assert.match(verifyAttestation(flipped).reason, /id does not match/);
  const reId = structuredClone(flipped); reId.id = attest(lab1, "drifted", { at: good.payload.ran_at }).id;
  assert.equal(verifyAttestation(reId).ok, false);
  const forged = structuredClone(good); forged.payload.runner.pubkey = lab2.pubkey;
  assert.equal(verifyAttestation(forged).ok, false);
  const badSig = { ...good, signature: attest(lab2).signature };
  assert.match(verifyAttestation(badSig).reason, /bad signature/);
  const traversal = signAttestation(lab1, { ...good.payload, claim_id: "../../etc" });
  assert.match(verifyAttestation(traversal).reason, /claim_id/);
  const future = attest(lab1, "reproduced", { at: new Date(Date.now() + 10 * 864e5).toISOString() });
  assert.match(verifyAttestation(future).reason, /future/);
});

test("aggregation: quorum counts distinct operators, trusted keys narrow it, a changed test makes witnesses stale", () => {
  assert.equal(statusOf([]), "unattested");
  assert.equal(statusOf([attest(lab1)]), "single-witness");
  assert.equal(statusOf([attest(lab1), attest(lab1b)]), "single-witness", "two keys, one operator, is not a replication");
  assert.equal(statusOf([attest(lab1), attest(lab2)]), "replicated");
  assert.equal(statusOf([attest(lab1), attest(lab2)], { trusted: [lab1.pubkey] }), "single-witness");
  assert.equal(statusOf([attest(lab1), attest(lab2)], { quorum: 3 }), "single-witness");
  assert.equal(statusOf([attest(lab1), attest(lab2, "drifted")]), "contested");
  assert.equal(statusOf([attest(lab2, "drifted")]), "failing-witness");
  const stale = testSubject({ ...entry, script_sha256: "f".repeat(64) });
  assert.equal(statusOf([attest(lab1, "reproduced", { subject: stale }), attest(lab2, "reproduced", { subject: stale })]), "stale-only");
  const earlier = attest(lab2, "drifted", { at: new Date(Date.now() - 6e4).toISOString() });
  assert.equal(statusOf([earlier, attest(lab2), attest(lab1)]), "replicated", "a signer's latest attestation is the one that counts");
});

test("two nodes exchange attestations; a lying peer and a dead peer change nothing", async () => {
  const [dirA, dirB] = [tmp(), tmp()];
  assert.equal(saveAttestation(attest(lab1), dirA).saved, true);
  assert.equal(saveAttestation(attest(lab2), dirB).saved, true);
  assert.equal(saveAttestation(attest(lab1), dirA).saved, true, "a re-run at another instant is a distinct attestation");
  const dupe = attest(lab2); saveAttestation(dupe, dirB);
  assert.equal(saveAttestation(dupe, dirB).saved, false, "same content address is stored once");

  const a = await serve(dirA);
  const b = await serve(dirB);
  const liar = await serve(tmp(), { tamper: () => { const e = attest(lab2); e.payload.outcome = "drifted"; return [e, attest(lab1b, "reproduced")]; } });
  try {
    process.env.DELPHI_FED_DIR = dirA;
    assert.equal(statusOf([...loadStore(dirA).valid.values()]), "single-witness");

    // A pulls from B: the lab-2 witness arrives, verified, and the claim is now replicated at A.
    const pulled = await fetchFromPeers({ claim: entry.claim_id, peers: [{ url: b.url }] });
    assert.equal(pulled.peers[0].verified, pulled.envelopes.length);
    for (const e of pulled.envelopes) saveAttestation(e, dirA);
    assert.equal(statusOf([...loadStore(dirA).valid.values()]), "replicated");

    // The liar's tampered envelope is rejected on arrival; its genuine one (same operator as lab-1) is kept but adds nothing.
    const fromLiar = await fetchFromPeers({ claim: entry.claim_id, peers: [{ url: liar.url }] });
    assert.equal(fromLiar.peers[0].rejected, 1);
    assert.equal(fromLiar.envelopes.length, 1);

    // A dead peer is reported, never thrown.
    const dead = await fetchFromPeers({ claim: entry.claim_id, peers: [{ url: "http://127.0.0.1:9" }, { url: b.url }], timeoutMs: 1500 });
    assert.equal(dead.peers[0].ok, false);
    assert.equal(dead.peers[1].ok, true);

    // Push: bad envelopes are refused, good ones stored; the info endpoint reports the count.
    const forged = attest(lab1); forged.payload.outcome = "failed";
    const push = await fetch(`${b.url}/federation/attestations`, { method: "POST", body: JSON.stringify([forged, attest(lab1b)]) }).then((r) => r.json());
    assert.equal(push.accepted.length, 1);
    assert.equal(push.rejected.length, 1);
    const info = await fetch(`${b.url}/federation/info`).then((r) => r.json());
    assert.equal(info.attestations, 3);

    // The MCP tool, reading node A's store and asking peers live.
    const tool = await replicationsTool({ claim: entry.claim_id });
    assert.equal(tool.status, "replicated");
    assert.deepEqual(tool.entries[0].witnesses.map((w) => w.operator).sort(), ["lab-1", "lab-2"], "one vote per signer");
    const summary = await replicationsTool({});
    assert.equal(summary.summary.replicated, 1);
    assert.equal(summary.claims_with_executable_test, manifest.entries.filter((e, i, all) => all.findIndex((x) => x.claim_id === e.claim_id) === i).length);
  } finally {
    delete process.env.DELPHI_FED_DIR;
    for (const n of [a, b, liar]) n.server.close();
  }
});

test("a node that does not accept posts says so", async () => {
  const saved = process.env.DELPHI_FED_ACCEPT;
  process.env.DELPHI_FED_ACCEPT = "0";
  const n = await serve(tmp());
  try {
    const r = await fetch(`${n.url}/federation/attestations`, { method: "POST", body: JSON.stringify([attest(lab1)]) });
    assert.equal(r.status, 403);
  } finally {
    process.env.DELPHI_FED_ACCEPT = saved;
    n.server.close();
  }
});

test.after(() => dirs.forEach((d) => rmSync(d, { recursive: true, force: true })));
