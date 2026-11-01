# SPEC-014 — Biodesign compiler and design iterations

Status: user-directed target, October 31, 2026. Existing design history is an
initial artifact lineage view, not an implemented whole-organism compiler.

SPEC-017 specifies self-validation for these assemblies: exact validation
contracts, separate assurance dimensions, meaningful negative controls and
dependency invalidation. Forward/inverse round trips test model consistency;
they do not establish biological function or make a missing coupling executable.

## Organism variants as pinned assemblies

Each organism variant is a versioned assembly manifest referencing exact subsystem
versions: regulatory/construct blueprint, cell programs, tissue/material models,
geometry, mechanics/flow, neural/controller and ecological context. A reference
to a missing design is an unresolved dependency, never a default successful part.

Record parent variants, changed knobs, rationale, producing Action, source/evidence
hashes, evaluation contexts, known contradictions and every unresolved interface.
Keep biological designs separate from manufactured print derivatives and display
poses. Siblings are alternatives; dates alone do not imply an evolutionary path.
No whole-genome design is inferred from a list of genes or regulatory candidates.

## Compiler stages and outputs

1. Resolve exact components and provenance; reject dangling or changed hashes.
2. Check typed interfaces: units, coordinate frames, species/assembly, cell/stage,
   time/length resolution, conserved quantities and permitted input domains.
3. Evaluate declared constraints and analytic/formal checks. Return a specific
   conflict or unsatisfied constraint with the affected components and inputs.
4. Construct only supported simulation couplings and their execution plan. Missing
   biological mappings generate an Experimentation question, not an invented law.
5. Run selected models, retain numerical/model-domain failures, and attach results
   and uncertainty to that exact assembly. Physical validation is separate.

Produce a report with separate axes: structural consistency, constraint
feasibility, executable coupling, numerical checks, empirical calibration and
biological implementation. Do not collapse them into one success badge. A model
that compiles may still fail an experiment. An unresolved bridge is different
from a violated constraint; neither should disappear when a renderer succeeds.

## Inspection and comparison

The selected organism, subsystem and intervention share context across Design,
Claims/Evidence, Equations, Experimentation and History. A history entry shows
before/after parameter and component changes, rationale, measured versus predicted
outcomes, invalidated results and the next open problem. Changing a regulator must
not silently reuse an old expression simulation as if its inputs were unchanged.

Show multiple complete variant manifests, including incomplete/failed assemblies,
in a gallery. Compare common metrics under matched conditions; visually appealing
variants do not receive invented feasibility scores. Existing regional assurance
and interface uncertainty views supply the evidence dimensions.

## Acceptance and initial scope

- [ ] Immutable assembly manifest with exact component pins and parentage.
- [ ] At least two alternative variants and one retained failing or unresolved
  assembly; report the actual failed interface, not an arbitrary status label.
- [ ] Interface checks with a deliberate incompatible unit/context/hash control.
- [ ] Change-impact analysis invalidating affected cached results.
- [ ] Per-level history/diffs and links back to equations, artifacts and experiments.
- [ ] Constrained variant exploration tied to actual model outputs and provenance.

A future generative model may propose these assemblies or learn from compiled
synthetic examples. Synthetic labels encode the simulator/constraint system;
empirical data must calibrate its biological reliability. This is the proposed
forward-data training direction, not a claim that such a model is already trained.
