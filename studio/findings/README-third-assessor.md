# A third model assessor disagrees with a two-model "consensus" more than chance-corrected agreement would suggest

Delphi carries **1,224 dataset-resolvability assessments over 612 claims from two assessors** (a
grok and a gpt), each scoring five dimensions — data-existence, data-adequacy,
analysis-feasibility, discriminating-power, operationalizability — and emitting a verdict.

We ran **Gemini 3 flash as an independent third assessor** on a stratified sample of 40 claims
that already carry both, to measure its agreement **before** using anything it says. The script
is `gemini_third_assessor.py`; the raw rows are
`gemini-third-assessor-calibration.json`. 40 of 40 assessed, 0 errors.

## Result

| | |
|---|---|
| Gemini vs the two-assessor majority, verdict agreement | **24/40 = 60%** |
| **Baseline: always answer "partially-resolvable"** | **29/40 = 72%** |
| Chance-expected agreement from the marginals | 36.6% |
| Cohen's kappa | **0.369** |
| Delphi's own two assessors, verdict agreement with each other | **35/40 = 88%** |
| Delphi's own two assessors, mean absolute score difference | **0.086** |
| Gemini vs their consensus, mean absolute score difference | **0.151** |

**The third assessor scores below the trivial baseline.** A rule that ignores the claim entirely
and always answers "partially-resolvable" agrees with the existing consensus more often than
Gemini does.

The verdict distributions are the tell. Across 40 claims the two existing assessors produced only
**two** distinct verdicts (partially-resolvable 29, resolvable-now 11). Gemini used **all four**,
including 6 `not-resolvable-with-public-data` and 2 `not-operationalizable`.

## Two readings, and we cannot separate them here

1. **Gemini is miscalibrated**, with higher variance in both directions (mean signed difference
   +0.065, sd 0.167, max 0.426).
2. **The existing two assessors are correlated with each other.** They are both frontier LLMs
   assessing the same text. Their 88% agreement is then not evidence of correctness, any more
   than two papers citing the same experiment are independent replications. On that reading the
   outlier is the informative one.

Reading 2 is the same error this project has been refusing all day in a different costume, and it
is why the Frontier `Assessment` record keeps seven **named** dimensions with a named reviewer and
**no composite truth score**: a number that averages correlated judges looks like consensus and is
not.

## The confound, stated because it is serious

**We do not have Delphi's original assessor prompt.** The prompt used here is ours. So an unknown
share of the disagreement is prompt difference rather than model difference, and this result
cannot attribute it. It is evidence that *the verdict label is unstable across assessor setups*,
which is weaker than, and must not be reported as, *Gemini disagrees with grok and gpt*.

Other limits: n=40, one model, one temperature (0), one sampling pass, stratified by the existing
consensus score across four buckets. Thompson and Wolfram domains only — no Darwin claim was drawn
into this sample. Score-level agreement is much better than verdict-level agreement, so the
five dimensions are more stable than the categorical verdict built from them.

## A harness defect that nearly became a finding

The first run reported 13 of 24 assessed with 11 `no JSON in reply`, and tidy-looking numbers
(mean absolute difference 0.107, Thompson −0.004). Those numbers were **not reported**, because
the failures were ours: Gemini 3 spends thinking tokens from the same output budget, and at
`maxOutputTokens=1200` the model finished thinking with nothing left to emit
(`thoughtsTokenCount: 58` on a one-line prompt). A 46% loss also means the survivors were whatever
was cheap to think about, which is not a sample. Fixed with structured output and an 8,000-token
budget: 40 of 40, 0 errors. The failure path now reports `finishReason` and usage, so the next one
is diagnosable instead of mysterious.
