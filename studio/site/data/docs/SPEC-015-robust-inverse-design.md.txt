# SPEC-015 — Robust inverse design across scales

Status: user-directed objective, October 31, 2026. Improved first-attempt physical
success is an outcome to measure, not an established platform result.

## Common design interface

Specify desired observables, context, constraints, editable variables, available
models and evidence. Generate multiple candidates; compile their interfaces;
evaluate under declared perturbations and model alternatives; select informative
experiments; update and preserve the entire lineage. Retain infeasible candidates
and failed simulations. Do not use rendered realism as a feasibility measure.

The design surface covers molecules, proteins/enzymes/complexes, receptors and
integrins, cell programs and specific expression, cell signaling, tissue patterns,
organ shape/material, behavior and ecology. Each scale must display its actual
capability state: sourced possibility, available tool, executed forward model,
executed inverse design, numerical checks or empirical validation. Listing a tool
or producing a candidate is not completion of every subsequent state.

## Robustness objective and reporting

- Evaluate explicit tolerance, environmental and implementation perturbations,
  plus model-discrepancy alternatives. Preserve correlations across parameters
  and interfaces; do not multiply component confidence scores into fish success.
- Declare expected-loss, worst-case or risk-quantile objective, units, constraint
  margins, cost/budget and scenario distribution. A designer-chosen distribution
  is not an empirical frequency model.
- Keep search/training conditions separate from held-out evaluation. Report
  failure rates and uncertainty under those conditions, including all candidates
  evaluated. Count solver/model-domain failures rather than dropping them.
- A wider design space may expose tradeoffs; it does not by itself demonstrate
  improved reliability. First-attempt success requires independent measured
  outcomes and calibrated predictions on relevant held-out designs.

## First prioritized demonstrations

1. Reuse the existing exact-rational mass/area/span/speed constraint solver as a
   scoped inverse feasibility calculation. Its lift proxy and assumed coefficients
   remain explicit; it does not establish whole-organism feasibility.
2. Train a bounded local-rule neural cellular automaton toward a pinned
   fish-derived pattern target, then test persistence and held-out perturbations.
   The target is an engineering objective; the learned rule is not a DNA program.
   Compare robustness training against a matched baseline if admitted by budget.
3. Couple the existing fin-control/ecology model to bounded inverse control only
   after numerical/domain controls pass. Inverse ecology requires defined
   population-level observables and local-action constraints; it is not implied
   by a visually pleasing school animation.
4. Molecular/regulatory inverse work uses permitted, context-appropriate models
   and assay evidence. Provider-stopped sequence work remains stopped; blueprint
   proposals do not count as new model execution or successful expression.

Every demonstration yields the common goal/variables/constraints, candidate
manifest, actual execution receipt, scoped result and next experiment. Link to
SPEC-013 experimental learning and SPEC-014 failed/valid assembly history.

Source: [Growing Neural Cellular Automata](https://distill.pub/2020/growing-ca/),
model and training sections read by coordinator. Its computational local-rule
growth/regeneration example is prior art; biochemical implementation is separate.
The earlier repository name `nca_link.py` refers to a contributor's glide outputs
and must not be mistaken for an executed neural cellular automaton.
