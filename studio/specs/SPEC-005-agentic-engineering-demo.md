# SPEC-005 — Agentic engineering on a shared biological frontier

**Status:** implementation contract, 2026-10-31. **Owner:** codex-03 integration.
Existing behavior is described by SPEC-001–004. Requirements below are proposed
until an execution receipt establishes them. This contract expands the earlier
read-only pilot without weakening its evidence or independence boundaries.

## Scope

The first mission is flying-fish engineering. Its constructive loop is:

`design requirement → scoped constraints → solver candidate → simulation →
counterexample / surviving candidate → revised design or new open question`.

A solver's satisfiable assignment is a candidate in its encoded model. An
unsatisfiable core names conflicting constraints in that model. Neither result
settles biological feasibility. Missing data cannot silently become a default
measurement or a satisfied constraint.

The product offers three linked views: knowledge (claims, evidence and scope),
frontier (questions and what settles them), and action (who can do the next work,
with which resources, and what happened). Multiscale engineering is a view over
those same records, not a second source of truth.

## Schema

The existing nine record envelopes remain authoritative. Domain records below
are versioned payloads/adapters linked to those envelopes; adding fields requires
backward-compatible validation and coupled tests, not an untyped second database.

| Object | Required semantics |
| --- | --- |
| Variable | Stable id, symbol, SI unit/dimension, domain and biological scale. |
| Parameter | Variable reference; value/range/distribution or explicit unknown; source locator/version; measured, fitted, assumed or design-selected; organism/context; uncertainty and transfer limits. |
| Constraint | Named relation, variables, input versions, mathematical expression, solver encoding, applicability premises, source references and the consequence of violation. Empirical envelopes are labeled as envelopes. |
| Model | Equations, state/control/input/output variables, units, solver/runtime versions, numerical method, boundary/initial conditions, calibration and validation domains. |
| Coupling | Source/target ports and scales, unit map, aggregation/time-scale assumptions, parameter transfer and an independent check. Unsupported mappings create Problems. |
| Connector | Dataset/service identifier, license/access, version/checksum and retrieval receipt; discovered, accessible, retrieved, replayed and validated are different states. |
| Tool/skill | Capability manifest, accepted input/output schemas, dependencies, bounds and observed success/failure receipts. Availability is not demonstrated competence. |
| Design | Goal, input parameter versions, applicable constraint versions, candidate assignment, solver status and scope. Rejected candidates and unknown constraints are preserved. |
| Run receipt | Exact code/input/model/environment/parameter hashes, seeds, command, hardware, elapsed time, exit status, output hashes, numerical controls and evidence kind. |
| Forecast | Resolvable event/version, horizon, probability/interval, prior/method, forecaster dependence, resolution source and proper scoring rule. No unresolved event is scored as false. |
| Priority | Named policy and reasons, prerequisites, bounded next action, estimated cost and decision consequence. Unknown utilities remain unknown. |

## Multiple scales and multiple parties

The mission indexes molecular, macromolecular, subcellular, cellular, tissue,
organ, neural/control, organism, developmental, collective and ecological scales.
Showing a scale does not claim an executable model exists there. Each scale has
its own evidence and open questions. A gene association does not establish a
parameter change in an aerodynamic model; a cross-species analogy is a proposed
transfer until reviewed.

Agents are first-class clients of the same store used by people. Discovery is
bounded and read-only by default. Opt-in writes use an operator credential kept
outside prompts, tool arguments and artifacts. Contributions remain proposed;
the executor cannot certify its own work. Leases, idempotency, stale-version
rejection and independent review apply equally to human and agent participants.
Imported peer reviews remain assertions governed by the receiving node's policy.

Open-science export preserves attribution, source versions, disagreement,
licensing and unknowns. A nanopublication draft is not published, signed or
time-anchored until a corresponding receipt exists. Hash integrity establishes
neither authority nor scientific truth.

## Solver and Lean boundary

1. The same named constraints drive candidate generation and displayed checks.
2. A bounded solver must return satisfiable, unsatisfiable, unknown or timeout;
   it must not collapse the latter two into success or failure of the science.
3. Where supported, emit an independently checkable mathematical certificate.
   A Lean receipt records theorem type, hypotheses, toolchain, code hash, exit,
   axiom audit and a law/certificate mutant that fails.
4. Proving a statement about constants is not a general biological theorem.
   The formal-to-informal correspondence and empirical premises have separate
   review dimensions. No blanket label of "Lean-verified biology" is allowed.
5. Numerical approximations require declared tolerances and convergence checks.
   Optimizing a surrogate does not validate that surrogate.

## Acceptance

Each row needs an actual run record on the integrated source. Counts of test
definitions, generated records or submitted jobs are not successful executions.

- [ ] A visitor selects a biological scale, inspects a sourced equation/parameter,
  and sees the unsupported cross-scale dependency beside it.
- [ ] A bounded design problem returns a candidate; a conflicting requirement
  returns a named conflict; a missing required input returns unknown.
- [ ] At least one model-dependent mathematical property is checked in Lean,
  and its altered law/certificate fails for the expected reason.
- [ ] A simulation consumes a candidate, records units/assumptions and passes
  positive/negative controls plus a step-size convergence check.
- [ ] One downloadable mesh has a declared unit, positive dimensions and a
  geometry-validation receipt; printability/flightworthiness not tested stays
  explicit. The mesh is a design artifact, not specimen data.
- [ ] A real MCP client discovers, proposes and leases an action, submits an
  artifact and reads its proposed status; stale lease and self-review fail.
- [ ] A persistent node survives restart; two workers cannot own one live lease.
- [ ] A versioned claim is actually used by two distinct scoped actions, with
  the reuse count derived from recorded edges and original source ids preserved.
- [ ] The frontier includes sourced field questions, project gaps and generated
  engineering questions with distinct labels; no corpus blank is called a
  field-level open problem without supporting evidence.
- [ ] All displayed result/compute/test counts are derived from receipts.
- [ ] Desktop/mobile navigation, source links, downloads and controls are checked;
  a clean build has no hidden absolute-path dependency.

## Measurement and resource use

Report accepted scoped results, useful failures, distinct reused claims, exact
input reuse, duplicate executions, reviewer work, elapsed time and actual resource
receipts. Keep proposed benefits separate from measured outcomes. Allocation
comparisons use fixed tasks, acceptance and budgets; retrospective trace replay
is labeled as such. Scaling and collective-intelligence claims remain unearned
without controlled comparisons, repeats and uncertainty.

Use CPU for cheap checks and baselines; Nebius/NVIDIA GPU for a bounded useful
batch or model run after input/control validation; Gemini for a separately
recorded review arm; BioModels/BioNeMo where their scientific scope fits; and
OpenResearch for actual run capture when accessible. Sponsor discovery, API
access and scientific execution have separate receipts. Never infer GPU use from
a hosted model name. Existing GPU owners coordinate submissions and shared-pool
capacity. No running jobs or credentials belonging to others are touched.
