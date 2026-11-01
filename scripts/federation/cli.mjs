#!/usr/bin/env node
// Federation CLI: sign what you re-ran, verify what you were sent, exchange it with peers.
//
//   node scripts/federation/cli.mjs keygen --operator "Jane Lab" --name jane-laptop
//   node scripts/federation/cli.mjs attest [--run scripts/exec/runs/latest.json] [--claim ID] [--include-failed] [--nanopub]
//   node scripts/federation/cli.mjs verify [file-or-dir ...]       (default: the whole store)
//   node scripts/federation/cli.mjs status                         (this node against its peers)
//   node scripts/federation/cli.mjs sync [--peer URL ...] [--claim ID] [--push]
//   node scripts/federation/cli.mjs show [--claim ID] [--quorum N] [--trusted KEY,KEY] [--peers]
//
// Peers come from --peer, DELPHI_PEERS (comma list) or mcp/peers.json. The store is
// DELPHI_FED_DIR, default test-data/replications. Your key lives in DELPHI_IDENTITY, default
// ~/.config/delphisci/identity.json, and is never written into the repo.

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { chmodSync, existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { homedir, platform } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { OUTCOMES, fedDir, federationStatus, fetchFromPeers, loadManifest, loadStore, newIdentity, peerList, replicationsTool, saveAttestation, signAttestation, testSubject, toNanopubDraft, verifyAttestation } from "../../mcp/federation.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../..");
const IDENTITY = process.env.DELPHI_IDENTITY ?? join(homedir(), ".config/delphisci/identity.json");

const [cmd, ...rest] = process.argv.slice(2);
const opts = { peer: [] };
for (let i = 0; i < rest.length; i++) {
  if (!rest[i].startsWith("--")) { (opts._ ??= []).push(rest[i]); continue; }
  const key = rest[i].slice(2);
  const next = rest[i + 1];
  const val = next === undefined || next.startsWith("--") ? true : next;
  if (val !== true) i++;
  if (key === "peer") opts.peer.push(val);
  else opts[key] = val;
}
const peers = () => (opts.peer.length ? opts.peer.map((url) => ({ url: url.replace(/\/$/, "") })) : peerList());
const out = (x) => console.log(JSON.stringify(x, null, 2));
const sha = (p) => createHash("sha256").update(readFileSync(p)).digest("hex");

function loadIdentity() {
  if (!existsSync(IDENTITY)) throw new Error(`no identity at ${IDENTITY}; run: node scripts/federation/cli.mjs keygen --operator "<you or your lab>"`);
  return JSON.parse(readFileSync(IDENTITY, "utf8"));
}

async function post(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: AbortSignal.timeout(15000) });
  return { status: res.status, body: await res.json().catch(() => null) };
}

const commands = {
  keygen() {
    if (existsSync(IDENTITY) && !opts.force) throw new Error(`${IDENTITY} exists; --force replaces it (and your old attestations stay under the old key)`);
    const id = newIdentity({ operator: opts.operator, name: opts.name });
    mkdirSync(dirname(IDENTITY), { recursive: true });
    writeFileSync(IDENTITY, `${JSON.stringify(id, null, 2)}\n`, { mode: 0o600 });
    chmodSync(IDENTITY, 0o600);
    out({ wrote: IDENTITY, pubkey: id.pubkey, operator: id.operator, name: id.name, note: "Share the pubkey so others can add it to their `trusted` list. Never commit this file." });
  },

  // Turn the last claims:exec run into signed attestations. A run only vouches for the test it ran,
  // so entries whose script, source or result changed since the manifest was built are skipped.
  attest() {
    const identity = loadIdentity();
    const runFile = opts.run ?? join(ROOT, "scripts/exec/runs/latest.json");
    const run = JSON.parse(readFileSync(runFile, "utf8"));
    const manifest = loadManifest();
    const byId = new Map(manifest.entries.map((e) => [e.id, e]));
    const allowed = new Set(opts["include-failed"] ? OUTCOMES : ["reproduced", "drifted"]);
    const commit = spawnSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" }).stdout.trim() || null;
    const made = [];
    const skipped = [];
    for (const r of run.results) {
      if (opts.claim && r.claim_id !== opts.claim) continue;
      const entry = byId.get(r.id);
      const skip = (reason) => skipped.push({ entry: r.id, reason });
      if (!entry) { skip("not in the manifest"); continue; }
      if (!allowed.has(r.status)) { skip(`status ${r.status} is not attested${r.status === "failed" ? " (use --include-failed; a failure may be your environment, not the claim)" : ""}`); continue; }
      if (r.script_changed_since_manifest || r.source_changed_since_manifest) { skip("test changed since the manifest was built; run npm run claims:manifest and re-run"); continue; }
      if (entry.kind === "data" && entry.result_sha256) {
        const p = join(ROOT, entry.dir, "result.json");
        if (existsSync(p) && sha(p) !== entry.result_sha256) { skip("result.json differs from the manifest; rebuild the manifest and re-run"); continue; }
      }
      const env = signAttestation(identity, {
        claim_id: r.claim_id,
        entry_id: r.id,
        kind: r.kind,
        test: testSubject(entry),
        outcome: r.status,
        observed: {
          verdict_committed: r.verdict?.committed ?? null,
          verdict_now: r.verdict?.now ?? null,
          numbers_compared: r.compared ?? null,
          mismatch_count: r.mismatch_count ?? r.mismatches?.length ?? 0,
          ...(r.axioms ? { lean_axioms: r.axioms } : {}),
        },
        commit_at_attest: commit,
        ran_at: run.ran_at,
        runner: { node_version: process.version, platform: platform() },
      });
      const saved = saveAttestation(env);
      if (saved.saved && opts.nanopub) {
        const dir = join(fedDir(), "nanopubs/unsigned");
        mkdirSync(dir, { recursive: true });
        writeFileSync(join(dir, `replication-${env.id.slice(7, 23)}.trig`), toNanopubDraft(env));
      }
      made.push({ entry: r.id, outcome: r.status, id: env.id, stored: saved.saved, ...(saved.saved ? {} : { why: saved.reason }) });
    }
    out({ signer: identity.pubkey, store: fedDir(), attested: made.length, skipped: skipped.length, made, skipped });
  },

  verify() {
    const targets = opts._?.length ? opts._ : [fedDir()];
    const results = [];
    const walk = (p) => {
      if (statSync(p).isDirectory()) return readdirSync(p).forEach((f) => walk(join(p, f)));
      if (!p.endsWith(".json")) return;
      try {
        const env = JSON.parse(readFileSync(p, "utf8"));
        const v = verifyAttestation(env);
        results.push({ file: p, ok: v.ok, ...(v.ok ? { id: env.id, signer: env.payload.runner.pubkey, outcome: env.payload.outcome } : { reason: v.reason }) });
      } catch (e) {
        results.push({ file: p, ok: false, reason: String(e.message) });
      }
    };
    targets.forEach(walk);
    const failed = results.filter((r) => !r.ok);
    out({ checked: results.length, valid: results.length - failed.length, invalid: failed });
    if (failed.length) process.exitCode = 1;
  },

  async status() {
    out(await federationStatus({ peers: peers() }));
  },

  // Anti-entropy by content address: list what a peer has, fetch only what we lack, verify each
  // envelope here, and (with --push) offer the peer what it lacks. Peers are never trusted.
  async sync() {
    const list = peers();
    if (!list.length) throw new Error("no peers: pass --peer URL, set DELPHI_PEERS, or fill mcp/peers.json");
    const mine = loadStore().valid;
    const report = [];
    for (const peer of list) {
      const row = { peer: peer.url, pulled: 0, rejected: 0, pushed: 0 };
      const got = await fetchFromPeers({ claim: opts.claim, peers: [peer] });
      const info = got.peers[0];
      if (!info.ok) { report.push({ ...row, error: info.error }); continue; }
      row.rejected = info.rejected;
      for (const env of got.envelopes) {
        if (mine.has(env.id)) continue;
        if (saveAttestation(env).saved) row.pulled++;
      }
      if (opts.push) {
        const have = new Set(got.envelopes.map((e) => e.id));
        const missing = [...loadStore().valid.values()].filter((e) => !have.has(e.id) && (!opts.claim || e.payload.claim_id === opts.claim));
        for (let i = 0; i < missing.length; i += 100) {
          const r = await post(`${peer.url}/federation/attestations`, missing.slice(i, i + 100));
          if (r.status === 200) row.pushed += r.body.accepted.length;
          else { row.push_error = r.body?.error ?? `HTTP ${r.status}`; break; }
        }
      }
      report.push(row);
    }
    out({ store: fedDir(), local: loadStore().valid.size, peers: report });
  },

  async show() {
    out(await replicationsTool({
      claim: opts.claim,
      quorum: opts.quorum ? Number(opts.quorum) : 2,
      trusted: opts.trusted ? String(opts.trusted).split(",") : undefined,
      includePeers: Boolean(opts.peers),
    }));
  },
};

if (!commands[cmd]) {
  console.error(`Usage: node scripts/federation/cli.mjs <${Object.keys(commands).join("|")}> [options]`);
  process.exit(1);
}
try {
  await commands[cmd]();
} catch (e) {
  console.error(e?.message ?? e);
  process.exit(1);
}
