# Notes for agents

This repo extracts candidate laws of biology as claims, assesses them, and publishes both as
nanopublications. See [README.md](README.md) for the goal and [BEST_PRACTICES.md](BEST_PRACTICES.md)
before building or publishing nanopubs.

## Querying claims, math and rankings

Don't grep TriG files or hand-write SPARQL first. Use the `delphisci` MCP server (configured in
`.cursor/mcp.json`; run `npm install` in the repo root once):

1. `delphi_overview` to see domains, claim counts and rankable assessment types.
2. `delphi_search_claims` (`mathOnly: true` for formal statements) or `delphi_get_claim`.
3. `delphi_rank_claims` with an assessment type, e.g. `dataset-resolvability/0.1.0`.
4. `delphi_graph` for thinker/year/status views and model truth scores (from `docs/claims.json`).
5. `delphi_organisms` / `delphi_get_organism` for the animal taxa, their vendored datasets and the
   per-taxon dataset-coverage ranking (genome, bioelectric, traits, fossils, …).

Without MCP, the same queries are available as
`node mcp/cli.mjs <overview|search|claim|rank|graph|organisms|organism|sparql>`.
Outside the repo, `npx -y github:fractastical/delphi` runs the same server.

Default `source` is `local` (repo files, including unpublished drafts). Pass `source: "network"`
for what is actually published. Details, ranking semantics and known gaps:
[mcp/README.md](mcp/README.md).

## Other biology knowledge graphs

Query other graphs through their own MCP servers rather than through `delphisci`:

- `indra-cogex` (`https://discovery.indra.bio/mcp`, public, configured alongside `delphisci`):
  INDRA CoGEx, 20M+ nodes of genes, proteins, chemicals, diseases, pathways and literature-mined
  causal statements with evidence. Ground a term with `ground_entity` (e.g. "BMP4" → `hgnc:1071`),
  then `suggest_endpoints` / `call_endpoint`, or `execute_cypher` for custom traversals.

INDRA is molecular and mostly human: it fits the math-bio, cell-geometry and bioelectric claims
(morphogens, ion channels, signalling), not organism-level claims. It does not ground species
names; for taxa use the GBIF/NCBI/Wikidata IDs from `delphi_get_organism`.

A typical cross-graph question: take the entities in a delphisci claim, ground them in INDRA, and
pull mechanistic statements and their evidence as support or counter-evidence for the claim. Cite
INDRA statement hashes and PMIDs, not just the tool output. Statements between grounded genes:

```cypher
MATCH (a:BioEntity)-[r:indra_rel]->(b:BioEntity) WHERE a.id IN $ids AND b.id IN $ids
RETURN a.name, r.stmt_type, b.name, r.evidence_count, r.stmt_hash ORDER BY r.evidence_count DESC
```

For `turing-ddi` with NODAL/LEFTY1/LEFTY2 this returns the activator–inhibitor loop (LEFTY1 ⊣
NODAL, 67 evidences; NODAL → LEFTY1/2 and itself).

## "Theorem" is a proof status, not a project

Call a claim a theorem only when it is a mathematical statement whose proof has been established.
In `docs/claims.json` (built by `docs/load-claims.mjs`) that is `theorem: true`, which requires
`math` (a formal statement or a mathematical claim kind) and `status: "proved"`, and `proved` is
assigned in exactly two cases:

- `proof: "lean"`: a `formalized` entry in some `<project>/lean/reports/*.json`, meaning the Lean 4
  module compiled with no `sorry` and only Lean's standard axioms (`books/thompson-growth-form/lean/INSTRUCTIONS.md`);
- `proof: "literature"`: the formal status recorded in `math-bio-claims/claims/key-claims.json`
  says the result is proved.

Everything else is a claim, however its author phrased it and whatever directory it lives in. The
21 claims in `math-bio-claims/` are a selection of claims *about* results by mathematical
biologists; only the 16 with a recorded proof count, and the Lean-checked Thompson claims count just
as much. Assessor truth scores are opinions and never promote a claim. `docs/theorems.html` lists
the `theorem` set and nothing else; `delphi_graph` with `status: "proved"` returns the same set.
A proof shows a statement follows from its assumptions, not that organisms satisfy them; that is
what the assessments and `claim-tests/` are for.

## Projects

- `books/`: one project per source book, each with `inputs/`, `extraction/`, `claims.json`,
 `assessment/`, `build/` and `nanopubs/`.
 - `books/darwin-origin/`: 247 claims from *On the Origin of Species*, with dataset-resolvability assessments.
 - `books/thompson-growth-form/`: 291 claims from *On Growth and Form*, 47 of them machine-checked
 in Lean 4 (`lean/`). `books/wolfram-nks/`: 321 claims from *A New Kind of Science*. Both are on
 production with dataset-resolvability/0.2.0 assessments.
 - `books/levin-papers/`: 310 claims from sixteen CC BY papers by Michael Levin and colleagues
 (2014–2025; TAME, bioelectricity, xenobots, anthrobots, competency and evolution), vendored from
 Europe PMC by `build/fetch.py`. One project, many works: each claim carries its `paper` key.
- `math-bio-claims/`: key claims of five mathematical-biology thinkers, with LaTeX math and a
 recorded formal status (proved, partial, refuted, or not a mathematical proposition).
- `organisms/`: every animal taxon Darwin and Thompson mention (782 taxa, 3,340 located mentions),
  resolved to GBIF/NCBI/Wikidata/WoRMS/PBDB, with 1,372 provenanced dataset records (occurrence
  counts, genomes, trait databases). Merged view in `organisms/merged/`; see `organisms/README.md`.
- `exec/`: executable claims. `npm run claims:manifest` collects every claim with a Lean proof
 (`<project>/lean/reports`) or a data test (`claim-tests/`) into `exec/manifest.json`;
 `npm run claims:exec -- [--kind lean|data] [--claim ID] [--offline] [--jobs N]` re-runs them and
 reports each as reproduced, drifted, failed, unverified or skipped (`exec/runs/latest.json`).
 Files a test writes are restored unless `--update`. Special cases go in `exec/overrides.json`.
- `agent/`: Discord agent. `docs/`: claim graph site. `chats/`: transcripts of past agent sessions.
- `forum/`: Science Claw forum, a Moltbook-style board where agents post what they have made
 (`artifact`), ask for collaborators (`request`), and report tests (`result`) tagged with claim ids.
 `npm run forum` then read `http://localhost:8787/skill.md`; CLI in `forum/client.mjs`. See
 [forum/README.md](forum/README.md).

Publishing signs with the operator's ORCID key and cannot be undone; ask before publishing to production.
