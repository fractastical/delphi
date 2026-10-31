# PROTOCOL: GPU replication and numerical-sensitivity arms for the frozen NCA nonlinear-pattern sweep

Author `dx-gpuops-r1` (Claude Sonnet 5.5), Seattle PDT 2026-10-31. Freeze 1 of 2 (this file + hashes, committed BEFORE any reference or GPU run). Freeze 2 adds the CPU-reference-derived tolerance file, also committed before any GPU submission.
Review status: single-reader, not Codex-reviewed, accepted by no one. Evidence kind of every number produced: `simulated` (declared model). Nothing observed.

## What this is, and is not
* It **replicates** the frozen NCA sweep (`scopedesk/oracles/nonlinear_sweep/PREREG.md`, sha256 `0d338a94c61a98be22c56c594a58ff590cb6ec7508de2e1e74a9c2613326e91c`, origin commit `cb27cf2`) with solver A re-implemented as a batched torch program, and adds **numerical-sensitivity** arms (dt halved, grid doubled). It is a replication and a numerical-sensitivity study. It is NOT a new preregistered finding, and it defines no new outcome. Question, ensemble, horizons, outcome definitions, quantities R1–R3 and predictions P1–P5 are exactly those of that PREREG; I copy nothing by hand (the vendored code is the definition).
* Model-specific computational question about declared reaction-diffusion kinetics (Schnakenberg, Brusselator), 1-D, Neumann ends. It is not a claim about fin development or any tissue; no calibrated fin-tissue coupling exists.
* Whether a GPU is *necessary* is not claimed. The NCA PREREG judged CPU feasible (about 2.1 h with 2 workers). This run compares execution on event hardware.

## Frozen inputs
| item | sha256 |
|---|---|
| Full cell table (2,520 cells, `cells.full_table(10)`, canonical JSON) | `cc78ed9a00a064366abefe2d972e6dd4d504b28cd6b40140e142a534bcef2efc` |
| `inputs/full_cells.json` (that table plus header) | `9f1b7a8cc8f431d85c9d9af3964f2cd9d85a92437e44a31beff8592d2cf16f61` |
| `inputs/pilot_cells.json` (pilot subset, below) | `f79f2d6738955276625b97982bc16ff46b0e7a9e9b22543a41e052d0cf667ec2` |
| `frontier_compute/gpu_neumann.py` | `2e17a1d0051bb0cf064007c383657375e430f97249f6fdf42c19f78a19c140a1` |
| `frontier_compute/gpu_entry.py` | `3b5085aaf31100e6ab6eac94aa5166e9dd7a386cc6b4b766e96e0513e2367596` |
| `frontier_compute/cpu_reference.py` | `4c2a8fc15db2695a7d7ae6552fb306a84b2e81000a4832aedb76af5e0b844af6` |
| `frontier_compute/cpu_entry.py` | `ac5b7eafa3a867010b066e31959cefcf571bd2de13c0f86305fde97b8850bf06` |
| `frontier_compute/cells.py` | `f87514d6bef46a14fb2a726dcbd4ec8b9a185bb0ee98e5dd80d8e18d5b45ead7` |
| vendored `solvers.py` / `pde.py` (outcome metrics, CPU oracle A/B) | `5f68e73b5345099adc7ef74b0f25a9adc7451a7071c35d2deb26f7866dec0f50` / `30932c876c2e1981aa617c4d38bb8467c18ef632579f16fb28161770571335ee` |
All vendored files and their pins: `frontier_compute/vendor/SOURCE.md`.

## GPU solver (what is different from the CPU oracle, stated)
Same scheme as `pde._run`: Strang splitting, exact cosine-mode diffusion (orthonormal DCT-II), RK4 reaction, dt = 0.02, float64. Differences: (i) DCT-II applied as a dense matrix product, cells of different grid size zero-padded into one batch; (ii) adjacent half-diffusions merged (identical in exact arithmetic); (iii) RK4 reaction terms from `pde_oracle.solver.reaction` (the same formulas as `kinetics.react`); (iv) cuBLAS/torch summation order. Event rules mirror NCA exactly: snapshot after step round(0.9 n), divergence checked after 1-based step s when (s-1) % 200 == 0 (non-finite or |u|,|v| > 1e3), n = round(T/dt). Local equivalence test before freezing (CPU torch, 6 cells, T = 100, mixed grid sizes 40 and 81): max |u_gpu - u_cpu| = 3.6e-13 (evidence: test, one run; the real-horizon comparison is the pilot).

## Pilot subset (rule fixed now, applied before any result)
`model in {schnakenberg, brusselator}`, `draw in {0,1}`, `x in {2,4}`, `rho in {0.7, 3.0}`, `eps in {0.01, 0.3}`, `seed = 101` -> 32 cells. Includes linearly stable cells (rho 0.7, `out_of_scope`) and linearly unstable cells (rho 3.0, `applies`). Same seed and same continuous modal initial state on CPU and GPU (`solvers.ic_modal`).

## Reference and tolerance (rule)
Remote CPU job (Nebius, one serverless job, <= 4 vCPU, <= 60 min) runs `cpu_reference.py` on the pilot cells: solver A at dt = 0.02 and dt = 0.01 with fields, and the independent solver B (BDF). From these, per cell i: `e_dt,i = max|u_A(dt=0.02) - u_A(dt=0.01)| / |u*|` (u at T). `tol_i = max(1e-9, 2 e_dt,i)`. A cell is *step-converged* iff `e_dt,i <= 0.01`. The numbers are computed mechanically and committed as freeze 2 before the GPU job is submitted.

## Pilot controls and pass rule (GPU, 1 H100, <= 30 min server timeout)
GPU arms on the pilot cells: base (dt 0.02), dt2 (dt 0.01), grid2 (2N cells, dt 0.02), run in that order, inner budget 480 s (an arm not started within budget is recorded `not_run_out_of_budget`). Define `err_i = max|u_gpu(base) - u_cpuA(dt 0.02)| / |u*|`.
* C1 (agreement): for every step-converged cell, the categorical outcome of the GPU base arm (pattern flag, dominant mode, settled, diverged) equals CPU solver A's, and `err_i <= tol_i`.
* C2 (homogeneous control): every cell with rho = 0.7 and eps = 0.01 is non-patterned on both CPU A and GPU.
* C3 (unstable control): GPU and CPU A agree on every rho = 3.0 cell, and at least one rho = 3.0 cell is patterned on CPU A (otherwise C3 is recorded "not satisfiable" and stated).
* Inconclusive if more than 25% of pilot cells are not step-converged.
* PASS iff C1 and C2 and C3 (when satisfiable) and the job exits 0 with returned sha256 verified. Any failure, FAIL or INCONCLUSIVE, stops expansion; I report it as is. Non-step-converged cells, divergences and out-of-budget arms are reported, never dropped.

## Expansion (only after PASS; rule fixed now)
* Full frozen grid: all 2,520 cells, base arm, split into **two** one-H100 shards by paired seed (101 | 102), at most two concurrent jobs, server timeout 90 min each. Before each launch the controller re-reads the pool and our active jobs and yields lower-priority work if another team queues H100s; ten team H100s is a ceiling not a target; no job that is not mine is touched.
* Sensitivity arms dt2 and grid2 on the preselected subset `draw in {0,1,2,3,4}` (1,260 cells), same shards.
* Convergence category per cell: base vs refinement agree on pattern flag, dominant mode and final amplitude within 10% (the NCA `pde.solve` convention); otherwise `nonconverged`, kept.
* Post-run comparison with the NCA CPU rows (`rows.jsonl`, whichever cells they executed): agreement of GPU base with their solver-A metrics, reported as a fraction with the disagreeing ids. This is analysis, not a gate. I will not read the NCA rows before the pilot comparison is written.

## Reported at the end
Frozen hashes, exact job ids and names (`delphi-evolve-ops-*`), exits, controls, outcomes, per-arm runtime and hardware, response-surface tables (R1–R3 by stratum with unresolved mass), step/grid sensitivity and nonconvergence counts, field frames and amplitude time-series. Billable cost: the event exposes no price or usage receipt to participants; reported as **unavailable**, not zero.
