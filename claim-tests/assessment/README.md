# A9 faithfulness assessment of the claim tests (run by a non-Anthropic model)

Role A9 in `AGENTS.md`: an independent check that the analysis measures what the claim asserts (right
variables, appropriate modality, assumptions compatible with the data collection, a decision rule that
discriminates, narrowing stated). The analyses in `claim-tests/` were written by Claude (Anthropic), so
Claude never scores them. A `not-representative` verdict stops the chain: the test's evidence does not
count, whatever its numbers said.

## Files

| path | content |
|---|---|
| `prompt.md` | Rubric `analysis-faithfulness/0.1.0`: five scored questions, a verdict and "what would change it". |
| `build-inputs.mjs` | Builds `inputs.json` and one blinded prompt per test in `prompts/`, from `docs/claims.json` and the test directory. Withheld on purpose: measured values, verdict, confidence, caveats, interpretation. |
| `run.mjs` | Sends each prompt to the chosen provider (`openai`, `openai-codex`, `gemini`, `vertex`; never anthropic) and writes `claim-tests/<project>/<dir>/faithfulness.json` plus a copy in `results/`. |
| `inputs.json`, `prompts/` | Generated; committed so the exact text each assessor saw is on record. |
| `results/` | One file per test and provider, same content as the `faithfulness.json` it wrote. |

## Run

```
node claim-tests/assessment/build-inputs.mjs
OPENAI_API_KEY=... node claim-tests/assessment/run.mjs --provider openai          # or --provider gemini, vertex, openai-codex
node claim-tests/assessment/run.mjs --provider openai --only thompson1917-ch03-07
```

Keys stay in the environment of whoever runs it and never enter the repository.

## Tests selected (the headline ones)

thompson1917-ch03-07 (the verdict is already known to turn on the pre-registered age range, from the
two-swarm cross-check), kimura-heterozygosity, maynardsmith-hitchhiking, darwin1859-ch09-03,
thompson1917-ch04-13, darwin1859-ch11-13, fisher-sex-ratio. The four tests whose directory carries the
`--delphi-claims` suffix are this team's attempts; the collaborator's attempts at the unsuffixed paths are
not assessed here.

## Output contract (`faithfulness.json`)

```json
{ "claim_id": "...", "test_dir": "claim-tests/<project>/<dir>", "rubric": "analysis-faithfulness/0.1.0", "role": "A9",
  "assessor": { "provider": "openai|google", "model": "<model id>", "date": "...", "blind": true, "withheld": [...] },
  "scores": { "right_variables": 0.0, "modality_appropriate": 0.0, "assumptions_compatible": 0.0, "rule_discriminates": 0.0, "scope_stated": 0.0 },
  "verdict": "representative | representative-with-caveats | not-representative",
  "reasons": "...", "what_would_change_it": "..." }
```
