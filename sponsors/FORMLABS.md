# Formlabs: what we used it for

Science Claw Hack @ MIT, Oct 30 – Nov 1, 2026. Everything below is read from repository files or
GitHub issues named in each row. Issues: [#3](https://github.com/fractastical/delphi/issues/3)
(Formlabs integration), [#58](https://github.com/fractastical/delphi/issues/58) (actually print wings),
[#46](https://github.com/fractastical/delphi/issues/46) (printable wing, WP5).

## What was printed

Three kinds of object: two dragonfly hindwings (recorded on issue #58 with a photograph), several
flying zebrafish, and a plate of simulated xenobot bodies (both reported by the project lead; not yet
photographed into the repo).

### Two dragonfly hindwings: real venation beside a mathematical model

| | |
|---|---|
| Printed | Two 140 mm SLA prints of the *Arigomphus villosipes* hindwing on the hackathon's Formlabs printers, 0.6 mm membrane, 1.5 mm at the main veins and margin. Recorded on issue #58 ("printed", 2026-11-01 03:28 UTC; report 06:49 UTC) and in `assets/arigomphus-wing.jpg` |
| The two designs | Same outline and primary veins. One carries the vein network segmented from a photograph of the real wing (442 closed cells). The other regenerates the cross veins with the Hoffmann et al. 2018 rule (*PNAS* 115:9905: inhibitory centres at the real local density, Lloyd-relaxed, Voronoi edges; 480 cells) |
| Why | Hoffmann's claim is that the model looks like the real wing. The prints put that claim in a hand. The claim is in the MorphoEval audit (`test-data/morpholib/links.json`, `hoffmann-wing-venation`), and the README section "The wings: a model next to the real thing" lists each wing design decision as a Lean-proved claim (hollow spar `thompson1917-ch16-03`, wall thickness `ch16-04`), a data-tested one, or open |
| What it does not show | The scan comparison (`wing_compare.py`, in [morpholib](https://github.com/fractastical/morpholib)) has passed only on a simulated scan, so there is **no measured print-vs-design agreement** yet. The venation rule is a model tested on the specimen, not a Lean theorem |

### Several flying zebrafish (`fabrication/flying-zebrafish/`)

| | |
|---|---|
| Printed | Several copies of the flying zebrafish, from `out/flying-zebrafish.stl` / `out/flying-zebrafish.3mf`, on the hackathon's Formlabs printers. Reported by the project lead (Joel Dietz), who has the printed copies, 2026-11-01. The repository holds no photograph, print log or `.form` file for these prints yet; add one to `assets/` and this row will cite it |
| The design | A six-agent swarm built it to a shared spec written for Form 3/3+/4 (`SPEC.md`: 0.6 mm minimum feature, 1.0–2.0 mm fin tips, 120 × 120 × 60 mm build envelope, STL and 3MF for PreForm import): an 80 mm standard-length zebrafish body with flying-fish changes (flat belly, high pectoral insertion, longer lower tail lobe), Exocoetidae-style pectoral (56 mm) and pelvic (32 mm) wings, and a display stand (`printpack/stand.stl`). `out/assembly.json` records the mesh check: watertight, 380,590 faces, 101.6 × 120.0 × 33.9 mm, no shells dropped. PreForm 3.64 was used for import |
| What it does not show | The animal is a design, not a species. Its glide is untested, and nothing about the print has been measured against the mesh |

### A plate of xenobot bodies (`fabrication/xenobots/`)

| | |
|---|---|
| Printed | The xenobot print job, sent from PreForm on 2026-11-01 at 13:21 EST (job `f022ffb3-b180-4248-b3bc-717ed7b08970`) to a Form Studio 1 (alias RaggedRaccoon) in Alpha Fast V1 at 0.150 mm layers, 452 layers, by tsuido0 and the agent that assembled the flying zebrafish. Printer, resin, layer count and upload come from the operator's local PreForm log; that log does not name the files in a job, so the identification of this job as the xenobot plate is the project lead's (Joel Dietz). The repository holds no photograph, print log or `.form` file for it yet; add a photograph to `assets/` and this row will cite it |
| The design | Twelve voxel bodies on one plate (`out/plate_smooth.stl`, 106.5 × 78.0 × 16.7 mm; a blocky variant is `out/plate_blocky.stl`) at 4 mm per voxel. Ten are the champions evolved in claim test `levin-2020-xenobots-06` (the repo's stand-in for the Kriegman, Blackiston, Levin & Bongard 2020 pipeline, [10.1073/pnas.1910837117](https://doi.org/10.1073/pnas.1910837117)); two are new designs evolved with the same simulator, one in "water" and one on "land". `out/manifest.json` records each body's source file and sha256, seed, simulator fitness, genome and watertight check. Thin necks between diagonal voxels measure 1.5 × 1.2 mm at this pitch, above the roughly 0.6 mm Formlabs minimum (`fabrication/xenobots/README.md`) |
| What it does not show | These are static resin casts of simulated designs, scaled up from under 1 mm to about 20 mm. They do not move, and the simulator fitness values have never been compared with living xenobots |

## Designed to Formlabs specifications, print-ready, not yet printed

### The winged zebrafish kit (`anatomy-model/print/`)

71 STL files generated from the project's own parametric meshes, nothing modelled by hand: a 1:1
(38.8 mm) ten-part starter kit, a 120 mm 56-part containment-hierarchy kit (organ systems, organs,
tissues, keyed press-fit pegs), a one-piece 120 mm glider, a 1:1 glider with a ballast bore, and a fit
coupon. The 1:1 files are designed for **Formlabs SLA in Tough 2000**: 0.50 mm minimum wall (Formlabs
holds about 0.4 mm supported), 1.40 mm D-keyed pegs, 0.10 mm radial clearance to be confirmed with the
coupon, with the reasoning for each value in `anatomy-model/print/README.md`. Every part is verified
in Blender (watertight, consistent winding, volume cross-checked two ways, wall thickness measured),
and the 12 parts that fail are listed in `manifest.json` rather than dropped. The README flags the
one resin-printing hazard (a sealed cavity in the 120 mm glider needs a drain hole). Flight is
untested; the animal is a design, not a species. Viewer at `/print/` on the dashboard.

### A pre-registered physical test of a Lean-proved law (`test-data/claim-tests/plant-hygromorph-mechanics/hygromorph-bilayer-curvature/printed-bilayer-01/`)

A humidity-driven bilayer strip to be printed on a Formlabs resin printer, whose curvature and
response time are predicted *before* it is built from the machine-checked statements
`hygromorph-bilayer-curvature` and `hygromorph-response-time` (Lean module
`ThompsonLaws.Hygromorphs`). The design sweep (486 geometries against four constraints) picked
3 × 30 mm strips at 0.6, 1.2 and 2.4 mm; the specimen plan includes zero-mismatch and flipped-layer
controls. `result.json` holds the pass and fail criteria with status `preregistered`. The README names
the real risk as fabrication (a Formlabs printer builds one resin at a time; laminate, mid-print swap
or cast are the routes) and states that the swarm can design and predict but an operator has to
print, cure, measure and photograph. Not printed.

## PreForm API

The scripted path (PreForm Insider build, `formlabs_sdk`, local PreForm Server at port 44388,
`print_scene(..., print_now=False)`) is written up from Formlabs' public documentation on issue #58,
with the material limits for Flexible 50A that matter for a thin membrane and hollow spar. It was
not exercised: the prints that happened went through the PreForm GUI. The pairing proposed in #3
(screen with NVIDIA ALCHEMI, print with the PreForm API, publish both as linked nanopubs) was not run.

## Verification

The dragonfly prints are attested by the issue #58 comments and the photograph in `assets/`; the
flying-zebrafish prints by the project lead's report only; the xenobot job by the project lead's report
plus the upload entries in the operator's local PreForm log (not copied into the repo). No print log or `.form` file for
any of them is in the repository. The kit's geometry checks are in
`anatomy-model/print/manifest.json`; the flying-zebrafish check is `fabrication/flying-zebrafish/out/assembly.json`;
the xenobot checks are `fabrication/xenobots/out/manifest.json`.
Nothing was re-run for this document.
