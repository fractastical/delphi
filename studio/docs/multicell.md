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

## Full horizon (t=2.0), remote, recovered 2026-10-31 15:30 PDT
Run by infra as job `aijob-e00q8z2et1q0zf5qaq` (4 vCPU, 3 arms x 1 thread, 3000 s cap each) from the frozen packet
`0d79314` (packet sha256 `994eb831...34f4f7`; receipt `packet_sha256`, `binary_sha256`, `source_commit` match the pins above).
All three arms exit 0 at t=2.0; each returned `model.xml` is byte-identical to the packet XML (checked here with `cmp`). **No gnuplot,
so no spatial frames and no full-horizon movie;** the movies above remain the partial (t<=0.46) ones. An earlier remote attempt
failed in the output wrapper after the sims finished; infra reports it and its repair, and I have not seen that wrapper.
Analysis here read only the returned `logger.csv` files (raw CSV kept at infra's path, not copied into git; sha256 in
`artifacts/multicell/full/full_summary.json`), under a 1 CPU / TasksMax 128 / MemoryMax 4G / MemorySwapMax 0 scope. No simulation was rerun.

| arm | rows | cells at t=0.5 / 1.0 / 1.5 / 2.0 | distinct division-event times | final total volume |
|---|---|---|---|---|
| baseline (feedback on, seed 3445) | 96,802 | 4 / 32 / 199 / 256 | 96 | 25,111 |
| feedback-off (seed 3445) | 23,519 | 4 / 8 / 32 / 128 | 7 | 25,052 |
| seed repeat (feedback on, seed 7) | 98,571 | 4 / 32 / 199 / 263 | 99 | 25,126 |

Reading, for this one generic ODE/CPM/PDE example: with the cytokine term, cells divide faster and lose synchrony (baseline reaches
256 cells, a power of two by coincidence only; its division events spread over 96 distinct times after ~0.57). Without it, division
stays synchronised in clean doublings (1 to 128, 7 events, period ~0.3). Total volume stays ~25,000 in every arm, as the volume
constraint implies. The seed repeat matches the baseline through t=1.5 (199 cells) and differs by 7 cells at t=2.0 (263 vs 256): the
seed does matter once divisions desynchronise. **This corrects my earlier statement** that the seed repeat was identical: that held
only for t<=0.46. Two seeds are still not a statistical replicate, and no time-step or lattice refinement (numerical convergence)
was run. Also corrected: the "cannot fit 600 s locally" estimate came from runs rendering frames while three arms shared a loaded host;
the remote frame-less arms took ~50 s each by infra's report.

Still true: generic example, NOT calibrated to fish or any tissue, units are the example's own, no dimensional ports, no comparison
to data, "cells" are model cells, not a growth measurement. `engineering/multicell/analyze_full.py` produced `cell_count.png` (a real
trajectory of the logged cell counts, log scale).

### Full-horizon chart video (not a spatial movie)
`artifacts/multicell/full/full_horizon_chart.mp4` (100 frames, 12 fps, 8.3 s) plots, as t advances to 2.0, the logged cell count
(log), mean CDK1 per cell and mean `g_l` per cell for the three arms. Rendered by `engineering/multicell/render_full.py` from the
returned `logger.csv` only, with one worker under the 1 CPU scope (38 s). It draws **no cell shapes or fields**: the remote run
saved no spatial frames. It is distinct from the earlier `{baseline,nofeedback,seed2}.mp4`, which are real spatial frames but
**partial (t<=0.46)**. I looked at the last frame. Visible in the data: the feedback-off CDK1 oscillation stays regular, the
feedback-on one speeds up then damps after ~t=1.5 as the count levels off near 256; I did not investigate why (crowding under the
volume/division condition is a guess, untested). The feedback-off `g_l` curve is still simulated and logged but is multiplied by 0
in the CDK1 equation, so it does not act on the cell cycle. Mean values are plain averages over cells at each logged time.
