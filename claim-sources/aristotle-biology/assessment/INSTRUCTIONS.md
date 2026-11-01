# Assessor instructions: dataset resolvability of claims in Aristotle's biological works

You are one of several independent assessors, each running a different language model.
Do not look for, read, or coordinate with other assessors' outputs (anything under
`claim-sources/aristotle-biology/assessment/raw/` other than the file you write), and do not read
`claim-sources/aristotle-biology/claims.json`, `claim-sources/aristotle-biology/worklist.tsv` or
`claim-sources/aristotle-biology/extraction/`: they contain the extractor's own guesses, which you
must not anchor on. Use only your input batch, the rubric, and the source texts if you want context.

## Inputs

- Your batch: a JSON array of claims, each with `id`, `label`, `claim` (a modern-English
  restatement faithful to Aristotle), `quote` (verbatim from the Oxford translation), `work`
  (`ha` History of Animals, `pa` Parts of Animals, `ga` Generation of Animals), `work_title`,
  `book`, `translator`, `section`, `scope` and `claim_kind`.
- Rubric: `claim-sources/aristotle-biology/assessment/rubric.json`. Read it fully; score each of its
  five dimensions with its anchors. It is the same rubric used for the other source works in this
  repository, so that scores are comparable across them.
- Source texts (optional context): `claim-sources/aristotle-biology/inputs/<work>.txt`, with
  metadata in `claim-sources/aristotle-biology/inputs/sources.json`.

## What you are judging

How far each claim, **as Aristotle states it**, can be resolved (confirmed or refuted) by
analysing **scientific data that are publicly available today**, without collecting new data.
You are scoring testability with existing resources, **not truth**. A claim you believe is false
can score high if existing data could show it is false; many of Aristotle's claims are of this
kind, and that is what makes them worth testing.

For these works:

- Most claims are comparative anatomy, behaviour and life history of named animals or groups.
  Trait databases (life-history, morphology, diet, reproduction), comparative-anatomy
  ontologies, occurrence records and the published zoological literature count as existing data.
- Aristotle's names and groups must be mapped to modern taxa first ("bloodless animals",
  "testaceans", "selachians", "the cestreus"). Lower operationalizability when the mapping is
  uncertain or several mappings give different answers.
- His explanations by final cause ("for the sake of protection", "nature does nothing in vain")
  are testable only through a measurable consequence; score `not-empirically-resolvable` when no
  observation distinguishes the explanation from the bare fact it explains.
- Claims about spontaneous generation, the role of semen or menstrual fluid, or innate heat are
  testable in so far as they predict something observable (e.g. that eels have no eggs or
  roe); score the observable part.

## Output

The example below is illustrative only; its scores are not a reference for any real claim.

Write a JSON array, one object per input claim, in input order, to the output path named in
your task:

```json
{
  "claim_id": "aristotle-haNN-NN",
  "scores": {
    "operationalizability": 0.8,
    "data-existence": 0.6,
    "data-adequacy": 0.5,
    "discriminating-power": 0.6,
    "analysis-feasibility": 0.8
  },
  "verdict": "partially-resolvable",
  "confidence": 0.7,
  "operationalization": "One or two sentences: the variables, the analysis, and what result would confirm or refute the claim.",
  "candidate_datasets": [
    {"name": "AnAge: The Animal Ageing and Longevity Database", "url": "https://genomics.senescence.info/species/", "role": "gestation length and maximum longevity for the named mammals, to compare with the stated values"}
  ],
  "obstacles": ["Aristotle's animal name maps to several modern species with different traits."],
  "rationale": "Two to four sentences justifying the scores."
}
```

Field rules:

- `scores`: all five dimensions, each a number in [0, 1] with at most two decimals.
- `verdict`: one of the rubric's four verdicts. It must be consistent with the scores.
- `confidence`: your confidence in your own assessment, in [0, 1].
- `candidate_datasets`: 0–3 entries. Each must be a **real, existing, public** dataset,
  database or code repository, with the URL of its official landing page or a DOI URL
  (`https://doi.org/...`). **Never invent a name, URL, accession or DOI.** If unsure a URL is
  right, give the database's top-level homepage instead, or omit the entry. Every URL will be
  checked automatically, and unresolvable ones will be dropped and counted against your batch.
  Use an empty array for `not-empirically-resolvable` claims.
- `obstacles`: 0–3 short strings: what limits a test (name mapping, biases, missing variables).
- `rationale`: plain prose; do not repeat the claim.

Before finishing, re-open your file and check that it parses as JSON, has exactly one entry
per input claim with matching `claim_id`s in input order, and that every score is in [0,1].
Report back the output path, the count per verdict, and any claims you found hard to score.
