# Assessor instructions: dataset resolvability of Wolfram's claims in A New Kind of Science (2002)

You are one of several independent assessors, each running a different language model.
Do not look for, read, or coordinate with other assessors' outputs (anything under
`claim-sources/wolfram-nks/assessment/raw/` other than the file you write), and do not read
`claim-sources/wolfram-nks/claims.json`, `claim-sources/wolfram-nks/worklist.tsv` or `claim-sources/wolfram-nks/extraction/`: they
contain the extractor's own guesses, which you must not anchor on. Use only your input batch,
the rubric, and the source text if you want context.

## Inputs

- Your batch: a JSON array of claims, each with `id`, `label`, `claim` (a modern-English
  restatement faithful to Wolfram), `quote` (verbatim from the book), `chapter`, `section`,
  `page`, `scope` and `claim_kind`.
- Rubric: `claim-sources/wolfram-nks/assessment/rubric.json`. Read it fully; score each of its five
  dimensions with its anchors. It is the same rubric used for the other source works in this repository,
  so that scores are comparable across books.
- Source text (optional context): `claim-sources/wolfram-nks/inputs/cache/nks.txt`, with `=== pN ===`
  page markers. Do not copy it anywhere.

## What you are judging

How far each claim, **as Wolfram stated it**, can be resolved (confirmed or refuted) with
**resources publicly available today**, without collecting new empirical data. You are scoring
testability with existing resources, **not truth**. A claim you believe is false can score
high if existing data or computation could show it is false. Do not credit or penalize a
claim for later developments in its favour or against it; judge whether the resources to
resolve it exist now.

Many claims in this book concern abstract systems (cellular automata, Turing machines,
number sequences). For those:

- Running a standard simulation or enumeration with public software counts as **analysis**,
  not new data collection, and public computational resources (enumerations such as OEIS,
  published proofs, open simulation software) count as existing data.
- A claim that is settled by a published, checkable proof is `resolvable-now`; one that
  would need a proof nobody has is `needs-new-data` only if the obstacle is missing
  computation or data, and `not-empirically-resolvable` if no computation or observation
  could settle it.
- Claims about nature (`model-of-nature`, `physical-hypothesis`) need real observational or
  experimental data about the natural system; showing that a program produces similar-looking
  output is not by itself a test. Weigh discriminating power against rival models.

Note when a claim is only testable after reinterpretation (e.g. "looks random" as passing
specific statistical tests); that lowers operationalizability unless the mapping is
uncontroversial.

## Output

The example below is illustrative only; its scores are not a reference for any real claim.

Write a JSON array, one object per input claim, in input order, to the output path named in
your task:

```json
{
  "claim_id": "wolfram2002-chXX-YY",
  "scores": {
    "operationalizability": 0.8,
    "data-existence": 0.9,
    "data-adequacy": 0.6,
    "discriminating-power": 0.6,
    "analysis-feasibility": 0.8
  },
  "verdict": "resolvable-now",
  "resolution_route": "computation",
  "confidence": 0.7,
  "operationalization": "One or two sentences: the variables or computation, the analysis, and what result would confirm or refute the claim.",
  "candidate_datasets": [
    {"name": "OEIS", "url": "https://oeis.org/", "role": "published terms of the sequence, to compare against the sequence the rule generates"}
  ],
  "obstacles": ["Statistical tests can only fail to detect regularity; they cannot prove its absence."],
  "rationale": "Two to four sentences justifying the scores."
}
```

Field rules:

- `scores`: all five dimensions, each a number in [0, 1] with at most two decimals.
- `verdict`: one of the rubric's four verdicts. It must be consistent with the scores.
- `resolution_route`: how the claim would be resolved: `empirical-data` (observations or
  experiments about the world), `computation` (running or enumerating programs), `proof`
  (mathematical proof), `mixed` (needs both empirical data and computation or proof), or
  `none` (for `not-empirically-resolvable` claims).
- `confidence`: your confidence in your own assessment, in [0, 1].
- `candidate_datasets`: 0–3 entries. Each must be a **real, existing, public** dataset,
  database or computational resource, with the URL of its official landing page or a DOI URL
  (`https://doi.org/...`). **Never invent a name, URL, accession or DOI.** If unsure a URL is
  right, give the resource's top-level homepage instead, or omit the entry. Every URL will be
  checked automatically, and unresolvable ones will be dropped and counted against your
  batch. Use an empty array for `not-empirically-resolvable` claims.
- `obstacles`: 0–3 short strings: what limits a test (biases, confounds, missing variables,
  undecidability, combinatorial explosion).
- `rationale`: plain prose; do not repeat the claim.

Before finishing, re-open your file and check that it parses as JSON, has exactly one entry
per input claim with matching `claim_id`s in input order, and that every score is in [0,1].
Report back the output path, the count per verdict, and any claims you found hard to score.
