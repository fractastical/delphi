# How it was built — frontier.morphoswarm.ai (crawl)

Crawled from [https://frontier.morphoswarm.ai/#/work?tab=built](https://frontier.morphoswarm.ai/#/work?tab=built) on 2026-11-01T14:19:30.634Z. The page is drawn in the browser from `data/snapshot.json` (snapshot label **snapshot of inputs 7d83f2d56c3b**, input fingerprint `7d83f2d56c3b8b199a09a8253983ac100d08771800cceb6131a175613bfd322a`, 843 input files hashed). This file re-renders the fields that page reads; the exact data is in [built.json](built.json) and the untouched download in `raw/`. Upstream source: [kganjam/delphi-frontier](https://github.com/kganjam/delphi-frontier). All statements below are the upstream authors' own records, quoted, not re-verified by this repo.

Inventory observed 2026-11-01 00:39:28 PDT (UTC-07:00) (2026-11-01T07:39:28.658877Z). Event window from 2026-10-30T07:00:00.

## Recorded counters

| Quantity | Value | Status | Note | Source |
|---|---|---|---|---|
| Recorded participants | At least 23 | partial | 11 harnesses + 4 native children + 8 nested Claude children. Historical supported floor through 2026-10-31 22:08:29 PDT; root counted once. Not completed scientific tasks. | results/resources/agent-participation.json |
| Recorded subagents | 12 | partial | 4 native + 8 nested Claude child identities; shared with the participant total, not additional participants. Global current activity is unknown. | results/resources/agent-participation.json |
| Native running snapshot | 4 | actual | 1 coordinator + 3 children at 2026-10-31 22:07:30 PDT. API running state, not CPU or model utilization; other harnesses not covered. | results/resources/agent-participation.json |
| Contributing harnesses | At least 11 distinct harness identities | partial | Authored handoffs or reviewed identity mappings with checked artifacts, observed 2026-10-31 22:09:07 PDT. A supported minimum, not a census or concurrent-worker count. | results/resources/agent-contributors.json |
| Native collaborators | 4 | partial | Historical native children, including retired sessions; transcript evidence through 2026-10-31 22:08:29 PDT. Artifact-backed identities below are a subset. Not a count of running workers. | results/resources/agent-participation.json |
| Live harness processes | 31 | partial | Process snapshot at 2026-10-31 22:09:07 PDT. Includes idle and authentication-blocked sessions; this is not a count of agents working. | results/resources/agent-contributors.json |
| GPU jobs (own H100) | 42: 30 completed, 8 failed, 4 cancelled | actual | Own job records from 2026-11-01 00:39:26 PDT to 2026-11-01 00:39:28 PDT. Provider COMPLETED is not a scientific pass. Shared H100 capacity is not our use. Separate attribution snapshot (2026-11-01 00:39:28 PDT): 48 current Frontier jobs, 15 historical team jobs, 31 unattributed (not asserted to be other teams). | results/resources/hackathon-usage.json |
| CPU jobs (own) | 6: 5 completed, 1 failed | actual | CPU seconds are not recorded: unknown. | results/resources/hackathon-usage.json |
| GPU container work seconds | 3184.1 s across 9 completed GPU jobs and 93.9 s across 2 completed CPU jobs, from controller receipts | partial | Subset with preserved controller runtime receipts, not all project runtime. Container work includes setup/CPU/render/emission; not GPU kernel seconds. Sum of returned COPS container wall_s for those five completed jobs. Includes setup, numerical CPU controls and artifact transport inside workload; excludes image pull. Not GPU kernel execution seconds or billed GPU time. GPU kernel seconds and billed GPU seconds: unknown. | results/resources/hackathon-usage.json |
| GPU utilisation | 12 sampled windows, listed below; current utilisation unknown | partial | Windows include low and zero values; no project-wide average is inferred. | results/resources/hackathon-usage.json |
| Model calls and tokens | Embedding index: 49 requests, 2444 documents, 0 failed. Bioservices ledger: 4 calls, 7556 input and 9700 output tokens (thinking included). Hosted OpenFold2: 1 operation, SUCCEEDED | partial | Named ledgers only; embedding and generation units are not merged. Total tokens: unknown. BioNeMo-specific execution: not established. | results/resources/hackathon-usage.json |
| Cost | Unknown (not $0) | unknown | Unknown. No dollar estimate or zero spend inferred from credits. Google Cloud allocation snapshot (2026-11-01T07:39:29.742145+00:00): 16 allocated vCPUs and 0 attached GPU(s) on RUNNING instances. Reservations are not measured utilization; spend remains unknown. | results/resources/hackathon-usage.json |
| Repository commits | 1,252 across four repositories | actual | 942 non-merge and 310 merge commit objects; full SHAs deduplicated. Default branches pinned separately, 2026-10-31 00:00:00 PDT to 2026-10-31 22:23:50 PDT. Code activity, not agent or scientific-result counts. | results/resources/repository-activity-20261101-0523.json |

## Audits

### Who contributed? The dated identity audit

Observed 2026-11-01T05:09:07.772749Z. roles, jobs, branches, models and process counts are different units; only the separately documented disjoint participation identities may be summed unknown for every session: a live process, an idle prompt or an auth block is not work

**Contributing harnesses, supported minimum (11):**

- `claude-02` — site (site02)
- `claude-04` — authored handoff in window
- `claude-05` — print
- `claude-06` — site-critic (critic06)
- `claude-07` — glider-dynamics (mechanics07)
- `claude-10` — authored handoff in window
- `claude-13` — launchable-fish-review (review13)
- `claude-14` — artifact-curation / compiler
- `claude-15` — authored handoff in window
- `codex-03` — authored handoff in window
- `dx-submit` — handoff sender equals the session name

**Native collaborators, separate identities (3):**

- `/root/infra_director` — infra-director: published work/infra-director, transport and job ledgers (artifact verified)
- `/root/mechanobio_sim` — mechanobio simulation: aeroelastic production, NCA seed and curriculum (artifact verified)
- `/root/resource_scaling` — resource scaling: demo 60/120 source and output, bio-model ledger (artifact verified)

**23 recorded participants**: 11 harnesses, 4 native children and 8 nested Claude children; the child groups total 12 recorded subagents. Historical identities, not concurrent workers. Transcript scan: {"claude_nested_participants":8,"claude_task_transcripts":8,"codex_native_participants":4,"codex_task_complete_events":33,"codex_task_turns_started":36,"distinct_scoped_child_participants":12,"excluded_transcripts":154,"scanned_transcripts":166}. Source `results/resources/agent-participation.json` `e667d04fa843…`.

Counts: distinct_contributing_harness_ids_supported_minimum = 11; git_identities_in_window = 4; harness_ids_named_by_others_only = 5; harness_ids_probable_not_counted = 5; live_harness_processes_now = 31; models_in_trailers = 4; native_contributors_supported_minimum = 3; pane_state_counts = {"auth_blocked":12,"error_visible":2,"idle":7,"unknown":11,"working":1}; provider_jobs_own = 46; roles_in_handoff_filenames = 99; tmux_session_names_raw = 34; tmux_sessions_after_rename_dedup = 33; worker_branches = 109.

Identity links include coordinator attestations; artifact checks establish that the work exists, not independent proof of authorship. Full audit `results/resources/agent-contributors.json` `d576ef7b76fd…`.

### Repository activity, four pinned histories

Public default-branch ancestry at each recorded HEAD; inclusive committer-date window. Shared full SHA IDs counted once. Not all branches, all hackathon history, human or agent counts, or scientific achievement. Window 2026-10-31T07:00:00Z through 2026-11-01T05:23:50.751884+00:00.

| Repository | Commits | Non-merge / merge | Pinned revision |
|---|---|---|---|
| [kganjam/delphi-frontier](https://github.com/kganjam/delphi-frontier) | 1102 | 816 / 286 | 2b6faf20c0 |
| [kavitakoolkarni-bio/delphi-portal](https://github.com/kavitakoolkarni-bio/delphi-portal) | 8 | 8 / 0 | ad8e85e86f |
| [kavitakoolkarni-bio/morpholib-delphi-branch](https://github.com/kavitakoolkarni-bio/morpholib-delphi-branch) | 6 | 5 / 1 | d8449d0b01 |
| [fractastical/delphi](https://github.com/fractastical/delphi) | 136 | 113 / 23 | 4aaf9ac15f |

Deduplicated: {"commit_objects":1252,"merge_commits":310,"non_merge_commits":942,"distinct_linked_author_accounts":6,"commits_without_linked_author":1094}. Commits are not participants or validated findings. Full IDs `results/resources/repository-activity-20261101-0523.json` `82313a993699…`.

### Models and simulators actually exercised, 15 scoped records

Receipt-bounded inventory of selected biology-related model and simulation executions and explicitly listed provider calls. It does not claim to enumerate every worker, provider account, or run in the hackathon. Provider/tool status and scientific predicate status are separate.

No BioNeMo or BioNeMo NIM execution is established by the scoped receipts in this ledger. The one hosted OpenFold2 receipt explicitly reports upstream-source-not-nim.

| Model or simulator | id | Provider | Recorded outcome | Usage (as recorded) | Evidence |
|---|---|---|---|---|---|
| gemini-embedding-001 | `gemini-discovery-embedding-index-20261031` | Google Generative Language API | completed. Discovery index only. Not total Gemini or provider usage. | {"requests":49,"failed_requests":0,"documents":2444,"dimensions":768,"truncated_inputs":2,"run_id":"95caa34e4a03491a82a81ffe48049063"} | `imports/2026-10-31-discovery-live-index-receipt.json` |
| gemini-3-pro-image-preview, gemini-3.1-pro-preview | `gemini-bioservices-audit-20261031` | Google Generative Language API | completed. Protocol critique and data-access audit. Counts the combined four-call ledger once; the two smaller per-model ledgers are subsets, not extra calls. Model opinions are leads, not independent verification. | {"calls":4,"input_tokens":7556,"output_tokens_including_thinking":9700} | `results/bioservices/gemini_usage_ledger.json`, `results/bioservices/gemini_audit/usage_ledger.json`, `results/bioservices/gemini_audit_text_model/audit_summary.json` |
| OpenFold2 | `openfold2-kcnj13-operation-op-5ba1d104dbbcd293` | Nebius Scientific AI MCP | succeeded. One hosted prediction. The initial observation response was HTTP 503, after which the same operation ID was polled to success; this was not a second inference. | see receipt | `artifacts/bio-services/kcnj13_source/source_manifest.json`, `artifacts/bio-services/kcnj13_openfold2/operation_receipt.json`, `artifacts/bio-services/kcnj13_openfold2/metrics.json` |
| facebook/esm2_t33_650M_UR50D | `esm2-kir21-pilot-20261031` | local CPU execution; no hosted inference provider | completed pilot. Only the 256-row pilot was scored. The 6,789 count is the matched source-assay population, not completed model scoring. Four protocol controls passed; assay agreement is a computational lead, not experimental validation. | {"scored_rows":256,"matched_variants_in_source_assays":6789,"elapsed_seconds":118.2,"cpu_count":8} | `results/bioservices/kir21_pilot_receipt.json`, `results/bioservices/kir21_analysis.json` |
| Evo2 7B | `evo2-h100-smoke-attempt-1` | Nebius serverless H100 job harness | provider completed science runner failed. The provider's job state is not the scientific/runner result; no successful smoke result is claimed for this attempt. | see receipt | `results/compute/evo2smoke/manifest-fevo2smoke1.json` |
| Evo2 7B | `evo2-h100-smoke-attempt-2` | Nebius serverless H100 job harness | completed | see receipt | `results/compute/evo2smoke2/manifest-fevo2smoke2.json` |
| Evo2 7B | `evo2-zebrafish-h100-20261031` | Nebius serverless H100 job harness | completed. Sequence-model output is not evidence of phenotype or function; see the packet's frozen controls and scientific review. | see receipt | `results/compute/evo2zf/manifest-fevo2zf1.json` |
| BETSE 1.5.0 | `betse-local-generic-cell-tissue-run` | local CPU execution | completed with declared checks passing. Generic 66-cell model. Internal consistency and numerical controls passed; they do not calibrate the model to fish or establish biological validity. | {"scenarios":5,"trajectory_files":5} | `artifacts/bioelectric-tissue/summary.json` |
| OpenMM 8.4 | `openmm-collagen-100ps-reference-replicates-infra15` | Nebius serverless H100 job harness | completed. Computed classical MD for a collagen-mimetic fragment. Empirical accuracy and transfer to tissue modulus/fin function are unknown. | {"replicates":3,"production_ps_each":100,"equilibration_ps_each":10,"production_wall_seconds_each":[18.238215963,17.944053932999992,17.762254869999992]} | `results/infra/md-v2/manifest-infra15.json`, `results/infra/md-v2/results/infra15-collagen-md-reference-oracle/parts/00-collagen-md-v2-controls-then-cuda/molecular-output/production/receipt.json` |
| OpenMM 8.4 | `openmm-collagen-900ps-conditional-branches-infra21` | Nebius serverless H100 job harness | completed. Branches started from recorded prior states with declared new thermostat seeds; an explicitly descriptive finite-window drift check did not establish equilibrium or material properties. | {"replicates":3,"production_ps_each":900,"production_wall_seconds_each":[136.736560592,136.452289271,137.96050005900003]} | `results/infra/md-v3/manifest-infra21.json`, `results/infra/md-v3/results/infra21-collagen-md-conditional-extensions/parts/00-collagen-md-v3-900ps-branches/molecular-output/production/receipt.json` |
| Morpheus generic edited ODE/CPM/PDE example | `morpheus-full-horizon-initial-attempt-infra16` | Nebius serverless CPU job harness | failed | see receipt | `results/infra/morpheus/manifest-infra16.json` |
| Morpheus generic edited ODE/CPM/PDE example | `morpheus-full-horizon-output-repair-infra17` | Nebius serverless CPU job harness | completed after output repair. Separate corrected output run; generic example, not fish-calibrated biology. The initial failed run remains recorded separately. | {"parallel_arms":3,"cpu_threads_per_arm":1,"arm_timeout_seconds":3000,"arms_full_horizon":["baseline","nofeedback","seed2"]} | `results/infra/morpheus-v2/manifest-infra17.json`, `results/infra/morpheus-v2/results/infra17-morpheus-output-repair/parts/00-morpheus-three-arms-output-repair/receipt.json` |
| custom neural cellular automaton; four trained checkpoints | `nca-inverse-pattern-four-model-comparison-infra27` | Nebius serverless H100 job harness | completed computation scientific predicates failed. Custom computational model only; biological success probability is null. Preserve zero design-target passes; completion means the comparison ran, not that targets passed. | {"models_trained":4,"training_steps_each":2000,"evaluation_runs":52,"design_target_passed":0,"design_target_executed":48,"negative_controls_passed":4} | `results/resources/nca-completion.json`, `results/infra/nca/recovered/transport-recovery.json` |
| custom neural cellular automaton; four trained checkpoints | `nca-seed-placement-four-model-comparison-infra28` | Nebius serverless H100 job harness | completed with mixed predicate results. Computational predicates on one design target only; no biological success probability, new-target generalization, or tissue regeneration established. Evaluation cases reused; retain the earlier zero-pass run separately. | {"models_trained":4,"training_steps_each":2000,"evaluation_runs":52,"design_target_passed":32,"design_target_executed":48,"negative_controls_passed":4} | `results/resources/nca-seed-completion.json`, `results/infra/nca-seed/manifest-infra28.json` |
| speech-2.8-turbo | `minimax-demo-video-final-voice-pass` | MiniMax | completed for final video revision. These are the seven new calls in the final video revision only; unchanged segment audio was reused. No USD charge was returned, and this is not total MiniMax/account usage. | {"provider_calls":7,"reported_characters":892,"cuts":["frontier-120s","frontier-60s"]} | `artifacts/demo-video/tts-manifest.json` |

Accounting, as stated upstream: actual_billing: unknown; billing meters were not queried. total_provider_llm_usage: unknown; the listed ledgers cover only their named tasks. usage_units_are_not_additive: API requests; tokens; model-job runtime; simulation runtime; TTS characters. do_not_infer: BioNeMo/NIM usage from OpenMM or Evo2; GPU allocation from a hosted service receipt that omits hardware; biological validity from model confidence or passing computational controls.

All 84 nested path/sha256 references checked against this exact source tree; later resource snapshots may differ. This records source integrity, not scientific validity. Full ledger `results/resources/bio-model-usage.json` `7945a1e99582…`.

## Where review changed a decision

retrospective process trace of five corrections, not a controlled multi-agent benchmark

- **DOE decision exercise used a centered margin; corrected to the finalist's actual margin.** Retracted a claim that measurement halves a 0.50 misclassification rate; the stated benefit is now small because the finalist is already probably inside the regime. (commit `4d9628f`, protocol frozen before rerun `c151433`)
- **Separate-harness review found two typed-input holes in the genotype compiler.** The compiler's string-flag and arbitrary-string-digest behaviour was treated as a blocking residual until fixed; the review kept the claim to bookkeeping, not biology. (commit `1a084328ae49ae2c065465d1c400cb8df3d6f78f`)
- **Compiler cache keys and pin reads: reproduced stale-cache false passes in two review rounds.** Cache reuse was no longer trusted on the manifest alone; stale pins now produce typed blocked results, not passes.
- **Contributor ledger mislabelled 31 live processes as verified active and missed known authors.** A headline contributor number moved from 4 to an 11 floor, and 31 stopped being described as active. (commit `474fb8e`)
- **A validator control that could not detect anything was caught by the run refusing.** The analytic screen's agreement with 192 recorded flags became meaningful evidence only after the control could fail. (commit `895487f`)

Independence, as stated upstream: All reviewers are agents or sessions of one fleet sharing one git identity; none is an independent lab. Classes: author_self_correction, root_review, separate_harness_review, native_review.

Counterfactual, as stated upstream: For every entry it is unknown whether one agent re-reading its own work could have found the same issue; this ledger cannot answer that.

Not claimed upstream:
- that collective work outperforms a single agent
- any agent-count based advantage
- any scientific breakthrough count
- a percentage improvement between differing check sets

Record: `artifacts/coordination/review-corrections.json` `e9064db6fe08…` (saved as `raw/review-corrections.json`).

## Role assignments in the earlier usage slice

One session can fill several roles (upstream note). Observed 2026-11-01 00:39:28 PDT.

| Contributor | Kind | Role | Status as recorded |
|---|---|---|---|
| /root | native | director; platform integration and exact-release publishing | running |
| /root/infra_director | native | provider admission, queue, output recovery, utilization receipts | running |
| /root/mechanobio_sim | native | molecular controls, exact-state diagnosis, MD visualization and scale interfaces | running |
| /root/resource_scaling | native | Scientific AI hosted source-native model inference and service receipts | running |
| dx-gpuops-r1 | tmux | RD/cylinder protocols, frozen comparison, corrected flow videos | not measured; completed artifact commit7c455f74 |
| claude-06 | tmux | Morpheus ODE/CPM/PDE packet and feedback control | not measured; packet commit0d79314 |
| claude-04 | tmux | controlled3D WaterLily fish solver and pressure interface | not measured; packet commit400ca5a |
| dx-market-r1 | tmux | BETSE tissue simulation; now bounded RD diffusion pilot | training packet preparation observed; no trained result yet |

## Own provider jobs (48)

By provider state: 35 COMPLETED, 4 CANCELLED, 9 FAILED. Provider COMPLETED means the container ended, not that a scientific check passed.

| Created | Kind | Job | Provider state | Capacity |
|---|---|---|---|---|
| 2026-10-31 06:12:34 PDT | GPU | delphi-evolve-ops-probe1-h100-probe-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 06:21:35 PDT | GPU | delphi-evolve-ops-nca1-nca-proxy-h100-a1 | CANCELLED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 06:26:50 PDT | GPU | delphi-evolve-ops-pde1-pde-bench-h100-a1 | CANCELLED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 06:31:20 PDT | GPU | delphi-evolve-ops-pde2-pde-bench-h100-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 06:33:28 PDT | CPU | delphi-evolve-ops-pdecpu4-pde-cpu-scaling-a1 | COMPLETED | vcpu 4, gb 16 |
| 2026-10-31 11:31:37 PDT | CPU | delphi-evolve-ops-fcpuref1-cpu-reference-pilot-a1 | COMPLETED | vcpu 4, gb 16 |
| 2026-10-31 11:38:28 PDT | GPU | delphi-evolve-ops-fgpupilot1-pattern-pilot-h100-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 12:06:50 PDT | CPU | delphi-evolve-ops-fcpurefho1-cpu-reference-heldout-a1 | COMPLETED | vcpu 4, gb 16 |
| 2026-10-31 12:18:48 PDT | GPU | delphi-evolve-ops-fgpuho1-heldout-validation-h100-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 12:31:36 PDT | GPU | delphi-evolve-ops-fevo2smoke1-evo2-7b-smoke-h100-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 12:38:27 PDT | GPU | delphi-evolve-ops-fgpuho2-heldout-validation-h100-a1 | FAILED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 12:40:12 PDT | GPU | delphi-evolve-ops-fflow1-ns2d-shear-demo-h100-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 12:54:24 PDT | GPU | delphi-evolve-ops-fevo2smoke2-evo2-7b-smoke-h100-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 12:54:24 PDT | GPU | delphi-evolve-ops-fgpuho3-heldout-validation-h100-a1 | CANCELLED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 13:17:40 PDT | GPU | delphi-evolve-ops-fflowrefine2-ns2d-refine-h100-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 13:25:46 PDT | GPU | delphi-evolve-ops-fatlas1-atlas-heldout-h100-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 13:30:13 PDT | GPU | delphi-evolve-ops-fevo2zf1-evo2-zebrafish-h100-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 13:53:41 PDT | GPU | delphi-evolve-ops-fwarm8-warm-p8-dt-halving-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 13:57:13 PDT | GPU | bioservices-evo2zf-score-a1 | FAILED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 14:06:16 PDT | GPU | bioservices-evo2zf-score-a2 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 14:19:35 PDT | GPU | bioservices-evo2zf-armb-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 14:26:14 PDT | GPU | delphi-evolve-ops-fwarm9-warm-p9-windtunnel-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 14:34:37 PDT | GPU | delphi-evolve-ops-infra10-frozen-subset-dt4-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 14:38:47 PDT | GPU | delphi-evolve-ops-infra11-atlas-perturb-completion-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 14:43:57 PDT | GPU | delphi-evolve-ops-infra12-fish-aoa-grid-pairs-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 14:50:18 PDT | GPU | delphi-evolve-ops-infra13-warm-p10-body-in-flow-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 14:55:21 PDT | GPU | delphi-evolve-ops-infra14-collagen-md-a1 | FAILED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 15:10:55 PDT | GPU | delphi-evolve-ops-infra15-collagen-md-reference-oracle-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 15:17:10 PDT | CPU | delphi-evolve-ops-infra16-morpheus-full-horizon-a1 | FAILED | vcpu 4, gb 16 |
| 2026-10-31 15:22:55 PDT | CPU | delphi-evolve-ops-infra17-morpheus-output-repair-a1 | COMPLETED | vcpu 4, gb 16 |
| 2026-10-31 15:27:17 PDT | GPU | delphi-evolve-ops-infra18-cfd3d-controlled-fish-a1 | FAILED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 15:36:35 PDT | GPU | delphi-evolve-ops-infra19-rd-ddpm-training-a1 | FAILED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 15:39:52 PDT | CPU | delphi-evolve-ops-infra20-candidate-cpu-diagnostic-a1 | COMPLETED | vcpu 4, gb 16 |
| 2026-10-31 15:45:29 PDT | GPU | delphi-evolve-ops-infra21-collagen-md-conditional-extensions | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 15:45:52 PDT | GPU | delphi-evolve-ops-infra22-cfd3d-geometry-dispatch-repair-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 15:55:32 PDT | GPU | delphi-evolve-ops-infra23-rd-ddpm-precision-diagnostic-a1 | FAILED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 15:58:39 PDT | GPU | delphi-evolve-ops-infra24-rd-training-only-discretization-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 17:05:11 PDT | GPU | delphi-evolve-ops-infra25-rd-ddpm-evaluation-recovery-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 17:39:23 PDT | GPU | delphi-evolve-ops-infra26-rd-ddpm-preregistered-secondary-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 18:24:20 PDT | GPU | delphi-evolve-ops-infra27-nca-inverse-pattern-four-model-com | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 19:07:19 PDT | GPU | delphi-evolve-ops-infra28-nca-seed-placement-comparison-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 19:08:12 PDT | GPU | delphi-evolve-ops-infra29-h100-cfd-controls-calibration-a1 | FAILED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 19:52:46 PDT | GPU | delphi-evolve-ops-infra30-h100-r2-frozen-assay-a1 | CANCELLED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 20:07:25 PDT | GPU | delphi-evolve-ops-infra31-nca-damage-curriculum-eight-models | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 20:08:42 PDT | GPU | delphi-evolve-ops-infra32-h100-r2-frozen-assay-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 20:18:46 PDT | GPU | delphi-evolve-ops-infra34-h100-frozen-cuda-control-arms-a1 | COMPLETED | gpu 1, vcpu 16, gb 200 |
| 2026-10-31 23:38:01 PDT | GPU | delphi-evolve-ops-infra36-voxcraft-modern-cuda-probe-a1 | FAILED | gpu 1, vcpu 16, gb 200 |
| 2026-11-01 00:12:47 PDT | GPU | delphi-evolve-ops-infra37-rd-inverse-six-synthetic-targets-a | COMPLETED | gpu 1, vcpu 16, gb 200 |

## Controller outcomes for recent GPU tasks

| Status | Task | Wall (s) | Return code | Path | sha256 |
|---|---|---|---|---|---|
| done | aoa | 112.2 | 0 | results/resources/usage-event-snapshots/20261101T003528Z/aoa-manifest-infra12.json | `3030a9a7b2a2…` |
| failed | cfd3d | 45.6 | 3 | results/resources/usage-event-snapshots/20261101T003528Z/cfd3d-manifest-infra18.json | `d32d77863530…` |
| done | cfd3d-diagnostic | 6.2 | 0 | results/resources/usage-event-snapshots/20261101T003528Z/cfd3d-diagnostic-manifest-infra20.json | `e38fe4ecb613…` |
| done | cfd3d-v2 | 1549 | 0 | results/resources/usage-event-snapshots/20261101T003528Z/cfd3d-v2-manifest-infra22.json | `82ac2b4b19d2…` |
| done | cylinder | 269.6 | 0 | results/resources/usage-event-snapshots/20261101T003528Z/cylinder-manifest-infra13.json | `f8f771a825cf…` |
| failed | diffusion | 5 | 1 | results/resources/usage-event-snapshots/20261101T003528Z/diffusion-manifest-infra19.json | `19147fcedd79…` |
| done | diffusion-recovery | 388.8 | 0 | results/resources/usage-event-snapshots/20261101T003528Z/diffusion-recovery-manifest-infra25.json | `acdf01a6e656…` |
| failed | diffusion-v2 | 1830.9 | 1 | results/resources/usage-event-snapshots/20261101T003528Z/diffusion-v2-manifest-infra23.json | `b85753825b09…` |
| done | dt4 | 410.1 | 0 | results/resources/usage-event-snapshots/20261101T003528Z/dt4-manifest-infra10.json | `378c2e9cdbc9…` |
| failed | md | not recorded | not recorded | results/resources/usage-event-snapshots/20261101T003528Z/md-manifest-infra14.json | `f25230ae1fa7…` |
| done | md-v2 | 126.3 | 0 | results/resources/usage-event-snapshots/20261101T003528Z/md-v2-manifest-infra15.json | `248f425157f9…` |
| done | md-v3 | 500.2 | 0 | results/resources/usage-event-snapshots/20261101T003528Z/md-v3-manifest-infra21.json | `884d3340969b…` |
| failed | morpheus | 59.7 | 1 | results/resources/usage-event-snapshots/20261101T003528Z/morpheus-manifest-infra16.json | `1a3f36f28892…` |
| done | morpheus-v2 | 87.7 | 0 | results/resources/usage-event-snapshots/20261101T003528Z/morpheus-v2-manifest-infra17.json | `032bb505abbd…` |
| done | p9-check | 34.2 | 0 | results/resources/usage-event-snapshots/20261101T003528Z/p9-check-manifest-infra-p9-check.json | `d6208d5064d8…` |
| done | perturb | 119.2 | 0 | results/resources/usage-event-snapshots/20261101T003528Z/perturb-manifest-infra11.json | `6acd4c325047…` |
| done | rd-numerics | 63.3 | 0 | results/resources/usage-event-snapshots/20261101T003528Z/rd-numerics-manifest-infra24.json | `2d563d675cc2…` |

## Failed primary diffusion-model training run, retained

Primary run status: **FAILED** (job `aijob-e00qazx6sby3vav47b`). Checkpoint after 30000 training steps, sha256 `1a0a185cdacd…`. Training artifact from FAILED primary run; not evaluated performance or validated biology. Published: true (`artifacts/rd-diffusion/primary-runtime-inputs.tar.xz`, 5.0 MB, sha256 `4c43b0410646…`). Next step as recorded: Only separately preregistered evaluation recovery after publicGET exactSHA and same-allocation original controls; no retraining

A separate diffusion pilot reused that checkpoint (4 files, manifest `artifacts/rd-diffusion/visuals/manifest.json`); the upstream page says its strict secondary audit failed and the primary timeout remains a failure.

## Recorded OpenResearch runs (local exemplars)

OpenResearch is a local recorder of which code was run. It is not a cloud dispatcher and none of these runs used a remote backend. A completed run is evidence that this code at this commit exited 0 and printed this, not that the science is right.

| Run | Command | Backend | orx | Started (UTC) | Duration (s) | Status | Record |
|---|---|---|---|---|---|---|---|
| Collier 1996 replay v4 (ecc2627) | `python3 run_replay.py` | local_job | orx 0.2.23 | 2026-10-31T19:04:13Z | 6.15 | done | connectors/biomodels/orx/orx_facts.json |
| Neumann-mode Turing scan (exact rationals) | `python3 run_modes.py` | local_job | orx 0.2.23 | 2026-10-31T18:04:45Z | 6.05 | done | frontier_adapters/examples/orx_run_turing/run.json |

OpenResearch integration note (corpus session, single reader, not independently reviewed)

External tools credited upstream: Nebius CloudAI H100 and CPUserverless, Google Gemini embedding/inference, ScientificAI OpenFold2, OpenMM, Morpheus, WaterLily/CUDA.jl, PyTorch, NumPy/SciPy, PostgreSQL/pgvector, Lean4.

Usage-slice limitations:
- Provider state COMPLETED is not a passed scientific gate. Preservefailed numerical checks and partial artifacts.
- Historical GPU sample windows include zero utilization; never present them as current occupancy.
- Model token receipts cover named ledgers only; total account/team tokens unknown.
- Contributors show distributed work; no causal collective-intelligence speedup established.
- No preparation or earlier in-house project origin narrative is part of this usage record.

## Providers and jobs

- Nebius (GPU jobs): 48 jobs by this project: 35 completed, 9 failed, 4 cancelled (observed 2026-11-01T07:39:28.658877Z). Allocation is requested capacity, not utilisation.
- Google Generative Language: provider bioservices gemini calls: calls 4, input tokens 7556, output tokens including thinking 9700; google-generative-language gemini-embedding-001: documents embedded 2444, embedding requests 49, failed requests 0.
- Live checks of the public node: 27 recorded, 27 with every check passed.

Unknown (upstream's own list): Unknown. Zero worker creations from the two recorded failed launch attempts does not establish zero total project spend. Total provider LLM usage: unknown; other workers are outside these receipts Utilisation of currently allocated GPUs is unknown until sampled.

## Dated record (41 rows; model usage, live check, GPU telemetry)

| Time (UTC) | Kind | What | Outcome | Scope | Evidence |
|---|---|---|---|---|---|
| 2026-10-31 18:46:55Z | model usage | provider bioservices gemini calls | recorded: calls 4, input tokens 7556, output tokens including thinking 9700; window 2026-10-31T18:46:55Z to 2026-10-31T18:50:06Z | Separate bioservices ledger; do not aggregate with embedding requests or infer total provider usage. | `results/bioservices/gemini_usage_ledger.json` `5980087c13a9…` |
| 2026-10-31 19:25:31.278487 | live check | first live check (https://frontier.morphoswarm.ai) | passed: 9 of 9 checks passed | HTTP access and rendering; no scientific acceptance or biological validation | `deploy/receipts/first-live-check.json` `73ed42b718be…` |
| 2026-10-31 19:52:21.015338 | live check | public live check (https://frontier.morphoswarm.ai) | passed: 13 of 13 checks passed | HTTP access and rendering; no scientific acceptance or biological validation | `deploy/receipts/public-live-check.json` `9b7689c7de43…` |
| 2026-10-31 19:52:49.948173 | live check | public access check (public node) | passed: 11 of 11 checks passed | Access controls and bounded calculators; no biological validation; Orchestra configuration unchanged. | `deploy/receipts/public-access-check.json` `807b5d5c2be0…` |
| 2026-10-31 19:54:05Z | GPU telemetry | ns2d-shear-demo-h100 | recorded: 52 samples at 1000 ms; GPU utilisation mean 96.63%, max 100.0%; memory max 1969.0 of 81559.0 MiB | A sampled historical window, not current utilisation. | `results/resources/telemetry/ns2d-shear.json` `74231b3d2b90…` |
| 2026-10-31 20:10:28Z | GPU telemetry | heldout-validation-h100 | recorded: 149 samples at 1000 ms; GPU utilisation mean 51.56%, max 55.0%; memory max 763.0 of 81559.0 MiB | A sampled historical window, not current utilisation. | `results/resources/telemetry/heldout-validation.json` `084ae7671461…` |
| 2026-10-31 20:20:14 | model usage | google-generative-language gemini-embedding-001 | passed: documents embedded 2444, embedding requests 49, failed requests 0; window 2026-10-31T20:20:14.809201Z to 2026-10-31T20:20:59.421924Z | This receipt covers the discovery embedding index only; it is not total Gemini or provider usage. | `discovery/imports/2026-10-31-discovery-live-index-receipt.json` `a6f0e2256f69…` |
| 2026-10-31 20:34:27Z | GPU telemetry | ns2d-refine-h100 | recorded: 181 samples at 1000 ms; GPU utilisation mean 98.62%, max 100.0%; memory max 2121.0 of 81559.0 MiB | A sampled historical window, not current utilisation. | `results/resources/telemetry/ns2d-refine.json` `13af1b53e601…` |
| 2026-10-31 20:36:42Z | GPU telemetry | evo2-zebrafish-h100 | recorded: 493 samples at 1000 ms; GPU utilisation mean 34.78%, max 89.0%; memory max 20925.0 of 81559.0 MiB | A sampled historical window, not current utilisation. | `results/resources/telemetry/evo2-zebrafish.json` `380cea4cbf26…` |
| 2026-10-31 20:56:10.958349 | live check | studio live check (https://frontier.morphoswarm.ai) | passed: 13 of 13 checks passed | HTTP access and rendering; no scientific acceptance or biological validation | `deploy/receipts/studio-live-check.json` `75ade899ddb9…` |
| 2026-10-31 21:03:02.065614 | live check | mcp public check (https://frontier.morphoswarm.ai/mcp) | passed: 12 of 12 checks passed | Public client connectivity, search, schema discovery and anonymous write denial; not scientific acceptance. | `deploy/receipts/mcp-public-check.json` `ce095305fec2…` |
| 2026-10-31 21:39:41.359745 | live check | deadline live check (https://frontier.morphoswarm.ai) | passed: 8 of 8 checks passed | HTTP access and rendering; no scientific acceptance or biological validation | `deploy/receipts/deadline-live-check.json` `7341eac63f5f…` |
| 2026-10-31 21:39:54.953247 | live check | mcp expanded check (https://frontier.morphoswarm.ai/mcp) | passed: 33 of 33 checks passed | Public client connectivity, search, schema discovery and anonymous write denial; not scientific acceptance. | `deploy/receipts/mcp-expanded-check.json` `33d59c52d960…` |
| 2026-10-31 21:48:23 | GPU telemetry | infra-dt-quarter | recorded: 410 samples at 1000 ms; GPU utilisation mean 45.802439024390246%, max 50.0% | A sampled historical window, not current utilisation. | `results/infra/dt4/results/infra10-frozen-subset-dt4/out/telemetry_device.csv` `c8600c0999d9…` |
| 2026-10-31 21:52:52 | GPU telemetry | infra-initial-perturbation-completion | recorded: 117 samples at 1000 ms; GPU utilisation mean 50.111111111111114%, max 56.0% | A sampled historical window, not current utilisation. | `results/infra/perturb/results/infra11-atlas-perturb-completion/out/telemetry_device.csv` `8d5d8d971c29…` |
| 2026-10-31 21:59:15 | GPU telemetry | infra-angle-grid-batch | recorded: 113 samples at 1000 ms; GPU utilisation mean 30.194690265486727%, max 88.0% | A sampled historical window, not current utilisation. | `results/infra/aoa/results/infra12-fish-aoa-grid-pairs/out/telemetry_device.csv` `b45b41b8e719…` |
| 2026-10-31 22:06:18 | GPU telemetry | infra-cylinder-re100 | recorded: 270 samples at 1000 ms; GPU utilisation mean 85.7925925925926%, max 98.0% | A sampled historical window, not current utilisation. | `results/infra/cylinder/results/infra13-warm-p10-body-in-flow/out/telemetry_device.csv` `b5ac3d99523b…` |
| 2026-10-31 22:13:23 | GPU telemetry | infra-collagen-md-v2 | recorded: 127 samples at 1000 ms; GPU utilisation mean 37.40944881889764%, max 95.0% | A sampled historical window, not current utilisation. | `results/infra/md-v2/results/infra15-collagen-md-reference-oracle/out/telemetry_device.csv` `67c85dbb4362…` |
| 2026-10-31 22:45:39.629578 | live check | about mcp live check (https://frontier.morphoswarm.ai/mcp) | passed: 35 of 35 checks passed | Public client connectivity, search, schema discovery and anonymous write denial; not scientific acceptance. | `deploy/receipts/about-mcp-live-check.json` `3ff00377fb99…` |
| 2026-10-31 22:45:44.207402 | live check | about public live check (https://frontier.morphoswarm.ai) | passed: 13 of 13 checks passed | HTTP access and rendering; no scientific acceptance or biological validation | `deploy/receipts/about-public-live-check.json` `693b9b32883c…` |
| 2026-10-31 23:06:27.447034 | live check | public repository check (https://github.com/kganjam/delphi-frontier) | passed: 2 of 2 checks passed | Anonymous metadata and current README retrieval; public read access, not collaborator write permissions. | `deploy/receipts/public-repository-check.json` `d5faaf5e36be…` |
| 2026-10-31 23:14:54.240377 | live check | rayfan public live check (https://frontier.morphoswarm.ai) | passed: 13 of 13 checks passed | HTTP access and rendering; no scientific acceptance or biological validation | `deploy/receipts/rayfan-public-live-check.json` `c195ae6390f5…` |
| 2026-10-31 23:14:54.902727 | live check | rayfan mcp live check (https://frontier.morphoswarm.ai/mcp) | passed: 35 of 35 checks passed | Public client connectivity, search, schema discovery and anonymous write denial; not scientific acceptance. | `deploy/receipts/rayfan-mcp-live-check.json` `12d630b10c29…` |
| 2026-10-31 23:53:44.922743 | live check | partial ddpm public archive (public node) | passed: 0 of 0 checks passed | Exact published recovery archive bytes; this is not model evaluation. | `deploy/receipts/partial-ddpm-public-archive.json` `e58851f79e39…` |
| 2026-10-31 23:54:01.957649 | live check | partial ddpm mcp live check (https://frontier.morphoswarm.ai/mcp) | passed: 37 of 37 checks passed | Public client connectivity, search, schema discovery and anonymous write denial; not scientific acceptance. | `deploy/receipts/partial-ddpm-mcp-live-check.json` `583e83837888…` |
| 2026-10-31 23:54:02.430762 | live check | partial ddpm public live check (https://frontier.morphoswarm.ai) | passed: 13 of 13 checks passed | HTTP access and rendering; no scientific acceptance or biological validation | `deploy/receipts/partial-ddpm-public-live-check.json` `95443c83988a…` |
| 2026-10-31 23:54:47.472024 | live check | contributor identity live check (https://frontier.morphoswarm.ai/v1/read/identity) | passed: 2 of 2 checks passed | Read-only HTTP checks; no persistent scientific or test records created. | `deploy/receipts/contributor-identity-live-check.json` `0e0d3332d079…` |
| 2026-10-31 23:57:31.712837 | live check | annotation composer integration (public node) | passed: 1 of 1 checks passed | Actual browser-generated records validated and read back through isolated PostgreSQL Store; imported-member cross-namespace anchors, two-page context, wrong-token refusal. No production writes; Studio mount remains siteowner work. | `deploy/receipts/annotation-composer-integration.json` `aaa0a6e083db…` |
| 2026-11-01 00:18:33.180857 | live check | studio history mcp live check (https://frontier.morphoswarm.ai/mcp) | passed: 37 of 37 checks passed | Public client connectivity, search, schema discovery and anonymous write denial; not scientific acceptance. | `deploy/receipts/studio-history-mcp-live-check.json` `753ccc06b715…` |
| 2026-11-01 00:18:43.946931 | live check | studio history public live check (https://frontier.morphoswarm.ai) | passed: 13 of 13 checks passed | HTTP access and rendering; no scientific acceptance or biological validation | `deploy/receipts/studio-history-public-live-check.json` `55273c6da027…` |
| 2026-11-01 00:19:50 | GPU telemetry | Exact-weight DDPM evaluation recovery | recorded: 389 samples at 1000.0 ms; GPU utilisation mean 85.6426735218509%, max 100.0% | A sampled historical window, not current utilisation. | `results/infra/diffusion-recovery/results/infra25-rd-ddpm-evaluation-recovery/out/telemetry_device.csv` `2ffaf945ea31…` |
| 2026-11-01 00:54:17 | GPU telemetry | infra-secondary-exact-w1 | recorded: 244 samples at 1000.0 ms; GPU utilisation mean 80.02459016393442%, max 100.0% | A sampled historical window, not current utilisation. | `results/infra/diffusion-secondary/results/infra26-rd-ddpm-preregistered-secondary/out/telemetry_device.csv` `f625d7c50a01…` |
| 2026-11-01 01:12:59.576996 | live check | r4 print bundle root check (public node) | passed: 5 of 5 checks passed | Artifact integrity and nominal fin chirality only. Independent thin-wall review is unresolved; no flight clearance. | `deploy/receipts/r4-print-bundle-root-check.json` `a65e5d44ecb2…` |
| 2026-11-01 01:36:32.421523 | live check | demo feature mcp live (https://frontier.morphoswarm.ai/mcp) | passed: 39 of 39 checks passed | Public client connectivity, search, schema discovery and anonymous write denial; not scientific acceptance. | `deploy/receipts/demo-feature-mcp-live.json` `245220fa922d…` |
| 2026-11-01 01:36:33.057890 | live check | demo feature web live (https://frontier.morphoswarm.ai) | passed: 8 of 8 checks passed | HTTP access and rendering; no scientific acceptance or biological validation | `deploy/receipts/demo-feature-web-live.json` `730959cbbc88…` |
| 2026-11-01 01:39:46 | GPU telemetry | Original four-model NCA comparison | recorded: 724 samples at 1000.0 ms; GPU utilisation mean 90.84944751381215%, max 95.0% | A sampled historical window, not current utilisation. | `results/infra/nca/recovered/out/telemetry_device.csv` `185a78d3becf…` |
| 2026-11-01 02:27:24.233480 | live check | demo final web live (https://frontier.morphoswarm.ai) | passed: 8 of 8 checks passed | HTTP access and rendering; no scientific acceptance or biological validation | `deploy/receipts/demo-final-web-live.json` `cc6e870fccc5…` |
| 2026-11-01 02:27:27.498250 | live check | demo final mcp live (https://frontier.morphoswarm.ai/mcp) | passed: 39 of 39 checks passed | Public client connectivity, search, schema discovery and anonymous write denial; not scientific acceptance. | `deploy/receipts/demo-final-mcp-live.json` `320779afba16…` |
| 2026-11-01 02:28:01.172582 | live check | demo videos live (https://frontier.morphoswarm.ai) | passed: 30 of 30 checks passed | Exact public media bytes, delivery and browser decoding/playback; not biological validation. | `deploy/receipts/demo-videos-live.json` `63b45da202d5…` |
| 2026-11-01 04:29:55.007733 | live check | recovery security review (public node) | passed: 0 of 0 checks passed |  | `deploy/receipts/recovery-security-review.json` `9844d79bbfbb…` |
| 2026-11-01 05:01:53.486833 | live check | mcp proofs stdio (public node) | passed: 0 of 0 checks passed |  | `deploy/receipts/mcp-proofs-stdio.json` `c7127e4791c4…` |

## Results, stops and failures, with what checked them (33)

- **passed** — **about release checks (release 0f8eadcbdc59)** (no time recorded, date only): site browser and actual GLB viewer: 65 passed; site and build code byte-identical to release commit (git diff checked) (exit 0); scratch public runtime integration: ALL LIVE CHECKS PASSED;37downloads,22documents,14players,solver,belief,live preview (exit 0); web, media and MCP regression: 137 passed; newer worker-budget implementation checked separately (exit 0); shared numerical worker budget: 66 passed in5.80s (exit 0); autoformalization adapter: 50 passed,1 skipped; optional external check not run (exit 0); About interaction checks: Five routes at1440px and390px, six equation controls, documentation drawer and About menu passed; desktop/mobile screenshots inspected (exit 0); snapshot current: stale=[] (exit 0); changed service lint: All checks passed (exit 0)  
  `deploy/receipts/about-release-checks.json` `4003ef5fb998…`
- **passed** — **aeroelastic integration** (no time recorded, date only): aeroelastic focused tests: not passed (exit 0); aeroelastic scoped lint: not passed (exit 0); aeroelastic artifact pins: not passed (exit 0)  
  `deploy/receipts/aeroelastic-integration.json` `8efc3c1dd1f0…`
- **recorded** — **claim reuse coordinator ready v2** (no time recorded, date only): no checks listed  
  `deploy/receipts/claim-reuse-coordinator-ready-v2.json` `0ca3d1481ad6…`
- **recorded** — **claim reuse coordinator ready** (no time recorded, date only): no checks listed  
  `deploy/receipts/claim-reuse-coordinator-ready.json` `381762883ace…`
- **failed** — **claim reuse root check** (no time recorded, date only): check: not passed (exit not recorded); check: not passed (exit not recorded)  
  `deploy/receipts/claim-reuse-root-check.json` `fbd5e3269662…`
- **recorded** — **curated print integration** (no time recorded, date only): no checks listed  
  `deploy/receipts/curated-print-integration.json` `f4096e05ee48…`
- **recorded** — **demo90 live** (no time recorded, date only): no checks listed  
  `deploy/receipts/demo90-live.json` `6526419c47a6…`
- **recorded** — **design control live** (no time recorded, date only): no checks listed  
  `deploy/receipts/design-control-live.json` `6bfe0c8ec51f…`
- **recorded** — **gcp recovery root check** (no time recorded, date only): no checks listed  
  `deploy/receipts/gcp-recovery-root-check.json` `fc8e461a5d34…`
- **recorded** — **mcp menu live (release 7d727934460d)** (no time recorded, date only): no checks listed  
  `deploy/receipts/mcp-menu-live.json` `a33d6d49346a…`
- **failed** — **mcp proofs checks** (no time recorded, date only): fixed catalogue current/stale/mutated receipt/published source/missing/symlink/invalid-family checks: passed (exit not recorded); official MCP stdio and remote anonymous HTTP tools/auth/limits: passed (exit not recorded); manual official SDK stdio source-sharing probe: passed (exit not recorded); scoped Ruff: passed (exit not recorded)  
  `deploy/receipts/mcp-proofs-checks.json` `41360866fd5e…`
- **recorded** — **multiscale returned integration** (no time recorded, date only): no checks listed  
  `deploy/receipts/multiscale-returned-integration.json` `1161778273bd…`
- **passed** — **nca seed root integration** (no time recorded, date only): check: not passed (exit 0); check: not passed (exit 0); check: not passed (exit 0)  
  `deploy/receipts/nca-seed-root-integration.json` `48e9aca96753…`
- **passed** — **partial ddpm public release checks (release 52cda98da77f)** (no time recorded, date only): New public download and Project history behaviors: 4 passed,77 deselected in5.44s on the identical staged source committed in this release. (exit 0); Snapshot reproducibility: stale=[] on committed release. (exit 0); Incremental secret scan: 9 commits,241284bytes,0findings; partial archive transport previously hash-checked; binary model weights not secret-scanned. (exit 0); Morpheus artifact lineage: Eight input/code/output hashes recomputed; rendering and simulation not rerun. (exit 0); Whitespace: Passed before commit. (exit 0)  
  `deploy/receipts/partial-ddpm-public-release-checks.json` `978c6d6d574b…`
- **recorded** — **partial ddpm root check** (no time recorded, date only): no checks listed  
  `deploy/receipts/partial-ddpm-root-check.json` `8a49072e24c3…`
- **recorded** — **print audit live (release 9d5a3d084d8a)** (no time recorded, date only): no checks listed  
  `deploy/receipts/print-audit-live.json` `9c107621e115…`
- **recorded** — **r4 mass root check** (no time recorded, date only): no checks listed  
  `deploy/receipts/r4-mass-root-check.json` `5f238a8aa689…`
- **passed** — **rayfan public release checks (release c1ad527e7c1a)** (no time recorded, date only): Geometry and additive print forms: 81 passed on b2fd16f; source scientific geometry unchanged since that check. (exit 0); Simulation and coupling integration: 117 passed in6.25s; computational checks only, not empirical biology. (exit 0); Combined Home About mobile and error browser checks: 19 passed,50 deselected in38.64s; subsequent public-source labels checked separately. (exit 0); Public repository labels: 3 passed,66 deselected in7.81s before commit on the identical staged code now in this SHA. (exit 0); Snapshot up to date: stale=[]; rerun on this committed release. (exit 0); Patch whitespace: Clean worktree and no whitespace errors. (exit 0)  
  `deploy/receipts/rayfan-public-release-checks.json` `d4ba5d2a9ee5…`
- **failed** — **recovery gcp root check** (no time recorded, date only): check: not passed (exit not recorded)  
  `deploy/receipts/recovery-gcp-root-check.json` `29b183e6f773…`
- **recorded** — **regulatory metadata root check** (no time recorded, date only): no checks listed  
  `deploy/receipts/regulatory-metadata-root-check.json` `f13c4dd4f5b9…`
- **recorded** — **reuse studies live** (no time recorded, date only): no checks listed  
  `deploy/receipts/reuse-studies-live.json` `593bc6fa6b33…`
- **failed** — **science integration 20261031** (no time recorded, date only): Molecular returned data and controls: 16 passed in1.53s (exit not recorded); Portable packet RD software and genomics: 41 passed in5.95s (exit not recorded); Genomics after style fixes: 37 passed in1.30s (exit not recorded); Molecular manifest: 120 paths with matching byte counts and SHA256 digests; root recomputed (exit not recorded); Pilot independent reconstruction: 27 distinct calls,27 JSON/text/hash matches,all27 scored16/16;53802provider tokens;18 prior artifact references resolved to earlier calls in the same condition/repeat (exit not recorded); Changed source Ruff: Passed after fixing15 style findings; scientific artifacts unchanged (exit not recorded); Incremental credential scan: 19 commits,5.84MB,0findings; gitleaks8.30.1,redacted (exit not recorded)  
  `deploy/receipts/science-integration-20261031.json` `1bf7ae1d9864…`
- **recorded** — **science integration security** (no time recorded, date only): no checks listed  
  `deploy/receipts/science-integration-security.json` `802b805a34a1…`
- **passed** — **secondary viewer integration** (no time recorded, date only): check: not passed (exit 0); check: not passed (exit 0)  
  `deploy/receipts/secondary-viewer-integration.json` `3f703d7e13a8…`
- **recorded** — **shared table live (release fb52a75f8b4c)** (no time recorded, date only): no checks listed  
  `deploy/receipts/shared-table-live.json` `8434f59db566…`
- **recorded** — **simulation batch security** (no time recorded, date only): no checks listed  
  `deploy/receipts/simulation-batch-security.json` `95d8bd1ec248…`
- **failed** — **studio history integration notes** (no time recorded, date only): check: not passed (exit not recorded)  
  `deploy/receipts/studio-history-integration-notes.json` `4708ac50d3f0…`
- **passed** — **studio history release checks (release d5313306ce95)** (no time recorded, date only): Contributor credentials, lineage and current availability: 3 passed,81 deselected in4.73s; exact committed tree. (exit 0); Snapshot reproducibility: stale=[] (exit 0); Incremental secret scan: 34 commits,1070340bytes,0findings. Binary model weights are outside textual secret-scan scope. (exit 0)  
  `deploy/receipts/studio-history-release-checks.json` `d4d155cec01f…`
- **recorded** — **team media live** (no time recorded, date only): no checks listed  
  `deploy/receipts/team-media-live.json` `bae860d25926…`
- **recorded** — **KCNE1 binding-ΔΔG test — STOPPED at the preregistered coverage floor** (2026-10-31, date only): Verdict: INCONCLUSIVE by the preregistered criterion, decided before any GPU job was submitted.  
  `results/2026-10-31-kcne1-binding-ddg-STOPPED.md` `c48ce5789ba8…`
- **recorded** — **Closing one loop on *Astyanax mexicanus*: the oca2 exon-21 deletion in Molino cavefish** (2026-10-31, date only): Final status: loop CLOSED, result POSITIVE. The preregistered criterion was met as  
  `results/2026-10-31-oca2-exon21-molino-RESULT.md` `676e03ac5097…`
- **failed** — **Nebius CPU worker request (mechanobio-sweep-cpu)**: ResourceExhausted on quota compute.instance.non-gpu.vcpu: limit 24, aggregate requested 28; no job created  
  `results/resources/provider-outcome.json` `3343f987b531…`
- **failed** — **Google compute enable (an earlier attempt; the later readiness receipt in the Cost row supersedes its state)**: FAILED_PRECONDITION (UREQ_TOS_NOT_ACCEPTED); no VM created  
  `results/resources/provider-outcome.json` `3343f987b531…`

## Limits of this record (upstream)

- Provider preset allocations are requested capacity, not measured utilization.
- Telemetry records are historical sampled windows; they do not represent current GPU utilization.
- Provider billing meter was not queried; actual spend is unknown.
- Other workers may have provider usage, so the recorded Gemini requests are not total project or account usage.
- Only Nebius job allocation state was refreshed at observed_at; other evidence retains its own original timestamp.

Inventory `results/resources/resource-inventory.json` `6901748b1952…`. Agent activity beyond these files is not reconstructed upstream, and nothing was reconstructed here.

## Files fetched

| Path | Saved as | Bytes | sha256 (of download) | Matches digest quoted in snapshot |
|---|---|---|---|---|
| data/snapshot.json | raw/snapshot.json | 2823623 | `7db6bf00923b64fd94e6fbc6c769f18f529fe90d21d5c2dc3f99bb156986fa6a` | no digest quoted |
| artifacts/coordination/review-corrections.json | raw/review-corrections.json | 9274 | `e9064db6fe084f54067f6414c3596c6c34eb78ae3028354e05e9542f31b64159` | true |
| data/catalog.json | raw/catalog.json | 86491 | `b9c79d2e15376523f0cf8af6f487047427a3e46b43ddfbefe419f3c59c5629cc` | no digest quoted |
| artifacts/coordination/collective-review-evidence.md | raw/collective-review-evidence.md | 3368 | `be7813448c9dbf57b8f031353b781b7ea5f47b0705ffa2c8c9608da93ff26f5f` | no digest quoted |
