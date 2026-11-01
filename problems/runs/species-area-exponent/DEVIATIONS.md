# Deviations from PREREG.md

PREREG.md (sha256 in PREREG.sha256, timestamp 2026-11-01T09:47:06Z) was not edited. Everything below happened
after it was written. No threshold, model, selection rule or grid was changed after any result was seen.

1. **Location.** The brief says `problems/runs/species-area-exponent/`. The working tree had been
   reorganised (staged renames moving `problems/` to `problems/`; `problems/` itself holds only an empty
   `forecasts/run-reports/` folder), and the other run (`metabolic-scaling-exponent`) sits in
   `problems/runs/`. This run is in `problems/runs/species-area-exponent/`. Nothing outside it was
   modified.
2. **Debug runs before the full runs.** `part1_null.py --quick` (4 replicates) and `part2_analysis.py --quick`
   (100 bootstrap resamples, 20 null replicates) were run first to debug. Their outputs were read before the
   full runs, and the full runs used the same frozen rules; the numbers agree to the precision reported. Two
   code-only changes were made between debug and full runs and before reading any result of the changed code:
   a syntax error in a dictionary key was fixed, and the Nelder-Mead iteration cap and number of dispersion
   starting values in `part2_analysis.py:fit` were reduced for run time (the first version did not finish in
   10 minutes). The likelihood, models and thresholds did not change.
3. **grok-4-7 n=2 was adapted, as pre-registered.** GIFT has no abundances, so the logseries is not identifiable from
   the calibration island's richness; individuals per km2 was swept on an 8-point grid instead, 300
   replicates per point instead of 1000.
4. **Post hoc exploratory fine density sweep** (`part2_grok_fine.py`, not pre-registered, not used in a verdict):
   the replicate nulls have 95% intervals narrower than 0.02, so with only eight pre-registered densities the
   empirical z fell between grid points. The noise-free expected curve was evaluated on a 0.25-dex grid to see
   where the null would contain the empirical z. It is labelled exploratory wherever it is reported.
5. **Triantis et al. observed-z comparison (claude-opus-5-5 n=2) not run.** The proposal compares the null with the
   per-dataset z values in the Triantis, Guilhaumon and Whittaker (2012) compilation. Its supplement is
   journal-hosted and was not retrieved; a single Dryad search ("island species-area relationship dataset", first
   page of results) did not show a Triantis or Matthews island-SAR compilation (it did list
   `doi:10.5061/dryad.k9711`, "Between geometry and biology: the problem of universality of the species-area
   relationship", not opened). The sampling null was therefore compared with real data only through GIFT (Part 2).
   Not exhaustive; Matthews et al. 2016, Kreft et al. 2008 and GBIF were not tried.
6. **Not run at all:** claude-opus-5-5 n=1 (GBIF coverage-standardised test) and n=3 (random-effects meta-analysis),
   gpt-5-6-sol n=1 and n=2, grok-4-7 n=3 (Lean). They are outside the brief or need data not retrieved here.
7. **Island groups.** GIFT's tables carry no island-group field, so the pre-registered fallback (mechanical
   60 x 30 degree cells) was used; 16 of 26 non-empty cells qualified (>= 10 islands). These are not archipelagos.
8. **Mainland subset.** 245 eligible mainland lists (232 entities) were fewer than the pre-registered cap of 400
   entities, so all were used (no random subsampling happened).
9. **Unrelated pre-existing stub.** `test-data/claim-tests/darwin-origin/darwin1859-ch12-04/overnight-sar-null/result.json`
   (a pre-registered, not run, test of the same claude-opus-5-5 n=2 approach) was seen and left alone; this run's
   grid and thresholds are different and were fixed independently.
