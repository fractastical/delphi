# SPEC-003 — Actions, Atomic Leases, and the Execution Lifecycle

**Status:** Draft · **Version:** 0.1.0 · **Owner:** fable-lead · 2026-10-31
**Specced against:** `work/frontier-foundation` @ `42cd967`. The code is authoritative.
**Reviewer status:** single-reader (fable-lead). NOT Codex-reviewed.

> Clauses are **VERIFIED** (named test; 16-test suite green this session, exit 0) or **ASSUMED**.
> Nothing here is marked accepted. **Note:** this store has **no job runner** — it coordinates who
> may execute and records what happened; it does not itself run anything (`__init__.py`,
> `http.py` line 1 "intentionally without job/tool execution").

## Scope

In scope: the Action record's cache key, the `action_state` execution state machine, atomic leasing,
lease expiry and owner fencing, the coordinator readiness gate, the review-adjudication coupling, and
the idempotency keys that make a retried coordination write safe.

Not in scope: Action field types (SPEC-001), the review/acceptance semantics `review` shares with
other kinds (SPEC-002), and bundles (SPEC-004). Actual compute, sandboxing, and cost metering are
**out of scope of the code entirely** and must not be implied by this spec.

## Schema — the eight-dimension cache key

`Action.cache_key` is a `dict[str, str]` whose keys must be **exactly** (`models.py`
`complete_cache`, line 184):

```
target · input · code · model · environment · parameters · scope · acceptance_policy
```

Each value must be non-empty and ≤ 1000 chars. Two are pinned to the record:
`cache_key["target"] == Action.target.version` and `cache_key["acceptance_policy"] == POLICY`
(`"frontier-independent-review-0.1"`). The cache key is the identity of *a unit of work plus the
policy it will be judged under*: same target, same inputs, same code, same model, same environment,
same parameters, same scope, same acceptance policy ⇒ the same cache key. **VERIFIED** the complete
eight-key shape is required (the `action()` fixture builds all eight; an Action is used throughout
`test_two_worker_atomic_lease_and_lifecycle`). **ASSUMED**: the store does not itself deduplicate or
memoize on the cache key — it is carried as identity/record data; no cache-hit code path exists.

### `action_state` — the execution state machine

One row per Action version (`schema.sql`), states:

```
proposed → ready → leased → running → submitted → (reviewed) → accepted | disputed | failed
                     ↑  ↘ blocked | failed | cancelled | expired
         blocked/expired ──(re-lease)──┘
```

Seeded `proposed` on submit (`_insert`, `store.py` line 156). Transitions are driven by four methods:
`transition` (contributor/coordinator), `lease` (contributor), and the Action branch of `review`
(reviewer). Acceptance is **not** reachable through `transition` — `transition` rejects any state not
in `{ready, running, submitted, blocked, cancelled, failed}` with "reviews control acceptance"
(`store.py` line 292). **VERIFIED** over HTTP: POSTing a transition to `accepted` returns 400
(`test_interfaces.py`, the `"state": "accepted"` assertion).

## The coordinator readiness gate

`transition(..., "ready")` (`store.py` line 296) requires the `coordinator` role and a current state
in `{proposed, blocked, expired}`, and re-validates references. An Action cannot be leased until a
coordinator has marked it `ready`. **VERIFIED**: leasing a freshly-submitted (still `proposed`)
Action raises `Conflict` ("too-early"), and the lease succeeds only after the coordinator readiness
transition (`test_two_worker_atomic_lease_and_lifecycle`).

## Atomic leasing

`lease` (`store.py` line 321) is the core concurrency primitive. Because every write first takes
`node_config … FOR UPDATE` (SPEC-002), leases serialize, and the claim itself is a single conditional
`UPDATE`:

```sql
UPDATE action_state SET state='leased', lease_id=…, lease_actor=…, lease_operator=…,
       lease_until=CURRENT_TIMESTAMP + <seconds> * INTERVAL '1 second', …
WHERE version=… AND (state IN ('ready','expired')
                     OR (state IN ('leased','running') AND lease_until <= CURRENT_TIMESTAMP))
RETURNING lease_until
```

If the `UPDATE` matches no row, the lease was not won → `Conflict` ("Action unavailable or lease
already held"). A fresh `lease_id` (uuid4) is minted on every successful lease. `seconds` is bounded
1..600. Only a local Action in this namespace can be leased.

**VERIFIED, exactly-one-winner under contention**
(`test_two_worker_atomic_lease_and_lifecycle`): two actors wait on a `Barrier` and lease the same
ready Action simultaneously; the test asserts **exactly one** winner and one `Conflict`.

## Lease expiry and owner fencing

The three ordinary execution transitions (`running`, `submitted`, and lease-held `blocked`/`failed`/
`cancelled`) go through the `else` branch of `transition` (`store.py` line 302), which requires:

1. `current.lease_actor == actor` **and** the supplied `lease_id == current.lease_id` — the exact
   lease, not just the right actor (`Forbidden` otherwise);
2. the lease is still live (`lease_until > CURRENT_TIMESTAMP`), else `Conflict` ("Lease expired");
3. the transition is legal from the current state:
   `leased → {running, blocked, failed, cancelled}`, `running → {submitted, blocked, failed,
   cancelled}`.

When a new `lease` is granted over an expired-but-still-`leased`/`running` row, the prior holder is
**fenced**: its `lease_id` no longer matches, so every subsequent transition it attempts is
`Forbidden`, and an `action_expired` event is emitted for the old lease. This is the correctness
property that TTL alone does not give (compare morphoswarm SPEC-010's "lease loss": an obsolete
worker must not act on a claim it no longer holds).

**VERIFIED** (`test_expired_lease_cannot_submit_and_reclaim_fences_owner`): the fixture advances
`lease_until` into the past in the DB (no sleeping); the expired holder's `running` transition raises
`Conflict`; a replacement lease is granted with a **different** `lease_id`; the original holder's
transition with its old `lease_id` is then `Forbidden`; and an `action_expired` event is present.

## Coordinator blocking/cancelling

A coordinator may force `blocked`/`cancelled`/`failed` without holding the lease (`store.py` line
299), except that a **terminal** state (`accepted`, `disputed`, `failed`, `cancelled`) cannot
transition again (`Conflict`, "Terminal action cannot transition").

## Review adjudication of submitted work

Acceptance of an Action happens only in `review` (SPEC-002), and only for work that is actually
done and independently executed. The Action branch (`store.py` line 273) requires:

- `action_state.state == "submitted"`, **and**
- the reviewer's operator ≠ the operator that held the lease (`lease_operator`) — the executor
  cannot adjudicate their own run (`Conflict`, "Only submitted work reviewed by a separate operator
  can be adjudicated").

The decision maps `accepted→accepted`, `disputed→disputed`, `rejected→failed` on `action_state`, and
emits `action_reviewed` then the matching `action_*` event, alongside the ordinary
`review_recorded`/`acceptance_changed`. **VERIFIED** (`test_two_worker_atomic_lease_and_lifecycle`):
`ready → lease → running → submitted → review(accepted)` leaves `action.state == "accepted"`, and a
further lease on the now-terminal Action raises `Conflict`.

## Why a `recorded` Problem cannot be actioned

`_validate_refs` (`store.py` line 115) raises `Conflict` when an **Action's** `targets` edge points
at a **Problem** whose `completeness == "recorded"` ("Target problem is recorded, not actionable;
supply the four actionability fields first"). This guard runs wherever references are validated —
`submit`, `lease`, `transition(ready)`, `review` — so a `recorded` problem can never acquire an
executing Action. The reasoning (SPEC-001): an Action needs `acceptance_criteria`, `falsifiers`,
`next_action`, and `cost_stop_bounds`; a `recorded` Problem has none, so there is nothing to execute
against and nothing to stop on.

**VERIFIED** (`test_register_import.py::test_store_refuses_an_action_against_a_recorded_problem`):
submitting an Action against a recorded Problem raises `Conflict` matching "recorded, not
actionable"; the **control** in the same test promotes the Problem to `actionable` with the four
fields and the identical Action then succeeds — proving the refusal is caused by actionability, not
by the target being a Problem. The whole-register test re-checks this against a real imported record
(`register-0`).

## Idempotency keys

Every method here runs through `_write` (SPEC-002), so each coordination write carries an
idempotency key (`^[A-Za-z0-9_.:-]{1,128}$`, per `(actor, key)`). A retried `lease`/`transition` with
the same key and identical request returns the stored response instead of acting twice; the same key
with a different request is a `Conflict`. This matters most for leasing: a client that retries a
lease on a flaky connection does not accidentally mint a second lease or steal its own. **VERIFIED**
indirectly — idempotency is pinned by `test_auth_idempotency_version_and_rollback` on `submit`, and
all write methods share the one `_write` path.

## Acceptance

Bounded run, this session: **16 passed, exit 0.**

| Contract | Verified by | Status |
|---|---|---|
| Eight-key cache key, target/policy pinned | `complete_cache` (`models.py` 184); exercised via `action()` fixture | VERIFIED (shape) |
| Lease before `ready` refused | `test_two_worker_atomic_lease_and_lifecycle` | VERIFIED |
| Coordinator readiness gate | same test | VERIFIED |
| Exactly one winner under concurrent lease | same test (Barrier race) | VERIFIED |
| Wrong/absent `lease_id` fenced | same test + `test_expired_lease_…` | VERIFIED |
| Expired lease cannot transition; reclaim issues new id; old owner fenced | `test_expired_lease_cannot_submit_and_reclaim_fences_owner` | VERIFIED |
| `action_expired` emitted on reclaim | same test | VERIFIED |
| Executor's operator cannot adjudicate own run | `test_two_worker_atomic_lease_and_lifecycle` (separate reviewer operator) | VERIFIED |
| Acceptance unreachable via `transition` (reviews control it) | `test_interfaces.py` (`state:"accepted"` → 400) | VERIFIED |
| Action against a `recorded` Problem refused; actionable control passes | `test_register_import.py::test_store_refuses_an_action_against_a_recorded_problem` | VERIFIED |
| Cache key is not used for memoization/dedup | exhaustive read; no cache-hit path | ASSUMED |

## Open questions

1. **No runner, by design — where does execution live?** The store coordinates leases and records
   submission/adjudication but never executes. The 24-hour contract implies an executor; this spec
   says only that any executor MUST obtain a live lease, honor `cost_stop_bounds`, stop the instant
   it loses the lease (fencing), and submit a result the lease holder's *operator* did not review.
   **Per the director's standing ruling, no GPU and no inference job runs for Frontier before a
   source-linked, bounded protocol exists.** That protocol is not specified here.
2. **`cost_stop_bounds` is free `Text`.** It is a human-readable bound, not a machine-enforceable
   one. Should an Action carry a structured budget (wall-seconds, token cap, memory cap) that an
   executor and the node can both read, so "stop" is checkable rather than aspirational?
3. **Cache key without a cache.** The eight-dimension key is validated and stored but nothing reads
   it back to skip duplicate work. Is a deliberate, auditable cache-hit path wanted (return a prior
   accepted result for an identical key), and if so, how is a stale environment/model invalidated?
4. **Lease duration vs. real work.** Leases cap at 600 seconds; a real integration or proof search
   can exceed that. Is renewal (heartbeat extending `lease_until` under the same `lease_id`) needed,
   and how does it interact with fencing so a renewed lease cannot resurrect a fenced one?
