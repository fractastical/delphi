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
  margin variance 0.055 vs 0.092 (variance reduction 1.08x the baseline's).
- Decision exercise (corrected, v3): true margin = m0 + theta.target with the finalist's actual offset
  m0 = 1.27 (Gaussian P(inside) 0.95; recorded pass fraction 63/64). Sign-misclassification: no measurement
  0.043, baseline 0.028, selected 0.023. **The absolute gain is small because the finalist is already
  probably inside the regime.** The v2 figures (0.50 / 0.13 / 0.10) came from a centered m0 = 0 exercise and
  are withdrawn. This is a model-based exercise under assumed Gaussian latents, not a fish error rate.
- Sensitivity (6561 noise x cost scenarios, full 255-plan replicate grid enumerated once): the first-ranked
  plan varies widely (the largest shares are R1x3+R3x3 467, R2x1 496, R1x2+R3x2 638, R1x1+R3x2 542). A
  discounted-cost case (all prices x0.5) considers 109 newly feasible plans and its best plan is one of them
  (variance reduction 0.532 vs 0.511). The baseline is affordable in 4374 scenarios and ineligible in 2187; it
  is not beaten in 315 of the 4374 comparable ones. R1 alone (cost 2) already removes 0.455 of 0.566.
- Dependence: R1/R3/R4 repeats are treated as independent in the nominal model (optimistic for repeats on one
  ray or setup). Giving every readout a shared term equal to its independent variance leaves
  R1x1+R2x1+R4x2 as the best nominal-budget plan (variance reduction 0.500).
- Forward-hypothesis discrimination (uniform vs tip load) from saved fields: parameter-free statistic
  ln[w(L)/w(0.5L)]; d' = 0.44 at assumed SD 0.2, so ~21 independent specimens for d' >= 2.

## Instrument contracts
Eight contracts (observable, unit, cross-section, forward/noise model, calibration/context, reference,
uncertainty, acceptance, status). V1/V2 read saved simulation fields (`simulation_derived`; no empirical calibration was performed and the instrument model is NOT calibrated to biology; max
|w_saved - w_analytic|/L = 1e-10 at sections 0.25..1.0 over 384 cases; a unit-mislabelled instrument fails, and an off-grid section raises the specific ValueError, both executed in the run).
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

## Provenance and superseded results (v3)
Protocol v3 was frozen at `c151433` before the v3 run. `artifacts/crossscale-doe/superseded/SUPERSEDED.json`
holds the timeline, the withdrawn claims and hashes. The v2 outputs (11b5c30) are preserved unchanged. Two
v1-protocol runs were overwritten before being committed and are irrecoverable; a regenerated copy of code
4bf5481 is kept and labelled as a reproduction. Code was edited after the v1 freeze twice (C3 mutant fix,
key rename plus SVG); the protocol does not pin code, so v3's manifest hashes the code files used.

## Compiler slots
`instrument-contracts.json` carries compiler02's six required fields per instrument and proposes slots
(I1 P1; I2 P2; I3 R1, R4; I4 V1, V2, R2, R3) for compiler02 to confirm. A slot's contract_ref is
`{path, sha256 from manifest.json, pointer /contracts/<index>}`.
