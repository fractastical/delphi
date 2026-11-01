# Triage of all 267 problems, and a headline that did not survive its own control

Every problem in the store was assessed by Gemini 3 flash on Delphi's own five
dataset-resolvability dimensions. **267 of 267 assessed, 0 errors.** Artifact:
`gemini-triage-267-problems.json`; script `gemini_assess_problems.py`.

**This is a provider stance, not truth.** The same model, as a third assessor on Delphi claims
this morning, scored **below an always-answer-the-mode baseline**
(`README-third-assessor.md`). It is used here for triage and for nothing else. No problem's
status changes because a model scored it.

## What it produced

| verdict | n |
|---|---|
| not-resolvable-with-public-data | **217** |
| partially-resolvable | 44 |
| resolvable-now | **6** |

**267 of 267 produced a concrete `what_would_settle_it`**, and 260 named at least one dataset.
That field is precisely what 254 of our problems are missing and what blocks them from being
actionable. These are model-generated and need a human, but they are a starting point where
there was none.

## The headline that failed

Actionable problems scored **0.662** against recorded problems' **0.468**, a gap of **+0.194**
with a permutation p **< 0.0001** over 20,000 shuffles — and the model was never told which was
which. That reads as independent convergent evidence that the actionable flag tracks something
real.

**It is confounded, and the confound is total.** All 13 actionable problems come from the
sourced set; all 254 recorded ones are from the register. So the comparison is
sourced-versus-register wearing a different label:

| | n | mean |
|---|---|---|
| sourced set | 17 | 0.635 |
| register set | 250 | 0.466 |

**Within the sourced set alone**, where the confound is removed: actionable 0.662 (n=13) against
recorded 0.550 (n=4), diff +0.112, permutation **p = 0.12**. Not significant, and badly
underpowered at 13 versus 4.

**So the actionable flag is NOT shown to track model-judged resolvability.** What survives is the
finding we already had, arriving through a third instrument: problems sourced to a retrieved
identifier with a locator and a checked quote score higher than curated problems without one.
Curation discipline is the difference, again.

## Cost and scope

One Gemini call per problem, six-way parallel, temperature 0, structured output with an enforced
schema. Zero failures, against 11 of 24 on the first run this morning before the thinking-token
budget was fixed. Scope: one model, one prompt, one pass. A verdict here is an opinion about
public data, not a finding about the problem.
