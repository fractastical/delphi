# Instructions for a forecaster

You are one agent in a swarm of forecasters, each from a different model provider. A round gives
you a slice of the open problems in [`../problems.json`](../problems.json) with the approaches
proposed for each. You set, for every approach and every problem in your slice, the probability
that the delphisci swarm gets it done. The rounds repeat, so your numbers are compared with what
later happens and with the other forecasters' numbers.

## What you may read

Only your slice file, `problems/forecasts/rounds/<round>/queue/<slice>.json`, and this file. The
slice contains the problem statements, every approach (method, decisive result, failure signature,
what the proposer says is missing), the state of the claims each problem bears on (Lean proofs,
data-test verdicts), the runs the swarm has actually logged, and what changed since the last
round. Do not read other forecasters' files, other rounds' forecasts, the repo's nanopubs or the
web. If you need a fact that is not in the slice, say so in the rationale and forecast on what is there.

If `blind` is true this is the first round and there is no prior: forecast from the slice alone.
If `blind` is false, every problem and approach carries a `prior` (the previous round's median
across forecasters). **Start from the prior and move only for a reason you can name**: a run was
logged, a claim changed status, an approach was added, or you think the prior was miscalibrated
(then say why). Quiet rounds should produce small moves. Do not reset to your own opinion just
because you would have said something else.

## What you forecast

All probabilities are for the swarm as it exists (agents with Lean 4, public-data tests, INDRA,
the organisms layer, the morpholib pipeline, simulation previews; no wet lab, no restricted
data, no new mathematics beyond what current provers can do), starting on the round `date`.
Nothing counts unless it is **run and logged**: a Lean report in `<project>/lean/reports`, a
`test-data/claim-tests/` result, or an entry in `problems/forecasts/runs.json`. A plan is not a result.

Per **approach**:

- `p_complete`: probability the swarm produces the approach's `decisive_result` artifact and logs
  it within **30 days** of agent time (pass or fail; reaching the failure signature still counts
  as complete). Compare with the proposer's `proposer_difficulty` (tractable > 50%, hard 10–50%,
  long-shot < 10%), which you may disagree with.
- `p_settle`: probability, **given completion**, that the result gives a definite answer to what
  the approach targets (the problem, or the piece of it the approach names), positive or negative,
  rather than an inconclusive or partial result.

Per **problem**:

- `p_solved_30d`: probability the problem's `acceptance_criteria` are met, or a `falsifier` is hit
  definitively, by logged artifacts within 30 days of the round date, by any route.
- `p_solved_365d`: the same within 365 days, counting that the swarm may try several approaches
  in sequence and learn from failures.

Constraints the validator checks: all values in [0, 1]; `p_solved_30d` ≤ `p_solved_365d`; every
approach and problem in your slice present exactly once. Warnings (explain in the rationale if
you keep them): a problem's `p_solved_30d` below the best single whole-problem approach's
`p_complete × p_settle`; a `p_solved_365d` below `p_solved_30d` plus a plausible extra.

## Calibration

- Use the full range. Do not park everything at 0.1–0.3. A finite computation the swarm has tools
  for can be 0.8; a famous open problem (Rule 30 center-column randomness, smallest universal
  machine) is below 0.02 for a proof, though a partial or exhaustive-bounded result is a different
  approach with its own number.
- Separate *doing the work* (`p_complete`) from *the work being decisive* (`p_settle`). A data test
  can complete with certainty and still not settle a question.
- Approaches are not independent: if two fail for the same reason (missing dataset, hard lemma),
  the problem's probability is far below the union of independent chances.
- Treat the proposers' claims about datasets, theorems and tools as unverified; discount
  approaches whose key step you cannot see how an agent would do.
- Percentages like 0.5 should mean you cannot tell. Round to two decimals; no false precision.

## Output

Write `problems/forecasts/rounds/<round>/forecasts/<model-slug>--<slice>.json` and nothing else
(you are told `<round>`, `<slice>` and `<model-slug>`). Valid JSON:

```json
{
  "round": "<round id>",
  "slice": "<slice id>",
  "model": "<model-slug>",
  "provider": "<OpenAI | Google | xAI | Anthropic | ...>",
  "generated": "<ISO timestamp>",
  "problems": [
    {
      "problem": "<problem id>",
      "p_solved_30d": 0.05,
      "p_solved_365d": 0.20,
      "rationale": "<two to four sentences: the main route to success, the main blocker, what would move you>",
      "change_reason": "<what changed vs the prior and why; null in a blind round or if you did not move>",
      "approaches": [
        { "approach": "<approach id>", "p_complete": 0.30, "p_settle": 0.60, "note": "<one sentence: why this number>" }
      ]
    }
  ]
}
```

Then run `node problems/forecasts/build/validate.mjs <round>` and fix every error. Do not edit any
other file.
