# Pre-registration: phylogenetic model comparison of mammalian basal metabolic scaling

Problem: `metabolic-scaling-exponent` (`problems/problems.json`).
Approach run: claude-opus-5-5 #1 ("Pre-registered PGLS model comparison: single power law vs curvature vs
clade slopes"), informed by gpt-5-6-sol #1 (fixed-slope comparison, family/clade structure) and grok-4-7 #1
(PanTHERIA paired-mass regression, Upham trees, AIC gap over 100 trees).
Registered before any measured BMR or mass value was inspected. Agent: claude-sonnet-5-5 (cloud/local subagent).

## What was looked at before this registration (full disclosure)

Only: column names; row counts; counts of non-missing entries per column; counts per taxonomic class;
whether binomials in PanTHERIA occur among the tip labels of the Upham tree; file sizes and HTTP status of
candidate URLs. No BMR or body-mass value, no summary of values, no plot and no fit has been seen.
Counts seen: PanTHERIA (WR05 file) 5,416 species rows, 573 with a positive `18-1_BasalMetRate_mLO2hr` and a
positive `5-2_BasalMetRateMass_g` (22 orders), of which 547 have an exact binomial match among the 5,911
tips of the Upham et al. 2019 "Completed" tree; AnAge `dataset.zip` (build dated 2023-07-03) has 4,645
species rows, 627 with both "Metabolic rate (W)" and "Body mass (g)": Mammalia 422 (378 with a body
temperature), Aves 171 (2 with a temperature), Amphibia 18, Reptilia 16, fishes 0.

## Question and hypotheses

Does mammalian basal metabolic rate B scale with body mass M as one power law, and if so is the exponent
3/4 or 2/3, or is the relation curved or clade-specific?

* H34: single exponent b = 3/4.
* H23: single exponent b = 2/3 (surface-to-volume).
* Hcurve: log B is a non-linear (convex or concave) function of log M (Kolokotrones et al. 2010 report convexity).
* Hclade: slopes differ between orders.
* Hnull-underdetermined: the single-exponent interval contains both 2/3 and 3/4 and no alternative wins
  (the problem's own falsifier).

## Datasets (all must be downloaded and checksummed by `fetch.py`; nothing is vendored over 1 MB)

Primary (P):
* PanTHERIA 1.0, Wilson & Reeder 2005 taxonomy file, Jones et al. 2009 (Ecological Archives E090-184):
  `https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt`. Columns
  `18-1_BasalMetRate_mLO2hr` (B) and `5-2_BasalMetRateMass_g` (M, the mass paired with the rate), missing
  code -999. Species key `MSW05_Binomial`, order `MSW05_Order`.

Replication / secondary:
* AnAge build 2023-07-03, `https://genomics.senescence.info/species/dataset.zip`: "Metabolic rate (W)",
  "Body mass (g)", "Temperature (K)", "Data quality", "Specimen origin", Class, Order.

Phylogeny (primary tree T0):
* Upham, Esselstyn & Jetz 2019 (PLoS Biol 17:e3000494), the "Completed" 5,911-species set, topology
  constrained, node-dated ("NDexp"), from the authors' GitHub repository `n8upham/MamPhy_v1`
  (`_DATA/`), pinned to the repository commit current at retrieval (recorded in `fetch.py`):
  - T0 = `MamPhy_fullPosterior_BDvr_Completed_5911sp_topoCons_NDexp_MCC_v2_target.tre` (maximum clade
    credibility tree) for all headline numbers;
  - T100 = `MamPhy_fullPosterior_BDvr_Completed_5911sp_topoCons_NDexp_v2_sample100_nexus.trees` (100 posterior
    trees) for tree uncertainty.
  Sensitivity trees (reported only): the FBD-dated MCC tree
  `..._topoCons_FBDasZhouEtAl_MCC_v2_target.tre`, and the Bininda-Emonds et al. 2007 supertree
  `bininda-emonds-et-al2007_treeFile_Supp1.nex` from the same repository (it uses the MSW05 taxonomy that
  PanTHERIA uses), if its branch lengths parse as time.
  The VertLife web form is not used (it needs an interactive request).
* Tip names are of the form `Genus_species_FAMILY_ORDER`; the key is the first two fields. Species are
  matched to PanTHERIA/AnAge by exact `Genus_species`; no synonym resolution. Unmatched species are dropped
  and counted.

## Exclusion rules (fixed)

Primary P: keep rows with B > 0 and M > 0 (not -999) that match a tip of T0. No value-based outlier removal
in the headline analysis. Variables: y = log10 B (mL O2/h), x = log10 M (g). Duplicated binomials: none
expected; if present average y and x within species.

Secondary S1 (AnAge mammals): Class Mammalia, metabolic rate and mass present, Data quality not
"questionable", matched to T0; y = log10 W (W), x = log10 M (g).

## Models (all by phylogenetic generalised least squares, maximum likelihood, Pagel's lambda free in [0,1])

Covariance V = sigma^2 (lambda * C_offdiag + diag(C)), C = shared root-to-MRCA path length in the pruned tree,
tree rescaled to unit height; fixed effects solved by GLS; lambda by 1-D bounded likelihood maximisation;
AIC and AICc count lambda and sigma^2. All models in the comparison are fitted by ML to the same data.

* M1: y = a + b x. b with analytic 95% interval (t, n-2 df) and a 1,000-replicate parametric bootstrap
  interval (simulate from the fitted M1 including lambda, refit incl. lambda). Fixed-slope fits M1(2/3) and
  M1(3/4) are fitted too, and their AICc relative to free M1 is reported.
* M2: y = a + b1 xc + b2 xc^2, xc = x - mean(x). Local slope s(x) = b1 + 2 b2 xc. Effect size
  D = |s(q95) - s(q05)|, q = quantiles of x.
* M3a: order-specific intercepts and slopes, M3b: order-specific intercepts, one slope. Orders with fewer
  than 10 matched species are pooled into one group "OTHER" (own intercept and slope in M3a, excluded from the
  slope-spread criterion). LRT of M3a against M3b (chi-square, df = groups - 1) tests slope heterogeneity.
  Spread R = max - min of M3a slopes over orders with >= 10 species.
* Secondary M4 (AnAge mammals with body temperature only): M1 + c * (1 / (k Tb) centred), k in eV/K; report c.

## Pre-registered decision rule (thresholds fixed here)

Evaluated on T0 (headline) and on each of the 100 trees of T100 (robustness). A statement is "robust" if it
holds on >= 95 of the 100 trees.

1. Curvature wins (Hcurve): AICc(M1) - AICc(M2) > 10 **and** D >= 0.05. (Both are needed: a significant
   but tiny curvature does not count with n of several hundred.)
2. Clade slopes win (Hclade): AICc(M1) - AICc(M3a) > 10 **and** LRT(M3a vs M3b) p < 0.01 **and** R >= 0.10.
3. If 1 or 2 holds, the headline classification is **heterogeneous**: no single exponent describes mammalian
   BMR; the M1 slope is reported as a descriptive average only.
4. Otherwise the classification is by the M1 interval [L, U]:
   * **3/4**: L <= 0.75 <= U and 2/3 < L (excludes 2/3);
   * **2/3**: L <= 2/3 <= U and U < 0.75 (excludes 3/4);
   * **neither**: both 2/3 and 3/4 excluded;
   * **underdetermined**: interval contains both 2/3 and 3/4.
   The bootstrap interval must give the same classification; if not, the result is downgraded to
   "underdetermined".
5. Tree robustness: if the classification on T0 is not the classification on >= 95 of the 100 trees, report
   "tree-sensitive" and use the weaker statement (underdetermined).

Replication criterion for S1: S1 replicates P if the M1 classification (steps 1-5 applied to S1) is the same.

## Sensitivity analyses (reported, not decisive)

1. Mass: PanTHERIA adult body mass `5-1_AdultBodyMass_g` instead of the paired mass (labelled, never pooled).
2. Range: M1 slope within terciles of x; and with masses < 10 g or > 100 kg removed.
3. Outliers: drop species with |standardised GLS residual| > 3 and refit.
4. Clade: leave-one-order-out M1 slope range.
5. Tree and lambda: M1 on FBD tree, BE2007 tree, lambda fixed 0 (OLS) and 1 (Brownian).
6. Data source: S1, S1 restricted to species absent from P (independence), S1 with Data quality "high" or
   "acceptable" only, S1 by specimen origin (wild vs captivity), P+S1 union where B is the P value.

## Exploratory, not part of the verdict

* S3 birds (AnAge Aves, n about 171) with a tree from the Open Tree of Life induced-subtree API (topology only,
  Grafen branch lengths); done only if the tree can be retrieved; compares bird and mammal M1 slopes.
* S4 ectotherms: AnAge Amphibia + Reptilia have n = 34, with temperature; declared underpowered in advance
  (no inference threshold); only descriptive slopes with Boltzmann temperature term are reported.

## Mapping to the claim graph

The problem's related claims (thompson1917-ch03-07, -ch02-01, -ch03-10) concern weight versus length and growth
curves, not metabolism, and the existing tests of them (NHANES, DATRAS) are on other data. The nearest
Thompson statement that bears on the metabolic exponent is `thompson1917-ch02-05` (energy supply scales with
respiratory surface, i.e. M^(2/3), while work available scales as the cube of length). `result.json` is logged
against ch02-05 with `problem: "metabolic-scaling-exponent"` and the others in `related_claims`.
Verdict: `supports` if the classification is "2/3"; `refutes` if "3/4" or "neither" (the 2/3 premise is
excluded as a mammalian BMR exponent); `mixed` if "heterogeneous"; `inconclusive` (reason `other`, or
`data-unavailable` if the data or tree cannot be obtained) if "underdetermined". Mammalian BMR is only a
proxy for the energy-supply premise, and this will be stated in the caveats.

## Software

Python 3 with numpy, scipy, pandas, requests (venv in the run directory); PGLS is implemented in
`analysis.py`, validated on simulated data with known slope and lambda in `selftest.py` before use.
Random seed 20261101 for bootstraps.
