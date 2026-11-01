# Forecast swarm

Every round, a swarm of forecasters from different model providers sets the probability that the
swarm solves each open problem in [`../problems.json`](../problems.json), and that each proposed
approach (proof, computation, data test, simulation, ...) gets done and settles its target. Rounds
repeat; later rounds start from the previous round's median and move only for named reasons (a run
logged, a claim changed status, an approach added). Rounds whose 30-day horizon has passed are
scored against what was actually logged. Latest numbers: [FORECASTS.md](FORECASTS.md).

| Path | What |
|---|---|
| `INSTRUCTIONS.md` | What a forecaster is asked to do, and the definitions of the four probabilities. |
| `runs.json` | The run log: what the swarm actually attempted against an approach and what came of it. The only source of outcomes. Append only. |
| `rounds/<id>/` | `ROUND.json`, `snapshot.json` (evidence at open), `queue/slice-NN.json` (what forecasters read), `forecasts/<model>--<slice>.json`, `aggregate.json`. |
| `history.json`, `scores.json`, `FORECASTS.md` | Built by `merge.mjs`: medians per round, Brier scores, the readable table. |

## One round

```sh
node scripts/site/build-claim-graph.mjs                  # refresh docs/claims.json so claim states are current
npm run forecast:open                                    # snapshot, diff vs last round, cut slices -> rounds/r<N>-<date>/
# launch one forecaster per (model, slice): each reads INSTRUCTIONS.md and its slice, writes forecasts/<model>--<slice>.json
npm run forecast:validate                                # checks every file in the latest round
npm run forecast:merge                                   # aggregate.json, history.json, scores.json, FORECASTS.md
```

Round 1 is blind. From round 2 each slice carries the prior and `changes_since_last_round`, and a
forecaster that moves a problem more than 0.10 must give a `change_reason`.

## Logging a run

When the swarm runs an approach, append to `runs.json` (`approach`, `date`, `outcome`, `settled`,
`solves_problem`, `artifact`, `note`) in the same commit as the Lean report or claim-test result it
points to. A forecast is scored on `p_complete` (a `completed` run in the 30 days after the round),
`p_settle` (the `settled` flag of that run) and `p_solved_30d` (any run with `solves_problem`).
Brier scores are per forecaster, so the table shows which model is calibrated, not only which is optimistic.
