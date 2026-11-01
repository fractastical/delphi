# Assessor calibration against settled claims

The truth scores in `test-data/truth/raw/` are model opinions on claims nobody has tested. This folder
measures how far those opinions can be trusted, using claims whose answer is already known: 102 of
Aristotle's biological claims that modern zoology has settled, including some that were dismissed for
centuries and later confirmed (the smooth dogfish placenta, the male-guarded catfish nest, the queen
as mother of the hive).

- `historical-verdicts.json`: the answer key. Each claim has its modern verdict, a group (`vindicated`,
  `confirmed`, `refuted`), the evidence and a source. `revised` records a verdict changed after reviewing
  assessor objections and `exclude` a claim left out of scoring; both are listed in `REPORT.md`, since a
  key revised after a run favours the assessors whose objections prompted the change.
- `make-batches.mjs`: writes `inputs/blind.json` (statement only) and `inputs/attributed.json` (with
  thinker, work and quote, as the main pipeline shows claims). Comparing the two shows how much an
  assessor recalls rather than reasons, and whether knowing the author moves its score.
- Assessors follow [../INSTRUCTIONS.md](../INSTRUCTIONS.md) and write `raw/<assessor>/<condition>.json`.
  These scores are kept out of `test-data/truth/raw/`, so they never reach the claim graph.
- `score.mjs`: Brier score, log loss, accuracy and calibration per assessor and condition, by group, into
  `REPORT.md` and `scores.json`.

```sh
node test-data/truth/calibration/make-batches.mjs
# run each assessor on both input files
node test-data/truth/calibration/score.mjs
```

A verdict applies to the claim as stated: a universal claim fails on an important exception and a
compound claim fails if any part fails, as the assessor instructions require.
