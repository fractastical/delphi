# PROTOCOL 5: refinement of the 2-D Navier-Stokes demo (resolve the CFL and time-step failures of Protocol 4)

Author `dx-gpuops-r1` (Claude Sonnet 5.5). Time from `date`: 2026-10-31 13:11:41 PDT. Frozen before the CPU controls and before any GPU job. Review status: single-reader, not Codex-reviewed. Evidence kind `simulated`. **Protocol 4's verdict (PARTIAL) is unchanged and its receipts are kept; this is a separate protocol and its result does not edit Protocol 4.** A failed numerical bound is not used as engineering evidence in either.

## What went wrong in Protocol 4, as diagnosed (observed, CPU, before freezing)
1. **The dt-halving "failure" (2.83e-3 at N = 512) was an artifact of my check**: the two runs used `n = round(T/dt)` steps, giving end times 1.9992 and 2.0004. On CPU at N = 128 (the demo's flow, nu = 1e-4): unequal end times (833 steps of 2.4e-3 vs 1667 of 1.2e-3) give relative L2 **2.47e-3**; equal end times (1000 steps of 2e-3 vs 2000 of 1e-3) give **3.4e-11**. So the failure measured a 1.2e-3 mismatch in time, not time-step error of the scheme. (Development probe, `scratchpad` script, run once; reproduced in the official controls below.)
2. **The CFL failure (max 0.864 > 0.5)**: the fixed dt = 1.2e-3 was chosen assuming |u| about 1; the speed reached 1.79 (observed in the Protocol 4 run). Not a stability failure (no non-finite values), a bound I set and missed.
Development run of `refine_controls.py` earlier in the same hour, honest record: a first draft assumed (a) that an under-resolved coarse case would reproduce the failure and (b) that a step 8x too large would be caught; both were false (differences 2e-8 and 2e-7), which is what led to the end-time hypothesis and to replacing those two controls with the controls below.

## Refined design (no duplicated simulations; one H100, 30 minutes, including paired validation)
All integrations use `dt = T / n` with integer n and compare fields only at exactly equal times.
* **A. The demo** at N = 2048, nu = 1e-4, T = 8, **n0 = 13,400 steps, dt0 = T/n0 = 5.970e-4** (CFL about 0.35 at |u| = 1.8; chosen from the observed maximum speed 1.79 of the earlier run). 72 frames of actual vorticity as in Protocol 4 (q8, low-passed to 128 x 128). The run provides its own snapshot at T/4 = 2 (step 3,350).
* **B. Paired partner at N = 2048** to T/4 only: dt0/2, 6,700 steps. **P1**: relative L2 of vorticity between A's snapshot and B at T/4.
* **C. N = 1024 runs** (shared by the order check and grid comparison): dt1 = 2 dt0 (6,700 steps to T, snapshot at 1,675), dt0 (13,400 steps to T, snapshot at 3,350), dt0/2 (6,700 steps to T/4 only). **P2**: dt1 vs dt0 at T = 8. **P3**: order check at T/4: ratio of ||dt1 vs dt0|| to ||dt0 vs dt0/2||. Grid comparison (reported, no threshold): N = 1024 snapshot vs N = 2048 snapshot (low-passed and 2/3-masked to 1024), same dt0, at T/4.

## Frozen criteria
* **CPU controls first** (`flow2d/refine_controls.py`, <= 2 threads): on a resolved case (N = 128, rho = 4, nu = 1e-3, T = 2, n = 200, 400, 800) the paired difference is <= 1e-4 and the ratio of successive differences >= 8 (4th order expects 16); on the demo's flow at N = 128 with equal end times the paired difference <= 1e-4; mutation M1 (unequal end times as in Protocol 4) must be caught by the 1e-4 criterion; mutation M2 (partner with nu x 1.1) must be caught. All must hold, else no GPU job.
* **P1** (N = 2048, T/4 paired) relative L2 <= 1e-4. **P2** (N = 1024, T paired) <= 1e-3. **P3** ratio >= 8. **P4** max CFL of the demo run (measured |u|) <= 0.5. **P5** max spectral divergence <= 1e-10, energy-budget residual <= 1e-3 relative, fraction of enstrophy above 0.66 k_max <= 1e-6, no non-finite value.
* Label: PASS if P1 to P5 hold; PARTIAL if the run completes and a named bound fails; FAIL if a CPU control or the run itself fails (non-finite). Whatever the label it is printed in the video caption. A PARTIAL or FAIL is not rerun with a changed bound.
* **Stop rule:** at most one H100 job of at most 30 minutes (inner budget 900 s) including all of A, B, C; **stop after two failed implementation attempts** (a job that errors or returns nothing counts as one; a scientific PARTIAL does not). Current count: 0.

## Reuse and consolidation
Reuses `flow2d/solver.py` (unchanged), `frontier_compute/telemetry.py` (assigned-device vs per-process telemetry, raw CSVs hashed) and `frontier_compute/render_flow_video.py` (same q8 frames format). NCA's glide package contains no Navier-Stokes solver (searched `engineering/` for navier, vorticity, lattice, poisson: none), so mine is the only candidate; there is nothing to choose between. No claim about fish, fins or flight.

## Frozen files (sha256)
| file | sha256 |
|---|---|
| `flow2d/solver.py` | `c3f4f5f2d62f5dedbd1eeefea3eaa1b3efa2bee72059faa74a9d760276991482` |
| `flow2d/refine_controls.py` | `644f2d729c7247d1036c4ca96c37c61ee95ab5f821b288ac228875e05d329c40` |
| `flow2d/flow_refine.py` | `a296a7960f3ceacab1a2b8d1137e36db7b9cbc1a24bee978d2118c06a0853e0f` |
| `frontier_compute/telemetry.py` | `983e046deaeedbfde9fe9f7cf0079301d061fdc6b720bfad723b62f32803c7a3` |
Telemetry raw CSVs will be verified by root from the raw files before any utilization figure is quoted; the 96.6% mean for the Protocol 4 run is stated with its sample count (52 samples over about 51 s) in PROTOCOL4.md.

## Run record P5-1 (written 2026-10-31 13:17:36 PDT by `date`, before the second submission)
**Attempt 1 failed at job creation (counts as one failed implementation attempt; no job was created, no GPU used).** 20:16:23Z: the API rejected the create call ("plaintext must not exceed 65536 bytes") although every injected file was under 64 KiB (parts of 40,960 and 6,883 bytes plus the 2,304-byte runner). With the earlier failure (61,250 + 2,304 B rejected) and the successes (about 29 KB total) the evidence says the limit is on the SUM of the injected files after base64 encoding (about 49 KB raw); this is an inference from three observations, not documented. Cause on my side: the item shipped the whole `flow2d` directory (controls, refine controls, demo) that this job does not need. Fix: explicit file list (`flow2d/__init__.py`, `flow2d/solver.py`, the entry, telemetry), bundle now 7,040 B; the controller now refuses a total above 60,000 encoded bytes (test added, 14 tests pass).
**Failed implementation attempts so far: 1 of 2.** One more submission is allowed; if it fails for an implementation reason the protocol stops and reports. Item file `inputs/items_flow_refine.json` (run tag `fflowrefine2`).
**Unrelated, same hour:** the controller's yield rule cancelled my held-out job on a false trigger and was fixed (PROTOCOL2.md E2-5); the fixed controller (`work/gpuops` @ `f7e92c7`) is the vendored one used here.
