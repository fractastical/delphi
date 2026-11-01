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
- **The O2 uptake limit is not what limits oxygen in this model.** In the stored baseline (`flux_table_pfba_o2_20.csv`), cytosolic O2 is produced at +1000 by `MAR04071` (`H2O2 + pyridoxal <=> O2 + pyridoxine`, a pyridoxine oxidase running in reverse), next to the pyridoxal uptake (-1000) and pyridoxine secretion (+1000) exchanges, which are uncapped. About 762 of that O2 goes to the mitochondria and complex IV runs at 261 against an O2 uptake of 20. A two-condition diagnostic (`o2_source_diagnostic.json`) confirms it: at O2 uptake limit 0, growth is 0.265 with `MAR04071` free and 3e-16 with it blocked; at limit 20, 0.291 free and 0.097 blocked. The sweep in v3 therefore says nothing about oxygen dependence. An earlier version of this note put the weak slope down to uncapped fuels alone; the internal O2 source is the measured cause of the O2 flatness, and the uncapped fuels are a second, separate looseness.
- Amino acids, fatty acids and vitamins are uptake-uncapped (-1000). The baseline takes up arachidonate at -250, secretes CO2 at +616, and has TCA reactions at ~420 against a glucose uptake of 10. Capping them needs data this slice does not have; that is why no new sweep was run.
- Plain FBA is degenerate; parsimonious FBA (`pfba_summary.json`) still shows these bound-pinned exchanges.
- Blocking `MAR04071` is a diagnostic of the model's structure, not a proposed biology: it is not known whether a fish has any such route, and the blocked growth numbers (0.097 at O2 20) are not a calibrated oxygen dependence.
- Cross-scale ports (not wired): lifecycle oxygen demand -> `MAR09048` lower bound; ATP demand -> `MAR03964` lower bound. Both need a documented mapping from whole-fish units to mmol/gDW/h, and the first is moot until the internal O2 source is dealt with.

## Diagrams and animation (`artifacts/metabolism/basic-nutrients-v3/`)
`energy_flow_network.png`: 14 reactions from the stored parsimonious flux table, schematic arrows, red where a flux sits at the ±1000 bound. `o2_atp_sweep_diagram.png`: the O2 sweep, the ATP-maintenance tradeoff and the diagnostic. `o2_sweep.mp4` (+ `o2_sweep_poster.png`): one frame group per stored sweep point (8 frames each, no interpolation), then the diagnostic. All carry the label "ASSUMED medium, UPTAKE-UNCAPPED, no time, not fin- or tissue-specific". `render_manifest.json` pins inputs, outputs, frame counts and the numbers shown. The animation steps through the stored sweep only: the network is drawn at one condition (O2 limit 20) because flux tables at the other conditions were not stored and re-solving them was held until nutrient bounds have evidence.

Rebuild: fetch the pinned XML, then `python engineering/metabolism/run.py MODEL.xml OUTDIR` (needs cobra 0.32.1), plus `pfba.py`, `egc.py`, `diagnose.py`, `o2_source.py`, `plot.py`, `render.py` (needs matplotlib and ffmpeg), then `manifest.py`.
