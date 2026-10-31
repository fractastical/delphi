# cfd3d: 3-D incompressible flow around the fish3d candidate (WaterLily.jl)

Single reader, not Codex-reviewed. Branch `work/cfd3d`.

## What it is
- **Solver.** A fixed, rigid fish3d candidate in a uniform stream. It uses
  [WaterLily.jl](https://github.com/WaterLily-jl/WaterLily.jl) 1.10.0: 3-D incompressible Navier–Stokes on a
  uniform Cartesian MAC grid with a BDIM immersed boundary (Weymouth & Font, CPC 2025, doi
  10.1016/j.cpc.2025.109748, arXiv 2407.16032; cited from the brief, not re-read here).
- **Geometry.** WaterLilyMeshBodies 0.2.0 turns the hashed component STLs into signed distances:
  - body and eyes are closed volumes;
  - fins and opercula are shells of half-thickness 1.866 cells.
- **Environment.** Julia 1.12.7 from the official tarball (sha256 pinned), with a pinned Manifest in
  `engineering/cfd3d/env`.
- **Not built here.** No homemade solver is involved.

| file | role |
|---|---|
| `engineering/cfd3d/gates_cpu.json` | reference gates, frozen in `609d1cf` before any run |
| `engineering/cfd3d/controls.jl` | C0 empty stream, C1 sphere Re 100 (D 8/16), C2 viscosity mutant; PLATFORM / GPU_DIAG modes for the container |
| `engineering/cfd3d/fish.jl` | one fish case → `case.json`, `forces.json`, `surface/*.f32`, slices, SDF (contract: `messages/cfd3d-to-coupled-mechanics.md`) |
| `engineering/cfd3d/render.py` | video from the actual solver slices (no interpolated frames) |
| `engineering/cfd3d/summarize.py` | grid pairs, time-window stationarity, simulated vs intended Reynolds regime |
| `engineering/cfd3d/gpu_entry.py`, `cfd3d_launch.py`, `build_packet.py`, `packet.json` | portable GPU packet (infra dispatches) |
| `tests/test_cfd3d.py` | packet/artifact/summary checks (no solver run) |

## Results so far (CPU, this host, measured)
- **Reference gate (2 threads, 380 s).**
  - C0: PASS (|u − U| = |div u| = 0.0).
  - **C1 sphere Re 100: FAIL.** |Cd| is 0.875 at D 16 and 0.857 at D 8 against the Schiller–Naumann
    correlation's 1.092 (recalled). The frozen band was [0.95, 1.35].
  - C2 mutant: PASS (1.91, outside the band).
  - Diagnostic D1 (10×6×6 D domain, convective exit): |Cd| 0.839. So the ~20% low bias is not blockage or
    the inlet gap. Whether it shrinks at D 32 is a GPU diagnostic.
  - **Until it is explained, no case here supports a physical-force claim.**
- **Fish (fish3d `994aac4`, candidate `4a3b912e`), Re_L 200, stream +x.**
  - Cd_total on L_ref² was 0.175 (L 24) and 0.137 (L 32).
  - **The pair differs by 27.8%:** it is not grid-independent, so no force claim is made.
  - The flow is stationary within each run: tU/L windows 2–3 and 3–4 differ by 0.2–0.3%.
  - An L 32 re-run reproduced the coefficients exactly.
- **Sign.** WaterLily's `pressure_force` is +∑ p·n·ds with an outward n (force on the fluid). Reported
  coefficients are body forces (−F).

## Limits that decide every reading
1. **Fins are sub-grid.** Plates are 0.5 mm, while h is 7.2 mm at L 32 and 0.9 mm at L 256. A fin needs
   L ≥ 923 cells to be 2 cells thick. The simulated shell is 3.7 cells thick (26.9 mm at L 32). Fin loads are
   refused, and claude-07's adapter refuses them too (MEMBER_UNRESOLVED).
2. **Regime.** For a fixed body in incompressible flow, air and water differ only through Re_L (and ρ when
   Cp is converted to Pa).
   - Re_L 200 is 13 mm/s in air or 0.87 mm/s in water.
   - The intended regimes are air glide ~1.5–3×10⁵ and underwater burst ~1–2×10⁶. Those speeds are assumed
     and unsourced.
   - No free surface, no motion, no taxiing.
   - **Low-Re numerical demo; not flight- or swim-validated.**
3. **Motion.** None yet. Behaviour coupling (frequency, phase, hinge motion) would come through
   `MeshBody` `update!` after the fixed body.

## GPU packet
- **Size.** 40.5 KB xz, under the ~45 KB injection limit. It carries code only:
  - the container rebuilds the fish3d STLs from fish3d's own builder with pinned wheels, and refuses on any
    sha256 drift (verified locally byte for byte on Python 3.12 and 3.13);
  - it rebuilds the Julia env from 103 exact pins, digest-checked against the local Manifest.
- **Gates in order:** CPU platform gate, then CUDA platform gate (both reproduce the local pins: model behaviour
  only), then the D 32 diagnostics, then the fish cases (L 64/128/192 at Re_L 200/1000).
- **Status.** `status.json` reports complete/partial/failed. `science` is always "model diagnostics only; C1
  FAILED". Dispatch and receipts: `messages/cfd3d-to-infra.md`.

## Reproduce (from the repo root)
```
JL=/data/artifacts/delphi-evolve-rethink/cfd3d/jl.sh     # capped runner: TasksMax 128, MemoryMax 4G, swap 0, 600 s
$JL --project=engineering/cfd3d/env engineering/cfd3d/controls.jl OUT.json all
$JL --project=engineering/cfd3d/env engineering/cfd3d/fish.jl engineering/cfd3d/cases/fish_L32_Re200.json OUTDIR
python -I engineering/cfd3d/render.py OUTDIR      # needs numpy + matplotlib, ffmpeg or imageio-ffmpeg
python engineering/cfd3d/summarize.py artifacts/cfd3d OUT.json fish_L24_Re200 fish_L32_Re200
```
Raw fields and slices live outside git, under `/data/artifacts/delphi-evolve-rethink/cfd3d/runs/`, with sha256s
in `artifacts/cfd3d/raw-manifest.json`.
