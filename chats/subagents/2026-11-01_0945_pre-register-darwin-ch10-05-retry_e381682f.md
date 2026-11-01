# Subagent: Pre-register darwin ch10-05 retry

- **Parent chat:** [do we need to go rhough and validate more of the claims ? we should have another](../2026-10-31_2254_do-we-need-to-go-rhough-and-validate-more-of-the-claims-we-s.md)
- **Started:** 2026-11-01 09:45 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 09:47 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `e381682f-7ae3-4a3b-b99f-7774d4f1b7a0`

---

### 2026-11-01 09:45 — Turn 1 (User)

> Repo: /Users/jdietz/Documents/GitHub/dev/delphisci (flat layout: test-data/, claim-sources/, scripts/ at the repo root; if that is not the case, look for an engine/ prefix, and tell me which). Your job: PRE-REGISTER one data test for claim `darwin1859-ch04-26` (Darwin, Origin of Species). Do NOT run the analysis and do NOT look at any data values.
> 
> Read first: test-data/claim-tests/README.md (rules and result.json schema, including test_contract), test-data/dataset-scouting/darwin-origin/darwin1859-ch04-26/datasets.json (the scout's record: which open dataset holds the variables), the claim in claim-sources/darwin-origin/claims.json, and the dataset-resolvability assessments for this claim under claim-sources/darwin-origin/assessment/raw/*/ (grep for the claim id) for the proposed operationalization. A good worked example of a pre-registration is `git show ed505563 --format=` (test-data/claim-tests/thompson-growth-form/thompson1917-ch02-03/limb-bone-pgls-01/result.json): copy its depth and style.
> 
> Write exactly one file: test-data/claim-tests/darwin-origin/darwin1859-ch04-26/<short-run-name>-01/result.json with status "preregistered", hypothesis, pass_criterion, fail_criterion (include mixed and inconclusive rules and minimum n), planned_datasets, datasets (id, name, landing_url, doi/version/license as verified in the scout record; download_url and the exact API query or file to fetch; do not invent anything), test_contract (all four fields), interpretation (how Darwin's terms map to measurable quantities; flag modern reinterpretation; state what the test does not cover), caveats (state honestly what you inspected before registering, e.g. field names/headers/record counts only, and any prior knowledge of the likely outcome), created date from `date -u`, and agent {kind:'cursor-subagent', model:<your model id>, run:'prereg-darwin-batch-1', date}. Thresholds must be numeric and fixed now, chosen from the claim's own wording and conventional statistics, not tuned to an expected result. You may make metadata-only requests (API field lists, record counts, HEAD requests) to confirm that the planned fetch works; cap about 6 requests; never download over 1 MB; never compute the statistic. If you find the planned dataset cannot hold the needed variables, say so in a REPORT note inside your final response and still write the best honest pre-registration, or say it should be dropped.
> 
> Hard rules: write only that one result.json (create the directories); do not edit claim files, assessments, nanopubs, docs/, or scouting records; do not git commit or push; never sign or publish anything. Validate that the file parses as JSON (python3 -m json.tool). Final response: the run directory path, the hypothesis, the pass/fail criteria in two lines each, and any doubts about operationalization.

**Assistant:**

Flat layout confirmed. Now the claim and assessments.

I'm thinking about using PBDB genus-level data to operationalize the claim, treating the fraction of genera from a past interval that are still extant as a proxy, while noting this is an upper bound since species survival rates would be lower than genus survival rates.

For the data fetching plan, I'm considering querying `taxa/list` with rank=genus and show=app to get first/last appearance ages, but worried the full Metazoa genus list could be huge (100k+ rows, ~15MB). I'm weighing whether to start with smaller rowcount checks at the order/family level first, since downloads need to stay reasonably sized and shouldn't be committed to the repo.

I'm trying to figure out whether taxa/list filters out synonyms by default, since I'm unsure about the taxon_status parameter's default behavior—I may need to filter by accepted_no matching taxon_no in my own analysis instead of relying on an API parameter.

Good, taxon status confirms accepted counts. Now I'm thinking through the main analysis: for accepted order-rank Metazoa taxa with a fossil record, I want to compute what fraction are extinct versus extant at each taxonomic rank to quantify how many entire orders, families, and genera have died out.

For "very few species of past periods have living descendants," I'm planning a genus-level survival analysis: tracking genera that first appeared in the Paleozoic versus Mesozoic and checking what fraction remain extant today, since genus survival sets an upper bound on species survival. I'm setting a threshold of roughly 10% survival to count as "very few," echoing Darwin's description of only a couple surviving twigs on a vast tree, and need to decide whether to use first-appearance midpoints or maximum ages for stratifying genera into these time periods.

I'll settle on Paleozoic as the primary, most faithful stratum for "long-past periods," with Mesozoic reported secondarily—requiring the Paleozoic Wilson upper bound to stay at or below 0.10 for the claim to pass.

I'm refining the fail condition: a Wilson lower bound above 0.25 for Paleozoic genus survival or extinct-family share below 10% would contradict the "very few survive, many died out" claim, with mixed/inconclusive cases handled separately when data is too sparse. I also need to decide how to treat blank is_extant records—excluding them from the denominator but flagging sensitivity to that choice since the missing-data share could be substantial.

A deeper issue is pseudoextinction: a genus marked extinct in PBDB can still have living descendant genera, so genus-level survival understates true lineage survival in Darwin's sense of "modified descendants." This biases genus-based tests toward finding extinction even when the lineage persisted, so I should weight family- or order-level survival more heavily as a better proxy for descent continuity.

I'm also flagging a denominator problem: the analysis only captures genera with fossil records, not all species that actually lived, and genera with purely extant records lacking a first appearance get excluded. From prior knowledge, Paleozoic marine genus survival rates are roughly 5-15%, so a threshold around 0.10 could be borderline and worth disclosing as a caveat.

For data retrieval, I'm planning to pull genus, family, and order-level taxon data from PBDB with pagination in chunks of roughly 20,000 rows for the ~79,170 genus records, recording retrieval timestamps and checksums since PBDB is a live, evolving database and exact reproducibility will drift over time. I'll verify the CC0 license and save the smaller derived counts rather than the full raw downloads.

I'm settling on naming conventions: directory "pbdb-survival-01", run date 2026-11-01, and model id "claude-sonnet-5-5" for the metadata before writing out the JSON.

I should fix the awkward "Free-living" wording in my caveat, and double check the other notes—the unfiltered count ratio, the Trilobita header look, and the family/genus counts—all seem fine on review.

I wrote the pre-registration for `darwin1859-ch04-26` and it parses with `python3 -m json.tool`. The repo has the flat layout (no `engine/` prefix). I made 6 metadata-only requests to PBDB (the Paleobiology Database), covering one CSV header line, the licence block and record counts. I viewed no data values and computed no statistic.

**Run directory:** `test-data/claim-tests/darwin-origin/darwin1859-ch04-26/pbdb-survival-01/` (the only file is `result.json`).

**Hypothesis:** In PBDB's accepted Metazoa taxa, only a small minority of genera that first appeared in the Paleozoic are still extant. A large share of the families and orders that first appeared before the Cenozoic have no extant member.

**Pass** (all four must hold; "extant" is the PBDB `is_extant` flag):
- **P1, P2 (genera):** the Wilson 95 % upper bound of the extant fraction of Paleozoic genera (first appearance ≥ 251.9 Ma) is ≤ 0.10. For pre-Cenozoic genera (≥ 66.0 Ma), the point estimate is ≤ 0.10 and the upper bound is ≤ 0.15.
- **P3, P4 (families, orders):** among pre-Cenozoic taxa, at least 100 families and 20 orders, and at least 25 % of each extinct.

**Fail** (any one of three):
- **F1:** the lower 95 % bound of Paleozoic genus survival is above 0.25.
- **F2, F3:** the extinct share of pre-Cenozoic families or of orders is below 10 %.
- **Mixed or inconclusive:**
  - Mixed if neither pass nor fail holds. A pass also drops to mixed if it would fail with blank `is_extant` flags counted as extant.
  - Inconclusive if there are fewer than 200 Paleozoic genera, 200 Mesozoic genera or 50 families with usable fields, or more than 30 % blank flags among Paleozoic genera.

**Dataset:** PBDB data service 1.2, `taxa/list.csv?base_name=Metazoa&rank=genus|family|order&taxon_status=accepted&show=attr,app`. Genus pages are 20,000 rows each via `offset`. The licence is CC0, read from the service's own datainfo block. The header confirms the fields `is_extant`, `firstapp_max_ma`, `firstapp_min_ma`, `lastapp_*` and `n_occs`. The metadata query counted 79,170 accepted genera against 91,047 unfiltered. Downloads will exceed 1 MB, so they are not committed; the analysis must record a SHA-256 for each file.

**REPORT / doubts about operationalization:**
- **Proxy:** No source gives species-level ancestor–descendant links, so the test measures survival of taxa, not of species. It covers Darwin's "orders, families and genera died out" half directly and the species half only roughly. Pseudoextinction (an ancestral genus renamed or split) makes genus survival undercount lineage survival, so family and order extinction is the more robust measure. This is flagged in `interpretation`.
- **Borderline outcome:** I expect P3 and P4 to pass. Whether Paleozoic genus survival falls under 10 % is the real unknown, so P1 is where a "mixed" result could appear.
- **Prior exposure:** I saw the unfiltered counts of 17,984 extant genera out of 91,047 genus records (about 20 %). That mixes all ages and includes synonyms, so it is not the statistic tested, but I disclosed it in the caveats.
- **Open points before the run:**
  - I assumed `firstapp_min_ma` is the youngest bound of first appearance; this must be confirmed in the PBDB docs, and any swap recorded under `deviations`.
  - `retrieved_at`, `byte_size` and `sha256` are `null` until the run.
  - The accepted-only family and order counts were not requested.
- **Dropped sources:** The Open Tree of Life and the Catalogue of Life were dropped because neither gives first-appearance ages, and MorphoBank returned HTTP 403. Sepkoski's genus database has no bulk download, so it is only a possible descriptive replicate.

_Tools used: Grep, Read ×2, Shell ×6, StrReplace, UpdateCurrentStep ×2, Write_
