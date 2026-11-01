# Printed hygromorph bilayer (printed-bilayer-01)

A humidity- or water-driven bilayer strip, printed on a Formlabs resin printer, whose curvature
and response time are predicted before it is built from the machine-checked statements
`hygromorph-bilayer-curvature` and `hygromorph-response-time` (Lean:
`ThompsonLaws.Hygromorphs`, see `claim-sources/thompson-growth-form/lean/reports/Hygromorphs.json`).
This is the "make a compelling biomaterial that uses the laws" build. It is also a test: the
pre-registered thresholds are in `result.json`, and the prediction is committed before any
curvature is measured.

**What it can and cannot show.** The data are physical (`data_kind: "physical"`): a fabricated
hydrogel bilayer, not an organism. A pass shows the law predicts a material we made from
independently measured inputs; it does not show pine cones obey it. That is the separate
pre-registered pine-cone test one directory up.

## What exists now

| File | What |
|---|---|
| `model.py selfcheck` | Closed-form Timoshenko coefficient against an independent force/moment/compatibility solve. Agreement is 3e-15 for mild contrast and 6e-10 at six decades of modulus contrast, which scales with the conditioning of the solve, so it is round-off. A common eigenstrain gives zero curvature. |
| `model.py design` / `design-sweep.json` | 486 candidate geometries checked against four constraints (below). Inputs are **assumptions**, listed in the file, used only to size specimens. |
| `model.py predict inputs.json` | The pre-registered prediction from **measured** inputs, with a Monte Carlo uncertainty. Not run yet: there are no measurements. |
| `result.json` | Hypothesis, pass and fail criteria, status `preregistered`. |

## Geometry constraints (from the sweep)

1. Small strain: swelling mismatch at most 0.10, because the beam theory is linear.
2. Slender: total thickness over radius of curvature at most 0.1.
3. No anticlastic curling: \(w^2/(R h) \le 1\), otherwise a wide strip curls across its width and
   the one-dimensional law no longer applies. This is the constraint that removed most
   candidates (212 of the failures), so width is the main design lever.
4. Visible: tip angle \(L\kappa\) between 0.2 rad and one full turn.

Under the placeholder inputs, strips 3 mm wide and 30 mm long pass at total thicknesses from
0.45 to 3.6 mm; 5 and 8 mm widths pass at thicker sections only. So: **3 mm wide, 30 mm long;
total thickness 0.6, 1.2 and 2.4 mm** (equal layers, \(m = 1\)), which spans a factor of 4 in
thickness and 16 in the predicted diffusive time. Re-run `design` with measured moduli and
mismatches before printing; the choice may move.

## Specimens

| Group | Strips | Purpose |
|---|---:|---|
| Resin pair A (active layer more swelling), 3 thicknesses x 5 | 15 | curvature test and \(\tau \propto h^2\) |
| Resin pair B (different mismatch), 3 thicknesses x 5 | 15 | same, at a second \(\Delta\varepsilon\) and \(n\) |
| Zero-mismatch controls (same formulation in both layers), 1.2 mm, 2 formulations x 5 | 10 | fabrication-asymmetry null: must not curve |
| Layer order flipped, pair A, 1.2 mm | 5 | curvature must reverse sign |
| Single-layer strips of each formulation | at least 5 each | independent measurement of \(E\), \(\varepsilon\), \(D\) |

## Materials (choose after screening)

The active layer must be a photocurable liquid that swells measurably and the passive layer a
stiffer or less-swelling formulation. Candidate classes, all 405 nm curable: PEGDA at different
molecular weight or dilution; gelatin methacrylate; a hydrophilic monomer such as HEMA blended
into a PEGDA base. A rigid, near-non-swelling stock resin as the passive layer is a possible
second design but gives \(n \ll 1\), where the strip behaves differently; keep it as a
sensitivity run, not the primary. Screening on single-layer strips comes first: record \(E\),
equilibrium swelling strain and uptake kinetics for each candidate, then pick the two pairs.

## The risk is fabrication, not the theory

A Formlabs printer builds one resin at a time. Routes, in order of preference:

1. **Laminate.** Print each layer flat as a thin sheet in its own resin, bond with a thin film of
   the active resin and a UV flood cure. Sheet thickness below about 0.3 mm prints poorly.
2. **Swap mid-print.** Print layer 1, wash the build plate, change the tank, continue. Needs an
   open-material setup and careful registration.
3. **Cast on a printed substrate.** Not a print, but acceptable if routes 1 and 2 fail.

Verify layer thicknesses and interface quality in cross-section after testing. Residual
stress in either layer can give an initial curvature, so the test uses the curvature change
from the reference state, and records the initial curvature of every strip.

## Protocol (order matters)

1. Screen candidate resins on single-layer strips; fix two pairs.
2. Print and cure all specimens; equilibrate at 30 % relative humidity and 23 C for 48 h
   (reference state). Photograph each strip against a scale; record initial curvature.
3. **Independent inputs:** tensile or three-point bending of single-layer strips in the
   reference and wet states (\(E_1\), \(E_2\)); free swelling strain of single-layer strips
   (\(\varepsilon_1\), \(\varepsilon_2\)); gravimetric uptake of thin slabs (\(D\)); layer
   thicknesses from calipers and cross-section. Write them to `inputs.json` with standard
   deviations.
4. `python3 model.py predict inputs.json --out prediction.json`. **Commit `prediction.json` and
   `inputs.json` before step 5.** The person measuring curvature does not see the prediction.
5. Stimulus: immerse in deionized water at 23 C (a step in boundary water content, which is
   the same diffusion problem as a humidity step). Photograph every 1 min for the first
   hour, then at lengthening intervals, to equilibrium. Fit a circle to each photograph for the
   curvature.
6. Score against the criteria in `result.json`; fill in `measured`, `datasets`, `verdict`.

## Measurements and tolerances

Curvature from circle fits to photographs of calibrated scale: the radius error should be
under 3 %; report it. Thickness to better than 20 micrometres on the thinnest layer, because
the predicted curvature scales as 1/h and the coefficient depends on \(m\). Modulus to 10 %.
Swelling strain to 0.005. If the propagated uncertainty on the prediction exceeds a factor of
1.5, the verdict is inconclusive (`underpowered`), not a pass.

## Not in scope

- Absolute response time. \(\tau \propto h^2\) is tested through the slope; the absolute value
  depends on \(D\), which is measured, and is reported but not scored.
- Twist from antisymmetric fibre angles (`hygromorph-antisymmetric-twist`). Printing
  oriented fibres is a follow-on, and would use carbon or cellulose-nanocrystal loading.
- Any claim about biocompatibility, implants or cell culture. Uncured methacrylate resins are
  skin sensitisers: nitrile gloves and a fume hood, and a certified resin and testing before
  any such claim.

## What the swarm can do and what needs an operator

The swarm can run `design`, `selfcheck` and `predict`, write the scoring script and screen the
literature for resin properties. An operator has to print, cure, measure and photograph.
