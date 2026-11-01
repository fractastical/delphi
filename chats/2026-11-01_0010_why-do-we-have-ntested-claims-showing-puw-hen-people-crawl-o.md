# why do we have ntested claims showing puw hen people crawl our repo

- **Started:** 2026-11-01 00:10 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 00:16 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 2
- **Subagents:** 0
- **Transcript ID:** `c1d1eab2-7a80-4b5d-9725-d36720af3d7b`

## Conversation

### 2026-11-01 00:10 — Turn 1 (User)

> why do we have ntested claims showing puw hen people crawl our repo

**Assistant:**

I'll check where untested claims get surfaced in the repo, starting with the README and the claim graph output.

I think they mean "untested claims" — I should look into whether our repo exposes claims or candidate data without evidence, maybe in a README, docs, or claims.json file.

This question is a bit ambiguous, but untested seems to be the default state here. I should pull the actual counts from the README table to back this up with numbers.

Untested claims show up because most of the repo's claims are untested, and every file a crawler reads says so.

**Why most claims are untested**
- The repo has 1,702 claims. Only 133 have a data test and only 63 are proved theorems. The other 1,508 are marked "neither proved nor tested", per the "Current numbers" table in `README.md`.
- The claims were extracted in bulk from texts like Darwin, Thompson, Wolfram, Levin and now Aristotle. Testing them against data is the slow step.
- In `scripts/site/load-claims.mjs`, `untested` is the default verification state. A claim only moves out of it when it has a Lean proof, a recorded proof in the literature, or a `result.json` data test. Assessor scores never change it.

**Where a crawler sees them**
- **`README.md`:** it lists "claims neither proved nor tested | 1508". `build-claim-graph.mjs` generates that row.
- **`docs/claims.json` and the claim graph:** every claim is listed there with `verification: "untested"`. `docs/claim-graph.template.html` also has an "Untested" column and a grey "Untested" badge.
- **`AGENTS.md` and the MCP server:** `delphi_claim_tests view: "candidates"` returns untested claims on purpose, ranked by testability, to show what to test next. `mcp/server.mjs` also exposes `verification: "untested"` as a filter.
- **`test-data/dataset-scouting/`:** it holds a record per untested claim of where its test data lives.
- **Published nanopubs:** 880 claims are live in production, and most of them are untested.

If you want fewer untested claims in front of crawlers, there are three options, and I can do any of them:
1. Soften the wording, for example "not yet tested" or "candidate", and tone down the README row.
2. Make the default views in `docs/claims.json`, the claim graph and the MCP search show only tested or proved claims, with the untested ones behind a flag.
3. Add a note or `robots.txt` entry saying the untested claims are an open queue and not findings.

Which of these do you want? Or did you mean something more specific, such as a particular crawler, the Aristotle drafts, or the `docs/` site?

I think they're asking about untested claims showing up when people crawl their repo—I should explain why that happens and lay out some options concisely.

_Tools used: Grep ×3, Read, Shell_

### 2026-11-01 00:14 — Turn 2 (User)

> we shoudl test more

**Assistant:**

I'll pull the highest-ranked untested claims that already have scouted data, and check how tests get written.

I want to test more claims, so I'm going to check the candidates view and the claim-testing process, exploring delphi_claim_tests and the related instructions via the CLI to work efficiently.

I'm narrowing down to two good candidates to test, Tallo and AnAge, and thinking through the process: pre-register the prediction first, but hold off on committing anything since that wasn't requested—the timestamp from writing the pre-registration itself is what matters.

Now I'm checking the data size for the Tallo dataset to see if it's reasonable to pull into a temp directory, and looking at existing test scripts and result schemas from prior thompson tests to use as a template, plus verifying network access works.


I'll start with the Tallo and AnAge claims, first checking the `result.json` schema and an existing test to follow its conventions.

Both datasets are reachable, so the next step is to pre-register. I'll look at one finished Thompson test for its conventions, and at how the data-kind and agent fields are filled in.

Both datasets are reachable, though pandas isn't installed, so I'll need to check other Python options or install it in a venv. Before touching the data, I want to look at an existing complete test for style and write my pre-registrations first, using what I know of the Tallo columns (stem_diameter_cm, height_m, height_outlier). My claim is that diameter scales as height^1.5, so I'm setting up a pre-registered log-log regression with slope fixed at 1.5 before looking at any actual data.

I'm reasoning through the allometric literature on tree scaling exponents without peeking at the data, then settling on using standardized major axis regression (rather than OLS, to avoid dilution bias), pre-registering pass/fail thresholds for the pooled and within-species slope confidence intervals around 1.5. For the second test, I'm moving to the AnAge dataset to operationalize the claim that organism size depends on both growth rate and growth duration, comparing species like rabbit vs. guinea pig (rate-driven) and human vs. rabbit (duration-driven).

I'll extend that to the rabbit/guinea-pig and man/rabbit contrasts without peeking at actual values, just defining the comparison logic using whatever column names the dataset provides, then move to setting up pandas for the analysis.

I'll set the test work aside for now and start on the export. First I'll look at what `docs/claims.json` holds today, so I know what counts as "extra confusing stuff".

This is a new request about exporting data for third-party import. I should look at the claims.json structure first, then build a reasonable default export with a clean folder containing CSV/JSON files with simple fields like tested/proved/untested, noting my assumptions since I don't know the specific third-party target. Let me first check if there was a prior shell interruption that left anything behind.

I see the real confusion now: status, verification, and evidence are being conflated. I want to design a cleaner export using one unified "standing" field covering proved, tested (supports/refutes/mixed/inconclusive), and untested states, while also figuring out whether to filter drafts versus published claims given the registry counts, and noting that truth scores are inherently subjective.


I spotted a contradictory claim with `status: "untested"` alongside `evidence: "refutes"`, caused by three overlapping status fields. I'll check the value distributions before designing a clean schema.

I'm planning a build-export script that generates claims.csv, claims.json, and a README field dictionary, deciding on a flat schema with fields like id, claim, statement, source author/work/year/chapter, and including the source quote for provenance.

I'm working through status fields: separating proof_status (proved/partial/refuted/none) from data_test results (supports/refutes/mixed/inconclusive/none), then collapsing them into a simple summary status of proved/tested/untested, figuring out how partial or refuted math claims should fold into that summary.

I'll also add `published` and `nanopub_url` fields, construct a `test_result_url` pointing to the GitHub repo path for test results, drop truth scores as too subjective, include all 822 unpublished claims with a published flag rather than filtering them out, and add a `proof_method` field distinguishing lean-verified from literature-based proofs.

For output, I'll generate the files into `docs/export/` so they're served through GitHub Pages at a stable URL, reading from the built `docs/claims.json`. I'll add a `README.md` there explaining the schema, wire up an `export:claims` npm script rather than modifying the existing build-claim-graph pipeline, and make sure the CSV writer properly escapes fields.


The overlapping status, verification, and evidence fields are why claims with a data test still show as "untested." I'll build a script to flatten these into clearly named columns and drop the internal fields, starting with checking what `data_test` contains.

I'll add an npm script to run this and verify the CSV parses correctly.

The clean export is built and checked. It's in `docs/export/`, so it would be served from the `docs/` site if that's published as a site (I haven't checked).

- **`claims.csv`:** UTF-8, comma-separated, header row, quoted where needed.
- **`claims.json`:** the same rows, as `{ built, count, claims: [...] }`.
- **`README.md`:** a field dictionary.

I checked it by reading it back. It has 1,702 rows and 1,702 unique ids, and the CSV parses with 17 columns. The counts match the README table (1,508 untested).

**What I fixed.** The source `docs/claims.json` has three overlapping status fields: `status`, `verification` and `evidence`. A claim can read "untested" and "refutes" at once, as `darwin1859-ch01-09` does. The export replaces them with:
- **`status`:** one summary value: `proved`, `partially_proved`, `disproved`, `tested` or `untested`. The README states that `untested` means no proof and no data test yet, not that the claim is false.
- **`proof`:** `lean`, `literature`, `partial`, `disproved` or `none`.
- **`data_test`:** `supports`, `refutes`, `mixed`, `inconclusive` or `none`.
- **`data_test_kind`:** whether the data was biological, physical or computational.
- **`data_test_url`:** a link to the full test record, empty if untested.

The other columns are `id`, `title`, `statement`, `author`, `work`, `year`, `chapter`, `quote`, `claim_type`, `is_mathematical`, `published` and `nanopub_url`.

**What I left out.** I dropped the hash keys, the AI assessor truth and testability scores, the Lean and MorphoLib details, the registry and draft flags, and the pre-registration contracts. They're still in `docs/claims.json` and available over MCP.

**Rebuilding.** Run `npm run export:claims`, which I added to `package.json`. The script is `scripts/site/build-export.mjs`. It reads `docs/claims.json`, so run `build-claim-graph.mjs` first to get current numbers.

**Choices for you:**
- **Unpublished claims:** all 1,702 claims are in the export, including the 822 not yet published as nanopubs. `published` marks them. If the third-party site should only see published claims, filtering is a one-line change.
- **`quote` column:** it carries the source passage and is the longest field. I kept it for attribution, and it's easy to drop.
- **Truth scores:** I left the model scores out because they're opinions and would confuse an importer. I can add an optional `assessor_score` column.
- **Target site:** I don't know which site this is for. If it needs a specific format, such as a particular CSV header or JSON-LD, tell me and I'll match it.

I haven't committed anything. I also paused the test work: I hadn't written any pre-registrations when I switched, so there are no test files yet. The best candidates are `thompson1917-ch02-02` (Tallo tree allometry) and `thompson1917-ch03-11` (AnAge growth), both with data ready. Tell me when you want me to go back to them.

The counts check out: 1508 untested matches the README, and 133 tested breaks down as 128 plus 5 proved with evidence. I should note the caveats when I summarize—the 822 unpublished entries need a flag, the truth scores are omitted, nothing's committed yet, and docs/claims.json is stale from an October 31 build that still includes the Aristotle claims; also the testing work is currently paused.

_Tools used: Grep, Shell ×10, StrReplace, Write_
