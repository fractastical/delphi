# Frontier execution board

Coordinator: codex-03. Updated October 31, 2026, 02:34PM PDT.
Canonical repository: kganjam/delphi-frontier; root task branch: codex/frontier-demo-20261031.
GOAL.md and SPEC-005 through SPEC-008 define acceptance. This board supersedes the earlier 1:48pm snapshot.
Every status distinguishes implementation, integration, publication and biological validation.

| Priority | Deliverable | Owner | Status / next acceptance |
| --- | --- | --- | --- |
| P0 | Public site and separate database | codex-03 | Live at frontier.morphoswarm.ai; PG16 port5471; public reads, credentialed writes; Orchestra still IP/token protected |
| P0 | Studio, readable claims, graph and semantic search | claude-02 + codex-03 | Public Studio release deployed; exact-pin/browser checks and13 deployed checks passed; independent critique recheck underway |
| P0 | Live vector index | dx-submit | 2444 public record/artifact documents embedded,49 Gemini requests; pgvector index live; ten-minute bounded refresh installed; API integration tested |
| P0 | Generic Project and anchored Annotation | guilds completed; codex-03 integrates | Migration applied after backup; old-version/hash tests passed; live project import and authenticated annotation UI pending |
| P0 | Remote public-read/authenticated-write MCP | native mechanobio worker + codex-03 | Published https://frontier.morphoswarm.ai/mcp; officialSDK12 production checks passed; public reads, individual credentials for writes; receipt deploy/receipts/mcp-public-check.json |
| P0 | Interactive simulation widgets | native bioelectric worker + site | Actual HH and motor-clutch subprocess previews,35 adapter/HTTP tests; public UI deployed and actual browser preview checked |
| P0 | Regional assurance, interface matrix, equation registry | native bioelectric worker | SPEC-008; real receipt aggregation underway; unknown empirical accuracy stays unknown |
| P0 | Adaptive candidate comparison and simulation accuracy | native mechanobio worker | Frozen three-fin-candidate assay with shared parameter draws, grid/model discrepancy, sensitivity and actual rendered outputs |
| P0 | Complete citations and bidirectional lineage | dx-corpus + codex-03 | Source→Claim→Equation/Model→Action→Evidence/Artifact→Project/region; import remaining bundles and audit missing links |
| P0 | Independent browser critique | dx-critic-r1 | Initial desktop/mobile audit complete; five major findings; source-download and table fixes integrated; recheck new deployed release |
| P0 | Goal/resource/progress surface | native resource_scaling + codex-03 | Current provider inventory and blockers being committed; no inferred spend or invented GPU utilization |
| P1 | Solver and meaningful Lean checks | integrated guilds/critic | Constraint solver and parameterized proofs with failing mutants executed; arithmetic/model scope only |
| P1 | BioModels, glide, fin mechanics, RD videos | integrated workers | Four videos live; corrected common-launch glide and six print forms integrated; no calibrated organism validation |
| P1 | Bioelectric and mechanobiology models | native workers | 49 HH parameter runs,600 motor-clutch/SLS runs, real videos and controls integrated; cell/tissue-to-fin transfer unknown |
| P1 | Genomic/tissue/cell data | claude-11 + corpus | Source retrievals,22 gene rows,24 draft records, source cards and plots integrated; import remains distinct from validation |
| P1 | Delphi live ingestion and MorphoLib/MorphoEval | claude-04 / claude-06 | Refresh source inventories and import bounded provenance-preserving bundles; 1,190 canonical Delphi claims and 73 MorphoLib records imported_unreviewed |
| P1 | Autoformalization | dx-market-r1 | Reassigned from authentication-blocked director; actual LLM proposal plus bounded checker, translation assumptions explicit |
| P1 | Fish scale formation and geometry | claude-05 | New source-grounded growth/pattern model assigned after six printable forms/turntables; distinguish abstract pattern from tissue validation |
| P1 | Full lifecycle and living-bioprint equations | claude-11 | Development/growth/maintenance/function and transport/viability/material constraints; sourced slice assigned, full living fish not established |
| P1 | Foundation-model assays and OpenResearch | claude-12 + GPUops | Evo2 arm B running at2:32pm; Scientific AI probes include maintenance failures; actual OpenResearch local analysis imported |
| P1 | Claim reuse, attention and epistemic action | market completed; root integrates | Actual pinned-input reuse receipt includes null result; exact-rational belief solver live; no measured swarm/scaling advantage |
| P1 | Prior-art differentiation and pitch | claude-15 | Revision assigned around organism design exposing knowledge gaps, regional assurance and reusable evidence |
| P1 | Print props and manufacturing | claude-05 | Six meshes and geometry checks; turntables ready; physical printing, printer/resin selection and living bioprinting unverified |
| P2 | Apex redirect and old Studio preservation | codex-03 | Only after new-site acceptance; studio.morphoswarm.ai retained; apex unchanged |

## Deadline release queue

- [x] Dedicated infrastructure lead assigned: native infra_director owns the ready queue, dispatch coordination, dated provider snapshots and useful utilization. GPUops and bioservices retain their current jobs; no duplicate dispatch.
- [x] Knowledge bottleneck measured: the client waited for 27 catalogue requests (~7.3 MB) before rendering. Backend hydration separately opens one connection per result. These are measured causes, not an assumed overload.
- [x] Site branch ba436d1 implements cursor infinite scroll, abort/retry/loading/end states and accessible Load more; 43 browser tests reported by its author. Root integration/deployment pending.
- [x] Same branch puts the fish above Frontier questions and adds the six-model printable selector to both Home and Frontier. STL downloads were individually fetched and digest checked on the live site; printer preparation remains unverified.
- [x] MCP branch b97f88c adds nine bounded discovery/project/artifact/calculation tools; author reports 34 official SDK tests. Root integration/deployment pending. Existing public endpoint passed 12 root production checks at 2:07pm PDT.
- [ ] Deploy and independently check one exact combined release, including the Knowledge fixes, fish/download placement and expanded MCP.
- [ ] Add exact-version project/subsystem design challenges, cited evidence, alternatives and falsifiable next tests. Native resource_scaling owns contract/API/MCP; root owns web integration; site owner owns readable project discussion. Debate does not establish biological plausibility.
- [ ] Publish the prepared wind-tunnel, data-derived controls, scale-growth, lifecycle, behavior and assurance surfaces after checking lineage and numerical limits.
- [ ] Finish corpus imports for new genomics, behavior, lifecycle, assurance and render evidence; audit all Project pins and remaining artifact gaps.
- [ ] Complete independent Playwright review of every route and major interaction on the new public release.

## Current resource evidence

Provider read at 2:32:40pm PDT, October 31: Evo2 arm B aijob-e00pywdm4ta362pwrh RUNNING; wind-tunnel P9 aijob-e00se2hy8rdykbfrbf IMAGE_PULLING. Four active jobs across the shared project. This is allocation state, not GPU kernel utilization. Prior telemetry retains its own time window.

- [x] Canonical Delphi import: all 1,190 Claims in the latest fetched catalogue are present, imported_unreviewed. Root independently queried that count. This does not establish scientific acceptance or future upstream completeness.
- [x] Corpus recovery reports 1,543 imported_unreviewed records, zero forks, all 13 Project members pinned and 73 MorphoLib records imported; exact receipts c324e10/7ac62ae/b58006c. Two MorphoLib models have no remediation Problem, so the correct total is 73, not 75.
- [x] Gemini embedding receipt: 2,444 public record/artifact documents, 49 requests, zero failures at the earlier refresh; ten-minute bounded refresh installed. This is not a current corpus-wide count.
- [x] Fresh Gemini inference succeeded at 2:05pm PDT. Google identity is working; Compute activation remains blocked by UREQ_TOS_NOT_ACCEPTED. No Google VM was created.
- [x] Local bioelectric 49-run atlas, mechanobiology 600-run sweep, fin ensemble and behavior controller produced actual artifacts. Actual OpenResearch local analysis was imported; it was not GPU inference.
- [x] Nebius 4-vCPU batch was rejected because shared CPU quota was full. No job was created by that attempt.
- [ ] Maintain prepared useful batches on warm GPU allocations; current image pulls have taken 6–17 minutes. Never create filler load to report occupancy.
- [ ] Obtain actual provider billing totals; unavailable spend remains unknown, not zero.

## Integration acceptance and next work

- [x] Persistent software MCP round trip recorded in imports/2026-10-31-mcp-roundtrip-receipt.json; not a biological result.
- [x] Public access/security checks recorded under deploy/receipts; no change to Orchestra controls.
- [x] Web/discovery/graph/search/mechanistic integration:162 targeted tests passed.
- [x] Interactive preview:35 targeted tests passed; private writes remain credentialed.
- [x] Project migration/store checks passed; circular snapshot dependency fixed,12 project tests and build check passed.
- [ ] Finish new combined integration run: one old graph fixture used Project as an unknown kind; now updated to FutureRecord because Project became real. Re-run that criterion.
- [ ] Commit/rebuild current site snapshot, run public scratch browser, publish ONE exact SHA, verify live, send independent critic the release.
- [ ] Deploy remote MCP at /mcp using that same release; verify public reads and per-request authenticated writes.
- [ ] Import genomic/simulation/render/geometry bundles and a repinned Project; link locally hosted media by actual digest.
- [ ] Ship equation/assurance registry, candidate comparison, regional overlay and open-question/action links.
- [ ] Ship bounded scale-growth and lifecycle/bioprint constraint slice with explicit missing mechanisms.
- [ ] Audit every displayed scientific artifact for source, producer, parameters, usage and lineage; retain unresolved gaps as findings.
- [ ] Reconcile all SPEC-007/008 acceptance, complete reviewed pitch and 24-hour queue; land validated task work on main.

## Resource and collaboration rules

One writer per worktree; commits pushed after validation. Use bounded process trees: TasksMax128, MemoryMax4G, MemorySwapMax0, RuntimeMaxSec600 unless a justified job has separate bounds. Local numerical threads<=2. One GPU/job, previously authorized team ceiling10, yield to shared demand; never cancel other teams' jobs. No token/reset grants consumed.

Workers report atomically under /data/artifacts/delphi-evolve-rethink/messages. Never inject messages into the user codex-03 pane. Authentication-blocked MCP and autoformalization work was reassigned and preserved. Communication files do not substitute for a tested commit or a provider receipt.

## Remaining proof obligations

No calibrated whole-fish probability, biological manufacturing feasibility, real flight result, independent biological review, measured claim-reuse benefit or collective-intelligence scaling law has been established. Actual zero/null/inconclusive results stay visible. The platform must make those gaps actionable while showing the checked computational work.
