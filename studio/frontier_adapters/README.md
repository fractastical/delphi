# frontier_adapters

Claim, Action and Evidence adapters plus an unsigned nanopub-draft exporter for the Frontier store. Single-reader (corpus
session, Claude Sonnet 5.5), **not Codex-reviewed**. Nothing here submits, accepts, signs or publishes. Provenance: `PROVENANCE.md`.

| module | does |
|---|---|
| `delphi_claim.py` | Delphi claim -> `Claim` draft. Keeps the original id/IRI, nanopub URI and registry (production / test / null = unpublished). Never keeps quote text (digest + locator only). Carries Delphi's source hash only after re-verifying it. Upstream verification labels travel as labelled assertions, never as acceptance. |
| `delphi_live.py` | live Delphi run: server inventory, a per-claim diff against the versions Frontier imported (new / unchanged / relocated / labels_changed / content_changed / removed / withheld), claim-test nanopubs -> `source_assessment` Evidence, and a readable claim-context index. Imports nothing. |
| `delphi_mcp.py` | read-only Delphi client: request budget, wall budget, `Retry-After`, stop on persistent 429 / 401 / 403, a receipt per request. |
| `orx_evidence.py` | OpenResearch (`orx`) run -> `Evidence` and `Action` drafts. Reads a live store (`read_store_run`) or an export (`read_run`). Refuses failed runs, tampered snapshots, and kinds other than simulated/predicted. Records per field who supplied it. |
| `orx_replay.py` | EXPLICIT re-execution (`trust_code=True`), with a mutation control that must change the output. `replay_external` handles runs whose inputs/outputs live outside the snapshot. |
| `artifacts.py` | artifact pointers (sha256 + git blob id + size), the store's typed `ArtifactRef`, the downloadable-style manifest, and the absolute-path scrubber/scanner. |
| `nanopub_draft.py` | Claim / Action / Evidence -> unsigned TriG (four named graphs), deterministic. Refuses private records, unlicensed available content, stored quote text, downloadable artifacts with no licence, malformed IRIs. No publish function. |
| `bundle.py` | Claims -> Actions -> Evidence pinned by exact version, drafts, `chain.json`, `manifest.json`. |
| `engineering_manifest.py` | producer receipts (engineering / formal) -> PROPOSED Problem, Claim, Action and Evidence drafts, frozen as an importable `frontier-bundle-0.1`. Added by the market worker; see the section below. |
| `morpholib.py` | MorphoLib/MorphoEval Tier-A loops -> PROPOSED Claim (`source_statement`), Evidence (`source_assessment`), Problem drafts, equation and model indexes, frozen bundles. Reads git blobs only; runs nothing from upstream. See `docs/morpholib-import.md`. |

## Example: claims -> evidence -> artifacts (`examples/nca_chain/`)
Real OpenResearch run `f81c0b68` (local backend, **not hosted compute**): the preregistered analysis of a finished nonlinear
sweep. Two Delphi claims (`turing-ddi`, `turing-wavelength`) -> two Actions (`inputs` pin the Claims) -> two Evidence records
(`relation: qualifies`, `produced_by` pins the Action, 9 typed artifacts) -> artifacts pinned by git commit and sha256.
`chain.json` is the graph with every link check; `replay_report.json` the replay and its controls;
`artifact-manifest.json` the manifest (digest + locator, no bytes, **not yet hosted**, no licence asserted).
Build it: `PYTHONPATH=. ORX_STORE=<openresearch data dir> NCA_REPO=<delphi-evolve checkout> python3 -m frontier_adapters.examples.make_nca_chain`.

## Tests
`python3 -m pytest frontier_adapters/tests -q` (bounded: `systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 -p TasksMax=128 -p RuntimeMaxSec=600 ...`).
Offline by default. `NCA_REPO` and `ORX_STORE` enable live re-hashing of the artifacts and a live store read; `rdflib` enables an
independent TriG parse. Each is reported as **skipped with its reason** when absent, never as passed.

## Bulk import (`delphi_bulk.py`, `delphi_curate.py`; run record in `examples/bulk_run/`)
Read-only, checkpointed, resumable; limits are parameters (`min_interval`, `max_requests`, `max_wall_s`); stops on persistent 429 or any 401/403.
Priority order: math -> Thompson math claims -> Thompson rest -> Levin -> Darwin -> Wolfram (an order, not a judgement). Output is
**proposed** `Claim` drafts in separate files by registry (production / test / unpublished); a draft that fails validation goes to `errors.jsonl`,
not away. Bulk output (about 6 MB) is not committed; the checkpoint, receipts and curation report are.


## Engineering and formal receipts (`engineering_manifest.py`; frozen output in `examples/engineering_manifest/`)
Market worker, single-reader, **not Codex-reviewed, not independently reviewed**. Reads immutable git blobs at a pinned commit and never writes to a store or
executes producer code; producing a bundle is not importing it (corpus owns imports). First slice, 9 records (limit 16):

* **fin mechanics** (6): Claim (derived critical stiffness `EI_crit = 1323/2048000 N m^2` for a *declared illustration* request) -> Action(sim) -> Evidence(sim, `unspecified`)
  -> Action(render, `inputs` pin the simulation Evidence) -> Evidence(render, `context_only`) ; Problem (the producer's measurement question, `recorded`, nothing invented).
  Simulation and render are separate Actions because they have different code and different output hashes; the producer records no creation time for either, and the bundle says so.
* **Lean certificate** (3): Claim (three declared constraints have no common solution) -> Action(Lean kernel check) -> Evidence(`formal`, `supports` declared by the adapter, statement
  fidelity unreviewed). The z3 search that produced the certificate is in provenance, labelled "re-checked by z3 only"; it is not separate evidence.
* **Every hash the producer states is recomputed from the blob** (outputs, code files, combined code hash, request, Lean sources, certificate text) and a mismatch refuses the whole
  chain naming the check; 15 must-fail controls edit a throwaway copy. Lean positive exit 0, standard axioms only, and all four negative blocks rejected are re-read, not trusted.
* Imported Actions say "NOT executed by Frontier". Evidence says the same producer made claim and result (`independent_of_claim: false`). All artifacts are the store's `ArtifactRef` via
  `artifacts.to_artifact_ref`: `urn:sha256`, availability `referenced`, no licence, no URL, no bytes. Nothing is claimed about site hosting.
* Not in this slice: glide fixed-launch and RD video manifests, and the print manifest. **Printer slicing is unknown** in the producer's material.

Freeze: `python3 -m frontier_adapters.engineering_manifest --repo . --source-commit <rev> --out <dir>` (records pinned to the commit's time; same input, same bytes). Checked on an ephemeral
store: the bundle imports (all `imported_unreviewed`) and `ArtifactIndex` then finds the certificate and the three simulation outputs.


## Live Delphi ingestion (`delphi_live.py`; run record in `examples/delphi_live/`)
Read-only and keyless, through the same budgeted client. The forum and proposal tools the server also offers are listed in the
inventory and **never called**. One run: `python -m frontier_adapters.delphi_live --out DIR --baseline-drafts <frozen bulk drafts>...
--imported-plan examples/live_import/plan-claims.json --imported-records examples/nca_chain/records.json`.

* **Baseline first.** The frozen drafts must rebuild the exact versions Frontier imported (`reproduce_imported`); otherwise the
  diff would compare against something Frontier does not hold.
* **Diff by kind of change, not by count.** Repository path moves (`relocated`) and label/opinion moves (`labels_changed`) make
  no successor version. A `content_changed` claim becomes a successor whose `predecessor` is the imported version, in a SEPARATE
  plan: `Store.import_bundle` records it as a fork and leaves the head alone (SPEC-004), so applying it is the importer's choice.
* **Claim tests are Evidence, not acceptance.** `evidence_kind: source_assessment`; the upstream verdict, confidence, data kind and
  preregistration flag stay raw in `provider_assessment`; `relation` only for a literal `supports`/`refutes`. Dataset checksums are
  Delphi's declarations (`bytes_checked: false`), so no `ArtifactRef` is made.
* Output: `records-new-claims-and-tests.json` (exact Records for `import_cli build --records`), `records-updates-FORK.json`,
  `claim-diff.json`, `claim-context.jsonl` (the readable field contract), `inventory.json`, `receipts.jsonl`, `summary.json`.
