# are we using java nanopub?

- **Started:** 2026-10-31 13:43 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 13:45 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 2
- **Subagents:** 0
- **Transcript ID:** `10132050-5c24-43ca-baee-aeb9116895e1`

## Conversation

### 2026-10-31 13:43 — Turn 1 (User)

> are we using java nanopub?

**Assistant:**

Let me check line 99 of the best practices for context on this.

Let me check what np refers to here.

No, we're not using nanopub-java. The pipeline signs and publishes with **nanopub-js** (`@nanopub/nanopub-js`). It's imported in every publish script:

- `darwin-origin/build/publish.mjs`
- `thompson-growth-form/build/publish.mjs`
- `wolfram-nks/build/publish.mjs`
- `cell-geometry/build/publish.mjs`
- `math-bio-claims/publish-test.mts` and `publish-production.mts`
- `darwin-origin/build/introduce-key.mjs`, which uses `createIntroNanopub` to register the ORCID key

Java does come up in two places, both as documentation:

- `BEST_PRACTICES.md` (line 99) says to run `np check` from nanopub-java on signed files before publishing to the test registry.
- `README.md` lists nanopub-java as a related tool.

That `np check` step probably isn't using Java on your machine. The `np` command on your PATH (`~/.local/bin/np`) is the Python **nanopub-py** CLI, installed with pipx, not the Java one. Java is installed at `/usr/bin/java`, but I found no nanopub-java jar or wrapper. So if anyone has been running `np check`, they've been running the Python version.

If you want Java's validator to be the actual check, you'd need to install the nanopub-java jar. If you're happy with the current setup, `BEST_PRACTICES.md` should be updated to name nanopub-py, or nanopub-js's own `verifySignature`, which `publish-production.mts` already uses.

The np command on PATH is actually nanopub-py, which is Python-based -- older versions relied on a bundled Java jar, but newer ones are pure Python, though this detail isn't critical to the answer.

_Tools used: Grep ×2, Read, Shell ×2_

### 2026-10-31 13:45 — Turn 2 (User)

> it seems like we should update best practices then

**Assistant:**

I'm trying to recall nanopub-py's CLI commands—whether there's a `check` subcommand alongside setup, sign, and publish, so I should just run the help command to verify.

I should edit line 99 to reference both nanopub-py's `np check` and nanopub-js's verifySignature within the publish script, and double-check whether the README also lists nanopub-js around lines 115-125.

I need to check whether the claim that publish scripts run it before upload actually holds—only publish-production.mts seems to do that, so I should verify the other scripts too.

I updated `BEST_PRACTICES.md` and `README.md` so they name the tools we actually use.

The validation step in section 3 of `BEST_PRACTICES.md` (line 99) used to say "`np check` (nanopub-java)". It now reads:

```markdown
- `np check` (the nanopub-py CLI, `pipx install nanopub`) passes on the signed files, and
  nanopub-js `verifySignature` accepts them (the publish scripts run it before upload).
```

Before writing that, I checked two things:
- **`np check` is real in the Python CLI.** The installed nanopub-py `np` has a `check` command for validating signed nanopubs, so the step works as written.
- **The publish scripts really do verify.** All the main publish scripts call nanopub-js `verifySignature` before uploading: Darwin, Thompson, Wolfram, cell-geometry, and both math-bio-claims scripts.

In the "Libraries and tooling" list in `README.md`, I added nanopub-js first, since it's what signs, verifies and publishes. I also noted that nanopub-py's `np` CLI is what we use for `np check`. I left nanopub-java in the list as a general reference.

Good, all the main publish scripts check out and the repo URL is correct.

_Tools used: Grep ×2, Read, Shell ×2, StrReplace ×2_
