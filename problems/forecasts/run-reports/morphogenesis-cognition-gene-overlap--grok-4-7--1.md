# morphogenesis-cognition-gene-overlap--grok-4-7--1

Pleiotropy-matched overlap of morphogenesis and learning genes (data test, claim `levin-2022-tame-19`).
Artifact: `test-data/claim-tests/levin-papers/levin-2022-tame-19/overnight-go-overlap/result.json`
(the repo moved `test-data/` under `` mid-run; the pre-registration was written at 05:50Z, before the first download at 10:15Z).

## Outcome: completed, verdict `mixed` (confidence 0.6)

Primary run (IEA excluded), 19,276 HGNC protein-coding genes, null = 10,000 label permutations within
5x5 strata of GO annotation count x INDRA CoGEx statement degree (3x3 within subsets):

| Endpoint | n | morph | learn | overlap | OR (95% CI) | null median OR | perm p | pass |
|---|---|---|---|---|---|---|---|---|
| E1 all genes | 19,276 | 1,417 | 117 | 37 | 5.96 (4.02-8.83) | 2.62 | 0.0002 | yes |
| E2 ion channel GO:0005216 | 407 | 21 | 7 | 2 | 8.02 (1.46-44.1) | 3.17 | 0.23 | no |
| E3 gap junction GO:0005921 | 26 | 3 | 0 | 0 | - | - | - | underpowered |

IEA-included run (labelled, does not count): E1 OR 5.65, p = 0.0002; E2 OR 10.42, p = 0.10; E3 underpowered.

## What it means

- The full-set overlap survives matching on annotation volume and INDRA degree (2.27x the matched-null median),
  so the failure signature (full-set OR inside the matched null) is not met.
- The bioelectric subsets Levin names do not pass: ion channels fail the p threshold, and no gap-junction gene
  carries a non-IEA learning-or-memory annotation. The decisive result required all three, hence `mixed`.
- Conflicts in direction with the parent mouse test (experimental codes only, depth-decile MH OR 0.94, refutes).
  Species, evidence rule and matching granularity differ; residual study bias is a live explanation.
- The OR > 2 threshold is weak because the matched null median already exceeds 2.

## Data

GO go-basic.obo, GOA human GAF, HGNC protein-coding list (SHA-256 in `checksums.json`), and INDRA CoGEx
per-gene distinct statement counts, queried via `execute_cypher` on the public MCP endpoint
(https://discovery.indra.bio/mcp; the `indra-cogex` MCP was not in this agent's tool list). No deviation
from the pre-registered matching was needed. Data (54 MB) are git-ignored; `fetch.py` regenerates them.

## Not done

No commit, signing or publishing. Approaches 2 (INDRA statement density) and 3 (pre-2015 annotations) not run.
