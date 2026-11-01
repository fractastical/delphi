# How we evaluated the work: receipts, mutants, controls and one unconverged fin
Date: 2026-11-01
Summary: Agreement between a model and itself is not evidence. These are the checks we used, a case where a check told us not to trust a number, and what remains untested.

Evaluation in this project has one rule: **a result is only as good as the check that could have shown it wrong.** A simulation that runs and a theorem that compiles are necessary, not sufficient. This post lists what we ran and, equally, what we did not.

## Receipts: what was run

Every recorded result carries a receipt with the command, the exit code, the input hashes and, where relevant, the job identifier. The site re-derives hashes when it builds, copies a video or mesh into the published tree only if its bytes match the declared digest, and shows missing evidence as unknown rather than zero.

The compute record follows the same discipline. At the last recorded inventory, our own cloud GPU jobs numbered 48: 35 completed, 9 failed and 4 cancelled, with none running at that moment. Allocated capacity is requested capacity, not measured utilisation, and the billing meter was not queried, so spend is unknown. Failed jobs stay in the table.

## Mutants: can the check fail?

For the Lean families, we wrote deliberately wrong versions of each theorem and confirmed Lean rejects them: 17 of 17 mutated blocks were rejected. The same idea applies to the solver: a conflict certificate with one number changed is rejected.

## Controls and fidelity checks

For simulations we ran paired arms and fidelity checks, and published the ones that came out unfavourably as well. Two examples from the design comparison for the three printable fin-and-body variants:

| Variant | Refinement change in lift coefficient | Usable? |
|---|---|---|
| v3a | 0.5% | Yes |
| v3c | 2.9% | Yes |
| v3b | 26% | **No, not converged** |

All three were run under matched conditions: 4 degrees angle of attack, a lifting-surface method (a horseshoe vortex lattice, which represents the wing as a grid of simple vortices) and isolated paired fins. When the lattice was refined, v3a and v3c barely changed. v3b's lift changed by about a quarter, so the manifest flags it as unusable for comparison and gives no feasibility score. We have not diagnosed why v3b fails to converge; that is recorded as open rather than guessed at. We would rather publish an unusable number with a warning than a rank order built on it.

The same attitude applies to the diffusion-model pilot on an abstract reaction-diffusion pattern problem. The visuals on the Generative biology page come from arrays returned by a recorded GPU job. Their scope line says no replacement was generated, no new simulation was run and no biological validation is claimed. The first attempt timed out before evaluation, and the recovery job was an evaluation-only rerun of the saved, unchanged model checkpoint, which is recorded as such.

## Interface checks

The public MCP endpoint (Model Context Protocol, the standard way an AI agent calls tools on a server; here it exposes search, records and bounded calculations) passed 12 of 12 recorded checks covering connectivity, search, schema discovery and rejection of anonymous writes. Those checks wrote zero scientific records, and passing them is not scientific acceptance.

## What we did not test

- **No wet-lab experiment** was run. Nothing here shows that a genotype produces a fin shape.
- **No registered calibration** links a cell-scale model to tissue or organ scale.
- **Collective advantage is unmeasured.** The build used coordinator-led allocation with specialist execution. A controlled shared-versus-isolated comparison is a separate experiment, and its result must be reported even if it shows no improvement.
- **Several goals are open**, including the full self-validation loop and extra simulators for related designed organisms.

## Why we think this is the right shape

A multiscale design will not work the first time, just as most structure-prediction outputs still need filtering and testing. What can be done up front is to make the filters explicit: units that must match, theorems that must reject mutants, refinement checks that must converge, and gaps that must be listed. Then experiments are chosen to close the largest gaps first.

[Open the System page](#/work) for dated agent, job and receipt records.
