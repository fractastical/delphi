# Assessor instructions: dataset resolvability of claims in Michael Levin's papers

You are one of several independent assessors, each running a different language model.
Do not look for, read, or coordinate with other assessors' outputs (anything under
`books/levin-papers/assessment/raw/` other than the file you write), and do not read
`books/levin-papers/claims.json`, `books/levin-papers/worklist.tsv` or
`books/levin-papers/extraction/`: they contain the extractor's own guesses, which you must not
anchor on. Use only your input batch, the rubric, and the source texts if you want context.

## Inputs

- Your batch: a JSON array of claims, each with `id`, `label`, `claim` (a modern-English
  restatement faithful to the paper), `quote` (verbatim from the paper), `paper` (key),
  `paper_title`, `year`, `section`, `scope` and `claim_kind`.
- Rubric: `books/levin-papers/assessment/rubric.json`. Read it fully; score each of its five
  dimensions with its anchors. It is the same rubric used for the other source works in this
  repository, so that scores are comparable across them.
- Source texts (optional context): `books/levin-papers/inputs/<paper>.txt`, with metadata in
  `books/levin-papers/inputs/sources.json`.

## What you are judging

How far each claim, **as the paper states it**, can be resolved (confirmed or refuted) by
analysing **scientific data or computation that is publicly available today**, without
collecting new data. You are scoring testability with existing resources, **not truth**. A
claim you believe is false can score high if existing data could show it is false.

These papers mix wet-lab findings (Xenopus, planaria, human cells), computational models, and
theoretical claims about cognition, agency and evolution. For them:

- A paper's own reported result counts as resolvable with existing data only if the data
  needed to check it are public (deposited raw data, published measurements, public
  expression datasets, or independent published replications) or, for a simulation result, if
  the model is specified well enough, or its code is public, so that re-running or
  re-implementing it is analysis rather than new research. Re-reading the paper's own
  figures is not a test.
- Running a model or simulation with public software or published models (for example models
  in BioModels) counts as **analysis**, not new data collection.
- Claims that use cognitive terms ("goal", "memory", "learning", "intelligence", "self",
  "agent") for cells, tissues or networks are testable only through a measurable
  operationalization (e.g. "memory" as a persistent change in response after a training
  stimulus; "goal" as a set point the system returns to after perturbation). Lower
  operationalizability when the mapping is contested or several operationalizations give
  different answers; score `not-empirically-resolvable` when no observation distinguishes the
  claim from a non-cognitive description of the same facts.
- Wet-lab claims whose test would need new perturbation experiments (new embryos, new
  regeneration assays) are `needs-new-data`, unless public datasets already contain the
  relevant perturbation and readout.

## Output

The example below is illustrative only; its scores are not a reference for any real claim.

Write a JSON array, one object per input claim, in input order, to the output path named in
your task:

```json
{
  "claim_id": "levin-XXXX-xxxx-NN",
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
    {"name": "Gene Expression Omnibus", "url": "https://www.ncbi.nlm.nih.gov/geo/", "role": "public expression profiles after membrane-voltage perturbation, to test whether the predicted transcriptional response occurs"}
  ],
  "obstacles": ["Few public datasets pair a voltage perturbation with an anatomical readout."],
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
- `obstacles`: 0–3 short strings: what limits a test (biases, confounds, missing variables).
- `rationale`: plain prose; do not repeat the claim.

Before finishing, re-open your file and check that it parses as JSON, has exactly one entry
per input claim with matching `claim_id`s in input order, and that every score is in [0,1].
Report back the output path, the count per verdict, and any claims you found hard to score.
