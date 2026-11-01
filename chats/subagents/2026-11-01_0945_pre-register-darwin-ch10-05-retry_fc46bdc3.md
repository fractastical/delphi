# Subagent: Pre-register darwin ch10-05 retry

- **Parent chat:** [do we need to go rhough and validate more of the claims ? we should have another](../2026-10-31_2254_do-we-need-to-go-rhough-and-validate-more-of-the-claims-we-s.md)
- **Started:** 2026-11-01 09:45 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 10:11 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `fc46bdc3-bc2d-41fd-adee-7a315a2eefd3`

---

### 2026-11-01 09:45 — Turn 1 (User)

> Repo: /Users/jdietz/Documents/GitHub/dev/delphisci (flat layout: test-data/, claim-sources/, scripts/ at the repo root; if that is not the case, look for an engine/ prefix, and tell me which). Your job: PRE-REGISTER one data test for claim `darwin1859-ch10-03` (Darwin, Origin of Species). Do NOT run the analysis and do NOT look at any data values.
> 
> Read first: test-data/claim-tests/README.md (rules and result.json schema, including test_contract), test-data/dataset-scouting/darwin-origin/darwin1859-ch10-03/datasets.json (the scout's record: which open dataset holds the variables), the claim in claim-sources/darwin-origin/claims.json, and the dataset-resolvability assessments for this claim under claim-sources/darwin-origin/assessment/raw/*/ (grep for the claim id) for the proposed operationalization. A good worked example of a pre-registration is `git show ed505563 --format=` (test-data/claim-tests/thompson-growth-form/thompson1917-ch02-03/limb-bone-pgls-01/result.json): copy its depth and style.
> 
> Write exactly one file: test-data/claim-tests/darwin-origin/darwin1859-ch10-03/<short-run-name>-01/result.json with status "preregistered", hypothesis, pass_criterion, fail_criterion (include mixed and inconclusive rules and minimum n), planned_datasets, datasets (id, name, landing_url, doi/version/license as verified in the scout record; download_url and the exact API query or file to fetch; do not invent anything), test_contract (all four fields), interpretation (how Darwin's terms map to measurable quantities; flag modern reinterpretation; state what the test does not cover), caveats (state honestly what you inspected before registering, e.g. field names/headers/record counts only, and any prior knowledge of the likely outcome), created date from `date -u`, and agent {kind:'cursor-subagent', model:<your model id>, run:'prereg-darwin-batch-1', date}. Thresholds must be numeric and fixed now, chosen from the claim's own wording and conventional statistics, not tuned to an expected result. You may make metadata-only requests (API field lists, record counts, HEAD requests) to confirm that the planned fetch works; cap about 6 requests; never download over 1 MB; never compute the statistic. If you find the planned dataset cannot hold the needed variables, say so in a REPORT note inside your final response and still write the best honest pre-registration, or say it should be dropped.
> 
> Hard rules: write only that one result.json (create the directories); do not edit claim files, assessments, nanopubs, docs/, or scouting records; do not git commit or push; never sign or publish anything. Validate that the file parses as JSON (python3 -m json.tool). Final response: the run directory path, the hypothesis, the pass/fail criteria in two lines each, and any doubts about operationalization.

**Assistant:**

Flat layout confirmed. Now the claim and assessments.

I'm weighing PBDB data sources for genus-level ranges, since occurrence lists are too massive to work with directly. Using taxa/list with the appearance data option could give first and last appearance info more efficiently.

There's a complication though: environment data is tied to occurrences or collections, not individual taxa. So I'm considering the occs/taxa endpoint, which might return per-taxon appearance ranges filtered by environment and base taxon, letting me get marine genus durations without pulling the full occurrence table. I should test this with small limited requests to confirm the fields and behavior before committing to it as the core design.

Matching environments across clades is tricky since marine and terrestrial organisms belong to different lineages, so a cleaner comparison might rely on per-capita origination/extinction rates (Foote-style boundary-crossing) in stage bins across Phanerozoic genera, since raw median duration is biased by preservation and the pull of the recent. I'm thinking the primary metric should be sampling-standardized boundary-crossing rates, possibly supplemented by a subsample with equal occurrence counts per bin, restricted to Metazoa genera assigned to environment categories.

I'm working out how to query the Paleobiology Database API, assigning genera to marine or terrestrial based on whether ≥90% of their occurrences fall into one environment type, then pulling separate occs/taxa queries for each group with occurrence counts and first/last appearance fields to test feasibility before scaling up.

The query returned 96,230 terrestrial taxa, but it looks like that includes ancestor ranks like Animalia rather than being limited to genus level, so taxon_reso may not have filtered as expected. I'm noting the fields returned—first and last appearance ages—and planning to try a rank filter instead.

My marine query timed out again at 30 seconds, so I'm going to retry with a longer 120-second timeout running in the background, and consider adding genus-level taxon resolution parameters. I'll also check the occs/taxa documentation endpoint to see if that approach might work better for the marine count.

I'm noticing a discrepancy between the taxa count and occurrence count for Animalia, likely because the taxa-based query includes non-Metazoa groups while the occurrence-based query used a narrower filter.

Let me also confirm the rank=genus filter works with show=app for terrestrial taxa, requesting a small limit and using the same app fields (fea, fla, lea, lla) as before, with a longer timeout since these queries run slow.

I'm seeing about 28,550 terrestrial genera, though one flagged crinoid record suggests some noise in the envtype classification. I also noticed I inadvertently glimpsed a couple of actual data values (names and ages) despite the instruction to stay metadata-only, which I should flag, and I'm also noting the fea/fla/lea/lla fields for first/last appearance timing.

I'm now sketching a pre-registration design: the hypothesis is that terrestrial genera show higher per-capita origination and extinction turnover than marine genera across Phanerozoic stage bins, and I'm planning the fixed fetch parameters (base_name=Metazoa, rank=genus, show=app, split by envtype) while keeping track of how many requests I've already used.

I'm working out how to compute each genus's environment fraction from terrestrial vs. marine occurrence counts, classifying a genus as terrestrial if that fraction is ≥0.9 and marine if ≤0.1, dropping ambiguous ones. Then I'm setting up fixed 10-Myr bins from 0–540 Ma using midpoint first/last appearance ages, and planning to compute Foote-style per-capita boundary-crosser turnover rates for each bin.

I'm now deriving origination and extinction rates from boundary-crosser counts across bin edges, requiring minimum sample sizes per environment before including a bin so the comparison is robust to singleton genera and sampling gaps.

For the paired comparison, I'm planning a Wilcoxon signed-rank test on the terrestrial-minus-marine turnover difference across qualifying bins, supplemented by a bootstrap confidence interval on the median difference, while flagging the autocorrelation issue between adjacent bins.

For a pass I'm requiring at least 15 qualifying bins, a positive median difference, a 95% bootstrap CI excluding zero, and at least 60% of bins showing a positive difference, plus confirmation under a sampling-standardized robustness check. Since true occurrence-level standardization isn't feasible with only occurrence counts per taxon, I'm considering instead restricting to well-sampled genera with at least three occurrences as an alternative robustness filter, though I recognize terrestrial genera tend to be more sparsely sampled, which could bias that threshold unevenly between environments.

I'm also adding a Cenozoic-only restriction as a secondary robustness check since terrestrial records are best preserved there, and defining failure criteria: the hypothesis is refuted if the median difference is negative with a CI upper bound below zero, while a CI spanning zero despite adequate bin count would be treated as an inconclusive, mixed result rather than outright support or refutation.

A directional claim with a CI spanning 0 isn't really a refutation unless the CI is tight enough to rule out meaningful effects. I should pre-specify a smallest effect of interest, maybe around 0.01 per Myr, a rough fraction of typical Phanerozoic turnover rates, so a narrow null CI can count as genuine refutation rather than just inconclusive.

I should also mark inconclusive if fewer than 15 qualifying bins exist, data fetch fails, or fewer than 2,000 genera get classified in either environment, and I'll report the fraction of dropped records from the environment-coding check. On limitations, I need to flag genus-level taxonomic differences and the fact that I'm only using PBDB—excluding NOW (Cenozoic mammals only, no marine comparison) and Dryad (lacks a marine group)—while noting Darwin's own reference point was Pictet's Swiss Tertiary fauna.

For the statistical pass criteria, I'm settling on requiring at least 15 bins, a positive median difference, a bootstrap 95% CI lower bound above zero, a one-sided Wilcoxon signed-rank p<0.05, and a robustness check restricted to genera with 5+ occurrences showing the same pattern, using 10,000 percentile bootstrap resamples. I also need to precisely define how boundary-crossing genera are assigned to 10-Myr bins based on their FAD/LAD midpoints relative to each bin's start and end.

For extant genera with LAD=0, I'm applying the Pull of the Recent correction by excluding the most recent bin from extinction rate calculations to avoid the edge effect that artificially inflates survivorship in the youngest time slice.

I need bins to require at least 5 qualifying genera before computing rates, and I should keep the midpoint calculation consistent even when the LAD is zero for extant taxa. For the data fetch, I'm checking whether PBDB's API requires pagination with limit/offset for large result sets, since omitting limit should return everything but I want to confirm that works reliably.

I'm also thinking through the interpretation side: the "change" metric reflects genus-level turnover rather than morphological change, which is a modern reinterpretation rather than what Darwin literally meant, so I shouldn't conflate the two. I need to settle on clear definitions for marine versus terrestrial environments using PBDB's envtype groupings, since terrestrial likely bundles in freshwater categories like fluvial and lacustrine settings.

I also noticed some oddities when glimpsing sample records — a Cambrian taxon and a Triassic echinoderm both flagged as terrestrial, which looks like environment-coding noise. This is honestly what motivated adopting a ≥90% threshold rule, even though that rule was conceived after peeking at the data, so I should disclose that timing transparently.

I'm drawing on general familiarity with PBDB-based turnover literature without inventing specific citations — my expectation is that terrestrial taxa will show higher raw turnover partly due to preservation bias and shorter observed ranges rather than true biological signal, so any pattern found should be treated as potentially artifactual.

For mitigation, I'll build in robustness checks restricting analysis to genera with at least 5 occurrences (possibly also testing ≥10 as a stricter threshold), framing this as a Lazarus-effect mitigation since missing records within a range inflate both origination and extinction rate estimates in the same direction that would support the claim — meaning a positive result should be labeled as weak, caveated evidence rather than strong support.

Now I'm working through metadata for the output file: deciding on the model identifier, dating it to the current retrieval period, and noting that dataset details like DOI, version, and license from PBDB can't be fully verified so I should mark them as null or unverified rather than guessing.

I'm also finalizing the exact query URLs to use, keeping the same tested parameters (including order=hierarchy) rather than altering them, since file sizes and retrieval timestamps will just be filled in at actual run time.

I need to flag the ambiguity around what "noc" actually counts in the occurrence response — likely occurrences matching the terrestrial/marine filter at genus rank, but I'm not fully certain whether species-level occurrences roll up into the genus count, so I should mark this assumption as unverified. The rank=genus filter should mean both result sets only contain genus-level taxa, which looks consistent with what I saw. Now I'll go ahead and write the JSON output using the Write tool.

I need to clean up that garbled caveats sentence about the limit=2 request calls. Also noting the Animalia terrestrial species count of 348,354 came from the first request with no rank filter applied, which is fine as-is.

I wrote the pre-registration for `darwin1859-ch10-03`, and it parses as JSON (`python3 -m json.tool`). I ran no analysis and computed no statistic. I made about six PBDB metadata requests. Nothing was committed or published. The layout is flat (`test-data/`, `claim-sources/`, `scripts/` at the repo root), with no `engine/` prefix.

**Run directory:** `test-data/claim-tests/darwin-origin/darwin1859-ch10-03/pbdb-land-sea-turnover-01/` (the file is `result.json`)

**Hypothesis:** If land productions change faster than sea productions, terrestrial animal genera in the Paleobiology Database (PBDB) have higher per-capita turnover than marine genera in matched 10-Myr bins. Turnover is the mean of Foote boundary-crosser origination and extinction rates. The median paired bin difference, terrestrial minus marine, should be above 0.

**Pass (supports):**
- The primary analysis has at least 15 qualifying bins, a median difference above 0, a 95% bin-bootstrap interval with its lower bound above 0, and a one-sided Wilcoxon p below 0.05.
- The robustness repeat, restricted to genera with at least 5 occurrences, also has at least 15 bins, a positive median and Wilcoxon p below 0.05.

**Fail (refutes):**
- The upper bound of the 95% interval is at or below 0, or the whole interval lies inside ±0.01 per genus per Myr (equal rates count against the claim).
- Mixed: the interval includes 0 without falling inside the equivalence band, the robustness check fails, or origination and extinction differ significantly in opposite directions.
- Inconclusive: fewer than 15 bins or fewer than 2,000 genera per environment (underpowered), or the data cannot be fetched (data-unavailable).

**REPORT notes:**
- **Dataset fit:** PBDB can hold the needed variables. `occs/taxa` with `rank=genus` and `show=app` returns first and last appearance bounds plus occurrence counts. Terrestrial returned 28,550 genera.
- **Not confirmed:** I did not run the marine genus-rank query, so its count is unknown. I did not confirm that `noc` includes species-level occurrences. I did not read the membership of PBDB's marine and terrestrial environment groups. The scout's marine occurrence count (1,090,143) differs from the `occs/taxa` figure (1,670,076), and I did not resolve that.
- **The scout's other datasets are dropped:** NOW has no marine comparison, and the Dryad Mesozoic tetrapod deposit has none either.
- **What I saw:** I viewed two genus records and the root record. Both genera are coded terrestrial: a Cambrian genus and a Triassic crinoid, so some terrestrial coding looks wrong. That led to the 90% occurrence-fraction rule for assigning environments. The file declares this as a design choice made after that glimpse.

**Doubts about operationalization:**
- **Direction of bias:** Poorer terrestrial preservation breaks ranges and inflates boundary-crosser rates, which pushes toward the claim. A pass is therefore weak evidence. There is no preservation model or occurrence-level subsampling, and the 5-occurrence filter only reduces the bias.
- **Reading of "change":** I mapped "rate of change" to genus-level turnover, not morphological change or species turnover.
- **Clade matching:** Land and sea faunas are mostly different clades, so clade composition is confounded with environment. A Tetrapoda comparison is descriptive only.
- **Statistics:** Adjacent bins share genera, so the bootstrap and Wilcoxon results will be optimistic.
- **Thresholds:** The ±0.01 equivalence band and the minimum counts (15 bins, 20 and 5 genera per bin, 2,000 genera per environment) are round conventional choices. They are not derived from a power analysis.

The PBDB licence is not verified; the scout recorded none, so `license` is null with a note.

_Tools used: AwaitShell, Grep, Read ×3, Shell ×7, StrReplace, UpdateCurrentStep ×2, Write_
