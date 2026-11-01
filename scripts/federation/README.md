# Federation prototype: replication attestations and peer nodes

Status: **prototype**. Local and in-process only. Nothing here is published, no nanopub is signed,
and the hosted server has not been redeployed with it.

## The problem it addresses

A claim's data verdict is one `result.json` written by us, `docs/claims.json` is built from one repo,
and the hosted MCP server is one machine. "Reproduced" means "we say it reproduced". Here a claim's
replication status is computed from **signed statements by independent runners**, and any node can
hold, verify and serve them.

## Model

A **replication attestation** says: *I re-ran this claim's Lean proof or data test, pinned to these
hashes, and it came out reproduced / drifted / failed.*

```
{ id: "sha256:<hash of canonical payload>",
  payload: { schema, claim_id, entry_id, kind,
             test: { script_sha256, result_sha256 | source_sha256, hash },   // from scripts/exec/manifest.json
             outcome, observed, commit_at_attest, ran_at,
             runner: { pubkey: "ed25519:<hex>", operator, name, ... } },
  signature }                                                              // ed25519 over the canonical payload
```

- **Self-certifying.** `id` is the hash of the payload and the signature verifies against the pubkey
  inside it, so an attestation is valid wherever you got it from. A node never trusts a peer, only
  the signatures. Tampering, a forged signer, a path-traversal `claim_id` and a future `ran_at` are
  all rejected (see `selftest.mjs`).
- **Status** per claim, against the *current* manifest (`mcp/federation.mjs`, `aggregate`):
  - only attestations whose test hash equals the manifest's count; the rest are `stale`;
  - one vote per signer, the latest by `ran_at`;
  - quorum (default 2) is over distinct declared **operators**, not keys, because two keys held by one
    party are not an independent replication (BEST_PRACTICES.md: "Model agreement is not replication");
  - `replicated` | `single-witness` | `contested` | `failing-witness` | `stale-only` | `unattested`;
  - `trusted` (a list of pubkeys) lets each reader choose whose votes count: the start of a per-observer
    truth score instead of one canonical one.
- **Nodes** serve `/federation/info | index | attestations | attestation/<hash>`, and accept
  `POST /federation/attestations` only when started with `DELPHI_FED_ACCEPT=1`. `info` carries the
  SHA-256 of `claims.json` and the manifest, so `status` shows whether two nodes agree on the claim
  graph. Peers come from `DELPHI_PEERS` or `mcp/peers.json`, never from tool arguments (that would
  let a caller aim the hosted server at internal URLs).
- **MCP tool** `delphi_replications` (and `node mcp/cli.mjs replications`): the summary, or one claim
  with every witness; `includePeers` also asks configured peers and verifies what they return.

## Use

```bash
node scripts/federation/cli.mjs keygen --operator "My Lab" --name my-laptop   # key in ~/.config/delphisci, never the repo
node scripts/exec/run.mjs --claim <id>                                        # re-run the test
node scripts/federation/cli.mjs attest [--claim <id>] [--nanopub]             # sign what you ran
node scripts/federation/cli.mjs sync [--peer https://node] [--push]           # exchange with peers
node scripts/federation/cli.mjs show --claim <id> [--trusted ed25519:..] [--peers]
node scripts/federation/cli.mjs status                                        # this node against its peers
node scripts/federation/selftest.mjs                                          # or: npm run federation:test
```

`attest` skips entries whose script, source or result changed since the manifest was built (the run
vouches only for what it ran) and, by default, `failed` runs: a timeout or missing dependency is your
environment, not evidence against the claim (`--include-failed` to override). Attestations land in
`test-data/replications/<claim>/<hash>.json` (`DELPHI_FED_DIR`), so git is one transport among several.

## Limits, stated plainly

- **Keys are not people.** A signer is a key and `operator` is self-declared, so one party can mint
  many operators. Quorum protects against honest duplication, not against sybils; for that, pass
  `trusted`. A real web of trust (ORCID-bound keys, vouching) is not built.
- **Replication here means re-execution**, with the same script on the same pinned data. It does not
  show the claim is true or that the analysis measures what the claim asserts (that is the A9
  faithfulness gate), and a `drifted` outcome can come from upstream fetch metadata, not the claim.
- **The nanopub draft** (`--nanopub`, unsigned TriG in the store's `nanopubs/unsigned/`) uses PROV-O
  only. A proper `delphi:` replication term has to be proposed upstream first, and publishing
  follows BEST_PRACTICES.md (test registry first, ask before production). The ed25519 envelope is
  not the nanopub signature.
- **No discovery.** Peers are a static list; there is no gossip, no peer exchange and no write
  authentication beyond the on/off switch, rate limit and size limits.
- **Still centralized:** the claim graph itself (`claims.json`) is built from one repo. Rebuilding it
  from the nanopub network, so any node can derive it, is the next step; `claims_sha256` in `info` is
  there to detect when nodes diverge.
