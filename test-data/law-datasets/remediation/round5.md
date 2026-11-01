# Round 5: final adjudication

Read `test-data/law-datasets/INSTRUCTIONS.md`, `REMEDIATION.md` and `test-data/law-datasets/validate.mjs`.
For each slice you are given you are the last check before the record is used in views.

1. **Re-verify every source with `added_in_round: 4`** against the live source: identifier resolves, title/authors/year match, the variables are really there, `reported.quote` is verbatim. Correct or drop (move to `dropped`, `dropped_in_round: 5`, `dropped_reason`).
2. **Resolve every flag** on a source (`flags`: `taxon-kingdom-mismatch`, `age-outside-pbdb-range`, `title-differs-from-doi`, `access-url-dead`) and every `flag` text under `taxa[].resolved` / `taxa[].pbdb`: fix the record, or keep it with a one-line reason. Then remove the entry from `flags` and log it as `flag-resolved` or `flag-kept` in your actions (keep a copy under `flags_resolved`).
3. **Deduplicate**: same DOI, same dataset under two ids, or a paper listed twice. Merge, keeping the most complete entry.
4. **Spot-check 10 sources** from earlier rounds that you have not been told about, chosen at random, with the same open-the-source procedure.
5. **Dummy-data lint** (BEST_PRACTICES.md section 2): no fabricated identifiers, no placeholder text, no numbers that disagree between `n`, `measurements` and `reported`.
6. Rewrite `coverage` and `summary` so they describe the final `sources` (counts by verdict, groups, intervals, gaps), and set `gap_note` if fewer than 6 sources remain.
7. Append the round-5 entry (`kind: "cursor-subagent"`, your model id, `counts`, `actions`). Run
`node test-data/law-datasets/validate.mjs --final <law>/<kingdom>` and fix every error (rounds 1 and 3 entries exist from scripts; rounds 2 and 4 from other models).
Reply with, per slice: final source counts by verdict, flags resolved/kept, sources dropped, validation result.
