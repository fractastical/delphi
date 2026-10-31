# SPEC-002 — The Contribution and Review Lifecycle

**Status:** Draft · **Version:** 0.1.0 · **Owner:** fable-lead · 2026-10-31
**Specced against:** `work/frontier-foundation` @ `42cd967`. The code is authoritative.
**Reviewer status:** single-reader (fable-lead). NOT Codex-reviewed.

> Clauses are **VERIFIED** (named test; 16-test suite green this session, exit 0) or **ASSUMED**
> (read from code). Nothing here is marked accepted.

## Scope

In scope: how a record gets in and how its *local review status* changes — provisioning and roles,
the authenticated write path, the five review statuses, the seven assessment dimensions, the
independence requirement, the acceptance gate, and the deliberate absence of any composite truth
score.

Not in scope: the field contracts of each kind (SPEC-001), the Action execution lifecycle — a
separate state machine in `action_state` (SPEC-003), and import status (`imported_unreviewed`,
SPEC-004).

**The one claim this spec defends:** nothing in this store ever computes or stores a single number
or verdict that says "this is true". Acceptance is a *node-local, policy-stamped, per-dimension,
independently-reviewed* status, and it is the strongest thing the system will say. There is no score.

## Schema — the status fields

Two status fields exist, on two tables, for two different objects:

- **`local_states.status`** (`schema.sql`): `proposed | imported_unreviewed | accepted | disputed |
  rejected`. This is the review status of **any** record version.
- **`action_state.state`** (`schema.sql`): `proposed | ready | leased | running | submitted |
  reviewed | accepted | disputed | failed | blocked | expired | cancelled`. This is the **execution**
  status of an Action version only, and is SPEC-003's subject.

They are coupled at exactly one point: reviewing a *submitted* Action writes both (below).

### Authority: principals, not records

`Store.provision` (`store.py` line 70) is the only way write authority is created. It is operator
configuration, never self-service: a token (24..512 chars) is supplied in memory and **only its
sha256 is persisted** (`principals.token_hash`); roles are a subset of `{contributor, reviewer,
coordinator}`; a `daily_write_limit` of 1..1000 is attached to the **operator**. `_auth` (line 85)
hashes the presented token, looks up the principal, and enforces the required role. **VERIFIED** an
unknown token is rejected (`test_store.py::test_auth_idempotency_version_and_rollback`, first
assertion → `Unauthorized`).

## The write path (every mutation goes through it)

`_write` (`store.py` line 124) wraps every mutating operation (`submit`, `review`, `lease`,
`transition`, `import_bundle`) in one transaction with this fixed order:

1. `SELECT singleton FROM node_config … FOR UPDATE` (line 130) — **all writes serialize on one node
   row.** The module docstring says this favors inspectable correctness over throughput and claims no
   scalability result. This is what makes the atomic-lease race (SPEC-003) and the rollback guarantee
   hold.
2. `_auth(token, role)` and a namespace check.
3. **Idempotency** (line 129 region): `(actor, key)` is looked up; a replay with the *same* request
   fingerprint returns the stored response; a replay with a *different* fingerprint raises
   `Conflict`. The key must match `^[A-Za-z0-9_.:-]{1,128}$`.
4. **Daily quota** (line 140): write receipts for the operator in the last day are counted against
   `daily_write_limit`.
5. The operation runs; a `write_receipt` and the `idempotency` row commit **with** it.

**VERIFIED, idempotency and rollback** (`test_auth_idempotency_version_and_rollback`): the same
`(key, request)` returns the identical response; the same key with a changed request → `Conflict`; and
when `_event` is monkeypatched to raise mid-transaction, the record does **not** appear
(`search("rollback") == []`) and the key is free to reuse — the whole transaction rolled back.

**VERIFIED, operator quota cannot be bypassed by an actor alias**
(`test_operator_quota_cannot_be_bypassed_by_actor_alias`): the limit is keyed on the operator, so a
second actor under the same operator still hits the wall.

## Contribution: `submit`

`submit` (`store.py` line 172) validates the `Draft`, refuses `kind == "Event"`, then inside the
write transaction:

- requires `draft.namespace == node` and `draft.issuer == authenticated actor`
  (`Forbidden` otherwise — **VERIFIED**, the `carol`-spoofing-`alice` assertion);
- requires `draft.predecessor` to equal the current head version for `(namespace, kind, id)`, else
  `Conflict` ("stale predecessor") — this is optimistic concurrency on the head
  (**VERIFIED**: wrong-head and stale-evidence assertions);
- validates every typed reference exists and (for `current=True`) is itself the head
  (`_validate_refs`), which is also where the **recorded-Problem guard** fires for Actions (SPEC-003);
- inserts the record as `status="proposed"`, sets the new head, writes typed edges, and (for an
  Action) seeds `action_state='proposed'`;
- emits `record_proposed`;
- returns `{"record": ..., "local_status": "proposed", "artifact_bytes_verified": False}`.

A new record always starts **`proposed`**. Submitting is not reviewing.

## Review: `review` — explicit, independent, multidimensional

`review` (`store.py` line 252) is the **only** path that changes `local_states.status` to
`accepted`/`disputed`/`rejected`. Uploading an `Assessment` *record* via `submit` does nothing to the
target's status — **VERIFIED** (`test_review_is_explicit_independent_and_multidimensional`: a forged
accepted-Assessment record is submitted, and the target stays `proposed`). The distinction is the
whole point: a review is a transaction, not a document.

Requirements, all enforced inside the transaction:

1. **Role.** Caller needs the `reviewer` role (`_write(..., "reviewer", ...)`). **VERIFIED**
   (`alice`, a contributor, is `Forbidden`).
2. **A decision.** `decision == "unreviewed"` is refused up front (`FrontierError`).
3. **Independence** (line 260): the review is `Forbidden` if the target's `issuer` is the reviewer's
   actor **or** the target's `submitter_operator` equals the reviewer's operator. So a different
   *operator*, not merely a different actor, is required. **VERIFIED** (`alias`, a reviewer under the
   same operator as `alice`, is `Forbidden`).
4. **Reviewer identity** (line 262): every `Dimension.reviewer` must equal the authenticated actor —
   a reviewer cannot attribute dimensions to someone else.
5. **The acceptance gate** (lines 264–267), only when `decision == "accepted"`:
   - **no** dimension may be `unreviewed`, `failed`, or `insufficient` (all must be `passed` or
     `not_applicable`), and
   - `target_fidelity` **and** `applicability` must specifically be `passed` (not merely
     `not_applicable`).
   `disputed` and `rejected` carry no such gate. **VERIFIED** (an assessment with one `unreviewed`
   dimension → `Conflict`; a complete one → `accepted`; a `disputed` one → `disputed`, and the target
   record bytes are unchanged across both).
6. On success: the `Assessment` is inserted as its own record, a `reviews` receipt row is written,
   `local_states.status` is set to the decision, and `review_recorded` + `acceptance_changed` events
   are emitted. For an Action target, the action-adjudication coupling in SPEC-003 also runs.

**The seven dimensions** (`DIMENSIONS`, SPEC-001): `source_fidelity`, `target_fidelity`,
`applicability`, `computational_replay_formal_check`, `statistical_adequacy`,
`independent_replication`, `empirical_relevance`. All seven must be present on every Assessment
(`complete_dimensions`), each with its own `status`, `reviewer`, `rationale`, and `evidence_links`.
A reviewer cannot silently skip a dimension; the honest move for an inapplicable one is
`not_applicable` with a rationale, which is visible, rather than omission, which is not.

### Why there is deliberately no composite truth score

There is no field, column, or function anywhere that reduces the seven dimensions to one number or
one boolean "verdict". This is intentional and is the project's central design commitment:

- Acceptance is **the conjunction of per-dimension judgements under a named policy**
  (`policy_version = "frontier-independent-review-0.1"`), recorded with the reviewer and operator who
  made each one. It is a status, not a measurement.
- It is **node-local.** `local_states` is per node; the same record can be `accepted` on one node and
  `disputed` on another, and neither is "the" truth. Imported reviews are explicitly not local
  authority (SPEC-004).
- A single scalar would invite exactly the failure `CONTRIBUTING-VERIFICATION.md` is written against:
  something that "looks well-read while recording nothing checkable" (§1, "compiling is not
  evidence"). Keeping seven named, separately-reviewed, evidence-linked dimensions means a reader can
  see *which* kind of scrutiny an acceptance did and did not survive, and a `disputed` edge stays
  first-class in the graph (`neighborhood` returns disputes; SPEC-001).

**ASSUMED** (by exhaustive reading, not by a dedicated test): no code path computes an aggregate
score; `search` and `get` return the raw status and the raw dimensions only.

## Acceptance

Bounded run, this session: **16 passed, exit 0.**

| Contract | Verified by | Status |
|---|---|---|
| New record starts `proposed`; submit ≠ review | `test_review_is_explicit_independent_and_multidimensional` | VERIFIED |
| Uploading an accepted-Assessment record does not accept the target | same test (forged review) | VERIFIED |
| Reviewer role required | same test (`alice` Forbidden) | VERIFIED |
| Independence is per-operator, not per-actor | same test (`alias` Forbidden) | VERIFIED |
| Acceptance gate: no unreviewed/failed/insufficient dimension | same test (`Conflict`) | VERIFIED |
| Idempotency: same key+request replays; different request → Conflict | `test_auth_idempotency_version_and_rollback` | VERIFIED |
| Mid-transaction fault rolls the whole write back | same test (monkeypatched `_event`) | VERIFIED |
| Operator daily quota not bypassable by actor alias | `test_operator_quota_cannot_be_bypassed_by_actor_alias` | VERIFIED |
| Token stored only as sha256 | `store.py` line 82; not pinned by a test | ASSUMED |
| No composite score exists anywhere | exhaustive read of `store.py`/`models.py` | ASSUMED |

## Open questions

1. **`target_fidelity` + `applicability` as the hard gate.** The code privileges exactly these two
   dimensions for acceptance. Is that the right pair, and should the choice live in the *policy*
   (`policy_version`) as data rather than hard-coded in `review` (line 266), so a policy change is a
   versioned record rather than a code change?
2. **Dispute does not propagate.** Disputing a Claim does not touch the status of Evidence or
   Assessments that point at it; `neighborhood` shows the edge but nothing recomputes. Is a derived
   "has a live dispute in its neighborhood" read wanted, carefully kept out of the record itself?
3. **Re-review after supersession.** A new version starts `proposed` again; the prior version keeps
   its old status. Should acceptance of a superseded version be visibly marked stale when a successor
   appears, or is "status is per exact version" the honest and sufficient answer?
4. **Who may `provision`.** `provision` is operator-only and never exposed over HTTP/MCP, but the
   spec does not yet state the out-of-band process by which an operator decides to grant `reviewer`
   to an independent party — the independence guarantee is only as strong as that process.
