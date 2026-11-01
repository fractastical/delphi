# Prompt for Kris: agent-use summary of delphi-frontier and delphi-evolve

Give this to an agent with a checkout of `kganjam/delphi-frontier` and `kganjam/delphi-evolve` (and access to
the machine the harnesses ran on, if it still exists). The output is folded into the swarm record in
[`chats/SWARM_COORDINATION.md`](../../chats/SWARM_COORDINATION.md) and the collaboration summary on
[#80](https://github.com/fractastical/delphi/issues/80), beside our own snapshot, so it asks for the same
fields we count for ourselves. Everything below the line is the prompt.

---

You are writing the agent-use summary for the delphi-frontier (MorphoSwarm Frontier) and delphi-evolve
(Darwin's Bridge) repositories: how many agents of which kind did the work, when, how they were organised, and
what each group produced. It will be placed next to the Delphi team's own summary of the same kind, so follow
the shape below exactly. The reader is a judge who was not there.

Time budget: 45 minutes. A partial summary with gaps labelled "not counted" is worth more than a complete one
with guessed numbers. Stop and write what you have when the time is up.

## Rules

1. Every number comes from a file or a command you ran now. Beside each number give its source: a repo path, a
   `git log` command, a process list, a transcript directory, an API log. If you cannot find a source, write
   `not counted`, not an estimate.
2. Label every figure as one of `measured` (you computed it now), `quoted` (copied from an existing page or
   file, name it), or `estimated` (say how).
3. Every timestamp carries its timezone and a UTC equivalent, e.g. `2026-10-31 22:07 PDT (2026-11-01 05:07 UTC)`.
   Say which clock produced it (git author date, commit date, file mtime, process start, API log).
4. Keep four things apart and never add them together: agent identities (a named role or harness), live
   processes (what was running at an observation time), sessions (a top-level chat or run), and running state
   (working, idle, auth-blocked, error, unknown). Give the observation time for each.
5. A counted floor is fine; say "at least N" and why the true number may be higher.
6. No credentials, coupon codes, credit links, API keys, email addresses or hostnames that grant access. If a
   log line contains one, redact it and say so.
7. Do not read or quote the Delphi team's numbers for anything; this is your side's record only. The cross-check
   happens after both are written.

## What to produce

Two files, committed to `delphi-frontier` at `docs/agent-use/AGENT-USE-SUMMARY.md` and
`docs/agent-use/agent-use-summary.json` (or a path you name in the summary), plus a comment on
fractastical/delphi issue #80 linking to the commit.

### 1. Snapshot (one table)

Observation time with timezone and UTC; repositories and the commit hash of each at observation.

| | Count | Source | Label |
|---|---:|---|---|
| Agent identities, total (floor) | | | |
| ... of which harnesses / native children / nested children (list the role of each) | | | |
| Top-level sessions (chats, runs, directors) | | | |
| Subagents or child sessions launched by them | | | |
| Live processes at observation, by state: working / idle / auth-blocked / error / unknown | | | |
| Max sessions active in any 180 s window (and when that window was) | | | |
| Remote compute jobs: total / completed / failed / cancelled (by provider) | | | |
| Long-running background processes (name each) | | | |
| External agent identities (MCP clients, forum accounts, bots) | | | |
| Commits by repository in the window, and the window | | | |
| Spend, if known; else "unknown (not $0)" | | | |

### 2. Timeline

- First and last agent activity, each dated and sourced.
- Hourly table in UTC for the whole window: commits per repository, sessions started, remote jobs submitted,
  remote jobs finished. Provide it as CSV inside the JSON (`timeline.hourly`) and as a table in the markdown.
  Use `git log --date=iso-strict` with author date, and say so.
- Mark the quiet stretches (no commits for over an hour) and what, if anything, was running during them.

### 3. Swarm dynamics

Write these as short dated entries, each with a source, not as prose about the design:

- **Structure**: the tree of who spawned whom (director, children, harnesses), with the time each came up and,
  if known, went down.
- **Assignment**: how work was handed to an agent (brief, lease, issue, message) and where those briefs live.
- **Waiting**: every case where one agent blocked on another or on an external system (auth, quota, a review),
  with start, end and what unblocked it.
- **Review changed a decision**: every case where a second session or reviewer changed a result (retraction,
  correction, a count revised). State the before and after values and the file where the change is recorded.
  State whether the reviewer shared a git identity or model with the author.
- **Duplicated or abandoned work**: two agents doing the same thing, or work thrown away, with the reason.
- **Failures kept**: runs that failed and were retained rather than deleted (time limits, provider errors,
  refusals), with their receipts.
- **Communication channels** actually used (files, store transitions, messages, issues, MCP calls), and what
  each carried.

### 4. What the agents did, by use case

One row per use case, in this exact format so it can sit beside ours:

| Use case | Agents (count and kind) | What it accomplished (numbers with sources) | Status | Sessions or commits it came from |
|---|---|---|---|---|

Expected rows, add or drop as the record dictates: claim import and adaptation from Delphi; problems and
bridges; the flying-fish design mission; simulator and model runs (Evo2, OpenFold2, ESM2, OpenMM, BETSE,
Morpheus, neural CA: one line each with provider state and scientific-predicate state kept separate); genotype
compiler; live node and MCP server; review and audit; enzyme planner and replay in delphi-evolve; Lean
certificates; nanopubs (state unsigned-draft or published, and to which registry); site and infrastructure.

### 5. Touchpoints with the Delphi repository

Dated, sourced: when your adapter first read Delphi claims and how many versions; MCP calls to `delphisci`
(client name you used, time windows); anything of yours that cites a Delphi claim id or nanopub IRI; anything
of Delphi's that depends on a result of yours. If none crossed back, say "none".

### 6. What this record does not establish

List plainly: anything not counted and why; whether any collective-versus-single-agent advantage is shown by
your record (if the counterfactual is unknown, say so); what was observed at one point in time only.

## JSON shape

```json
{
  "observed_at": {"local": "...", "utc": "...", "clock": "..."},
  "repositories": [{"name": "...", "commit": "...", "default_branch": "..."}],
  "snapshot": [{"metric": "...", "value": 0, "floor": true, "source": "...", "label": "measured|quoted|estimated"}],
  "identities": [{"id": "...", "kind": "harness|native-child|nested-child|external", "role": "...", "up": "...", "down": "..."}],
  "processes_at_observation": {"working": 0, "idle": 0, "auth_blocked": 0, "error": 0, "unknown": 0, "observed_at": "..."},
  "timeline": {"window": {"start": "...", "end": "..."}, "hourly_csv": "hour_utc,commits_frontier,commits_evolve,sessions_started,jobs_submitted,jobs_finished\n..."},
  "dynamics": {"structure": [], "assignment": [], "waiting": [], "review_changed_decision": [], "duplicated_or_abandoned": [], "failures_kept": [], "channels": []},
  "use_cases": [{"use_case": "...", "agents": "...", "accomplished": "...", "status": "...", "sources": []}],
  "delphi_touchpoints": [],
  "not_established": [],
  "commands_run": ["..."]
}
```

Every entry in `dynamics` is `{"when": "...", "what": "...", "source": "..."}` plus the fields the section
asks for. Finish by listing the commands you ran in `commands_run`, so the counts can be re-run.
