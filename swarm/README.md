# Swarm: structure, and a measured comparison against one agent

Two things live here.

**1. The control logic.** `emperor.mjs` decides swarm structure (kings, queens per king, peer links, context budgets)
from `roster.json` plus per-queen metrics; it never reads science content. Without `metrics.json` it runs a seeded
simulation and labels the output `simulated`. With `metrics.json` (written by the comparison below) it runs in
`measured` mode. `state.json` is its output and feeds the main dashboard.

**2. The comparison (`compare/`).** Does a swarm beat a single agent at a real unit of this project's work? The task:
for 20 Darwin and Thompson claims, write a pre-registered test plan naming one real public dataset. Four arms, same
model, tools, prompt, schema and budget; a script checks every URL and DOI. Design and scoring rule were fixed before
any run in [`PREREG.md`](PREREG.md); anything that changed after is in [`compare/DEVIATIONS.md`](compare/DEVIATIONS.md).

| arm | who decides | feedback |
|---|---|---|
| single | one agent, one call, all 20 claims | none |
| isolated | 20 parallel workers, one claim each | none |
| centralized | emperor sets structure, king assigns, reviews, retries, escalates | through the king |
| decentralized | queens pull from a shared board, post gaps and tips | through the board |

Results, verdicts and every plan are on the sub-dashboard `dashboard/public/t/swarm/` (live at `/t/swarm/`), all read
from `compare/results.json`.

**When it helps, and when it does not.** A sister project ([delphi-evolve](https://github.com/kganjam/delphi-evolve),
page `/evolve/`) ran the same four-arm design on an enzyme benchmark (equal 1,000-assay budget, 100 episodes, zero false
certificates anywhere) and found no collective advantage: specialists sharing evidence 78/100, isolated 77/100, a single
planner 78/100, a single planner without its model prior 96/100. Their members are deterministic code, so every member
computes the same thing and sharing adds nothing. Ours are language models with a context limit, and the per-claim table
shows the single agent lost mainly by leaving plans blank (all 8 losses in experiment 2, 3 of 7 in experiment 1) rather
than by naming worse datasets. Collaboration paid where the bottleneck was attention. The centralized arm's wins over the
single agent are spread over 6 (experiment 1) and 7 (experiment 2) distinct claims, not one item.

**3. The partner project's build record (`frontier/`).** [MorphoSwarm Frontier](https://frontier.morphoswarm.ai/#/work?tab=built)
is delphi-frontier, the sibling project that imports our claims (see "Sibling repositories" in the root README); its "How it
was built" tab is their dated record of agents, GPU jobs, model calls, review corrections and failures. The site is a client-rendered SPA, so `node swarm/frontier/crawl.mjs` fetches the `data/snapshot.json`
the page draws from, extracts exactly the fields that tab renders into `frontier/built.json`, re-renders them as
[`frontier/BUILT.md`](frontier/BUILT.md), and records what was fetched with sha256 and retrieval time in `frontier/crawl.json`
(untouched downloads in `frontier/raw/`). Everything in it is the upstream authors' own record, quoted, not re-verified here;
the one check that runs is that a linked document's download hash equals the digest the snapshot quotes for it.
`node swarm/frontier/git-history.mjs` adds the uncurated record: it clones their default branch (commit metadata only) and
writes every commit to `frontier/git-history.json`, renders [`frontier/GIT-HISTORY.md`](frontier/GIT-HISTORY.md) (totals,
hour-by-hour beside our own `git log` in Boston time, and per stretch of `DAY-BY-DAY.md` their first and last commit plus the
subjects matching pre-registration, corrections, Lean and the Delphi import, each regex shown), and regenerates the table
between the `frontier-git` markers at the end of [`DAY-BY-DAY.md`](../DAY-BY-DAY.md). Author dates are used, with commit-date
counts beside them where a rebase moved work. `--repo <path>` reuses a clone; `--render` re-renders from the JSON.
[`FRONTIER-SUMMARY.md`](FRONTIER-SUMMARY.md) reads their record and ours together against the judging rubric: what each side
supplies, the reuse edges documented from both ends, and what would make the partnership count for the collaboration bonus.

## Reproduce

Needs Node 20+, the Claude Code CLI on `PATH` and logged in (`claude --version`), and network access. No API key is read
from the repo. Each arm costs about $3 at list price and takes 2 to 3 minutes.

```bash
node swarm/compare/run.mjs --arm single        # or isolated | centralized | decentralized
node swarm/compare/metrics.mjs                 # -> compare/results.json and swarm/metrics.json (measured queen metrics)
node swarm/emperor.mjs                         # -> swarm/state.json in measured mode
node swarm/compare/publish.mjs                 # copies data files next to the sub-dashboard
node dashboard/build.mjs && (cd dashboard && npx wrangler deploy)
```

Run the arms one at a time so wall-clock minutes are comparable. Each run writes `compare/runs/<arm>-<time>/` with one
JSON per agent call (`calls/`), the plans (`plans/`), the verifier records (`verify/`), an event log (`log.jsonl`) and
`summary.json`. The earliest full run per arm is the primary result; later ones are replicates. `--tag test` or
`--limit N` marks a run as a test, which the aggregator ignores.

Files: `compare/claims.json` (frozen inputs and the selection rule), `compare/prompt.md` and `compare/plan.schema.json`
(what every agent gets), `compare/briefs.json` (the distinct information each queen has), `compare/verify.mjs`
(the mechanical checker and its classes: resolves, fabricated, blocked, malformed).
