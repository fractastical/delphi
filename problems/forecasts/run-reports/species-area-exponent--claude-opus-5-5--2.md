# Coleman null for the island species-area exponent

Approach `species-area-exponent--claude-opus-5-5--2`, a computation. The null half was run. The comparison with observed exponents was not: the Triantis, Guilhaumon and Whittaker 2012 compilation is not in an open file. The problem is not solved.

Claim: `darwin1859-ch12-04` (oceanic islands have fewer species than equal continental areas). `darwin1859-ch12-05` is endemism; `darwin1859-ch11-02` is barriers.

Pre-registered before any download at `test-data/claim-tests/darwin-origin/darwin1859-ch12-04/overnight-sar-null/result.json`. Pass: Anderson–Darling p > 0.05 against the Coleman null means z needs no further mechanism. Fail: observed z systematically higher is an excess. Those fields were not changed.

Data search on 2026-11-01 for DOI 10.1111/j.1365-2699.2011.02652.x. Crossref lists no related dataset. DataCite has no 2012 Triantis dataset and no title match. Dryad returned 0. A Zenodo dataset query for the DOI returned 0. Figshare returned 0. Unpaywall and OpenAlex mark the paper closed. Europe PMC records no supplement and a subscription-only full text. Wiley returned HTTP 403 for the article and for downloadSupplement URLs. The only OpenAlex dataset that cites the paper is CRAN `sars`; its seven example curves are not the 601-dataset table and were not used. No observed z was invented.

`analysis.py` evaluates E[S(a)] = sum_i 1-(1-a)^{n_i} on the pre-registered fallback windows (per-dataset areas were unavailable). 1618 of 1632 cells are feasible. Median z is 0.134, mean 0.275, sd 0.304, 5th–95th percentile 0 to 0.925, maximum 0.986. The share with z in [0.20, 0.30] is 7.0%.

On the lognormal and log-series cells, total abundance J accounts for 79% of the variance in null z. The median is 0.752 at J=10^3, 0.286 at J=10^5, 0.055 at J=10^7 and 0.001 at J=10^9. Family medians: lognormal 0.105, log-series 0.196, Preston canonical 0.123. Preston communities, with the least abundant species fixed at one individual, have realized J of 4523, 1411693 and 539369619 for S0 of 20, 100 and 500. One stochastic draw at J=1000 (seed 20261101) differed from the analytical z by 0.027 on average (maximum 0.340, 371 comparisons) and was not treated as data. The log-series closed form matches a truncated Coleman sum to 5e-13. Fourteen cells were infeasible, all embedded windows whose small islands fell below expected richness 0.5.

Verdict: inconclusive, reason data-unavailable, data_kind computational, confidence 0.8. The Anderson–Darling test was not run. Random placement does put fewer species in a smaller sample, which is the direction of Darwin's sentence, but this run does not show that islands do so, and it does not pin z near 0.25. With J free, the null can sit almost anywhere in (0, 1). That is the approach's failure signature as a property of the calculated curves, not a test of the compilation.

The problem's acceptance criteria are unmet. No GBIF archipelago comparison was run. Per-cell z values are in `derived/null_z.csv` (117550 bytes).
