# Zebrafish-GEM flux-balance slice

Steady-state flux-balance analysis (a linear programme) of the generic *Danio rerio* genome-scale model Zebrafish-GEM (Wang 2021 PNAS, CC-BY-4.0 as stated by the repo), commit `846f0b7b3…`, SBML `model/Zebrafish-GEM.xml` (sha256 pinned in `artifacts/metabolism/manifest.json`, file not stored here). This is **not** time-dynamic metabolism, and the model is **not** fin-, tissue- or stage-specific.

## Measured from the file (not copied from the README)
12,833 reactions, 8,435 metabolites, 2,709 genes, 9 compartments, 1,658 exchange reactions. Objective `MAR00021` (biomass). The SBML defines **no medium**: every exchange is open at ±1000 and flux units are not declared. A proper ATP hydrolysis reaction exists (`MAR03964`, ATP + H2O → ADP + H+ + Pi), so an ATP-maintenance sweep is a lower bound on it.

## What was run (all under TasksMax 128, MemoryMax 4G, MemorySwapMax 0)
| dir | medium | result |
|---|---|---|
| `artifacts/metabolism/` (v1) | the file's default, all exchanges open | biomass 4.26: **not a medium**. Minimum-uptake derivation on it takes UTP at -337 and ATP: degenerate. Kept as a record. |
| `basic-nutrients-v2` | allowlist of basic nutrients, vitamin E as alpha-tocopherol only | biomass 0: the biomass pool "cofactors and vitamins" needs vitamin E catabolites from gamma-tocopherol |
| `basic-nutrients-v3` | same plus gamma-tocopherol | biomass 0.265 (O2 0) → 0.291 (O2 20) → 0.329 (O2 50), glucose capped at 10 |

Controls (v1/v3 `metabolism_results.json`): all uptake closed → 0 growth; glucose alone → 0; max |S·v| ≤ 1e-10; bounds respected; the objective flux equals the biomass flux; no energy-generating cycle with every uptake closed (ATP hydrolysis and ATP synthase max at 0).

## Assumed, not published
Medium (allowlist, 58 names, all found as exchanges), glucose cap 10, flux unit mmol/gDW/h. No fish feeding or tissue oxygen data was used. Absolute growth values mean nothing physiologically.

## Limits you must keep when reading the sweeps
- Amino acids, fatty acids and vitamins are uptake-uncapped (-1000). The baseline solution takes up arachidonate at -250, secretes CO2 at +616 and runs pyridoxal -1000 / pyridoxine +1000 at the bounds. Energy is effectively unlimited, so the oxygen slope (0.265 → 0.329) and the ATP-maintenance cost (0.291 → 0.258 for 0 → 100) are weak and **not** a measurement of oxygen dependence. Capping the other uptakes needs data this slice does not have.
- Plain FBA is degenerate (many equivalent solutions); parsimonious FBA (`pfba_summary.json`) still shows these bound-pinned exchanges.
- No animation or graph of energy flow was built; `selected_energy_flow.json` lists a few named reactions only.
- Cross-scale ports (not wired): lifecycle oxygen demand → `MAR09048` lower bound; ATP demand → `MAR03964` lower bound. Both need a documented mapping from whole-fish units to mmol/gDW/h.

Rebuild: fetch the pinned XML, then `python engineering/metabolism/run.py MODEL.xml OUTDIR` (needs cobra 0.32.1), plus `pfba.py`, `egc.py`, `diagnose.py`, `plot.py`.
