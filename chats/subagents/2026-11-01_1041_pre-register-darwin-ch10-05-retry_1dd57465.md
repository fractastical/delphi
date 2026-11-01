# Subagent: Pre-register darwin ch10-05 retry

- **Parent chat:** [do we need to go rhough and validate more of the claims ? we should have another](../2026-10-31_2254_do-we-need-to-go-rhough-and-validate-more-of-the-claims-we-s.md)
- **Started:** 2026-11-01 10:41 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 11:15 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** unknown
- **Transcript ID:** `1dd57465-a025-475f-8fca-01840021086c`

---

### 2026-11-01 10:41 — Turn 1 (User)

> Repo: /Users/jdietz/Documents/GitHub/dev/delphisci (flat layout: test-data/, claim-sources/, scripts/ at the repo root; if that is not the case, look for an engine/ prefix, and tell me which). Your job: PRE-REGISTER one data test for claim `darwin1859-ch10-05` (Darwin, Origin of Species). A previous attempt failed on connection errors and wrote nothing, so write the file early and refine it. Do NOT run the analysis and do NOT look at any data values.
> 
> Read first: test-data/claim-tests/README.md (rules and result.json schema, including test_contract), test-data/dataset-scouting/darwin-origin/darwin1859-ch10-05/datasets.json (the scout's record: which open dataset holds the variables), the claim in claim-sources/darwin-origin/claims.json, and the dataset-resolvability assessments for this claim under claim-sources/darwin-origin/assessment/raw/*/ (grep for the claim id) for the proposed operationalization. Other pre-registrations in this batch to match in style: test-data/claim-tests/darwin-origin/darwin1859-ch10-10/pbdb-cenozoic-balance-01/result.json and darwin1859-ch04-26/pbdb-survival-01/result.json; also `git show ed505563 --format=` for the original worked example. Do not duplicate their tests: this claim is about genera and families existing CONTINUOUSLY from first to last appearance (no gaps in the range), so design a distinct test on its own wording.
> 
> Write exactly one file: test-data/claim-tests/darwin-origin/darwin1859-ch10-05/<short-run-name>-01/result.json with status "preregistered", hypothesis, pass_criterion, fail_criterion (include mixed and inconclusive rules and minimum n), planned_datasets, datasets (id, name, landing_url, doi/version/license as verified in the scout record, null if unverified; download_url and the exact API query or file to fetch; do not invent anything), test_contract (all four fields), interpretation (how Darwin's terms map to measurable quantities; flag modern reinterpretation; state what the test does not cover), caveats (state honestly what you inspected before registering and any prior knowledge of the likely outcome), created date from `date -u`, and agent {kind:'cursor-subagent', model:<your model id>, run:'prereg-darwin-batch-1-retry', date}. Thresholds must be numeric and fixed now, not tuned to an expected result. Metadata-only requests (field lists, record counts, HEAD) are allowed; cap about 5 requests; if a request fails, do not retry more than once and note it; never download over 1 MB; never compute the statistic.
> 
> Hard rules: write only that one result.json (create the directories); do not edit claim files, assessments, nanopubs, docs/, or scouting records; do not git commit or push; never sign or publish anything. Validate with python3 -m json.tool. Final response: the run directory path, the hypothesis, pass/fail criteria in two lines each, and doubts about operationalization.

**Assistant:**

I'm thinking through the test design around PBDB occurrence data—since genus-level downloads could be too large to commit (over the 1MB cap), I should plan to fetch the data fresh at run time rather than storing it in the repo.

I'm weighing how to quantify sampling gaps: distinguishing genera actually sampled in a stage bin versus those merely implied present by range-through, with the unsampled-but-implied cases serving as a proxy for Lazarus-style gaps. For a concrete test I'm considering genera with enough occurrences, counting internal zero-occurrence stage gaps within their sampled range, and comparing against a null model where presence is continuous but detection per stage follows some probability derived from the genus's own occurrence pattern.

Now I'm sketching the actual data pull: fetching PBDB occurrences at the genus level for a fixed, well-sampled set of marine invertebrate classes (trilobites, brachiopods, bivalves, gastropods, anthozoans, cephalopods, crinoids) rather than downloading the whole Animalia dataset, since that's too large. Then I'd define the metric around genera with enough occurrences and stage-bin spread, counting the interior stage bins between first and last occurrence with no sampling as the gap measure.

For the null expectation, I'm weighing options between bin-specific sampling probabilities versus a simpler multinomial reshuffling approach -- redistributing each genus's occurrences randomly across its own observed stage range to see how often empty interior bins arise by chance alone, as a test of whether apparent gaps are just a sampling artifact rather than real absences.

I'd count empty interior bins within the fixed range and compare aggregated observed versus expected excess emptiness, but I realize this null is conservative since genus-specific abundance clustering (not just collection density) would inflate empty bins beyond what collection-weighted sampling predicts. I should reconsider the pass criterion in terms of what Darwin's gradualism claim actually requires.

Family-level sibling presence doesn't really settle genus absence, so I need a cleaner test. I'll frame it as a primary measure: for genera, the fraction of interior bins with no occurrence (ghost gaps), compared against the null expectation from a weighted multinomial continuity model, and judge Darwin's claim supported if the observed rate roughly matches that null.

Though a strict O/E ratio threshold feels arbitrary since genus occurrences naturally cluster, pushing ratios above 1.5 regardless of true gappiness. A more defensible version uses collection-count weights per class/bin for the null rather than raw occurrence counts, which better accounts for lumpy sampling. I'll apply the same logic at the family level, deriving family identity from each occurrence's class field so families get analogous gap statistics.

For practical implementation I'd pull occurrences per class with class and basic fields (including early/late age), restrict to marine environments, and pick a manageable set of six classes -- Trilobita, Brachiopoda, Bivalvia, Gastropoda, Cephalopoda, Anthozoa -- to keep download sizes reasonable while still covering diverse clades. Bin definitions would need to reference PBDB interval IDs or ICS stages, though I'm not actually running these queries myself.

Actually, maybe safer to pull the documentation page instead, since that describes the API without returning actual occurrence data. I'll draft a plan file first, then make a handful of careful requests.

I should draft the output file first before refining further requests. For binning, I'm planning to use ICS stage-level intervals from PBDB's interval list covering the Phanerozoic, assigning each occurrence to a stage only when its age range fully falls within that stage's bounds, otherwise marking it unresolved.

For taxa, I need to work out genus-level groupings from the occurrence data using the genus field returned by the class-level API query, excluding blank or informally resolved genus names, while flagging any uncertainty about exact column naming to verify against documentation. Then I'm defining the criteria for qualifying genus sets—requiring at least six stage-resolved occurrences spread across at least three distinct bins with a minimum temporal span between first and last bin.

Now I'm extending this to families, requiring at least ten occurrences across at least three bins with the same span threshold, and sketching the null model: for each qualifying unit I'd compute the number of empty interior bins between first and last occurrence, then simulate 2000 replicates drawing occurrences by random sampling weighted by overall class-level sampling intensity per bin, counting simulated empties on the same interior bins for comparison.

I'm refining the null to force one occurrence at each endpoint bin and distribute the remaining occurrences across all span bins, which seems like the more accurate approach. I'll aggregate observed versus expected empty-bin counts across all units within a rank to get a pooled ratio and also compute an absolute per-bin empty rate.

Given the clustering of genera within families, I should use a cluster bootstrap that resamples at the family level rather than treating genera as independent, running around 10,000 resamples. For the actual test, I'm defining the ratio threshold for Darwin's continuity claim—roughly R ≤ 1.25 as a pass with an upper bootstrap bound near 1.5, failing if the ratio clearly exceeds that.

I also want a stricter "well-sampled absence" criterion: flag a gap as meaningful only when the null probability of failing to detect that unit in an empty bin is low, computed from the per-bin detection probability under a multinomial model, then count the fraction of units with at least one such well-sampled-empty bin to see if it exceeds what continuity would predict.

I'm settling on two primary statistics: R, the excess ratio of gaps relative to expectation, as the main test at the family level with genus-level as a co-primary check, and H, the fraction of unit-ranges containing at least one well-sampled empty bin, as the absolute criterion for "disappear and reappear" claims—tentatively requiring H_family ≤ 0.10, though I'm unsure this threshold is well justified.

I'll simplify: let H serve only as descriptive context rather than a hard pass criterion, keeping the verdict based on R for both ranks plus a permuted negative-control check. For failure, I'm leaning toward requiring that the bootstrap 95% lower bound of R exceed 2.0 alongside a point estimate ≥2.0, applied to the family- and genus-level claims specifically.

I should also mark it inconclusive if too few families/genera pass the filters, if PBDB can't be reached, if the expected gap count is too low for statistical power, or if there aren't enough usable stage bins — I'll set a minimum threshold like 30 expected gaps and 20 bins. For the data pull itself, I'm planning queries against the PBDB occurrence list endpoint filtered by class, marine environment, and genus-level taxonomic resolution, alongside interval data and checking license fields.

With only five requests available, I'll spend the first few confirming the CC0 license via a datainfo-only call, then pull interval names, then check field documentation — before writing up the draft.

Nothing's written yet, so I'll start by using the Write tool to create the skeleton file.

Now the metadata requests (record count and licence, interval list, field docs).

I'm noting the default fields returned include age bounds and accepted name/rank, with roughly 760,260 records potentially around 150MB, and that genus/family lookups will need the class parameter added. For intervals, I'm unsure about the "level" parameter, so I'll try querying the intervals list endpoint with scale and age range options to see what comes back.

_Tools used: Shell ×8, UpdateCurrentStep, Write_
