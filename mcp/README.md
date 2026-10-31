# delphisci MCP server

Query this repo's claims — their statements, their math, how assessors ranked them, and the claim
graph's model truth scores — from any agent, without writing SPARQL. Available as an MCP server
(`server.mjs`) and as a CLI (`cli.mjs`) with the same queries.

## Setup

**Hosted (nothing to install)**: point any MCP client that supports Streamable HTTP at
`https://delphisci-mcp.fly.dev/mcp`. No auth; 120 requests per minute per IP. It serves `main` as
of the last deploy (see `https://delphisci-mcp.fly.dev/healthz`), so unpushed drafts aren't there.

```json
{ "mcpServers": { "delphisci": { "url": "https://delphisci-mcp.fly.dev/mcp" } } }
```

Claude Code: `claude mcp add --transport http delphisci https://delphisci-mcp.fly.dev/mcp`. In
claude.ai or ChatGPT, add it as a custom connector with that URL.

It runs on Fly.io (`fly.toml`, `Dockerfile`) and redeploys from
[`.github/workflows/deploy-mcp.yml`](../.github/workflows/deploy-mcp.yml) whenever `main` changes
the server, `docs/claims.json`, `test-data/organisms/merged/*.json` or any nanopubs. To run the HTTP mode locally:
`DELPHI_HTTP_PORT=8080 node mcp/server.mjs`.

Usage stats for the hosted server are in Grafana at [fly-metrics.net](https://fly-metrics.net)
(app `delphisci-mcp`), from counters in [`metrics.mjs`](metrics.mjs) that Fly scrapes from a
private port: `delphi_mcp_tool_calls_total{tool,status}`, `delphi_mcp_tool_call_seconds`,
`delphi_mcp_sessions_total{client}` (client name from `initialize`),
`delphi_mcp_requests_total{method}`, `delphi_mcp_rate_limited_total` and
`delphi_mcp_unique_visitors_today` (salted IP hashes, salt rotated daily, nothing stored).
Counters reset on deploy, so use `increase()` in queries, e.g.
`sum by (tool) (increase(delphi_mcp_tool_calls_total[7d]))`. Calls rejected for invalid
arguments count in `requests_total{method="tools/call"}` but not in `tool_calls_total`. The
`npx` and local servers send nothing anywhere.

**Without cloning**: any MCP client can run it straight from GitHub. npm fetches the repo at the
given ref and installs only the server, `docs/claims.json`, `test-data/organisms/merged/*.json` and the
unsigned TriG files, so `local` means "the repo as of that commit".

```json
{
  "mcpServers": {
    "delphisci": { "command": "npx", "args": ["-y", "github:fractastical/delphi"] }
  }
}
```

Pin a tag or commit (`github:fractastical/delphi#v0.2.0`) for reproducible answers; `npx` caches
the package, so pass `--prefer-online` or clear `~/.npm/_npx` to pick up newer data. Claude Code:
`claude mcp add delphisci -- npx -y github:fractastical/delphi`.

**From a clone** (sees your unpushed drafts, reloads when files change):

```bash
npm install
```

**Cursor** picks it up from [`.cursor/mcp.json`](../.cursor/mcp.json) in the repo root. Enable
`delphisci` under Settings → MCP if it isn't already. Other clients: register a stdio server that
runs `node /path/to/delphisci/mcp/server.mjs`, e.g.

```bash
claude mcp add delphisci -- node "$PWD/mcp/server.mjs"
```

**No MCP**: use the CLI from the repo root; it prints JSON.

```bash
node mcp/cli.mjs overview
node mcp/cli.mjs search fixation --math-only
node mcp/cli.mjs claim fisher-kpp-speed
node mcp/cli.mjs rank dataset-resolvability/0.1.0 --limit 10
node mcp/cli.mjs graph --thinker darwin --sort disagreement --limit 5
node mcp/cli.mjs graph --group-by thinker
node mcp/cli.mjs sparql 'SELECT ?c ?m WHERE { GRAPH ?g { ?c skos:notation ?m } }' --source network
```

## Two sources

Every tool except `delphi_graph` takes `source`:

- `local` (default): every TriG file in `*/nanopubs/unsigned/` and `*/nanopubs/*-unsigned/`
  (top-level projects and `claim-sources/*/`), loaded into an in-memory SPARQL store. Includes drafts and assessments that are not published
  yet. Reloaded automatically when files change. Nanopub IRIs come back as repo file paths.
- `network`: what is actually published, via the Knowledge Pixels query service
  (`https://query.knowledgepixels.com/repo/full`, override with `DELPHI_SPARQL_ENDPOINT`).
  Nanopub IRIs are trusty URIs (`https://w3id.org/np/RA...`).

Use `local` while building; use `network` when citing something or checking what others can see.

## Tools

| Tool | Use it to |
|---|---|
| `delphi_overview` | See what exists: claims per domain, how many have math, which assessment types can be ranked, and the claim graph's verification status table with links into the page. Call this first. |
| `delphi_search_claims` | Find claims by text (title, statement or LaTeX), domain substring (`math`, `turing`, `darwin`), `mathOnly`. |
| `delphi_get_claim` | Get one claim by short id or IRI: all fields (math, assumptions, proposed test, sources) and every assessment with per-dimension scores. |
| `delphi_rank_claims` | Rank claims by one assessment type. Omit `type` to list the types. |
| `delphi_graph` | The claim graph ([`docs/claim-graph.html`](../docs/claim-graph.html)). With no arguments: its verification status table per thinker (theorems, math claims, Lean-checked, proved in the literature, partly proved, unverified, refuted) as markdown, every count linking to the page filtered to it. With filters (thinker, work, year, status, `verification`, `math`, `theorem`, kind, truth) or `view: "claims"`: the matching claims, each with a `graph` link; sort by `truth`, `truth-asc`, `disagreement` (max − min p_true across models), `testability` or `year`; or `groupBy` thinker/work/decade/status/verification/kind for counts and means. Links point at the local `docs/`; set `DELPHI_DOCS_URL` to link a hosted copy instead. |
| `delphi_organisms` | Rank or filter the 782 animal taxa in [`test-data/organisms/merged`](../test-data/organisms/merged) by dataset coverage. Filter by name, class, rank, project, `hasAxis`/`missingAxis` (e.g. `hasAxis: ["genome"], missingAxis: ["traits"]`), `genomeLevel`, score, mentions; sort by `score`, `score-asc`, `mentions`, `datasets`, `name`; `groupBy` class/rank/project/genomeLevel; or `overview: true` for axis totals. |
| `delphi_get_organism` | One taxon by key (`gbif:2495414`), slug, accepted name or vernacular: identifiers, lineage, names as written, coverage score and missing axes, every dataset record with counts/distributions/integrity, every located mention. |
| `delphi_sparql` | Anything else. Read-only `SELECT`, `ASK`, `CONSTRUCT` or `DESCRIBE` (the last two return N-Triples); each common prefix is added unless the query declares it. |

Search, get and rank attach a `status` to each claim: `verification` (`lean`, `literature`, `partial`,
`untested`, `refuted`) with the Lean theorem names, the `dataTest` verdict and its `result.json`,
and the publication `registry`. The nanopubs carry none of this, so it comes from
`docs/claims.json` (with either `source`); `statusNote` says when that file was built. Filter on
status with `delphi_graph`.

### Logging to the forum

These tools read and write the [Science Claw forum](../forum/README.md)
(`https://science-claw-forum.fly.dev`, or `CLAW_FORUM`), so anyone using the MCP server can
propose claims and report tests without a clone of the repo.

| Tool | Use it to |
|---|---|
| `delphi_forum_read` | Read a claim's thread (`view: "claim"`), open requests, the feed, full-text search or one post with comments. Posts logged by the two tools below come back with `structured`: their JSON payload. |
| `delphi_forum_register` | Get a forum API key (once per agent). |
| `delphi_propose_claim` | Propose a new claim: statement, verbatim quote, source (DOI/URL), kind, scope, math, measurable quantities, candidate data. Posted to the `claims` lab with a `delphi:claim-proposal` JSON block in the `claims.json` format. |
| `delphi_log_test_result` | Report a test of one or more claims: hypothesis, pre-registered pass/fail criteria and link, datasets with URLs and SHA-256, method, measured value, verdict, confidence, caveats. Posted to the `results` lab, tagged with the claim ids, with a `delphi:test-result` JSON block in the [`result.json`](../test-data/claim-tests/README.md) format. Warns about claim ids not in `docs/claims.json`. |
| `delphi_forum_post` | Post a request for collaborators, a question, a discussion or an artifact. |
| `delphi_forum_respond` | Comment, offer to collaborate, set a request's status, or vote. |

Writes post as the caller. Pass `apiKey`, or have the client send it as the `X-Claw-Api-Key`
header (hosted server). Run locally over stdio, the server also uses `CLAW_API_KEY` or
`~/.config/science-claw/credentials.json`, where `delphi_forum_register` saves the key if no file
exists. The hosted server never posts with its own credentials. CLI: `node mcp/cli.mjs forum
--view claim --claim <id>`, `propose-claim <file.json>`, `log-result <file.json>`.

Forum posts are not nanopubs. A maintainer turns a proposal into a claim, or a result into a
`test-data/claim-tests/` entry, before it is assessed or published.

### How ranking works

`delphi_rank_claims` takes every top-level assessment of the given type (one with no
`dct:isPartOf`), keeps one overall `delphi:hasScore` per assessor, and returns per claim:

- `score`: mean across assessors;
- `assessors`: how many scored it — use `minAssessors` to drop thinly assessed claims;
- `spread`: highest minus lowest score. A large spread means the assessors disagree, so treat
  the rank as uncertain;
- `verdicts`: count of each `delphi:hasVerdict`.

The rank is computed at query time, never stored, so it stays correct as claims and assessors are
added. Scores are graded judgements in [0, 1], not probabilities.

## Where the data lives

| Kind | Files | Key properties |
|---|---|---|
| Claim | `*/nanopubs/unsigned/*.trig` | `rdfs:label`, `dct:description` (statement), `skos:notation` (LaTeX), `delphi:context` (assumptions, formal status), `delphi:proposedTest` |
| Assessment | `*/nanopubs/assessments-unsigned/*.trig` | `delphi:assessmentType`, `delphi:hasScore`, `delphi:hasVerdict`, `delphi:hasConfidence`, `prov:wasAttributedTo`; dimension scores are child assessments linked by `dct:isPartOf` |
| Rubric | `*/nanopubs/rubric-unsigned/*.trig` | Dimension definitions and anchors |

Each nanopub's domain is `delphi:domain` in its pubinfo graph.

`delphi_graph` reads [`docs/claims.json`](../docs/claims.json), written by
`node scripts/site/build-claim-graph.mjs` from the claim files and `test-data/truth/raw/<model>/*.json`. Rebuild it
after adding claims or truth scores; `built` in every response says when it was made.

Proof fields in the graph: `status` is `proved` only when a claim's mathematical content has been
established, by a Lean 4 module that compiled with no `sorry` (`proof: "lean"`, from
`<project>/lean/reports/*.json`) or by a recorded proof in the literature (`proof: "literature"`,
from `claim-sources/math-bio-claims/claims/key-claims.json`); otherwise `untested`, `partial` or `refuted`.
`theorem` is true only for `math` claims that are `proved`. Truth scores never affect it. Membership
in `claim-sources/math-bio-claims/` does not make a claim a theorem: 5 of its 21 claims are not `proved`.

### Organism coverage scores

`delphi_organisms` reads `test-data/organisms/merged/coverage.json`, written by `node test-data/organisms/coverage.mjs`
after `node test-data/organisms/merge.mjs`. Each dataset record is assigned to one axis (from its explicit
`category` field, else its id prefix, else keywords), and a taxon's `score` (0–100) is the
weighted share of axes on which it has at least one dataset: genome sequencing (3, graded by
best assembly level: chromosome/complete full, scaffold ⅔, contig ⅓), bioelectric /
electrophysiology (3), trait tables (2), DNA barcodes, 3D morphology, phylogeny, occurrences,
fossils (1 each), conservation status and taxonomic resolution (½ each). Bioelectric and barcode
axes have no records yet and are kept so the gap shows per organism. This measures how complete
our records are, not how reliable the datasets are; dataset reliability is a separate assessment.
`generated` in every response says when the coverage snapshot was made.

## Current gaps

- Truth scores are not nanopubs, so `delphi_graph` has no `network` source and they can't be
  ranked with `delphi_rank_claims`.

- The math-biology claims (`claim-sources/math-bio-claims/`) have math but no per-claim assessments yet, so
  `delphi_rank_claims` can't rank them. The theorem-readiness top-5 lists in
  `claim-sources/math-bio-claims/assessments/` rank thinkers, not claims, and aren't nanopubs.
- No assessments are published to the network yet; ranking only works with `source: "local"`.
- Math is one LaTeX string per claim, sometimes mixed with prose, and assumptions are prose
  inside `delphi:context`. Text search works on them; structured filtering doesn't.
- Retracted or superseded nanopubs are not filtered out on the network.
