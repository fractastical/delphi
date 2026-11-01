# Single agent (prompt chain) vs swarm: Aristotle, *History of Animals* Book VI

One slice, one run of each arm. Treat the numbers as a pilot, not a benchmark (see Limits).

## What was compared

Task: extract the major claims of *History of Animals* Book VI (`inputs/ha.txt` lines 927-1186, 18,611 words;
generation in birds, fishes and viviparous animals), then assess each claim's dataset resolvability on
`assessment/rubric.json` (dataset-resolvability/0.2.0).

| | Swarm (existing) | Single agent chain (this run) |
|---|---|---|
| Extraction | one extractor agent for this book (`extraction/D-ha-06.json`) | one agent, same `extraction/INSTRUCTIONS.md` |
| Verification | extractor re-checks its own quotes | deterministic script, `verify-extraction.mjs` |
| Assessment | separate assessor agents on other models: GPT-5.6 Sol and Grok 4.7 in the merged data (Gemini 4 Argon finished batch 1 only and is not in `assessments.json`) | the same agent, from the blinded batch fields only, same rubric and field rules |
| Validation | `merge-assessments.mjs` (schema, scores, weights, URL resolution) | `validate-assessments.mjs`: same checks plus verdict-versus-score bands |
| Model | extractor model not recorded in the repo (the builder is Claude Opus 5.5 per `generate-assessments.mjs`); assessors GPT and Grok | Claude Sonnet 5.5 for every stage |

The chain: read the book, `stage1-draft.json` (claims with quotes, no line numbers), `verify-extraction.mjs`
(fills in section and line, fails on any non-verbatim quote), `stage3-batch.json` (same fields as the
swarm's `make-batches.mjs`, no triage or candidate data), `stage3-assessments.json`,
`validate-assessments.mjs`, then this comparison. All files are in `single-agent/`; `FROZEN.sha256` holds
their hashes, taken before the swarm's Book VI extraction and assessments were opened.

Blinding: the single agent did not read the content of `extraction/D-ha-06.json`, `claims.json`,
`assessment/raw/` or `assessment/assessments.json` until its outputs were frozen. It did see, while
orienting, the swarm's claim counts per file and per book (42 for Book VI, from `worklist.tsv` ids and a
per-file count of `extraction/*.json`), the first rows of `worklist.tsv` (Book I, a different slice), and
the file names of the swarm's outputs. It therefore knew the swarm's target size but not its claims or scores.

Claims were matched across the arms by content, by hand (`match.json`: 23 same proposition, 4 partial).
Both runs number their claims `aristotle-ha06-NN`, so an id does not identify the same claim in the two runs.

Reproduce: `node verify-extraction.mjs single-agent/stage1-draft.json single-agent/stage2-claims.json`,
`node validate-assessments.mjs single-agent/stage3-batch.json single-agent/stage3-assessments.json single-agent/stage4-validated.json single-agent/stage4-dropped.json`,
`node compare.mjs` (writes `comparison.json`).

## Extraction

| | Swarm | Single |
|---|---|---|
| Claims | 42 | 43 |
| Claims per 1,000 words | 2.26 | 2.31 |
| Quotes verbatim on the stated line | 42 / 42 | 43 / 43 (first pass, enforced by script) |
| Paragraphs with a claim (of 147) | 40 | 38 |
| Birds (25% of the words) | 13 (31%) | 10 (23%) |
| Fishes and marine mammals (31%) | 18 (43%) | 12 (28%) |
| Land viviparous animals (44%) | 11 (26%) | 21 (49%) |
| Claims with a number in them | 7 | 13 |
| Extractor triage `testable-with-existing-data` | 40 / 42 | 30 / 43 |

- Overlap is modest: 27 of the claims match (23 same, 4 partial); 15 are swarm-only and 16 single-only. Jaccard
  0.47 counting partial matches, 0.37 counting only same-proposition matches.
- The swarm's extractor put 11 claims on the land mammals, 26% of its claims from 44% of the text. It has no
  claim giving a gestation, lifespan or litter figure for the horse, cattle, dog, elephant or lion, which are
  among the most checkable statements in the book. The single agent's split follows the text closely. Swarm-only claims are mostly Aristotle's explanations and
  generalizations that the single agent skipped (blinded swallow chicks, the cuckoo not being a transformed hawk,
  eels' 'earth's guts', fishes not interbreeding, fish embryos' eyes first, `Erythrinus` and `channa` always
  pregnant, deer and horse sex-differences in lifespan, nourishing yolk).
- Both readings are allowed by `extraction/INSTRUCTIONS.md`: it asks for "the generalization over the
  catalogue" and also for single-animal facts that are "concrete enough to check (counts, sizes, durations)".
  The swarm's extractor leaned to the first, the single agent to the second. Which reading an extractor takes
  is a source of variation that one run per arm cannot separate from the effect of the arm.

## Assessment (27 matched claim pairs)

Scores are rubric-weighted overalls in [0,1]; verdicts are the rubric's four.

| | Value |
|---|---|
| Single vs mean of GPT and Grok: Pearson r / mean abs. difference / bias | 0.69 / 0.079 / -0.043 |
| Single vs GPT: r / MAE | 0.58 / 0.115 |
| Single vs Grok: r / MAE | 0.70 / 0.079 |
| GPT vs Grok on all 42 swarm claims: r / MAE | 0.80 / 0.109 |
| Same-proposition pairs only: single vs swarm mean r / MAE | 0.78 / 0.075 |
| Verdict identical: single = GPT / single = Grok / GPT = Grok | 59% / 59% / 56% |
| Verdict within one step of each assessor | 100% |
| Verdict identical to both assessors | 37% (10 of 27) |

Mean overall on all claims: single 0.70, GPT 0.77, Grok 0.67. Verdicts (resolvable-now / partially / needs-new-data):
single 21 / 19 / 3, GPT 26 / 15 / 1, Grok 16 / 24 / 2. Nobody used `not-empirically-resolvable`.

- The single agent's scores sit between the two swarm assessors and track them about as well as they track
  each other (single vs Grok r 0.70 against GPT vs Grok 0.80, on different claim sets). On verdicts it
  agrees with an assessor as often as the assessors agree with each other.
- Largest gaps (single vs swarm mean): spontaneous generation of fishes (single 0.49, GPT 0.81), milt
  sprinkling (0.59 vs 0.89), smooth-shark placenta (0.61 vs 0.85), cuckoo (0.68 vs 0.87): the single agent
  scored the textbook-but-hard-to-pin-down claims lower. The reverse: only the sheat-fish guards eggs (single
  0.85, both assessors 0.62), because a universal "only" claim is refuted by FishBase's reproductive guilds.
- Spread: single sd 0.15, GPT 0.13, Grok 0.13; the single agent used more of the range (three `needs-new-data`
  verdicts with data-existence at or below 0.30, against one and two).
- Confidence is not comparable: mean 0.69 (single), 0.87 (GPT), 0.76 (Grok).
- Triage honesty: the swarm extractor marked 40 of 42 claims testable with existing data; its assessors
  agree on the verdict for 26 (GPT) and 17 (Grok) of them. The single agent's own triage matches its own
  verdict for 33 of 43. Part of that is the single agent having assessed claims it wrote; see Limits.

## Dataset references

| | Single | GPT | Grok |
|---|---|---|---|
| References proposed for the 42/43 claims | 53 | 75 | 72 |
| Claims with no dataset | 7 | 0 | 4 |
| Dropped by the URL check | 11 | 3 | 10 |
| Reason | all HTTP 403 (FishBase 9, GBIF 2) | all HTTP 403 (GBIF 3) | all network time-outs |

None of the dropped references was a 404 or an unresolvable DOI in either arm. The 403s are sites refusing
the checker's request (FishBase and GBIF both exist), and Grok's were time-outs at run time, so the "dropped"
counts measure the checker, not invented datasets. The single agent proposed fewer references per claim (1.2
against 1.8 and 1.7) and left seven claims empty where it could not name an open dataset (for example
veterinary schedules held in textbooks).

## Replication with two more models (three single-agent arms vs the swarm)

To separate "one agent vs many" from "which model", the same chain (same scripts, instructions and blinding
rules) was run alone on Book VI by [Claude Opus 5.5](3cdcfdde-dda9-4cf7-ab1d-2ba9a50a5908) and
[GPT 5.6 Sol](a342506b-fb71-4cc0-8dbe-769997cc1d95), as separate runs under `arms/`. Both reported no
forbidden content seen. Claims are matched by `compare-arms.mjs`, a deterministic matcher (same paragraph,
greedy one-to-one on quote plus claim word overlap). It reproduces 24 of the 27 hand matches in `match.json`
with no false ones, so it understates overlap; the order of the arms is the same at thresholds 0.45, 0.35 and
0.30. Numbers: `comparison-arms.json`.

| | Swarm | Sonnet 5.5 | Opus 5.5 | GPT 5.6 Sol |
|---|---|---|---|---|
| Claims | 42 | 43 | 40 | 37 |
| Verbatim quotes | 42 | 43 | 40 | 37 |
| Birds / fishes+marine / land | 13 / 18 / 11 | 10 / 12 / 21 | 12 / 16 / 12 | 13 / 12 / 12 |
| Claims with a number | 7 | 13 | 11 | 18 |
| Mean overall score (sd) | GPT 0.77 (0.13), Grok 0.67 (0.13) | 0.70 (0.15) | 0.63 (0.14) | 0.77 (0.13) |
| Resolvable-now / partial / new-data | GPT 26/15/1, Grok 16/24/2 | 21 / 19 / 3 | 14 / 24 / 2 | 11 / 22 / 4 |
| Datasets per claim (claims with none) | GPT 1.8 (0), Grok 1.7 (4) | 1.2 (7) | 1.0 (12) | 0.9 (5) |
| Dropped references | GPT 3, Grok 10 | 11 | 1 | 2 |
| Run time (tool time) | not recorded | about 4 min after reading | 7.5 min, about 20 calls | 2 min, about 27 calls |

Dropped references: HTTP 403 for Sonnet and Opus (FishBase, GBIF), connection refused for GPT (eChickAtlas).
The swarm's were 403s (GPT) and time-outs (Grok). No arm had a 404 or an unresolvable DOI.

Pairwise agreement on matched claims (overall score; verdict agreement counts each assessor separately for the swarm):

| Pair | Matched | Jaccard | Pearson r | Mean abs. diff | Verdict identical |
|---|---|---|---|---|---|
| Swarm vs Opus | 31 | 0.61 | 0.84 | 0.090 | 71% |
| Swarm vs Sonnet | 24 | 0.39 | 0.78 | 0.078 | 63% |
| Swarm vs GPT | 13 | 0.20 | 0.57 | 0.091 | 50% |
| Sonnet vs Opus | 20 | 0.32 | 0.82 | 0.065 | 70% |
| Sonnet vs GPT | 15 | 0.23 | 0.35 | 0.106 | 47% |
| Opus vs GPT | 15 | 0.24 | 0.06 | 0.124 | 40% |

Every pair was within one verdict step on every matched claim. With 13 to 31 matched claims per pair, the
correlations are rough.

What this shows:

- **Extraction coverage follows the model.** The Opus single-agent run overlaps the swarm's extractor much more
  (Jaccard 0.61) than either other single-agent run does (0.39, 0.20) and more than any two single-agent runs
  overlap each other (0.23 to 0.32). That fits the swarm's extractor being a Claude model close to Opus, which
  the repo does not record, but it is not proof. The earlier gap on the land mammals (swarm 26% of claims,
  Sonnet 49%) is a reading difference between models: Opus (30%) and GPT (32%) sit between them.
- **Scoring level follows the model, not the role.** GPT's mean overall is 0.77 both as a swarm assessor and as
  a single agent; the Claude single-agent runs are lower (0.70, 0.63) and Grok is 0.67. GPT's verdicts are the
  most generous in both arms (26 of 42 and 11 of 37 are resolvable-now, however, so counts are not a clean
  measure of generosity because the claim sets differ).
- **GPT's single-agent run is the outlier.** It chose mostly numeric life-history facts (18 of 37) and its
  scores correlate weakly with the other runs on shared claims (r 0.06 to 0.57, n 13 to 15), even though GPT is
  also a swarm assessor. Its agreement with the swarm's own GPT assessor was not computed separately and is
  worth checking.
- **The spread between single-agent runs is as large as the single-versus-swarm gap.** The Sonnet-to-swarm
  gap found earlier (r 0.78, 63% identical verdicts, Jaccard 0.39) is no worse than Sonnet against Opus or against
  GPT. Nothing here favours the swarm on extraction or score agreement; nothing favours a single agent either.
- **Swarm claims reached by the single agents:** of the swarm's 42 claims, 10 were reached by all three
  single-agent runs, 13 by two, 12 by one and 7 by none: the chick forming from the white and nourished from
  the yolk, very few birds breeding in their first year, the cuckoo not being a transformed hawk, selachians
  coming inshore to give birth, dolphins and porpoises suckling, fish embryos' eyes appearing first, and
  mice being the most prolific animals. These are the places where the swarm's single extractor kept
  something that three single-agent runs dropped (the matcher may miss a loosely worded match, so treat the
  count as an upper bound on "none").
- **Dataset naming is more conservative in the single-agent runs:** 0.9 to 1.2 references per claim against
  1.7 to 1.8 for the swarm's two assessors, and 5 to 12 claims left with no dataset. Whether the extra
  references are useful or padding needs a scouting pass.

What it does not show: that any arm is more accurate. All comparisons are against other models' outputs, one run
per arm, one slice.

## Cost

Not measured for either arm. The swarm's wall time, tokens and cost were not recorded, and the single run's
tokens were not captured. The single chain wrote its first output and passed validation within about four
minutes of tool time after the reading, but that excludes the reading and the model's own deliberation, so
it is not a wall-clock figure. A cost comparison needs the same logging on both arms.

## Limits

1. n = 1 slice and one run per arm, so there is no run-to-run variance to set the differences against. The claim
   sets differ, so assessment differences mix the effect of the arm with the effect of what each arm chose to
   extract.
2. Models differ across arms (Claude Sonnet 5.5 against an unrecorded extractor model and GPT/Grok assessors), so
   this is not a clean test of "one agent vs many agents".
3. The single agent assessed its own claims after writing them, including the triage and candidate data. The
   swarm's assessors never saw those fields, and the single agent's blind step was blind only by omission of
   fields. This favours agreement with its own extraction, not with the swarm.
4. No ground truth for resolvability exists, so agreement with other assessors is the only yardstick, and it
   rewards matching the others, not being right. (The data-test verdicts in `test-data/claim-tests/` cover the
   Darwin, Thompson, Wolfram and Levin claims, not Aristotle's, so they cannot serve here. A yardstick would be
   a scouting pass that checks whether the named datasets really hold the variables, as in
   `test-data/dataset-scouting/`, on a sample of claims.)
5. Claim matching was done by hand by the single agent, which had also written one side of every pair; it is in
   `match.json` for audit.
6. The swarm's Gemini assessor is absent from the merged data (batch 1 only), so the swarm comparison uses two
   assessors, not three.

## What this does and does not show

- The single-agent chain produced an extraction and assessment of the same quality on the checkable
  properties (verbatim quotes, schema, URL resolution, similar score distribution and similar agreement with
  the swarm's assessors) from one context, with the script doing the quote and schema checking.
- It did not show a gain from the swarm on this slice. It did show where the swarm differs: independent
  assessors give a measurable disagreement signal (GPT vs Grok verdicts agree 64% of the time on 42 claims),
  which a single agent cannot produce about its own work, and the swarm's extraction coverage depended on one
  agent's reading of the instructions.
- See the replication section: with two more models the single-agent arms differ from each other about as much
  as they differ from the swarm, so this slice cannot separate "one agent vs many" from "which model".
- To turn this into evidence for the 25% collective-capability criterion, run the remaining Aristotle ranges
  (`extraction/A`-`K`) with the same logging on every arm, repeat each arm to get run-to-run variance, and
  score a sample of claims against a scouting pass rather than against other assessors.
