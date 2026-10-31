# PROTOCOL 4: 2-D incompressible Navier-Stokes demo (double shear layer) on one H100, after CPU analytic controls

Author `dx-gpuops-r1` (Claude Sonnet 5.5). Time from `date`: 2026-10-31 12:39:46 PDT. Frozen before the CPU control run and before the GPU job. Review status: single-reader, not Codex-reviewed. Evidence kind: `simulated` (declared equations). Priority set by the user; NCA informed by file.

## What this is
A fluid-dynamics simulation of the 2-D incompressible Navier-Stokes equations in vorticity form on the doubly periodic box [0, 2pi)^2, solved pseudo-spectrally (2/3 dealiasing) with an integrating-factor RK4 scheme in float64 (`flow2d/solver.py`). The demo is the Bell-Colella-Glaz style double shear layer (rho = 30, delta = 0.05), a standard roll-up test, at N = 2048, nu = 1e-4, dt = 1.2e-3, T = 8. Output: field frames from the run itself and diagnostics. **It is a numerical-fluid-dynamics demonstration. It makes no claim about fish, flight, fins or any biological flow.** (Flying-fish engineering would need a different geometry, boundary conditions and a validated aerodynamic or hydrodynamic model; none is claimed here.)

## Why GPU, honestly
A 2048^2 float64 spectral run of about 6,700 steps is large for a shared two-core CPU host (its 4 stage-FFT work is on the order of tens of CPU-minutes per 1,000 steps at 2048^2; not measured here). The CPU is used for all analytic controls at small N. No claim that a GPU is *necessary*; the run uses event hardware for a size the local host should not take on. The GPU timing is reported from the run, and telemetry is sampled.

## CPU analytic controls (run first, locally, <= 2 threads; `flow2d/controls.py`, results committed before the GPU job)
* **C-A** Taylor-Green vortex advected by a uniform mean flow: `w = 2 sin(x - U0x t) sin(y - U0y t) exp(-2 nu t)` is an exact NS solution; error at N = 64, nu = 0.01, T = 1, dt = 0.01, U0 = (1, 0.5). Tolerance rule: `max(1e-12, 3 x error at dt = 0.01)`, and the observed temporal order from dt = 0.02, 0.01, 0.005 must be >= 3.5. It tests viscosity, advection sign and magnitude.
* **C-B** Energy balance identity `dE/dt = -2 nu Z` on a nonlinear random smooth field: relative residual of `E(T) - E(0)` against `-2 nu int Z dt` (Simpson) must be <= 1e-3.
* **C-C** Temporal order on the nonlinear field against a dt/128 reference: observed orders >= 3.5.
* **C-D** Spatial convergence: N = 32, 48, 64 against a 96 reference on shared Fourier modes, error decreasing (reported).
* **C-E** Mutations: viscosity x 1.1, advection x 1.05, advection reversed; each must make C-A fail (100% kill).
All thresholds were written in `controls.py` before its first run (a development run happened before this freeze; it passed; the official run repeats it after the freeze with identical code apart from output paths).

## GPU job (one H100, 30 min server timeout, inner budget 900 s; pool and our jobs re-read by the controller)
1. Re-run C-A on the GPU at N = 512 (tolerance from the CPU rule) and a GPU-vs-CPU cross-check of the nonlinear N = 64 run (max abs difference <= 1e-10).
2. dt-halving at N = 512, T = 2 (dt 2.4e-3 vs 1.2e-3): relative L2 of vorticity <= 1e-4 (else reported as dt-sensitive); grid check N = 512 vs 1024 (the 1024 field low-passed to 512), reported, no threshold (512 is expected under-resolved for this shear layer at nu = 1e-4).
3. The demo run. Diagnostics every ~T/72: energy, enstrophy, max speed, CFL, max spectral divergence. Bounds: CFL <= 0.5, divergence <= 1e-10, no non-finite values; the energy budget residual and the fraction of enstrophy above 0.66 k_max are reported (resolution diagnostic; a large fraction means under-resolved).
4. 72 frames of the actual vorticity, spectrally low-passed to 128 x 128 and 8-bit quantized for return (mapping recorded). The video is rendered from these frames only.
Labels: PASS if 1, the dt-halving bound, and the demo bounds hold; PARTIAL if the run completes but a bound fails (named); FAIL if a control fails or the run goes non-finite. Whatever the label, the video carries it in its caption. The 2048 run's convergence is **not** verified beyond the spectral-tail diagnostic and the 512/1024 comparison.
Telemetry: bounded nvidia-smi sampler (assigned-device vs per-process labelled, raw sample files hashed). Cost: unavailable (no price or usage receipt), not zero.

## Frozen files (sha256)
| file | sha256 |
|---|---|
| `flow2d/solver.py` | `c3f4f5f2d62f5dedbd1eeefea3eaa1b3efa2bee72059faa74a9d760276991482` |
| `flow2d/controls.py` | `2ef546014e4ec2cb00f97ed3ef7fcb3552d4d169b310a67a9adbd25166ab5b4e` |
| `flow2d/flow_demo.py` | `99f1c78223619da0a0bc0de578bce5a763c28bf6c4a5541e997c8232f4893193` |
| `frontier_compute/telemetry.py` | `983e046deaeedbfde9fe9f7cf0079301d061fdc6b720bfad723b62f32803c7a3` |
