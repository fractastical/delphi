# Xenobot/Voxelyze packet for infra

From: `work/xenobot-simulators` (delphi-frontier), branched off
`origin/codex/frontier-demo-20261031` at `4662d6b`.
Packet commit: **`2aa54c6`**. Protocol frozen separately at **`7b9bd5d`**, before any
output existed.

I am not a cloud dispatcher. Nothing below was launched on shared compute by me,
and nothing below asks you to accept a result I have not measured.

---

## 1. What is ready and already measured (CPU only, no dispatch needed)

`Voxelyze` **builds and runs here**. This is a receipt, not a plan.

| fact | value | how it was obtained |
|---|---|---|
| upstream repo | `https://github.com/jonhiller/Voxelyze` | cloned |
| pin | `4287e365e11416dd108f2f361e9ec4c5a011a16c` | `git rev-parse HEAD` after checkout, asserted in `build.sh` |
| library version string | `voxelyze.0.9.92` | upstream `makefile` |
| licence of record | **LGPL-3.0-or-later** | declared in every `src/*.cpp` and `include/*.h` header |
| licence caveat | GitHub API reports `license: null` | there is **no LICENSE file at that commit**; the per-file headers are the licence. The API's null means "no detectable LICENSE file", not "unlicensed" |
| build | exit 0, 11.45 s | unmodified upstream `make`, `g++ 13.3.0`, Ubuntu 24.04 |
| full recipe build | exit 0, 17.85 s | `scripts/voxel_actuation/build.sh` from an empty directory |
| GPU needed | **none** | pure C++, no CUDA, no boost, no cmake |
| caps honoured | `MemoryMax=2G MemorySwapMax=0 TasksMax=128`, `nice -n 19` | every invocation |
| system changes | none | no apt, no install, nothing outside the work directory |

**Upstream build defect you will hit if you use the makefile as shipped.** Its default
`FLAGS` contain `-DPARDISO_5=1`. The archive then carries undefined references to
`pardisoinit` and `pardiso`, and any program linking it fails unless a commercial
Pardiso 5 library is present. Build with `FLAGS` overridden to drop that define;
`doLinearSolve()` is unused. `build.sh` already does this.

**Nothing here needs cloud GPU.** The longest single run was **8.6 s**. The whole
battery of 15 simulation runs and 11 analytic runs is a couple of minutes on two
cores. If you want it reproduced, reproduce it on a CPU box; do not spend a GPU
hour on it.

---

## 2. The concrete build blocker: voxcraft-sim cannot be probed here

`voxcraft/voxcraft-sim` is the GPU engine the computationally designed organism
line of work actually uses. It is **not** runnable on this host and I did not
attempt a partial build that would produce a misleading log.

| fact | value | source |
|---|---|---|
| pin | `dd8668f99ff74fb2fc2ee60deb91287a3b519d8f` | GitHub API, `master`, committed 2021-11-18 |
| repo licence file | **CC0-1.0** | `LICENSE` at that commit is the CC0 1.0 Universal text |
| build system | CMake >= 3.12, `project(... LANGUAGES CXX CUDA)`, C++17 | `CMakeLists.txt` |
| hardcoded | `set(CMAKE_CUDA_COMPILER /usr/local/cuda/bin/nvcc)` | `CMakeLists.txt:10` |
| other deps | Boost `filesystem thread chrono program_options`, static libs | `CMakeLists.txt` |
| pinned container | `nvcr.io/nvidia/cuda:10.2-devel-ubuntu18.04` | `Dockerfile` |
| README says | CUDA **10.1**, Boost 1.65.1/1.67.0 | `README.md` |
| arch selection | autodetects and takes the **newest** arch found, `-gencode=${CUDA_ARCH}` | `CMakeLists.txt:46-60` |

**Blocker, stated exactly:** this host has no GPU and no CUDA toolkit.
`nvidia-smi` is not on PATH and `/usr/local/cuda*` does not exist (checked with a
positive control: `/usr/local` does exist). The arch autodetection in `CMakeLists.txt`
probes a GPU at configure time, so even a CPU-only configure is not meaningful here.
The README/Dockerfile disagree with each other (10.1 vs 10.2), which is one more
reason the version question has to be settled by a run rather than by reading.

**I make no claim about whether voxcraft-sim works on a modern GPU.** I have not run
it. Below is the probe, not a prediction.

### Probe for infra to run, if you want this engine at all

Two arms, each with a definite pass/fail, both small:

**Arm 1 — modern toolkit.** Build at the pin in a current CUDA devel image
(`nvcr.io/nvidia/cuda:12.x-devel-ubuntu22.04`), forcing the target arch rather than
autodetecting:
```
cmake .. -DCUDA_ARCH=arch=compute_89,code=sm_89     # L4 (Ada)
cmake .. -DCUDA_ARCH=arch=compute_90,code=sm_90     # H100 (Hopper)
```
Expected failure mode if it fails: 2021 CUDA-10-era device code against a CUDA 12
toolchain. Capture the **first** compiler error verbatim; that is the useful artifact.

**Arm 2 — pinned toolkit, forward JIT.** Build in the pinned
`cuda:10.2-devel-ubuntu18.04` image and run the binary on the modern GPU.
This only works if the build emits **PTX**, and the current CMake line emits
`code=sm_XX` (SASS only) from autodetection. So this arm must pass
`-DCUDA_ARCH=arch=compute_75,code=compute_75` to keep a PTX fallback the driver can
JIT forward. Whether that JIT succeeds on sm_89/sm_90 is the question; I am not
asserting an answer.

**Acceptance for either arm:** `./voxcraft-sim -i demos/basic/ -o output.xml -f`
produces a non-empty history file and exits 0. Record the image digest, the driver
version, the GPU name, the exit code and the wall time. A build that compiles but
produces an empty history is a failure, not a pass.

**Budget:** this is a build probe. One short interactive session per arm. Do not
queue a sweep behind it.

---

## 3. Licence conflict you must not resolve in our favour

The project website `https://cdorgs.github.io/code` states, verbatim:
*"The source code and build instructions are distributed under an
Attribution-NonCommercial Creative Commons license"*, linking CC BY-NC 4.0.

The repositories it links carry **CC0-1.0 LICENSE files** at their roots —
`voxcraft/voxcraft-sim`, `voxcraft/voxcraft-viz` and
`skriegman/reconfigurable_organisms`, all confirmed from the actual file bytes and
the GitHub API.

These disagree. A reuser should rely on the LICENSE file in the repository they
actually clone and record that the website says otherwise. Do not quote only the CC0
because it is convenient, and do not quote only the CC BY-NC because it is cautious.
Quote both and name the conflict.

Separately: `reconfigurable_organisms` declares CC0 at its root and **vendors
Voxelyze** under `_voxcad/Voxelyze`, whose per-file headers declare
LGPL-3.0-or-later. The top-level CC0 does not obviously reach vendored third-party
code. Check per-file headers of that subtree before reusing it.

`reconfigurable_organisms` is also **source-only for a hard practical reason**, not
a soft one: its README requires Python 2.7, `networkx==1.11` and Qt4. All three are
end-of-life. Porting is a project, not a step.

---

## 4. What the measured run found, with the failures preserved

Full detail in `artifacts/voxel-actuation/summary.json`. Classification is explicit
in the artifact and repeated here.

### DISCOVERY (preregistered in `7b9bd5d` before any output existed)

Six actuation phase patterns, matched material, amplitude, frequency and duration:

| pattern | body lengths in 5 cycles |
|---|---|
| travelling | 0.3644 |
| longitudinal | 0.1532 |
| lateral | 0.1412 |
| dorsoventral | 0.0031 |
| checker | 0.0000 |
| uniform | 0.0000 |

Controls B (cte=0) and C (amplitude=0) are numerically identical and ~0, as they must
be. Control D removes friction and gives **exactly 0.0** horizontal displacement:
centre-of-mass x and y constant to nine decimals across all 241 samples while z ranges
0.009967–0.011017 m, so the body is demonstrably active and its horizontal centre of
mass does not move.

Timestep refinement: 0.15318 / 0.15189 / 0.15180 body lengths across a 4× dt range,
a 0.90% spread. **This is a convergence observation about dt on this one arm. It is
not a claim that the model converges in general**, and it is not a claim about arm G.

Two analytic positive controls reproduce their closed forms at ratio **1.0000**
(thermal expansion, and an end-loaded cantilever against `F L^3/(3EI)`), and three
must-fail mutants are rejected at ratios 1.2222, 1.1000 and 10.0000 — each while
settled and not diverged, which is the condition that stops a crash counting as a
negative control.

### FAILED CONTROLS, PRESERVED

**Arm E missed its predeclared bound.** 0.0175 body lengths against a 0.01 bound.
The argument behind the prediction was wrong, not the threshold: it assumed removing
gravity removes the normal force. With the floor enabled, actuation itself drives
voxels into the floor and generates transient normal force, so friction still acts.
Arm D is the control that actually isolates friction. **The threshold was not changed
and the miss is recorded as a miss.**

**Arm G did not converge under spatial refinement.** 0.1532 body lengths coarse
(5×3×3, 10 mm voxels) against 0.0188 fine (10×6×6, 5 mm voxels) — an 8.2× drop. The
protocol predicted no convergence and said so in advance. **There is no spatial
convergence claim anywhere in this packet.**

### POST-HOC (run after arm G to explain it; diagnosis, not confirmation)

Hypothesis 1, global damping, **REFUTED**: displacement *rises* with `zeta_global` at
both resolutions, so it is not a parasitic drag, and matching total drag widens the
gap to 15× rather than closing it.

Hypothesis 2, actuator-layout parity, **SUPPORTED**: at fixed 10 mm resolution and
fixed zeta, nx = 4, 5, 6, 7 give 0.0200, 0.1532, 0.0086, 0.0796 body lengths. Odd nx
moves 7.7×–17.8× further than its even neighbours. The `longitudinal` split at
`x < nx/2` confounded lattice resolution with layout asymmetry. **That is my own
encoding, not the engine.**

With that confound removed — the travelling-wave pattern sets phase as a gradient and
carries its own asymmetry at any nx — coarse gives 0.3644 and fine 0.3744 body
lengths, a 2.74% difference. **This is a post-hoc observation on one pattern at two
resolutions. It is not a convergence proof and must not be relabelled as one.**

---

## 5. What this is not

Generic soft-voxel mechanics under declared parameters. Nothing is calibrated to
Xenopus tissue, frog cells, cilia, or any measured organism. "Xenobot-inspired" names
the design pattern, not biology. This is not a reproduction of Kriegman et al. 2020
(PNAS 117(4):1853–1859, `10.1073/pnas.1910837117`) and it is not fish or frog
validation. No relation measured here is a biological law.

The rectifying ground reaction is part Coulomb friction and part global damping to a
stationary absolute frame. Voxelyze's global damping is a numerical term, **not a
fluid model**, so no swimming interpretation is available and the split between the
two mechanisms has not been measured.

---

## 6. Reproduction

```
git clone <delphi-frontier> && git checkout 2aa54c6
bash scripts/voxel_actuation/build.sh /some/empty/dir     # clones + pins Voxelyze
/some/empty/dir/soft_actuation   --pattern=travelling --out=/tmp/t
/some/empty/dir/analytic_controls --mode=cantilever --n=4 --F=3.472e-5 --simT=20 --out=/tmp/c
```
Voxelyze 0.9 contains no RNG and this driver introduces none, so repeat runs are
identical. **There are no stochastic replicates and no seed spread may be reported as
uncertainty.**

Trajectory data for animation is at
`artifacts/voxel-actuation/trajectory/travelling-voxels.csv` (241 frames × 45 voxels),
produced by this run. **No upstream recording is reused anywhere in this artifact.**
