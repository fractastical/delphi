# Live Delphi run, 2026-10-31 20:34–20:40 UTC (13:34–13:40 PDT)

Server `delphisci` 0.2.0 at `https://delphisci-mcp.fly.dev/mcp`, keyless, read-only tools only. `healthz` said built
`2026-10-31 20:10`, 3,672 files. `fractastical/delphi` `main` was `2452a0a58fab5e396ecc122eb38875b05ac5d5a5` (committed 20:10:43Z)
when read. That is the branch tip, not a proof of what the server deployed. 124 logged requests, all HTTP 200, none rate-limited
(`receipts.jsonl`; the two session-setup posts are not logged). Code: `frontier_adapters.delphi_live` 0.1.0 on branch
`work/delphi-live-ingest`. Single-reader, not Codex-reviewed.

## What Frontier already held, and what changed

The baseline is the 880 Claims imported at 19:05 UTC (`examples/live_import`). **All 880 frozen drafts rebuild the exact imported
versions** (`summary.json` `baseline`), so the diff below compares against what the store holds.

| status | claims | meaning |
|---|---:|---|
| relocated | 749 | no content or label change; Delphi moved the TriG file (`books/<d>/…` or `<d>/…` → `claim-sources/<d>/…`) |
| labels_changed | 131 | content identical; Delphi's `evidence`/`evidenceKind` labels appeared (the claim tests below) |
| content_changed | **0** | so no successor versions and no forks (`records-updates-FORK.json` is empty) |
| new_to_store | 310 | Levin claims: catalog-only at 18:25Z, now with local unsigned nanopubs. Still on **no registry** and absent from the network source |
| removed_upstream / withheld | 0 / 0 | |

The catalog id set is byte-identical to the 18:25Z run (`catalog_sha256` `ea1bb3a3…`): **this build added no claim ids.**

## New records (plan `plan-new.json`, 5 bundles, 443 records, plan sha256 `5c7d30f4…`)

* **310 Claims** (`node-a`, Levin), `publication_state` `delphi_local_unsigned_nanopub: in Delphi's repository, on no registry`.
* **133 Evidence** from Delphi's 134 claim-test nanopubs (`evidence_kind: source_assessment`). Upstream verdicts are 78 supports,
  25 mixed, 22 refutes and 9 inconclusive. One `refutes` test (`levin-2022-tame-19-screens`) names a claim id that is in neither
  Delphi's catalog nor Frontier, so it is **withheld**. The 133 carry `relation` 78 supports, 21 refutes and 34 unspecified
  (mixed and inconclusive are not mapped). **All 134 tests say `preregistered: false`.** Data kinds: 67 biological,
  60 computational, 4 physical, 3 not stated. 244 dataset declarations, 158 of them with a sha256. No byte was fetched, so none
  is an `ArtifactRef`.
* Gates: `offline-gates.json` (with the rebuilt baseline: 0 refused; control without it: 131 refused, as it must be).
  `trial-import.json`: a scratch PostgreSQL store holding the rebuilt 880 imported the plan with **0 forks**. 443 records came back
  as head and `imported_unreviewed`, and a re-run changed no count.

## Inventoried, not imported (counts from `inventory.json`)

* 2,338 dataset-resolvability assessments (1,844 of type 0.2.0 on 922 claims; 494 of type 0.1.0 on 247 claims), each by 2 LLM
  assessors. These are upstream opinions; only their count travels in `prior_review`.
* Organisms: 938 taxa, 1,679 datasets, 7,949 book mentions (`delphi_organisms`, "measures completeness of our records, not dataset
  reliability").
* `cell-geometry`: 32 graphs, so 8 nanopubs. A read truncated at 600 rows showed 7 of them (5 datasets, 2 evidence); the 8th was not seen. Also the `rubric-unsigned` graphs (2 nanopubs), and Science
  Claw forum posts.
* LanguageModel provenance that the claim nanopubs now carry (which model extracted the claim, 74 claims). It is not carried here:
  it would change the content of claims that have not otherwise changed. Reading it as an ISBN was a mapping bug, now fixed.
* Network source: 883 claims (Levin absent; a 3-claim `morphogenesis` domain present there and not locally); 1,224 assessments.
  Trusty URIs were not dereferenced.

## Files

Committed here: `inventory.json`, `summary.json`, `claim-diff-compact.json`, `plan-new.json`, `offline-gates.json`,
`trial-import.json`, `receipts.jsonl`, and `fixtures/` (the rows of one claim-test nanopub, for the tests). The bundles, records,
`claim-context.jsonl` (the readable index, 1,190 rows), full diff and snapshots total 21 MB. They live under the root named in
`artifact-manifest.json`, with each file's sha256.
