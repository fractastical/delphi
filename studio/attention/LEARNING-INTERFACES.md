# Collective-learning interfaces and research queue (pheromone-style attention)

Market worker, single-reader, not Codex-reviewed. **A protocol sketch and a research queue, not an implementation.** There is no learning
algorithm here, no reinforcement-learning claim, no learned weight, and nothing deployed. What exists today is the *data foundation*: actual
trace events read from the store and turned into plain outcome rows (`attention/ledger.py`, `outcome`). Stigmergic coordination and
ant-colony optimisation are old ideas; this note claims no novelty and no advantage.

## 1. Four things that stay separate (binding for any future design)

| layer | what it is | who can change it |
|---|---|---|
| **assessment** | what a reviewer asserted about an exact record version, with issuer and source; local acceptance is this node's own state | review workflow only |
| **priority inputs** | declared annotations: typed unlock edges, decision models, bounded actions | an annotator, pinned to an exact Problem version |
| **trace data** | what the store witnessed: events, action paths, outcomes | nobody; append-only |
| **learned marks** (future) | a deterministic function of trace data and a declared decay policy, shown as an *extra labelled column* | the function only; never written back |

A mark can attract attention. It is not evidence, never writes to an assessment, never alters a declared priority input, and a ranking that uses
it is a separate named policy compared with the deterministic baselines on real traces (section 5). A high mark does not imply a design,
mechanism or claim is viable or true; every output keeps `does_not_imply`.

## 2. Data foundation that exists now

* Source: the store's events (`record_proposed`, `action_ready|leased|running|submitted|reviewed|accepted|disputed|failed|blocked|expired|cancelled`, ...) with
  actor, operator, `witnessed_at`, exact target ref. Read-only through `attention/pg.py` or an exported event list.
* Per Action, `ledger.outcome`: `path` (ordered event types), `final_state`, `terminal`, counts of leases, expiries, failures, blocks, cancellations, disputes,
  first/last witnessed time, elapsed seconds. **Plain data; no weight, score or decay is computed.**
* Not recorded by the store today, and needed before anything is learnable: why a path failed (a `reason`), resources actually consumed (SPEC-003: the store meters
  nothing), result quality, and the exact inputs consumed (root is adding `Action.inputs`; `Evidence.produced_by` would link results to the action that made them).
* Volume today: the live store holds 0 Actions and 0 action events, so **no action outcome exists to learn from.** The only real failed-path-then-repair data I know of is
  the Lean-commons attempts in delphi-evolve (`ebe0242`, `artifacts/commons/runs/*/attempts.jsonl`: per target up to 3 attempts with compiler feedback). It is
  model-specific, not Frontier traffic, and I have not analysed it for this purpose.

## 3. Interfaces (proposed; none is built unless stated)

* **I1 TraceSource** `events(after_sequence, limit)`: exists (`Store.events`; `pg.read_store` is a read-only equivalent).
* **I2 OutcomeTable** `outcomes(records, events)`: exists as `ledger.action_ledger(...)[i]["outcome"]`.
* **I3 PathMark (a derived view, not a new record kind):** a mark is keyed by a *path key* = the Action cache key (target, input, code, model, environment, parameters, scope,
  acceptance policy) so "the same path" has the store's own definition. It lists *deposits*, each pointing at an exact event: `{event_ref, operator, kind: progress | failure | negative_result | success,
  scope_note, witnessed_at}`. Nothing is stored; a mark is recomputed from events.
* **I4 DecayPolicy (declared, versioned, hashed):** a document naming the kernel per deposit kind, e.g. exponential with a stated half-life, evaluated *at read time*
  as a pure function of (events, policy, `now`). Two readers with the same snapshot, policy and `now` get the same numbers. Decay never edits an event. Time-decay is not
  the only invalidation: a failure recorded under an old Problem version or cache key is *marked stale* when the version or key dimension changes, not merely faded.
* **I5 NegativeResult as first-class data:** a failed or disputed Action with its reason is a deposit of kind `failure`/`negative_result`. It suppresses an identical retry only
  while the path key is unchanged; any change in a key dimension re-opens the path. A negative result is progress for the map, and is credited as such (`credit.contribution_credit`).
* **I6 Independence:** deposits count per distinct *operator* (not account, agent or model name), repeated deposits from one run collapse, and the executor of a path cannot be its reviewer.
* **I7 Explain(path_key):** returns every contributing event, its exact ref and its contribution to the mark. No opaque aggregate is ever shown.
* **I8 EvaluationHook:** a mark-using policy may be offered only after `experiment.trace_gate` passes on real traces and `experiment.evaluate` compares it at a matched budget with
  curator order, `derived_dependents`, `declared_evpi` (where declared) and a persistent sequential agent, on a preregistered outcome. Fewer than 6 problems: descriptive only.

## 4. Failure modes the protocol must design against (not solved here)
Rich-get-richer lock-in (a mandatory exploration share, and decay); popularity as truth (marks are labelled attention, never a rating); Sybil deposits (operator-distinct counting needs an
identity layer that does not exist); reward hacking on easy completions (value must come from preregistered decision-relevant resolution, not completion counts); stale marks after a
scope change (invalidate by version, not only by time).

## 5. Research queue (ordered; each has a stop rule)

| # | question | data needed | minimal bounded step | stop rule / what would count | blocked by |
|---|---|---|---|---|---|
| R1 | Do action outcomes carry any signal about later outcomes of related paths? | >= 30 Actions with terminal outcomes across >= 6 Problems | descriptive tables of `outcome` by Problem and capability; no model | stop at tables; a "signal" needs a preregistered comparison with a base-rate predictor | **no Actions exist** |
| R2 | What half-life, if any, fits? | inter-event durations over many paths | a fixed grid of half-lives, sensitivity only | do not choose from sparse data; declare and report the whole grid | R1 |
| R3 | Does suppressing identical-key retries cut duplicate effort without hiding fixable failures? | traces with repeated identical-key attempts and a later success or a changed key | replay on real traces, never simulation | only a preregistered replay can support a claim; otherwise a null is reported | traces with retries |
| R4 | Does a mandatory exploration share prevent lock-in? | a policy run on real allocation traces | compare two shares at a matched budget via `evaluate` | needs `trace_gate` to pass; today it is blocked (see `results/trace_gate_commons_ebe0242.json`) | allocation traces |
| R5 | Can path keys be made stable enough that "the same path" is well defined? | cache keys of real Actions | audit of key-dimension change frequency | report how often a retried path changes a dimension | Actions |
| R6 | Operator-distinct counting vs account counting | an identity layer | none today | out of scope until an identity model exists; no federation or identity claim | identity |
| R7 | Are forecasts of action outcomes calibrated? | specs and resolutions written before forecasts | `forecast.score_events` on real specs | `calibrated_claim_allowed` stays false until a preregistered, adequately large set resolves | specs, resolutions |

## 6. Coupled changes proposed to other owners (none applied)
Event `details.reason` on `action_failed` / `action_blocked` / `action_cancelled`; an `Action.inputs` and `Evidence.produced_by` read path so realized reuse is derivable from accepted
Actions; receipts for consumed resources (the store records none). These are for root and the store owner to decide; this layer reads whatever exists and reports the rest as "not recorded".
