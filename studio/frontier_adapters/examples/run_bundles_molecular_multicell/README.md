# OpenFold2, Morpheus and atomistic-MD run bundles

Frozen from root tip `17edd4480f4616de0e930cec02e8453fb237e40f` by
`python3 -m frontier_adapters.run_bundles --repo . --source-commit 17edd4480f4616de0e930cec02e8453fb237e40f --only openfold2 morpheus md`.
Three bundles: openfold2 (5 records), morpheus (8), md (11). Imported status is the importer's call; these files are proposals until root imports them.

- Morpheus is PARTIAL: local arms were capped before completion; the provider baseline reached t=2.0 and the job FAILED with only the baseline recovered.
- MD keeps the failed first GPU attempt, the CPU run, the three-seed CUDA run and the cross-scale gate refusal as separate records. Render is context-only.
- Artifacts are `urn:sha256:` references: no URL, no licence, no bytes served.
