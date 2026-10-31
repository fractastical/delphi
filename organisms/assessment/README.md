# Dataset-reliability assessment (the scoring pass)

Scores every dataset record in `organisms/merged/datasets.json` on the five dimensions of
`rubric.json` (source authority, integrity, completeness, independence, authenticity), as the
ontology's dataset convention requires. The assessor is never the agent that vendored the
record. Nothing here is a nanopub yet; these files are the raw assessor outputs that the
nanopub builder will consume, mirroring `darwin-origin/assessment/raw/`.

## Inputs

- `organisms/merged/datasets.json`: the merged records (one per dataset id, with `slices`,
  `distributions`, `counts`, `integrity`, `taxa`).
- `organisms/<project>/<slice>/datasets/<id>.json`: the per-slice originals when a merged
  record has `alternate_identifiers` or conflicting counts.
- `organisms/merged/SUMMARY.md`, section "Identifier conflicts to resolve": disagreements
  between slices that bear on integrity and completeness.
- `rubric.json`: read it fully; score each dimension with its anchors.

## Two levels of scoring

1. **Source databases** (`sources/<source-id>.json`). Source authority, independence and
   authenticity are mostly properties of the database (GBIF occurrence API, NCBI Assembly,
   PBDB, OBIS, WoRMS, AnAge, PanTHERIA, AVONET, Amniote Life-History DB, EltonTraits, FishBase,
   MorphoSource, IUCN, Open Tree, TimeTree, Wikidata, GBIF backbone, NCBI Taxonomy). Score
   each database once, in depth, citing its data paper, governance, licensing and versioning
   pages (real URLs/DOIs only; check they resolve).
2. **Records** (`records/<assessor>/<batch>.json`). Every record gets all five scores. Integrity
   and completeness are re-checked per record, by script: re-resolve the identifier, re-download
   small files and recompute SHA-256, re-query API counts and compare with the recorded value
   (tolerance: relative <= 0.5% or absolute <= 5). Source authority, independence and
   authenticity inherit from the source score unless the record itself shows a problem (an
   accession that does not exist, a count that cannot be reproduced at all, a taxon key that
   resolves to a different name than the label).

Commit the re-check script under `scripts/` so the numbers can be regenerated.

## Output: `records/<assessor>/<batch>.json`

A JSON array, one object per dataset id, in input order:

```json
{
  "dataset_id": "gbif-occurrences-acantharia-2026-10-31",
  "source_id": "gbif-occurrence-api",
  "scores": {
    "source-authority": 0.95,
    "integrity": 1.0,
    "completeness": 0.9,
    "independence": 0.9,
    "authenticity": 1.0
  },
  "verdict": "reliable",
  "confidence": 0.9,
  "checks": {
    "checked_at": "2026-10-31T16:00:00Z",
    "identifier_resolves": true,
    "checksum_match": null,
    "count_recheck": {"recorded": 74583, "observed": 74601, "relative_diff": 0.00024, "within_tolerance": true},
    "taxon_key_resolves_to": "Acantharia"
  },
  "obstacles": ["GBIF counts are live and drift as records are indexed."],
  "rationale": "Two to four sentences justifying the scores, naming what was checked."
}
```

- `scores`: all five dimensions, each in [0, 1] with at most two decimals.
- `verdict`: one of the rubric's four verdicts, consistent with the scores.
- `confidence`: your confidence in your own assessment, in [0, 1].
- `checks`: what the script actually observed; `null` where a check does not apply.
- Never invent a DOI, URL, accession or number. If a check could not run (blocked download,
  authentication), say so in `checks` and `obstacles` and score integrity at most 0.5.

## Output: `sources/<source-id>.json`

```json
{
  "source_id": "gbif-occurrence-api",
  "label": "GBIF Occurrence Search API",
  "homepage": "https://www.gbif.org/",
  "data_paper_or_docs": ["https://techdocs.gbif.org/en/openapi/v1/occurrence"],
  "governance": "Intergovernmental infrastructure; publishers register datasets; records carry per-dataset licences (CC0, CC BY, CC BY-NC).",
  "versioning": "Live index; counts change daily. No snapshot identifier for a count query.",
  "scores": {"source-authority": 0.95, "independence": 0.9, "authenticity": 1.0},
  "known_issues": ["Taxon keys for some higher ranks are orphaned in the current backbone (e.g. Reptilia 358, Actinopterygii 204)."],
  "rationale": "..."
}
```

## Output: `dataset-aliases.json`

Different slices recorded the same shared database under different ids (for example five
variants of the Amniote Life-History Database, six of AVONET). Map every variant to one
canonical id so the nanopub builder publishes each dataset once:

```json
{ "amniote-life-history-database-2015": "amniote-life-history-db-2015-08", "...": "..." }
```

Choose the canonical id as the one with the fullest metadata; do not edit the slice files.

## Rules

- Do not edit anything under `organisms/<project>/`, `organisms/merged/`, claims, assessments
  or nanopubs. Never sign or publish.
- Do not read other assessors' outputs under `records/`.
- Write scripts that can be re-run; keep committed outputs under 1 MB per file (split batches).
- Report: counts per verdict, records whose checks failed, sources with open questions.
