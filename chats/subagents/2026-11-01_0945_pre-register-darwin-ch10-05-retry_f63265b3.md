# Subagent: Pre-register darwin ch10-05 retry

- **Parent chat:** [do we need to go rhough and validate more of the claims ? we should have another](../2026-10-31_2254_do-we-need-to-go-rhough-and-validate-more-of-the-claims-we-s.md)
- **Started:** 2026-11-01 09:45 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 10:09 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `f63265b3-999b-4f3b-96fb-3fe0ab6bcd8e`

---

### 2026-11-01 09:45 — Turn 1 (User)

> Repo: /Users/jdietz/Documents/GitHub/dev/delphisci (flat layout: test-data/, claim-sources/, scripts/ at the repo root; if that is not the case, look for an engine/ prefix, and tell me which). Your job: PRE-REGISTER one data test for claim `darwin1859-ch02-11` (Darwin, Origin of Species). Do NOT run the analysis and do NOT look at any data values.
> 
> Read first: test-data/claim-tests/README.md (rules and result.json schema, including test_contract), test-data/dataset-scouting/darwin-origin/darwin1859-ch02-11/datasets.json (the scout's record: which open dataset holds the variables), the claim in claim-sources/darwin-origin/claims.json, and the dataset-resolvability assessments for this claim under claim-sources/darwin-origin/assessment/raw/*/ (grep for the claim id) for the proposed operationalization. A good worked example of a pre-registration is `git show ed505563 --format=` (test-data/claim-tests/thompson-growth-form/thompson1917-ch02-03/limb-bone-pgls-01/result.json): copy its depth and style.
> 
> Write exactly one file: test-data/claim-tests/darwin-origin/darwin1859-ch02-11/<short-run-name>-01/result.json with status "preregistered", hypothesis, pass_criterion, fail_criterion (include mixed and inconclusive rules and minimum n), planned_datasets, datasets (id, name, landing_url, doi/version/license as verified in the scout record; download_url and the exact API query or file to fetch; do not invent anything), test_contract (all four fields), interpretation (how Darwin's terms map to measurable quantities; flag modern reinterpretation; state what the test does not cover), caveats (state honestly what you inspected before registering, e.g. field names/headers/record counts only, and any prior knowledge of the likely outcome), created date from `date -u`, and agent {kind:'cursor-subagent', model:<your model id>, run:'prereg-darwin-batch-1', date}. Thresholds must be numeric and fixed now, chosen from the claim's own wording and conventional statistics, not tuned to an expected result. You may make metadata-only requests (API field lists, record counts, HEAD requests) to confirm that the planned fetch works; cap about 6 requests; never download over 1 MB; never compute the statistic. If you find the planned dataset cannot hold the needed variables, say so in a REPORT note inside your final response and still write the best honest pre-registration, or say it should be dropped.
> 
> Hard rules: write only that one result.json (create the directories); do not edit claim files, assessments, nanopubs, docs/, or scouting records; do not git commit or push; never sign or publish anything. Validate that the file parses as JSON (python3 -m json.tool). Final response: the run directory path, the hypothesis, the pass/fail criteria in two lines each, and any doubts about operationalization.

**Assistant:**

I'm checking the BOLD API's summary endpoint with a genus-level query and field filters, planning a handful of test requests to verify the extent_limit behavior before downloading data.

Now I need to design a feasible sampling plan: pick genera within Insecta using a deterministic rule, but genus size estimation is tricky since BINs are circular with distance (they're defined by clustering thresholds), so I should instead use named species counts per genus as a size proxy and compute nearest-neighbor distances between representative sequences, while being careful that sequencing effort doesn't confound the distance estimates.

I'm thinking through how to query BOLD's API to get per-genus species counts — testing summary queries with different fields and taxonomic scopes to see what shape of data comes back before settling on a fixed sampling cap per species.

That was species metadata, not a statistic—I should note Carabus shows around 890 species entries. I've used 3 requests already, so I'm being careful about remaining calls as I test whether the query syntax supports combining genus and marker filters like "tax:genus:Carabus,marker_code:COI-5P".

I'm uncertain about the exact AND query syntax, so rather than spend another request experimenting, I'll just filter by marker_code client-side once I have the TSV data, saving my last request for something more useful.

Good, the download endpoint works with full extent. Now I'm designing a feasible test using genus as the unit, restricting to COI-5P barcode data in Insecta rather than trying to cover plant markers like rbcL/matK.

For enumerating genera, the BOLD summary endpoint doesn't seem to support a genus field directly, so I'm weighing alternatives — using Open Tree of Life's taxonomy API to pull genus children from a family subtree, versus pre-registering a fixed, seeded-random sample of families and genera to avoid any appearance of tuning the selection after seeing results.

To keep downloads manageable, I'll cap sequences per species at 3 and limit genus selection by specimen count. For genus size I need an independent measure separate from the barcode sampling itself, so species counts should come from OTT taxonomy rather than from how many species happen to have qualifying BOLD sequences — otherwise the statistic would be confounded with sampling effort.

Now I'm defining the actual metric: genus size from OTT's accepted species count, paired with an outcome measuring the mean nearest-neighbor congener p-distance across a sampled subset of sequenced species (capped at 10, minimum 4). I still need to settle how to compute pairwise distances given that BOLD sequences may be unaligned, with gaps in the nucleotide field — leaning toward a simple p-distance approach rather than something like Kimura 2-parameter, keeping tooling to plain Python/numpy.

I'm weighing whether to require MAFFT alignment via subprocess versus a gapless comparison requiring a minimum overlap of unambiguous sites, since COI-5P sequences are nearly gapless and introducing an external aligner adds a dependency risk if it's unavailable.

I also need to control for sampling bias: nearest-neighbor distance shrinks mechanically as more species are sampled, so I'll fix a subsample size of exactly 8 sequenced named species per genus (seeded, requiring at least 8 available) to keep comparisons on equal footing, restricting the analysis to genera with ≥8 barcoded species.

But this raises a subtler issue — with random subsampling, NN distance within larger genera would actually be biased larger (sparser draws from more species), working against Darwin's claim, whereas mean pairwise distance among the sampled 8 is unbiased with respect to sampling fraction since it's just averaging random pairs. So I'll switch to using mean pairwise p-distance among the 8 randomly drawn species per genus, repeated across 20 seeded draws and averaged, picking one representative sequence per species via a seeded random choice when duplicates exist.

I need to account for genus age as a confound, since older genera may be both larger and more divergent, biasing toward a spurious negative relationship. I'll test this with an OLS regression of mean pairwise distance on log10(species count) including family fixed effects, bootstrapping the slope's confidence interval over 10,000 resamples of genera, and treating the claim as supported only if the upper bound of that CI is negative alongside a consistent within-family Spearman correlation.

I'll settle on refutes being a positive point estimate or a CI that doesn't exclude zero at adequate sample size (n≥40 genera), treating a null result as a pre-registered failure of the "always" claim rather than letting ambiguous middle cases slide.

Mixed outcomes need their own bucket too: negative slope but CI crossing zero, or CI below zero but weak magnitude, or disagreement between primary and secondary metrics. Inconclusive cases are ones with too few genera, families, or barcoded species, or missing tools like MAFFT, or sparse large-genus bins—and I still need to pin down exactly how genus size S should be defined, since OTT's child counts aren't fully reliable and I may need to fall back on counting distinct named species directly from BOLD.

I've used up my budget of verification requests, so I'll settle on OTT as the primary source for S since it was already confirmed to work, with BOLD named-species counts as a documented fallback if OTT's child enumeration fails, noting that deviation explicitly rather than trying to verify GBIF as another option.

For genus selection I'm choosing eight families with strong BOLD coverage and spread across Coleoptera, Lepidoptera, and Hymenoptera -- Carabidae, Curculionidae, Noctuidae, Geometridae, Formicidae, Tortricidae, Chrysomelidae, and Cerambycidae -- and I should disclose that any specific counts I cite from memory, like Carabus species numbers, come from prior knowledge rather than fresh verification.

I'm setting the inclusion criteria as at least eight named species with COI-5P sequences of 500+ bp, using log10 of species count as the genus-size metric, seeding the RNG at 20261101, and running 100 random draws of eight-species subsets averaged together, while deciding how to cap downloads for very large genera like Agrotis so the analysis stays manageable without excluding them outright.

I'm pre-registering that differences should be treated as a relative comparison rather than absolute, and thinking about how to operationalize Darwin's claim by contrasting top-tercile versus bottom-tercile genera by species richness while keeping the main analysis descriptive. I'm also flagging caveats around genetic distance not equaling morphological divergence, taxonomic lumping/splitting circularity, and genus age as a confound to note but not control for, plus setting minimum sample requirements like needing genera spread across several families with enough high-richness and low-richness genera represented.

For power, I'm settling on requiring at least 40 genera spanning 5+ families with a large spread in richness, otherwise declaring the test underpowered. I'm specifying the regression approach with family fixed effects, genus-within-family clustered bootstrap, and a threshold combining a negative confidence interval with a within-family rank correlation computed on family-demeaned residuals of distance and log richness.

I don't have a strong prior here—genuinely uncertain whether larger genera show older or younger divergences, so I'll state that honestly rather than fake confidence.

Now I'm drafting the JSON metadata: marking BOLD license as null with a note that its data policy wasn't verified, confirming the Open Tree taxonomy version while leaving DOI null, and documenting the query/download URL pattern along with the distinction between default and full-extent queries.

I'm also noting edge-case query behaviors I observed — an empty summary when filtering by genus field, Carabus returning hundreds of provisional species names, and marker filters needing semicolon versus space handling, which means I'll filter client-side instead. For the final metadata, I'll use today's date and the correct model identifier before writing everything out.

This could be a race condition since these run in parallel, so I should retry.

I wrote the pre-registration for `darwin1859-ch02-11`, status `preregistered`, and `python3 -m json.tool` parses it. The layout is flat, with no `engine/` prefix. I did not run the analysis or compute any statistic. I wrote only this one file and did not commit, sign or publish anything.

**Run directory:** `test-data/claim-tests/darwin-origin/darwin1859-ch02-11/bold-congener-distance-01/` (the file is `result.json`)

**Hypothesis:** In insect genera, the mean pairwise COI-5P distance among congeneric species falls as genus size rises (log10 of the species count in the Open Tree taxonomy OTT 3.7), within families. The outcome is the mean over 100 seeded draws of 8 barcoded named species per genus. I used 8 species in each draw so that the distance doesn't depend on how many species were barcoded.

**Pass:**
- The family-fixed-effects OLS slope of distance on log10(genus size) is negative, and its 95% stratified-bootstrap CI (10,000 resamples within families) lies entirely below 0.
- The family-adjusted Spearman correlation is at most −0.20.

**Fail:**
- The slope's point estimate is 0 or above, or its CI lies entirely above 0.
- The result is `mixed` if the slope is negative with a CI that includes 0, or if the CI is below 0 but the correlation is above −0.20.
- The result is `inconclusive` if:
  - fewer than 40 genera have at least 8 barcoded named species;
  - fewer than 5 families contribute at least 3 qualifying genera each;
  - the largest genus is less than 10 times the smallest;
  - BOLD or Open Tree can't be queried;
  - no aligner is available.

**Notes on the dataset:**
- BOLD works for the genetic route. It supplies genus, species and `marker_code` per specimen, and the download with `extent=full` gave `extent_limit: null`. It can't list genera, because a `fields=genus` summary on a family returned `{}`, so Open Tree supplies the genus list and sizes.
- BOLD's combined taxon-and-marker query failed (HTTP 500 with `;`, `{}` with a space), so the marker filter is applied client-side.
- I did not test `POST /v3/taxonomy/taxon_info` with `include_children` on Open Tree, so the genus-size route is unverified. The file records a fallback: genus size from BOLD's clean-binomial species count, written up as a weaker test.
- Plants are not covered. COI isn't a plant barcode and TRY needs registration. Morphology isn't covered either, and the "resemble varieties" half of the claim isn't tested.
- BOLD and Open Tree licences are `null` in the file, because the scout record gives none and I didn't verify any.

**What I inspected:** six metadata requests, all of a few KB or less. One BOLD summary for *Carabus* returned 890 species and 4,003 specimens, plus a per-species count dictionary that I did not examine. No sequences, no Open Tree counts, no distances.

**Doubts about operationalization:**
- COI distance is not the morphological difference Darwin meant.
- Requiring 8 barcoded species excludes small genera, so the contrast is between medium and very large genera.
- Genus size and delimitation are taxonomic judgments, so splitting practice can build the association into the data.
- Genus age is unresolved. Older genera are both larger and more divergent, which pushes the slope positive. The Open Tree age covariate is descriptive only.
- The numeric thresholds, the families (the file lists them) and the draw settings are my choices, made now and not tuned. I have no firm expectation of the outcome.
- This is not a REPORT-level problem. BOLD can hold the needed variables, so the test should not be dropped.

_Tools used: Read ×3, Shell ×11, UpdateCurrentStep ×2, Write_
