# Xenobot voxel designs as Formlabs-printable STL

Takes the voxel "organisms" evolved by the repo's xenobot simulator and turns each one into watertight
STL files for PreForm (Form 3/3+/4). Nothing here is biology: these are static casts of simulated designs,
scaled up for printing.

## Where the designs come from

- **Simulator**: `test-data/claim-tests/levin-papers/levin-2020-xenobots-06/voxsim.py` + `voxsim.mjs`,
  the pre-registered stand-in for the Voxelyze/VoxCad pipeline of Kriegman, Blackiston, Levin & Bongard 2020
  (PNAS, [10.1073/pnas.1910837117](https://doi.org/10.1073/pnas.1910837117); code
  `github.com/skriegman/reconfigurable_organisms`, pinned in that test's `result.json`). 5x5x4 workspace, each
  cell empty / passive / contractile, 2 Hz sinusoidal contraction, selection on net displacement. It keeps the
  paper's mechanism, it is not a port of its physics.
- **Existing champions** (`champion-s1` … `champion-s10`): the ten second-pass champions of claim test
  `levin-2020-xenobots-06` (`derived/pass2_champions.json`), evolved in "water" with phases fixed per clade,
  50 generations each. Their simulator fitness and the shuffle/fresh-phase controls are in that test's
  `derived/summary.json`.
- **New designs** (`designs/*.json`): `python3 evolve.py --seed N --env water|land --gens G` runs the same
  loop with a new seed and saves the genome, fitness curve and parameters. Runs here used 25 generations
  (the claim test used 50); the manifest records this per design.

## Files

| file | what |
|---|---|
| `voxel2stl.py` | genome → mesh. `blocky_mesh` is the exact union of voxel cubes (manifold3d). `smooth_mesh` blurs the occupancy on an 8x finer grid and isosurfaces it (marching cubes), giving the rounded xenobot look and removing the edge-only contacts between diagonal voxels. Also a CLI for one design. |
| `evolve.py` | evolve a new design with the unchanged claim-test simulator; plain `python3` + numpy + node. |
| `build.py` | builds `out/` for every champion and every `designs/*.json`. Run with the print venv: `../flying-zebrafish/.venv/bin/python build.py [--pitch 4]`. |
| `out/<name>/` | `_blocky.stl`, `_smooth.stl`, `_contractile.stl`, `_passive.stl` (the last two tile the blocky solid exactly, for a two-colour print or a paint guide), `_preview.png` (contractile red, passive grey-blue). |
| `out/plate_smooth.stl`, `out/plate_blocky.stl` | all designs laid out on one plate, 8 mm apart. |
| `out/manifest.json` | per design: source file + sha256, seed, simulator fitness, genome, bbox, volume, watertight check. |

## Print notes

- Units mm, Z up (the simulator's ground is z = 0). Default pitch 4 mm per voxel → each body fits in
  20 x 20 x 16 mm; `--pitch 6` for 30 x 30 x 24 mm. Real xenobots are under 1 mm across; the pitch is a
  print-scale choice.
- Every exported mesh passes `trimesh.is_watertight`; volumes of the split parts are asserted to add up to the
  voxel count. Smooth meshes keep ~95–100% of the voxel volume (σ 0.35 voxel, iso 0.4).
- Smooth bodies have thin necks where two voxels meet only along an edge. Measured on an isolated
  edge-touching pair (section through the shared edge): 1.5 x 1.2 mm at 4 mm pitch, 1.1 x 0.9 mm at 3 mm,
  0.7 x 0.6 mm at 2 mm. Formlabs' supported minimum is about 0.6 mm, so 4 mm pitch is comfortable, 2 mm is
  not. Blocky bodies have no such necks; their edge-only contacts are touching cubes, which PreForm accepts.
- Print the smooth plate for display; print `_contractile` and `_passive` separately in two resins if the
  cell types should be visible.

## What this does not establish

The xenobot print job ran on the hackathon's Formlabs printers on 2026-11-01 (reported by the project lead;
see `sponsors/FORMLABS.md`). No printed part has been photographed into the repo or measured. A printed resin part does not move; in the simulator the bodies move
because contractile cells pulse, which the STL cannot carry. Fitness values are simulator predictions
(dimensionless displacement over 10 s) and have never been compared with living xenobots.
