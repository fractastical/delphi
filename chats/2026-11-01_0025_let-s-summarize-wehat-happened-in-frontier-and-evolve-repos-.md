# let's summarize wehat happened in frontier and evolve repos in our readme and li

- **Started:** 2026-11-01 00:25 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 00:35 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 2
- **Subagents:** 0
- **Transcript ID:** `47e516d0-9efe-4612-9366-84dfba174b86`

## Conversation

### 2026-11-01 00:25 — Turn 1 (User)

> let's summarize wehat happened in frontier and evolve repos in our readme and link them

**Assistant:**

I'll start by looking at the README and finding what it already says about the frontier and evolve repos.

I'll start by exploring the repo README to find any mentions of frontier and evolve repos.

I'm not finding any local repos named "frontier" or "evolve" offhand, so I should check COLLABORATIONS.md and search for related fractastical repos or MCP references to figure out what these refer to.

I don't see an obvious frontier/evolve repo yet, so I should search transcripts and the frontier MCP, check the full fractastical repo list, and look across other orgs to list out possible names.

There's a lead: `kganjam/delphi-evolve`. I'll check that transcript and the frontier server.

The repos are `kganjam/delphi-evolve` and `kganjam/delphi-frontier`. Next I'll read what happened in each.

Next I'll pull the outcomes (handoff, status, build board, live catalogue counts) so the summary uses real numbers.

I still need to check a few more specifics: the pivot results in evolve's HANDOFF/STATUS, frontier's BUILD.md status, catalogue counts, and how delphisci connects via the delphi MCP and claims, plus the rethink-control piece. Let me quickly read through STATUS.md, HANDOFF.md, BUILD.md, and the frontier catalogue.

I notice Frontier references a claim with an upstream claim ID that looks like it could be from Delphi, but I'm not certain of that link. Let me check the repo to see if Frontier actually imports Delphi claims directly.

I have what I need. I'll add a section after the Nebius block and extend "Related projects" with links.

I'll add a "Sibling projects" section to the README, placing it after the Nebius snapshot and before Approach, and ignoring the inline line-number artifacts in the file view since those are just display markers, not actual content.

I added something that wasn't requested, so I should pull it back out to stay within scope.

I added a "Sibling repositories: Evolve and Frontier" section to `README.md`, just before "Approach". I also added both repos to "Related projects". I haven't committed anything, and I didn't re-run either repo's checks, so the numbers are theirs as of today.

I found the two repos through the earlier agent chats and GitHub: [`kganjam/delphi-evolve`](https://github.com/kganjam/delphi-evolve) and [`kganjam/delphi-frontier`](https://github.com/kganjam/delphi-frontier). Both are Kris Ganjam's. If you meant different repos, tell me and I'll swap them.

**Evolve (Darwin's Bridge, Oct 31)**
- It's a prototype for deciding which experiment would justify the next step in a protein's evolution, built on the measured TrpB enzyme landscape.
- Delphi claims (Kimura, Fisher, Turing) became hand-written checks that decide whether a computation runs or is refused.
- A LazySP-style baseline certified 96/100 episodes against 78/100 for the original model-assisted planner. Five BioNeMo ESM2 model sizes showed no clear benefit.
- The team kept the decision-and-evidence system rather than claiming an algorithm beats the baseline.
- The Lean certificates only hold under stated assumptions, and the nanopubs are unpublished drafts.

**Frontier (MorphoSwarm, Oct 31 to Nov 1)**
- It's a research workspace and fish design studio, live at [frontier.morphoswarm.ai](https://frontier.morphoswarm.ai/), with its own MCP server.
- It imports Delphi claims through an adapter. The live catalogue has 1,326 claim versions and 629 artifact declarations, but no hosted artifact has been byte-checked.
- It ran simulations on H100s. The neural-cellular-automata curriculum comparison came out as a null result (45/96 against 44/96).
- The README states that the fish is an engineering candidate, not a validated organism, and that no swarm advantage was shown.

In the Frontier bullets I used your repo's `COLLABORATIONS.md` entry for the `frontier-adapters` client. Neither repo documents that link itself, so check the wording if you know more.

_Tools used: GetDynamicTools, Grep ×2, Read, Shell ×9, StrReplace ×3, frontier_capabilities, frontier_catalogue_

### 2026-11-01 00:35 — Turn 2 (User)

> ok sounds good

**Assistant:**

Good. The README changes are in place and uncommitted. Tell me if you'd like me to commit them or adjust the wording.
