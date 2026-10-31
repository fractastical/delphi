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
- [ ] Diagnose that exact metadata difference before any CFD retry. The failed
  physical sphere reference remains visible independently of the packaging issue.
- [x] Dispatch the conditional RD diffusion training pilot at 15:36:40 PDT.
  The frozen CUDA control must pass before training and held-out evaluation.
- [ ] Recover the trained checkpoint, hold-out results and baseline/null comparisons.
- [x] Queue a CPU-only diagnostic for the 3D candidate hash mismatch; preserve
  the exact GPU failure and all three full candidate JSON variants.
- [ ] Extend the three short MD states only after the exact warm-start archive
  is public and hash-checked. The frozen question measures remaining structural
  drift; it does not assert equilibrium or a tissue modulus.

The angle batch requires a passing parity check in the same allocation. Its
subsequent workloads reject a missing or failed gate. The original 3 MB return
cap discarded a 6.78 MB field archive; that failure remains recorded. The new
12 MB cap was selected before the recovery run. Returned hashes and actual
field trajectories are required before videos or downstream evidence are added.

These simulations are declared models. The current fish flow is a two-dimensional,
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
