# Fish scale layer (SIMULATED)

One physically grounded layer: **Erk trigger waves that drive osteoblast growth in one regenerating zebrafish
scale.** Code: `engineering/scales/`. Outputs: `artifacts/scales/erk-wave/`.

```
python -m engineering.scales.run          # standard run + controls + video + receipt (~2 min, 1 core)
pytest --noconftest tests/test_scales.py  # 7 tests, ~10 s
```

Needs the `geometry` extra plus ffmpeg (the video encoders are reused from `engineering/geometry/turntable.py`).

## Model
Hayden, Poss, De Simone, Di Talia 2021, *Biophys J* 120:4287 (doi 10.1016/j.bpj.2021.05.004), read in full:

    dE/dt = a1 A^2/(b^2 + A^2) (1 - E) - E (g1 I + ge)
    dA/dt = a2 [source] + a3 E - g2 A + D lap(A)
    dI/dt = g3 (a4 E - I)

E is the active fraction of Erk, A a diffusible activator (an Fgf candidate), I an inhibitor. Units are µm and
hours. Every parameter comes from their Table 1, and the numbers match the authors' public MATLAB code (read, not
copied; it is GPL-3.0). The scale is a 520 µm disc on a 5 µm grid with a 0.01 h step. The simulation starts with
every species at 0, and the domain edge absorbs activator.

**Growth** (De Simone et al. 2021, *Nature* 590:129, doi 10.1038/s41586-020-03085-8):
- **Measured.** Extended Data Fig. 7b fits a **linear** slope to normalised cell area after the Erk peak:
  d(a/a_peak)/dt = **0.006 ± 0.002 h⁻¹** (n = 89 cells, 3 scales).
- **Assumed: the coupling form.** The code integrates **d ln a/dt = 0.006 h⁻¹**, which is **exponential** growth
  that uses the measured linear slope as a log-rate. A cell grows this way for **24 h (assumed)** after each of its
  own Erk peaks, and the growth compounds over successive waves.
- Over one window the two forms give ×1.155 (exponential) against ×1.144 (linear). The area numbers below are
  those of the assumed exponential form, and they have not been tuned.

The waves are computed in reference (material) coordinates, and growth does not feed back on them.

`engineering/scales/sources.json` marks every parameter `fitted-in-source`, `from-source`, `measured`,
`assumed` or `unknown`. The measured linear slope (`growth.measured_linear_slope_per_h`) and the assumed
log-rate the code uses (`growth.rate_after_peak_per_h`) are two separate rows.

## Results (`artifacts/scales/erk-wave/receipt.json`)

| quantity | simulated | measured (De Simone 2021) | in band? |
|---|---|---|---|
| wave speed | 11.4 µm/h | "order of 10 µm/h" | yes |
| first wave source → rim | 56 h | "about 2 days" | yes |
| front width (FWHM) | 65 µm | 50–100 µm | yes |
| Erk fall (peak → 10%) | 7.3 h | ~5 h | yes |
| source period | 28 h | ~1 wave per day at onset | yes |
| **Erk rise (10 → 90%)** | **1.2 h** | **~3 h** | **no** |

The bands were set from the papers' own wording before the run, and they stay as set. The rise-time miss is a
finding, not a failure of the code. One possible cause is the reporter: the measured value comes from an Erk
KTR translocation reporter, which this model does not include. That cause is untested.

Over 120 h the scale's area grows ×1.55 (effective radius 520 → 647 µm). That figure comes from the
**assumed** exponential coupling and is not a measured growth curve.

## Controls (they set the exit code)
- **no source:** E stays 0 everywhere and the area does not change. Pass.
- **positive-feedback sign mutant** (α3 → −α3): no cell is reached and no wave arrives at the rim. Pass.
- **D/4:** the speed ratio is 0.49, against the 0.5 predicted by trigger-wave scaling v ∝ √D. Pass.
- **time step halved:** speed changes by 0.05% and the period by 0%. Pass.
- **synchronous activation** (reported, not gated): De Simone 2021 *measured* that daily tissue-wide Erk
  activation impairs growth. This model grows *more* (×2.05 against ×1.55). The growth law cannot reproduce
  that measurement, so whatever makes synchrony harmful is missing from this layer.

## Not claimed
- That flying-fish scales follow these kinetics. Every number is from zebrafish, and from regeneration rather
  than first-time development.
- Absolute concentrations (E_T is unknown).
- Mineralisation, scale shape beyond a disc, or overlap between scales.
- Anything a microscope saw. Every picture is a rendering of simulated state.
- That a living or bioprinted fish is feasible. The resin props in `artifacts/print` are display objects and
  are unrelated to this layer.

## Next
Place scales on a fish body surface (S2). The planned source is Cooper et al. 2018 (shark denticles, Turing-like
patterning), read so far only at abstract level, and it will be labelled an abstract pattern because its
transfer to teleost scales is unknown.
