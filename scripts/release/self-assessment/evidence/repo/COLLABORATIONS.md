# Collaboration log

Who we have worked with or pointed at delphisci, when, and what came of it, plus what the hosted
MCP server (`https://delphisci-mcp.fly.dev/mcp`) records about its use. Times are UTC, with
US Eastern (UTC-4) in brackets where the source showed local time. Add new entries at the bottom
of each table.

## People and teams

| When (UTC) | Who | Where | What | Status |
|---|---|---|---|---|
| 2026-10-31 14:41 | srirangam-r | SentiLab hackathon room (`scienceclaw-e14-hackathon-room-ws`, session `32a841e5`) | Admitted to the room at the same time as us (fractastical). No exchange yet. | Contact |
| 2026-10-31 14:43 | SentiLab room (all agents) | SentiLab room | Our agent Delfie (`delfie-claude`) introduced the claim graph and the delphisci MCP tools, and asked for biology/morphology reviewers and nanopub collaborators. | Open invitation |
| 2026-10-31 14:50 | SentiLab team (2.5D chiplet thermal placement) | SentiLab room | Delfie suggested math-bio claims that may transfer to floorplanning and heat spreading: Murray's law and branching networks, surface-to-volume and allometric scaling (Thompson), reaction-diffusion spacing. Offered to pull the LaTeX statements through the MCP. | No reply yet |
| 2026-10-31 16:22 | InquilineKea (human-inquilinekea) | SentiLab room | Asked which collagen networks and phase changes to map. Delfie offered Thompson's tension and form statements (71 formal statements) and the Turing/reaction-diffusion claims as a scaffold, queried through the MCP. | Active |
| 2026-10-31 16:56 | InquilineKea | SentiLab room, ticket `57c7c42f` | On the H100 collagen rigidity-transition run, Delfie gave the physics anchors (sub-isostatic connectivity z≈3–4 against Maxwell z_c=6, strain-controlled transition at γ_c(z), G ~ \|γ−γ_c\|^f with f≈0.7; Sharma, Licup, MacKintosh et al., *Nature Physics* 2016), offered to formalize them as delphisci claims and invited collaboration on github.com/fractastical/delphi. | Active, awaiting their repo |
| 2026-10-31 14:18 [10:18] | Symplectic Geometry of Awe (CRBS) | Discord | Joel shared `https://delphisci-mcp.fly.dev/` and asked whether some of the open problems there are tractable. Reply: "Oh! that would be nice!!". Joel followed up at 15:01 [11:01] suggesting they would find something (e.g. Turing patterns). | Said they would check out the MCP server |
| 2026-10-31 16:00 [12:00] | Joshua G (WIKI) | Discord | Replied to the same message: "i'll check this out too". | Said they would check out the MCP server |
| 2026-10-31 18:12 | PiXlRAM (human-pixlram) | SentiLab room; Discord 15:42 [11:42] | Posted a closed-loop CNC manufacturing project (milled-slot width) and asked for multi-agent collaborators. Not biology; no exchange with us. | Contact |
| 2026-10-31 19:00 [15:00] | Fittest MCP (Pavel-Tk) | Announcement shared with Joel; [issue #57](https://github.com/fractastical/delphi/issues/57) | ML-potential trust-or-DFT router. We ran a pilot against the hosted server and borrowed its routing design for assessor truth scores (`plugins/fittest/`). Feedback for them: sparse calibration buckets pass on the posterior mean (a 2× stretched C–O bond trusted at 0.67 on 3 labels). | Not contacted yet |

## Agents

Every agent that has worked on this repo, what it was for and what it produced. Counts come from
the Cursor agent transcripts (`~/.cursor/projects/.../agent-transcripts`, summarized in
[`chats/`](chats/README.md)) and from the processes running on the operator's machine. Cloud agents
report to GitHub branches, so they are listed from the chat that launched them and not re-counted
live. Subagent roles are classified by keyword from each subagent's first prompt, so the per-role
numbers are approximate; the totals are exact. Update the snapshot below when you update the table.

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
| Outreach and collaboration | Delfie on Moltbook (checks every 30 minutes), `delfie-claude` in the SentiLab room (listener plus 30-minute poll), Discord bot | The contacts in the table above; MCP server offered to other teams | Running since 14:50 and 14:59 UTC |
| Infrastructure and site | About 40 single-purpose chats (MCP server, forum, claim graph site, theorem view, status script, animated GIFs, chat logs, README) | `delphisci` MCP server (hosted on Fly), Science Claw forum, `docs/` claim graph, theorems page, team page | Ongoing |

Known issue: `npm run status` fails because `levin-2015-place-01`, `-05` and `-06` have no
`data_kind` in their `result.json`, which also blocks rebuilding the numbers above.

## MCP server usage

The server keeps no per-user logs. It exposes only aggregate Prometheus counters
(`mcp/metrics.mjs`); visitor IPs are hashed with a salt that changes daily and are never stored.
The in-memory counters reset on every deploy, but Fly scrapes them into its managed Prometheus,
which keeps the history across deploys. Even so, **usage cannot be tied to a person**. To see
whether the Discord contacts above have connected, compare `delphi_mcp_unique_visitors_today` and
the client names before and after they say they have tried it.

### Deploys (Fly releases)

| Release | Time (UTC) |
|---|---|
| v1 | 2026-10-31 04:33 |
| v2 | 2026-10-31 13:41 |
| v3 | 2026-10-31 14:04 |
| v4–v5 | 2026-10-31 14:39–14:40 |
| v6–v7 | 2026-10-31 17:46–17:49 |
| v8 | 2026-10-31 18:07 |
| v9–v10 | 2026-10-31 18:17–18:20 |

Metrics shipped with v4/v5 (commit `468f3e9`), so v1–v3 (04:33–14:39 UTC) recorded nothing and
that usage is lost.

### Daily usage files

`npm run mcp:usage` (`scripts/usage/mcp-usage.mjs`) reads the raw scrape samples from Fly's
Prometheus and writes one file per UTC day to `mcp/usage/<date>.json`: tool calls by tool and
outcome, sessions by client with first and last time seen, JSON-RPC methods, rate-limited requests,
peak visitors per process and an hourly breakdown. It handles counter resets at deploys. Run it at
least daily; `-- --days 7` backfills a week, and today's file is partial until midnight UTC.

### 2026-10-31 (14:40 to 19:28 UTC, from `mcp/usage/2026-10-31.json`)

| Metric | Value |
|---|---|
| Tool calls | 1,522. `delphi_get_claim` 1,012 ok / 8 errors, `delphi_sparql` 172 / 29, `delphi_graph` 92, `delphi_search_claims` 78, `delphi_rank_claims` 49, `delphi_overview` 31, `delphi_organisms` 30, `delphi_get_organism` 12 / 9. Another 105 `tools/call` requests were rejected before reaching a tool |
| Sessions (`initialize`) | 60 |
| Rate-limited requests | 534, all 16:37–16:43 during the `corpus-census` burst |
| Peak unique visitors per process | 3 (14:40–17:49), then 1, 2, 1, 1 |

Sessions by client name, in the order first seen:

| Client | Sessions | Active (UTC) | Who |
|---|---|---|---|
| `probe` | 1 | 14:40 | Unidentified; likely our post-deploy check |
| `curl-probe` | 1 | 15:05 | Ours (a Cursor session's smoke test) |
| `claude-code` | 5 | 16:34; 18:12; 18:24–18:31 | Claude Code; whose is unknown |
| `corpus-census` | 19 | 16:35–17:28 | Unidentified. About 1,000 calls, mostly `delphi_get_claim`, hitting the rate limit |
| `delphi-validation` | 4 | 18:00–18:12 | Unidentified |
| `frontier-adapters` | 30 | 18:10–18:51 | Unidentified |

None of these client names appear in our repo, so the unidentified ones could be our cloud agents
or outside users. The visitor gauge never went above 3 distinct IPs in one deploy. Discord
contacts were invited at 14:18 UTC (Symplectic Geometry of Awe) and 16:00 UTC (Joshua G). The
second and third visitors in the first window (15:04, 15:06) and the `claude-code` session at 16:34
are the only candidates for them, and none can be confirmed.

### Snapshots

**2026-10-31 19:12 UTC** (live counters since release v10, 18:20 UTC): 1 visitor, 27 sessions
(`frontier-adapters` 24, `claude-code` 3), 160 tool calls, 0 rate-limited.

To read the live counters for the current process (requires access to the Fly app):

```sh
fly ssh console -a delphisci-mcp -C "node -e 'fetch(\"http://localhost:9091/metrics\").then(r=>r.text()).then(console.log)'" | grep -v -e _bucket -e '^#'
```

Historical series are in Fly's managed Prometheus (Grafana at https://fly-metrics.net, series
`delphi_mcp_*`).
