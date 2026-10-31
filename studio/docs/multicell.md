# Multicell growth: Morpheus cell-cycle -> CPM -> cytokine PDE -> feedback

Slice written 2026-10-31 (Seattle, PDT). Source: Morpheus official example `Examples/Multiscale/MultiscaleModel.xml`
("Example-CellCycle-MultiScale"). **Generic and NOT calibrated to any fish, cell type or real tissue.** Nothing here is
fin growth, and nothing is a measurement.

## Source and pins
- Upstream `https://gitlab.com/morpheus.lab/morpheus.git`, tag `v2.3.9` = commit `29a26b00838736c4180f22fea075688f1d51e619`
  (XML read with `git show`, sha256 in each arm's `manifest.json`). Licence: BSD 3-clause, TU Dresden (`LICENSE.md`, read).
- Binary: upstream release asset "Static simulator binary" v2.3.9, sha256 `3d9a6e5a4cb86824b745500df1474596d39cce5deed24f767c0841df0f94d5ad`.
  Not built from source. Gnuplot 6.0.5 from conda-forge, isolated prefix, for frames only.
- Upstream states the ODE is from Ferrell, Tsai, Yang (2011) Cell 144:874-885, doi:10.1016/j.cell.2011.03.006 (cited from the XML
  description; the paper was not read).

## Coupling (equations as written in the XML)
- Cell ODE (per cell, Runge-Kutta, time-scaling 15): `dCDK1 = a1 + g_l - b1*CDK1*APC^n/(K^n+APC^n)`,
  `dPlk1 = a2*(1-Plk1)*CDK1^n/(K^n+CDK1^n) - b2*Plk1`, `dAPC = a3*(1-APC)*Plk1^n/(K^n+Plk1^n) - b3*APC`;
  n=8, K=0.5, a1=0.1, a2=a3=3, b1=3, b2=b3=1.
- ODE -> CPM: `CellDivision` when `CDK1 > 0.5 and c == 0 and cell.volume > 100`, minor-axis plane; target volume halves.
- Cell -> PDE: global field `g`, `dg/dt = APC - 0.05 g`, diffusion rate 100 (the APC term is read at each lattice site's cell).
- PDE -> ODE: `CellReporter` averages `g` over the cell into `g_l`, which enters the CDK1 equation (the feedback).
- CPM: hexagonal 250x250 periodic lattice, MCS 1e-4, temperature 2, contact cell-cell -12, VolumeConstraint target Vt strength 1.
- Units are the example's own; no dimensional mapping to seconds or micrometres was attempted.

## Edits to the upstream XML (each a recorded exact-once string replacement, `run_morpheus.py`)
`version-2` (see below), `surface-mode` (`mode="aspherity"`, the schema default), `log-states` (logger of CDK1, APC, g_l, d,
volume instead of `dist`), `frame-step` 0.1 -> 0.02, `stop-time` 2 -> 0.6, `seed`; feedback-off arm: `feedback-off`
(`g_l` multiplied by 0 inside the CDK1 equation only; `g` is still simulated and reported).
**Why version-2:** the v2.3.9 binary refused the v1 file ("Unable to upgrade MorpheusML model from 1 to 2"). The only attribute
it then required was `SurfaceConstraint/@mode`; I did not find a v1->v2 rule set and applied the minimal fix by hand, so the
model is not byte-for-byte the shipped one. The XML carries upstream's own note that cell property `dist` is wrong; it is not used.

## Runs (executed, 1 CPU quota, TasksMax 128, MemoryMax 4G, MemorySwapMax 0, RuntimeMaxSec 600; three arms concurrently)
**All three arms were stopped by the 600 s cap (SIGTERM, exit -15) before `StopTime=0.6`.** Common reached horizon t=0.456
(example time units). The full 2.0 horizon was not run: an unrecorded earlier attempt reached t~0.35 at ~5 min, so it cannot fit 600 s locally.
The threads env (`OMP_NUM_THREADS=1`) was added after these arms started and was **not** applied to them. Root measured ~9 threads each.

| arm | cells at t=0.456 | division-event times | CDK1 at t=0.456 |
|---|---|---|---|
| baseline (feedback on, seed 3445) | 4 | 0.166, 0.374 | ~0.186 (daughters) |
| feedback-off (seed 3445) | 2 | 0.166 | 0.488, just under the 0.5 trigger |
| seed repeat (feedback on, seed 7) | 4 | 0.166, 0.374 | - |

Reading, limited to this window: with the cytokine term in the CDK1 equation the second division round came earlier (0.374) than
without it, where the cells had not yet divided by 0.456. That is a timing difference within one short window, one seed each; whether
feedback-off divides later or never was not run to the end. Seed 3445 vs 7 gave the same division-event times to the logged
resolution: the cycle is ODE-timed and the seed only perturbs CPM shape, so this is a **noise check on the CPM, not an independent
replicate**. It does not show numerical convergence (no time-step or lattice refinement was run). Total volume stays ~25000 (4 x 6250).

Movie: `artifacts/multicell/{baseline,nofeedback,seed2}.mp4`, 22 frames each, produced by Morpheus' Gnuplotter (cells coloured by
APC, field `g` as colour map with isolines), concatenated by ffmpeg at 4 fps. Real simulation frames only; the last, possibly
truncated frame is dropped. Gnuplot printed a `set colorbox` warning at each frame (conda gnuplot 6.0.5 vs the generated script);
the frames render. Hashes in `mp4.sha256`.

## Not done
- No fish-specific example was catalogued. No calibration, no comparison to data, no dimensional ports.
- No SBML/libroadrunner fallback (Morpheus ran, so it was not triggered; `libroadrunner` import failed here for a missing libpython).
- No full-horizon run, no refinement study, no independent seeds beyond one.
- Provider spend: none by me for this slice (no LLM fork); actual account spend is not measured.

## Reproduce
`python3 engineering/multicell/run_morpheus.py --clone <morpheus clone> --binary <v2.3.9 binary> --gnuplot <gnuplot> --out <dir> --arm baseline`
(`--feedback-off`, `--seed N`), then `python3 engineering/multicell/analyze.py --arms <dir> --out artifacts/multicell`.
Tests: `python3 -m pytest engineering/multicell/tests` (2 tests: division-event parsing; edit refusal). They do not run Morpheus.
