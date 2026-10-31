# Dedicated infrastructure queue

The infra director owns dispatch readiness and collection. GPUops owns its
existing wind-tunnel result and cylinder boundary-control development. The
multiscale science worker owns CPU controls and the pending OpenMM packet.
The bioservices harness stopped after its existing Evo2 run; its safeguard is
preserved and no new sequence-generation request is being routed elsewhere.

- [x] Dispatch the timestep-quarter follow-up: 33 changed cells and 48 controls.
- [x] Dispatch 357 missing atlas perturbation cases plus 48 fixed repeats.
- [x] Collect the original fish CUDA numerical checks from actual job output.
- [x] Queue one warm allocation with four workloads: recover truncated fields,
  then compare 0°, 4° and 12° angle controls at two grid resolutions.
- [ ] Collect and interpret those three allocations, including failed checks.
- [ ] Dispatch the CPU-controlled molecular-dynamics packet when ready.
- [ ] Dispatch the cylinder boundary model only after its controls pass.

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

Operators run `python -m frontier_compute.resource_snapshot` for public-safe
state. It refuses paginated lists instead of publishing incomplete counts and
retains no credentials, job environments or other teams' identifiers. The batch
controller enforces one GPU per job, the existing team ceiling, bounded runtime
and yielding to foreign queued demand. Only its own recorded job IDs may be
cancelled. It runs inside capped systemd units on this host.
