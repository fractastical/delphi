# PROTOCOL 2 (new, separately preregistered experiment): does pattern-conditioned mode comparison generalize to held-out cells?

Author `dx-gpuops-r1` (Claude Sonnet 5.5). Time from `date`: 2026-10-31 12:06:32 PDT (2026-10-31T19:06:32Z). Authorized by codex-03 (message after the pilot). Frozen BEFORE any held-out result (CPU reference, GPU, or otherwise) exists. Review status: single-reader, not Codex-reviewed. Evidence kind: `simulated` (declared model). Nothing observed.

## Retained from Experiment 1 (not altered)
* The frozen pilot verdict for Experiment 1 is **FAIL (C1)** and stands (PROTOCOL.md, "Pilot result"). It is not relaxed, not renamed, and not used to trigger the original expansion.
* The post-hoc finding "24 of 24 step-converged cells pass if the mode is compared only where patterned" was defined after seeing that FAIL. It is **post-hoc only**: it motivates this experiment, it is not a result of it, and it is not evidence that the revised criterion works.
* Why the old metric measured noise (observed in Experiment 1, a hypothesis here): all 12 failures were rho = 0.7 cells decayed to amplitude 2e-15 to 2e-13, where the argmax over DCT coefficients picks a roundoff component. On the 16 patterned pilot cells the mode agreed 16 of 16; on the 16 non-patterned cells it agreed 4 of 16. Experiment 2 tests this with a non-pattern noise control below.

## Question (single, model-specific)
On previously unscored held-out cells with an initial-state seed not used before, does the revised agreement criterion (below) hold between the GPU solver and the CPU reference oracle, with the whole-field, convergence, stability, noise and mutation controls behaving as stated?
It is a statement about numerical agreement of two implementations of declared reaction-diffusion kinetics (Schnakenberg, Brusselator) on a 1-D Neumann interval. It is not a claim about any tissue or fin; no correspondence between these kinetics and fin biophysics exists here.

## Held-out inputs (rule fixed now; `frontier_compute/heldout.py`)
* New initial-state seed **518331** (first 4 bytes of sha256 of the fixed string `delphi-frontier-heldout-v1`, mod 900000, plus 1000), distinct from the frozen 101/102. A second derived seed 478778 is reserved and unused (it seeds only the draw selection).
* Ensemble parameter draws: 3 of draws 2..9 chosen by `random.Random(478778).sample`; result **4, 5, 6**. The pilot used draws 0 and 1, so no parameter draw is shared with the pilot; no cell id is shared (ids offset by 100000; overlap with pilot ids = 0, checked).
* Cells: 2 models x 3 draws x x in {2,4} x rho in {0.7, 0.9, 1.5, 3.0} x eps in {0.01, 0.3} = **96 cells**, 48 linear `out_of_scope` and 48 `applies`. Everything else (horizon T, grid, K, outcome metrics, initial function family) is the vendored NCA definition at `cb27cf2`.
* `inputs/heldout_cells.json` sha256 `a04196e7b01629c8450da291408d96dcefb98ef06b149d35e6fbbc09d0e1998c`.

## Revised agreement criterion (R)
For a cell with CPU solver A (dt 0.02) result `a` and GPU base result `g`: if either diverged, they must agree on diverged; else pattern flag equal AND settled equal AND (dominant mode equal **only if the CPU cell is patterned**) AND whole-field `err <= tol`, where `err = max|u_gpu - u_cpuA| / |u*|` at T and `tol = max(1e-9, 2 e_dt)`, `e_dt = max|u_A(dt 0.02) - u_A(dt 0.01)| / |u*|` from the CPU reference. A cell is *step-converged* iff `e_dt <= 0.01`.

## Gate (all must hold; verdict PASS / FAIL / INCONCLUSIVE)
* **G1** every step-converged cell satisfies R (zero failures).
* **G2** homogeneous control: every cell with rho = 0.7 and eps = 0.01 is non-patterned on CPU and GPU.
* **G3** unstable control: every rho = 3.0 cell has equal pattern flags on CPU and GPU and at least one is patterned.
* **G4** checker mutations (applied to the real GPU results, one cell at a time, on cells that satisfy R): M1 dominant mode +1 on a patterned cell; M2 pattern flag flipped; M3 field error of 10 x tol added; M4 settled flipped. Each mutant must be rejected by R on **100%** of the cells it is applied to, with at least one application of each.
* **INCONCLUSIVE** if more than 25% of cells are not step-converged, or fewer than 8 patterned step-converged cells exist.
A FAIL is reported as FAIL; no gate is changed after results exist.

## Controls reported, not gating (their results qualify the diagnosis, not the verdict)
* **Non-pattern noise control:** mode agreement CPU vs GPU, and GPU base vs GPU perturbed, separately for patterned and non-patterned cells; the maximum amplitude of non-patterned cells. Stated expectation: non-patterned mode agreement clearly below patterned. If non-patterned agreement is >= 95%, the claim "the old metric measured noise" is **not supported** and I say so.
* **Design-intent check:** a +1 mode shift on non-patterned cells is rejected by the old rule and not by R (counts reported).
* **Stability control:** GPU arm `perturb` (relative 1e-10 multiplicative noise on the initial state, fixed per cell id); flag, settled and (patterned) mode agreement with base; flips listed.
* **Convergence controls:** GPU arms `dt2` (dt 0.01) and `grid2` (2N cells): flag flips, patterned mode flips, amplitude changes over 10%, diverged/missing listed. No pass/fail threshold.
* The old rule (mode on every cell) is computed alongside, never used as gate.

## Execution (bounded)
1. CPU reference (Nebius serverless CPU, one job, 4vcpu-16gb, 40 min stop bound): `cpu_reference.py` on `heldout_cells.json` (solver A at dt and dt/2 with fields, solver B). Tolerances computed mechanically (`compare tolerances`) and committed before the GPU job.
2. **One H100 validation job, 30 min server timeout**, arms base, dt2, grid2, perturb (inner budget 600 s), base-arm frames for the six video cells (100 frames each): `gpu_entry.py ... --frames <video ids> --nframes 100`. Pool and our active jobs re-read by the controller before launch; no job that is not mine is touched; ten team H100s is a ceiling, not a target.
3. `python3 -m frontier_compute.compare2` produces the verdict file. Receipts via `frontier_compute.receipts`.

## Conditional Experiment 3 (only if Experiment 2 verdict is PASS; registered now so it is not a post-hoc choice)
Full frozen grid (2,520 cells), base arm, two one-H100 shards (seed 101 | 102), 90 min server timeout each, at most two concurrent, started only after a fresh pool read and yielding to others. Reference: NCA `rows.jsonl` field A (sha256 `a32c2bf7dd3c10162317974ae6a0ecbefa06c1c180a6886dea1bcb8ea4d4c882`), which has no fields, so whole-field error cannot be computed there; the comparison is: diverged equal; pattern flag equal; settled equal; mode equal where patterned; relative amplitude <= 1e-6 **only where patterned** (for decayed cells the amplitude is a roundoff residual and a relative comparison is meaningless, the same defect as the old mode rule). Sensitivity arms dt2 and grid2 on the union of draws 0 to 4 and NCA's `id % 10 == 0`. Reported as a new experiment, not as a pass of Experiment 1. If Experiment 2 is FAIL or INCONCLUSIVE, no Experiment 3.

## Video artifact (actual trajectories)
The six video cells (ids 100618, 100604, 100514, 101878, 101864, 101774: per model, draw 4, x = 4, rho/eps = 3.0/0.01 (expected pattern), 1.5/0.3, 0.7/0.3 (expected decay)) return 100 frames of u(x,t) captured from the GPU run itself (the state after the Strang step at 100 equally spaced step indices, not including t = 0). A video is rendered from those frames only (profile animation plus space-time map), labelled with job id, solver, hash of the frames file, evidence kind `simulated`, and "declared model, not tissue". Nothing in a video is drawn or interpolated beyond frame display.

## Frozen files (sha256)
| file | sha256 |
|---|---|
| `frontier_compute/compare2.py` | `83abaec2042e6be292e92859f39e91d721e0bd59ec21d424d7de9841009bcbf1` |
| `frontier_compute/heldout.py` | `3e96e4ff9c35955db24b9d133a5e3255eb96e0ca46f48b610a02631a7ac244dd` |
| `frontier_compute/gpu_neumann.py` | `64ce2d6acf1010bda1c17454f760d31530e18364b931247e8a9e9c4919c758a5` |
| `frontier_compute/gpu_entry.py` | `33cead837a66a9c776527612ff2687502bb3872b5d6499c00b7f5c62b120457f` |
| `frontier_compute/cpu_reference.py` | `4c2a8fc15db2695a7d7ae6552fb306a84b2e81000a4832aedb76af5e0b844af6` |
| `frontier_compute/compare.py` (tolerances subcommand) | `44825b1c0bf5e92490fcdfd67eec08783be5278e472bceb5cd9109de65f1ba8f` |
`gpu_neumann.py`/`gpu_entry.py` gained optional `perturb` and frame-capture arguments after Experiment 1; the base-arm numerical path is unchanged (local regression: max field difference 1.1e-14 against the Experiment 1 version on two cells, CPU torch). The machinery of `compare2.py` was exercised once on the Experiment 1 pilot data (not evidence; all gates evaluated there, with the old rule rejecting 12 step-converged cells that R accepts). Cost: unavailable (the event exposes no price or usage receipt), not zero.

## Freeze E2-2 (written 2026-10-31 12:18:44 PDT by `date`; before the GPU validation job is submitted)
**Held-out CPU reference job:** `aijob-e00cs2drpmgzwtqy4h` (`delphi-evolve-ops-fcpurefho1-cpu-reference-heldout-a1`), Nebius serverless CPU 4vcpu-16gb, COMPLETED, controller rc 0, created 19:06:56Z, finished 19:18:03Z, in-container wall 518.1 s, returned bundle sha256 `e23fad1cb8a64f295b160ce20591ea6bcc2f47f184a19506be1d6a84c1bf4038` verified. Files: `cpu_ref.jsonl` `5379b20cd83cd3f1f3c9a19bb7ae1fd8d0a3bb6ec9c5ebf45a1780a53706ab21`, `cpu_ref_fields.npz` `20c948dd7bd2d03b274471e539e3e1c91c288e66cecac6890d6e17eded92cb0e`. Tolerances `inputs/tolerances_heldout.json` sha256 `aaa539cc25990a5e0ebdd75940f43e6fa117eb6d0e9ea3ef221650a74f1809f3`, derived mechanically.
**Observed on the CPU reference alone (before any GPU result):** 66 of 96 cells are step-converged; **30 of 96 = 31.25% are not**, which is more than the frozen 25% line. By the frozen rule the Experiment 2 verdict is therefore **INCONCLUSIVE regardless of the GPU outcome**. Not step-converged: Brusselator rho = 3.0 (12 of 12), Brusselator rho = 1.5 (8 of 12), Schnakenberg rho = 3.0 (5 of 12), Schnakenberg rho = 1.5 (4 of 12), Brusselator rho = 0.9 (1 of 12 patterned). Patterned and step-converged cells: 19 (at least 8, so that second inconclusive condition is not triggered).
**Decision:** the verdict is fixed as INCONCLUSIVE by the frozen rule; I do not change the rule. The authorized single H100 validation job is still run for its descriptive content, with the verdict label stated in advance: gates G1 to G4, the noise, stability and convergence controls, and the six real trajectories for video are computed and reported, but a G1 to G4 pass cannot upgrade the INCONCLUSIVE verdict. Experiment 3 is NOT triggered by this outcome. This observation is itself a result about the frozen protocol: at dt = 0.02, 30% of held-out cells (most strongly the patterned Brusselator cells at rho >= 1.5) change by more than 1% of u* in the sup norm when dt is halved.

## Run record E2-3 (written 2026-10-31 12:38:20 PDT by `date`)
**First held-out GPU run: results lost to MY size cap, not a scientific outcome.** Job `aijob-e00cmrs77wc8hp9snf` (`delphi-evolve-ops-fgpuho1-heldout-validation-h100-a1`), created 19:18:54Z, COMPLETED, in-container rc 0, wall 169.3 s; the job log shows all 8 arm/model batches finished and "done 384 rows 166.9 s" (base 19.5 s brusselator / 13.8 s schnakenberg, dt2 38.5 / 27.6, grid2 19.3 / 14.2, perturb 19.3 / 13.8 s of GPU wall; no stage timed out). The returned bundle was 1,029,842 bytes against my `max_result_bytes` of 900,000, and the in-container runner discards the bundle when it exceeds the cap (`data = b""`), so no result file exists and the controller marked the item `failed` (truncated). The job log (`results/compute/gpuheldout/.../job.log`, kept) is the only record of that run. I had set the cap before knowing the size. No result of that run was seen by me, so nothing was selected or discarded on the basis of its content.
**Rerun (same cells, same arms, same frozen tolerances, same criteria):** `inputs/items_gpu_heldout_rerun.json` (run tag `fgpuho2`, cap raised to 3,000,000 bytes). Differences from the first submission, all non-numerical: `gpu_entry.py` now also runs the bounded nvidia-smi sampler (`frontier_compute/telemetry.py`, assigned-device vs per-process labelled, raw files hashed) per the instruction received; new `gpu_entry.py` sha256 `396343bc68ac1634410c6bf89f2e32f7349081195389c05b3aee1efdb802f5d9` (the hash in the frozen table above is the first submission's). The base-arm numerical path is untouched. This is one further H100 job to obtain a result the first run should have returned; I report it as such and not as an additional experiment. The verdict is still fixed as INCONCLUSIVE by E2-2.
**Known controller weakness (mine):** a result over `max_result_bytes` is dropped silently in the container. Future payloads should print their expected size or the cap should be generous.
