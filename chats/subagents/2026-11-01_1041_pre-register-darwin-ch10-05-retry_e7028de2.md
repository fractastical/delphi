# Subagent: Pre-register darwin ch10-05 retry

- **Parent chat:** [do we need to go rhough and validate more of the claims ? we should have another](../2026-10-31_2254_do-we-need-to-go-rhough-and-validate-more-of-the-claims-we-s.md)
- **Started:** 2026-11-01 10:41 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 11:15 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** unknown
- **Transcript ID:** `e7028de2-20a3-401b-85b1-3de281cefbb8`

---

### 2026-11-01 10:41 — Turn 1 (User)

> Repo: /Users/jdietz/Documents/GitHub/dev/delphisci (flat layout: test-data/, claim-sources/, scripts/ at the repo root; if that is not the case, look for an engine/ prefix, and tell me which). Your job: PRE-REGISTER one data test for claim `darwin1859-ch10-01` (Darwin, Origin of Species). A previous attempt failed on connection errors and wrote nothing, so write the file early and refine it. Do NOT run the analysis and do NOT look at any data values.
> 
> Read first: test-data/claim-tests/README.md (rules and result.json schema, including test_contract), test-data/dataset-scouting/darwin-origin/darwin1859-ch10-01/datasets.json (the scout's record: which open dataset holds the variables), the claim in claim-sources/darwin-origin/claims.json, and the dataset-resolvability assessments for this claim under claim-sources/darwin-origin/assessment/raw/*/ (grep for the claim id) for the proposed operationalization. Other pre-registrations in this batch to match in style: test-data/claim-tests/darwin-origin/darwin1859-ch10-10/pbdb-cenozoic-balance-01/result.json and darwin1859-ch04-26/pbdb-survival-01/result.json; also `git show ed505563 --format=` for the original worked example. Do not duplicate their tests: this claim is about NEW SPECIES appearing slowly and one after another, on land and in water, so design a distinct test on its own wording.
> 
> Write exactly one file: test-data/claim-tests/darwin-origin/darwin1859-ch10-01/<short-run-name>-01/result.json with status "preregistered", hypothesis, pass_criterion, fail_criterion (include mixed and inconclusive rules and minimum n), planned_datasets, datasets (id, name, landing_url, doi/version/license as verified in the scout record, null if unverified; download_url and the exact API query or file to fetch; do not invent anything), test_contract (all four fields), interpretation (how Darwin's terms map to measurable quantities; flag modern reinterpretation; state what the test does not cover), caveats (state honestly what you inspected before registering and any prior knowledge of the likely outcome), created date from `date -u`, and agent {kind:'cursor-subagent', model:<your model id>, run:'prereg-darwin-batch-1-retry', date}. Thresholds must be numeric and fixed now, not tuned to an expected result. Metadata-only requests (field lists, record counts, HEAD) are allowed; cap about 5 requests; if a request fails, do not retry more than once and note it; never download over 1 MB; never compute the statistic.
> 
> Hard rules: write only that one result.json (create the directories); do not edit claim files, assessments, nanopubs, docs/, or scouting records; do not git commit or push; never sign or publish anything. Validate with python3 -m json.tool. Final response: the run directory path, the hypothesis, pass/fail criteria in two lines each, and doubts about operationalization.

**Assistant:**

Good, the layout is flat. Now I'll move on to reading the claim, the assessments, and the sibling prereg files.

I should check the land-sea turnover and genus richness siblings to avoid overlap, then design a distinct test. The real claim is about origination being gradual and asynchronous rather than happening in simultaneous batches, so I'm thinking of using PBDB genus-level first-appearance data with min/max age ranges to examine this directly.

Splitting by environment is tricky since taxa/list lacks an environment field, and pulling per-occurrence environment data would be too large a query. I'm considering using occs/diversity with envtype filters (marine worked before, terr was rejected) to test rowcounts per stage as a workaround, keeping my request budget tight.

For the actual statistical test, I want to compute origination counts per stage (X_Ft + X_FL), normalize by standing diversity for a per-capita rate, and check whether originations cluster in a single burst stage versus a uniform null — focusing the window on Paleogene and Neogene stages to match Darwin's emphasis on the Tertiary, while differentiating my approach from the earlier balance-based analysis by focusing purely on origination burstiness.

I'm settling on a per-capita origination rate per million years, normalizing new genera by total sampled diversity in each interval, as a way to measure how evenly originations are spread across stages rather than concentrated.

With uniform share, 3/17 ≈ 0.176, so I want M3 ≤ 0.30 as a pass threshold in both environments. I need a proper null though—since stage durations are unequal, a uniform-rate null would expect the top-3 share to equal the share of total duration from the three longest stages, so I'm tallying up Cenozoic stage durations to compute that baseline.

Rather than rely on memory for exact duration values, I'll switch to a rate-based concentration measure instead: define a pulse as any stage where the per-Myr rate exceeds the median plus three robust MAD units, and check whether the number of pulse stages supports the claim.

I also need to think about sample size issues—marine data is probably solid across all 17 stages but terrestrial coverage may be sparse, especially in older intervals, so I should set a minimum genera threshold per stage and treat terrestrial results as inconclusive if too many stages fall short, requiring both environments to pass for a full verdict rather than just one.

Now I'm defining the core origination-pulse statistic: fraction of new genera per stage per environment, normalized by stage duration, then flagged as a pulse if its robust z-score (using median and MAD, Iglewicz-Hoaglin style) exceeds the standard outlier threshold of 3.5.

I also want a secondary "steady successive origination" condition requiring that originations occur in nearly every usable interval—at least 80% of stages with meaningful new-genera counts—rather than concentrating in one or two bursts. I note that the Danian recovery after the K-Pg event will likely register as a pulse, which is a legitimate radiation signal rather than noise, so I should check sensitivity by excluding that interval separately.

I'm also considering confounds like sampling bias from Lagerstätten and edge effects near the Piacenzian, which I'll note descriptively via correlation checks but won't use to override the verdict. For the actual fail criteria, I'm settling on: three or more pulse stages in at least one adequately sampled environment, or fewer than 60% of usable stages showing origination activity.

Since the claim asserts pulses occurred both on land and in water, failure in either domain alone should refute the whole conjunction—so if terrestrial data is too sparse to test (fewer than 12 usable stages), I'll mark that component "inconclusive-for-land" and let the overall verdict hinge on whether marine passes, fails, or is mixed, rather than treating insufficient land data as grounds for outright refutation.

I need to nail down what counts as a usable stage (at least 50 sampled genera) and require at least 12 such stages per environment, while being careful about how origination/extinction counts near boundaries like the Piacenzian-Recent transition are handled. I also want to check ch10-03 for possible overlap with another land-vs-sea turnover comparison before finalizing the metadata filters.

Before running the actual queries, I should verify envtype values by checking the diversity documentation page, keeping in mind my request budget is capped at 5 calls and under 1MB total, and the doc page itself is small enough not to be a concern.

I should verify that "terr" is a documented envtype by checking the env codes list alongside "marine," then try a header-only request with envtype=terr to confirm it works.

_Tools used: Grep ×3, Read ×4, Shell ×4, UpdateCurrentStep_
