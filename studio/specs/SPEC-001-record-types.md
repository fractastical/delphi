# SPEC-001 — The Nine Record Types and Their Field Contracts

**Status:** Draft · **Version:** 0.2.0 · **Owner:** fable-lead · 2026-10-31
**Specced against:** `work/frontier-foundation` @ `42cd967` ("Import 250 sourced open problems;
separate recorded from actionable"). This is ahead of `origin/main` (`4e10ce0`); the integration
owner merges. The code is authoritative; the prose did not exist before this spec.
**Reviewer status:** single-reader (fable-lead). NOT Codex-reviewed. Independent review pending the
18:00 cut.

> Every clause is **VERIFIED** (a named test exercises it; the 16-test suite ran green this session,
> exit 0) or **ASSUMED** (read from code, not pinned by a test). Nothing here is marked accepted.

## Scope

In scope: the wire envelope (`Draft`/`Record`), the nine payload kinds and their exact field
contracts as enforced by `frontier/models.py`, the shared scalar constraints, the content-addressed
`version`, the `Problem.completeness` distinction, and the explicit typed edges a record emits.

Not in scope: how records change local review status (SPEC-002), the Action execution lifecycle and
why a `recorded` Problem cannot be acted on (SPEC-003), export/import bundles (SPEC-004), and the SQL
layer (named only where a column mirrors a field).

A record being **schema-valid is not a scientific claim of any kind** (`models.py` line 1). Validity
means the bytes parse and the digest matches — nothing about whether the statement is true, reviewed,
reproducible, or even sourced.

## Schema

### Shared scalar constraints (`frontier/models.py`)

| Alias | Constraint | Line |
|---|---|---|
| `Digest` | `^[0-9a-f]{64}$` (lowercase sha256 hex) | 16 |
| `Identifier` | 1..160 chars, `^[A-Za-z0-9][A-Za-z0-9_.:/-]*$` | 17 |
| `Short` | 1..3000 chars | 18 |
| `Text` | 1..12000 chars | 19 |
| `Strings` | `list[Short]`, max 40 items | 20 |

Every model sets `extra="forbid"` and `allow_inf_nan=False` (`Model`, line 42): unknown fields are
rejected, NaN/±Inf rejected wherever a float appears. **VERIFIED** `extra="forbid"` is load-bearing
on the wire — `test_interfaces.py::test_http_real_authenticated_proposal_and_shared_read` sends
`{"token": ...}` in the body and gets HTTP 400 (`http.py` line 28).

`KINDS` (line 14): `Problem, Claim, Evidence, Assessment, Action, Actor, ResourceOffer, Interest,
Event` — the only values the `record_versions.kind` CHECK permits (`schema.sql`).

### The envelope

**`Ref`** (46) — a pin to one exact version: `namespace: Identifier`, `kind: Kind`, `id: Identifier`,
`version: Digest`. A `Ref` names a *specific immutable version*, never "whatever is current".

**`Draft`** (250), what a contributor submits: `namespace: Identifier`, `kind: Kind`,
`id: Identifier`, `issuer: Identifier`, `source_uri: Short`, `visibility: "public" | "private"`
(default `"public"`), `predecessor: Digest | None`, `payload: dict`. Validator `typed_payload`: the
payload is validated against the typed model named by `kind`, and the canonical byte length of the
whole draft must be ≤ `MAX_RECORD_BYTES` = 65536 (line 11).

**`Record`** (268) extends `Draft` with `schema_version: "frontier-record-0.1"`, `created_at: str`
(must be tz-aware), `version: Digest`. Validator `integrity`: `version ==
sha256(canonical(record without version))`. The version **is** the content digest.

**VERIFIED** the digest is recomputed server-side, never trusted from input:
`test_store.py::test_two_store_bundle_preserves_digest_source_and_no_trust` tampers a record's
`statement`, recomputes the bundle digest to hide it, and import still fails with `ValidationError`.

### The nine payloads

Line numbers are `frontier/models.py`.

**Claim** (76): `title: Short`, `statement: Text`, `context: Text`, `assumptions: Strings`,
`limitations: Strings`, `source: Source`, `source_record_version: Short | None = None`,
`prior_review: dict = {}`. `prior_review` carries *upstream* review provenance and is **not** local
acceptance (SPEC-002).

**Source** (66), embedded in Claim/Problem/Evidence: `uri: Short | None`, `locator: Short | None`,
`source_version: Short | None`, `content_sha256: Digest | None`, `content_available: bool`,
`access: Short`, `license: Short | None`. `content_available` is a bool the submitter asserts; the
store never fetches or hashes the source bytes (`submit` returns `"artifact_bytes_verified": False`,
`store.py` line 193).

**Problem** (90): `title: Short`, `known_state: Text`, `question: Text`, `problem_kind:
"project_gap" | "computational_open_question" | "sourced_field_open_problem" |
"resolved_scope_correction"`, `novelty_status: Short`, `data_access: Text`, **`completeness:
"recorded" | "actionable"` (default `"actionable"`, line 108)**, `acceptance_criteria: Strings = []`,
`falsifiers: Strings = []`, `next_action: Text | None = None`, `required_capabilities: Strings`,
`cost_stop_bounds: Text | None = None`, `downstream_uses: Strings`, `dependencies: list[Ref] (max 30)
= []`, `source: Source`, `original: dict = {}`.

`ACTIONABILITY` (87) = `("acceptance_criteria", "falsifiers", "next_action", "cost_stop_bounds")`.
Validator `actionability` (120): if `completeness == "actionable"`, all four must be truthy, and the
error **names the missing ones**. A `recorded` Problem may omit all four. This is the load-bearing
distinction: a curated register states *what is unknown and why it matters*; it does not state what
would settle the question, what would refute an answer, what to do next, or when to stop — and those
four are exactly what an Action needs (SPEC-003).

**VERIFIED**: `test_register_import.py::test_recorded_problem_may_omit_every_actionability_field`
(a recorded problem validates with all four empty) and
`::test_actionable_problem_must_carry_all_four_and_names_the_missing_ones` (an actionable problem
missing them raises, and every missing field name appears in the message).

**Evidence** (127): `target: Ref`, `evidence_kind: "observed" | "predicted" | "simulated" | "formal"
| "source_assessment"`, `source: Source`, `created_time: TimeClaim`, `retrieved_time: TimeClaim`,
`method: Text`, `context: Text`, `assumptions: Strings`, `provenance: dict`, `source_dependence:
dict`, `uncertainty: Text`, `limitations: Strings (min 1)`, `local_id: Short | None = None`,
`provider_assessment: dict | None = None`. Validator `target_kind`: `target.kind` ∈ {`Claim`,
`Problem`}. The first four `evidence_kind` values are the observed/predicted/simulated/formal
separation the verification rules require (`CONTRIBUTING-VERIFICATION.md` §6); `source_assessment` is
a weaker "a source asserted this" tier.

**TimeClaim** (53), in Evidence: `value: str | None`, `basis: "declared" | "witnessed" | "unknown"`.
Validator: a non-null `value` must be tz-aware, and `value is None` **iff** `basis == "unknown"`.

**Assessment** (160): `target: Ref`, `policy_version: "frontier-independent-review-0.1"` (fixed to
`POLICY`), `decision: "accepted" | "disputed" | "rejected" | "unreviewed"`, `dimensions: dict[str,
Dimension]`, `independence_rationale: Text`, `limitations: Strings (min 1)`. Validator
`complete_dimensions`: the keys must be **exactly** the seven in `DIMENSIONS`. Decision semantics and
the acceptance gate are SPEC-002.

**Dimension** (153): `status: "unreviewed" | "passed" | "failed" | "not_applicable" |
"insufficient"`, `reviewer: Identifier`, `rationale: Short`, `evidence_links: list[Ref] (max 30)`.

`DIMENSIONS` (150): `source_fidelity, target_fidelity, applicability,
computational_replay_formal_check, statistical_adequacy, independent_replication,
empirical_relevance`.

**Action** (175): `target: Ref`, `title: Short`, `acceptance_criteria: Strings (min 1)`,
`required_capabilities: Strings`, `cost_stop_bounds: Text`, `cache_key: dict[str, str]`. Validator
`complete_cache` (184): exactly eight cache dimensions, each non-empty ≤ 1000 chars;
`cache_key["target"] == target.version` and `cache_key["acceptance_policy"] == POLICY`. Note the
asymmetry with Problem: an Action's `acceptance_criteria` and `cost_stop_bounds` are **always
required** — an Action is by definition the actionable object. Detailed in SPEC-003.

**Actor** (194): `display_name: Short`, `operator_identifier: Identifier`, `capabilities: Strings`,
`identity_verification: "declared" | "operator_configured"`. Descriptive only; write authority comes
from a provisioned `principal` row (SPEC-002), not from an Actor record.

**ResourceOffer** (201): `operator_identifier: Identifier`, `capability: Short`, `amount: float
(>0)`, `unit: Short`, `available_from: str`, `available_until: str`, `restrictions: Strings (min 1)`,
`terms: Text`, `verification_status: "unverified" | "declared" | "checked"`, `verification_reference:
Short | None`. Validator `window`: `available_until` strictly after `available_from` (tz-aware);
`"checked"` requires a reference and is "still subject to local review".

**Interest** (222): `target: Ref`, `signal: "following" | "can_contribute" | "resource_offer" |
"blocked_by_this"`, `explanation: Text`, `downstream_reference: Short | None = None`. Validator:
`"blocked_by_this"` requires `downstream_reference`.

**Event** (238): `event_type: EventType`, `target: Ref`, `actor: Identifier`, `operator:
Identifier`, `witnessed_at: str`, `details: dict`. `EventType` is a closed set of 16 values.
**Events are not submittable**: `submit` raises `Forbidden` on `kind == "Event"` (`store.py` line
174); they are emitted only inside transactions by `_event`.

### Typed edges a record emits

`references()` (290) returns the **only** edges a record produces, from explicit typed fields, never
inferred from free text:

- `targets` — from `payload.target` (Evidence, Assessment, Action, Interest).
- `depends_on` — one per `payload.dependencies[]` (Problem).
- `review_evidence` — one per `dimensions[*].evidence_links[]` (Assessment).

`neighborhood` returns these one hop out, disputed assessments included, "no implicit support
inference" (`store.py` line 250).

## Acceptance

Bounded run: `systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0
-p RuntimeMaxSec=600 bash scripts/test_postgres.sh`. Suite this session: **16 passed in 23.39s, exit
0.** The register importer was also run directly against the real file (below).

| Contract | Verified by | Status |
|---|---|---|
| Unknown fields rejected (`extra="forbid"`) | `test_interfaces.py::test_http_real_authenticated_proposal_and_shared_read` | VERIFIED |
| `version` = recomputed content digest; tamper detected | `test_store.py::test_two_store_bundle_preserves_digest_source_and_no_trust` | VERIFIED |
| Predecessor/head chaining; successor supersedes head | `test_store.py::test_auth_idempotency_version_and_rollback` | VERIFIED |
| Evidence must pin a Claim/Problem; missing/stale refs rejected | `test_store.py::test_auth_idempotency_version_and_rollback` | VERIFIED |
| Seven dimensions mandatory on Assessment | `test_store.py::test_review_is_explicit_independent_and_multidimensional` | VERIFIED |
| `recorded` Problem may omit all four actionability fields | `test_register_import.py::test_recorded_problem_may_omit_every_actionability_field` | VERIFIED |
| `actionable` Problem must carry all four; error names the gaps | `test_register_import.py::test_actionable_problem_must_carry_all_four_and_names_the_missing_ones` | VERIFIED |
| Whole register imports; none actionable; provenance measured | `test_register_import.py::test_whole_register_imports_and_none_of_it_is_actionable` | VERIFIED |
| Events cannot be submitted directly | `store.py` line 174; not pinned by a test | ASSUMED |
| Per-field scalar bounds (Short/Text/Strings/Identifier) | pydantic aliases; not individually pinned | ASSUMED |

## The register finding, measured this session

The design above exists to carry a real result. I ran `scripts/import_register.py` against
`/home/ubuntu/git/morphoswarm/data/problems/register.yaml` (sha256
`a0155552a2bcda40688d38e95c4069828922d21042c87c9c6cf96311de94f7d7`) in the bounded scope, exit 0:

- **problems_in_register: 250 · importable: 250 · rejected: 0** — every curated open problem maps to
  a valid `Problem` draft.
- **actionable: 0 · recorded_not_actionable: 250** — not one carries the four actionability fields,
  and the importer invents none of them (`import_register.py` sets `completeness: "recorded"`).
- **Provenance, measured not assumed:** `with_locator_and_quote: 34`, `topic_reference_only: 68`,
  `no_source_at_all: 148`. So **102 of 250 have any source and 148 (59.2%) have none.**

This corrects an earlier generalization (that each of the 250 carries a PMC id, a locator and a
verbatim quote) that was true only of the first record read; the whole-register count is above and
is pinned by the register test. The 148 unsourced problems are labelled in the record's own
`source.access` as "a curator's statement, not a sourced field-level open problem, and must not be
presented as one" (`import_register.py` line 97), and the 68 topic-reference-only ones are labelled
"WEAKER … supports the problem's topic and not any specific statement" (line 92). An evidence layer
built on this register **must** carry those labels forward. (The `import_register.py` docstring line
74 says "74" for the references path; the code counts, and the test pins, **68** — the docstring is a
stale typo, noted for the integration owner, not edited by me since it is the foundation worker's
file.)

## Known defect — Problem still has no typed unlock edge

Recorded rather than papered over. The `completeness` split fixed the import-blocking defect (sourced
problems now enter as `recorded`), but a separate defect remains:

**`Problem.next_action` is free text (`Text | None`, line 111) and there is no `unlocks` field.** The
seed data carries an `unlocks` relation (`seeds/frontier-problems.json`), but `seed.py` flattens it
into `downstream_uses: Strings` — prose phrases, not `Ref`s — so "Problem A unlocks Problem B" is
representable only as unstructured text. `references()` emits no `unlocks` relation and `typed_edges`
never records one, while the inverse (`dependencies` → `depends_on`) *is* typed. The graph is
navigable one way and lossy the other. **VERIFIED** by reading `references()` (`models.py` 290–301)
and `seed.py`. Because every payload model is `extra="forbid"`, adding `unlocks` to a submitted
payload today is rejected on write; closing this is a model change, not a data change — see Open
questions.

## Open questions

1. **A typed `unlocks` edge.** Proposal, not current behavior: add `unlocks: list[Ref] = []` to
   `Problem`, emit an `unlocks` relation in `references()`, validate each target is a
   `Problem`/`Claim`, and migrate the flattened `downstream_uses` strings. Breaking; belongs to a 0.3
   schema.
2. **Promoting `recorded` → `actionable`.** Nothing in the store yet records *who* supplied the four
   fields that turn a recorded problem actionable, or whether that supply should itself be reviewed.
   An unreviewed promotion is an unreviewed scientific judgement about what would settle a question.
   Should promotion require an independent review (SPEC-002), or at least an Event?
3. **The 148 unsourced problems.** They import today as `sourced_field_open_problem` with
   `provenance_path: "none"` and an access note that says they are not sourced. Is `problem_kind`
   itself wrong for them — should an unsourced curator statement get a distinct `problem_kind` so the
   label is structural, not only prose in `access`?
4. **`content_available` / `artifact_bytes_verified`.** Both are submitter-asserted or constant
   `False`. Is there ever a tier where the store (or a separate checker) fetches and hashes source
   bytes, or is that permanently out of scope by design?
