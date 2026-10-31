# SPEC-008: Holistic organism design, equation graph and regional assurance

Status: implementation in progress, October 31, 2026. Owner: codex-03.

## Product outcome

A design goal produces multiple candidate fish, an inspectable graph of equations
and a map of the evidence supporting each region and interface. Working through
development, growth, maintenance and function creates open questions wherever
the models cannot be connected. Those questions become bounded proposed actions;
new evidence can revise the candidate, its uncertainty and the work frontier.

This is an engineering application of the shared scientific substrate. Other
projects can reuse the same versioned claims, laws, datasets and checked models.
No transfer to a new species, developmental stage or regime is inferred merely
from matching parameter names or units.

## Technical analogues and their limits

AlphaFold separates local structural confidence from relative-placement and
interface confidence. Its pLDDT, PAE and ipTM outputs motivate separate regional
and interface views here; their thresholds and numerical scales are not portable
to organism engineering. See the [EMBL-EBI confidence guide](https://www.ebi.ac.uk/training/online/courses/alphafold/alphafold-3-and-alphafold-server/how-to-assess-the-quality-of-alphafold-3-predictions/).

The [AlphaFold 3 paper](https://doi.org/10.1038/s41586-024-07487-w) also motivates
retaining and testing multiple candidates. Our candidate ensemble is a declared
engineering search, not a trained model of biological success or an equilibrium
distribution. Sequence likelihood from a foundation model, structural confidence,
numerical agreement and organism function remain different quantities.

## Design bundle and equation registry

A versioned DesignBundle pins its Project, candidate geometry, region identifiers,
equation registry, parameter state, simulator Actions and Evidence, interface graph,
assurance map and open Problems. A view is a projection of those objects, not a
second unversioned scientific database.

Every implemented element exposes:

- Equation identifier and rendered LaTeX, with the actual implemented expression
  or source selector and model version.
- Variables, units, domain, boundary/initial conditions, timescale and spatial
  support; inputs, outputs, intervention controls and observables.
- Parameter value or distribution and its basis: measured, fitted, sourced for
  another context, assumed, design requirement or unknown.
- Exact source locations and artifact hashes; cited organism, tissue and stage.
- Solver/proof and simulation receipts, including failed checks and mutations.
- Input/output ports, transformations, transfer assumptions and affected regions.
- Missing mechanism or data, the decision it blocks and the next bounded action.

The graph must distinguish mathematical compatibility, assumed transfer and
empirically supported coupling. Dimensional consistency is necessary but does not
establish causal or biological validity. Editing a parameter invalidates downstream
derived results; prior results remain pinned to their original inputs.

Lineage is bidirectional: source passage/data → Claim → equation/model → Action
→ Evidence/artifact → design element, with reverse usage queries. Generated claims
and equations identify their producing agent/model, exact inputs, model/tool version,
prompt or procedure where shareable, output digest and subsequent checks. A source
citation and a model-generated interpretation are separate objects. The integration
audit reports orphaned artifacts, unpinned equations and missing producers instead
of silently displaying them as grounded. Identical evidence reused in several
places retains one source-dependence identity.

## Regional assurance vector

Display separate axes; no uncalibrated weighted average masquerades as a probability.

| Axis | Allowed evidence | What it does not establish |
| --- | --- | --- |
| Formal property | Actual Lean/solver run, parameterized law, assumptions, mutation gate | Truth of empirical premises or fidelity of translation |
| Numerical fidelity | Analytic oracle, grid/time convergence, conservation, implementation comparison | Agreement with a real fish |
| Empirical validity | Held-out measured outcomes, matching context, residuals and uncertainty | Transfer outside the tested domain |
| Parameter coverage | Declared sampled envelope and sensitivity, data provenance | That assumed ranges describe nature |
| Cross-scale transfer | Typed ports, explicit transformation and measured coupling check | That separate validated parts compose correctly |
| Ensemble robustness | Count of candidates/scenarios meeting a frozen endpoint | Probability of biological success without a justified sampling model |

Each axis has a status, scope, receipt and limitations. Missing evidence is unknown,
shown separately from failed evidence. The colour legend names the selected axis.
Unknown regions stay visible. Proof status is a logical result under premises,
not a learned per-region probability.

An interface matrix, inspired by PAE's presentation, shows the state of every
required transfer. Quantitative error is in declared physical units when measured;
otherwise it is null. Do not invent pairwise error values to fill a heatmap.

## Simulation accuracy and uncertainty

Separate numerical error, parameter uncertainty, model discrepancy, measurement
noise and context transfer. A possible model is

\[
y_{obs}(x)=f_h(x,\theta)+\delta_{numerical}(h,x,\theta)
          +\delta_{model}(x)+\epsilon_{measurement}.
\]

This is a decomposition to investigate, not evidence that its components are
identifiable from available data. Analytic and refinement checks constrain
numerical error; measured held-out outcomes are needed to estimate model error.
Report interval coverage and calibration only on an actual stated evaluation set.
Repeated use of one source or one model is not independent confirmation.

Shared inputs induce dependence between regions. Keep their provenance groups and
joint draws; do not multiply regional scores as independent probabilities. A
whole-design success event must name endpoint, environment and horizon. If its
probability is supplied from explicit uncalibrated priors, label it a scenario.
No calibrated whole-fish success probability is currently established.

## Adaptive design and full-cycle scope

Retain several candidate designs and counterexamples. The initial assay compares
three fin candidates under correlated parameter draws, mesh refinement and a
load-distribution challenge. Its endpoint and sampling recipe are frozen before
the run. Render actual states and attach receipts to each candidate and region.

Proposed actions should resolve a named blocked requirement: parameter measurement,
alternative model, finer simulation, formalization, source review or biological
experiment. Expected information gain or expected utility is computed only when
its probability and utility inputs are explicit; otherwise show qualitative
blocking dependencies and costs with unknowns.

The lifecycle graph covers development, scale and fin formation, growth,
maintenance, swimming/gliding and environmental interaction. A living-bioprint
path additionally needs material/cell identity, geometry, transport, viability,
mechanics and maturation criteria. Current resin-print geometry does not discharge
those criteria. Missing stages remain first-class Problems.

## Acceptance checklist

- [ ] Selecting a fish region reveals equations, units, sources and current inputs.
- [ ] Every implemented model connects to real execution and output artifacts.
- [ ] Unsupported interfaces remain explicit and prevent a whole-design validation claim.
- [ ] Regional axes and interface matrix retain unknown, failed and checked states.
- [ ] At least three actual candidate/scenario comparisons and a discriminating control.
- [ ] Numerical accuracy and empirical accuracy are shown separately.
- [ ] A parameter edit creates a new bounded preview and marks dependent results stale.
- [ ] A gap produces a pinned Problem and proposed Action that can accept new Evidence.
- [ ] Desktop/mobile browser review checks equations, legends, region selection and sources.
