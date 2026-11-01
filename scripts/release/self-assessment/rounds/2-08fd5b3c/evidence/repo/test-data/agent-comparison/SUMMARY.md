# Four-arm agent comparison: single agent vs isolated workers vs centralized swarm vs decentralized swarm

The measured collective-vs-single comparison the blind rubric assessors asked for in
[`scripts/release/self-assessment/SUMMARY.md`](../../scripts/release/self-assessment/SUMMARY.md) (issues #41, #61, #62).
Run by Amit Shenoy's swarm thread on 2026-10-31 and imported unchanged from
[PR #36](https://github.com/fractastical/delphi/pull/36) (`dashboard/public/t/swarm/` at `fab9a2d2`) into
[`four-arm/`](four-arm/). This file and [`four-arm.json`](four-arm.json) are generated from `four-arm/results.json` and
`four-arm/results2.json` by `node test-data/agent-comparison/build.mjs`; no number is re-scored here.

**Task.** For each of 20 claims (the top 10 by dataset-resolvability testability for Darwin and for Thompson, frozen in
`four-arm/claims.json` and `claims2.json` before any run), write one pre-registered empirical test plan naming exactly one
real public dataset that could decide it. Every arm uses the same model (`claude-sonnet-5-5`, headless `claude -p`),
prompt, output schema, tools (WebFetch, WebSearch only) and budget. Plans are scored mechanically by
`four-arm/code/verify.mjs`: every URL and DOI is fetched; the primary metric is **verified datasets out of 20** (landing page
returns 2xx and names the dataset), and **fabricated identifiers** (404/410/DNS failure/nonexistent DOI) must be 0.

**Arms** ([PREREG.md §Arms](four-arm/PREREG.md)): *single*, one agent, one call, all 20 claims; *isolated*, 20 parallel
workers, one claim each, no feedback; *centralized*, a king assigns claims to domain queens and routes verifier failures
back as retries and escalations; *decentralized*, no planner, three queens pull tickets from a shared board and post
done/gap notes and tips. **Decision rule, pre-registered:** A beats B if A has 0 fabricated identifiers and A's verified-dataset count exceeds B's by at least 2 claims. Under 2 claims is reported as no difference. Primary run only; replicates never replace the primary.

**Pre-registration.** `four-arm/PREREG.md` was written 2026-10-31T05:52:04Z, before the first run (05:57:46Z); the
experiment-2 section at 06:27:23Z, before its first run (06:28:12Z). The timestamps rest on the session transcript,
not a commit hash, because the hub held all commits ([DEVIATIONS.md](four-arm/DEVIATIONS.md)). Experiment 2's
predictions were written down before it ran and are compared with the outcome in DEVIATIONS.md.

## Experiment 1: web tools allowed, used by no arm (budget $3 per arm)

| Arm | Verified / 20 | Checker-only | Fabricated ids (all attempts / final plans) | Calls | Wall min | Cost (USD, list) | Replicate verified |
|---|---:|---:|---|---:|---:|---:|---:|
| single | **13** | 13 | 0 / 0 | 1 | 2.64 | 0.57 | 15 |
| isolated | **17** | 17 | 0 / 0 | 20 | 1.98 | 2.60 | 15 |
| centralized | **19** | 19 | 0 / 0 | 26 | 2.7 | 2.98 | 19 |
| decentralized | **18** | 18 | 1 / 0 | 22 | 1.8 | 3.28 | 18 |

| A | B | A verified | B verified | Verdict (pre-registered rule) |
|---|---|---:|---:|---|
| centralized | single | 19 | 13 | centralized beats single |
| decentralized | centralized | 18 | 19 | no difference (under 2 claims) |
| centralized | isolated | 19 | 17 | centralized beats isolated |
| decentralized | single | 18 | 13 | decentralized verified more but fails the hard constraint (1 fabricated identifier), so no win |
| isolated | single | 17 | 13 | isolated beats single |

Best collective arm with 0 fabricated identifiers: **centralized**, 19 vs 13
(margin **+6 claims**, 5.19× the cost). The weakest multi-agent arm still beat
single by 4. The decentralized arm verified 18 but one first-attempt plan named a nonexistent NCBI
accession (corrected after the board's gap note), so under the strict all-attempts count it fails the hard constraint;
final-plans count is 0.

## Experiment 2: web tools required, landing page must be fetched before it is named (budget $8 per arm)

| Arm | Verified / 20 | Checker-only | Fabricated ids (all attempts / final plans) | Calls | Wall min | Cost (USD, list) | Replicate verified |
|---|---:|---:|---|---:|---:|---:|---:|
| single | **12** | 12 | 0 / 0 | 1 | 1.96 | 0.52 | — |
| isolated | **16** | 17 | 0 / 0 | 20 | 2.16 | 4.48 | — |
| centralized | **18** | 19 | 0 / 0 | 26 | 3.62 | 5.61 | — |
| decentralized | **17** | 18 | 0 / 0 | 26 | 2.73 | 6.37 | — |

| A | B | A verified | B verified | Verdict (pre-registered rule) |
|---|---|---:|---:|---|
| centralized | single | 18 | 12 | centralized beats single |
| decentralized | centralized | 17 | 18 | no difference (under 2 claims) |
| centralized | isolated | 18 | 16 | centralized beats isolated |
| decentralized | single | 17 | 12 | decentralized beats single |
| isolated | single | 16 | 12 | isolated beats single |

Best collective arm: **centralized**, 18 vs 12
(margin **+6 claims**, 10.74× the cost). Weakest multi-agent arm over single: +4.
Zero fabricated identifiers in every arm. The prediction that the single agent would improve with web tools was wrong:
it fell from 13 to 12, leaving 8 claims as honest nulls after 13 fetches in one context.

## What it shows, and what it does not

- **Shown:** on the same task, same model and same budget, every multi-agent arm beat a single agent by at least
  4 of 20 verified datasets in both experiments, twice the pre-registered margin, with no fabricated identifier in
  any final plan. Replicates (experiment 1) kept the ordering: single 15, isolated 15, centralized 19, decentralized 18.
- **Not shown:** a ranking among the three multi-agent arms. Centralized vs decentralized is "no difference" in both
  experiments; the honest cell is "any multi-agent arm beats a single agent by ≥4 of 20".
- **Cost:** the single agent costs a fifth (experiment 1) to a tenth (experiment 2) of a swarm arm. Its shortfall is mostly blank plans from context
  exhaustion, not worse dataset picks (experiment 2: 8 of 8 shortfalls blank, 0 named-but-unverified). On a cost-per-
  verified-dataset basis the single agent wins; the collective wins on coverage.
- **Limits:** n=20 per experiment; one model in every arm, from the same provider as the builder; "verified" means the
  URL resolves to a page that names the dataset, not that the dataset can decide the claim; no assessor from another
  provider has scored the plans; held-out clade Aves is touched by two claims (DEVIATIONS.md). A sister project with
  deterministic specialists (delphi-evolve) reported no collective advantage, so the gain belongs to the regime where
  context and attention are the bottleneck.

## Claim-level results (primary runs)

✓ verified, ✗ dataset named but not verified, ∅ no dataset named, · untouched.

### Experiment 1

| Claim | single | isolated | centralized | decentralized |
|---|:-:|:-:|:-:|:-:|
| darwin1859-ch09-03 | ✓ | ✓ | ✓ | ✓ |
| darwin1859-ch12-08 | ✗ | ✗ | ✓ | ✓ |
| darwin1859-ch12-02 | ✓ | ✓ | ✓ | ✓ |
| darwin1859-ch12-09 | ✗ | ✓ | ✓ | ✓ |
| darwin1859-ch01-09 | ✓ | ✓ | ✓ | ✓ |
| darwin1859-ch01-10 | ✓ | ✓ | ✓ | ✓ |
| darwin1859-ch11-13 | ✓ | ✓ | ✓ | ✓ |
| darwin1859-ch12-04 | ✗ | ✓ | ✓ | ✓ |
| darwin1859-ch11-16 | ✓ | ✓ | ✓ | ✓ |
| darwin1859-ch12-10 | ✗ | ✗ | ✓ | ✓ |
| thompson1917-ch03-05 | ✓ | ✓ | ✓ | ✓ |
| thompson1917-ch17-13 | ✓ | ✓ | ✓ | ✓ |
| thompson1917-ch03-08 | ✓ | ✓ | ✓ | ✓ |
| thompson1917-ch15-01 | ∅ | ✓ | ✓ | ✓ |
| thompson1917-ch04-13 | ✓ | ✓ | ✓ | ✓ |
| thompson1917-ch03-07 | ✓ | ✓ | ✓ | ✓ |
| thompson1917-ch03-17 | ✓ | ✓ | ✓ | ✓ |
| thompson1917-ch14-02 | ∅ | ∅ | ✓ | ∅ |
| thompson1917-ch03-24 | ✓ | ✓ | ✓ | ✓ |
| thompson1917-ch05-24 | ∅ | ✓ | ∅ | ∅ |

### Experiment 2

| Claim | single | isolated | centralized | decentralized |
|---|:-:|:-:|:-:|:-:|
| darwin1859-ch05-06 | ∅ | ✗ | ✓ | ∅ |
| darwin1859-ch04-22 | ∅ | ✓ | ✓ | ✓ |
| darwin1859-ch11-01 | ∅ | ✓ | ✓ | ✓ |
| darwin1859-ch10-16 | ✓ | ✓ | ✓ | ✓ |
| darwin1859-ch09-14 | ✓ | ✓ | ✓ | ✓ |
| darwin1859-ch10-12 | ✓ | ✓ | ✓ | ✓ |
| darwin1859-ch09-04 | ✓ | ✓ | ✓ | ✓ |
| darwin1859-ch14-03 | ∅ | ✓ | ✓ | ✗ |
| darwin1859-ch12-05 | ∅ | ✗ | ✗ | ✓ |
| darwin1859-ch04-13 | ✓ | ✓ | ✓ | ✓ |
| thompson1917-ch07-04 | ∅ | ✓ | ✓ | ✓ |
| thompson1917-ch14-06 | ✓ | ∅ | ∅ | ✓ |
| thompson1917-ch11-08 | ✓ | ✓ | ✓ | ✓ |
| thompson1917-ch11-10 | ✓ | ✓ | ✓ | ✓ |
| thompson1917-ch14-05 | ✓ | ✓ | ✓ | ✓ |
| thompson1917-ch17-06 | ∅ | ✓ | ✓ | ✓ |
| thompson1917-ch13-02 | ∅ | ∅ | ✓ | ∅ |
| thompson1917-ch02-01 | ✓ | ✓ | ✓ | ✓ |
| thompson1917-ch03-18 | ✓ | ✓ | ✓ | ✓ |
| thompson1917-ch03-13 | ✓ | ✓ | ✓ | ✓ |

Per-claim plans and the verifier's fetch record for every attempt are in `four-arm/runs/<arm>/plans/`, `verify/` and
`log.jsonl` (experiment 1) and `four-arm/runs2/` (experiment 2). Every claim id resolves in `docs/claims.json`.
