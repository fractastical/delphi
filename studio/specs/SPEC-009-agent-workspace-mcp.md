# SPEC-009: Frontier as an agent workspace

Status: implementation in progress, October 31, 2026. Owner: codex-03.

## Outcome

An external agent can discover the same public knowledge, projects, artifacts and
open questions that a person sees in the Studio; contribute through the same
versioned store; run named bounded calculations; and request larger work without
confusing a proposal with execution or scientific acceptance.

The public Streamable HTTP endpoint is https://frontier.morphoswarm.ai/mcp.
The initial nine-tool deployment was tested with the official SDK. This spec
extends that deployment; a capability manifest reports what is actually available.

## Required workflows

- Discover claims, questions, projects and artifacts by text and typed filters.
  Hybrid retrieval names its actual engine and reports a lexical fallback when
  the embedding service is unavailable. Relevance is separate from truth.
- Retrieve an exact record version, inspect sources, conditions, limitations,
  local review state, typed graph edges and reverse uses. Head discovery must not
  silently replace a version supplied by a caller.
- Inspect a Project's requirements, scales, members, annotations and unresolved
  questions through its pinned relationships. Empty projects and missing links
  remain visible; counts do not substitute for inspectable records.
- Inspect artifacts through their producing Evidence and Action, digest, media
  type, declared availability and licence. A hosted copy is downloadable only
  after its bytes match. Text inspection is bounded and confined to published
  assets; arbitrary filesystem paths or remote fetch URLs are not inputs.
- Propose or revise Claims, Problems, Evidence, Projects and Annotations with
  typed payloads, identity, source context and an exact predecessor. The existing
  generic contribution tool remains valid; examples must show each object kind.
- Run the supported simulation previews, engineering constraints, formalization
  checker and belief calculations through their existing bounded adapters. Each
  result declares its model, effective inputs, execution identity and limitations.
  An ephemeral result is neither a persisted Evidence record nor an accepted claim.
- Propose research, design modifications, simulation sweeps, formalization and
  curation as Actions with pinned inputs, acceptance criteria, capabilities,
  resource/stop bounds and expected outputs. Claim a lease, report progress, and
  submit the resulting evidence. Proposal, ready, leased, running, submitted and
  reviewed states retain their existing meanings.
- Read the event stream with a cursor so independent agents can follow progress
  and avoid duplicate work. Idempotency keys protect retried contributions.

## Execution and attribution

Public reads require no credential. Every persistent contribution acts as the
principal whose individual bearer accompanies the request. A shared demonstration
credential has shared attribution; its users do not become independent reviewers.
Contributor authority grants neither coordinator transitions nor reviewer authority.

Immediate calculators accept declarative inputs to installed models, never shell
commands, generated Python, arbitrary Lean files or provider credentials. Model
inference and larger CPU/GPU work are explicit budgeted worker Actions, with a
capability match and execution receipt. Queuing an Action does not dispatch it or
reserve compute. The response must state which of these actually happened.

Persisted simulation results pin the effective parameters, source/model/code and
actual worker environment, scope, target and acceptance policy. A timeout or
failed numerical check remains an unknown/failed result. Artifact publication and
rendering are separately attributed steps. They do not promote biological validity.

Review, if exposed through MCP, must call the existing store policy with a
reviewer credential and preserve operator independence. Administrative credential
provisioning, unrestricted imports and infrastructure management are not public
tools. Clients never send cloud, database or repository credentials to tool arguments.

## Acceptance

- [x] Public official-SDK connection, discovery, source search and schema retrieval.
- [x] Invalid tokens and anonymous writes rejected on the deployed endpoint.
- [x] Contributor token authenticated through public HTTPS without a scientific write.
- [ ] Expanded tools and actual availability described by the capability manifest.
- [ ] Official-SDK reads cover exact Project, question, claim, graph and artifact paths.
- [ ] A supported simulation executes and exposes actual inputs, units and provenance.
- [ ] A bounded AI/work request persists as a proposed Action, with no execution claim.
- [ ] Authorized proposal/revision and worker lease flow retain existing policy gates.
- [ ] Public client checks and readable connection/workflow examples cover the release.

Checks establish software behavior on the stated release. They do not establish
faithful scientific translation, independent biological review or calibrated success.
