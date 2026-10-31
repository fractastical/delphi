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

## Freeze 2 (committed before the GPU pilot is submitted)
Seattle 11:4x PDT, Oct 31. Changes since freeze 1, all non-scientific except the reference numbers: (a) `gpu_entry.py` gained a scipy preflight import (new sha256 `6ba25df65e45fbe5fc2a5212339bea9f5e5595ad768c439fe25cef93faf961bb`); (b) controller chunk size fixed (40 KiB, `__pycache__` excluded; delphi-evolve `work/gpuops` @ `1760198`), vendored copy re-pinned in `SOURCE.md`; the first create attempt failed with the API's "plaintext must not exceed 65536 bytes" and created no job.

**CPU reference job (Nebius serverless CPU, 4vcpu-16gb, python:3.12-slim, 40 min stop bound):** id `aijob-e00b95e1p1mkbtxa78`, name `delphi-evolve-ops-fcpuref1-cpu-reference-pilot-a1`, state COMPLETED, controller rc 0, in-container wall 183.9 s (controller 191.6 s), returned bundle sha256 `3f83e68ec5894b92be1bf05b5a45e6155f30ade9979f605f8f55dbe5be418615` verified. Python 3.12.16, numpy 2.5.4, 4 processes. Files (sha256): `cpu_ref.jsonl` `9ef545288a7681a06f19d0e047b8b2ee8d063a835d3af90830d1cce4c5c87ab9`, `cpu_ref_fields.npz` `f601aab76ad84340495328c026bb307e22e01912ef9fd5066d17bb92f22dedc5`, manifest `4fa6584dbd1cd52bc2a0b24356e1f132d70fbfa137a3ba5384e6f331045b594c`.
**Tolerances** (`inputs/tolerances_pilot.json`, sha256 `729794b36284b36f97493f79a94db10dd2ba697a41f770e0d219699aadb7968f`) were computed mechanically by `python3 -m frontier_compute.compare tolerances` from that bundle, by the rule above, before any GPU result exists.
**Result of the step-refinement on CPU (observed numbers, simulated model):** 24 of 32 pilot cells are step-converged (`e_dt` <= 0.01). The 8 that are not are the 8 Brusselator rho = 3.0 cells (`e_dt` 0.12 to 0.60; the pattern flag and solver B agree with solver A on all 8, but the field changes by that much between dt 0.02 and 0.01). That is exactly 25.0% non-converged, which is NOT more than 25%, so the pilot is not declared inconclusive by the rule as written; I record that it sits on the boundary. Those 8 cells are not gated by C1 but ARE inside C3 (GPU and CPU A must agree on the pattern flag for every rho = 3.0 cell). Schnakenberg rho = 3.0 cells have `e_dt` 1.9e-3 to 6.2e-3; all rho = 0.7 cells 1e-13 to 8e-13.
CPU solver A cost on this node was about 7 to 9 s per cell at dt 0.02.

## Amendment A (committed before the GPU pilot returns and before any expansion)
After reading `nca-to-gpuops.md` (NCA, 18:35Z, branch `work/rethink-nca` @ `02346812b93a6ee8c9e67c89b02ae6e2a69e51a7`), which declares NCA's own replay subsets and tolerances for the same frozen sweep. NCA's own torch port (`gpu_replay.py`, sha256 `07df1d29cf8c41449d07ac14d22267b38ed094e1ead0b807f9cfe2f18cefba02`) is NOT used here; this work uses its own independently written solver, so the two ports could in principle be cross-checked. Nothing in freeze 1 or 2 is changed; these additions are reporting rules:
* **NCA tolerances, reported not gating:** GPU base arm vs `rows.jsonl` field `A` (sha256 `a32c2bf7dd3c10162317974ae6a0ecbefa06c1c180a6886dea1bcb8ea4d4c882`): pattern flag equal on every non-diverged cell; dominant mode equal where patterned; relative amplitude difference <= 1e-6. Reported for all compared cells and for NCA's pilot subset `id % 100 == 0` (26 cells) and `id % 10 == 0` (252 cells) separately (`frontier_compute/compare_nca.py`). My gate for expansion stays C1-C3 above.
* **Sensitivity subset:** dt-half and grid-double arms are run on the UNION of my subset (draws 0-4) and NCA's `id % 10 == 0`, reported separately by subset. No pass/fail threshold; differences and any flag or mode flips are reported.
* **Speed report:** seconds per cell on the GPU base arm, versus NCA's 6 s per cell (CPU, torch) and my measured 7 to 9 s per cell (numpy solver A, Nebius 4-vCPU node). A pilot of 32 cells in one batch is launch-bound and overstates the per-cell GPU cost at full batch; the first full shard measures it. NCA's rule "if less than about 10x speedup, say so and do not expand [further arms]" is applied to the arms beyond the base replay, using the first shard's measured seconds per cell.
* The NCA rows are not read until the pilot comparison file is written.
* Receipts: `frontier_compute/receipts.py` collects job ids, names, states, returned-bundle sha256 and every file hash from the controller manifests (ids only, no URLs) for the OpenResearch adapter (dx-corpus).
