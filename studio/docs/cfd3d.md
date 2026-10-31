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
| `engineering/cfd3d/vlm.py`, `gates_vlm.json` | thin-surface vortex lattice for the v3 paired fins (CPU), analytic controls V1–V6 |
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

## GPU results (infra job `aijob-e00k0jpm34h4na3b99`, H100, packet `5af94b3f`, rc 0, complete)
Curated in `artifacts/cfd3d/gpu-v1/` with `receipt.json`. The transport hash was re-derived here from job.log
(1,855,111 B, `30b9fe61…`), and the 48 files are byte-identical to infra's raw copy. The candidate is `4a3b912e`
(v1 fish, fish3d `994aac4`).
- **Platform gates.**
  - CPU D8 equals its pin exactly.
  - CUDA D8/D16 match the CPU pins to 8e-6 / 2.4e-5 (relative): model behaviour reproduced, nothing more.
- **C1 sphere Re 100 stays FAILED.** |Cd| against 1.092 (recalled):
  - standard domain: 0.857 / 0.875 / 0.918 at D 8/16/32;
  - big domain: 0.839 (D 16) and 0.881 (D 32).
  - Resolution raises |Cd| by ~5% per doubling, and blockage adds ~4% at D 32. The bias is unexplained.
- **Fish, Cd_total on L_ref²** (`summary-gpu-v1.json`; all stationary within 0.2%):
  - Re 200: 0.1008 (L64) and 0.0890 (L128). The pair differs by 13.2%, so it is not grid-independent.
    Including the CPU cases, the sequence is 0.175 / 0.137 / 0.101 / 0.089 for L 24/32/64/128, roughly
    first-order.
  - Re 1000: 0.0403 (L128) and 0.0367 (L192), 9.8%. That is inside the 10% rule but **not** grid independence
    of a fixed body: the fin shells are a fixed 1.866 cells half-thick, so the simulated fins thin from 6.7 to
    4.5 mm as h shrinks.
  - **No physical force claim in either case** (C1 FAIL, sub-grid fins).
- **Surface-pressure closure fails.**
  - Summing the surface Cp rows recovers only 0.10 (L32) / 0.20 (L128) of the solver's own pressure force.
  - Body Cp_max is about 0.6, where stagnation should give about 1.
  - The rows are sampled 2–2.9 cells off the wall: attenuated near-wall values, not wall pressures.
  - Use them as a qualitative distribution only. A future packet must extrapolate to the wall and pass a
    frozen closure gate.
- **Videos.** `gpu_fish_L128_Re1000` and `gpu_fish_L192_Re1000` `render/flow.mp4` are from actual solver
  slices. Their captions carry the hash, sub-grid fins, low-Re and C1 FAILED.

## v3 paired fins: thin-surface VLM (CPU, `engineering/cfd3d/vlm.py`)
- **Why VLM.** The v3 membrane (0.10 mm) is 0.06–0.11 cells at L 128–256, and 2 cells would need
  L ≥ 4,614, so no WaterLily grid here resolves it. The VLM treats pectoral_L/R and pelvic_L/R as
  zero-thickness lifting surfaces. That is the approximation, not a resolution: inviscid, attached flow,
  Re-independent, no body, median fins left out.
- **Gates.** Frozen in `gates_vlm.json` (`1719b7d`) before the code existed. V1–V6 all PASS
  (`artifacts/cfd3d/vlm/controls.json`):
  - Helmbold, AR 6: 1.3%;
  - lifting line, AR 20: 0.08%;
  - refinement: 0.36%;
  - camber: 1.1%;
  - mutant fails;
  - mirror symmetry to 3e-16.
- **Transfer to claude-05's `panels.json` quads.** Panel force is split by sampled overlap area, so the vector
  sum is conserved to 1e-15. Quad dCp is the normal component. A pressure-only (membrane) load misses the
  tangential, suction part: about 7% of gross at 4° and 15% at 8°.
- **v3a and v3c** (48×16 lattice; at 72×24, CL changes 0.5% / 2.9% and pectoral quad dCp 5.1% / 8.3% RMS):
  - paired-fin CL on own area at 4°: 0.248 / 0.251; at 8°: 0.494 / 0.501;
  - area 52.9 / 67.7 cm²;
  - lift at 16 m/s in air (assumed speed): 0.20 / 0.26 N.
- **v3b does NOT converge.** CL at 0° goes −0.070 / +0.007 / +0.072 at 24×8 / 36×12 / 48×16 with either
  normal rule, while the input slope stays fixed. Its quad normals tilt up to 19° from the fin plane. No v3b
  lift is claimed. Geometry only: its pectoral mid-surface rises 3.55° toward the tail.
- **Regimes.** dCp converts to Pa per medium as dCp × ½ρU², tabled in each `vlm.json` (air 10/16/20 m/s;
  water 5/10 m/s, assumed). Applicability at glide Re_c 2–4×10⁴ assumes attached flow, which is untested here.

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
