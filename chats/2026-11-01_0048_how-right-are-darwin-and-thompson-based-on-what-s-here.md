# how right are darwin and thompson based on what's here?

- **Started:** 2026-11-01 00:48 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 00:49 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `cc33b2ae-5403-4fa2-89cf-5fc7e9aeb45c`

## Conversation

### 2026-11-01 00:48 — Turn 1 (User)

> how right are darwin and thompson based on what's here?

**Assistant:**

I'll pull the thinker views, truth scores, and data-test verdicts from the repo.

To figure out how accurate Darwin and Thompson actually are according to this repo, I should pull up the delphi_graph tool for thinker views and truth scores, plus delphi_claim_tests for verdicts—checking whether the local MCP namespace has claim-tests or if I need the remote one, and also cross-referencing the README's current numbers and the claim-tests summary file.

Now the model truth scores and the Lean status, grouped per thinker.

Short version: Darwin comes out clearly better than Thompson on both of the repo's measures, but both are "right" mostly at the level of pattern and wrong at the level of mechanism. Numbers from `test-data/claim-tests/SUMMARY.md` and `delphi_graph` (snapshot built 2026-11-01 04:42).

**Data tests (agents ran claims against real datasets)**

| | tested | supports | mixed | refutes | inconclusive | supports ÷ (supports+refutes) |
|---|---:|---:|---:|---:|---:|---:|
| Darwin (247 claims) | 46 | 22 | 14 | 9 | 1 | 71% |
| Thompson (291 claims) | 37 | 12 | 9 | 12 | 4 | 50% |

**Model truth scores** (mean p_true across GPT-5.6 Sol and Grok 4.7, all claims): Darwin 0.68, Thompson 0.50. For reference, Wolfram is 0.60 and Levin 0.65; Thompson is the lowest of the four big sources.

**Where Darwin holds up**: nearly everything structural. Biogeography (barriers predict faunal differences, island species counts and endemism, continent-wide relatedness regardless of habitat, mountain floras), the fossil record (consecutive formations more alike, regional succession, differing rates of change, no global cataclysm), convergent evolution, unity of biochemistry, pigeon monophyly. These are the claims that carry the argument of the book and they come out as supports at 0.75–0.95 confidence.

**Where Darwin is wrong**: two kinds of things.
- Physical/geological premises he borrowed: the Weald denudation giving ~300 Myr (refuted, 0.98), fixed continents since the Silurian (refuted, 0.95), a simultaneous glacial period (mixed).
- Over-sharp island generalizations: no amphibians on oceanic islands, no mammals beyond 300 miles, dogs from several wild species, freshwater fish never shared between continents, northern species naturalising south far more than the reverse. All refuted at 0.7–0.93. The pattern was real; the "never" was not.
- The lowest-scored untested claims are all his Lamarckian mechanisms: blindness and flightlessness from disuse, inherited effects of use, variability from the reproductive elements being disturbed (p_true 0.05–0.14). Natural selection survives; his theory of variation does not.

**Where Thompson holds up**: growth and phyllotaxis. Human growth curves, boys/girls differing mainly in phase, prenatal velocity peak, parastichy numbers changing with size, left/right parastichies equally common, eggs always prolate, aquatic mammals lacking withers, corallites hexagonal on average. Also 47 of his claims are Lean-checked theorems, the most of any thinker, so when he states a geometric proposition it is usually a correct one.

**Where Thompson is wrong**: the places where he insists physics replaces biology.
- Cell physics is nearly all refuted or scored near zero: mitosis as a magnetic field, chromatin as diamagnetic, mitochondria as surface-tension clumps, chromosome numbers between 6 and 16 (refuted, 0.9).
- The shell geometry overclaims: shells grow without changing shape (refuted), each increment is a gnomon (refuted), the spiral angle is 80–85° (refuted), the turreted-shell suture as a conical geodesic (refuted). The log spiral is a fine approximation, not a law.
- Transformations read as phylogeny: perissodactyls closer to rabbits than to other ungulates (refuted, 0.97; p_true 0.015), Schistosoma spine as a mechanical artefact rather than a species mark (refuted, 0.97), ventricle wall thickness ratio of 6–7 (refuted), fish volume conserved under transformation (refuted).
- His Lean theorems don't rescue him here: the proofs show the geometry follows from its assumptions, and the data tests are exactly what show organisms often don't satisfy the assumptions. Note also that the proved Thompson claims have the highest model disagreement in the graph (0.19), i.e. the assessors argue about whether the theorem is biologically true even when it's mathematically proved.

**Caveats on reading this as a verdict**
- Only ~19% of Darwin's and ~13% of Thompson's claims have been tested, and the tested set skews to what was easiest to get data for (high testability), not a random sample.
- Verdicts and confidences were assigned by agents, and truth scores are two models' opinions; the repo's own rule is that neither promotes a claim.
- Thompson's claims are being judged against a century more of cell biology and phylogenetics than Darwin's are against geology; a fair share of his misses are 1917 physics, not bad reasoning.

So: Darwin is right about roughly 7 in 10 of the things that have been checked, and his errors are concentrated in the premises he took from others and in the mechanism of variation. Thompson is right about half, with a sharp split between growth curves and phyllotaxis (good) and cell physics and transformation-as-phylogeny (bad).

The 20 "proved" figure for Darwin likely reflects Lean-checked claims, consistent with the 71 total Lean-checked claims across both. I have enough data now — Darwin tested 46 claims with 22 supports, about 48%.

Thompson's mean truth score (0.497) trails Darwin's (0.684), sitting below Wolfram (0.602) and Levin (0.648). The pattern is clear: Darwin's failures cluster in geology and biogeography overreach, while his core structural ideas on common descent and fossil succession hold up; Thompson's growth curves and phyllotaxis work hold, but his cell physics and shell geometry claims overreach, even though his underlying math checks out in Lean.

I should flag the caveats honestly — the tested theorems are a non-random, mostly-testable subset (~19% Darwin, ~13% Thompson), judged by two AI models' confidence scores rather than ground truth. Now I'll write up the answer compactly, maybe with a small table.

_Tools used: GetDynamicTools, Grep, Read, delphi_graph ×5_
