# Frontier execution board

Coordinator: codex-03. Started 2026-10-31 11:07 PDT from the fetched foundation.
All work is in isolated task worktrees. Existing subscription harnesses were
reused because they already hold relevant context and paid capacity; no new
metered model was selected. Provider-billed incremental spend is not yet known.

| Priority | Deliverable | Owner | Status / acceptance |
| --- | --- | --- | --- |
| P0 | Product goal, engineering contract, integrated site | codex-03 | Working; SPEC-005 and browser checks |
| P0 | Constraint solver + meaningful Lean boundary | dx-guilds | Delivered; root requested certificate and parameter-correspondence repairs before integration |
| P0 | Flying-fish sourced constraint checker | claude-15's flying-fish-research | Handoff delivered; source-envelope scope needs integration review |
| P0 | Scoped glide simulation + uncertainty | delphi-rethink-nca | Assigned; frozen protocol then convergence and baseline |
| P0 | MCP contribution tools | dx-collab | Integrated; root ran 8 interface tests on integrated code, exit 0 |
| P0 | Typed attention and action adapter | dx-market-r1 | Managed authentication recovered; port in progress |
| P0 | Persistent node + site data/export | dx-collab | Implementing separate PG16 instance and gated web runtime |
| P0 | Multiscale website | claude-02 | Implementing portable data build and functional views |
| P1 | Data/tool indexes and multiscale source cards | dx-fable-lead | Darwin primary texts, precursor hypotheses and source cards in progress |
| P1 | Indexed search and explicit curation | dx-submit | Delivered; ranking and truncation review repairs requested |
| P1 | OpenResearch and evidence/nanopub adapter | dx-corpus | Assigned; inspectable adapter and draft export |
| P1 | Nebius/Google live inventory and bounded execution | dx-gpuops-r1 | Managed authentication recovered; bounded Neumann PDE replay authorized |
| P1 | BioModels model replay | claude-11 | Retrieving public SBML and checking reproducible solver options |
| P1 | Matched-assay biomodel evaluation | claude-12 | Public ProteinGym archive retrieved; frozen protocol before inference |
| P1 | Printable candidate geometry | claude-05 | Three parametric forms; final dimensions must come from engineering results |
| P1 | Explicit factor-graph beliefs | director / nca | Ownership consolidation requested; exact controls required |
| P1 | Typed action-to-artifact provenance | codex-03 | Committed; 14 selected store/provenance checks passed |
| P1 | Whiteboard directions and artifact index | codex-03 | Implemented; 14 selected artifact/register checks passed |
| P1 | Reuse and allocation measurements | dx-market + codex-03 | Pending; matched tasks and receipt-derived counts |
| P1 | Integrated QA, deployment and pitch handoff | codex-03 + existing director | Pending; exact source SHA and checks |

## Integration update — October 31, 12:25 PDT

This section supersedes the kickoff statuses above. It is a coordinator report;
the System endpoint separately measures database and service state.

- [x] First gated release at https://frontier.morphoswarm.ai, source
  `9e6045ed5f219fc6aa82ccafa18eb53fe7d3c0ef`, with a separate persistent PG16
  service. Nine deployed access/rendering checks passed; see
  `deploy/receipts/first-live-check.json`. The apex has not been redirected.
- [x] Live read paths: catalog, lexical search, records, events, artifacts,
  attention, System. Scratch browser also exercised feasible, unsatisfiable and
  unknown engineering results, and exact-rational belief scenarios including
  impossible actions and missing priors. Beliefs are not calibrated forecasts.
- [x] Imported 880 Delphi claims plus two source Actions and two Evidence
  records, all imported_unreviewed. The 21 local claims remain separate versions
  in a different namespace. Imported Action state does not certify execution.
- [x] Imported 250 curated questions, proposed and recorded; together with the
  seven local seed questions the deployed node had 257. No import accepts a claim.
- [x] Typed action proposals and non-executable aggregate plans: 21 selected
  proposal/store/provenance checks passed. A real MCP round trip is still assigned
  to dx-submit; it will be labelled a software integration diagnostic.
- [x] BioModels replay, fin-ray beam simulation, fixed-launch glide comparison,
  reaction–diffusion animations, typed coupling contracts and three print forms
  are integrated in the task branch. Integration is not deployment or biological
  validation. The initial glide Pareto ranking is diagnostic, not a recommendation.
- [x] Numerical coupling/simulation integration checks: 59 passed. Geometry
  checks initially skipped for a missing dependency; their separate run is pending.
- [ ] Finish publishing actual videos, artifact downloads and model-source cards
  (claude-02); show live questions alongside the authored mission diagram.
- [ ] Complete exact-source Lean checks and mesh verification (codex-03).
- [ ] Import the BioModels replay/render lineage and newly sourced flying-fish
  claims/questions after validating their final mappings (dx-corpus, claude-11,
  dx-fable-lead). Rendering has its own Action, separate from numerical replay.
- [ ] Finish System panels and a reproducible release/rollback command
  (claude-02, dx-collab). Root owns deployment and the canonical release SHA.
- [ ] Record a reuse measurement from actual pinned inputs (dx-market-r1).
  The existing allocation experiment is blocked; no collective advantage claimed.
- [ ] Publish the reviewed prior-art comparison and pitch (claude-15).

## Active bounded research queue

| Work | Owner | Current state and bound |
| --- | --- | --- |
| Held-out RD CPU/GPU agreement | dx-gpuops-r1 | CPU reference completed; H100 validation submitted. The CPU step-convergence failure makes the experiment inconclusive regardless of GPU agreement. No conditional expansion. |
| Kir2.1 paired-assay evaluation | claude-12 | 256-variant CPU evaluation completed; hypothesis undetermined. Expanded 6,789-variant follow-up authorized with a new frozen protocol, at most 60 CPU minutes or 30 minutes on one H100. |
| Evo2 regulatory candidate demonstration | claude-12 + dx-gpuops-r1 | Proposed bounded 7B run: at most 32 candidates of at most 2 kb, one H100, 60 minutes including setup, two failures then stop. No functional-expression claim. |
| Two-dimensional fluid simulation | delphi-rethink-nca + dx-gpuops-r1 | Assigned; analytic and conservation controls first, at most 90 minutes implementation plus a 30-minute one-H100 job. Idealized laminar model, no calibrated flying-fish aerodynamics. |
| Typed model and design-primitive index | dx-fable-lead + dx-guilds | Extend current interfaces with explicit implemented, external and missing capabilities. No inferred biological bridge from matching units. |
| Historical claim corrections | dx-critic-r1 | Finite-domain ensemble and cavefish wording corrected, original records retained. Older Lean theorem naming/strict-stability checks in progress. |

Provider-billed spend remains unavailable. The completed GPU pilot failed its
original criterion; its post-hoc interpretation does not change that verdict.
Shared-host load is not attributed to our project or used as utilization evidence.

## Findings to correct during integration

- The earlier site builder counted `def test_` lines as passing tests. Replace
  that count with actual execution receipts or omit it.
- Importable records were described as records in a store; no persistent node
  existed at takeover. Label snapshots accurately and initialize a real node.
- Git timestamps alone do not prove independent witnessing or preregistration.
  Preserve the recorded ordering and hashes without overstating the trust model.
- The inherited code has prose action bounds and no enforced resource runner.
  Report those limits; process scopes enforce actual local runs.
- Existing forecasts, reputation and attention mechanisms must not become truth
  scores or empirical claims of collective advantage.

## Resource and review bounds

All process-spawning test/build/worker runs use a systemd scope with TasksMax=128,
MemoryMax=4G, MemorySwapMax=0 and RuntimeMaxSec=600 unless a separately bounded
job needs a documented limit. CPU threads <=2. Raw GPU jobs remain with their
assigned owner, one GPU per job, at most the previously authorized ten in total,
yielding to other teams; never cancel others' work. Do not consume reset grants.

No website publication broadens the existing audience. New Sites start private.
No external emails or team outreach are authorized by this build board.

## Current communication protocol

Workers write atomic reports under
`/data/artifacts/delphi-evolve-rethink/messages/<role>-to-codex03.md`.
They must never inject tmux input into the user's `codex-03` pane. The coordinator
polls these files and owns integration and publication. Recovered workers are
`dx-market-r1` and `dx-gpuops-r1`; their original sessions have stale credentials.
