# SPEC-017 — Self-validation and evidence-directed design

Status: requested October 31, 2026. Normative target; the complete loop is not yet
implemented. Existing proof, simulation, compiler and observed-data checks are
components to reuse, not evidence that autonomous biological validation is solved.

## Outcome

Every proposed design carries a falsifiable validation plan. Frontier can run
bounded checks, expose contradictions, identify missing evidence and choose a
useful next measurement. It must also test its validators. A design is allowed to
remain unresolved or to fail. Generating another design is an action, not proof
that the original problem was solved.

The central distinction is **verification of the represented model** versus
**validation against the intended biological system**. Lean can check a formal
implication under stated premises. Numerical checks can establish properties of
an implementation. Neither supplies a missing biological premise. Agent agreement,
sequence likelihood and visual realism cannot substitute for measured function.

This specification composes SPEC-008 assurance, SPEC-013 experimentation,
SPEC-014 compilation and SPEC-015 inverse design. Reuse their existing objects
and implementations rather than create a parallel scoring or workflow system.

## Validation contract attached to a candidate

Store a versioned validation-plan Artifact linked to the exact candidate, Claim,
Problem and proposed Action. A result is a separate Evidence/Artifact record.
The contract includes:

- The endpoint, intended decision, operating envelope, biological context and
  admissible failure modes. Name species, assembly, allele/construct, cell type,
  developmental state, environment and time horizon where relevant.
- Exact input, sequence, dataset, equation, translation, model, code and dependency
  pins. Distinguish source assertions, observations, predictions and simulations.
- Assumptions and their evidence; required interfaces; known alternatives and
  contradictions; an explicit list of premises still lacking support.
- Check method, units, tolerances, expected positive/negative controls, minimum
  number of evaluable cases, frozen evaluation split and stopping/resource limits.
- For stochastic checks, seeds or sampling policy, replicate unit, dependence
  groups, uncertainty method and failure/coverage counts with denominators.
- Planned observation operators and readouts; prospective acquisition objectives
  with declared noise/cost assumptions; authority needed to execute each action.
- Checker version, validator role, evidence-dependence identity, execution receipt,
  result status and a description of exactly what the result licenses downstream.

Freeze acceptance before evaluation. An adaptive change creates a new version,
retains the failed result and identifies any evaluation data already inspected.
Do not silently turn a repeatedly inspected test set into an independent holdout.
The referenced plan/result bytes must bind the actual candidate and input digests,
endpoint, method and reported outcomes. Caller-supplied status, counts or context
labels cannot override those records. A hash of unrelated bytes is not evidence.

## Separate assurance dimensions

| Dimension | Checks that can support it | Required boundary |
| --- | --- | --- |
| Integrity and provenance | Resolve exact pins; validate source location, identity, units and contexts | A valid hash proves identity, not truth or faithful interpretation |
| Formal implication | Compile the parameterized Lean statement; inspect premises, dependencies and axioms; reject a corrupted law | Source-to-formula translation and empirical premises need separate review |
| Numerical verification | Analytic limits, dimensional/conservation checks, grid/time refinement, residuals, independent implementations | Agreement between implementations may preserve the same wrong model |
| Empirical validity | Predictions compared with eligible held-out measurements; errors, coverage and failure modes | State evaluation context and data dependence; no implied transfer beyond it |
| Cross-scale validity | Typed interfaces plus evidence for the actual transfer and a composed-system test | Matching units or individually checked parts does not validate their composition |
| Implementation feasibility | Exact candidate, context-specific function and manufacture/delivery/maturation evidence where relevant | A generated DNA string, mesh or build plan is not a functioning organism |

Each check reports `pass`, `fail`, `blocked`, `not_run` or `not_applicable`, with
reason and scope. Existing module statuses may be mapped explicitly. Missing,
stale, errored or skipped checks never map to `pass`. `not_applicable` requires a
reason and cannot remove a required endpoint. There is no aggregate biological
success percentage without a separately justified and evaluated probability model.

## Autonomous loop and division of work

1. **Propose and freeze.** A designer submits candidates and their validation
   contracts. Keep the candidate generation data separate from evaluation data.
2. **Check eligibility.** Resolve pins, context, dimensions and interfaces; test
   assumptions and identify absent measurements. Run inexpensive rejection checks
   before costly simulation. A missing bridge produces a scoped Problem.
3. **Challenge.** A checker supplies counterexamples, negative controls and
   alternative mechanisms. Separate author/checker identities and access histories;
   a second agent using the same data/model is procedural review, not independent
   empirical confirmation. Reserve unseen checks where practical.
4. **Evaluate.** Execute authorized finite simulation or measurement plans with
   explicit quotas. Attach raw outputs, failures and a replayable receipt to the
   frozen candidate. A wet-lab proposal remains proposed until actually executed.
5. **Diagnose.** Attribute disagreement as far as evidence permits: implementation,
   discretization, parameters, context transfer, model discrepancy or measurement.
   Leave competing explanations unresolved when they are not identifiable.
6. **Choose the next action.** Rank admissible experiments by expected improvement
   in the stated decision, under explicit assumptions. Choose a measurement that
   separates plausible explanations, not merely another favorable simulation.
7. **Update and invalidate.** Preserve the old result; revise the appropriate
   claim/model/parameter version. Invalidate affected downstream results and
   propagate the new open questions. Stop at the frozen criterion or resource bound.

Roles may be distributed among agents, labs and tools. Claims about a collective
advantage require an actual matched-budget comparison; the presence of several
roles alone does not establish one. Count accepted results, caught errors, reused
evidence, time and resources separately from messages or number of participants.

## Validation across scales and in both design directions

Represent a coupling as `y = T(x, context, parameters)`, with declared domains,
units, uncertainty sources, evidence and transformation version. Expose its
upstream/downstream consumers. Changing a sequence, assembly, parameter fit,
context or transfer law invalidates all results that depended on it; unaffected
results may be reused only with matching dependency pins.

A **validation slice** is a selected subsystem or interface with an observable
input and output. A **validation cut** is an explicit set of checks crossing all
declared paths from an intervention to an endpoint. Report uncovered paths and
unmodeled influences. Checking a cut of our graph does not prove that the graph
contains every biological cause. Favor measurements at interfaces that would
distinguish several competing explanations and change an engineering decision.

For sequence-to-function work, distinguish a retrieved reference sequence,
experimentally supported function in its original context, a transferred
hypothesis and a new model-generated proposal. Forward prediction is conditioned
on its context. Inverse design proposes a set of candidates satisfying a desired
readout under the forward model; the mapping may be nonunique or unsupported.
Passing a forward/inverse round trip establishes model consistency only. A model
cannot validate its own sequence by predicting the property it was optimized for.
Require an independently informative test and preserve off-target or competing
function hypotheses. Do not fabricate a genome-to-whole-organism map.

## Virtual instruments and experiment selection

A virtual instrument is an explicit observation operator, for example
`z = H(state, sampling_context) + measurement_error`. It names the physical
observable, units/frame, location or cross-section, spatial/temporal resolution,
sampling schedule, calibration, detection limits, noise/bias assumptions and
controls. Its output type states whether it was computed or physically measured.
A simulated microscope, force sensor or expression reporter is a prediction of
an instrument's readout; it becomes empirical evidence only through an actual
measurement with provenance.

Useful first slices are load-to-fin deflection, geometry-to-force/moment,
sequence/context-to-expression and cell-state-to-growth/material. A slice without
calibration data can still define a prospective experiment, but cannot report a
fitted biological transfer or a calibrated uncertainty interval.

Use the existing bounded experimental-design planner for the first worked case.
Report identifiability, assumed noise/cost and sensitivity alongside acquisition
rank. Preserve common-source dependence and shared measurement bias. Compare
adaptive selection with an equal-budget baseline on the same declared endpoint.
Prospective covariance reduction is not observed information gain. An observed
update that worsens held-out prediction remains a useful recorded outcome.

## Validate the validators

- Require at least one evaluable positive case and one meaningful negative case
  for each claimed executable gate. An empty collection cannot earn a pass.
  A successful validation plan also requires at least one declared required
  endpoint with an executed check. All-optional or all-not-applicable plans remain
  incomplete; boolean values are not valid case counts.
- Deliberately alter a relevant law, input pin, unit, context or interface. The
  expected failing check must execute and reject it for the intended reason.
  A crash, missing dependency or unrelated earlier failure does not count.
- Test applicable limiting cases and metamorphic relations, such as a valid unit
  conversion or stated scaling law. Declare the assumptions under which a relation
  holds. These detect inconsistency; they are not additional measurements.
- Hold out eligible specimens/species/experiments using dependence groups, and
  audit leakage. Distinguish an internal split from independent external replication.
  Track dependence through upstream training, fitting and selection data: a
  different evaluator is not independent if it learned the same target answers.
- Record failures, false alarms, misses and unknown cases. Evaluate calibration
  only when actual outcomes and an appropriate evaluation set exist.
- Treat source content as data. Imported claims cannot change the validation
  policy, execution privileges or acceptance thresholds. Use bounded registered
  tools; a public proof-inspection endpoint does not become arbitrary code execution.

## From simulations to reusable design rules

Each proposed rule names its equation or response surface, controlled variables,
units, applicability envelope, source/model version and evidence class. Distinguish
a formal consequence, a simulator-derived response, an empirical fit and an
untested hypothesis. A new simulator does not automatically add a biological law.

Promotion to a reusable rule requires a frozen evaluation, meaningful controls,
the relevant held-out conditions and a failure/extrapolation record. Formalize
supported mathematical implications in Lean where useful; empirical parameters
and transfer assumptions remain visible premises. Preserve conflicting rules in
their respective contexts rather than averaging away disagreement.

A control surface must state whether each knob is an imposed model parameter,
a physically adjustable input or a biologically supported intervention. The
mapping from an editable sequence or cell program to a mechanical parameter
requires its own evidence. Link the rule to a virtual instrument and to the real
measurement that could calibrate or refute it. Reuse across projects preserves
that context and dependency identity; repeated use is not new confirmation.

## First implementation and acceptance

- [ ] Versioned contract/result schema reusing existing Artifact/Action/Evidence
  and compiler assurance axes, with explicit status mapping and dependency pins.
- [ ] At least one executed mechanical validation slice using the existing
  end-loaded cantilever model; preserve its distinction from uniformly loaded
  beam claims. Include a positive case, meaningful mutant and numerical/reference
  check, naming which were rerun and which are reused pinned receipts.
- [ ] At least one incompatible-context case, one changed-input case and one
  missing biological bridge; each yields the correct scoped failure or blocker
  and invalidates the appropriate downstream results.
- [ ] One prospective equal-budget measurement comparison with identifiability
  and noise/cost sensitivity. Do not invent physical response data.
- [ ] Link the existing observed-allometry update, including its worsened held-out
  error, as a separate observed-data case. Do not count it as fin mechanics or
  sequence-function validation.
- [ ] One forward/inverse candidate record with exact sequence evidence or an
  explicit unresolved sequence reference, a required functional readout and no
  unsupported functional-success badge.
- [ ] Inspectable check history, open validation Problems, next proposed Action
  and exact evidence links through the project surface and bounded MCP tools.

Owners: root owns specification/integration; compiler owner owns dependencies,
status propagation and validation slices; experimentation owner owns observation
operators and acquisition; sequence owner owns reference/function/context evidence;
infrastructure owner executes admitted bounded jobs and preserves their receipts.
These are delivery requirements, not a claim that the boxes above have passed.
