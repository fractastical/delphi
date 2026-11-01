# Self-assessment on the Science Claw judging rubric

Blind, multi-provider rating of where the project stands against the hackathon's own judging
rubric ([scienceclawhack.ai](https://scienceclawhack.ai/)), published as nanopubs. Tracks
[issue #61](https://github.com/fractastical/delphi/issues/61). Results: [SUMMARY.md](SUMMARY.md).

| File | What |
|---|---|
| `rubric.json` | `scienceclaw-rubric/0.1.0`: the five judged criteria with the published weights, 0–10 anchors, and the separate collaboration bonus. Any wording change is a new version. |
| `assessors.json` | The assessor roster: GPT-5.6 Sol, Gemini 4 Argon, Grok 4.7. Claude built most of the repo and does not score. |
| `INSTRUCTIONS.md` | What assessors may read (only `evidence/`), how to judge, and the output shape. |
| `evidence/` | The frozen evidence pack: copies of the repo's descriptive documents, captured MCP/CLI outputs, issues, PRs, forum feed, git stats; `MANIFEST.json` pins the commit and SHA-256 of every file, `PACK_SHA256` hashes the manifest. Rebuilt by `build/pack.mjs`. |
| `raw/<assessor>.json` | Each assessor's output, untouched. |
| `assessments.json`, `SUMMARY.md` | Merged by `build/merge.mjs`: validation against the rubric and pack hash, weighted totals, mean and spread, each assessor's ranked fixes. |
| `nanopubs/` | `rubric-unsigned/`, `assessments-unsigned/` from `build/generate.mjs`; `*-signed/` and `manifest.jsonl` from `build/publish.mjs`. |
| `rounds/<n>-<commit>/` | Earlier rounds, archived whole (`evidence/`, `raw/`, `assessments.json`, `SUMMARY.md`). `merge.mjs` reports the change since the latest archived round. Before a new round: `mkdir rounds/<n>-<commit> && git mv evidence raw assessments.json SUMMARY.md rounds/<n>-<commit>/`. |

## Run

```sh
node scripts/release/self-assessment/build/pack.mjs          # freeze the evidence pack
# launch one blind assessor subagent per entry in assessors.json; each writes raw/<id>.json
node scripts/release/self-assessment/build/merge.mjs         # assessments.json + SUMMARY.md
node scripts/release/self-assessment/build/generate.mjs      # nanopubs/*-unsigned
node scripts/release/self-assessment/build/publish.mjs --registry test --dir nanopubs/rubric-unsigned
node scripts/release/self-assessment/build/publish.mjs --registry test --dir nanopubs/assessments-unsigned
```

Production needs the operator's explicit go-ahead (irreversible, signed with the ORCID key).

## Modelling notes

The assessed thing is a project snapshot, `https://github.com/fractastical/delphi/tree/<commit>`,
typed `prov:Entity, schema:SoftwareSourceCode`, and linked with `delphi:hasAssessment` as a claim
would be. The ontology defines `delphi:hasAssessment` on hypotheses; using it for a project
snapshot is a deliberate stretch so the same queries that rank claims by assessment also find
this. Each assessment nanopub holds the overall `delphi:LLMClaimAssessment` (score = weighted
total / 100, confidence = the assessor's confidence in its own scoring), one part per criterion
(score = criterion / 10, `dct:description` = justification, `delphi:evidenceAgainst` = the gaps
that would raise it) and one for the bonus. Provenance records the raw file, the pack manifest,
the rubric IRI and the instructions, and states that the assessment was blind.
