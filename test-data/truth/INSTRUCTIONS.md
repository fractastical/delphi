# Truth-score assessment instructions

You are a blind assessor. For every claim in your input batch, give your probability that the
claim is **true**, with a short rationale. These scores are shown next to each claim's separate
testability score, so judge truth only, not how easy the claim is to test.

Read only your input batch file. Do not read any other file in this repository (claims files,
assessments, other assessors' outputs, docs), and do not search for this project's own pages.

## What to judge

- `p_true`: your probability in [0, 1] that the claim, **as stated and within its stated scope**,
  is true given the current state of scientific knowledge.
- Judge the modern restatement in `statement`. The `quote` (when present) is the author's original
  wording, given for context; do not penalise archaic terms if the restated proposition holds.
- **Empirical claims**: the probability that nature actually behaves as claimed across the stated
  scope. A claim stated universally ("all", "always", "never") is only true if it holds without
  important exceptions; a claim stated as a tendency ("generally", "most") is true if the tendency
  holds.
- **Mathematical claims** (model theorems): the probability that the statement is true *under its
  stated assumptions* (`assumptions`, `notation`). A correctly stated, proved theorem is near 1;
  a misstated one, or one that bundles an empirical assertion that fails, is lower.
- **Conceptual, definitional or methodological claims**: the probability that the position is
  correct by the lights of current science and philosophy of science. Use values near 0.5 only
  when you are genuinely uncertain, not as a default.
- Compound claims are true only if every part is true.
- Be calibrated: across many claims you rate 0.8, about 80% should turn out true.

## Output

Write a JSON array to the output file named in your task, UTF-8, one element per input claim, in
input order:

```json
{ "key": "<copied from input>", "p_true": 0.0, "rationale": "One or two sentences: the main evidence or argument for and against." }
```

- Copy `key` exactly. Every input claim must appear exactly once.
- `p_true` is a number with at most two decimals.
- The rationale names evidence in words. Do not invent citations, DOIs, URLs or dataset names;
  if you are not sure a source exists, describe the evidence instead.
- Validate your file parses as JSON and has one entry per input claim before you finish.
