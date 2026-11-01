# MorphoSwarm Studio — complete summary

**One file.** Everything from the ten dossier pages, consolidated: what the system is, how
it was built, what it measured, what it used, and what it does **not** establish.

**Live site:** https://frontier.morphoswarm.ai · **Repository:** https://github.com/kganjam/delphi-frontier
**Agent endpoint:** `https://frontier.morphoswarm.ai/mcp`

Every figure was read from the site's own published data snapshot, from a receipt file
named beside it, or from a live command run at the time stated. Where a figure is unknown,
this says unknown rather than estimating it.

---

# 1. The one-paragraph version

Biological engineering spans molecules to ecosystems, and the models at each scale were
built by different communities with incompatible units, assumptions and contexts. We built
a shared workspace where a design goal — engineer toward a flying fish — forces those
models to meet, and where every junction is either checked, labelled as an assumption, or
**refused**. Underneath it is a Lean 4 proof base so the laws being reused are stated
exactly and checked mechanically. Around it is a record layer where claims carry their
conditions and review status, and an MCP endpoint so other agents can read and contribute.
The flying fish is an engineering candidate, not a viable organism; what we claim is the
method, the evidence trail, and the map of what is missing.

**What we do not claim:** no biological validation; no organism built; no wet-lab
experiment; no measured advantage for multi-agent over single-agent work; no calibrated
bridge between biological scales; total provider spend unknown.

---

# 2. Scale of the effort — measured

## 2.1 Tokens

**Two agent harnesses wrote transcripts on this host, and an earlier version of this page
counted only one of them.** Claude Code writes to `~/.claude/projects` and to seven
Orchestra-managed account directories; Codex/GPT writes to `~/.codex/sessions`. Both were
streamed line by line and their usage blocks summed. The Codex side is **six times the
size** of the Claude side and was absent from this page entirely.

### Combined, all time

| Harness | Transcript files | Tokens, all categories |
|---|---:|---:|
| Codex / GPT | 6,778 (6,545 carrying a usage block) | **922,177,496,289** — 922.2 billion |
| Claude Code | 18,198 | **144,988,434,152** — 145.0 billion |
| **Combined** | **24,976** | **1,067,165,930,441 — about 1.07 trillion** |

"All categories" is fresh input + cache read + cache creation + output. It counts tokens
**moved**, not work done — see the cache-read note below.

### Claude Code — all time, build host plus seven Orchestra accounts

| Measure | Tokens |
|---|---:|
| Cache read | 141,749,753,482 (141.7 billion) |
| Cache creation | 2,573,117,395 |
| Output generated | 618,985,553 (619 million) |
| Fresh input | 46,577,722 |
| **Assistant messages** | **601,938** |

### Codex / GPT — all time

| Measure | Tokens |
|---|---:|
| Input | 920,340,481,928 (920.3 billion) |
| — of which cached | 905,347,191,552 (905.3 billion) |
| Output | 1,837,014,361 (1.84 billion) |
| — of which reasoning | 555,050,084 (555 million) |
| **Total** | **922,177,496,289** |

Codex keeps one cumulative `total_token_usage` counter per session; the figure above sums
the **last** counter in each of the 6,545 session files. Within a session nothing is
double-added — the total is input + output exactly (920,340,481,928 + 1,837,014,361 =
922,177,496,289), and reasoning is a subset of output. **Across** sessions it can be: a
resumed or forked session opens a new file while carrying the same cumulative counter
forward, and this method would count the shared prefix again. No deduplication was done
for that, so the Codex total is an **upper bound**, not a settled figure.

### Per day since 2026-10-26 — Claude Code

Each assistant message is attributed to **its own timestamp**.

| Day | Assistant messages | Output tokens | Cache read |
|---|---:|---:|---:|
| 2026-10-26 | 21,498 | 16,016,942 | 4,013,283,053 |
| 2026-10-27 | 44,702 | 52,775,080 | 9,180,622,394 |
| 2026-10-28 | 52,281 | 63,436,326 | 11,820,718,671 |
| 2026-10-29 | 50,068 | 74,609,336 | 9,564,698,335 |
| **2026-10-30** | **32,212** | **37,402,765** | **6,181,699,742** |
| **2026-10-31** | **31,789** | **47,869,754** | **8,978,192,632** |
| **2026-11-01** (to ~09:00 PST) | **13,453** | **17,439,842** | **3,999,963,608** |
| **Seven-day total** | **246,003** | **309,550,045** | **53,739,178,435** |

### Per day since 2026-10-26 — Codex / GPT

**A different attribution rule, so the two tables are not merged.** Codex's counter is
cumulative per session, so a session's whole lifetime total lands on the day of its
**last** usage record, not on the days it ran.

| Day | Total tokens | Output tokens | of which reasoning |
|---|---:|---:|---:|
| 2026-10-26 | 381,095,992 | 614,723 | 194,248 |
| 2026-10-27 | 302,088,858 | 1,055,054 | 367,148 |
| 2026-10-28 | 926,160,963 | 3,097,376 | 1,001,581 |
| 2026-10-29 | 2,654,465,889 | 9,467,166 | 3,060,559 |
| **2026-10-30** | **2,187,180,520** | **6,484,121** | **2,081,258** |
| **2026-10-31** | **1,369,688,098** | **3,447,924** | **1,146,446** |
| **2026-11-01** (to ~09:00 PST) | **1,674,640,948** | **5,721,893** | **2,690,741** |
| **Seven-day total** | **9,495,321,268** | **29,888,257** | **10,541,981** |

Those seven days carry **1.0%** of the all-time Codex total (9.50 billion of 922.18
billion). Under this attribution rule that says most session files last recorded usage
before 2026-10-26. It is **not** a claim that 99% of the tokens were spent before the
window: we do not know how the 922 billion distributes over calendar time, and this method
cannot tell us.

### The event window, 2026-10-30 to 2026-11-01

| Harness | Assistant messages | Output tokens | Cache read / cached input | All categories |
|---|---:|---:|---:|---:|
| Claude Code | 77,454 | 102,712,361 | 19,159,855,982 | 19,553,362,586 |
| Codex / GPT | not recorded per message | 15,653,938 | 5,128,615,680 | 5,231,509,566 |

**A correction to this page.** It previously reported **178,002,683** output tokens and
**49,642,734,476** cache reads "since 2026-10-30". That figure selected transcript *files*
by modification time and then summed **every** usage record inside them, including messages
written days before the window — so pre-event work was carried into an event number.
Re-summed by each message's own timestamp, the window is **102,712,361 output tokens**
across **77,454** assistant messages. The superseded number is printed here rather than
deleted, because it was published.

### Why cache read is reported apart from output

An agent loop re-sends its entire context on every turn and hits the prompt cache on nearly
all of it, so cache-read scales with turn count and context length rather than with work
produced. Folding it into one headline would make a long conversation look like a large
result. **Output tokens are the closer measure of generated work: 102.7 million from Claude
and 15.7 million from Codex in the event window.**

### Per account, all time (Claude Code only)

| Account | Messages | Output tokens | Cache read |
|---|---:|---:|---:|
| build host | 353,380 | 322,774,745 | 103,046,275,930 |
| max_gmail | 91,745 | 111,339,749 | 14,317,208,158 |
| max_outlook1 | 60,511 | 73,763,501 | 9,571,177,816 |
| max_outlook2 | 48,030 | 52,072,533 | 6,871,012,674 |
| max_outlook | 33,580 | 40,874,183 | 5,865,561,359 |
| max_allen | 7,189 | 10,343,718 | 1,163,483,522 |
| max_outlook3 | 4,675 | 4,846,820 | 575,346,435 |
| ent_allen | 2,828 | 2,970,304 | 339,687,588 |

Codex sessions carry no account split in their transcripts, so there is no equivalent table
for them.

### What these token numbers are not

- **Not spend.** No price is applied to any row, and the billing meter was never queried.
  A token count is not a cost, and we do not know the cost.
- **Not complete.** Gemini (`gemini-embedding-001`, `gemini-3.8-flash`, `gemini-4-argon`),
  Evo 2, OpenFold2 and the Nebius-hosted scientific models write into neither transcript
  set; only the two receipts in §2.5 cover them. The true total is **higher**, not lower.
- **Not scoped to this project.** Both transcript sets are host-wide. They include work on
  other projects — MorphoSwarm's attack campaign among them, see §2.3 — and no attempt was
  made to split tokens by project.
- **Not evidence of productivity.** A token was moved; whether it helped is not measured
  here, and §8 is where the work is actually checked.

## 2.2 Models actually used

### Claude Code transcripts — fourteen models, by assistant-message count

| Model | Messages |
|---|---:|
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

Non-Anthropic models in bold. The unit here is the assistant message, which is **not** a
unit of work: one Opus message and one Haiku message count the same.

### Codex / GPT transcripts — eight models, by session

The unit is different, and deliberately so. Codex transcripts record the model in a
turn-context record rather than beside the usage block, so these are **sessions**, counted
by the **first** model each session names. A session that switches model mid-run is counted
once, under the first, so this is a model **census** and not a share of tokens or of work.
It also undercounts the model list: a 40-file spot check found `gpt-6-luna` named in later
turns of sessions whose first model was something else, and it appears nowhere in the table
below.

| Model named first | Sessions |
|---|---:|
| `gpt-5.6-sol` | 5,801 |
| `gpt-rosalind-5.5` | 703 |
| `gpt-5.5` | 92 |
| `gpt-6-astra` | 51 |
| `codex-auto-review` | 34 |
| `gpt-6.1-sol` | 10 |
| `heisenberg` | 9 |
| `gpt-5.4` | 6 |
| **Total with a model field** | **6,706 of 6,778** |

Scan method and its controls: the first 256 KB of every one of the 6,778 session files was
read and the first `"model"` field taken. **72 files named no model in that window** and
are reported as such rather than dropped silently; a negative control for a model name that
cannot exist returned **0**, so the matcher is not matching itself or everything.

### Outside both transcript sets

**Gemini** (`gemini-embedding-001`, `gemini-3.8-flash`, `gemini-4-argon`), **Evo 2**,
**OpenFold2**, and the hosted scientific models on the Nebius Scientific AI workbench.
These write no transcript here, so only the receipts in §2.5 cover them and there is no
message or session count for any of them.

**Twenty-two distinct model identifiers** appear in the two tables above — 14 Claude Code,
8 Codex — from at least four vendors: Anthropic (10), OpenAI, Zhipu/GLM (2) and MiniMax
(2), plus Google's Gemini and the Nebius-hosted models outside them. `gpt-6-luna` is a
twenty-third, seen mid-session and so missed by the first-model census. Two of the
Codex identifiers, `codex-auto-review` and `heisenberg`, are names as the transcripts
record them; whether they are models or routing aliases was not established. This is a
genuinely multi-model system rather than one vendor. **Which model did which useful work is
not measured**, and no model here is ranked against another.

## 2.3 Agents, sessions, tool calls and repositories

**Read at 2026-11-01, 09:54 PST**, from `tmux ls` and `ps` on the build host. The counts
move during the day; an earlier reading on this page recorded 43 sessions and 12 harnesses.

| | Count |
|---|---:|
| tmux agent sessions on the build host | **47** |
| live `claude` / `codex` processes | **48** |
| — of the 47: general `claude-NN` sessions | 17 |
| — of the 47: `ff-*` simulation harnesses | 14 |
| — of the 47: `dx-*` named role sessions | 11 |
| — of the 47: `codex` sessions | 4 |
| — of the 47: other (`delphi`) | 1 |
| Claude transcript files scanned | **18,198** |
| Codex transcript files scanned | **6,778** |

Not all 47 are active. Several are spend-capped, quota-exhausted or
authentication-blocked. **A session existing is an orchestration state, not measured work,
and this count does not claim any of them is productive.**

### The harnesses

Each owns one scale or question, runs in its own git worktree on its own branch, submits
its own cloud jobs under its own name prefix, and writes its own status file.

| Harness | Owns |
|---|---|
| `ff-evo` | Evo 2 regulatory sequences, fin and scale candidates |
| `ff-mol` | molecular and cell scale; structure, signalling |
| `ff-tissue` | tissue and developmental; patterning, growth |
| `ff-organ` | organ and organism; fin mechanics, aerodynamics, glide |
| `ff-neuro` | neural; escape, CPG, glide stabilisation |
| `ff-eco` | ecological and collective; reachability, schooling |
| `ff-zf2ff` | the zebrafish-to-flying-fish project |
| `ff-xeno` | the preregistered microcarrier endpoints |
| `ff-voxgpu` | unblocking the GPU voxel engine |
| `ff-xenomodel` | actuation equations, a Lean family, PhysiCell |
| `ff-xenomorph` | cell aggregation into printable morphology |
| `ff-sitecritic` | independent Playwright critique of every route |

Two more `ff-*` sessions — `ff-agentuse` and `ff-fseries` — were running at the read time
above and have worktrees (`claude-agentuse`, `claude-fseries`), but no scope statement was
recorded for them, so none is invented here.

They hand work to one another through **files**, not conversation, so a worker can pick up
another's output without shared memory.

### Tool calls — a floor, not a total

Counted by substring match over the Claude transcript lines written since 2026-10-26
(2,504 session files), for **four tools only**:

| Tool | Calls |
|---|---:|
| `Bash` | 158,393 |
| `Edit` | 13,419 |
| `Read` | 10,980 |
| `Write` | 8,458 |
| **Total, these four** | **191,250** |

Every other tool — web fetch, MCP calls, the agent-spawn tool, the browser suite,
everything the harnesses invoke — is **outside this count**. 191,250 is therefore a floor
on tool use, not a total. It also covers Claude sessions only; Codex tool calls are not
counted at all.

**Subagent spawns: not counted.** The extraction searched for the agent-spawn tool by name
across all 2,504 files and returned **zero matches**. Subagents were used, so zero is an
extraction failure, not a measurement. It is reported as not counted rather than filled in
with a guess.

### Repositories built during the event window

The event window runs **2026-10-30 to 2026-11-01**. Two anchors fix its start, both read
here: `delphi-evolve`'s first commit is `3090ca7`, authored **2026-10-30 23:58:05 PST**,
and the `kganjam/delphi-frontier` repository was created at **2026-10-31T14:49:43Z**
(GitHub API `repos/kganjam/delphi-frontier`, field `created_at`).

| Repository | Commits | Branches | Tracked files |
|---|---:|---:|---:|
| `kganjam/delphi-frontier` | **1,700** | 166 | 6,687 |
| `kganjam/delphi-evolve` ("Darwin's Bridge") | **461** | 66 refs | 829 |

`delphi-evolve` was omitted from earlier versions of this page. Its 461 commits fall on
exactly two days — **2 on 2026-10-30 and 459 on 2026-10-31** — so all of it is event work.
Its GitHub repository was created 2026-10-31T06:58:06Z, after the first commits were
authored locally.

The `delphi-frontier` row is a re-read at 2026-11-01 10:00 PST and is larger than §2.4's
reading of 1,595 commits / 158 branches / 6,684 files taken earlier the same day; the
repository was still taking commits while this was written. Both readings are kept, with
their times, rather than one overwriting the other.

### Swarm infrastructure at scale — measured on a DIFFERENT project, NOT hackathon work

**Read this subsection as evidence about the orchestration machinery, not about the
hackathon.** The figures below come from `kganjam/morphoswarm` on **2026-10-28 and
2026-10-29**, which is **before the event window** and is a **separate attack-campaign
project**. None of it is hackathon work, none of it is folded into any total above, and
nothing in §2.4, §2.5 or §9 counts it. It is here only because it is the one place where
the agent swarm's throughput was driven hard enough to be worth measuring.

Orchestra, the task orchestrator on this host, lists **1,551 tasks** for the `morphoswarm`
project — 1,434 `done`, 52 `archived`, 28 `blocked`, 23 `open`, 8 `cancelled`, 6 `failed`
(`orchestra list --project morphoswarm --all`, read 2026-11-01 09:52 PST). The repository's
own backlog holds 1,078 `M<id>` rows and retains 556 distinct `orchestra/task/<id>`
branches.

In the two days 2026-10-28/29, across every ref in that repository:

| Measure | Count |
|---|---:|
| Unique commits in the two-day window | **2,138** |
| — carrying at least one model `Co-Authored-By` trailer | **1,792** |
| Distinct `M<id>` backlog task ids named by those commits | **350** |
| Distinct `orchestra/task/<id>` branches named by those commits | 226 |

Model `Co-Authored-By` trailer lines on those commits — **2,848 lines over 1,792 commits**,
because a commit may carry more than one:

| Trailer | Lines |
|---|---:|
| Claude Opus 5 | 1,568 |
| Claude Sonnet 5.5 | 551 |
| Claude Opus 5.5 | 421 |
| Claude Haiku 5.5 | 216 |
| Claude Code (unversioned) | 87 |
| OpenAI Codex | 5 |

Command, re-runnable: `git -C ~/git/morphoswarm log --all --since=2026-10-28
--until=2026-10-30 --format='%H%n%B%n==ENDC=='`, parsed for unique SHAs, `Co-Authored-By:`
lines, `orchestra/task/<hex>` and `M<digits>`. `--since`/`--until` filter on committer
date; counts by author date differ by roughly 1% and the repository is still moving, so a
re-run will not match to the unit.

**What this does and does not show.** It shows that the orchestration layer sustained
~1,070 merged commits a day from ~175 distinct task rows a day across four model tiers,
for two days, on one host — that is a real throughput measurement of the swarm
infrastructure. It shows **nothing** about the hackathon, nothing about whether those
commits were good, and nothing about multi-agent versus single-agent performance: there was
no single-agent arm, and the work was handed out by a coordinating session sharing one git
identity.

## 2.4 Commits

| | Count |
|---|---:|
| Commits in `kganjam/delphi-frontier` | **1,595** |
| Of those, made since 2026-10-30 | **1,595 (all of them)** |
| Repository created | **2026-10-31 14:49 UTC** |
| Branches | **158** |
| Tracked files | **6,684** |
| Commits co-authored by a named model | **703** |

The repository was **created during the event** and every commit in it was made during the
event. Co-authorship breaks down as 426 Sonnet 5.5, 150 Opus 5, 120 Opus 5.5, 7 Opus 4.8.
Branch prefixes: 131 `work/`, 10 `codex/`, 10 `claude/`.

This excludes the sibling repositories (`fractastical/delphi`,
`kavitakoolkarni-bio/morpholib-delphi-branch`, `kavitakoolkarni-bio/delphi-portal`), which
carry their own commit histories.

## 2.5 GPU, CPU and services

**Nebius H100**, project shared with other hackathon teams:

| | Jobs |
|---|---:|
| All jobs listed in the shared project | **123** |
| — completed | 87 |
| — failed | 23 |
| — cancelled | 6 |
| — running at read time | 2 |
| Carrying our name prefixes | **77** |
| Submitted by this campaign's harnesses | **28** |

Campaign jobs: 19 completed, 2 running, 2 failed, 1 error, 1 provisioning. Every job is
1 GPU. Failures are kept in the record.

**Measured GPU utilisation** — the only real evidence, sampled at 1 Hz:

| Task | Samples | Mean | Max | Power |
|---|---:|---:|---:|---:|
| `ns2d-refine-h100` | 181 | **98.6%** | 100% | — |
| `ns2d-shear-demo-h100` | 52 | **96.6%** | 100% | 454 W |
| `heldout-validation-h100` | 149 | 51.6% | 55% | 121 W |

Allocation is not utilisation. Three sampled windows do not establish continuous
saturation, and the jobs used a small fraction of each 80 GiB card.

**CPU.** Google Cloud project `scienceclaw26bos-3016`: 5 instances, 1 running (16 vCPU),
quota 32 vCPU and 0 GPU; the lab account is scheduled for deletion. A Nebius CPU request
was refused with `ResourceExhausted` (limit 24 vCPU against 28 requested); a later bounded
4-vCPU job was admitted.

**Service and model receipts.**

| Receipt | Measured |
|---|---|
| Discovery embedding index | 2,444 documents embedded, 49 requests, 0 failed, 768 dimensions, 45-second window |
| Bioservices Gemini ledger | 4 calls, 7,556 input / 9,700 output tokens |
| Bio-service harvest | **105 API calls, 95 succeeded, 10 failed** across UniProt, Europe PMC, NCBI E-utilities, NCBI Datasets, Ensembl, BioModels, ZFIN |
| Structure prediction | 4 OpenFold2 predictions (mean pLDDT 41–56, low confidence, labelled) |
| Systems biology | 5 BioModels CPU simulations at curated defaults |

**Cost: unknown.** The billing meter was never queried. Zero worker creations from two
failed launch attempts does not establish zero spend.

---

# 3. What the system is

Five human surfaces and two machine surfaces, one deployment.

| Surface | What it is |
|---|---|
| **Studio** | The flying-fish project across eleven scales, each panel holding sources, models, equations, media **and its gap** |
| **Frontier** | Open questions as records: field questions, project gaps, questions the design generated |
| **Knowledge** | 21 seeded claims with conditions and review status, a graph view, semantic search over 2,444 embedded documents |
| **Evidence** | Sources with read-levels, preserved disagreements, replayable results, hashed artifacts |
| **System** | The build inspecting itself: specs, owner board, receipts, resources, unknowns |
| **REST API** | records, search, events, artifacts, graph, counts, bounded calculation |
| **MCP** | 21 tools — 18 read, 3 opt-in write |

**The eleven scales:** molecular · macromolecular · subcellular · cellular · tissue ·
organ · neural · organism · developmental · collective · ecological.

**MCP tools.** Read: `frontier_search`, `frontier_get`, `frontier_neighborhood`,
`frontier_events`, `frontier_artifacts`, `frontier_capabilities`, `frontier_discover`,
`frontier_graph`, `frontier_catalogue`, `frontier_project_inspect`,
`frontier_design_context`, `frontier_artifact_inspect`, `frontier_simulate`,
`frontier_engineer`, `frontier_proofs`, `frontier_formalize`, `frontier_belief`,
`frontier_plan_experiments`. Write, opt-in: `frontier_propose`, `frontier_lease`,
`frontier_transition`.

Public reads need no login. Writes need an **individual contributor credential**; each
request authenticates as its own principal and the server holds no shared token. A
proposal enters as `proposed` and waits for review elsewhere. **Recorded check: 12 of 12
passed**, including rejection of anonymous writes, with zero scientific records written.

---

# 4. How it was built

**Store.** PostgreSQL 16 with pgvector on its own instance and port. Nine record types
with explicit field contracts. Every record carries namespace, kind, id and a
**content-addressed version**, so a reference pins exact bytes.

**Review is separate from the record.** There is deliberately **no accept tool**.
Proposing returns `proposed`, never `accepted`. An upstream label is an assertion by that
upstream, never local acceptance.

**Web application.** Vanilla JavaScript, no bundler, no npm build step. Two vendored
libraries with licence files and verified digests: KaTeX 0.16.47 and three.js 0.170.0. The
only build step is a data snapshot that hashes every input — currently **848 files** — and
copies a video or mesh into the published tree **only when its bytes match the declared
digest**.

**Snapshot or live.** The page asks `/api/health`. If the node answers, records, search
and solvers read it; if not, the page falls back to the committed snapshot **and says so
in a banner**. An interface the node does not serve raises `Unavailable` and the UI shows
no result rather than a plausible one.

**Releases.** The service runs from `app -> releases/<40-hex commit sha>`, an immutable
`git archive` of exactly that commit plus a build-info receipt. Only committed content is
archived, so a working tree cannot leak into a release. Deploys swap the symlink
atomically, restart, health-check three times in a row, and **roll back automatically on
any failure**. The predecessor stays on disk and addressable.

**Specifications.** Eighteen specs published with paths and sha256 digests: record types;
contribution and review lifecycle; actions, leases and execution; bundles, fork-on-conflict
and what a digest is not; the demo's acceptance list; action proposals and learning;
studio and discovery; holistic design assurance; the agent workspace; the launchable
glider; behaviour and ecology; genetic blueprints; adaptive experimentation; the biodesign
compiler; robust inverse design; demo videos; self-validation.

**Work organisation.** An owner board records **24 deliverables** at P0/P1/P2, each with a
named owner and a next acceptance.

**Two levels of claim, kept apart in code, not just prose:** *author report* (what the
repository's documents say — checkboxes, status, owners, plans) and *measured* (what a
receipt records — a run with its hash and result). **A receipt covers only what it says it
covers.**

**Progress, honestly.** The goal checklist stands at **18 of 34**. **SPEC-005's own
11-item acceptance list is entirely unchecked** — several underlying capabilities exist
and are demonstrable, but the end-to-end acceptance each item demands was never recorded.
We would rather show an unchecked box than a checked one we cannot evidence.

---

# 5. Why: motivation and prior art

**Why design a whole organism.** Studying one mechanism at a time hides where mechanisms
disagree. Building one design forces the question every model skips: *does the output of
this model mean the same thing as the input of that one?* The gaps that appear are a map
of what is unknown, and **the gap list is the scientific output**.

Two directions meet. **Bottom up:** fit known biology with equations and sourced
parameters. **Top down:** start from a goal and derive what tissue, material and flow
properties it would require. Where they disagree, there is a question to work on.

**Why Lean is the foundation.** Every other capability depends on laws stated exactly with
their conditions attached. Once a law is formalised, solvers can use it, generators can be
constrained by it, and a second project can reuse it without re-deriving or misreading it.

**What we build on:** form, function and development (Darwin's own flying-fish passage is
a cited source); multiscale mechanobiology as a framing that treats forces, cell behaviour
and tissue structure as one connected problem; knowledge that carries its context (ASK);
generative models of mechanism, where forward simulation trains a model and equations and
experiments decide; computationally designed organisms as the precedent for a design loop
with the evidence trail kept; open contestable claim networks and nanopublications.

**How we differ.**

1. **Refusal is a first-class result.** We publish the junctions we will not make, and why.
2. **Mechanically checked laws under the design**, not around it.
3. **The record refuses to accept.** No accept tool; review and identity separable.
4. **Receipts for failures too** — failed jobs, a quota refusal, an unconverged variant, a
   stopped protocol.
5. **The gap map is the product.**

---

# 6. The formal core: Lean for biology

Lean 4.35.0 (commit `eb6cafb7`) with a pinned Mathlib revision `56a0058`. Recorded runs:
the site does not run Lean, and a family whose files changed since its receipt is marked
**stale** with its source withheld.

| Family | What it states | Statements | Mutants rejected |
|---|---|---:|---:|
| Geometric similarity | Scale by ratio *k*: wing loading scales as *k*, level-flight proxy speed as √*k* | 9 | 4 / 4 |
| Unit algebra | Units as dimensions; conversions and interval mappings checked | 7 | 4 / 4 |
| Cantilever guard | A small-deflection bound for a fin ray, **plus** a proof its hypotheses are satisfiable | 3 | 1 / 1 |
| Oxygen transport | Centre-content bounds for sphere and slab under steady diffusion with uptake | 8 | 4 / 4 |
| Scaled threshold intervals | Two recorded intervals shown incompatible with a factor-of-two band | 10 | 4 / 4 |

**Totals: 37 definitions and theorems, 17 of 17 mutants rejected, all five families
current.** Positive runs exit 0 using only Lean's three standard logical axioms; negative
runs exit 1, the required result.

**What makes a proof count.** A theorem can compile and be worthless. Three checks:
it must mention the model's actual parameters; it must **fail when the law is changed**
(all 17 mutated variants were rejected — a small hand-written set, showing sensitivity to
the mutations we thought of, **not** a coverage measure); and its hypotheses must be
satisfiable.

**The solver bridge.** The constraint solver reported `unsat` on a conflict between a
level-flight lift proxy, a minimum wing loading and a maximum speed, and emitted a
**conflict certificate** compiled inside the positive Lean run. The same certificate with
the speed cap changed from 10 to 20 is **rejected**.

**What Lean does not tell you,** stated on the page itself: that a statement describes a
fish; that a parameter is correct (the oxygen family supplies no cell-specific value,
boundary condition or tissue calibration); that the Lean text is faithful to a source
passage; or anything empirical.

**Honest scale check.** What is formalised so far is textbook-level — similarity scaling,
unit bookkeeping, a beam bound, steady diffusion. Not yet biological mechanism. Its value
today is as a worked pattern for how a law, its assumptions and its checks are stored.

---

# 7. Simulations, and the layer that refuses to connect them

**31 recorded runs across 9 of 11 scales**, each with a manifest, scope, numerical checks,
hashed inputs and verified media, all labelled **simulated, not observed**.

| Scale | Runs | Examples |
|---|---:|---|
| molecular | 4 | OpenMM MD (CPU and CUDA, plus a continuation), OpenFold2 for KCNJ13 |
| subcellular | 1 | Zebrafish-GEM genome-scale metabolic model |
| cellular | 10 | Delta-Notch replay from published SBML, BETSE bioelectric, motor-clutch mechanobiology, Morpheus multicell |
| tissue | 12 | reaction-diffusion fields, fin-ray bilaminar mechanics, ERK wave, epithelial closes-vs-arrests **with a control arm** |
| developmental | 4 | neural cellular automata: pattern, seed placement, curriculum |
| organ | 7 | fin mechanics, 2D wind tunnel, aeroelastic coupling and a fidelity arm |
| neural | 1 | central pattern generator |
| organism | 10 | fixed-launch glide, WaterLily 3D CFD at L128 and L192 (Re 1000), fish3d render, Voxelyze travelling wave |
| **collective, macromolecular** | **0** | **empty — published as gaps** |

**The coupling layer.** Each model declares a typed interface
(`frontier.model.interface/1`): ports with quantity, unit, dimension, **scale**,
**context**, regime, provenance status and bounds. Three verdicts:

| Verdict | Meaning | May it run? |
|---|---|---|
| `composable` | Typed identity, exact unit conversion, or a registered calibration | yes |
| `scenario` | Only under named assumptions, unknown bounds or uncertainty | yes, labelled, never evidence about an organism |
| `refused` | A bridge is missing or inconsistent | **no** |

**Current manifest: 4 composable, 5 scenario, 4 refused.**

**The refusal that matters most.** Delta-Notch asymmetry (cellular) feeding fin flexural
rigidity (organ) is **refused**: no mapping declared; scale changes cell → organ; context
changes from the SBML's annotated species to the flying-fish design envelope; and the
Delta-Notch model is non-dimensional as stored. An assumption may differ in *regime* only
— **an assumption can never stand in for a transfer across biological scale or context.**

**Registered calibrations today: NONE.** That is the most important number on the page,
and why every cross-scale bridge is refused or assumption-level. The manifest carries an
explicit `must_not_say` list: *"the models are coupled"*, *"validated multiscale model"*,
*"the fin pattern is explained"*, *"Lean proves the biological correspondence"*.

---

# 8. Evidence, validation, and corrections

## What was measured

| What | Result | Covers — and does not |
|---|---|---|
| Lean check of the constraint certificate | all recorded checks passed | three constraints and four mutants; **not biology** |
| Glide numerical controls | all pass | analytic and step-halving controls of a point-mass model; **not a fish** |
| Attestation quote check, 15 items | 15 of 15 quotes found; **judgment 4 of 15 clean** | a hand-picked sample; **not a population rate** |

The attestation check went against us: all 15 quotes existed, but only 4 were clean — 3
`stance_overstated`, 4 `scope_narrower_than_question`, 2 with the question's core only
partly answered, 3 dated, 1 not biology. **A quote can be present and still not state what
the stance claims.** A hash or a matched string establishes neither.

## A check that disqualified our own design

Three printable variants under matched conditions (4° angle of attack, horseshoe vortex
lattice, isolated paired fins). On lattice refinement:

| Variant | Lift-coefficient change | Usable? |
|---|---:|---|
| v3a | 0.5% | yes |
| v3c | 2.9% | yes |
| **v3b** | **26%** | **no — not converged** |

v3b is published with a warning and **no feasibility score**, its non-convergence recorded
as undiagnosed rather than guessed.

## Claim reuse with a null result

One versioned claim, pinned by content hash, used by two distinct scoped actions with
causal order checked, including a **below-threshold** case. Exact rationals carried
through rather than floats. A reuse demonstration that only ever succeeds demonstrates
nothing.

## The review-corrections ledger

Five corrections, with a schema and a hash:

| id | What changed |
|---|---|
| `doe-centered-margin` | Retracted a claim that measurement halves a 0.50 misclassification rate. Root read the code and the arithmetic; the author had only run it. |
| `sequence-compiler-typed-inputs` | A reader built adversarial typed inputs the author's tests had not, and compared snapshots to git objects. |
| `compiler-cache-and-pins` | Reviewers supplied failure cases; stale pins now produce typed **blocked** results instead of passes. |
| `contributor-count-labels` | A headline contributor number moved from **4 to an 11 floor**; 31 stopped being described as active. |
| `doe-mutant-control` | An analytic screen's agreement with 192 recorded flags became meaningful **only after the control could fail**. |

**What the ledger refuses to claim,** quoted: *"that collective work outperforms a single
agent"*, *"any agent-count based advantage"*, *"any scientific breakthrough count"*. On
independence: *"All reviewers are agents or sessions of one fleet sharing one git
identity; none is an independent lab."* And: *"For every entry it is unknown whether one
agent re-reading its own work could have found the same issue."*

Four of five involved information one party had and another did not. That is a real
pattern. It is not a controlled experiment and is not presented as one.

## What was not tested

No wet-lab experiment. No registered calibration between scales. No controlled
multi-agent versus single-agent arm. SPEC-005's 11 acceptance items all unchecked. Total
spend and total model usage unknown. Which commit is deployed is listed among our own
unknowns.

---

# 9. Evidence map against the judging criteria

**Problem significance.** Eleven scales, open-ended, consequential, and the difficulty is
not compute — it is that two models each correct in their own paper cannot be connected
without a calibration nobody has measured. *Limit:* a design exercise, not a result about
a real organism.

**Scientific and technical impact.** A formal base (37 statements, 17/17 mutants); a
solver-to-proof bridge; 31 simulations across 9 scales; a refusal layer with 4 refusals and
zero registered calibrations stated plainly; a reusable record layer with 2,444 embedded
documents and 21 MCP tools; and negative results published. **Novelty we would defend:**
treating refusal to connect two models as a first-class published result, and putting
mechanically checked laws underneath the design. *Limit:* no biological validation;
textbook-level formalisation so far.

**Decentralized agency.** Capabilities genuinely distributed: 12 purpose-built harnesses
with distinct tools and context, handing work through files rather than conversation; 24
board deliverables with named owners; atomic leases and fork-on-conflict bundles so
independent operators could review elsewhere. *Limit, in our own words on the site:* much
of the event work was handed out by a single coordinating session; the node, database and
site are **one deployment**; there is no running federated network, and we do not claim a
decentralised architecture was exercised.

**Collective capability.** The corrections ledger, where in four of five entries the
correcting party held information the author did not, producing a retracted benefit claim,
a corrected contributor count, and a cache that now returns typed `blocked` results.
*Limit:* a retrospective process trace, not a controlled benchmark. A proper measurement
needs a preregistered shared-versus-isolated arm, published either way. **We did not run
it**, and would rather be marked down for a missing experiment than claim an advantage our
data cannot support.

**Execution and validation.** Publicly reachable; separate PostgreSQL with pgvector;
public MCP with 12/12 checks including anonymous-write rejection; immutable
commit-addressed releases with automatic rollback. Validation that could fail and sometimes
did: 17/17 mutants, a rejected corrupted certificate, step-halving controls, a refinement
check that disqualified a variant, a control arm, and an attestation check that failed its
own corpus. *Limit:* SPEC-005 acceptance 0 of 11; goal list 18 of 34.

**Collaboration bonus.** Reusable today: a public MCP endpoint readable without
credentials; domain-independent record contracts and the coupling interface schema; the
coupling checker itself with refusal as a legitimate verdict; the anti-triviality
discipline for formal claims; hashed artifacts and printable meshes with declared units.
*Limit:* we are not aware of another team having reused these during the event. We claim
availability and fitness for reuse, not demonstrated uptake.

---

# 10. Resources we are thankful for

**People and partners.** The team — Kris Ganjam (Allen Institute) and collaborators, with
Kavita Koolkarni's Delphi portal and Joel Dietz's Delphi claim work as sibling efforts.
**Nebius** (H100s and the Scientific AI workbench, 69 hosted tools). **Google** (Gemini
models and Google Cloud). **NVIDIA** (BioNeMo, Brev, CUDA). Upstream communities: the
nanopublication network, BioModels, UniProt, Ensembl, NCBI, ZFIN, Europe PMC, FishBase.

**Open-source code.** Lean 4.35.0 + Mathlib · Z3 5.3.3 · PostgreSQL 16 + pgvector · MCP
SDK 1.27 · libRoadRunner 2.10 · BETSE 1.5.0 · Morpheus 2.3.9 · OpenMM 8.4 · OpenFold2 ·
Evo 2 · WaterLily.jl 1.10 · Voxelyze · manifold3d 3.5.4 · trimesh 5.2 · NumPy 2.4 · SciPy
1.17 · RDFLib 7.6 · KaTeX 0.16.47 (MIT) · three.js 0.170.0 (MIT) · pytest 9 · Playwright.

**Mathematics and source texts,** each with a read-level: Darwin 1859 *Origin of Species*
ch. VI (full text) · Fish 1990 wing design and scaling (full text) · Park & Choi 2010
gliding aerodynamics (full text) · Davenport 1992 wing-loading (abstract) and 2003
allometric limits (listing) · Lovejoy et al. 2004 beloniform phylogeny (abstract) · Xu et
al. 2013 stem neopterygian (search summary) · Daane et al. 2021 the *lat4a* × *kcnh2a*
interaction phenocopying flying-fish fin proportion (full text) · Collier et al. 1996
Delta-Notch · Alben et al. 2007 fin-ray mechanics · Hayden et al. 2021 ERK trigger waves ·
Wang et al. 2021 Zebrafish-GEM (CC-BY-4.0). *Listing a source is not reading it, and a
search summary is a lead rather than evidence.*

**Data.** BioModels, UniProt, Ensembl, NCBI Datasets and E-utilities, ZFIN, Europe PMC,
FishBase, Delphi claims and nanopublications imported with provenance preserved. NCBI
lists exactly one Exocoetidae genome: *Hirundichthys speculiger* **GCA_018398805.1**;
Ensembl has none, so medaka is the nearest annotated proxy.

**Licences.** All vendored web libraries are MIT with licence files and verified digests.
Imported records keep upstream licences. Darwin's text is public domain.

---

# 11. The Xenobot / computationally designed organism line

A **12-engine catalogue** ranked by value to this project: Voxelyze, Morpheus, BETSE and
OpenMM already running; PhysiCell, CompuCell3D, SOFA SoftRobots (+Inverse),
reconfigurable-organisms, voxcraft-viz and a CPM-DDPM surrogate source-only; voxcraft-sim
**blocked**.

**Real licence findings.** The cdorgs website's licence statement disagrees with the
LICENSE files in the repos it links. `reconfigurable_organisms` declares CC0 at root while
vendoring Voxelyze, whose headers say LGPL-3.0-or-later. `license: null` from the GitHub
API means opposite things in different repos — hiding LGPL for Voxelyze and BSD-3 for
PhysiCell. It reports a missing root LICENSE file, not a missing licence.

**voxcraft-sim, the GPU engine the published work used, does not compile on modern CUDA.**
The probe ran and failed honestly: source fetch verified (1,247,489 bytes, sha256 matched,
14/14 files match the pin); CMake configured against CUDA 13.1 with arch forced to
`sm_90`; the build failed on **`cudaDeviceSynchronize` called from device code** at ten
sites, an API removed from device code in CUDA 12, plus a Boost 1.83 header failure under
nvcc 13.1. Receipt status `COMPILE_FAIL`, first error preserved verbatim, no retry.

**The audit that corrected us.** An independent Voxelyze review **withdrew an agreement
claim**: an earlier "~2.74%" used changing denominators; recomputed, raw SI displacement
differs by **15.5739%**. One frozen check still **fails** its bound (0.017479 against
0.01). A spread claimed as "about five orders" is **4.2277**. The artifact is a **45 g
soft-voxel ground-contact benchmark, not tissue, not a microcarrier**, and its prescribed
thermal expansion is **not** measured cellular contractility.

**The microcarrier project** holds three **preregistered endpoints with falsifiers** —
`passive-control`, `pattern-dependence`, `mirror-symmetry` — and `runner: null`. The
experiment was fully specified and never run; harnesses are now executing it. Its sources
are read at **abstract level only**, and the record keeps visible that the published
constructs move by **cilia** while contraction is this project's own modelling choice.

---

# 12. If you read only one thing

Open https://frontier.morphoswarm.ai/#/studio/flying-fish and count how many scale panels
say *"no model exists"*. Then open `/#/engineering` and see which model connections were
refused. The claim is that **publishing those two lists honestly is more useful than a
polished pipeline whose joints are unsupported** — and that a mechanically checked base of
laws is what makes the refusals principled rather than merely cautious.
