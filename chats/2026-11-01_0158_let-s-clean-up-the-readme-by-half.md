# let's clean up the readme by half

- **Started:** 2026-11-01 01:58 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 02:00 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `f6538175-98bd-46d4-968a-7f8408742736`

## Conversation

### 2026-11-01 01:58 — Turn 1 (User)

> let's clean up the readme by half

**Assistant:**

The README is at 223 lines and I want to trim it down to around 110, keeping the logo, title, goal, MCP info, progress markers, and a condensed agent comparison section while cutting back the wings and sibling repos content rather than removing it entirely.

I should condense the approach, layout, best practices, forum, and related sections too, trimming examples but keeping short links, while making sure the numbers block stays untouched since the script regenerates it based on specific markers.

I'm noticing the repo now has an engine/ directory, so I should check whether the root README's links, like claim-sources/, still point to valid paths or if they're referencing an outdated structure.

The repo's been restructured into engine/, so paths in the README like assets/ have likely moved to engine/assets/. I should check the actual locations of things like claim-sources and test-data before writing any links, to make sure what I reference is accurate.

Since the restructure is still in progress with engine/ and site/ directories, I should update the README's relative links to point to engine/ paths where those files actually exist, like engine/claim-sources and test-data/, rather than the stale ones.

I'll leave the auto-generated numbers block untouched since the script regenerates it anyway, even though its internal links may look stale for now. Now I'm drafting the new README, aiming for roughly 105 lines.

Now I'll write the condensed version, keeping the generated numbers block byte-for-byte so the build script still works.

I cut `README.md` from 223 lines and about 2,460 words to 119 lines and about 1,120 words. The old version is saved at `/tmp/README.old.md`, and `git diff` shows the changes.

**What I cut**
- **Goal and MCP:** shortened, with the same content.
- **Progress:** the three illustrated snapshots are now one-line links instead of embedded images. The agent-comparison paragraph is a single sentence.
- **Wings:** the three-bullet "what has and has not been shown" and the closing paragraph are down to two sentences. The design-decision table is kept, with shorter cells.
- **Sibling repos:** Evolve and Frontier are two bullets each. I kept the caveats (conditional certificates, unsigned drafts, the fish isn't a validated organism, no swarm advantage established).
- **Layout, best practices and forum:** merged into the layout section.
- **Related projects:** the Evolve and Frontier entries now just point back to the sibling section.
- **Nanopub resources:** the example SPARQL query and the long link lists are gone. They're now a short bullet list of links.

**What I kept as is**
- The `numbers:start`/`numbers:end` block is byte-for-byte unchanged, so `build-claim-graph.mjs` can still regenerate it. Its internal links (`test-data/...`, `docs/claims.json`) are stale after the `engine/` move. They'll stay stale until that script is updated.

I also repointed the other links to the new layout: `engine/...` for most paths, `site/team/team.gif` for the GIF, and `engine/assets/...` for the images. I checked that the targets exist. The hosted URLs still use `/docs/team.html`, which I didn't touch.

I haven't committed anything.

Word count checks out at 45% of the limit, which is good. The numbers block looks fine too, even though some internal links are stale, so this is done.

_Tools used: Grep ×2, Read, Shell ×5_
