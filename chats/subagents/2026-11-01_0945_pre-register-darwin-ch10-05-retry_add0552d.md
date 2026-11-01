# Subagent: Pre-register darwin ch10-05 retry

- **Parent chat:** [do we need to go rhough and validate more of the claims ? we should have another](../2026-10-31_2254_do-we-need-to-go-rhough-and-validate-more-of-the-claims-we-s.md)
- **Started:** 2026-11-01 09:45 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 09:48 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `add0552d-f723-4bb5-8e83-f091559ecba7`

---

### 2026-11-01 09:45 — Turn 1 (User)

> Repo: /Users/jdietz/Documents/GitHub/dev/delphisci (flat layout: test-data/, claim-sources/, scripts/ at the repo root; if that is not the case, look for an engine/ prefix, and tell me which). Your job: PRE-REGISTER one data test for claim `darwin1859-ch02-09` (Darwin, Origin of Species). Do NOT run the analysis and do NOT look at any data values.
> 
> Read first: test-data/claim-tests/README.md (rules and result.json schema, including test_contract), test-data/dataset-scouting/darwin-origin/darwin1859-ch02-09/datasets.json (the scout's record: which open dataset holds the variables), the claim in claim-sources/darwin-origin/claims.json, and the dataset-resolvability assessments for this claim under claim-sources/darwin-origin/assessment/raw/*/ (grep for the claim id) for the proposed operationalization. A good worked example of a pre-registration is `git show ed505563 --format=` (test-data/claim-tests/thompson-growth-form/thompson1917-ch02-03/limb-bone-pgls-01/result.json): copy its depth and style.
> 
> Write exactly one file: test-data/claim-tests/darwin-origin/darwin1859-ch02-09/<short-run-name>-01/result.json with status "preregistered", hypothesis, pass_criterion, fail_criterion (include mixed and inconclusive rules and minimum n), planned_datasets, datasets (id, name, landing_url, doi/version/license as verified in the scout record; download_url and the exact API query or file to fetch; do not invent anything), test_contract (all four fields), interpretation (how Darwin's terms map to measurable quantities; flag modern reinterpretation; state what the test does not cover), caveats (state honestly what you inspected before registering, e.g. field names/headers/record counts only, and any prior knowledge of the likely outcome), created date from `date -u`, and agent {kind:'cursor-subagent', model:<your model id>, run:'prereg-darwin-batch-1', date}. Thresholds must be numeric and fixed now, chosen from the claim's own wording and conventional statistics, not tuned to an expected result. You may make metadata-only requests (API field lists, record counts, HEAD requests) to confirm that the planned fetch works; cap about 6 requests; never download over 1 MB; never compute the statistic. If you find the planned dataset cannot hold the needed variables, say so in a REPORT note inside your final response and still write the best honest pre-registration, or say it should be dropped.
> 
> Hard rules: write only that one result.json (create the directories); do not edit claim files, assessments, nanopubs, docs/, or scouting records; do not git commit or push; never sign or publish anything. Validate that the file parses as JSON (python3 -m json.tool). Final response: the run directory path, the hypothesis, the pass/fail criteria in two lines each, and any doubts about operationalization.

**Assistant:**

I need to design a way to test this claim using PBDB data, looking at marine animal genera and species richness per genus across stage bins. I'm weighing data fetch options—occurrence downloads are large, so I'm considering using the taxa list endpoint to get per-genus counts more efficiently.

I'm thinking through how to design the richness statistic: using fixed 10-Myr bins across the Phanerozoic instead of relying on PBDB's interval scale, and defining species ranges from midpoints of first/last appearance ages. I also need to account for range-through bias at the species level (like the Pull of the Recent effect from singleton collections) when computing genus-level species richness trajectories across bins.

For testing whether "small genera often grow large," I need working definitions: genus size based on peak richness across bins, "small" as an initial richness of 1-2 species, and "growth" as a multiplicative increase relative to that initial value. The tricky part is quantifying "often" — this likely requires some baseline comparison or permutation test rather than an arbitrary fixed threshold.

For eligibility criteria, I'm leaning toward extinct genera with a range spanning at least a few consecutive bins, though I need to balance strictness against having enough sample size to work with.

For "small genera that grew greatly," I'm defining small as starting with 1-2 species and "greatly increased" as reaching at least 5 species total and quadrupling their initial count. For large genera peaking and declining, I'm setting a threshold around peak richness of 10+, requiring the peak to occur mid-range rather than at the start or end of their lifespan, with a notable drop-off before extinction — and I'm still calibrating what frequency counts as "often" for this pattern to hold.

To validate this isn't just a statistical artifact, I'm adding a permutation test: shuffling each genus's richness values across its occupied time bins while preserving duration, then checking if the observed proportion of hump-shaped trajectories exceeds what random reshuffling would produce at a 95th percentile threshold across many iterations.

I also want to add sampling sensitivity: restricting analysis to species with sufficient occurrence counts, which the taxonomic data appears to support.

Data volume should be manageable since the 1MB cap is about committed files, not the analysis itself — I'll fetch with checksums and avoid storing raw dumps. I need to check field structures with minimal limit=1 or limit=2 probes to understand species-level taxon naming without over-exposing individual record values beyond what's necessary.

I'm planning my six-request budget: first get field lists for a combined base_name query across major animal phyla (Brachiopoda, Bivalvia, Gastropoda, Trilobita, Cephalopoda, Anthozoa, Echinoidea, Crinoidea, Bryozoa, Ostracoda), then get rowcounts for species-rank records in that group, check extinct-only counts, verify offset/pagination works, and look at interval/appearance field documentation.

I should decide whether to use vocab=pbdb for readable field names versus the default compact names, and figure out whether the taxa/list endpoint defaults to accepted/valid taxa only or needs an explicit status filter.

I'm looking at the fields like parent name, extinction status, occurrence counts, and flags, and trying to figure out how to filter for only accepted species, excluding junior synonyms or nomen dubium entries. Some records seem to lack occurrence data entirely, like the Conularia entry, which complicates the filtering logic.

I'm wondering if there's a `taxon_status=valid` parameter I could test to simplify filtering instead of manually excluding flagged fields, and I should run a trial request to check the resulting row count. I also need to think about pagination strategy given the large total species count, likely using a reasonable limit with offset-based paging.

I've used about 7 requests now, slightly over my cap, so I should stop and note that I discarded some data. I'm also noticing an odd entry—Cladoporium, which looks like a fungus—showing up under what should be an Ostracoda/Anthozoa listing with valid status, which seems like a data inconsistency worth flagging.

Now I'm working out the filtering criteria: species-rank, valid status, with complete first/last appearance fields and no accessory flags, requiring a parent genus match. I'm defining first and last appearance ages as midpoints of the early/late bounds, then binning species into 10-Myr intervals from 0 to 540 Ma based on whether their age range overlaps each bin.

For genus-level trajectories, I'm requiring at least 3 occupied bins and at least 2 species per genus to be eligible, and working through how to classify extinction versus extant status while accounting for the Pull of the Recent bias when deciding which genera count as "disappeared" versus the full eligible set.

For Part A, I don't think extinction should be required—genera still growing today can still count—so I'll use all eligible genera for that analysis rather than filtering further, though I want to be careful about edge effects from genera starting at the oldest Cambrian bin. I'm defining the growth threshold as starting richness of 2 or fewer species, with a "growth event" meaning the peak richness reaches at least 5 and at least 4 times the starting value, simplifying the rule based on whether initial richness was 1 or 2.

I'm settling on "often" meaning the fraction of eligible genera showing a growth event should be at least 0.10, since most genera are monotypic and genuine growth to 5+ species seems like it would be fairly rare, maybe 10-15% among those starting with at least 2 species and spanning 3+ bins—though I'm uncertain about the exact number and don't want to overtune the threshold.

I should also require a minimum absolute count of at least 50 such events for it to be meaningful across the whole record, and test significance by permutation: shuffling richness within each genus's bins, recomputing the growth fraction, and checking whether the observed fraction exceeds the 95th percentile of 1000 permuted trials. I'm flagging a complication though—since the permutation changes which genera even qualify as "eligible" in the first place, since the starting richness S0 depends on the permuted sequence.

For the second pattern involving larger genera that peak and then vanish, I'm defining eligibility as genera with peak richness at least 10, spanning at least 5 bins, and going extinct without any surviving species, then checking whether the richness peak occurs in a middle bin (not the very first or last) and whether the final bin's richness drops to half or less of the peak.

Since the final bin typically captures only the last surviving species, S there is usually small relative to peak, so declining-to-disappeared would hold almost trivially for most extinct genera — meaning I need to check against a null permutation baseline too, requiring observed P_B to both exceed 0.50 and beat the null's 95th percentile, with at least 50 eligible genera for the test to be meaningful.

I'm settling on a unified "often" threshold of 0.20 for both criteria A and B, rather than tuning them separately, and defining the verdict so that a clear "supports" classification requires both to pass simultaneously in the primary analysis.

For "refutes," I'm setting the bar at either fraction falling below 0.05 or both parts failing to clear the null 95th percentile, with everything else landing as "mixed." I'm also flagging "inconclusive" cases where sample sizes are too small, data retrieval fails, or the retained species count falls short of 20,000.

I also need to flag taxon scope limits — the claim about genera in the fossil record isn't covered by terrestrial groups like plants, vertebrates, insects, or most microfossils, and genus-level species counts in PBDB are heavily shaped by taxonomic splitting effort rather than true richness, which is a real artifact to caveat. For the dataset citation I should note the PBDB license isn't confirmed in my records, so I'll mark it unverified rather than assume CC BY 4.0.

I'm also planning the actual fetch strategy: paginated taxa/list.json calls with a 5000-record limit across roughly 22 pages per base_name query, and I noticed that adding status=valid slightly reduces the count, which seems expected and fine to use.

For verification, I'll record retrieval timestamps and sha256 hashes per page, deduplicate records by oid, and require at least 99% of records_found to be captured since strict pagination ordering guarantees aren't fully confirmed. I'm also sorting out field logic — pulling the genus from the first word of nam when show=parent is used, defining extinction as last bin index ≥1 with no ext=1 species, and noting that Recent range-through species carry ext=1 and lea=0.

For the permutation null, I'm using seed 20261101 with numpy's default_rng to run 1000 permutations per eligible genus, shuffling species richness across bins within each genus's time span to compute the test statistic — checking that eligibility criteria for both conditions remain permutation-invariant or properly scoped to pre-permutation values.

I should handle edge cases where permuted richness series produce zero-richness gaps or an initial bin value of zero; I'll require S0≥1 for eligibility to keep things consistent with the actual data construction, treating rare zero-gap cases as acceptable. Time to write this up.

I pre-registered the test for `darwin1859-ch02-09` as a `result.json` with status `"preregistered"`. I ran no analysis, built no genus trajectory and committed nothing. The file passes `python3 -m json.tool`.

The layout is flat, with `test-data/`, `claim-sources/` and `scripts/` at the repo root and no `engine/` prefix.

**Run directory:** `test-data/claim-tests/darwin-origin/darwin1859-ch02-09/genus-richness-trajectories-pbdb-01/`

**Hypothesis:** Among well-sampled marine animal genera, (A) genera that start with 1–2 valid species often grow to many, and (B) extinct genera that become large (10 or more species) often peak and then decline before vanishing. Both patterns must be more frequent than when the same genus's richness values are shuffled in time.

The data are PBDB `taxa/list.json` species records for ten groups: brachiopods, bivalves, gastropods, trilobites, cephalopods, corals, echinoids, crinoids, bryozoans and ostracods. Species richness per genus is counted per 10-Myr bin using range-through counts.

- **Pass:** Parts A and B each have at least 50 eligible genera, an event fraction of at least 0.20, and a fraction above the 95th percentile of 1000 within-genus time shuffles. Both parts must also pass when only species with at least 2 occurrences are kept.
- **Fail:** Refuted if both parts fail, meaning a fraction below 0.05 or not above the shuffle null. Mixed covers every other outcome with adequate n. Inconclusive means fewer than 50 eligible genera in a part, fewer than 20,000 retained species, or fetched records below 99% of PBDB's `records_found`.

**Doubts about operationalization**
- "Often" has no number in Darwin. I fixed 0.20 as the pass level and 0.05 as the floor from the word's plain meaning, along with the other cut-offs.
- Range-through counts make genera rise and fall by construction, and singleton species get short ranges. The shuffle null and the 2-occurrence check only partly address this. I did not pre-register proper occurrence-based subsampling, because the taxa endpoint has no per-collection data and the occurrences endpoint is too large for a first test.
- Part B is probably easy to pass, since large extinct genera usually end small. Part A and the shuffle null are where the test can discriminate. The file says this, along with my prior expectation that clades commonly rise and fall.
- The scope is a shelly marine subset, not "genera in the fossil record" as a whole. Plants, vertebrates and insects are excluded, and genus size reflects taxonomic effort as well as true richness.
- The three assessors disagree on adequacy (0.67, 0.85 and 0.54), mostly about sampling bias. The file notes this.

**REPORT**
- **Dataset:** The PBDB dataset can hold the needed variables. The scout's per-genus fields are not enough on their own, so I used species-rank records with first and last appearance ages, `noc` (occurrence count), `ext` (extant flag) and the parent genus name `prl`. I did not use the Dryad datasets (about 1 GB), Neotoma (late Cenozoic only) or WoRMS (no time dimension).
- **Metadata checks:** About 7 requests (the cap was about 6). Species counts were 108,472 for the ten groups, 108,019 with `status=valid`, 96,115 of those extinct, and 36,668 genera. The results show a 2000-record page is about 413 KB.
- **What I looked at:** I saw only the first record from three `limit=1` requests, and one 2000-record page went to `/dev/null` unread. The file records both.
- **Licence:** PBDB's licence is null in the scout record and unverified, so the file leaves it null with a note to record it at fetch time.
- **Fetch size:** The full fetch is about 22 pages of tens of MB, so the files should not be committed. Only the script and checksums go in the repo.
- **Agent model:** I recorded the agent model as `claude-sonnet-5-5`, matching the scout record.
- **Untracked folder:** Git also shows an untracked `darwin1859-ch04-26/` folder in the same directory. It is not mine.

_Tools used: Read ×3, Shell ×8, UpdateCurrentStep ×2, Write_
