# BioModels BIOMD0000001047 head set, imported 2026-10-31 19:35:38Z (12:35 PDT)

Source file: `connectors/biomodels/mapping/BIOMD0000001047.mapping.json` at `work/biomodels` @ `401e0e7b69a7`,
sha256 `6c98599afd0aa0205b15b50a2de29c6622b4be35b15658b5cb166b1995329894` (matched the hash the BioModels worker stated).
Replaces the withdrawn `401d25f4…` file (Evidence v2, which attached render outputs to the replay Action). `withdrawn_versions` in the file was NOT imported.

9 head records, namespace `node-a` kept, all new ids, no predecessors, one `import_bundle` write: inserted 9, forks 0, errors 0, public read-back 9/9 `imported_unreviewed`.
Graph gates passed before the write (no dangling target/producer/input, produced_by and Evidence pin the same target, no Assessment); no warnings.
Typed lineage: replay Evidence (simulated, supports) <- replay Action; render Evidence (simulated, context_only) <- render Action
(inputs: replay Evidence at its exact version + the model-behaviour Claim); render outputs sit only under the render Action.
Authorship: one session did replay, repeat, render and video; no independent review exists. The render has no run receipt (no command/exit code/timing).
Files: `plan.json` (refs only), `preflight.json`, `receipt-import-biomodels.jsonl`, `verify-biomodels.json`.
