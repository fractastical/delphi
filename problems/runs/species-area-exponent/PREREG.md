# Pre-registration: species-area-exponent

Problem: `species-area-exponent` (`problems/problems.json`). Related claims: `darwin1859-ch12-04`
(primary claim for `result.json`), `darwin1859-ch12-05`, `darwin1859-ch11-02`.
Approaches run: `claude-opus-5-5` n=2 (sampling-only null), `grok-4-7` n=2 (logseries null), and
`grok-4-7` n=1 (power law against METE-type on GIFT island floras). Not run: `claude-opus-5-5` n=1 and n=3,
`gpt-5-6-sol` n=1 and n=2, `grok-4-7` n=3 (Lean).

State of knowledge when this file was written: before it, the only things inspected were the
problem entry, the approach proposals, column names of the GIFT API tables (`lists`, `geoentities`,
`taxonomy`), their row counts (3,859 lists; 3,838 geographic entities) and the counts of the categorical
metadata columns of `lists` (`type`, `subset`, `taxon_ID`, `entity_class`, `native_indicated`).
No species count, area, richness or fitted value had been looked at. Repo layout note: the working
tree has been reorganised under ``, so this run lives in `problems/runs/species-area-exponent/`.

An existing, unrelated pre-registered stub for the claude-opus-5-5 n=2 approach exists in
`test-data/claim-tests/darwin-origin/darwin1859-ch12-04/overnight-sar-null/result.json`. It is not touched
and this run is independent of it (own grid, own code, own thresholds).

Seed for every random number generator: 20261101. Software: Python 3, numpy, scipy, pandas, statsmodels.

## Part 1. Sampling-only null (no external data)

### Hypotheses

- H1A: random (passive) sampling of a regional pool with a lognormal or logseries species abundance
  distribution (SAD) gives a fitted island exponent z in [0.15, 0.35] for most plausible conditions
  (sampling alone reproduces the clustering of z around 0.25).
- H1B: the sampling-only z is nearly universal, that is, insensitive to pool size, SAD shape and island
  area range. (If it is not, z carries no information that distinguishes mechanisms.)
- H1C: sampling-only expected richness curves are not power laws (log-log curvature is non-zero) and a
  logseries-placement curve (the form used here as the METE-type non-power form) beats the power law by AIC.
- H1D (Preston): the canonical lognormal (gamma = 1) with the veil line at one individual gives an
  isolate exponent z close to 0.262.

### Model

Individuals of S0 species with abundance vector n_j (integers >= 1) form the regional pool of J
individuals. An island of area A_i takes a fraction a_i = A_i / A_pool of the pool (Coleman random
placement). Expected richness is E[S(a)] = sum_j (1 - (1 - a)^n_j). For stochastic runs, the count of
species j on island i is Binomial(n_j, a_i), independently across islands; S_i = number of species with
count >= 1.

Pools:

- Lognormal: S0 in {100, 1000, 10000}; sigma (natural-log sd) in {1.0, 1.5, 2.0, 2.45, 3.0}; J in
  {1e5, 1e7, 1e9}; abundance n_j = max(1, round(q_j)) where q_j are the lognormal quantiles at
  probabilities (j - 0.5)/S0 with log-mean mu = ln(J/S0) - sigma^2/2 (so the continuous mean gives J). Cells
  with mean abundance J/S0 < 10 are skipped. The realised J' after rounding is recorded.
- Logseries: alpha in {5, 20, 100, 500}; J in {1e5, 1e7, 1e9}; S0 = alpha ln(1 + J/alpha). Expected
  richness uses the closed form E[S(a)] = alpha ln(1 + a J/alpha), verified against the numerical sum
  over the logseries pmf for a subset. Stochastic runs (only J <= 1e7) draw S0 abundances from
  scipy.stats.logser with p = J/(J+alpha).

Islands: n_isl in {10, 30, 100}; D = log10(Amax/Amin) in {1, 2, 3, 4, 5}; Amax as a fraction of the pool
amax in {1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 0.5}. Island areas: log10 A = log10 Amax - D u with u_1 = 0, u_n = 1,
the others uniform(0, 1) (fixed by seed). Islands with E[S] < 1 are dropped; a cell with fewer than 8
islands left or a retained span below 1.5 decades is infeasible.

Analytical pass (all cells, no noise): z_OLS = OLS slope of log10 E[S] on log10 A; q = quadratic
coefficient of log10 E[S] on (log10 A, (log10 A)^2).
Stochastic pass (cells with n_isl = 30 only; 30 replicates per cell): z_OLS on islands with S >= 1,
z_Poisson from a Poisson GLM with log link on S including zeros (log S = log c + z log A); AIC (Poisson
log-likelihood, count-aware) of four forms fitted to the same data: power (2 params), Gleason logarithmic
S = c + z ln A (2), logseries-placement S = alpha ln(1 + A/A*) (2; the METE-type non-power form, a
surrogate: real METE needs abundance totals and nested cells), and power with log-log curvature (3).

Plausible cells (pre-registered subset used for the verdicts): lognormal sigma in {1.5, 2.0, 2.45, 3.0} or
logseries alpha in {20, 100, 500}; J >= 1e7; D in {2, 3, 4, 5} before dropping; amax <= 0.1; feasible
after the drop rule.

### Decision rules (Part 1)

- H1A holds if at least 50% of plausible cells have analytic median-cell z_OLS in [0.15, 0.35].
- H1B holds if H1A holds and the standard deviation of z_OLS across plausible cells is < 0.05.
- claude-opus-5-5 n=2 passes its own criterion if H1A and H1B hold ("z needs no mechanism and the null is
  sharp"); it fails if the SD across plausible cells is >= 0.10 or H1A is false (its stated failure
  signature: the null can be tuned to fit any observed z, so it has no discriminating power); otherwise
  it is reported as partial. The Triantis et al. observed-z comparison in that proposal is not run
  because it needs a dataset that is not retrieved here; the comparison with real data is made on
  GIFT in Part 2 instead.
- H1C holds if in at least 70% of plausible cells the analytic q is < -0.01 (concave in log-log) and the
  logseries-placement form beats the power law by AIC > 10 in at least 70% of stochastic plausible cells.
- H1D holds if the isolate z of Preston's canonical lognormal lies within 0.262 +/- 0.02.

### Preston canonical lognormal

Canonical (gamma = 1): the individuals curve (peak at mu + sigma^2 on the natural-log abundance axis)
coincides with the abundance of the most abundant species, taken as the expected maximum
mu + sigma * q_S with q_S = Phi^-1(1 - 1/(2 S)) and the rarest species set at one individual (the veil
line is at 1: mu = sigma * q_S). Gamma = 1 gives sigma = q_S, hence mu = sigma^2. For S on a log-spaced grid
from 30 to 1e6 species the abundance vector is n_j = max(1, round(exp(mu + sigma Phi^-1((j-0.5)/S)))),
N = sum n_j, and the isolate exponent is the slope of ln S on ln N (area proportional to N): global OLS over
S in [100, 1e5] and the local slope per S. Stochastic confirmation: independent lognormal draws with the same
(mu, sigma) at S in {100, 1000, 10000}, truncated at 1, 200 replicates. Also reported: the canonical
a = 0.2 form (sigma = 1/(0.2 sqrt 2) octaves = 2.45 natural-log units, S where gamma = 1) sampled by
random placement at area fractions 1e-6..1 (the "sample" exponent, which Preston distinguished from
the isolate exponent).

## Part 2. Real data (GIFT)

### Data

GIFT, the Global Inventory of Floras and Traits (Weigelt et al. 2020, Journal of Biogeography,
https://doi.org/10.1111/jbi.13623), public anonymous API at https://gift.uni-goettingen.de/api/.
Tables used: `index.php?query=geoentities` (entity_ID, area in km2, centroid, distance_to_mainland),
`extended/index.php?query=lists` (list metadata), and per list
`extended/index.php?query=checklists&listid=<id>` (species rows with the `native` flag). The fetch
script records URL, retrieval time, byte size and SHA-256 per file.

Dataset selection, frozen now:

- Lists: taxon_ID = 2 (Tracheophyta), type in {Flora, Checklist}, subset in {all, native,
  native and naturalized}, native_indicated = 1, restricted = 0, suit_geo = 1.
- Richness of a list: number of distinct work_ID among rows with native = 1.
- Entity: entity area > 0 (from geoentities). One list per entity, the one with the largest native
  richness. Richness >= 1.
- Islands (primary): entity_class = "Island" (not Island Group, Island Part, Island/Mainland).
- Mainland (secondary comparison for darwin1859-ch12-04): entity_class = "Mainland" with entity_type
  in {Political Unit, Botanical Country, Landscape/Region}; a random subset of at most 400 such
  entities (seed above) if more are eligible, to bound download size.
- Island group (needed for between-group heterogeneity): GIFT returns no island-group field in the
  tables above. Following the grok-4-7 rule (do not invent clusters) the groups are mechanical:
  cells of a fixed 60 degree longitude x 30 degree latitude grid applied to the centroid (longitude from
  -180, latitude from -90). A group is qualifying if it contains at least 10 eligible islands. If fewer
  than 5 groups qualify the universality rule is inconclusive.
- Exploratory only (not used in a verdict): z by isolation class (distance_to_mainland < 100 km,
  100-1000 km, > 1000 km).

### Models (all fitted to island richness S by maximum likelihood with a negative binomial (NB2) likelihood, same
likelihood and same data for every model, dispersion estimated)

- M_pow: mu = exp(b0 + z ln A).
- M_quad: mu = exp(b0 + z ln A + q (ln A)^2) (power law with log-log curvature; local exponent
  z + 2 q ln A).
- M_gle: mu = max(c + z ln A, 1e-6) (Gleason logarithmic).
- M_lom: mu = d / (1 + c A^-z) (Lomolino-type sigmoid; d, c, z > 0).
- M_ls: mu = alpha ln(1 + A / A*) (logseries-placement curve, the METE-type non-power form; NOT meteR,
  which needs abundance totals GIFT does not hold; alpha, A* > 0).

Selection by AIC (pooled over all eligible islands) and by spatially blocked cross-validation: leave one
qualifying group out, fit on the rest, sum the held-out NB log-likelihood (ELPD); islands in
non-qualifying cells are always in the training set. Mean absolute residual is on the ln S scale.
Secondary robustness fits (reported, never decide a verdict): OLS of log10 S on log10 A with
robust SE; islands with area >= 1 km2 only.

### Decision rules (Part 2, island SAR)

Universal power law (U), all of:
- U1: pooled M_pow z in [0.15, 0.35];
- U2: pooled z 95% interval (bootstrap over islands, 1000 resamples) of width < 0.1;
- U3: at least 5 qualifying groups and every qualifying group's z 95% interval (Wald, NB GLM) overlaps the
  pooled interval;
- U4: DerSimonian-Laird between-group SD of z (tau) < 0.05;
- U5: no alternative beats M_pow by AIC > 10 and by held-out ELPD > 10.
Universality refuted if two qualifying groups have non-overlapping 95% z intervals, or if any
qualifying group's interval does not overlap the pooled one (falsifier text in problems.json).
Scale-dependent form supported if all of: M_quad beats M_pow by AIC > 10 and by ELPD > 10; q is
negative or positive with the same sign in >= 70% of qualifying groups; the 95% interval of q pooled
excludes 0. METE-type win (grok-4-7 n=1 rule): M_ls beats M_pow by AIC > 10 and has smaller mean absolute
residual (ln S); a win on only one of the two is a split and not a win. Overall classification:
"universal power law" (U holds), "scale-dependent / non-power" (scale-dependent supported and
universality refuted or U5 fails), "power law holds on average but exponent is not universal"
(U1 and U5 hold, U3 or U4 fail), otherwise "neither". Data too thin (fewer than 150 eligible islands
or fewer than 5 qualifying groups) -> inconclusive, underpowered.

### grok-4-7 n=2 (logseries null on GIFT islands), adapted

Proposal: fit a logseries to the largest island, thin individuals onto the other islands in proportion
to area, 1000 replicates, and ask whether the empirical pooled z lies in the central 95% of the null z.
GIFT has no abundances, so the logseries is not identifiable from richness alone (S = alpha ln(1 + N/alpha)
has two unknowns). Adaptation, frozen now: the calibration island is the eligible island with the largest
area; for each individuals-per-km2 density rho in {1e1, 1e2, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8}
(N_cal = rho * A_cal, require N_cal > S_cal) alpha is solved from S_cal = alpha ln(1 + N_cal/alpha); species
abundances for the calibration island are S_cal draws from the logseries with p = N_cal/(N_cal + alpha);
each other island with area A_i takes each species Binomial(n_j, A_i/A_cal) (individuals placed
independently in proportion to area, the same density everywhere); 300 replicates per density (not
1000, for run time), z estimated by the same NB GLM (M_pow) on the remaining islands. Verdict per
density: empirical z inside the central 95% (2.5-97.5 percentile) of the null z. The approach "passes" if it
is inside for at least one density and "fails" otherwise; if it is inside for at least 5 of 8 densities
the null is also flagged as having no discriminating power (it fits whatever density is assumed).
Using the test islands to fit the logseries would void the test; only the calibration island is used.

### darwin1859-ch12-04 (island versus equal-area mainland, secondary)

Fit M_pow on the mainland subset above, predict richness at each eligible island's area. Oceanic proxy:
islands with distance_to_mainland >= 500 km (GIFT field). Supports if the median ratio observed/predicted
over those oceanic-proxy islands is <= 0.5, at least 70% lie below the mainland prediction, and a one-sided
Wilcoxon signed-rank test of the log ratios gives p < 0.01; refutes if the median ratio is >= 1;
mixed otherwise. Reported with the caveat that extrapolation below the mainland area range is
model-dependent (areas outside the mainland range are flagged). This is a different dataset (GIFT checklists)
from the existing WCVP test of this claim and is an independent replication.

## Outputs and reproducibility

`PREREG.md`, `PREREG.sha256`, `part1_null.py`, `fetch_gift.py`, `part2_analysis.py`, `run_all.sh`,
`RESULTS.md`, `result.json`, `DEVIATIONS.md`, `derived/*.csv|json` (< 200 KB each), `data/` (git-ignored,
raw downloads; not committed) with `derived/gift_manifest.csv.gz` (URL, time, bytes, SHA-256 per file).
