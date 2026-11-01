# OpenResearch literature grounding for the headline claim tests (issue #16)

`AGENTS.md` (role A2) requires, per claim, a real run through the official alphaXiv OpenResearch CLI
recording what the modern literature says and whether prior work already answers the claim. This
folder holds the runs for six headline tests.

## What was run

`orx discover <source> "<query>" --limit 10` (OpenResearch CLI 0.2.23, installed from
openresearch.sh on 2026-10-31 with `OPENRESEARCH_CLI_NO_MODIFY_PATH=1`; sources `openalex`, `pubmed`,
and the alphaXiv corpus where relevant). `run.mjs` logs, per query, the exact command, the UTC time,
the exit code and the returned records verbatim (id, title, date, citation count, abstract) into
`test-data/claim-tests/<project>/<dir>/openresearch.json`.

`orx discover` is a stateless retrieval primitive: it issues no run or experiment identifier. The
files say so (`run_identifier: null`) rather than carry an invented one. The command, time and
returned records are the reproducible record.

## Assessments

`assessments.mjs` writes the `assessment` block of each file by hand (what the literature says,
whether prior work already answers the claim, the citations, the implication for the test). It
refuses to write any identifier that the runs did not return, so every citation is one the search
produced.

| claim | already answered by prior work | implication |
|---|---|---|
| kimura-heterozygosity | yes | the refuted pattern (Lewontin's paradox) is established; the test is a reproduction; the open question is the cause |
| thompson1917-ch03-07 | partly | within-age exponent is about 2 (BMI); the across-growth exponent varies with the age window, which is what the cross-check found |
| maynardsmith-hitchhiking | yes | the diversity-recombination correlation in humans is settled; attribution to sweeps vs background selection is the open part |
| darwin1859-ch09-03 | yes | the end-Cretaceous age is a settled measurement; no citation for the Phillips episode was returned |
| thompson1917-ch04-13 | yes | plant chromosome-number distributions are compiled; the animal half has a 2021 compilation |
| darwin1859-ch11-13 | yes | long, repeated, two-hemisphere glacial cycles are textbook; Darwin's single long period is the point of departure |

Two queries returned no PubMed results (weight-for-height exponent; benthic stack duration); the
OpenAlex queries covered them.

## Re-run

```
node test-data/claim-tests/openresearch/run.mjs            # all six claims; --only <claim_id> for one; --orx <path>
node test-data/claim-tests/openresearch/assessments.mjs    # re-applies the hand-written assessments, validating citations
```
