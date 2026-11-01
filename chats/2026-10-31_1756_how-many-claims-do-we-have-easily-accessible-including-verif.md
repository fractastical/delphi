# how many claims do we have easily accessible including verified claims in the re

- **Started:** 2026-10-31 17:56 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 17:59 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 4
- **Subagents:** 0
- **Transcript ID:** `3153d01b-c7f0-465b-a60c-d3c4edf5fede`

## Conversation

### 2026-10-31 17:56 — Turn 1 (User)

> how many claims do we have easily accessible including verified claims in the repo now?

**Assistant:**

I'll check the headline counts in the README and the MCP overview.

Since the user wants specific counts, I should check the README's current numbers table or the delphi overview for the exact figures.

Let me pull the remaining rows of that table for a fuller breakdown.

The repo has **1,702 claims** in the claim graph, which was rebuilt today at 20:44 UTC. Of those, 194 are verified in some way: 63 are proved theorems and 133 have been tested against data, with 2 claims counted in both groups.

**By source:**

| Source | Claims | Theorems | Tested against data |
|---|---:|---:|---:|
| Aristotle | 512 | – | – |
| Wolfram, *A New Kind of Science* | 321 | – | 59 |
| Levin papers | 310 | – | 2 |
| Thompson, *On Growth and Form* | 291 | 47 (Lean-checked) | 31 |
| Darwin, *Origin of Species* | 247 | – | 41 |
| Math-bio thinkers (Fisher, Turing, Kimura, Hamilton, Maynard Smith) | 21 | 16 (proved in the literature) | – |

**Verified claims:**
- **Theorems:** 63 math claims have an established proof. 47 are Thompson claims checked in Lean 4, and 16 are math-bio claims whose proofs are recorded from the literature.
- **Tested against data:** 133 claims. The verdicts are 78 supports, 25 mixed, 21 refutes and 9 inconclusive. 66 of these tests used data measured on organisms.
- **Pre-registered:** 13 more tests are set up and waiting for data.
- **Neither proved nor tested:** 1,508 claims.

**Published:** 880 of the claims are live as nanopublications on production. The other 822 exist only in the repo, including all 512 Aristotle claims.

There's a small mismatch in the totals. The TriG files in the repo contain 1,756 claims, while the claim graph has 1,702. That suggests about 54 drafts haven't been added to the graph yet.

The full numbers table is in `README.md` under "Current numbers". Every tested claim and its verdict is listed in `test-data/claim-tests/SUMMARY.md`.

I notice a discrepancy worth flagging: the TriG files show 1756 claims while the claim graph only has 1702, so I should mention that gap briefly.

_Tools used: Grep, Shell ×2_

### 2026-10-31 17:58 — Turn 2 (User)

> i think we should create something in the bast practice that publshing the nanopubs to test registery and committing and pushing happen at the saem time

**Assistant:**

I'll add this to step 3 of the short version and as a rule in section 3, and point section 8's manifest rule at it.

I should add a rule in section 3: publishing to test, recording in the manifest, and committing/pushing should all happen together in the same session — never leave published-but-uncommitted or committed-but-unpublished states. I'll edit item 3 of the short version to capture this.

I added the rule to `BEST_PRACTICES.md`: publishing a batch to the test registry, committing it and pushing it now count as one step. I haven't committed the change.

- **Short version, step 3:** now says to publish to the test registry first, and to commit and push the signed files and the manifest in the same step.
- **Section 3 (Publish to the test registry first):** a new paragraph, "Publish, commit and push together", says:
  - Don't leave published files uncommitted or unpushed, and don't commit signed files that were never published.
  - Commit only the batch, not other work in the tree, and put the registry and the number of files in the commit message.
  - If publishing fails partway, commit what reached the registry, record the failures in the manifest, and mention them in the commit message.
  - If the push fails, fix it before starting another batch.
  - Promotion to production follows the same rule.
- **Section 8 (manifest):** now says the manifest is committed and pushed together with the publication.

The working tree already breaks the new rule: signed assessments under `claim-sources/darwin-origin/nanopubs/assessments-signed/` (the `--gpt` and `--grok` files) haven't been committed yet. I didn't check whether they were published to test. If they were, they should be committed and pushed now along with the manifest entries for them.

That git status showing multiple signed-but-uncommitted assessments in darwin-origin matches this situation exactly, so I should point that out.

_Tools used: Grep, Read, StrReplace ×3_

### 2026-10-31 17:58 — Turn 3 (User)

> since i thnk that's one of hte syncing errors

**Assistant:**

Let me check whether those signed Darwin assessments were actually published to test, so we know which way the drift goes.

This sounds like one of the syncing errors mentioned, so I should check whether the darwin files are actually published by looking at the manifest for darwin-origin.

Good, the shell's working directory carried over, so I'm already in the nanopubs directory.

This matches the sync error pattern exactly—494 assessments and the rubric got published to test but the manifest and signed files weren't committed. I want to check whether the signed directory is actually tracked in git or gitignored, so I'll look at the gitignore rules and confirm with git ls-files whether signed/ is being tracked.

That case is confirmed: the Darwin assessments are on test but not in git. Let me check whether other projects have the same drift.

Good, confirmed. Now I want to check if other projects have this same issue, so I'll scan for untracked signed directories and manifest diffs across claim-sources.

You're right, and it's the only case of it in the repo right now. The Darwin assessment batch was published to the test registry this afternoon but never committed or pushed:

| What | On test registry | In the manifest | In git |
|---|---:|---:|---:|
| Signed Darwin assessments (`assessments-signed/`) | 494 | 494 | 0 |
| Signed rubric (`rubric-signed/`) | 1 | 1 | 0 |

The 495 rows recording those publications (published 21:05–21:10 UTC today) are sitting as uncommitted changes in `claim-sources/darwin-origin/nanopubs/manifest.jsonl`. The registry has these nanopubs, but the pushed repo has neither the signed files nor any record that they were published. The unsigned versions of the same files were committed earlier, which makes git look complete when it isn't.

The 566 untracked Aristotle files in `aristotle-biology/nanopubs/unsigned/` are a different case. Nothing for them is in any manifest, so they haven't been published and nothing is out of sync. They're just unfinished work.

To fix the Darwin batch under the new rule, I'd commit and push only these files: `assessments-signed/`, `rubric-signed/` and `manifest.jsonl` from the Darwin project, plus the `BEST_PRACTICES.md` change, with a message like "darwin-origin: 494 assessments + rubric published to test registry". None of the other uncommitted work in the tree would go in. Should I go ahead?

The Aristotle entry seems unsigned and unpublished, which is fine. Since committing and pushing is a meaningful action, I should check with the user before going ahead with the darwin batch rather than assuming agreement.

_Tools used: Shell ×5_

### 2026-10-31 17:59 — Turn 4 (User)

> let's also create an issue on the ontology doc realted to this

**Assistant:**

I'll check the upstream ontology repo's PUBLISHING.md and existing issues so the new issue doesn't duplicate anything.

I'm thinking I should file this in the fractastical/project-delphi-ontology repo using gh issue create, checking PUBLISHING.md for a relevant section to reference and verifying gh auth and existing issues first before drafting the issue body.

Since issue #23 is the related umbrella issue, I'll create a new one referencing it, writing the body to a temp file first and verifying the documentation and enhancement labels exist before creating it.


I checked issue #23 and confirmed it's the umbrella issue for publishing best practice, but nothing yet covers this sync problem. I'll open a new issue linking back to #23.

I opened [project-delphi-ontology#31](https://github.com/fractastical/project-delphi-ontology/issues/31), labelled documentation and enhancement.

- **Problem it describes:** the upstream `PUBLISHING.md` requires a manifest and a pushed generator commit. It never says the signed files and the manifest have to reach git when a batch is published. The issue uses today's Darwin batch as the example: 494 assessments and 1 rubric are on the test registry, while git has neither the signed files nor the manifest rows recording them.
- **Proposed change:** the same "Publish, commit and push together" wording I added to our `BEST_PRACTICES.md`, noting that this repo already follows it.
- **Possible follow-up:** publish scripts that refuse to run unless the batch's files are clean and then commit and push the result themselves, plus a check that flags signed files or manifest rows that aren't in git.
- **Link:** it points to [#23](https://github.com/fractastical/project-delphi-ontology/issues/23), the umbrella issue for publishing best practice. #23 plans CI checks on the committed signed nanopubs, which only work if those files actually get committed.

Still pending: should I commit and push the Darwin batch (the signed assessments, the signed rubric and the manifest) together with the `BEST_PRACTICES.md` change, as described earlier?

I could note this in our best practices doc, but since upstream takes precedence here, it's fine to just mention it briefly rather than dwell on it.

_Tools used: Shell ×2_
