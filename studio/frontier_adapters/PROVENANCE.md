# Provenance of this package

Ported from the `delphi-evolve` repository, branch `work/corpus`, commit `4c51ad81dc085c64cfed508e3fba7f83eb39773e`
(status record `07a7ab3`), authored by the corpus session (Claude Sonnet 5.5). Single-reader, not Codex-reviewed.

Changes made on porting into Frontier (core `1b329cc`): Frontier models are imported directly (no `$FRONTIER_PATH`); no absolute
paths remain in code, examples or tests; the Delphi client has an explicit request budget, `Retry-After` handling and a
persistent-429 stop; Delphi's changed response shapes are handled (SPARQL rows as an object keyed by index; Markdown preface
before the overview JSON); unpublished catalog-only claims are supported; artifacts are typed `ArtifactRef`s; Actions carry
`inputs`; Evidence carries `relation` and `produced_by`.

Reused from elsewhere, by reading, not copying: TriG layout and the `de:` vocabulary from codex-api
`claim_runtime/trig.py`; determinism rules and the refusal-to-publish stance from MorphoSwarm `nanopub/build.py` and
`nanopub/publish.py`. No code was imported from either.
