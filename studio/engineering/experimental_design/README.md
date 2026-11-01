# Prospective experimental design

`plan_experiments(contract)` validates an exact `frontier.experimental-design.request/1`
contract and returns prospective linear-Gaussian covariance, expected target-variance
reduction per declared cost, and identifiability diagnostics. It accepts no response
values, creates no measurement rows, and makes no store or lab writes. The result's
ActionProposal remains unlinked until exact Project/Problem references are supplied.

## Frozen cantilever example

The example compares equal assumed-cost readout plans for
`delta = F * L^3 / (3 * EI)`. It uses dimensionless log stiffness and load-scale
parameters. Different nominal force settings have the same normalized
log-deflection sensitivity `[-1, +1]` and therefore remain rank one. An independent
load-scale readout `[0, +1]` supplies a second direction. Priors, noise and costs
are declared assumptions; this is not a species-calibrated model or empirical
posterior.

Freeze and commit the protocol before computing the demo result:

```sh
python -m engineering.experimental_design.cantilever_demo freeze
git add artifacts/experimental-design/protocol.json
git commit -m "Freeze cantilever prospective design protocol"
python -m engineering.experimental_design.cantilever_demo run
```

`run` refuses an untracked or modified protocol. It writes `result.json`,
`plot-data.json` and `manifest.json` next to the committed protocol. These files
contain prospective covariance and exact code/protocol hashes; `measurement_rows`
is empty. No physical experiment is submitted or executed.
