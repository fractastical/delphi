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
- [ ] Dispatch the missing-only two-scenario ecology continuation after its packet freezes.
- [x] Admit the bundled four-model NCA comparison; training and 52 held-out results remain pending.
- [x] Admit Google L4 controls: pinned environment plus CPU and CUDA restart checks passed.
- [ ] Collect same-state parity and L4 calibration; run R2 only if the original time/memory gates pass.
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
The NCA comparison is admitted. The exact-W1 evaluation has returned with a
retained strict metric-audit failure. The next ready CPU admission is the
missing-only ecology continuation; its original partial run remains immutable. The local
resolved-fin CFD protocol awaits its CPU controls and measured runtime; no extra
GPU is reserved for an unprepared packet. Pressure-to-mechanics work reuses the
returned 3D arrays with Reynolds-consistent units and explicit unresolved
physical-reference/fin-resolution limits. No further molecular job is requested.

At the 2026-10-31 16:26:01 PDT accounting refresh, current Frontier jobs and exact-record
historical team jobs remain separate. The shared project's unmatched jobs are
**unattributed**, not asserted to be other teams. None of the broader historical
attribution grants cancellation permission.
