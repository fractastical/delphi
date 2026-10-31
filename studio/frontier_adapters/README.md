# frontier_adapters

Claim, Action and Evidence adapters plus an unsigned nanopub-draft exporter for the Frontier store. Single-reader (corpus
session, Claude Sonnet 5.5), **not Codex-reviewed**. Nothing here submits, accepts, signs or publishes. Provenance: `PROVENANCE.md`.

| module | does |
|---|---|
| `delphi_claim.py` | Delphi claim -> `Claim` draft. Keeps the original id/IRI, nanopub URI and registry (production / test / null = unpublished). Never keeps quote text (digest + locator only). Carries Delphi's source hash only after re-verifying it. Upstream verification labels travel as labelled assertions, never as acceptance. |
| `delphi_mcp.py` | read-only Delphi client: request budget, wall budget, `Retry-After`, stop on persistent 429 / 401 / 403, a receipt per request. |
| `orx_evidence.py` | OpenResearch (`orx`) run -> `Evidence` and `Action` drafts. Reads a live store (`read_store_run`) or an export (`read_run`). Refuses failed runs, tampered snapshots, and kinds other than simulated/predicted. Records per field who supplied it. |
| `orx_replay.py` | EXPLICIT re-execution (`trust_code=True`), with a mutation control that must change the output. `replay_external` handles runs whose inputs/outputs live outside the snapshot. |
| `artifacts.py` | artifact pointers (sha256 + git blob id + size), the store's typed `ArtifactRef`, the downloadable-style manifest, and the absolute-path scrubber/scanner. |
| `nanopub_draft.py` | Claim / Action / Evidence -> unsigned TriG (four named graphs), deterministic. Refuses private records, unlicensed available content, stored quote text, downloadable artifacts with no licence, malformed IRIs. No publish function. |
| `bundle.py` | Claims -> Actions -> Evidence pinned by exact version, drafts, `chain.json`, `manifest.json`. |

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
