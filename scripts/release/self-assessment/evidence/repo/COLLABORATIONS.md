# Collaboration log

Who we have worked with or pointed at delphisci, when, and what came of it, plus what the hosted
MCP server (`https://mcp.delphibio.org/mcp`) records about its use. Times are UTC, with
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
| 2026-10-31 23:01 – 2026-11-01 07:42 | SentiLab team (aneta-claude, sentilab-host, pocket-forge), Carter-ChatGPT, ScienceClaw team | SentiLab room, tickets `897c7563` and `ba58c374` | Delfie answered both research tickets. 897c7563: reproduced TAP-2.5D's published 75.48 / 115.94 °C from SentiLab's `case.json` with HotSpot 6.0, showed HotSpot 7.0 gives 123.42 / 232.67 °C on identical inputs because its detailed-3D vertical link carries the sink's convection share, and posted a 9-line patch (78.77 / 125.52 °C after) plus a reproduction harness (v1 #57314, v2 with receipts #57872 after Carter-ChatGPT's review); ScienceClaw re-ran the patch independently (PASS, #57666/#57668, byte-identical outputs #57883) and Team Vortex on ARM (reply under #57881); Delfie then ran the SuperLU solver path (#58029, same fix applies) and guarded Variant 2 (#58035). Rows 1–3, 7, 11, 18 of the overnight re-run table (#58018). ba58c374: Kannan et al. MICRO 2015 gives the CPU–DRAM arrangement only, no coordinates or powers (#57597, re-derived by ScienceClaw #57820). SentiLab's slides credit "Delfie (delphisci team)". Both tickets closed as solved by the host (#57756). | Done |
| 2026-10-31 19:00 [15:00] | Fittest MCP (Pavel-Tk) | Announcement shared with Joel; [issue #57](https://github.com/fractastical/delphi/issues/57) | ML-potential trust-or-DFT router. We ran a pilot against the hosted server and borrowed its routing design for assessor truth scores (`plugins/fittest/`). Feedback for them: sparse calibration buckets pass on the posterior mean (a 2× stretched C–O bond trusted at 0.67 on 3 labels). | Not contacted yet |

## Agent networks (Moltbook, The Colony, Science Claw forum, Discord)

Delfie's four Moltbook posts (`plugins/agent/moltbook-drafts.json`) drew replies from nine outside
agents; participants re-read live on 2026-11-01 15:23 UTC (Delfie karma 20). What each objection
changed is recorded in the file named in the last column.

| Agent | Thread | What they contributed | What it changed |
|---|---|---|---|
| vina | `e06b5458` (intro) | Asked for a null: run the junction statistics on segmenter output for synthetic tilings with known non-hexagonal packing | Segmenter-bias null run (`claim-sources/cell-geometry/results/segmenter-bias/`); `thompson1917-ch07-04` confidence 0.60 → 0.35 (`revisions[0]` in its `result.json`), later re-based on expert-segmented Drosophila epithelia (`revisions[1]`) |
| hivefound | `e06b5458` | Expected observation, disconfirming observation, admissible data and inference method as separate fields; keep revisions as new records | The test contract fields in `result.json`; revisions as `prov:Activity` in `test-data/claim-tests/build-test-nanopubs.mjs` |
| nanoswarm | `9ff17185` (segmenter bias) | Blur alone curves wall ridges toward Y near a vertex; fit lines in an annulus and sweep its radius on synthetic tilings first | Planned ridge re-measurement in `ch07-04` `inference_method` |
| doctor_memory | `e06b5458`, `9ff17185` | Fisher's theorem has no single reading; tag formalizations; 25-record assessment batch with unmarked seeds; synthetic CV sweep before clinical images | `formalization` tag on all 23 math claims (commit `912fbea9`); Hardy–Weinberg and Price added to `math-bio-claims`; batch `test-data/organisms/assessment/batches/doctor-memory-01.json` (scores not yet returned) |
| grokbot_polymath | `1154e21c` (cornea pre-registration) | Annotation noise alone produces the negative slope the design called confirmation; rodrep.com spelling | Contract amended before any clinical image was opened (`amend-cornea-grokbot` in the drafts file) |
| yuigui | `e9010612` (Darwin large genera) | Namer effort sits on both sides of the regression; registered a prediction (holds without control, shrinks with occurrences, mostly gone with authority count) | Three-model contract with namer-effort rates and per-source stratification (`amend-darwin-yuigui`); prediction to be recorded beside the result |
| sheeshscout | `e06b5458` | Seed known records into each dataset-assessment batch | `test-data/organisms/assessment/seeds.json` |
| nyna, anandanode | `e06b5458`, `e9010612` | Welcome; discussion of the attention confound | Nothing to change |

Every agent whose objection changed a design is `dct:contributor` in the provenance of the resulting
nanopub. The other networks so far: The Colony (`@delfie`, 2 posts, karma 4, 6 unread; nothing has
changed a file), the Science Claw forum (20 posts, one registered agent, which is ours, 0 comments at
`/healthz` on 2026-11-01) and Discord (two people said they would try the MCP; unconfirmed, see above).

## Agents

The agent counts (local chats, subagents, cloud agents, background processes, external identities)
and the table of what the agents did by use case moved to
[`chats/SWARM_COORDINATION.md`](chats/SWARM_COORDINATION.md), next to the chat log
([`chats/`](chats/README.md)). Tracking issue:
[#80](https://github.com/fractastical/delphi/issues/80).

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
