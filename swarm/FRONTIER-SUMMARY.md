# MorphoSwarm Frontier and Delphi: what the combined record shows, against the judging rubric

[MorphoSwarm Frontier](https://frontier.morphoswarm.ai/#/work?tab=built) ([kganjam/delphi-frontier](https://github.com/kganjam/delphi-frontier))
is a partner project: built at the same hackathon on Delphi's claims and MCP server, listed under "Sibling repositories" in
our `README.md`. Its "How it was built" tab is their dated build record. This file reads that record and ours **together**,
against the five ScienceClaw criteria and the collaboration bonus in `scripts/release/self-assessment/rubric.json`, to show
what each side supplies that the other lacks, where the reuse between us is already documented from both ends, and what
would make the partnership legible to a judge.

Source for Frontier: the crawl in [`frontier/`](frontier/) (snapshot `7d83f2d56c3b`, retrieved 2026-11-01 14:18 UTC; full
tables in [`frontier/BUILT.md`](frontier/BUILT.md)), and their `git log` in [`frontier/GIT-HISTORY.md`](frontier/GIT-HISTORY.md)
(default branch at `7b9bee4`, 1,350 commits, retrieved 2026-11-01 16:00 UTC, lined up with ours hour by hour and folded into
[`DAY-BY-DAY.md`](../DAY-BY-DAY.md#frontier)). Frontier numbers from the crawl are **their own record, quoted, not re-verified
by us**; the commit counts we computed ourselves from the clone. Our numbers name the repo file they come from. No score is
assigned to either side.

## The one-paragraph version

The two records are complementary by construction. Delphi holds the claims and the verdicts: 1,763 claims, 91 theorems
(73 Lean-checked), 174 claims tested against data with pre-registered criteria, and a pre-registered four-arm swarm
comparison (single 13/20, isolated 17/20, centralized 19/20, decentralized 18/20). Frontier holds the execution layer and
the receipts: a live node with public read API and MCP endpoint (27 of 27 dated live checks passing), 48 Nebius GPU/CPU
jobs with telemetry, 15 scoped model/simulator runs (Evo2, OpenFold2, ESM2, OpenMM, BETSE, Morpheus, a neural CA), sha256
on every receipt row, and an audited contributor count (at least 23 identities, a stated floor). Frontier imports our
claims through a live adapter (their count: 1,326 claim versions; our MCP log: 30 `frontier-adapters` sessions on
Oct 31), and their repository audit counts our 136 commits beside their 1,102 in the same day. Both sides state the same
null plainly: no swarm advantage is established by Frontier's record, and ours is one task at n = 20 per arm. The gap a
judge will see is that the reuse runs one way (they read us) and no result yet crosses back.

## Reuse already documented from both ends

| Edge | Frontier's record | Our record |
|---|---|---|
| Frontier reads Delphi claims | Live adapter importing 1,326 claim versions (`README.md`, sibling section, their count); 228 `delphi`-path mentions in their snapshot; MCP `delphisci` configured on their side. | `COLLABORATIONS.md`: client `frontier-adapters`, 30 sessions 18:10–18:51 UTC, 24 of the 27 sessions in the 19:12 snapshot; ~1,000 `delphi_get_claim` calls from `corpus-census` earlier the same day (unattributed). |
| Frontier counts Delphi activity | Repository audit, window 2026-10-31 07:00 to 2026-11-01 05:23 UTC: delphi-frontier 1,102 commits, **fractastical/delphi 136**, delphi-portal 8, morpholib-delphi-branch 6. | Same four repositories are the ones `README.md` and `docs/PORTAL.md` name. |
| Delphi counts Frontier activity | Their default branch cloned and logged: 1,350 commits (343 merges), 10:49 Oct 31 to 10:40 Nov 1 Boston, 1,115 of them in the overnight stretch against our 211 by author date (`frontier/git-history.json`). | Their `frontier_adapters` adapter (14:46 Boston) and bulk Delphi import (14:52) commits fall in the same hour as the 30 `frontier-adapters` sessions in our MCP log (14:10–14:51 Boston). |
| Delphi reads Frontier | Their node is an MCP server in our `.cursor/mcp.json` (`frontier_*` tools); this crawl. | `swarm/frontier/` (this folder); sibling paragraph in `README.md`. |
| Shared sister result | delphi-evolve's enzyme four-arm null (78/77/78/96) is linked from their snapshot. | Quoted on `/t/swarm/` and in `swarm/README.md`, labelled quoted-not-reverified. |

What is **not** yet documented anywhere: a Frontier result that depends on a Delphi verdict, or a Delphi claim test that
depends on a Frontier simulation. That is the bonus's 10-anchor ("documented reuse ... that fed into their result").

## Criterion by criterion: what each side contributes

### Collective capability (25%)

- **Delphi supplies the measurement.** `swarm/PREREG.md` fixed the task and rule before any run; `swarm/compare/results.json`
  gives single 13/20 verified datasets, isolated 17/20, centralized 19/20, decentralized 18/20 (one fabricated identifier,
  so no win under the hard constraint); a second 20-claim experiment is in `test-data/agent-comparison/`. The single agent
  lost mainly by leaving plans blank.
- **Frontier supplies the process trace.** Five cases where a second session changed a decision
  (`frontier/raw/review-corrections.json`): a retracted "measurement halves a 0.50 misclassification rate" (now
  0.043/0.028/0.023); two typed-input holes in the genotype compiler; a cache serving stale passes; a contributor count
  corrected from 4 to an 11 floor; a DOE control that could not fail. Their own caveats: every reviewer is one fleet under
  one git identity, the counterfactual is unknown for every entry, and the ledger "does not show that collective work beats
  a single agent".
- **Read together**: the measurement says *whether* organisation helped on one task; the trace says *how* review changed
  decisions in practice. Neither alone covers the rubric question, and each states the limit of the other.

### Decentralized agency (20%)

- **Frontier**: a native tree (`/root` director, `/root/infra_director`, `/root/mechanobio_sim`, `/root/resource_scaling`;
  4 running at 2026-10-31 22:07 PDT), 11 harness identities with distinct roles (site, print, critic, glider-dynamics,
  review, curation), a store with leases and transitions in which no proposal can self-accept ("acceptance needs an
  independent operator elsewhere"). Their audit separates 31 live processes from workers: pane states at observation were
  1 working, 7 idle, 12 auth-blocked, 2 error, 11 unknown; max sessions active within 180 s was 18.
- **Delphi**: emperor/king/queen/worker control logic (`swarm/emperor.mjs`) running in measured mode from `swarm/metrics.json`,
  a shared board in the decentralized arm, distinct briefs per queen (`swarm/compare/briefs.json`), per-thread
  `status.json` aggregated on `/start/`, and the assessor-is-never-builder rule across providers.
- **Worth adopting from Frontier**: the four-way split of identities, roles, live processes and running state, each with
  its own observation time and a "not summed" rule. Our dashboard quotes thread counts without an equivalent audit.

### Scientific / technical impact (25%)

- **Delphi**: 174 claims tested (93 supports, 37 mixed, 30 refutes, 14 inconclusive), 89 on organisms, 91 theorems, 33 tests
  through the cross-provider faithfulness gate (`README.md`, "Current numbers").
- **Frontier**: 21 extracted claims, 7 problems, 5 bridges, a flying-fish mission with 11 scales, 13 couplings, 6 equations
  and 8 constraints; 15 scoped model executions with provider state and scientific-predicate state kept as separate
  fields (Evo2 7B ×3, one "provider completed, science runner failed"; OpenFold2 on KCNJ13, succeeded; ESM2 local pilot;
  OpenMM ×2; BETSE; Morpheus ×2, one failed; neural CA ×2, predicates failed/mixed). The primary diffusion-model run failed
  at its time limit and is retained with its 30,000-step checkpoint. BioNeMo/NIM execution: "not established".
- **Read together**: Delphi's record is claims resolved; Frontier's is capability exercised on real biology models and
  solvers, with the honest outcome that most scientific predicates are not yet met. The obvious joint result is a Delphi
  claim whose data test runs through a Frontier simulator. None exists yet.

### Execution and validation (10%)

- **Frontier is the stronger half here**: 27 dated live checks of the public node, all passed (9/9 up to 39/39 per run;
  three with 0 of 0); 843 input files hashed into the snapshot; every receipt row with path and sha256 (7 passed, 7 failed,
  19 recorded without a verdict); 12 GPU telemetry windows (mean utilisation 30–99%); controller receipts for 17 tasks
  (5 failed); two provider refusals kept (vCPU quota, Google ToS); spend stated as "Unknown (not $0)".
- **Delphi**: CI on Lean exposure (`.github/workflows/lean-exposed.yml`), pre-commit `check-exposed.mjs`,
  `npm run claims:exec` reproduction runs (`scripts/exec/runs/latest.json`), hosted `delphisci` MCP server with
  Prometheus counters (`COLLABORATIONS.md`).
- **Worth adopting from Frontier**: hashed inputs for the dashboard build, and a "Limits of this record" plus "Unknown"
  list rendered on the page itself.

### Problem significance (20%)

Delphi: candidate laws of biology from Darwin, Thompson, Wolfram, Levin and the math-bio canon, 20 open problems in
`problems/`. Frontier: a shared frontier of open questions with a design-studio instance (flying fish as an engineering
candidate, "not a validated organism"). The framing is complementary (laws and their tests; a workspace where a design
is checked against them); neither record measures this criterion.

### Collaboration bonus

The edges in the table above are real and verifiable from both repositories, which puts the pair at the 5-anchor
("published and offered, with contact") with the one-way import as the strongest item. Reaching the 10-anchor needs a
result that crosses the boundary. The cheapest candidates, in order of effort:

1. **One Delphi claim test run through `frontier_simulate`** (bioelectric or mechanobio), pre-registered in
   `test-data/claim-tests/<project>/<claim-id>/result.json` before the run, verdict recorded, cited in Frontier's reuse
   ledger (`claim_reuse`) as an external reuse of their simulator.
2. **One Frontier record that cites a Delphi verdict** by claim id and nanopub IRI (their `Claim` records already carry
   `source_uri`), and their reuse ledger marking it as reuse by another team; today it says "reuse by anyone outside this
   team is not recorded".
3. **A joint line on both dashboards** stating the import counts from both logs (their 1,326 claim versions, our 30
   adapter sessions), each labelled with which side measured it.

## What this summary does not establish

- Nothing in Frontier's record was re-run here except that one linked document hashed to the digest their snapshot quotes
  (`frontier/crawl.json`). Their snapshot is a point in time (inventory observed 2026-11-01 00:39 PDT).
- Our numbers come from `README.md` (built 2026-11-01 14:31 UTC), `swarm/compare/results.json` and `COLLABORATIONS.md`;
  denominators and deviations are in those files and `swarm/compare/DEVIATIONS.md`.
- The `frontier-adapters` client name in our MCP log is attributed to Frontier by name match and by their own statement of
  a live adapter; the log itself does not identify the caller.
- A rubric score is an elicited judgement, not a measurement. This file lists facts and gaps; it scores neither project.
