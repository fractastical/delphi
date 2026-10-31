# attention — read-only attention layer over exported Frontier records

Owner: market worker. **Single-reader, not Codex-reviewed.** Branch `work/market-attention`. Touches nothing in `frontier/`, `specs/`, `site/`.
It reads exported records and events, writes nothing to the store, adds no record kind, and makes no persistence, endpoint, identity or federation claim.

**Premise.** Priority, forecast and rank say nothing about whether a design, mechanism, intervention or claim is viable or true (every output carries
`does_not_imply`). Truth is the Assessment column and is never read by a ranking; probability appears only (a) as a declared prior inside EVPI, labelled
as a belief about a *decision* state, and (b) in forecasts of *process events*. They are never blended into one score.

## Changes after review (2026-10-31)
* **Keys keep the namespace.** Rows, rankings, facets, dependents and actions are identified by `namespace/kind/id` (`row["key"]`), never by bare id; a bare id collides across nodes. Dependencies, claim ids, annotations, interests and assessments are matched on namespace, kind, id and (where pinned) exact version. Collision tests use two nodes with the same ids.
* **`truth` is gone.** The column is `assessment`: each assertion carries issuer, source, record namespace and whether it was imported from another node; `local_acceptance` is this node's own state for the exact target version and exists only when local states are supplied. Nothing here is called truth.
* **Store adapter** (`attention/pg.py`): read-only PostgreSQL reader (server-side `default_transaction_read_only=on`, five tables, no credential-bearing table, private records excluded). Digest failures (corruption) and schema skew (a store newer than this checkout) are reported separately; unknown vocabulary values are carried verbatim with `recognized: false`.
* **Snapshot** (`attention/snapshot.py`, `python -m attention snapshot --dsn ... --namespace ... [--demo] --out ...`): actual attention snapshot with `missing_priorities` per Problem and an explicit `unplaced` reason in each ranking; source-field links (`attention/links.py`); authored demo annotations are separate (`attention/demo.py`, never in the actual snapshot).
* **Learning interfaces and research queue:** `attention/LEARNING-INTERFACES.md` (protocol sketch only; no implementation, no RL claim).

## Interface

```
python -m attention view --records BUNDLE.json [--events EVENTS.json] [--annotations A1.json A2.json ...] [--now ISO] [--out OUT.json]
python -m attention score-events --specs S.json --forecasts F.json --resolutions R.json --now ISO
python -m attention evaluate --rows ROWS.json --frozen FROZEN.json --arms a,b
python -m attention trace-gate --commons-runs DIR [--out OUT.json]
```
`BUNDLE.json` = a `frontier-bundle-0.1` or a list of record envelopes; `EVENTS.json` = `Store.events(...)["events"]` rows or Event envelopes.

`view` returns `rows[]` (one per Problem head) with:
* `store` — store fields verbatim, **tagged with the store vocabulary** (`problem_kind`, `completeness`), plus the untyped `next_action_text`, `cost_stop_bounds_text`,
  `downstream_uses_untyped`, typed `dependencies`, and `approach`/`scales`/`context_tags` passed through unvalidated (None until the store carries them);
* `register_labels` — morphoswarm importance/tractability in **their own** vocabulary (never translated; `vocab.translate` refuses without an explicit mapping);
* `truth` — the Assessment decision for the *current* version, a separate column; assessments on older versions are counted, not applied;
* `annotation` — `applied | stale | none`; an annotation is pinned to an exact Problem version and goes stale when the Problem changes;
* `typed_unlocks`, `unlock_reasons` (relation `design_requirement` | `theory_challenge`, required `reason`, whether it `counted_in_value`), `typed_next_action`, `bounded_cost` (estimate only);
* `utility` — `unknown` unless the annotation declares prior, utilities and sources; EVPI with unknown decisions listed (a lower bound), never imputed;
* `dependents` — derived inverse of the store's typed `dependencies` (factual, unannotated);
* `actions[]`, `interest_issuers` (distinct issuers, current version only), `why_priority[]` (each entry names the field that decided it).

Also `whiteboard_facets` (which questions carry a design-requirement reason, a theory-challenge reason, both, or neither stated), `action_ledger[]` (state replayed from events, live
lease, flags for transitions outside SPEC-003, `consumed` = "not recorded by the store", passthrough of `Action.inputs` when present), `annotations_rejected[]`, and `rankings`.

`rankings` are **tiered, never tie-broken**, each with `pairs_ordered_fraction` (0.0 = degenerate): `id_order`, `actionable_first`, `register_label_layers`,
`derived_dependents`, `typed_unlock_groups`, `declared_evpi`. Rows a ranking cannot place go to `unplaced` with the reason; nothing is imputed.

## Annotation (the sidecar that carries what the store cannot)
`attention.annotation.make_annotation(body)` validates and hashes a document pinned to a Problem `Ref`: typed `unlocks` (kind `logical_necessity | empirical_relevance | proposed_connection`,
optional `relation` + `reason`, `independent_group`), `decisions` (each `declared` with prior/utilities/sources, or `unknown` with no numbers), and a `BoundedAction` (pinned input hashes, estimate,
stop rule, acceptance criterion, reviewer). `proposed_connection` and `theory_challenge`-only edges never enter a value; edges in one `independent_group` are not additive.

## Evidence in this repo (commands in the handoff)
* `tests/test_attention_*.py`: 43 hand-worked tests; with the existing suite 61 passed, exit 0 (`scripts/test_postgres.sh` under the capped scope). 44 deliberate-breakage mutants over the new modules, 0 survivors.
* `results/trace_gate_commons_ebe0242.json`: the real Lean-commons traces (228 rows, 12 arm-runs x 19 targets) are **blocked** for an allocation comparison, with three exact reasons.
* `results/trace_inventory.json`: no live attention trace exists.

## Not claimed
No allocation result, no advantage of coordinated allocation, no calibrated forecast, no viability of anything. Test fixtures are invented to exercise code and are labelled so.
