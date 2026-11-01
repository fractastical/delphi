# SPEC-013 — Adaptive experimentation within and across scales

Status: user-directed platform extension, October 31, 2026. The first planner is
prospective numerical design under stated assumptions; no wet-lab observations
or empirically learned biological law are asserted.

SPEC-017 adds the self-validation contract: explicit virtual instruments,
frozen tests and controls, validation slices across interfaces, and evidence-led
selection of the next experiment. A prospective plan remains distinct from an
executed measurement and a measured improvement in prediction.

## Purpose and design loop

An uncertain bridge is an engineering object: identify its input/output variables,
context, candidate mechanisms and missing measurements. Propose experiments,
compare their expected decision value, freeze a protocol, execute through an
appropriate resource/lab, ingest outcomes, challenge the inference and update
the applicable model and downstream designs. Preserve null/failed experiments.

The target is a useful **contextual transfer model**, not a universal biological
law. Species, genotype, cell state, developmental time, environment and measurement
method define applicability. A surrogate trained on a simulator estimates that
simulator; additional simulation alone cannot remove simulator-to-biology error.

## Per-level Experimentation tab

Every supported scale, selected region, intervention and design variant links to
an Experimentation tab preserving that exact context. Provide within-scale and
cross-scale views, current observations/model fits, unresolved interfaces,
alternative hypotheses, candidate experiments, measurement plans and revisions.

| Bridge | Measurements to consider; remaining separation |
| --- | --- |
| Sequence/regulatory context → expression | Context-matched reporter/transcript distributions and off-target cell states; accessibility alone does not establish expression. |
| Transcript → protein/activity | Protein abundance/activity and turnover, matched to transcript context; abundance is not functional activity. |
| Cell signaling/voltage → cell program | Time-resolved state, proliferation and perturbation controls; a generic voltage simulation does not calibrate fish growth. |
| Cell state → matrix/mineral/mechanics | Matrix/mineral measurements, tissue geometry and mechanical response; cell markers are not elastic moduli. |
| Fin geometry/material → deformation | Dimensioned load and displacement together, fixture/boundary conditions and material state. |
| Geometry/deformation → fluid performance | Forces, moments, actual flow and speed, matched geometry/medium; aerodynamic model discrepancy remains separate from solver convergence. |
| Neural/control model → behavior/ecology | Sensing, latency, trajectories, interactions and effort with matched controls; simulated controllers do not establish neural implementation. |

These are measurement categories, not executed experiments or complete wet-lab
protocols. Tissue/animal protocols need an executing lab's actual constraints and
review; computational planning must not silently submit them for execution.

## Versioned experiment contract

Represent a plan as an Artifact linked to an Action/Problem/Project, using existing
typed records. It must carry:

- Exact source Claims, equation/model version, proposed bridge and design version.
- Intervention variables, ranges and units; readouts, observation model, sampling
  times, detection limits, censoring/missingness and measurement noise assumptions.
- Context/eligibility, controls, randomization/blocking, biological replicate unit,
  technical repeats, batch effects and comparisons held out for validation.
- Input datasets with assembly/locus/sample identities and immutable hashes.
- Hypotheses/priors, parameterization, likelihood and discrepancy model, fit method,
  identifiability diagnostics and sensitivity to assumptions.
- Compute/lab capability, duration/cost units, concurrency/stop limits and operator.
- Protocol hash, proposal/ready/running/failed/completed/review states and lineage.
- Acquisition score with objective/assumptions, distinct from a probability of
  biological success or an observed gain in knowledge.

Observation, simulation, prediction and source assertion remain different types.
Plans without observed results have no fabricated observation rows. A scheduled
measurement may have a **prospective covariance**, not a fitted empirical posterior.
Reusing a dataset must not count it as new independent evidence. Cells, technical
repeats and simulations are not independent animal/donor replicates.

## First executable planner

Use a bounded linear-Gaussian working model with dimensionless parameters and
explicit finite prior covariance `Sigma`, observation sensitivity `h`, positive
noise variance `R` and positive declared cost. For one candidate:

`Sigma_expected = Sigma - Sigma h^T (h Sigma h^T + R)^(-1) h Sigma`.

Rank by expected reduction in a declared design-relevant variance divided by
cost. The objective's parameter scaling/weights must be explicit; adding variances
with incompatible units is invalid. Retain covariance/correlation, and reject
invalid or non-positive-semidefinite inputs. Zero-sensitivity observations provide
no information. Treat repeat observations as independent only when explicitly
declared; shared batch/measurement error cannot be averaged away by assertion.

Concrete demo: Euler–Bernoulli cantilever tip displacement
`delta = F L^3 / (3 EI)` under its small-deflection assumptions. Let the unknowns
be dimensionless log-ratios of stiffness and applied-load calibration. A normalized
log-deflection observation has sensitivity `[-1, +1]`: changing nominal force
alone preserves rank one. An independent load measurement `[0, 1]` supplies the
missing direction. Actually compute matched-budget deflection-only and mixed
plans and compare prospective covariance/rank. Noise and costs are assumed, not
measured. No synthetic response may be presented as a physical measurement.

Later work may compare model structures, learn sparse equations, fit nonlinear
surrogates and use expected information gain or reduction in decision loss.
Equation discovery must pass held-out interventions, dimensional/symmetry checks,
stability/conservation checks where applicable, and context-transfer tests. A
predictive fit does not establish causality; a formal proof checks the stated
equation, not whether biology follows it.

## Acceptance

- [ ] Generic bounded planner with exact covariance and identifiability controls.
- [ ] Frozen protocol and actual prospective comparison artifact; no observations
  or physical success probabilities invented.
- [ ] Contextual Experimentation view with controls, assumptions, proposed data
  acquisition, fit/validation gaps and iteration history.
- [ ] Agent/MCP access to inspect plans, compare choices and submit typed proposed
  Actions; calculation and submission authority stay distinct.
- [ ] An actual observed-data import/update path retaining sample identity,
  provenance, failed outcomes and independent review. Wet-lab execution pending.
- [ ] Change impact: model updates identify dependent design variants and which
  prior results require reevaluation.

Owners: native resource_scaling planner/artifacts; claude-15 source/method review;
claude-02 interface; root specification, integration and MCP. Source anchors:
[adaptive design](https://proceedings.mlr.press/v139/foster21a.html),
[Bayesian experimental design](https://papers.nips.cc/paper_files/paper/2019/hash/d55cbf210f175f4a37916eafe6c04f0d-Abstract.html),
[sparse equation discovery](https://doi.org/10.1073/pnas.1517384113).
Coordinator read primary indexed abstracts; detailed methodological review is
assigned separately. These methods are prior art, not claimed platform inventions.
