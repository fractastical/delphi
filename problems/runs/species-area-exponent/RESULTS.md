# Results: species-area-exponent

Pre-registration: `PREREG.md`, sha256 `6573bfe3…6c2a6c6a2` (`PREREG.sha256`, 2026-11-01T09:47:06Z), written before any
richness or area value was seen. Deviations: `DEVIATIONS.md`. Re-run: `run_all.sh`. All numbers below are in
`derived/*.json`; `result.json` (claim-test schema) is written to `test-data/claim-tests/darwin-origin/darwin1859-ch12-04/problem-sar-gift/`.

Short version: a sampling-only null does not pin z. It gives anything from about 0 to 1 depending on how much of the
regional pool the islands cover, how large the pool is and the SAD, and it reaches 0.15 to 0.35 in only 23% of plausible
conditions. On 1,124 real GIFT islands the pooled exponent is 0.307 (95% CI 0.295 to 0.319), but exponents differ between
regions (0.14 to 0.49), so universality fails; the curvature is real in the pooled data but not consistent across regions;
and the METE-type surrogate fits much worse than the power law. Preston's canonical lognormal does give z = 0.264.

## Part 1. Sampling-only null (claude-opus-5-5 n=2 and the sampling half of grok-4-7 n=2)

Grid: 57 pools (45 lognormal, 12 logseries), 90 island configurations each, 5,130 cells,
3,425 feasible, 1,705 "plausible" under the pre-registered definition; stochastic replicates (30 per cell, 535 plausible
cells) for 30-island sets. The logseries closed form E[S] = alpha ln(1 + aJ/alpha) matched the numerical pmf sum to 1e-13.

| Pre-registered quantity | Value |
|---|---|
| plausible cells with analytic z in [0.15, 0.35] (H1A needs >= 50%) | 22.6% |
| SD of z across plausible cells (H1B needs < 0.05; "no discriminating power" if >= 0.10) | 0.284 |
| 5%, 25%, 50%, 75%, 95% quantiles of z | 0.017, 0.175, 0.402, 0.656, 0.914 |
| stochastic Poisson-GLM z in [0.15, 0.35] | 26.2% (median 0.36; the count-aware fit is on average 0.066 below the OLS-on-S>=1 value because zeros are kept) |
| analytic concavity q < -0.01 in plausible cells (H1C needs >= 70%) | 94% |
| logseries-placement form beats the power law by AIC > 10, stochastic cells (needs >= 70%) | 64% (power with curvature: 71%; Gleason: 31%) |
| Preston canonical isolate z (H1D needs 0.262 +/- 0.02) | 0.264 (local 0.259 to 0.274 over S = 100 to 1e5; stochastic 0.272) |

Scale and SAD dependence of the null z (median over plausible cells):

| Island area at most this fraction of the pool | median z | | Island area span (decades) | median z | | Pool individuals J | median z |
|---|---|---|---|---|---|---|---|
| 1e-5 | 0.75 | | 2 | 0.26 | | 1e7 | 0.58 |
| 1e-4 | 0.59 | | 3 | 0.38 | | 1e9 | 0.24 |
| 1e-3 | 0.42 | | 4 | 0.48 | | | |
| 1e-2 | 0.24 | | 5 | 0.50 | | | |
| 1e-1 | 0.13 | | | | | | |

By SAD: lognormal sigma 1.5, 2.0, 2.45, 3.0 give 0.38, 0.40, 0.42, 0.43; logseries alpha 20, 100, 500 give 0.25, 0.38, 0.52.

What this says. Under passive sampling the local exponent falls from near 1 (islands that hold few individuals) to near 0 (islands that
hold most of the pool), so a fitted z is set by where the island area range sits on that curve and by the SAD. z = 0.25 appears
when the largest island is about 1% of the pool, when J = 1e9, or for a logseries with alpha around 20; it is not a
property of the sampling process. The sampling-only null is therefore a family of curves, not a prediction.

Preston. For the canonical constraint (individuals-curve mode at the most abundant species, rarest species at one
individual: sigma = Phi^-1(1 - 1/2S), mu = sigma^2), a larger isolate has N = S exp(1.5 sigma^2), and z = d ln S / d ln N is
0.264 by global fit over S = 100 to 1e5 (0.274 at S = 114, 0.260 at S = 31,000). So the "z = 0.262 for canonical isolates" figure
is reproduced, to within 0.002 of memory; note that it is an isolate result (every island is a complete community with the same
canonical shape), not a sampling result. The a = 0.2 canonical community (sigma = 2.45 natural-log units, S = 70 species at
gamma = 1) sampled by random placement has a local exponent that falls from 0.86 at area fraction 3e-6 to 0.02 at 0.56 and a
log-log fit over six decades gives 0.33. Passive-sample z and isolate z are different quantities.

Verdicts under the pre-registered rules.

- claude-opus-5-5 n=2 (sampling-only null): **failed its own criterion**. H1A and H1B are false (22.6% in range; SD 0.28 against
  the 0.10 limit), which is the proposal's stated failure signature: a plausible SAD and scale can be found to fit any observed z, so the
  null does not discriminate. What it does establish is that z in 0.15 to 0.35 needs no ecological mechanism *for some choices*
  of pool size and area range, and that the curve is concave in log-log (H1C concavity part true; the AIC half falls short at 64%
  against 70%, so H1C is not met). The comparison with the Triantis et al. z values was not run (`DEVIATIONS.md` 5).
- grok-4-7 n=2 (logseries null): see Part 2.

## Part 2. Real data: GIFT islands (grok-4-7 n=1, grok-4-7 n=2, and the claim-level test)

Data. GIFT public API (`https://gift.uni-goettingen.de/api/`, no key). 1,288 eligible island lists on 1,175 entities,
1,124 entities after one list each with richness >= 1 and area > 0; area 1.8e-5 to 740,635 km2 (10.6 decades), native
vascular richness 1 to 9,884. Mainland: 232 entities. 1,533 list files, 333 MB, URL, time, size and SHA-256 for every one in
`derived/gift_manifest.csv.gz`; raw files are in `data/` (git-ignored). The island table is `derived/gift_richness.csv`.

Pooled island SAR (NB2, all 1,124 islands): power law z = 0.307 (bootstrap 95% CI 0.295 to 0.319, width 0.024; OLS on
log10 gives 0.307, r2 = 0.62; islands >= 1 km2 only: 0.256).

| Model | AIC minus power law AIC | held-out ELPD minus power | mean abs residual (ln S) |
|---|---|---|---|
| power (pooled z 0.307) | 0 | 0 | 0.938 |
| power with log-log curvature | -17.8 | +14.9 | 0.925 |
| Lomolino-type sigmoid | -8.0 | +4.3 | 0.930 |
| Gleason logarithmic | +835 | -575 | 1.388 |
| logseries-placement (METE-type surrogate) | +409 | -143 | 1.110 |

The curvature is negative (q = -0.0047, 95% CI -0.0068 to -0.0027): the local exponent is 0.42 at the smallest
island, 0.31 at the median and 0.18 at the largest.

Regions (16 qualifying 60 x 30 degree cells, `derived/part2_groups.csv`): group z runs from 0.137 (cell lon -180 to -120, lat 30 to 60, n = 10) to 0.487
(cell lon -60 to 0, lat 0 to 30, n = 20; both at the small end of the sample sizes, wide intervals); 9 of 16 intervals overlap the pooled interval; 46 of
120 pairs of cells have disjoint 95% intervals; DerSimonian-Laird tau = 0.054 (threshold 0.05). The sign of the
curvature agrees with the pooled sign in 8 of 16 cells (threshold 70%).

Rules.

- Universal power law: U1 (pooled z in 0.15 to 0.35) true; U2 (CI width < 0.1) true; U3 (all groups overlap) false; U4 (tau < 0.05) false;
  U5 (no alternative beats the power law by AIC > 10 and ELPD > 10) false (the curved power law does, by 17.8 and 14.9).
  **Universality is refuted** under the pre-registered falsifier (46 disjoint pairs).
- Scale-dependent form: AIC, ELPD and the pooled CI of q all pass, but only half the cells share the curvature sign
  (needs 70%), so by the pre-registered rule it is **not supported**. Pooled curvature that cells do not share is what a
  mixture of regions with different z would produce.
- METE-type (grok-4-7 n=1): the logseries-placement surrogate loses to the power law on both AIC (+409) and residual
  (1.11 against 0.94): **no win**, and not even a split. Overall classification under the rule: **"neither"** (power law adequate
  on average, not universal, and no single non-power form supported).
- Robustness (not deciding): isolation classes, exploratory: z = 0.337 (< 100 km, n = 571), 0.225 (100 to 1,000 km, n = 242),
  0.253 (> 1,000 km, n = 311), CIs 0.321 to 0.353, 0.191 to 0.260, 0.228 to 0.278.

grok-4-7 n=2, logseries null calibrated on Borneo (S = 7,534; 1,123 test islands; empirical pooled z = 0.307).
With individuals per km2 as a free nuisance parameter, the 95% null interval for z is 0.80 (rho = 10), 0.71 (1e2), 0.56 (1e3),
0.38 (1e4), 0.24 (1e5), 0.16 (1e6), 0.115 (1e7), 0.087 (1e8), each only about 0.02 wide. The empirical z is inside none of the eight.
Pre-registered outcome: **failed** (it needs at least one density). Exploratory fine sweep (not pre-registered, `part2_grok_fine.py`): z_empirical
matches the null at about 2.9e4 individuals per km2, and the null's exponent spans 0.07 to 0.81 across the grid, so a density can be chosen to
reproduce any z; at 1e6 to 1e7 individuals per km2 the null gives 0.16 to 0.11, well below 0.307. I cannot say which density is right for
plants (no abundance data), so I do not claim that sampling is ruled out; the null is simply not constraining.

Claim-level test, darwin1859-ch12-04 (islands versus equal-area mainland, GIFT, independent of the existing WCVP test):
mainland power law z = 0.200 (SE 0.020, 232 units, 2.5 to 4.3e6 km2). For the 440 islands >= 500 km from the mainland the median
observed/predicted richness is 0.22 (86% to 89% below the prediction; one-sided Wilcoxon p = 5.5e-67); restricted to islands inside the
mainland area range (243) 0.28, 86% below. Rule met (<= 0.5, >= 70%, p < 0.01): **supports**, confidence 0.7 (no latitude or climate
control; GIFT mainland units differ in checklist effort from island lists; the proxy for "oceanic" is distance).

## What each approach did

| Approach | Run | Outcome by its own pre-registered criteria |
|---|---|---|
| claude-opus-5-5 n=2, sampling-only null | yes (grid; Triantis comparison replaced by GIFT) | fail: null z not pinned (SD 0.28), 23% in range |
| grok-4-7 n=2, logseries null | yes, adapted (density grid, richness only) | fail on the pre-registered grid; fine sweep shows no constraining power |
| grok-4-7 n=1, power law vs METE on GIFT | yes, with a METE-type surrogate, not meteR | universality refuted; METE-type no win; classification neither |
| claude-opus-5-5 n=1, n=3; gpt-5-6-sol n=1, n=2; grok-4-7 n=3 | no | not run |

## Verdict I would give the claims

- `darwin1859-ch12-04`: supports on a second, independent dataset (median ratio 0.22 on far-offshore GIFT islands).
- The problem question: the power-law form is a good first description of island richness (pooled z about 0.31, 0.26 when islands under 1 km2
  are removed, consistent with the usual 0.2 to 0.35 range) but there is no universal exponent: regional z ranges from 0.14 to 0.49 with
  disjoint intervals, and z of 0.25 is not a property of sampling alone (null z spans 0 to 1 with scale and SAD). The pooled data prefer a
  concave curve over a straight log-log line, but the evidence does not agree across regions, and the logseries-placement surrogate for METE
  is clearly worse than the power law. This neither confirms a near-universal 0.25 nor shows that METE explains the scale dependence.
  `darwin1859-ch12-05` and `darwin1859-ch11-02` were not tested here.

## Limits that matter

- GIFT checklists differ in completeness and effort; richness is not coverage-standardised (that was the gpt-5-6-sol and claude-opus-5-5 n=1 idea).
- Cells are not archipelagos; heterogeneity between cells mixes biogeography with sampling.
- The METE-type form is a surrogate. A real METE test needs abundance totals per island, which GIFT does not hold.
- One taxon (vascular plants), one database, one extraction date.
- "Plausible" in Part 1 was fixed before the grid was run, but different bounds would change the 23%; the conclusion that z moves
  with scale does not depend on them (see the by-fraction table).
