# README, best-practice guide and project goals

- **Started:** 2026-10-30 18:38 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-30 19:24 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 7
- **Subagents:** 0
- **Transcript ID:** `3eb906a8-fa17-4377-bc46-c211f956a5f4`

## Conversation

### 2026-10-30 18:38 — Turn 1 (User)

> create a readme explaning that this has been created for science claw hack @ MIT  and linnk the project delphi ontology (https://github.com/fractastical/project-delphi-ontology/pulls) and nanopub links for how to query nanopubs

**Assistant:**

I'll take a quick look at the repo to see what's here before writing the README.

Let me take a quick look at the repo first.

Since the repo is empty, I'll draft a README covering the key Nanopub resources—Nanopub Query, Nanodash, the official docs, the nanopub-py library, and the SPARQL endpoint.

Let me make sure the links actually resolve.

Let me quickly verify the links work using curl.

I wrote `README.md` at the repo root. All of its links currently open; I checked each one and removed a docs link for the Python library that returned a 404.

The README has three parts:

- **Intro:** says the project was created for Science Claw Hack @ MIT.
- **Related projects:** links to the [Project Delphi Ontology](https://github.com/fractastical/project-delphi-ontology) repo and its [open pull requests](https://github.com/fractastical/project-delphi-ontology/pulls).
- **Querying nanopubs:**
  - **Web tools:** [Nanodash](https://nanodash.knowledgepixels.com/) for browsing nanopubs and [Nanopub Query](https://query.knowledgepixels.com/) for running database-style queries against them.
  - **Example query:** a short sample that lists the 20 most recent nanopubs, with a pointer to the [nanopub-query docs](https://github.com/knowledgepixels/nanopub-query).
  - **Code libraries:** [nanopub-py](https://github.com/fair-workflows/nanopub) for Python, [nanopub-java](https://github.com/Nanopublication/nanopub-java) for Java, and the [nanopub registry](https://github.com/knowledgepixels/nanopub-registry).
  - **Background reading:** [nanopub.net](https://nanopub.net/) and the [nanopublication guidelines](https://nanopub.net/guidelines/working_draft/).

I haven't run the example query against the live service. The repo has no commits yet, and I left the README uncommitted.

_Tools used: Shell ×2, StrReplace, Write_

### 2026-10-30 18:39 — Turn 2 (User)

> ok push

**Assistant:**

The README is now on GitHub at [fractastical/delphisci](https://github.com/fractastical/delphisci). It's the repo's first commit on `main`, with the message "Add README for Science Claw Hack @ MIT". Local `main` now tracks `origin/main`, so later `git push` and `git pull` commands will work without extra arguments.

_Tools used: Shell ×2_

### 2026-10-30 18:43 — Turn 3 (User)

> let's bring our own best practice guide into this repo based on what is in project delph ontology

**Assistant:**

I'll look at the Project Delphi Ontology repo to find its best-practice guidance.

I should check the project-delphi-ontology repo for their best practice guide, either by cloning it locally to a temp directory or checking if it's already available.

No file is literally named "best practices", so I'll search for that phrase, check the open PRs, and read the main guidance docs.

There's no single dedicated best-practice file, so I should search for mentions of "best practice" and check key docs like README, ONTOLOGY.md, PUBLISHING.md, and the nanopubs/pipeline/queries-views READMEs, plus any open PRs proposing a guide.

PUBLISHING.md looks like the right source for best practices, along with PR #26 on the 12-step loop. Since delphisci is an empty hackathon project, I should adapt the core rules into a BEST_PRACTICES.md there, pointing back to the upstream repo as the source of truth while stripping out anything too project-specific like the morphology details.


I found the upstream publishing guide (PUBLISHING.md from PR #24), plus an open PR #26 documenting a 12-step loop. I'll review PR #26 before adapting it.

I'm drafting BEST_PRACTICES.md tailored to delphisci's hackathon context, treating the upstream repo as the source of truth and pointing commands to its tools like cloning the ontology repo and running lint. I want to cover querying guidelines—no inference, enumerating legacy spellings, using canonical namespaces—plus ontology usage rules like reusing standard terms, treating Claim as a belief, using scores rather than probabilities, and noting the 2.0 attribution model.

I should avoid citing test URIs, never commit keys, and treat morpholib-specific scripts as examples rather than hardcoded requirements. For the lint command, I want to verify the exact syntax by checking the pipeline README around lines 160-190 before stating it definitively.


I've gathered the key references — PUBLISHING.md, ONTOLOGY.md, the query notes, and the 12-step loop page from PR #26. Now I'll check the exact lint setup steps before writing.

I'll draft a moderately sized BEST_PRACTICES.md, around 150 lines, and link it from the README. I'll leave it uncommitted since the user hasn't asked to push yet, following the earlier pattern of waiting for that explicit cue.


I'll write `BEST_PRACTICES.md`, adapting the upstream guide for our hackathon repo while adding the ontology and query rules relevant to nanopubs.

Let me check the new upstream links resolve.

I'm confirming the "Dataset convention" heading generates the anchor #dataset-convention on GitHub, so the link should resolve correctly.

I added `BEST_PRACTICES.md` to the repo and linked it from the README. It's adapted mainly from the ontology repo's [publishing guide](https://github.com/fractastical/project-delphi-ontology/blob/main/PUBLISHING.md), and it says that guide is the source of truth if the two ever disagree.

**Carried over from upstream:**
- **The 12-step build-and-audit loop**, including two rules: whoever built the work never scores it, and AI-audited results aren't called "expert-validated."
- **Checks for fake or placeholder data**, plus the commands to run upstream's lint script on a batch before it's published.
- **Publishing:** everything goes to the test registry first and is promoted to production only after review.
- **Sources and datasets:** every claim must cite its data, and each dataset gets its own nanopub.
- **Never edit what's published:** fix it by superseding or retracting, using the same signing key.
- **Records and keys:** keep a manifest of every publication, and never commit signing keys.

**Added for this repo** (drawn from upstream's ontology reference and query notes):
- **Using the ontology:** use the current version-2.0 namespaces and attribution pattern, and reuse standard vocabulary terms where they fit. Keep rubric scores, evidence weights and probabilities as separate values, and don't use the deprecated terms.
- **Querying:** the public query service doesn't apply the ontology's equivalence rules. Queries therefore have to list every old and new spelling of a term, and should use upstream's published queries where possible.
- **Hackathon-specific:** production is off by default during the hack, and test-registry links shouldn't appear in demos or slides.

I drew on the 12-step loop page from the still-open [PR #26](https://github.com/fractastical/project-delphi-ontology/pull/26), so that part may need updating if the PR changes before it merges. I checked that all the new links open.

Both files are uncommitted. Say the word and I'll commit and push.

That endpoint returned 200, so it seems morpholib is accessible publicly. Good enough confirmation, no need to commit to anything further.

_Tools used: Read ×6, Shell ×5, StrReplace, Write_

### 2026-10-30 18:45 — Turn 4 (User)

> push

**Assistant:**

The best-practices guide is pushed to `main` on [fractastical/delphisci](https://github.com/fractastical/delphisci) as commit `38f1ea8`. That commit adds `BEST_PRACTICES.md` and the README link to it.

_Tools used: Shell_

### 2026-10-30 18:52 — Turn 5 (User)

> state our goal to find the fundamental theorems of biology

**Assistant:**

I'll add a "Goal" section near the top of the README.

I'll add a concise Goal section to the README, keeping it tied to the ontology/Lean formal-verification convention without overclaiming. I'll leave the change uncommitted and offer to push rather than doing it automatically.

I added a "Goal" section near the top of the README stating that our goal is to find the **fundamental theorems of biology**. It describes them as general laws that hold across organisms, scales and systems, stated precisely enough to test.

Below that, the section lists the four steps toward that goal:

- **Extract** candidate laws from papers as claims, each traced to its source papers and datasets.
- **Formalize** them as Lean 4 theorems where possible, using the ontology's formal-verification terms.
- **Test** them against real data and record the evidence and our assessments.
- **Publish** each step as a nanopub so it can be cited, queried and challenged.

I also added one caveat: a machine-checked proof shows a theorem follows from its assumptions, not that living systems meet those assumptions. That follows the ontology's own warning that a Lean proof checks the mathematics, not the biology.

The existing one-line description of the project now sits under its own "Approach" heading. The change is uncommitted; say "push" and I'll commit and push it.

_Tools used: Read, StrReplace_

### 2026-10-30 18:53 — Turn 6 (User)

> push

**Assistant:**

The Goal section is now on `main` at [fractastical/delphisci](https://github.com/fractastical/delphisci), in commit `adb3218`.

That wraps it up.

_Tools used: Shell_

### 2026-10-30 19:24 — Turn 7 (User)

> i think we should simulatate othe organisms as well

**Assistant:**

I read this as adding simulation across many organisms to the README's plan, so I'll add it to the Goal section's steps.

The phrase "simulate other organisms as well" is ambiguous since the repo has no simulation code—it could mean testing candidate laws across multiple species rather than just one. I'll interpret this as expanding the README's approach to cover simulating across various organisms, and just make a reasonable edit rather than asking for clarification.

Without inventing a specific list of organisms, I'll add a bullet noting that candidate laws should be tested across a range of species rather than a single model system, comparing against each organism's real data—since a law only holding in one organism isn't truly fundamental. I should also flag that the dataset needs to match the organism in question.

I added simulation across many organisms to the README's Goal section. I took this as a change to the plan, since the repo doesn't have any simulation code yet.

- **New step:** simulate candidate laws across many organisms, not just one model system. The reason given is that a law that holds in only one organism isn't fundamental.
- **Updated testing step:** testing against real data now happens for each organism.
- **Added to the caveat:** each organism's simulation is checked against that organism's own data, not data borrowed from another species. Upstream's best-practice guide cites a real case of this mistake: ant and bee claims that cited a fish dataset.

I didn't name specific organisms. If you have some in mind, I can list them as starting points.

The change is uncommitted; say "push" when you want it up.

_Tools used: StrReplace ×2_
