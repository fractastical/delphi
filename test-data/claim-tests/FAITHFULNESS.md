# A9 faithfulness assessment of data tests

The faithfulness assessor (role A9 in `AGENTS.md`) answers one question about a finished data
test: **does this analysis measure what the claim asserts?** Right variables, an appropriate
modality, and assumptions compatible with how the data were collected. It does not re-run the
test, re-derive the verdict or judge whether the claim is true; it judges whether the number the
test produced is about the claim. A `not-representative` verdict means the evidence does not
count, whatever the numbers said. That verdict is a finding to publish, not a problem to fix
quietly. Tracks [issue #40](https://github.com/fractastical/delphi/issues/40).

## Rules

1. The assessor is never the builder and never the builder's model provider. The tests were
   written by Claude models (Anthropic); A9 runs on another provider and the model is named in
   the output.
2. Read only: the claim (label, statement, verbatim quote, chapter, stated scope), the test
   directory (`result.json`, the analysis script, anything under `derived/`, any README or
   pre-registration note in that directory). Do not read other tests, assessments, the forum,
   or the web. Do not run code.
3. Judge the test against the claim **as the author stated it, within the author's scope**. A
   test that refutes a modern reinterpretation the author did not make is not representative of
   the author's claim. A test that is narrower than the claim (one taxon, one proxy, one period)
   can still be faithful-with-narrower-scope if the narrowing is stated in `interpretation`.
4. Three verdicts:
   - `faithful`: the measured quantity is the quantity the claim is about, on data of the kind
     the claim is about, and the pass/fail criterion matches the claim's own standard.
   - `faithful-with-narrower-scope`: the measurement is about the claim, but covers part of its
     scope (taxa, period, conditions) or uses a proxy the test itself declares; the verdict
     holds for that part only.
   - `not-representative`: the measurement is of something else (a different variable, a
     reinterpretation the author did not make, data whose collection violates an assumption of
     the claim, or a criterion that no outcome of the data could meet or fail).
5. Say what would change the verdict: a concrete variable, dataset or analysis change.

## Output: `test-data/claim-tests/<project>/<claim-id>/faithfulness.json`

```json
{
  "claim_id": "darwin1859-ch09-03",
  "assessor": { "model": "GPT-5.6 Sol", "provider": "OpenAI", "role": "A9 faithfulness" },
  "assessed_at": "2026-11-01T06:00:00Z",
  "test_verdict_seen": "refutes",
  "verdict": "faithful | faithful-with-narrower-scope | not-representative",
  "confidence": 0.0,
  "variables": { "claim_asserts": "…", "test_measures": "…", "match": "exact | proxy | different" },
  "modality": { "appropriate": true, "note": "…" },
  "assumptions": { "compatible": true, "note": "…" },
  "scope": { "claim_scope": "…", "test_scope": "…", "narrower": false },
  "reasons": ["…"],
  "what_would_change_it": "…",
  "files_read": ["result.json", "analysis.py"]
}
```

Integers are not required; `confidence` is the assessor's confidence in its own faithfulness
judgment, in [0, 1]. One file per assessor per test: the first assessor writes
`faithfulness.json`; a second opinion from another provider, blind to the first, goes in
`faithfulness.<assessor>.json` (e.g. `faithfulness.grok.json`). Every `not-representative`
verdict gets a second opinion before it is reported as a finding; where the two disagree the
test is `contested`, not cleared. The build (`node scripts/site/build-claim-graph.mjs`) reads
all of them into `docs/claims.json` as `faithfulness` (verdict per assessor, and `agreed` /
`contested`) and counts them in [SUMMARY.md](SUMMARY.md).
