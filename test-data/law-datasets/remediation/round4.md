# Round 4: gap filling

Read `test-data/law-datasets/INSTRUCTIONS.md` (evidence rules and source format) and `REMEDIATION.md`.
For each slice you are given, read `laws.json` (law, claims, variables, kingdom brief) and the record:
`sources`, `coverage` (groups, intervals, gaps), `flags` on sources, `dropped` (don't re-add anything dropped for a
non-resolving identifier), and the taxa/ids resolved in round 3.

1. Tabulate what the record covers: taxon groups (class/order level), geologic intervals (fossils), methods, decades, data holders.
2. Find the biggest holes against the kingdom brief and `coverage.gaps`: major clades, intervals, biomes or methods with no source.
3. Search for sources to fill them (same APIs and rules as scouting; log each search in `search_log`, appending to the
   existing log) and add **10 to 30 new sources** in the same format. Every addition: `added_in_round: 4`, `suggested_by: []`,
   checked against the live source (`checked.method` starting "r4 gap-filler:"), `reported` only if you read the text.
   Don't duplicate an existing `id`, DOI or URL. Include sources unfavourable to the law as well as favourable ones;
   never label one as supporting or refuting.
4. Update `coverage` for the new sources. Append the round-4 entry to `remediation` (`kind: "cursor-subagent"`, your model id,
   `counts.added`, an `actions` item per source). Run `node test-data/law-datasets/validate.mjs <law>/<kingdom>`.
Reply with, per slice: sources added by verdict, the groups/intervals now covered, remaining gaps.
