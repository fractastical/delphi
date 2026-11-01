// Federation: signed replication attestations and peer nodes.
//
// A replication attestation says "I re-ran this claim's Lean proof or data test, on this exact
// test (script and result hashes from scripts/exec/manifest.json), and it came out reproduced,
// drifted or failed". It is signed with the runner's own ed25519 key and addressed by the SHA-256
// of its canonical payload, so any node can verify it without trusting whoever delivered it.
// A claim's replication status is then computed from the verified attestations, not read from a
// file that one party wrote. Design and limits: scripts/federation/README.md.
//
// Nothing here is a nanopub yet: `toNanopubDraft` writes an unsigned TriG that nanopub tooling
// can sign, and publishing stays a separate, explicit step (BEST_PRACTICES.md section 3).

import { createHash, createPrivateKey, createPublicKey, generateKeyPairSync, sign as edSign, verify as edVerify } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { REPO } from "./lib.mjs";

export const SCHEMA = "delphi/replication/0.1";
export const OUTCOMES = ["reproduced", "drifted", "failed"];
export const STATUSES = ["replicated", "single-witness", "contested", "failing-witness", "stale-only", "unattested"];
const SPKI_PREFIX = Buffer.from("302a300506032b6570032100", "hex");
const ID_RE = /^[A-Za-z0-9._-]{1,120}$/;
const HASH_RE = /^sha256:[0-9a-f]{64}$/;
const KEY_RE = /^ed25519:[0-9a-f]{64}$/;
const MAX_ENVELOPE_BYTES = 16_384;

export const fedDir = () => process.env.DELPHI_FED_DIR ?? join(REPO, "test-data/replications");
const sha256hex = (data) => createHash("sha256").update(data).digest("hex");

// ---- canonical JSON ----------------------------------------------------------------------

const sortKeys = (v) =>
  Array.isArray(v) ? v.map(sortKeys)
  : v && typeof v === "object" ? Object.fromEntries(Object.keys(v).sort().filter((k) => v[k] !== undefined).map((k) => [k, sortKeys(v[k])]))
  : v;
export const canonical = (v) => JSON.stringify(sortKeys(v));

// ---- keys --------------------------------------------------------------------------------

export function newIdentity({ operator, name }) {
  const { publicKey, privateKey } = generateKeyPairSync("ed25519");
  const raw = publicKey.export({ type: "spki", format: "der" }).subarray(SPKI_PREFIX.length);
  return {
    operator: operator ?? null,
    name: name ?? null,
    pubkey: `ed25519:${raw.toString("hex")}`,
    privateKey: privateKey.export({ type: "pkcs8", format: "der" }).toString("base64"),
  };
}

const publicKeyOf = (pubkey) => createPublicKey({ key: Buffer.concat([SPKI_PREFIX, Buffer.from(pubkey.slice(8), "hex")]), format: "der", type: "spki" });

// ---- sign and verify ---------------------------------------------------------------------

// `identity` is {pubkey, privateKey, operator, name}; `fields` the claim-specific part of the payload.
export function signAttestation(identity, fields) {
  const payload = {
    schema: SCHEMA,
    ...fields,
    runner: { pubkey: identity.pubkey, operator: identity.operator ?? identity.pubkey, name: identity.name ?? null, ...(fields.runner ?? {}) },
  };
  const bytes = Buffer.from(canonical(payload));
  const key = createPrivateKey({ key: Buffer.from(identity.privateKey, "base64"), format: "der", type: "pkcs8" });
  return { id: `sha256:${sha256hex(bytes)}`, payload: sortKeys(payload), signature: edSign(null, bytes, key).toString("base64") };
}

// Returns {ok: true} or {ok: false, reason}. Checks shape first, so nothing malformed reaches the
// filesystem (claim ids become directory names) or the crypto.
export function verifyAttestation(env) {
  try {
    if (!env || typeof env !== "object") return bad("not an object");
    if (Buffer.byteLength(JSON.stringify(env)) > MAX_ENVELOPE_BYTES) return bad("envelope too large");
    const { id, payload: p, signature } = env;
    if (!HASH_RE.test(id ?? "")) return bad("malformed id");
    if (p?.schema !== SCHEMA) return bad(`unknown schema ${p?.schema}`);
    if (!ID_RE.test(p.claim_id ?? "")) return bad("malformed claim_id");
    if (!/^(data|lean):[A-Za-z0-9._-]{1,120}$/.test(p.entry_id ?? "")) return bad("malformed entry_id");
    if (!HASH_RE.test(p.test?.hash ?? "")) return bad("malformed test hash");
    if (!OUTCOMES.includes(p.outcome)) return bad(`outcome must be one of ${OUTCOMES.join(", ")}`);
    if (!KEY_RE.test(p.runner?.pubkey ?? "")) return bad("malformed runner pubkey");
    const t = Date.parse(p.ran_at);
    if (!Number.isFinite(t) || t > Date.now() + 864e5) return bad("ran_at missing or in the future");
    if (typeof signature !== "string") return bad("missing signature");
    const bytes = Buffer.from(canonical(p));
    if (`sha256:${sha256hex(bytes)}` !== id) return bad("id does not match payload");
    if (!edVerify(null, bytes, publicKeyOf(p.runner.pubkey), Buffer.from(signature, "base64"))) return bad("bad signature");
    return { ok: true };
  } catch (e) {
    return bad(String(e?.message ?? e));
  }
}
const bad = (reason) => ({ ok: false, reason });

// ---- what was tested ---------------------------------------------------------------------

export function loadManifest() {
  const p = join(REPO, "scripts/exec/manifest.json");
  if (!existsSync(p)) return { entries: [], sha256: null };
  const text = readFileSync(p);
  return { ...JSON.parse(text), sha256: sha256hex(text) };
}

// The pinned subject of a test: for data tests the analysis script and the committed result, for
// Lean the module source. The hash of this is what attestations must match to count as current.
export function testSubject(entry) {
  const subject = entry.kind === "lean" ? { source_sha256: entry.source_sha256 } : { script_sha256: entry.script_sha256, result_sha256: entry.result_sha256 };
  return { ...subject, hash: `sha256:${sha256hex(canonical(subject))}` };
}

// ---- store -------------------------------------------------------------------------------

let cache = null;
const invalidate = () => (cache = null);

// All attestations under the store, verified once per load; invalid files are reported, not served.
export function loadStore(dir = fedDir()) {
  const stamp = `${dir}:${Math.floor(Date.now() / 5000)}`;
  if (cache?.stamp === stamp) return cache;
  const valid = new Map();
  const invalid = [];
  if (existsSync(dir)) {
    for (const claimDir of readdirSync(dir, { withFileTypes: true })) {
      if (!claimDir.isDirectory() || claimDir.name === "nanopubs" || !ID_RE.test(claimDir.name)) continue;
      for (const f of readdirSync(join(dir, claimDir.name))) {
        if (!f.endsWith(".json")) continue;
        try {
          const env = JSON.parse(readFileSync(join(dir, claimDir.name, f), "utf8"));
          const v = verifyAttestation(env);
          if (v.ok && env.payload.claim_id === claimDir.name && f === `${env.id.slice(7)}.json`) valid.set(env.id, env);
          else invalid.push({ file: `${claimDir.name}/${f}`, reason: v.ok ? "filed under the wrong name" : v.reason });
        } catch (e) {
          invalid.push({ file: `${claimDir.name}/${f}`, reason: String(e?.message ?? e) });
        }
      }
    }
  }
  return (cache = { stamp, dir, valid, invalid });
}

export function saveAttestation(env, dir = fedDir()) {
  const v = verifyAttestation(env);
  if (!v.ok) return { saved: false, reason: v.reason };
  const claimDir = join(dir, env.payload.claim_id);
  const file = join(claimDir, `${env.id.slice(7)}.json`);
  if (existsSync(file)) return { saved: false, reason: "already stored", id: env.id };
  mkdirSync(claimDir, { recursive: true });
  writeFileSync(file, `${JSON.stringify(env, null, 2)}\n`);
  invalidate();
  return { saved: true, id: env.id, file };
}

// ---- aggregation -------------------------------------------------------------------------

// Verified attestations -> per-claim replication status against the current manifest.
//
// - One vote per signer per entry: the latest attestation by `ran_at`.
// - Only attestations whose test hash equals the manifest's count; the rest are `stale`.
// - `trusted` (pubkeys) restricts whose votes count: each reader chooses their witnesses.
// - Quorum is over distinct declared operators, since two keys held by one party are not
//   independent replications (BEST_PRACTICES.md: "Model agreement is not replication"). The
//   operator is self-declared, so a reader who cares passes `trusted`.
export function aggregate(envelopes, { manifest = loadManifest(), quorum = 2, trusted = null, claim = null } = {}) {
  const trust = trusted?.length ? new Set(trusted) : null;
  const entries = manifest.entries.filter((e) => !claim || e.claim_id === claim);
  const byEntry = Map.groupBy(envelopes, (e) => e.payload.entry_id);
  const claims = new Map();
  for (const entry of entries) {
    const want = testSubject(entry).hash;
    const latest = new Map();
    for (const env of byEntry.get(entry.id) ?? []) {
      const key = env.payload.runner.pubkey;
      if (trust && !trust.has(key)) continue;
      const prev = latest.get(key);
      if (!prev || env.payload.ran_at > prev.payload.ran_at) latest.set(key, env);
    }
    const votes = [...latest.values()];
    const current = votes.filter((v) => v.payload.test.hash === want);
    const ops = (pred) => new Set(current.filter(pred).map((v) => v.payload.runner.operator));
    const reproduced = ops((v) => v.payload.outcome === "reproduced");
    const divergent = ops((v) => v.payload.outcome !== "reproduced");
    const status = !votes.length ? "unattested"
      : !current.length ? "stale-only"
      : reproduced.size && divergent.size ? "contested"
      : divergent.size ? "failing-witness"
      : reproduced.size >= quorum ? "replicated"
      : "single-witness";
    const row = {
      entry: entry.id,
      kind: entry.kind,
      status,
      test_hash: want,
      reproduced_by: reproduced.size,
      divergent_by: divergent.size,
      stale: votes.length - current.length,
      witnesses: current.map((v) => ({
        id: v.id, signer: v.payload.runner.pubkey, operator: v.payload.runner.operator, name: v.payload.runner.name,
        outcome: v.payload.outcome, ran_at: v.payload.ran_at, commit_at_attest: v.payload.commit_at_attest ?? null,
      })),
    };
    if (!claims.has(entry.claim_id)) claims.set(entry.claim_id, []);
    claims.get(entry.claim_id).push(row);
  }
  return { quorum, trusted: trust ? [...trust] : null, manifest_sha256: manifest.sha256, claims };
}

// Best status across a claim's entries, for one-line summaries: contested > replicated > the rest.
const RANK = { contested: 5, replicated: 4, "failing-witness": 3, "single-witness": 2, "stale-only": 1, unattested: 0 };
export const claimStatus = (rows) => rows.reduce((best, r) => (RANK[r.status] > RANK[best] ? r.status : best), "unattested");

// ---- peers -------------------------------------------------------------------------------

export function peerList() {
  const env = process.env.DELPHI_PEERS?.split(",").map((s) => s.trim()).filter(Boolean);
  if (env) return env.map((url) => ({ url: url.replace(/\/$/, "") }));
  const p = join(REPO, "mcp/peers.json");
  if (!existsSync(p)) return [];
  return (JSON.parse(readFileSync(p, "utf8")).peers ?? []).map((x) => ({ ...x, url: x.url.replace(/\/$/, "") }));
}

async function getJson(url, timeoutMs) {
  const res = await fetch(url, { signal: AbortSignal.timeout(timeoutMs), headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(res.status === 404 ? "peer does not speak federation (404)" : `HTTP ${res.status}`);
  return res.json();
}

// Pull envelopes from every peer, verify each one here, and keep only those that pass. A peer is
// never trusted: it can only add signed statements, which are then weighed like any other.
export async function fetchFromPeers({ claim, peers = peerList(), timeoutMs = 8000 } = {}) {
  const results = await Promise.all(peers.map(async (peer) => {
    try {
      const body = await getJson(`${peer.url}/federation/attestations${claim ? `?claim=${encodeURIComponent(claim)}` : ""}`, timeoutMs);
      const list = Array.isArray(body.attestations) ? body.attestations : [];
      const good = list.filter((e) => verifyAttestation(e).ok && (!claim || e.payload.claim_id === claim));
      return { peer: peer.url, ok: true, received: list.length, verified: good.length, rejected: list.length - good.length, envelopes: good };
    } catch (e) {
      return { peer: peer.url, ok: false, error: String(e?.message ?? e), envelopes: [] };
    }
  }));
  return { envelopes: results.flatMap((r) => r.envelopes), peers: results.map(({ envelopes, ...r }) => r) };
}

// The union of local and (optionally) peer attestations, deduplicated by content address.
export async function gather({ claim, includePeers = false, peers } = {}) {
  const store = loadStore();
  const all = new Map(store.valid);
  let peerReport = null;
  if (includePeers) {
    const got = await fetchFromPeers({ claim, peers });
    for (const e of got.envelopes) all.set(e.id, e);
    peerReport = got.peers;
  }
  return { envelopes: [...all.values()], local: store.valid.size, invalid: store.invalid, peers: peerReport };
}

// ---- MCP tool ----------------------------------------------------------------------------

export async function replicationsTool({ claim, quorum = 2, trusted, includePeers = false } = {}) {
  const { envelopes, local, invalid, peers } = await gather({ claim, includePeers });
  const manifest = loadManifest();
  const agg = aggregate(envelopes, { manifest, quorum, trusted, claim });
  const base = {
    quorum, trusted: agg.trusted, attestations: envelopes.length, local, peers,
    ...(invalid.length ? { invalid_files: invalid.slice(0, 10) } : {}),
    how: "Each witness is a signed attestation (ed25519, content-addressed) that the claim's pinned test was re-run. Status counts only attestations of the current test hash, one vote per signer, quorum over distinct operators. Signers are keys, not verified people: pass `trusted` to count only keys you choose. Add one with scripts/federation/cli.mjs attest.",
  };
  if (claim) {
    const rows = agg.claims.get(claim);
    if (!rows) return { claim, found: false, ...base, note: "No Lean proof or data test for this claim in scripts/exec/manifest.json, so nothing to replicate." };
    return { claim, status: claimStatus(rows), entries: rows, ...base };
  }
  const summary = Object.fromEntries(STATUSES.map((s) => [s, 0]));
  const attested = [];
  for (const [id, rows] of agg.claims) {
    const s = claimStatus(rows);
    summary[s]++;
    if (s !== "unattested") attested.push({ claim: id, status: s, reproduced_by: Math.max(...rows.map((r) => r.reproduced_by)), divergent_by: Math.max(...rows.map((r) => r.divergent_by)) });
  }
  attested.sort((a, b) => (RANK[b.status] - RANK[a.status]) || a.claim.localeCompare(b.claim));
  return { claims_with_executable_test: agg.claims.size, summary, attested: attested.slice(0, 200), ...base };
}

// ---- node info and HTTP ------------------------------------------------------------------

export function nodeInfo(dir = fedDir()) {
  const store = loadStore(dir);
  const claimsJson = join(REPO, "docs/claims.json");
  const manifest = loadManifest();
  return {
    schema: SCHEMA,
    node: process.env.DELPHI_NODE_NAME ?? null,
    claims_sha256: existsSync(claimsJson) ? sha256hex(readFileSync(claimsJson)) : null,
    manifest_sha256: manifest.sha256,
    attestations: store.valid.size,
    accepts_posts: process.env.DELPHI_FED_ACCEPT === "1",
    peers: peerList().length,
  };
}

// Compare this node with its peers: same claim graph and manifest, how many attestations each holds.
export async function federationStatus({ peers = peerList(), timeoutMs = 8000 } = {}) {
  const me = nodeInfo();
  const rows = await Promise.all(peers.map(async (p) => {
    try {
      const info = await getJson(`${p.url}/federation/info`, timeoutMs);
      return { peer: p.url, ok: true, node: info.node, attestations: info.attestations, same_claims: info.claims_sha256 === me.claims_sha256, same_manifest: info.manifest_sha256 === me.manifest_sha256, accepts_posts: info.accepts_posts };
    } catch (e) {
      return { peer: p.url, ok: false, error: String(e?.message ?? e) };
    }
  }));
  return { self: me, peers: rows };
}

// Mounted by mcp/http.mjs. Returns true when it handled the request.
export async function handleFederation(req, res, path, { send, readJson, dir = fedDir() }) {
  if (!path.startsWith("/federation/")) return false;
  const url = new URL(req.url, "http://x");
  const store = loadStore(dir);
  const byClaim = (claim) => [...store.valid.values()].filter((e) => !claim || e.payload.claim_id === claim);

  if (req.method === "GET" && path === "/federation/info") return send(res, 200, nodeInfo(dir)), true;
  if (req.method === "GET" && path === "/federation/index") {
    const claim = url.searchParams.get("claim");
    return send(res, 200, { ids: byClaim(claim).map((e) => ({ id: e.id, claim: e.payload.claim_id })) }), true;
  }
  if (req.method === "GET" && path === "/federation/attestations") {
    const claim = url.searchParams.get("claim");
    if (claim && !ID_RE.test(claim)) return send(res, 400, { error: "bad claim id" }), true;
    return send(res, 200, { attestations: byClaim(claim).slice(0, 2000) }), true;
  }
  const one = path.match(/^\/federation\/attestation\/([0-9a-f]{64})$/);
  if (req.method === "GET" && one) {
    const env = store.valid.get(`sha256:${one[1]}`);
    return env ? send(res, 200, env) : send(res, 404, { error: "unknown attestation" }), true;
  }
  if (req.method === "POST" && path === "/federation/attestations") {
    if (process.env.DELPHI_FED_ACCEPT !== "1") return send(res, 403, { error: "this node does not accept attestations (DELPHI_FED_ACCEPT=1 enables it)" }), true;
    let body;
    try { body = await readJson(req); } catch (e) { return send(res, e.status ?? 400, { error: e.message }), true; }
    const list = Array.isArray(body) ? body : [body];
    if (list.length > 100) return send(res, 413, { error: "at most 100 attestations per request" }), true;
    const accepted = [];
    const rejected = [];
    for (const env of list) {
      const r = saveAttestation(env, dir);
      if (r.saved) accepted.push(r.id);
      else rejected.push({ id: env?.id ?? null, reason: r.reason });
    }
    return send(res, 200, { accepted, rejected }), true;
  }
  return send(res, 404, { error: "unknown federation endpoint" }), true;
}

// ---- unsigned nanopub draft --------------------------------------------------------------

// A draft of the attestation as a nanopub, in the repo's unsigned-TriG convention, for nanopub
// tooling to sign. It uses PROV-O only: a dedicated delphi: replication term would have to be
// proposed upstream first (BEST_PRACTICES.md section 9). The ed25519 signature stays in the JSON
// envelope; the nanopub is signed separately with the operator's nanopub key.
export function toNanopubDraft(env) {
  const p = env.payload;
  const lit = (s) => JSON.stringify(String(s));
  return `@prefix this: <http://purl.org/nanopub/temp/np1/> .
@prefix sub: <http://purl.org/nanopub/temp/np1/> .
@prefix np: <http://www.nanopub.org/nschema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix delphir: <https://w3id.org/delphi/resource/> .

sub:Head {
  this: a np:Nanopublication ;
    np:hasAssertion sub:assertion ;
    np:hasProvenance sub:provenance ;
    np:hasPublicationInfo sub:pubinfo .
}

sub:assertion {
  sub:replication a prov:Activity ;
    rdfs:label ${lit(`Re-run of ${p.entry_id}: ${p.outcome}`)} ;
    prov:used delphir:claim/${p.claim_id} ;
    dct:identifier ${lit(env.id)} ;
    dct:description ${lit(`Test hash ${p.test.hash}; outcome ${p.outcome}.`)} ;
    prov:endedAtTime ${lit(p.ran_at)}^^xsd:dateTime ;
    prov:wasAssociatedWith sub:runner .
  sub:runner a prov:SoftwareAgent ;
    rdfs:label ${lit(p.runner.name ?? p.runner.pubkey)} ;
    dct:identifier ${lit(p.runner.pubkey)} .
}

sub:provenance {
  sub:assertion prov:wasAttributedTo sub:runner ;
    prov:wasGeneratedBy sub:replication .
}

sub:pubinfo {
  this: dct:created ${lit(new Date().toISOString())}^^xsd:dateTime ;
    rdfs:label ${lit(`Replication attestation for ${p.claim_id}`)} .
}
`;
}
