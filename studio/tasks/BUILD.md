# Frontier execution board

Coordinator: codex-03. Updated October 31, 2026, 6:11pm PDT.
Canonical repository: kganjam/delphi-frontier; root task branch: codex/frontier-demo-20261031.
GOAL.md and SPEC-005 through SPEC-015 define acceptance. The latest dated checkpoint supersedes older status snapshots.
Every status distinguishes implementation, integration, publication and biological validation.

## Current checkpoint — October 31, 2026, 6:11pm PDT

- [x] Site/MCP release `5e27158` is live. Root ran 22 focused browser/blueprint
  checks (85 deselected), then 8 deployed public-read checks and 37 MCP checks.
  Desktop/mobile downloads were inspected: 49 links, no viewport overflow;
  the headless browser used the labelled static-render fallback for the fish.
- [x] Home now has a direct v3a scale-relief STL link and an expandable catalog
  of print editions, stands and candidate GLBs next to the main viewer.
  Manifest digests are checked before publication. The public repository is
  `kganjam/delphi-frontier`; all new implementation stays there.
- [x] Genetic blueprints, 19 regulatory actors, 47 claim-use rows, source links,
  regulatory map, claim-reuse example and local OpenResearch provenance are live.
  Root checked cached source digests/excerpt presence, not biological truth.
- [x] Prospective experimental-design planner integrated from `cc12164`; root
  ran its 10 focused tests. Its frozen comparison has no observations: mixed
  load/deflection is identifiable under declared assumptions; repeated deflection
  alone is not. This is model-based planning, not an empirical posterior.
- [ ] Claude-02: contextual Experimentation UI; native resource_scaling: bounded
  read-only MCP planner. Claude-14: pinned biodesign compiler and layer lineage.
- [ ] Print priority: selected the larger-fin r3-daane geometry for a fit/balance
  prototype. Independent review found right-fin STL chirality wrong in r1;
  root reproduced it in r3. Claude-05 is producing additive r4-daane-printfix;
  claude-13 reviews it. R3 body alone was shared; fin prints are held.
  No printed mass, flight, catch-load survival or biological buildability claimed.
- [ ] Native ecology canonical simulations/media `335648d` and packet `08e5b77`
  await root integration; claude-10 builds the actual-state viewer. Native
  mechanobio_sim is preparing a separate inverse-pattern NCA training protocol.
- [ ] Infrastructure tip `56a1ed5` plus telemetry `5d37bca` awaits integration.
  Secondary H100 evaluation completed; strict metric audit FAIL is retained:
  zero-amplitude relative metrics are undefined and float32 rounding fails the
  frozen float64 tolerance. Generated fields are finite; no blanket pass.
- [x] Infra reports actual Google allocations: 16 vCPU CFD, 4 vCPU ecology,
  4 vCPU plus one L4 for GPU calibration. L4 setup/controls are ongoing; physical
  stock failures in two other zones were retained. At the delayed 6:05pm PDT
  metric, CFD used 59.60% of its allocation and ecology 96.87% of its allocation.
  These are host measurements, not completed-case counts or biological results.
- [x] The Google 23-genome run completed with 23 archive MD5 checks. Claude-11
  interprets the locus results; source coverage gaps are not gene-loss claims.
- [ ] Integrate and publish corrected print bundle, ecology viewer, experimental
  planner/UI, genomic result interpretation and actual diffusion visuals; preserve
  failed simulations, unresolved connections, and independent review findings.

## Previous checkpoint — October 31, 5:34pm PDT

- [x] Site and MCP release `d531330` deployed: 13 website and 37 MCP checks
  passed. Transient contributor credentials and exact-version discussion/history
  are live. Root browser checks passed; separate route critique continues.
- [x] Fixed public static-asset throttling in the Frontier nginx configuration
  (`d3c8890`): API routes retain request limits; static JS no longer shares that
  limit. Config validation passed; only the Frontier vhost changed, with Orchestra
  hashes unchanged. Independent fresh-browser confirmation remains pending.
- [x] Exact-Claim reuse and independent review readback integrated. Both resulting
  Evidence records are disputed; scoped numerical reproduction does not establish
  biological relevance or independent experimental replication.
- [x] OpenResearch actually ran a Turing calculation and BioModels replay. The
  local-run adapter records provenance/hashes; this is not cloud orchestration.
  Root recomputed all four current BioModels output hashes on this checkpoint.
- [x] Regulatory literature/cell-program map integrated. Native metadata audit
  has 128 retrieved records; root integration is pending. Sequencing matrices
  were not fetched; assembly and biological-replicate mismatches stay explicit.
- [x] Define two controlled behavior/ecology comparisons in SPEC-011 and genetic
  implementation blueprints in SPEC-012, including enhancer/promoter compatibility,
  delivery, integration and autonomous-chromosome feasibility as separate questions.
- [ ] Native mechanobio_sim: real MuJoCo gliding and local collective escape,
  controls before sweeps. Claude-10: viewer of actual saved trajectories.
- [ ] Claude-14: source-backed genetic blueprint package. Claude-02: readable
  Studio implementation view and regulatory map, linked to source/evidence/gaps.
- [ ] Claude-05: first reinforced printable glider revision; claude-07 dynamics;
  claude-13 independent review. Requirements calculations integrated and 14 root
  tests passed. No new assembled print, launch or measured glide is claimed yet.
- [x] Infrastructure reports exact-weight DDPM evaluation recovery COMPLETED;
  strict audit complete, no nonfinite results. It did not retrain the model.
  Reported generation timing is slower than its same-GPU solver comparison.
  Root review/integration of the returned artifacts remains pending.
- [ ] Infrastructure: exact-W1 secondary evaluation, repaired GCP genomics retry,
  and replacement CFD VM using Python 3.12 for the nested archive extraction.
  Both initial CPU VMs stopped at software gates; no completed CFD case or full
  genome survey resulted. Failed outputs were exported and independently hashed.
- [x] Infrastructure's 5:32:37pm PDT provider read: 83 Nebius jobs, 53 ours
  (42 completed, 8 failed, 3 cancelled), 30 unattributed. Zero active/queued ours
  at that instant; one unattributed job running. Recovery telemetry separately
  reports 85.64% mean GPU utilization during its measured window, not now.

The owner table below retains earlier assignments as history; the current work
is governed by the checkpoint above. No unmeasured spend, activity or biological
success probability is inferred from resource reservations or completed software.

| Priority | Deliverable | Owner | Status / next acceptance |
| --- | --- | --- | --- |
| P0 | Public site and separate database | codex-03 | Live at frontier.morphoswarm.ai; PG16 port5471; public reads, credentialed writes; Orchestra still IP/token protected |
| P0 | Studio, readable claims, graph and semantic search | claude-02 + codex-03 | Public Studio release deployed; exact-pin/browser checks and13 deployed checks passed; independent critique recheck underway |
| P0 | Live vector index | dx-submit | 2444 public record/artifact documents embedded,49 Gemini requests; pgvector index live; ten-minute bounded refresh installed; API integration tested |
| P0 | Generic Project and anchored Annotation | guilds completed; codex-03 integrates | Migration applied after backup; old-version/hash tests passed; live project import and authenticated annotation UI pending |
| P0 | Remote public-read/authenticated-write MCP | native mechanobio worker + codex-03 | Published https://frontier.morphoswarm.ai/mcp; 19 tools, 35 official SDK production checks passed at 3:45pm PDT; public reads, credentialed writes; receipt deploy/receipts/about-mcp-live-check.json |
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

## Current integration checkpoint — October 31, 3:32PM PDT

This section supersedes the earlier resource snapshots below; their timestamps remain as history.

- [x] About overview, people/agents, docs and inspirations, plus Generative Biology research thesis implemented. Primary prior art includes physics-informed diffusion, GenCFD and biological cellular-Potts diffusion surrogates; novelty is an integration hypothesis. Root browser checks exercised five routes at desktop/mobile, all six equation controls, document drawer and About menu; screenshots inspected. Publication pending the shared release.
- [x] Actual mesh viewer, wider Home, sourced anatomy framing and System build/usage narrative integrated. Independent critique still requires final checks for Frontier table width, phone Knowledge filter width, navigation and raw JSON presentation.
- [x] H100 OpenMM run recovered: three 100 ps trajectories, 101 saved frames each; CPU/CUDA numerical checks and output hashes recorded. Actual-state render and descriptive ensemble integrated. No equilibration, biological accuracy or fin modulus claimed.
- [x] BETSE generic tissue run, Morpheus partial local run, Kcnj13 hosted OpenFold prediction and associated media integrated. New Morpheus CPU full-horizon run is recovered by infrastructure; scientific analysis/curation still pending.
- [x] Controlled 3D WaterLily GPU job admitted at 3:27:22pm PDT, one H100. Provider read at 3:27:58pm showed PROVISIONING. Frozen numerical checks precede candidate cases; no completed GPU/physical validation claimed yet.
- [ ] User-requested actual conditional diffusion pilot: dx-market-r1 owns frozen RD solver data, parameter/seed holdouts, small DDPM training, baseline evaluation and claim/equation provenance. Infrastructure owns one-H100 dispatch; packet preparation underway. No trained result yet.
- [ ] Anatomy/appearance improvement: claude05 owns additive v3 fish with biological fin outlines, rays/membranes, scales and explicitly assumed pigmentation; claude10/site own interactive presentation. Same geometry must be reused for physical comparisons.
- [ ] Publish warmstart-v3.tar.xz (exact SHA in molecular manifest), then infrastructure can dispatch the frozen MD continuation after higher-priority RD/3D packets.
- [ ] Controlled collective-capability pilot: resource_scaling preregisters three matched-budget evidence-synthesis arms using primary public papers, 27 bounded model calls. No collective improvement or scaling law established yet.
- [ ] Public repository: source/history and current tree scans completed and classified, public-web hardening integrated. Final updated scan, regression checks, main-branch landing and visibility change remain. Current repository still private. No active account credential identified by the scoped scans; expired public Figshare download URLs were removed from current receipts.
- [ ] Final release: regenerate snapshot, test combined exact commit, deploy web + design-context MCP, verify public reads/authenticated writes and media. Current live release remains c804b317b2afe3e6d180141de134e03606c2e910.

System reporting must use dated actual hackathon receipts: available shared capacity is not our utilization; completed jobs are not current GPU occupancy; missing total tokens/spend stay unknown. Public pages should make meaningful results and limitations easy to inspect without self-awarded judging scores or earlier in-house-project marketing history.

## Deadline release queue

- [x] Dedicated infrastructure lead assigned: native infra_director owns the ready queue, dispatch coordination, dated provider snapshots and useful utilization. GPUops and bioservices retain their current jobs; no duplicate dispatch.
- [x] Knowledge bottleneck measured: the client waited for 27 catalogue requests (~7.3 MB) before rendering. Backend hydration separately opens one connection per result. These are measured causes, not an assumed overload.
- [x] Site branch ba436d1 implements cursor infinite scroll, abort/retry/loading/end states and accessible Load more; 43 browser tests reported by its author. Root integration/deployment pending.
- [x] Deployed branch puts the fish above Frontier questions and adds the six-model printable selector to both Home and Frontier. STL downloads were individually fetched and digest checked on the live site; printer preparation remains unverified.
- [x] MCP branch b97f88c adds nine bounded discovery/project/artifact/calculation tools; author reports 34 official SDK tests. Root integration/deployment pending. Existing public endpoint passed 12 root production checks at 2:07pm PDT.
- [x] Deployed exact release c804b317b2afe3e6d180141de134e03606c2e910. Root 43 browser checks and scratch runtime checks passed; public web 8 checks and expanded MCP 33 checks passed (18 tools, actual bounded calculations). Native performance read: first 50 claims 322.7 ms, one 274089-byte request; previous 26 requests / 7.09 MB and~10.14 s. These are single captured samples, not latency guarantees.
- [x] Implement exact-version project/subsystem challenges: contract/API/MCP plus web GET context are integrated at a77d35b; 88 focused tests passed. Four source-context challenges were submitted as proposed Annotations and anonymously read back through exact Project context. Receipt: imports/2026-10-31-design-challenges-receipt.json. These are authored critiques, not independent reviews or accepted conclusions.
- [x] Deploy the design-context API and readable project discussion together. The About release exposes 19 MCP tools, including exact-version design context. Four proposed challenges remain authored critiques rather than independent reviews. Production readback is recorded in deploy/receipts/about-mcp-live-check.json.
- [ ] Publish the prepared wind-tunnel, data-derived controls, scale-growth, lifecycle, behavior and assurance surfaces after checking lineage and numerical limits.
- [ ] Finish corpus imports for new genomics, behavior, lifecycle, assurance and render evidence; audit all Project pins and remaining artifact gaps.
- [ ] Complete independent Playwright review of every route and major interaction on the new public release.

## Current resource evidence

### Latest checkpoint: October 31, 3:50pm PDT

- [x] The About release is live, including the generative-model roadmap, team and documentation routes, actual GLB viewer, simulation media and System build evidence. Exact release SHA and check provenance are in deploy/receipts/about-release-checks.json. At 3:45pm PDT, 13 public web checks and 35 official MCP SDK checks passed; the latter discovered 19 tools. These checks do not establish biological validity or resolve every usability finding.
- [x] Imported five immutable multiscale bundles: 39 records (9 Claims, 14 Actions and 16 Evidence) covering geometry, scale growth, behavior, lifecycle and BETSE. Exact-version readback found all 39 imported_unreviewed, no forks and no readback problems. Actions remain proposed; importing them did not launch work. Receipts and frozen plans are under imports/2026-10-31-multiscale/. Three lineage warnings remain: a geometry output, a check certificate and a comparison log do not use the generic output role. Existing Project pins were preserved.
- [x] Infrastructure's 3:50:19pm PDT provider snapshot lists 80 shared jobs: 35 confirmed ours and 45 other/unattributed. Ours: 24 completed, 5 failed, 3 cancelled, 2 running and 1 pulling an image. Other/unattributed: 32 completed, 10 failed, 2 cancelled and 1 running. Ownership is determined from our recorded IDs/prefixes; the provider returned no owner fields. This is a job census, not measured GPU saturation.
- [ ] Current useful GPU work: conditional molecular-dynamics continuation and repaired 3D flow job running; reaction-diffusion DDPM job pulling its image. Setup and numerical controls precede kernels. Collect actual results before claiming training, scientific success or utilization.
- [ ] Critical independent browser findings still need closure: Frontier table width, mobile Knowledge overflow, mobile navigation access, and large raw System detail expansion. Recheck each fix on the published release.
- [x] Completed the final credential review and incremental scan, merged PR7, and made kganjam/delphi-frontier public at 4:06pm PDT. Anonymous metadata and current README reads passed; public read access does not grant write access. The review scope and retained classifications are in docs/security-review.md.

Earlier snapshots below retain their original observation times and are superseded for current-state reporting by this checkpoint.

Infrastructure lead's provider read at 2:51:49pm PDT: dt/4 RUNNING; perturbation and angle-of-attack jobs IMAGE_PULLING; cylinder STARTING. Molecular dynamics was created at 2:55:36pm PDT. Five jobs are in the infrastructure pipeline; this is not five occupied GPUs. The separate hosted OpenFold2 operation reported QUEUED at 2:56:54pm PDT. Prior telemetry retains its own time window.

| Job / operation | Purpose | Latest reported state |
| --- | --- | --- |
| aijob-e00h6cqxa1c7cwts6y | Frozen 81-case timestep check | RUNNING at 2:51:49pm PDT |
| aijob-e00cqbmnzwmvms8ayr | 357 missing perturbations plus 48 fixed repeats | IMAGE_PULLING at 2:51:49pm PDT |
| aijob-e00saz7cewggkp50d2 | Recover actual flow fields; N1 angles 0/4/12 degrees on two grids | IMAGE_PULLING at 2:51:49pm PDT |
| aijob-e00vga5krqxr3xxc94 | Three-grid/timestep cylinder reference assay | STARTING at 2:51:49pm PDT |
| aijob-e00a3q798jsc6fdbas | OpenMM explicit-solvent collagen, CUDA parity then three 100 ps trajectories | CREATED at 2:55:36pm PDT; not yet a completed trajectory |
| op-5ba1d104dbbcd293 | Hosted OpenFold2, exact unmodified BAF03613.1/Q0KIZ7-matching Kcnj13 sequence | QUEUED at 2:56:54pm PDT; not counted as our H100 allocation |

P9 wind-tunnel completed at 2:40:36pm PDT. Infrastructure lead recovered numeric controls: CPU/CUDA coefficient difference 1.49e-13; drag refinement differences 1.922% and 0.794%. Its 35-sample telemetry window had mean 71.54% and maximum 88% GPU utilization. The field archive exceeded an old 3 MB recovery cap and was discarded; the truncation remains a finding and the next packet reruns recovery with a larger bounded cap. These are low-Re 2D numerical results, not measured flight performance.

## Executable multiscale queue

Every run must retain exact inputs, model/code versions, units, parameter provenance, numerical controls, actual saved states, artifacts and limits. Cross-scale compatibility is not biological calibration. The existing coupling contract remains normative.

| Scale / question | Owner | Active work and next gate |
| --- | --- | --- |
| Molecules: collagen structure and fluctuations | native mechanobio_sim + infra_director | Actual 10,491-atom CPU setup trajectory and force/NVE controls delivered at 5a4b6fa. GPU job above must pass same-job CPU/CUDA parity; actual-state video and source/model matrix follow. A short peptide trajectory does not estimate fin stiffness. |
| Protein structure: sourced ion channel | native resource_scaling | One hosted OpenFold2 operation above; exact 362-aa source sequence, RefSeq discrepancy retained. Single-sequence monomer omits membrane/tetramer/ligands; structure does not establish conductance. |
| Cell/tissue voltage: electrodiffusion | dx-market-r1 | BETSE baseline ran; K-permeability, gap-junction and half-step controls underway. Generic tissue, not calibrated fish tissue. |
| Metabolism: oxygen and biomass feasibility | claude-11 | Zebrafish-GEM/COBRApy actual solves. Unrestricted uptake allowed energy-rich compounds and is retained as a failed physiological assumption; explicit assumed nutrient medium being checked. Steady-state flux is not organism growth. |
| Growth: intracellular dynamics to tissue | claude-06 | Morpheus ODE to cell division to cytokine PDE feedback, source model plus disabled-feedback controls. Generic multiscale example; fish correspondence unknown. |
| Geometry/flow: 3D Navier–Stokes | claude-04 | WaterLily/mesh-body feasibility and reference controls before exact fish geometry. Actual units, mesh resolution and Reynolds-number limits required. |
| Flow to fin deformation | claude-07 | New coupling adapter: pressure to traction to ray load, conservation and analytic controls. Await a dimensioned compatible flow artifact; lattice units or 2D projections cannot silently become whole-fin pressure. |
| Scale formation and fish geometry | claude-05 | Corrected scale-model labels integrated; model mismatch retained. Biological-scale mesh 994aac4 awaits integration; additive corrected print v2 task dispatched, old files preserved. |
| UI and independent critique | claude-02 / dx-critic-r1 | Design discussion and simulation cards; all remaining public routes/major interactions assigned for audit against exact deployed SHA. |

Next valuable couplings are the actual Morpheus closed loop and pressure-to-fin mechanics. Additional generic parameter sweeps do not substitute for either. FEBio multiphasic/growth and PhysiCell intracellular ODE models are sourced candidates for later work; no execution is claimed.

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
- [x] Deploy remote MCP at /mcp using the same release; public reads and invalid/anonymous write rejection checked. Typed authenticated proposal/lease flow exercised in isolated SDK tests; shared contributor identity checked against production without a scientific write.
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

## Public-source and geometry integration checkpoint

- [x] Three sourced ray-fan fish candidates and additive corrected print forms integrated. Root ran81 focused geometry/print checks.
- [x] Full-horizon tissue analysis, metabolic solves, pressure-transfer refusals, diffusion controls and resource receipts integrated; root ran117 focused checks.
- [x] Viewer review identified and repaired small-mesh picking precedence, transformed-distance errors and missing destruction on candidate/navigation changes. Source materials and exact geometry hashes are preserved.
- [x] Root ran19 targeted combined Home/About/mobile/table/error browser checks;50 unrelated cases were deselected. New geometry is not biological validation.
- [x] Published the selectable ray-fan candidates, critical browser fixes and public-repository labels in release `c1ad527e7c1a0cc1494def66fae3e12db6ef5f92`. Public website 13 checks and MCP 35 checks passed at 4:14:54pm PDT; receipts are in deploy/receipts/rayfan-*.json. Independent critique of this exact release remains in progress.
- [x] Integrate returned 1 ns molecular branches with all three frozen-window outcomes and the four-case 3D flow bundle. Primary diffusion training is tracked separately below.
- [x] Commit the matched-budget synthesis comparison as a ceiling/null result; all arms 16/16 does not establish collective advantage. Website exposure remains part of the next release.

## Resource attribution correction — October 31, 4:13PM PDT

The live shared-project listing contained 82 job records. 52 were attributable to
our team: 37 current Frontier/BioServices jobs plus 15 earlier Delphi/setup jobs.
The remaining 30 were unattributed to us; provider metadata does not identify
each other team. Earlier prefix-only totals missed our historical jobs.

| Status | Our team | Other/unattributed |
| --- | ---: | ---: |
| RUNNING | 2 | 1 |
| IMAGE_PULLING | 1 | 0 |
| COMPLETED | 39 | 18 |
| FAILED | 7 | 9 |
| CANCELLED | 3 | 2 |

Our running jobs were 3D CFD and the precision-controlled reaction-diffusion
DDPM; the training-only discretization audit was pulling. Each requested one
H100. These are allocation states, not measured GPU utilization. Attribution
was checked against the prior Delphi job manifest, compute receipts and the
recorded setup test. The infrastructure owner is correcting the public counter;
this does not widen cancellation permissions.

## Returned multiscale evidence and contribution checkpoint

- [x] Integrated the returned 3D flow fields, two actual-field videos and twelve
  surface-pressure arrays. Independent coupling inspection retains failed physical
  reference, unresolved fins, geometry/frame/unit mismatch and pressure-force
  closure findings. No whole-fish flight or transferred fin load is claimed.
- [x] Integrated v3 isolated-fin VLM comparisons. The v3b lattice does not converge;
  its lift is not accepted. v3a/v3c results remain inviscid attached-flow scenarios.
- [x] Integrated the versioned per-station tributary-width contract, exact geometry
  pins and analytic force/moment controls. Unknown stiffness remains unknown.
- [x] Integrated the zebrafish metabolic network and sweep animation, with the
  diagnosed internal oxygen source and assumed-medium limitation visible.
- [x] Root ran 139 targeted CFD, coupling, fin, metabolism and resource tests;
  independently checked 57 returned input/output/producer hashes. Exact tested
  commit and scope are in deploy/receipts/multiscale-returned-integration.json.
- [x] Integrated the independent requirements audit and deployed-site critique.
  Their timestamps and incomplete requirements remain explicit.
- [x] Fixed cached MCP text-preview paths and ran all 37 media tests. Added a
  bearer-only contributor identity endpoint; four targeted real-HTTP tests passed.
  Browser sessions still grant no persistent write authority.
- [x] Committed a conditional 24-hour queue with owners, admission and stop gates
  in results/infra/queue.json. Actual spend remains unavailable.
- [x] Publish the integrated artifacts, bounded text preview and identity endpoint
  together with the gallery/mobile fixes in one exact release.
- [ ] Connect persisted exact-version project discussion to the Studio contribution
  interface, using an explicit contributor credential held only in memory.
- [x] Imported 37 new curated records with zero forks and exact readback; submitted
  Project version 1177c609 with 22 members, retaining all 13 original members and
  four challenges on the previous version. Records remain unreviewed/proposed.
- [x] Recompute the site snapshot and expose prior-version Project discussion.
- [ ] Demonstrate two actual computations consuming one exact existing Claim and
  a separate review of their evidence. The current public-head reuse count is zero.
- [ ] Collect the live primary diffusion job; run the preregistered secondary
  evaluation only after its checkpoint, completeness audit and transport gates pass.

The fresh provider receipt at 4:33pm PDT records 52 team jobs (41 completed,
7 failed, 3 cancelled, 1 running) and 30 unmatched jobs. One team GPU job was
running; no team job was queued or pulling. These are job states, not device
utilization. Current hosted release is still c1ad527 until the release receipt
records otherwise.

## Published integration and resource handoff — October 31, 4:54pm PDT

- [x] Published release `52cda98` and restarted the MCP on that immutable release.
  Actual public verification passed 13 website checks and 37 MCP checks. Two
  additional HTTP checks exercised contributor identity: anonymous access refused,
  authenticated identity correct with no-store and no credential in the response.
- [x] Published both v3 printable display props and stands, prior-version Project
  challenges, formalization and gallery updates, and the full-horizon Morpheus
  chart with its actual declared video/poster hashes. Root recomputed eight
  Morpheus input/code/output hashes; this was not a new simulation or rendering.
- [x] Retrieved the public diffusion recovery archive: HTTP 200, 5,007,988 bytes,
  SHA256 `4c43b04106469764c1d24450a29c1e200914e3b7952c417bb62508fd52862a5d`.
  The original 1,800-second primary job FAILED after returning a 30,000-step
  checkpoint. No held-out evaluation or generated examples were returned.
- [ ] Run one separately frozen evaluation-only recovery from the exact returned
  weights; preserve the original failure and original scientific criteria.
  Public transport is ready; infrastructure owns the remaining execution gates.
- [ ] Complete and independently review the two exact-Claim fin computations.
  Original proposals were made ready but superseded before leasing or calculation
  to strengthen their cache identity. Revised heads `0ed92cdd` and `67532172` are
  ready; both consume the existing exact Claim `4998ef85`. Numerical results and
  review remain subsequent evidence, not implied by authorization.
- [ ] Complete Studio contribution UI integration. The transient bearer adapter
  and isolated-Store browser tests exist. Pagination and cross-namespace member
  anchoring fixes are in progress; no browser session gains write authority.
- [ ] Recheck the released routes with the separate browser critic. The site
  owner's broad run observed one viewer reset pixel mismatch among 102 checks;
  an isolated rerun passed. The viewer owner is investigating this timing issue.
- [ ] Use newly available GCP CPU capacity for ready scientific jobs. The user
  reports Compute API and billing enabled on `scienceclaw26bos-3016`, global
  CPU quota 32, GPU quota 0. Infrastructure confirmed the active lab account and
  is checking existing allocations before creating workers. Requesting a GPU
  quota increase does not imply that one has been granted.
- [ ] Export every GCP result before the account's user-reported deletion on
  Sunday night, November 1. Each job needs explicit input/output hashes, bounded
  resources, a collection path and cleanup ownership.

The fresh 4:49pm PDT provider listing contained 52 attributable team jobs:
41 completed, 8 failed, 3 cancelled, none running or queued. The 30 unattributed
jobs included one running job. These are dated job states, not current device
utilization. Infrastructure is the sole cloud dispatcher; no other team's jobs
are touched. Exact release and live-check receipts are under `deploy/receipts/`.

## Added user requirement — launchable printed fish

- [x] Define SPEC-010 with required slingshot launch, a distinct manufactured
  glider, actual mass/center-of-mass inputs, release dynamics and physical-test
  acceptance. Existing display props remain distinct.
- [ ] Build the lightweight fish-derived assembly (claude-05) and integrate
  stability, launch-load and trajectory sweeps (claude-07, aero controls04).
- [x] Record sourced Form Studio material cards and exact manufacturing
  conditions; geometry/dynamics binding remains in progress and printer/resin availability remains an optional user
  clarification while provisional scenarios proceed.
- [ ] Publish linked launchable-model files, simulation artifacts and assembly/
  physical-test instructions. No flight demonstration has occurred.

## Integration checkpoint — October 31, 5:11pm PDT

- [x] Integrated two actual exact-Claim computations and the separate reviewer
  findings. Root checked 56 artifact hashes/sizes, eight frozen code hashes and
  both saved read→input-binding→solver→Evidence sequences; six focused tests
  passed. Receipt: `deploy/receipts/claim-reuse-root-check.json`. This is input
  reuse, not evidence of collective advantage or biological validity. Reviewer
  reported both Evidence records disputed despite correct scoped mathematics;
  empirical relevance and independent non-computational replication are absent.
- [x] Add strong-fin and revision-history acceptance to SPEC-010. Printed fins,
  1:1 scale and Alpha Grey are coordinator defaults, not confirmed user choices.
- [ ] Geometry05: first reinforced lightweight print assembly; dynamics07:
  quantify launch loads, trim and mass feasibility. Preliminary analytic wing
  loading indicates 15–20 g may require more than the provisional 4–8 m/s launch
  speeds. Retain this constraint rather than promising flight from appearance.
- [ ] Site02: contribute through transient bearer credentials and show design
  lineage. Root is reviewing the integration; deployed release remains 52cda98.
- [ ] Separate browser critic06 replaces the previous critic's revoked-login
  blocker. Review each route and major interaction against the exact release.
- [ ] Research worker: map primary Evo2 cell-specific regulatory results and
  zebrafish fin cell/epigenetic datasets to explicit missing biological bridges.
  This literature/data work does not resume provider-stopped sequence work.
- [ ] Infrastructure reports GCP one-GPU quota approved; no VM allocation implied.
  CPU packet admission and durable collection remain in progress. Nebius recovery
  job `aijob-e00fb6jhvdt12fgsje` was image-pulling at the last report; no new
  evaluation result is claimed. Export GCP artifacts before account deletion.
