# Agent and compute usage

What was actually run, by whom, on what hardware. Every number here was read from a live
command at the time stated, not estimated. Where a figure cannot be measured, it says so.

**Read at:** 2026-11-01, late morning PST (daylight saving ended in Seattle that morning).
Sources: `tmux ls` and `ps` on the build host, `nebius ai job list` (profile `hackathon`),
`gcloud compute instances list`, `git log` over the three repositories, the GitHub API for
repository creation times, `orchestra list` for the task database, the status files each
worker writes to a shared message directory, and a line-by-line scan of the Claude Code and
Codex session transcripts on this host for the token and model tables.

## Agents

### Sessions on the build host

Re-read at **2026-11-01, 09:54 PST**. The counts move during the day; an earlier reading
the same morning recorded 43 sessions, 47 processes and 10 `ff-*` harnesses.

| | Count |
|---|---|
| tmux agent sessions in total | **47** |
| live `claude` / `codex` processes | **48** |
| simulation harnesses (`ff-*`), all started for this campaign | **14** |

The 47 break down as: 17 `claude-NN` general sessions, 14 `ff-*` harnesses, 11 `dx-*`
named role sessions (`dx-corpus`, `dx-critic-r1`, `dx-submit`, `dx-guilds`, `dx-market`,
`dx-gpuops`, `dx-collab`, `dx-fable-lead`, a rethink director and two retired), 4 `codex`
sessions, and 1 `delphi` session.

Not all 47 are active. Several are spend-capped, quota-exhausted or
authentication-blocked, and this count deliberately does not claim they are working.

Of the 14 `ff-*` harnesses, the ten below have a recorded scope and job prefix. The other
four — `ff-sitecritic`, `ff-xenomorph`, `ff-agentuse`, `ff-fseries` — were running at the
read time and have worktrees, but `ff-agentuse` and `ff-fseries` have no scope statement
on record, so none is invented for them here.

### The ten simulation harnesses with a recorded scope

Each owns one scale or question, runs in its own git worktree on its own branch, submits
its own cloud jobs under its own job-name prefix, and writes its own status file.

| Harness | Owns | Job prefix |
|---|---|---|
| `ff-evo` | Evo 2 regulatory-sequence work, fin and scale candidates | `claude-evo-` |
| `ff-mol` | molecular and cell scale; protein structure, signalling | `claude-mol-` |
| `ff-tissue` | tissue and developmental; patterning, growth | `claude-tissue-` |
| `ff-organ` | organ and organism; fin mechanics, aerodynamics, glide | `claude-organ-` |
| `ff-neuro` | neural scale; escape, CPG, glide stabilisation | `claude-neuro-` |
| `ff-eco` | ecological and collective; reachability, schooling | `claude-eco-` |
| `ff-zf2ff` | the zebrafish-to-flying-fish project | `claude-zf2ff-` |
| `ff-xeno` | the preregistered microcarrier endpoints | `claude-xeno-` |
| `ff-voxgpu` | unblocking the GPU voxel engine | `claude-voxgpu-` |
| `ff-xenomodel` | actuation equations, a Lean family, PhysiCell | `claude-xenomodel-` |

Two earlier background workers (GPU operations and bio-services) ran to completion before
these and are counted separately.

### What makes them distinct rather than copies

Each holds different tools and different context, and they hand work to one another
through files rather than conversation, so a worker can pick up another's output without
shared memory. **8 status files** exist in the shared message directory, each timestamped
and rewritten atomically. Cross-harness handoffs are written as named packets, for example
the Evo-to-zebrafish and voxgpu-to-xeno routes.

**The honest limit.** They were allocated by a coordinating session, they share one git
identity, and no controlled comparison against a single agent was run. Our own
review-corrections ledger refuses to claim an agent-count advantage, and so does this page.

## Branches and worktrees

| | Count |
|---|---|
| `claude/*` branches pushed to the public repository | **8** |
| git worktrees created for this campaign | **14** |

Pushed branches: `about-blog`, `bioservices`, `dossier`, `eco`, `evo2-fin-scale`,
`mol-sims`, `neuro`, `zf2ff`. More are in flight and unpushed.

## GPU jobs — Nebius H100

Project `project-e00p797qpr0049snsqvf0k`, shared with other hackathon teams.

### Everything in the shared project

| State | Jobs |
|---|---|
| COMPLETED | 87 |
| FAILED | 23 |
| CANCELLED | 6 |
| RUNNING | 2 |
| ERROR | 1 |
| **Total listed** | **123** |

### Ours

**77 jobs** carry one of our name prefixes. Of those, the **28** submitted by the ten
harnesses in this campaign stand at:

| State | Jobs |
|---|---|
| COMPLETED | 19 |
| RUNNING | 2 |
| FAILED | 2 |
| ERROR | 1 |
| PROVISIONING | 1 |

By harness: `claude-zf2ff` 7, `claude-tissue` 5, `claude-organ` 5, `claude-evo` 5,
`claude-mol` 4, `claude-neuro` 2. The remaining 49 of our 77 are the earlier
`delphi-evolve-ops-` and `bioservices-` families.

Every job is 1 GPU. Failures are kept in the record; three of this campaign's jobs did not
succeed and are counted above rather than dropped.

### Measured GPU utilisation

Allocation is not utilisation, so the only real evidence is sampled telemetry at 1 Hz:

| Task | Samples | Mean util | Max | Power |
|---|---|---|---|---|
| `ns2d-shear-demo-h100` | 52 | 96.6% | 100% | 454 W |
| `ns2d-refine-h100` | 181 | 98.6% | 100% | — |
| `heldout-validation-h100` | 149 | 51.6% | 55% | 121 W |

Three tasks, historical windows. They do not establish continuous saturation across the
campaign, and the jobs used a small fraction of each 80 GiB card.

## CPU

- **Google Cloud**, project `scienceclaw26bos-3016`: 5 instances exist, **1 RUNNING**
  (16 vCPU) and 4 terminated. Quota is 32 vCPU in all regions and **0 GPU**. The lab
  account is scheduled for deletion, so artifacts are exported ahead of it.
- **Nebius CPU**: one attempt was refused with `ResourceExhausted` on
  `compute.instance.non-gpu.vcpu` (limit 24 vCPU against 28 requested); a later bounded
  4-vCPU job was admitted.
- **Build host**: shared by every session above, running PostgreSQL, the web service, the
  Lean toolchain and the browser suite alongside the harnesses.

## Token usage

**Two agent harnesses wrote transcripts on this host, and an earlier version of this page
said token usage was unknown because it had looked at neither.** Claude Code writes to
`~/.claude/projects` and to seven Orchestra-managed account directories; Codex/GPT writes
to `~/.codex/sessions` (47 GB on disk). Both were streamed line by line and their usage
blocks summed. Figures match §2.1 of `SUMMARY.md`.

### Combined, all time

| Harness | Transcript files | Tokens, all categories |
|---|---|---|
| Codex / GPT | 6,778 (6,545 carrying a usage block) | **922,177,496,289** — 922.2 billion |
| Claude Code | 18,198 | **144,988,434,152** — 145.0 billion |
| **Combined** | **24,976** | **1,067,165,930,441 — about 1.07 trillion** |

"All categories" is fresh input + cache read + cache creation + output. It counts tokens
**moved**, not work done.

### Claude Code, all time (build host + 7 Orchestra accounts)

| Measure | Tokens |
|---|---|
| Cache read | 141,749,753,482 |
| Cache creation | 2,573,117,395 |
| Output generated | 618,985,553 |
| Fresh input | 46,577,722 |
| Assistant messages | 601,938 |

### Codex / GPT, all time

| Measure | Tokens |
|---|---|
| Input | 920,340,481,928 |
| — of which cached | 905,347,191,552 |
| Output | 1,837,014,361 |
| — of which reasoning | 555,050,084 |
| **Total** | **922,177,496,289** |

Codex keeps one cumulative `total_token_usage` per session and the figure sums the **last**
counter in each of the 6,545 session files. Within a session nothing is double-added
(total = input + output exactly). Across sessions it can be — a resumed or forked session
carries the same cumulative counter into a new file — and no deduplication was done, so
the Codex total is an **upper bound**.

### Per day since 2026-10-26

Claude Code, each assistant message attributed to **its own timestamp**:

| Day | Assistant messages | Output tokens | Cache read |
|---|---|---|---|
| 2026-10-26 | 21,498 | 16,016,942 | 4,013,283,053 |
| 2026-10-27 | 44,702 | 52,775,080 | 9,180,622,394 |
| 2026-10-28 | 52,281 | 63,436,326 | 11,820,718,671 |
| 2026-10-29 | 50,068 | 74,609,336 | 9,564,698,335 |
| **2026-10-30** | **32,212** | **37,402,765** | **6,181,699,742** |
| **2026-10-31** | **31,789** | **47,869,754** | **8,978,192,632** |
| **2026-11-01** (to ~09:00 PST) | **13,453** | **17,439,842** | **3,999,963,608** |
| **Seven-day total** | **246,003** | **309,550,045** | **53,739,178,435** |

Codex / GPT — **a different attribution rule, so the tables are not merged.** The counter
is cumulative per session, so a session's whole lifetime total lands on the day of its
**last** usage record, not on the days it ran:

| Day | Total tokens | Output tokens | of which reasoning |
|---|---|---|---|
| 2026-10-26 | 381,095,992 | 614,723 | 194,248 |
| 2026-10-27 | 302,088,858 | 1,055,054 | 367,148 |
| 2026-10-28 | 926,160,963 | 3,097,376 | 1,001,581 |
| 2026-10-29 | 2,654,465,889 | 9,467,166 | 3,060,559 |
| **2026-10-30** | **2,187,180,520** | **6,484,121** | **2,081,258** |
| **2026-10-31** | **1,369,688,098** | **3,447,924** | **1,146,446** |
| **2026-11-01** (to ~09:00 PST) | **1,674,640,948** | **5,721,893** | **2,690,741** |
| **Seven-day total** | **9,495,321,268** | **29,888,257** | **10,541,981** |

Those seven days carry 1.0% of the all-time Codex total. Under this attribution rule that
says most session files last recorded usage before 2026-10-26; it is **not** a claim about
when the tokens were spent, and this method cannot tell us.

### The event window, 2026-10-30 to 2026-11-01

| Harness | Assistant messages | Output tokens | Cache read / cached input | All categories |
|---|---|---|---|---|
| Claude Code | 77,454 | 102,712,361 | 19,159,855,982 | 19,553,362,586 |
| Codex / GPT | not recorded per message | 15,653,938 | 5,128,615,680 | 5,231,509,566 |

**A correction.** An earlier figure of **178,002,683** output tokens and **49.6 billion**
cache reads "since 2026-10-30" selected transcript *files* by modification time and then
summed **every** record inside them, including messages written before the window.
Re-summed by each message's own timestamp the window is **102,712,361 output tokens** over
**77,454** assistant messages. The superseded number is kept here rather than deleted.

### Why cache read is reported apart from output

An agent loop re-sends its whole context every turn and hits the prompt cache on nearly all
of it, so cache-read scales with turn count and context length, not with work produced.
Folding it into one headline would make a long conversation look like a large result.
**Output tokens are the closer measure of generated work.**

### Per account, all time (Claude Code only)

| Account | Messages | Output tokens | Cache read |
|---|---|---|---|
| build host | 353,380 | 322,774,745 | 103,046,275,930 |
| max_gmail | 91,745 | 111,339,749 | 14,317,208,158 |
| max_outlook1 | 60,511 | 73,763,501 | 9,571,177,816 |
| max_outlook2 | 48,030 | 52,072,533 | 6,871,012,674 |
| max_outlook | 33,580 | 40,874,183 | 5,865,561,359 |
| max_allen | 7,189 | 10,343,718 | 1,163,483,522 |
| max_outlook3 | 4,675 | 4,846,820 | 575,346,435 |
| ent_allen | 2,828 | 2,970,304 | 339,687,588 |

Codex sessions carry no account split in their transcripts, so there is no equivalent
table for them.

### Models actually used, by assistant-message count

Claude Code transcripts — fourteen distinct models:

| Model | Messages |
|---|---|
| Claude Opus 5.5 | 267,497 |
| Claude Opus 5 | 173,463 |
| Claude Sonnet 5.5 | 96,156 |
| Claude Haiku 5.5 | 55,040 |
| Claude Opus 4.8 | 5,866 |
| Claude Sonnet 4.6 | 2,191 |
| **MiniMax-M2.7** | 905 |
| Claude Fable 5.1 | 375 |
| **GLM-5** | 296 |
| **MiniMax-M3.1-Flash** | 79 |
| Claude Haiku 4.5 | 42 |
| **GLM-4.5** | 20 |
| Claude Fable 5 | 4 |
| Claude Opus 4.7 | 2 |

Non-Anthropic models in bold. The unit is the assistant message, which is **not** a unit of
work: one Opus message and one Haiku message count the same.

Codex / GPT transcripts — eight models, counted by **session**, by the **first** model each
session names (Codex records the model in a turn-context record, not beside the usage
block). A session that switches model mid-run is counted once, under the first, so this is
a census rather than a share of tokens. It also undercounts the model list: a 40-file spot
check found `gpt-6-luna` named in later turns of sessions whose first model was something
else, and it appears nowhere below.

| Model named first | Sessions |
|---|---|
| `gpt-5.6-sol` | 5,801 |
| `gpt-rosalind-5.5` | 703 |
| `gpt-5.5` | 92 |
| `gpt-6-astra` | 51 |
| `codex-auto-review` | 34 |
| `gpt-6.1-sol` | 10 |
| `heisenberg` | 9 |
| `gpt-5.4` | 6 |
| **Total with a model field** | **6,706 of 6,778** |

Method and controls: the first 256 KB of each of the 6,778 session files was read and the
first `"model"` field taken. **72 files named no model in that window** and are reported
rather than dropped; a negative control for an impossible model name returned **0**.

**Twenty-two distinct model identifiers** across the two tables above, from at least four
vendors — Anthropic (10), OpenAI, Zhipu/GLM (2), MiniMax (2) — plus Gemini and the
Nebius-hosted models outside them, and `gpt-6-luna` as a twenty-third seen only mid-session.
`codex-auto-review` and `heisenberg` are names as the transcripts record them; whether they
are models or routing aliases was not established.

### Tool calls — a floor, not a total

Substring match over Claude transcript lines written since 2026-10-26 (2,504 session
files), for **four tools only**:

| Tool | Calls |
|---|---|
| `Bash` | 158,393 |
| `Edit` | 13,419 |
| `Read` | 10,980 |
| `Write` | 8,458 |
| **Total, these four** | **191,250** |

Every other tool — web fetch, MCP calls, the agent-spawn tool, the browser suite — is
outside this count, as are all Codex tool calls, so 191,250 is a floor.

**Subagent spawns: not counted.** The extraction searched all 2,504 files for the
agent-spawn tool by name and returned **zero matches**. Subagents were used, so zero is an
extraction failure, not a measurement, and it is reported as not counted rather than
guessed.

## Repositories built during the event window

The event window runs **2026-10-30 to 2026-11-01**. Two anchors fix its start, both read
here: `delphi-evolve`'s first commit `3090ca7` is authored **2026-10-30 23:58:05 PST**, and
`kganjam/delphi-frontier` was created at **2026-10-31T14:49:43Z** (GitHub API
`repos/kganjam/delphi-frontier`, `created_at`).

| Repository | Commits | Branches | Tracked files |
|---|---|---|---|
| `kganjam/delphi-frontier` | **1,700** | 166 | 6,687 |
| `kganjam/delphi-evolve` ("Darwin's Bridge") | **461** | 66 refs | 829 |

`delphi-evolve` was omitted from earlier versions of this dossier. Its 461 commits fall on
exactly two days — **2 on 2026-10-30 and 459 on 2026-10-31** — so all of it is event work.
Its GitHub repository was created 2026-10-31T06:58:06Z, after the first commits were
authored locally. The `delphi-frontier` row is a re-read at 2026-11-01 10:00 PST and is
larger than the 1,595 / 158 / 6,684 recorded earlier the same day; the repository was still
taking commits. Both readings are kept with their times.

## Swarm infrastructure at scale — measured on a DIFFERENT project, NOT hackathon work

**This section is evidence about the orchestration machinery, not about the hackathon.**
The figures come from `kganjam/morphoswarm` on **2026-10-28 and 2026-10-29** — **before the
event window**, on a **separate attack-campaign project**. None of it is hackathon work,
none of it is folded into any total above, and nothing in the GPU, CPU or repository
sections counts it. It is here because it is the one place where the swarm's throughput was
pushed hard enough to be worth measuring.

Orchestra lists **1,551 tasks** for the `morphoswarm` project — 1,434 `done`, 52
`archived`, 28 `blocked`, 23 `open`, 8 `cancelled`, 6 `failed` (`orchestra list --project
morphoswarm --all`, read 2026-11-01 09:52 PST). The repository's backlog holds 1,078
`M<id>` rows and retains 556 distinct `orchestra/task/<id>` branches.

In those two days, across every ref in that repository:

| Measure | Count |
|---|---|
| Unique commits in the two-day window | **2,138** |
| — carrying at least one model `Co-Authored-By` trailer | **1,792** |
| Distinct `M<id>` backlog task ids named by those commits | **350** |
| Distinct `orchestra/task/<id>` branches named by those commits | 226 |

Model `Co-Authored-By` trailer lines on those commits — **2,848 lines over 1,792 commits**,
since a commit may carry more than one:

| Trailer | Lines |
|---|---|
| Claude Opus 5 | 1,568 |
| Claude Sonnet 5.5 | 551 |
| Claude Opus 5.5 | 421 |
| Claude Haiku 5.5 | 216 |
| Claude Code (unversioned) | 87 |
| OpenAI Codex | 5 |

Re-runnable: `git -C ~/git/morphoswarm log --all --since=2026-10-28 --until=2026-10-30
--format='%H%n%B%n==ENDC=='`, parsed for unique SHAs, `Co-Authored-By:` lines,
`orchestra/task/<hex>` and `M<digits>`. `--since`/`--until` filter on committer date;
counting by author date differs by roughly 1%, and the repository is still moving, so a
re-run will not match to the unit.

**What it shows and does not show.** It shows the orchestration layer sustaining ~1,070
merged commits a day from ~175 distinct task rows a day across four model tiers, for two
days, on one host. It shows **nothing** about the hackathon, nothing about whether those
commits were good, and nothing about multi-agent versus single-agent performance — there
was no single-agent arm, and the work was handed out by a coordinating session sharing one
git identity.

## Non-transcript API receipts

These cover the services that write **no** transcript, so none of it appears in the token
tables above. Two receipts exist and are **not** aggregated, because they measure different
things:

| Receipt | Model | Measured |
|---|---|---|
| Discovery embedding index | `gemini-embedding-001` | 2,444 documents embedded, 49 requests, 0 failed, 768 dimensions, 45-second window |
| Bioservices ledger | Gemini | 4 calls, 7,556 input tokens, 9,700 output tokens including thinking |

Separately, a bio-service harvest logged **105 API calls, 95 succeeded and 10 failed**
across UniProt, Europe PMC, NCBI E-utilities, NCBI Datasets, Ensembl, BioModels and ZFIN,
plus 4 OpenFold2 predictions and 5 BioModels CPU simulations.

Models reached this way: Gemini (`gemini-embedding-001`, `gemini-3.8-flash`,
`gemini-4-argon`) for indexing and cross-review, Evo 2 and OpenFold2 through Nebius, and
hosted scientific models through the Nebius Scientific AI workbench. The models that **do**
write transcripts — Claude, Codex/GPT, GLM and MiniMax — are counted in the model tables
above, not here.

## What is not measured

- **Total provider spend: unknown.** The billing meter was never queried. No price is
  applied to any token count on this page, and a token count is not a cost. Zero worker
  creations from two failed launch attempts does not establish zero spend.
- **Token usage outside the two transcript sets: unknown.** Gemini, Evo 2, OpenFold2 and
  the Nebius-hosted scientific models write no transcript here; only the two receipts above
  cover them. The true total is **higher** than the tables, not lower.
- **Token usage per project: not split.** Both transcript sets are host-wide and include
  work on other projects, MorphoSwarm's attack campaign among them.
- **Subagent spawns: not counted.** The extraction returned zero matches across 2,504
  files, which is an extraction failure rather than a count of zero.
- **Tool calls beyond four tools: not counted.** The 191,250 figure covers `Bash`, `Edit`,
  `Read` and `Write` in Claude sessions only, and is a floor.
- **Continuous GPU saturation: not established.** Three sampled windows are not a campaign.
- **Which sessions were productive: not claimed.** A session existing, or reporting
  `running`, is an orchestration state, not measured work. Neither is a token, a commit or
  a tool call.
- **Any multi-agent advantage: not measured.** No controlled single-agent arm was run, in
  the hackathon or in the MorphoSwarm campaign above.
