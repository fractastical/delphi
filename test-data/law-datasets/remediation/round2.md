# Round 2: blind relevance audit

You audit scouting records you did not build. Read `test-data/law-datasets/INSTRUCTIONS.md` (evidence rules)
and `test-data/law-datasets/REMEDIATION.md` first. Work only on the slices you are given.

**Blind.** Read `laws.json` (the law, its claims, `variables`, the kingdom brief) and the record's `sources`.
Do NOT read the record's `summary`, `coverage`, `remediation`, or the queue file; they are the builder's opinion.

For every entry in `sources`:
1. Open it (`curl -sL` the `url`, `access_url` or the DOI via `https://doi.org/<doi>` with `Accept: application/vnd.citationstyles.csl+json`, or an API such as Crossref, OpenAlex, DataCite, Dryad, Zenodo, GBIF, PBDB, Europe PMC; read the abstract or metadata). 
2. Check: is it the work the title/authors/year say it is? Does it measure or hold the variables listed in `measurements`? Do the `taxa` and `geologic_age` match? Is `n` as stated? Is the `kingdom` right for this slice (a fossil source in a plants slice is fine if it is a fossil plant slice item; wrong kingdom is not)?
3. If `reported` is set, find the quote in the text you fetched. Not verbatim or not found: set `reported` to `null` (or replace it with a verbatim quote you read) and log it.
4. Correct `verdict`, `scope`, `n`, `relevance`, `variables_present`/`variables_missing` where wrong. A source that is a different work, whose identifiers you cannot confirm, that does not hold the stated variables at all, or that is not about this kingdom's organisms, is dropped: move it to `dropped` with `dropped_in_round: 2` and `dropped_reason`.
5. Update `checked` (`at`, `method` starting "r2 audit:", `http_status`) for what you did.

You may not add sources (round 4 does that). You may not change `claims` to a claim outside the law.
Append the round-2 entry to `remediation` (see REMEDIATION.md; `kind: "cursor-subagent"`, your model id). Run
`node test-data/law-datasets/validate.mjs <law>/<kingdom>`. Reply with counts per slice: verified, corrected, dropped, and the three worst problems you found.
