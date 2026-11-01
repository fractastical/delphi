# should we have a citations folder or doc maybe in the main are aor in teh readme

- **Started:** 2026-11-01 12:03 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 12:03 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `d1d2f4ca-b4b4-4f2c-ab8f-6c936756c2e4`

## Conversation

### 2026-11-01 12:03 — Turn 1 (User)

> should we have a citations folder or doc maybe in the main are aor in teh readme?

**Assistant:**

I'll look at how citations are stored now and what the README already points to, so the recommendation matches the repo rather than adding a second place for the same thing.

A short pointer in the README is enough. A new citations folder, or a bibliography pasted into the README, would be a second copy of records that already have a home.

Citations are already stored next to the thing they support:

| What is being cited | Where it lives |
|---|---|
| Prior work on the project itself | `research/prior-art/works.json`, with the reading in `REPORT.md` and the searches in `SEARCHES.md` |
| The book or paper a claim was taken from | `claim-sources/<project>/inputs/` |
| Whether the modern literature already answers a tested claim | `test-data/claim-tests/openresearch/` and each test's `openresearch.json` |
| A dataset | the `bibliographic_citation` field on that dataset file |

Those files are the record: each identifier was returned by a search or a fetch. A folder that restates them, or a list typed into the README, would go stale the first time one of those files changes. The README is already the tour; the layout section is the right place for three or four lines that name the table above.

The one citation that does not exist yet is how someone should cite this repository. That belongs at the root as `CITATION.cff`, which GitHub shows as "Cite this repository". It is a single record for DELPHI, not a bibliography.

_Tools used: GetDynamicTools, Glob ×7, Grep ×5, Read ×7_
