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

Without MCP, the same queries are available as `node mcp/cli.mjs <overview|search|claim|rank|graph|sparql>`.
Outside the repo, `npx -y github:fractastical/delphi` runs the same server.

Default `source` is `local` (repo files, including unpublished drafts). Pass `source: "network"`
for what is actually published. Details, ranking semantics and known gaps:
[mcp/README.md](mcp/README.md).

## Projects

- `darwin-origin/`: 247 claims from *On the Origin of Species*, with dataset-resolvability assessments.
- `math-bio-theorems/`: key theorem claims of mathematical-biology thinkers, with LaTeX math.
- `thompson-growth-form/`, `wolfram-nks/`: in progress.
- `organisms/`: every animal taxon Darwin and Thompson mention (782 taxa, 3,340 located mentions),
  resolved to GBIF/NCBI/Wikidata/WoRMS/PBDB, with 1,372 provenanced dataset records (occurrence
  counts, genomes, trait databases). Merged view in `organisms/merged/`; see `organisms/README.md`.
- `agent/`: Discord agent. `docs/`: claim graph site. `chats/`: transcripts of past agent sessions.

Publishing signs with the operator's ORCID key and cannot be undone; ask before publishing to production.
