# Dedicated infrastructure queue

The infra director owns dispatch readiness and collection. GPUops owns the
dt-quarter and cylinder interpretation. The multiscale science worker owns
OpenMM controls and the derivative-oracle repair.
The bioservices harness stopped after its existing Evo2 run; its safeguard is
preserved and no new sequence-generation request is being routed elsewhere.

- [x] Dispatch the timestep-quarter follow-up: 33 changed cells and 48 controls.
- [x] Dispatch 357 missing atlas perturbation cases plus 48 fixed repeats.
- [x] Collect the original fish CUDA numerical checks from actual job output.
- [x] Queue one warm allocation with four workloads: recover truncated fields,
  then compare 0°, 4° and 12° angle controls at two grid resolutions.
- [x] Collect the timestep and perturbation allocations: all requested rows
  returned. The tiny initial-state perturbation comparison had zero flag changes;
  two patterned-mode differences remain in the separate timestep refinement.
- [x] Recover all four angle-batch parts, including full original field arrays.
  All six angle/grid cases passed the frozen numerical bounds; four tests reject
  corrupt field evidence, nonfinite coefficients and a failed parity gate.
- [x] Dispatch and collect the cylinder model after its CPU analytic controls.
- [x] Preserve the first molecular attempt's failed force-gradient check and
  recover its complete System/State archive with the exact provider hash.
- [x] Fix a transport defect that removed legitimate identical base64 chunks.
  Four tests check repeated payloads, query overlaps and corruption.
- [x] Dispatch one molecular retry after a specific derivative-oracle diagnosis
  on the recovered state. Physical parameters and original tolerances remain.
- [x] Collect the molecular retry: three actual 100 ps CUDA trajectories,
  303 finite saved states, all 20 output hashes checked and all numerical controls
  passed. Equilibration, experimental accuracy and tissue-to-fin transfer remain unknown.
- [x] Admit the useful remote 4-vCPU Morpheus packet at 15:17:17 PDT. Three
  one-thread arms continue the original full horizon; earlier local partials remain.
- [x] Integrate GPUops' frozen cylinder interpretation and corrected field videos.
  Cylinder numeric gates passed; the literature bands remain source-unverified.
- [x] Collect all three Morpheus arms through the full t=2 horizon. Thirteen
  output hashes matched; final cell counts were 256, 128 and 263. The first
  wrapper failure remains distinct from the successful recovery attempt.
- [x] Dispatch the controlled 3D WaterLily packet after its packaging, runtime
  and status contracts were frozen. It stopped at the candidate metadata hash:
  all twelve STL hashes matched, but candidate JSON differed. No CFD ran.
- [x] Diagnose the exact metadata difference on remote CPU: NumPy AVX-512
  dispatch changes three float64 widths by one or two ULPs. Disabling that
  dispatch reproduces the original hash. No geometry gate is relaxed.
- [x] Admit repaired CFD packet7abfc640 at15:45:57PDT with the frozen
  geometry-only SIMD setting.
  The failed physical sphere reference remains visible independently.
- [x] Dispatch the conditional RD diffusion training pilot at 15:36:40 PDT.
  The frozen CUDA control must pass before training and held-out evaluation.
- [x] Preserve the first RD CUDA-control failure: network maxdifference
  0.001191914 exceeded0.001; no training or holdouts ran.
- [x] Admit a preregistered precision-only diagnosis and conditional retry.
  The source/config/tolerance remain fixed; explicitFP32 controls must pass.
- [x] Recover the trained checkpoint after the primary timeout, then recover full held-out comparisons in a separate evaluation-only job; the primary failure remains.
- [x] Admit a separate training-only RD discretization audit, five axial
  grid/timestep settings, hard900s; no network/holdout changes.
- [x] Queue a CPU-only diagnostic for the 3D candidate hash mismatch; preserve
  the exact GPU failure and all three full candidate JSON variants.
- [x] Admit three900ps MD branches at15:45:34PDT after publicHTTP200 and
  exactarchiveSHA. Frozen question measures remaining structural drift,
  not equilibrium or a tissue modulus.
- [x] Collect MD extensions:33filehashes,303finite savedstates, original
  controls passed; frozen window-drift resultsFALSE,FALSE,TRUE retained.
- [x] Collect repaired CFD: four 3D cases, twelve pressure arrays and two actual-field movies; the frozen physical sphere reference still FAILS.
- [x] Collect all five training-only RD audit configurations and 960 paired rows. The independent full derived-metric reproduction FAILED; all 66 discrepancies concern nearly uniform-field spectral-power ratios. Original values remain.
- [x] Unify the primary diffusion collection/publication audit before outputs arrive; 23 focused tests pass, including nonfinite rejection.
- [x] Collect the separate secondary evaluation and full generated arrays. Structural completeness passes, but strict metric reproduction fails; undefined ratios and every failed scalar remain visible.
- [x] Return all 23 pinned public-genome survey records from the Google CPU worker; preserve the species deviation and ten unscored records.
- [x] Collect 26 of 28 paired ecology scenarios, including all trace files; preserve two unstarted deadline rows.
- [x] Dispatch and collect the missing-only two-scenario ecology continuation. Combined coverage is28pairs/56simulations; the original partial is unchanged.
- [x] Collect the original four-model NCA comparison: all52evaluations returned,0/48design checks passed. Preserve exact original archive and metadata-clipping failure.
- [x] Admit a separate seed-placement comparison with unchanged source/criteria and reused evaluations; all52evaluations returned; 32/48design checks; native independent audit c34c372 retains left-half0/12.
- [x] Admit Google L4 controls: pinned environment plus CPU and CUDA restart checks passed.
- [x] Collect L4 same-state parity and calibration. Numerical controls passed; runtime NO-GO stopped R2 before any assay. Five later capacity attempts failed.
- [x] Admit H100 controls/calibration only; actual Julia setup started, no R2cases selected.
- [x] Collect H100 controls/timing: original numerical gates and5907s conservative runtime projection passed. Native rc10/providerFAILED preserve intentionally absent cases.
- [x] Freeze scoped production checkpoint transport after actual tiny upload, hash and cancellation checks; full-size scientific checkpoint transfer remains unmeasured.
- [x] Admit and collect all36 aeroelastic CPU arms;161file hashes checked, native independent exact numerical reproduction a54f478 reported.
- [x] Admit and collect all eight BETSE trajectories; preserve native render-stage failure. Local report/video recovery uses the existing arrays. Metabolic worker remains provider-stopped.
- [ ] Collect the three already-running CPU cylinder cases and exact checkpoints.

The angle batch requires a passing parity check in the same allocation. Its
subsequent workloads reject a missing or failed gate. The original 3 MB return
cap discarded a 6.78 MB field archive; that failure remains recorded. The new
12 MB cap was selected before the recovery run. Returned hashes and actual
field trajectories are required before videos or downstream evidence are added.

These simulations are declared models. The earlier fish flow was a two-dimensional,
low-Reynolds sagittal projection of a print mesh. It cannot establish the effect
of changing wing span, real flight performance or biological viability. The
projection limitation was checked on all three meshes at three resolutions.

Provider startup and scientific work are separate clocks: the original fish job
spent about 14 minutes pulling its image and 34 seconds computing. Frozen warm
queues combine useful serial work under one pull and exit when finished. They
do not keep an idle GPU alive. Current state is in the timestamped inventory;
past utilization windows and unmeasured spend remain explicitly separate.

The cylinder allocation measured 85.79% mean GPU utilization and a 98% peak
over 270 samples from 15:06:18 to 15:10:47 PDT on October 31. Its three numerical
runs took 267.1 seconds. The angle batch averaged 30.19% over its full 113-sample
window, including setup and artifact emission. These are recorded windows,
not current utilization. The newer inventory retains source CSV hashes.

Operators run `python -m frontier_compute.resource_snapshot` for public-safe
state. It refuses paginated lists instead of publishing incomplete counts and
retains no credentials, job environments or other teams' identifiers. The batch
controller enforces one GPU per job, the existing team ceiling, bounded runtime
and yielding to foreign queued demand. Only its own recorded job IDs may be
cancelled. It runs inside capped systemd units on this host.


The next 24-hour plan is the `preparation` array in
[`results/infra/queue.json`](../results/infra/queue.json), with owners, prepared
source/protocol commits, time estimates, admission requirements and stop gates.
The original NCA comparison completed4models/52runs, with0/48 design predicates passing. The separately frozen seed-placement comparison completed32/48design checks with the reused evaluation labels preserved. The exact-W1 evaluation has returned with a
retained strict metric-audit failure. The missing-only ecology continuation completed its two pairs; combined coverage is28pairs, and the original26-pair partial run remains immutable. The local
resolved-fin CFD protocol awaits its CPU controls and measured runtime; no extra
GPU is reserved for an unprepared packet. Pressure-to-mechanics work reuses the
returned 3D arrays with Reynolds-consistent units and explicit unresolved
physical-reference/fin-resolution limits. A new molecular protocol is only prospective; no additional packet is ready or admitted.

At the 2026-10-31 16:26:01 PDT accounting refresh, current Frontier jobs and exact-record
historical team jobs remain separate. The shared project's unmatched jobs are
**unattributed**, not asserted to be other teams. None of the broader historical
attribution grants cancellation permission.


At7:08pm PDT on October31, the two admitted H100 jobs were starting/provisioning, not yet measured busy. They test seed placement and same-source CFD hardware timing. Full R2 remains blocked on measured runtime and coherent checkpoint transport; the original L4 NO-GO is preserved. Google VM03 remains the only running scientific CPU worker (16vCPU); five later L4 capacity attempts returned stockouts. Original NCA telemetry measured90.85% mean GPU utilization over724samples from6:39:46–6:51:49pm PDT, alongside0/48 design checks. Exact archives/transport recovery are retained in results/infra/nca/recovered.

At7:40pm PDT both H100 jobs were terminal: zero active Frontier GPU allocations. Seed-comparison telemetry measured87.91% GPU utilization over742samples from7:21:49–7:34:12pm PDT, including export. Tiny create-only resumable upload and restarted-controller cancellation passed actual GCS checks. Provider session TTL remains one week; the explicit cancellation deadline is an operator control, not a short provider expiry. Production adapter remains required.

At7:55pm PDT the fullR2 job aijob-e00gjhtd6nk55b266v was IMAGE_PULLING after admission7:52:53. BETSE VM04 was installing dependencies; actual20vCPU allocated across it and the existing16vCPU CFD worker. Latest7:52pm CPU samples were58.48% of16 and21.99% of4; these sampled windows include setup and are not current kernel measurements. The next NCA curriculum evaluation is independently committed atf5db91a before its source packet/admission.

At8:19:13pm PDT, three H100 jobs are admitted: NCA curriculum and the repaired R2 are IMAGE_PULLING, and the separately declared CUDA R1/M1/R3 comparison is PROVISIONING. None has current kernel telemetry yet. The original R2 admission was cancelled before science because its wrapper silently clipped a long budget; that defect and cancellation remain recorded. The control-arm first submission failed locally on total injection size, creating no cloud job; a tested operator/worker module split fixed that transport limit without changing its science. Google VM03 is the sole active16vCPU worker; its8:14pm sample was59.46%, approximately9.51busy CPUs. The8:17pm collected status retains all three original CPU cases running beyond their first checkpoint segments. BETSE VM04 has terminated after exporting all eight trajectories.

At8:55pm PDT the curriculum job had completed all8models/200probes;89/192 design predicates and8/8negative controls passed. The matched baseline45/96 versus curriculum44/96 retains targeted damage gains and persistence losses, not overall improvement. Both CFD H100 jobs are running; the three-arm job passed its frozen runtime gate and averaged86.32percent GPU utilization over the measured8:55:40–8:56:39pm window. No additional frozen packet is ready. Regulatory metadata preparation must meet its exact source/control contract before CPU admission. The original16vCPU Google cylinder worker and checkpoint collectors remain active.

At9:45:18pm PDT, the fresh shared queue had92 terminal records:61 exact/prefix-attributed team jobs and31 unattributed, with zero active H100 allocations. R2 and CUDA R1/R3/M1 returned all18 and20 native files respectively, independently size/SHA checked. Their unchanged total-drag fidelity bands fail; pressure coupling remains disallowed. Actual whole-allocation GPU sample means were58.20% for R2 and54.25% for the three-arm job, including setup and return. All five unused scoped upload sessions were cancelled. No new frozen GPU packet is ready; original Google CPU runs retain their bounded collector and separate backend identity.

At10:17:17pm PDT on October31, all92 Nebius job records were terminal:46 current Frontier,15 historical team,31 unattributed. Google live quota reads32CPU/16used and1GPU/0used; VM03 is the only running16CPU worker. The10:18pm CPU metric is59.52% of its allocation (about9.52busy CPUs), not an instantaneous value. Its latest exported status still has the three original CPU cylinder cases running; no complete CPU case is returned. No new admitted job is being claimed.

The renewed functional-DNA work first reuses existing outputs:32unique1,000bp Evo2 candidates have matching sequence hashes and scores, independently checked in `results/resources/evo2-reuse-audit.json`. Their eight target labels are not LEN/lepb, kcnh2a or fgf20a; likelihood/motif scores do not validate function or transfer contexts. The native evidence owner is extracting source-defined LEN/lepb and real reporter/endogenous-RNA controls. Regulatory quantitative-data availability and a small consequential aeroelastic resolution study have disjoint owners. A ready metadata-pairing replay is deliberately deprioritized because its answer already exists locally. No generated sequence is submitted for synthesis, no provider-stopped task is replayed elsewhere, and no new GPU workload is admitted without frozen inputs, controls and a distinct question.

At11:05pm PDT on October31, the45-arm aeroelastic packet was complete and VM04 had terminated. All45 arms were numerically valid but all27 effects were only sign-resolved, with magnitude decisions undetermined under unchanged criteria. Regulatory VM02 returned165usable of330identities and preserved partial_data exit3 after zero-byte206 index responses; owner10 is independently auditing, not blindly retrying. Only VM03 remained RUNNING with16allocated vCPUs; its11:02pm metric was59.66% (about9.55busy CPUs). No active GPU allocation is claimed. Owner15 is preparing one bounded modern-Voxcraft compatibility/control packet; its already completed VoxelyzeCPU evidence will not be replayed onGPU.

### 11:37pm PDT recovery and next admissions

- [x] Collect and independently rehash all nine missing-only regulatory artifacts (203,757 bytes). Native exit 3 preserves partial data: 106 usable of 165 recovery identities.
- [x] Read and rehash the owner-audited union: 271 usable of 330, 59 unresolved. One permitted recovery is exhausted; no further automatic retry.
- [ ] Admit one frozen Voxcraft H100 compatibility/control probe after immutable-output packaging fixtures pass.
- [ ] Admit the epithelial interval-threshold CPU sweep only after source/transport/finite-cardinality repairs. Thresholds remain intervals; descriptive and unevaluable gates are not passes.
- [ ] Review the source-grounded VLM analytic diagnosis before any additional fin simulation.

- [x] Admit Voxcraft job aijob-e00wfnzb38fccw6k57: accepted11:38:06pm PDT;11:42pm read IMAGE_PULLING, no kernel activity claimed.
- [x] Admit VLM4CPU worker04 at11:41:04pm PDT,900s science bound; native and diagnostic variants remain separate.
- [x] Admit epithelial8CPU worker02 at11:41:51pm PDT,5400s whole-tree bound; frozen interval/finite completeness criteria preserved.
- [x] Start bounded automatic collection services for both Google prefixes.
- [ ] Independently verify returned files and hand native science to their owners; retain compiler failures, incomplete families and unresolved brackets.

- [x] Collect all372 extended VLM solves; native extended collocation diagnostic supported, core unknown retained. Independent science audit pending.
- [x] Preserve Voxcraft native COMPILE_FAIL:39.1s runtime,12files/92,682bytes;40device samples all0%GPU. First Boost.Asio error plus actual device-sync CUDA incompatibilities. No simulation cases, source edits or blind retry.
- [x] Repair local collector overhead with30-second in-memory token reuse;16focused tests passed. No scientific packet changed.

### 12:26am PDT November 1 — current work and completed returns

- [x] Independently rehash 971 files from the 240-arm epithelial sweep. The native fixed-horizon interval criterion FAIL remains; interpretation and plot-caption corrections are under independent publication review, with no new simulation.
- [x] Finish the 372-solve VLM diagnostic audit. Its original production solver is unchanged. The distinct corrected-collocation packet is now running on Google VM04 with 4 vCPUs; its first 20 original numerical controls all passed. The 51 paired arms and five lattice-control groups remain pending.
- [x] Admit one bounded inverse Schnakenberg H100 job, `aijob-e00grxtt94bh26a9c0`, at 12:12:53am PDT. At 12:26:41am it was IMAGE_PULLING; zero current GPU kernel activity has been observed. Six new synthetic targets use equal 64-solver-evaluation budgets per method, with separate refinement and negative controls. This is a numerical pattern-design exercise.
- [x] Collect and independently stream-hash three original CPU CFD restart checkpoints: 1,185,906,124 bytes. They preserve partial R1/R3/M1 states; no completed CPU case is claimed. Their arrival follows the completed 795f140 backup cutoff and needs a separate add-on.
- [x] Refresh exact ownership: 94 Nebius records, 48 current Frontier plus 15 historical team records, 31 unattributed. One current job is pulling its image; all other records are terminal. Historical attribution does not grant cancellation rights.
- [x] Refresh Google allocation: VM03 and VM04 RUNNING, 20 of 32 vCPUs allocated, zero active GPUs. At 12:23am, provider CPU fractions were 59.35% of 16 and 19.96% of 4, including startup/control work. These dated measurements are not instantaneous utilization. Actual provider spend remains unknown.
- [ ] Collect and independently verify both new scientific returns; preserve failed controls and partial coverage.
- [ ] Add later checkpoint/results bytes to an encrypted private recovery snapshot after the next stable cutoff. The d87e5d1 full add-on and 795f140 source/deploy delta are already off-host decrypted and hash-checked.
