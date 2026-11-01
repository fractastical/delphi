# Swarm coordination

How the agents that build this repo are run, logged and counted. Two things live here that used
to be split between `chats/` and the "Agents" section of [COLLABORATIONS.md](../COLLABORATIONS.md):

- [`chats/`](chats/README.md): the chat log. One file per Cursor agent chat (every user message with
  its timestamp, the assistant's written replies, tools used), with the subagent runs each chat
  launched in `chats/subagents/`. Rebuild with `python3 chats/generate.py`.
- The swarm usage below: how many agents of which kind have worked on the repo, what each use case
  was for, and what it produced. The counts come from the same transcripts
  (`~/.cursor/projects/.../agent-transcripts`) plus the processes running on the operator's machine.

Who we worked with outside the repo, and what the hosted MCP server records about its use, stay in
[COLLABORATIONS.md](../COLLABORATIONS.md). The measured comparison of a single agent against swarm
arms is in [`test-data/agent-comparison/`](../test-data/agent-comparison/SUMMARY.md).
Tracking issue: [#80](https://github.com/fractastical/delphi/issues/80).

## Swarm usage

Every agent that has worked on this repo, what it was for and what it produced. Cloud agents report
to GitHub branches, so they are listed from the chat that launched them and not re-counted live.
Subagent roles are classified by keyword from each subagent's first prompt, so the per-role numbers
are approximate; the totals are exact. Update the snapshot when you update the table.

### Snapshot: 2026-10-31 22:05 EDT (2026-11-01 02:05 UTC)

| | Count |
|---|---:|
| Local Cursor chats (top-level agents) | 101 |
| Subagents launched by those chats (local) | 262 |
| Chats active in the last 3 hours | 19 (6 in the last 20 minutes) |
| Cloud agents launched (claim tests 13, organism data 6) | 19 |
| Long-running background processes | 7 (3 Nebius fold submitters, Moltbook loop, Senti listener, Senti poll loop, local docs server) |
| External agent identities | 2: Delfie on Moltbook and `delfie-claude` in the SentiLab room (plus the Discord bot and the forum) |

### What the agents did, by use case

| Use case | Agents | What it accomplished | Status |
|---|---|---|---|
| Claim extraction: Darwin, Thompson, Wolfram, Levin, math-bio | About 170 subagents (35 Darwin, 55 Thompson including Lean, 37 Wolfram, 29 Levin, 15 math-bio thinkers) across 6 chats | 1,702 claims across the claim sources; 880 live as nanopubs on production; 63 theorems (47 Lean-checked, 16 literature) | Done; Levin and Lean formalization still growing |
| Dataset-resolvability assessment | About 70 subagents (GPT, Gemini and Grok assessors, run blind, in batches) | Assessments of every claim's candidate datasets; `dropped-datasets.json` for those that failed to resolve | Done for Darwin, Thompson, Wolfram; a further round of four assessors started at 18:14 EDT (not checked) |
| Truth scoring | 5 subagents plus the chat on how right each thinker is (48 subagents) | Model truth scores feeding the claim graph | Ongoing (`be8988f6`) |
| Claim tests against data | 13 cloud agents (Darwin 4, Thompson 4, Wolfram 5) plus local test runs | 133 claims tested: 78 supports, 25 mixed, 21 refutes, 9 inconclusive; 66 on organisms; 13 pre-registered tests awaiting data | Cloud branches not yet re-checked |
| Organism reference data | 6 cloud agents (Darwin 3, Thompson 3) | 782 taxa, 3,340 located mentions, 1,372 provenanced dataset records, completeness ranking | Done; scoring pass is a separate step |
| Dataset scouting | A swarm of 6 scouts plus a 13-subagent scouting chat | `test-data/dataset-scouting/` records of where data to test each untested claim lives | Ongoing (`7fe227ee`) |
| Protein structure folds (Nebius) | 3 background submitters | AlphaFold/ESMFold jobs for HCN2 tetramers, an innexin octamer and a channel panel including PIEZO2 windows (Levin claims 16, 11 and 14) | Running; the octamer job is still `admission_pending` |
| Morphology and fabrication | Flying-fish swarm (6 subagents), morpholib 12-step dataset build (6 subagents, with a round-2 relevance auditor), Formlabs print prep | Zebrafish-to-flying-fish design work; MorphoEval-linked dataset build; Formlabs print preparation (outputs not yet checked) | Ongoing (`2826b8f3`, `54dc2b9d`) |
| Review and self-assessment | 3 blind assessors (GPT-5.6 Sol, Gemini 4 Argon, Grok 4.7), a single-agent comparison run, a "most validated Darwin claims" reviewer | Self-assessment on the Science Claw rubric: 57–60/100, published to the test registry; single-agent vs swarm comparison | Single-agent run in progress (`63086ead`) |
| Outreach and collaboration | Delfie on Moltbook (checks every 30 minutes), `delfie-claude` in the SentiLab room (listener plus 30-minute poll), Discord bot | The contacts in COLLABORATIONS.md; MCP server offered to other teams | Running since 14:50 and 14:59 UTC |
| Infrastructure and site | About 40 single-purpose chats (MCP server, forum, claim graph site, theorem view, status script, animated GIFs, chat logs, README) | `delphisci` MCP server (hosted on Fly), Science Claw forum, `site/` claim graph, theorems page, team page | Ongoing |

Known issue: `npm run status` fails because `levin-2015-place-01`, `-05` and `-06` have no
`data_kind` in their `result.json`, which also blocks rebuilding the numbers above.

## Known gaps

- The chat log was last regenerated 2026-10-31 10:05 (22 chats, 119 subagent runs); the snapshot
  above counts 101 chats and 262 subagents. `generate.py` has a hand-kept title map and only names
  chats it knows, so regenerating does not pick up new chats automatically.
- Cloud agents, background processes and the external identities are counted by hand. There is no
  script that produces the snapshot table.
- The use-case table and the chat log are not cross-linked: a row does not say which chats it came
  from, and a chat does not say which row it belongs to.
