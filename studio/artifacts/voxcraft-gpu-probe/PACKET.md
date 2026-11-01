# voxcraft-sim modern-toolkit H100 compatibility probe — frozen packet

**Archive** `artifacts/voxcraft-gpu-probe/voxcraft-h100-probe.tar.gz`
**sha256** `624065f577bc8bae9d27f596610a18b797bc9946605ccdec66db4ab9fcbd7285`
**bytes** 15415 compressed, 42.3 KiB uncompressed (injection budget ~48 KiB)
**deterministic** rebuilding the archive from the same inputs reproduces the same sha256.

```
mkdir -p /work/inj && tar xzf voxcraft-h100-probe.tar.gz -C /work/inj
bash /work/inj/run_probe.sh /work/run            # add --no-dep-install to forbid the Boost install
```

Return archive: `/work/run/out/probe-return.tar.gz` (logs + receipt + both histories + validation).
Receipt: `/work/run/out/receipt.json`.

One GPU, one arm, no sweep, no fleet. **No cloud job was launched from this branch.**

## What it does, in order

| stage | what | stop status on failure |
|---|---|---|
| 0 | records driver, device, compute capability, nvcc release and CUDA build string, cmake, g++, OS, NVIDIA env vars, Boost presence | `NO_GPU`, `NO_CUDA_TOOLKIT`, `NO_CMAKE` |
| 1 | fetches the pinned public archive and checks size **and** sha256 | `SOURCE_HASH_MISMATCH` |
| 2 | re-hashes 14 load-bearing files against the frozen pin | `SOURCE_FILE_HASH_MISMATCH` |
| 3 | greps the **fetched** CMakeLists for the `if (NOT DEFINED CUDA_ARCH)` guard | `CMAKE_GUARD_ABSENT` |
| 4 | installs the four Boost components, recording dpkg versions and static-library sha256 | `DEP_MISSING_BOOST`, `DEP_INSTALL_FAILED` |
| 5 | configures with architecture/config flags only | `CONFIGURE_FAIL` |
| 6 | `make -j2` under a 600 s cap; captures the **first** error and any device-sync evidence | `BUILD_TIMEOUT`, `COMPILE_FAIL` |
| 7 | runs the actuated and passive cases under 120 s each | `RUN_TIMEOUT`, `RUNTIME_FAIL` |
| 8 | validates history structure and the actuation contrast | `HISTORY_STRUCTURAL_FAIL`, `ACTUATION_DISCRIMINATOR_FAIL`, `INCONCLUSIVE` |

A **timeout is its own status**, distinct from a compile failure. There is no retry anywhere.

## `-DCUDA_ARCH` does survive autodetection — verified, not assumed

`CMakeLists.txt:47` is `if (NOT DEFINED CUDA_ARCH)`. Defining it on the command line skips
lines 48–56 entirely: the `CUDA_SELECT_NVCC_ARCH_FLAGS` call at 48 and the
`message(FATAL_ERROR "Nvidia GPU not found. Abort.")` at 54. The runner re-greps those exact
lines in the fetched bytes before configuring.

`-DCMAKE_CUDA_ARCHITECTURES=90` goes with it because `project(... LANGUAGES CXX CUDA)` at
line 12 runs **before** line 47, so CMake picks its own default architecture first; line 60 then
appends `-gencode=${CUDA_ARCH}` globally and lines 78–83 add the same flags again per target.
Three targets have `CUDA_SEPARABLE_COMPILATION ON`, and device linking needs a consistent
architecture set.

**Adapter action is those three flags. Zero upstream source bytes are changed.**

## Predicted first failure — a prediction, not a result

`src/VX3/VX3_VoxelyzeKernel.cu` contains **eight device-side kernel launches and eight
device-side `cudaDeviceSynchronize()` calls** inside `__device__` member functions: launches
at lines 230, 267, 301, 310, 426, 434, 443, 454, 471, each followed by
`VcudaDeviceSynchronize()` (macro at `src/Utils/VX3.cuh:70`) at 232, 269, 303, 312, 428, 437,
446, 473. The enclosing functions are `updateTemperature()` (219), `doTimeStep()` (237),
`updateAttach()` (401) and `updateDetach()` (461).

That is legacy CUDA Dynamic Parallelism. Device-side `cudaDeviceSynchronize()` was deprecated
in CUDA 11.6 and removed in CUDA 12.0. **So I expect `COMPILE_FAIL`, first at
`VX3_VoxelyzeKernel.cu:232`.**

**If it fails that way: record it and stop.** Do not patch the synchronisation out — removing a
device-side sync changes the integration order, which is a semantic change, not an adapter
action, and the repaired build would answer a different question. **If it does not fail that
way, that is the more interesting result** and the run proceeds to the history checks.

The supplied image digest
`nvcr.io/nvidia/pytorch@sha256:11e9976339d08669ede155cdbc601b1df5f57772fcee772b23527efc54e05602`
is used as given, and **its toolkit is not assumed to support device-side synchronisation**.
The compiler's own output is the evidence.

## Source identity

| | |
|---|---|
| commit | `dd8668f99ff74fb2fc2ee60deb91287a3b519d8f` |
| archive | `https://codeload.github.com/voxcraft/voxcraft-sim/tar.gz/dd8668f99ff74fb2fc2ee60deb91287a3b519d8f` |
| bytes | 1,247,489 |
| sha256 | `0a0f4fd105a8df21df8b62a7d00e5178096d28415f2fb9f1679f6c78fd2c6546` |
| measured | fetched twice from this host, byte-identical both times |
| cross-checked | all **403** git-tracked files extracted from this archive hash-match a manifest computed from a clone at the same commit: 0 missing, 0 mismatched |

The 403-file manifest is **not injected** (48 KB on its own); it lives at
`artifacts/voxcraft-gpu-probe/source-manifest.json`. The injected pin carries 14 load-bearing
files, which is enough because the archive sha256 already covers every byte.

If the archive sha256 ever stops matching, the runner **stops**. GitHub's gzip output is not
contractually byte-stable, and the sanctioned alternative is a clone with a
`git rev-parse HEAD` check — selected explicitly, never silently.

## The two cases differ by one line

`<VaryTempEnabled>1</VaryTempEnabled>` versus `0`. Everything else is byte-identical.
A 4×4×2 = 32-voxel body at 10 mm lattice; all 32 are surface voxels, so all 32 appear in the
history. Every VXA key used was read from the source at the pin, with its line number, and is
listed in `probe.json`.

The actuation law, from `VX3_VoxelyzeKernel.cu:636-646`:
`T(t) = TempAmplitude * sin(2π(t/TempPeriod + phaseOffset))`, **clipped at zero** because
`EnableExpansion` is 0, so voxels only contract. `TempBase` is **not** used on the CUDA path.
With CTE 0.01 and amplitude 10 the zero-stress extent should run 10.0 mm down to 9.0 mm.

Material baseline (`Elastic_Mod` 1e5, `Density` 1e3, `Poissons_Ratio` 0.35, `uStatic` 1,
`uDynamic` 0.8) comes from `demos/basic/base.vxa` at the same commit. **CTE, amplitude and
period are our assumed values with no measured referent.**

## Acceptance is structural, not "non-empty"

The history is written by `printf` from **inside a `__global__` kernel**, so it passes through
the CUDA device printf FIFO ring buffer. **On overflow, lines are dropped silently**, and a
non-emptiness check passes on truncated output. So the validator requires step indices spaced
at exactly the stride the program itself reports, a constant voxel count of 32, exactly 15
numeric fields plus one trailing empty per voxel block, all finite, and no `Diverged`.

The actuation discriminator uses the PPP−NNN corner extent, which carries both the thermal
factor and the elastic strain (`VX3_Voxel.cu:147-158`): the actuated run must oscillate by
≥ 0.5 mm, the passive control must be at least 3× quieter, and the actuated mean must be
*smaller* because the clip permits only contraction. A2 or A3 failing returns **INCONCLUSIVE**,
not a pass.

## The validator was itself tested before asking for a GPU

On the host CPU, against synthetic histories: the positive control passes, and **nine must-fail
cases all fire** — no actuation, a lively control, dropped frames, too few frames, a deleted
field, a doubled comma, a wrong voxel count, `Diverged`, and an empty file.

**One gap the controls caught:** the first validator filtered empty comma-separated items, so a
doubled comma was absorbed and a malformed-block case **passed when it had to fail**. The parser
now requires exactly 15 values plus one trailing empty. Recorded because a validator that was
not itself tested is not evidence.

The runner's own failure path was also exercised: run on this host, it stops at `NO_GPU` in
preflight and still writes a receipt and a return archive.

## Scope

A compiler and runtime compatibility probe on a numerical soft-voxel engine. **No biological
fidelity is claimed or implied, and no convergence is tested.** The existing CPU preregistration
stands unchanged — including the arm E miss at 0.0175 against a 0.01 bound, the arm G spatial
non-convergence at 8.2×, and the withdrawal of the 2.74% travelling-wave figure for 15.5739% at
a common denominator.

**No second arm and no fleet before this one returns.**
