# SPEC-007 — MorphoSwarm Frontier: studio, knowledge and open work

Status: implementation contract, October 31, 2026. This extends SPEC-005 and
SPEC-006 following the owner's design, search, visualization and project-model
instructions. A requirement below is not a claim that it already works.

## Product and navigation

MorphoSwarm Frontier combines an organism-design studio with a shared scientific
frontier. Flying Fish is the featured project, not the platform's schema or scope.
Delphi supplies the versioned claim, evidence and contribution foundation. The
repository remains `delphi-frontier`; existing record identifiers do not change.

The two primary journeys are connected:

1. **Studio:** choose a project, select a subsystem and scale, inspect its models,
   equations, parameters, source evidence and design artifacts, then propose or
   run an explicitly supported change.
2. **Frontier:** discover an open question, inspect its context and dependencies,
   find applicable knowledge and assets, propose bounded work, track its state,
   contest evidence and reuse a result in another project.

Scientific results, computational checks, source assertions and conceptual
illustrations retain distinct labels. Robustness means a stated result over a
declared uncertainty set with controls and failure cases. It never means a
guarantee that a new organism will work on its first attempt.

## First-class projects and anchored discussion

Projects carry a mission, explicit design requirements, biological scales and
version-pinned members. A member's role, subsystem and rationale explain why it
belongs. Shared records can belong to multiple projects without being copied.

Annotations attach a comment, question, challenge or proposed edit to an exact
record version and, where relevant, an artifact digest and a bounded selector:
named mesh part, normalized image rectangle, equation symbol or parameter path.
Selectors are interface anchors, not biological coordinate systems by default.
Replies and revisions preserve history. Contribution identity comes from the
authenticated record envelope. An annotation does not silently edit an artifact,
execute a job, accept evidence or impersonate another agent.

The same mechanisms support cooperative proposals and adversarial challenges.
Agent identity, operator identity and independent review remain separate.
Aggregate plans are still non-executable; constituent Actions retain their own
permissions, bounds, leases and acceptance rules.

## Readable knowledge and artifact pages

Claims, questions, models, artifacts and evidence open in readable views with a
clear title, main statement or result, scope, source, limitations and relationships.
Equations render with the existing local KaTeX assets; unsupported syntax has a
visible readable fallback. Raw JSON is an optional inspection mode.

Nanopublications are an interoperable import/export representation, not a limit
on the internal schema or user interface. Imported nanopublications and draft
exports use the same entity and artifact views. A draft is not described as
published, signed or independently accepted.

Every implemented simulation should have an appropriate view: animation/video,
interactive plot, parameter response plot or a static infographic when motion
would add no information. Visualizations link to their producing Action, exact
inputs, code/settings and output digests. Rendering is distinct from numerical
simulation. No generated illustration stands in for model output or measurement.
Available print meshes receive actual mesh previews and download links.

The Flying Fish project maps molecular, macromolecular, subcellular, cellular,
tissue, organ, neural, organism, developmental, collective, ecological and
evolutionary work. Each layer needs an indexed, inspectable asset and an explicit
frontier: an implemented model/result where available, otherwise a sourced model
or design proposal and the next concrete missing measurement/computation. A
diagram connection does not establish a mechanistic or calibrated transfer.

## Hybrid discovery

Index all public record kinds and artifact metadata using actual embeddings in
the dedicated PostgreSQL instance. Record provider/model, dimensions, text recipe,
input hashes, exact record/artifact identities, coverage and failures. Never embed
private records. Lexical search remains available and is visibly identified when
semantic retrieval is unavailable. Similarity scores are not truth probabilities.

`GET /api/discovery?q=&kind=&limit=12&mode=hybrid` returns the actual mode, typed
items, relevance explanations and index coverage. Each item includes a pinned
record Ref, an artifact digest when applicable, title, snippet, kind, local review
state, score and score kind. Query embedding calls have time, size and concurrency
bounds and a cache. UI requests are debounced, superseded requests are cancelled,
and stale responses cannot replace newer results. Keyboard navigation, empty
states and provider failures are part of the interface.

Assess lexical versus hybrid retrieval on a frozen, explicitly judged query set.
Report the exact targets, coverage, retrieval metric and outcome. Do not assert
an improvement from a few chosen screenshots.

## Knowledge and asset graph

`GET /api/graph` returns bounded neighborhoods of public exact-version records and
artifact pointers. Nodes distinguish record and artifact identities. Edges retain
their type and provenance: support, refutation, qualification, context, production,
input use, dependency, plan membership, predecessor and explicit project links.
Tentative links and similarity never appear as established causal relationships.
Namespace collisions and versions remain distinct; truncation is visible.

The viewer supports click, hover, pan/zoom, an edge legend, selected-entity detail
and a keyboard-accessible route to the same information. Large neighborhoods do
not default to an unreadable hairball. Private records must not leak through
labels, edges, counts or traversal.

## Historical design lenses

A small cited panel may connect Darwin's variation/adaptation, D'Arcy Thompson's
geometry/scaling and Wolfram's local-rule exploration to concrete tools or
experiments. It is secondary to the working studio. Historical analogy is not
validation; a geometric transform is not a developmental mechanism, and a
cellular-automaton result is not evidence that a biological design is optimal.

## Acceptance and evidence checklist

- [ ] Generic Project and anchored Annotation records persist, preserve old
  versions and enforce the existing contribution permissions.
- [ ] Flying Fish has pinned project members and useful views across all declared
  scales, with implemented assets separated from proposed work and missing links.
- [ ] A region/subsystem comment is persisted and can be retrieved at its original
  version; a proposed edit remains distinct from an executed design change.
- [ ] Every implemented simulation and available mesh has a readable visual view
  tied to actual input/output provenance; videos play and downloads match hashes.
- [ ] Typed autocomplete searches indexed records and artifacts, handles stale
  responses, and reports the actual retrieval mode and coverage.
- [ ] An actual embedding index and a frozen relevance comparison have execution
  receipts; no semantic or performance claim relies on synthetic vectors.
- [ ] Graph neighborhoods expose real relationships, versions and namespaces;
  private-record and truncation controls are exercised.
- [ ] Human-readable entity views render equations and sources without requiring
  users to read raw JSON or understand nanopublication serialization.
- [ ] A separate Playwright auditor covers every route/tab and major interaction
  on desktop/mobile, captures screenshots and failures, and rechecks critical fixes.
- [ ] The demo tells both stories: a usable design studio and a shared frontier
  that makes reusable knowledge, unknowns and coordinated work inspectable.

Execution receipts must name their actual release or input hashes. This checklist
is updated only from those receipts, not from worker intent or test definitions.
