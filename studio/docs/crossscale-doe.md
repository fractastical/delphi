# Cross-scale candidate screen and measurement selection

Finite worked case, mechanical layer only. All outcomes are **simulated or prospective** under a declared
linear beam model and assumed latent laws. No measurement, no response rows, no empirical accuracy, no
biological success probability, no wetlab order.

Flow: 30 candidates (6 lengths x 5 EI multipliers) -> four screens -> FEM refinement of survivors (both load
shapes, 64 recorded draws) -> finalist -> measurement-plan selection against an equal-budget baseline.
Code: `engineering/experimental_design/crossscale_screen.py`. Artifacts: `artifacts/crossscale-doe/`
(protocol frozen and committed before the run; `manifest.json` pins code and input hashes).

## Results (read from `result.json` / `candidates.json`)
- Controls: analytic screen reproduces all 192 recorded (candidate, draw) pass flags, 0 mismatches
  (anchors 20/33/34 of 64); zero load passes, 10^6 load fails; a wrong-exponent mutant changes 86 flags.
- Funnel: 10 rejected by length < 0.12 m (assumed lift proxy), 6 by EI cap 3 (assumed), 6 by pass fraction
  < 0.5 (some candidates carry two reasons), 0 by Pareto dominance, 10 survivors. FEM and analytic flags
  agree on every refined case (0 disagreements; that is numerical consistency, not validation).
- Finalist `L0.12-EIx3` (63/64). **This is the corner of two assumed constraints, not a discovery**; the
  tie-break is declared, flight consequence and stiffness cost are unknown.
- Measurement, target = finalist's log margin to the linear limit (prior SD 0.75, from assumed latents):
  baseline R2x2 (in-flow tip twice, cost 6) is rank 1 of 3, because repeats share the assumed discrepancy
  and cannot separate load from stiffness. Selected plan R1x1+R2x1+R4x2 (cost 6) is full rank: posterior
  margin variance 0.055 vs 0.092 (variance reduction 1.08x the baseline's, posterior variance 40% lower).
  Model-based sign-misclassification 0.10 vs 0.13 vs 0.50 with no measurement.
- Honest weakness: R1 alone (cost 2) already removes 0.455 of 0.566 variance, so the extra spend buys
  little; the top plan in noise/cost sensitivity (6561 scenarios) varies (R1x1+R2x1+R4x2 first in 2074,
  R1x2+R3x1 in 1165); the baseline is not beaten in 315 scenarios. Rankings depend on assumed noise and cost.
- Forward-hypothesis discrimination (uniform vs tip load) from saved fields: parameter-free statistic
  ln[w(L)/w(0.5L)]; d' = 0.44 at assumed SD 0.2, so ~21 independent specimens for d' >= 2.

## Instrument contracts
Eight contracts (observable, unit, cross-section, forward/noise model, calibration/context, reference,
uncertainty, acceptance, status). V1/V2 read saved simulation fields (`simulation_derived`; max
|w_saved - w_analytic|/L = 1e-10 at sections 0.25..1.0 over 384 cases; a unit-mislabelled instrument fails).
R1-R4 are physical proposals with assumed noise; P1 (reporter) and P2 (growth->EI) stay
`proposed_uncalibrated`. `instrument-flow.svg` is the shareable visual.

## Bidirectional
Forward seq->function: only the last arrow is computed. Inverse function->seq: executed only as target
observable -> mechanical candidate set; no sequence or genome inversion is attempted.
`interface-map.json` lists proposed tests at each level with blockers.

## Not done
No real data, no calibration of noise/cost, no regulatory or growth model, no GPU, compiler/site untouched.
Planner contract validation (`plan_experiments`) was not used for the final plans; only `evaluate_design`
and the linear-Gaussian code were reused.
