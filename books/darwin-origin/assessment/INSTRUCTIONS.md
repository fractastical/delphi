# Assessor instructions: dataset resolvability of Darwin's 1859 claims

You are one of several independent assessors, each running a different language model.
Do not look for, read, or coordinate with other assessors' outputs (anything under
`darwin-origin/assessment/raw/` other than the file you write), and do not read
`darwin-origin/claims.json` or `darwin-origin/worklist.tsv`: they contain the extractor's own
guesses, which you must not anchor on. Use only your input batch, the rubric, and the source
text if you want context.

## Inputs

- Your batch: a JSON array of claims, each with `id`, `label`, `claim` (a modern-English
  restatement faithful to Darwin), `quote` (verbatim from the 1859 first edition), `chapter`,
  `section`, `scope` and `claim_kind`.
- Rubric: `darwin-origin/assessment/rubric.json`. Read it fully; score each of its five
  dimensions with its anchors.
- Source text (optional context): `darwin-origin/inputs/pg1228.txt`.

## What you are judging

How far each claim, **as Darwin stated it**, can be resolved (confirmed or refuted) by
analysing **scientific datasets that are publicly available today**, without collecting new
data. You are scoring testability with existing data, **not truth**. A claim modern biology
considers false can score high if existing data could show it is false.

Note when a claim is only testable after reinterpretation in modern terms (e.g. "variation"
as heritable genetic variation); that lowers operationalizability unless the mapping is
uncontroversial.

## Output

The example below is illustrative only; its scores are not a reference for any real claim.

Write a JSON array, one object per input claim, in input order, to the output path named in
your task:

```json
{
  "claim_id": "darwin1859-chXX-YY",
  "scores": {
    "operationalizability": 0.8,
    "data-existence": 0.9,
    "data-adequacy": 0.6,
    "discriminating-power": 0.6,
    "analysis-feasibility": 0.8
  },
  "verdict": "resolvable-now",
  "confidence": 0.7,
  "operationalization": "One or two sentences: the variables, the analysis, and what result would confirm or refute the claim.",
  "candidate_datasets": [
    {"name": "Paleobiology Database", "url": "https://paleobiodb.org/", "role": "occurrence counts per taxon per time bin, to test whether occupancy declines before last appearance"}
  ],
  "obstacles": ["Preservation and sampling biases make apparent rarity before extinction partly an artefact (Signor-Lipps effect)."],
  "rationale": "Two to four sentences justifying the scores."
}
```

Field rules:

- `scores`: all five dimensions, each a number in [0, 1] with at most two decimals.
- `verdict`: one of the rubric's four verdicts. It must be consistent with the scores.
- `confidence`: your confidence in your own assessment, in [0, 1].
- `candidate_datasets`: 0–3 entries. Each must be a **real, existing, public** dataset or
  database, with the URL of its official landing page or a DOI URL (`https://doi.org/...`).
  **Never invent a name, URL, accession or DOI.** If unsure a URL is right, give the
  database's top-level homepage instead, or omit the entry. Every URL will be checked
  automatically, and unresolvable ones will be dropped and counted against your batch. Use an
  empty array for `not-empirically-resolvable` claims.
- `obstacles`: 0–3 short strings: what limits a test (biases, confounds, missing variables).
- `rationale`: plain prose; do not repeat the claim.

Before finishing, re-open your file and check that it parses as JSON, has exactly one entry
per input claim with matching `claim_id`s in input order, and that every score is in [0,1].
Report back the output path, the count per verdict, and any claims you found hard to score.
