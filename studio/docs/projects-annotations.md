# Projects and anchored discussion

Two record kinds on the existing append-only store: **Project** (a named design effort that pins exact record versions) and
**Annotation** (a comment, question, challenge or proposed edit anchored to a pinned record). The platform is a design studio plus
a shared frontier; *flying fish is one featured Project, not a hardcoded organism*: the schema names no organism, and the same
pinned records can belong to any number of Projects. Author: dx-guilds. Not Codex-reviewed.

## Rules that hold for both kinds
* Written only through `Store.submit`: authenticated token, `contributor` role, issuer == authenticated actor, idempotency key,
  quota, predecessor/head check, `record_proposed` event. **No new write path, nothing anonymous.**
* `proposed` until an independent operator reviews them with the existing `Store.review`. No field lets either kind mark itself
  accepted, resolved, validated or causally bridged (extra fields are rejected). Discussion never changes a record's status.
* Pins are exact versions (`namespace, kind, id, version`). They must exist and be readable by the author but need not be heads: a
  discussion may concern a superseded version, and a Project says exactly which version it means. A **public** Project/Annotation may
  reference only **public** records.
* Old hashes are unchanged: `SCHEMA` is still `frontier-record-0.1`; the new kinds only widen what validates.

## Project payload
`title, mission, source, limitations (>=1), scale_coverage [{scale, status: implemented_model|source_only|unimplemented|unknown, note}]`
(>=1, no repeated scale), `members` (<=60), `requirements` (<=40), `open_questions` (<=40).
* **member**: `ref` (Claim|Problem|Action|Evidence), `role` (mission|subsystem|evidence|measurement|design|context|gap), `subsystem`,
  `scale` (must be one of the declared coverage scales), `relationship` (supports|constrains|depends_on|informs|challenges|implements|
  measures|context_for), `applicability` (a *declaration* of where it applies), `causal_bridge` (`none_declared` | `assumed` |
  `calibrated`, the last requiring a `calibration` Evidence/Claim ref), `rationale`, optional `artifact` = the member's own Evidence
  ref plus a sha256 that the store checks is listed in that Evidence version's `artifacts` (a pointer check, not a byte check).
* **requirement**: `id`, `kind` (function|constraint|validation|safety|non_goal), `text`, optional `quantity {name, unit, comparator,
  value: exact decimal string}`, `source_member` index, `stage` (declared|proposed).
* **open_question**: `text`, optional `problem` (Problem ref), `blocks` (member indexes).
* Typed edges written: `project_member`, `project_member_artifact`, `project_calibration`, `project_open_question`.

## Annotation payload
`kind` (comment|question|challenge|proposed_edit), `body`, `anchor`, optional `reply_to` (an Annotation on the **same record id**),
`proposed_edit {target_path, proposed, rationale}` (exactly when kind is `proposed_edit`; first path segment must be a top-level
field of the anchored record).
* **anchor**: `record` (any kind but Event); optional `artifact` (Evidence ref + digest, only on that Evidence); optional `region`:
  `named_subsystem {name}` | `mesh_part {part_id, artifact_sha256?}` | `image_rect {x,y,w,h}` exact decimal strings in [0,1] with
  `x+w<=1`, `y+h<=1` | `equation_symbol {symbol, equation_id?}` | `parameter_path {path}`; `frame` = `ui_anchor` (default) or
  `declared_biological` (needs a `frame_declaration` and a region). **Regions are UI anchors, not biological coordinates** unless the
  frame says so.
* A proposed edit is data. The anchored record is untouched; a real change is a new version by its owner (predecessor rule).
* Author = the envelope's `issuer`. There is no speaker/agent field, so no record can claim an answer by someone else. Edit your own
  annotation with a new version (`predecessor`); answer with `reply_to`.
* Typed edges: `annotates`, `annotates_artifact`, `replies_to`.

## Store helpers (read-only, visibility-checked)
`annotations_for(target, token, limit, all_versions)` (current heads; ordered by each head's creation time), `projects_for(target,
token, limit, all_versions)`, `project_members(project, token)` (availability, whether the pin is the current head, local review
status), `head_ref(kind, id, token, namespace)` (the current head, never substituted silently).

## Migration
`Store.initialize()` (operator only, idempotent) runs `schema.sql`: replaces the `record_versions` kind CHECK on an old store
(`NOT VALID` then `VALIDATE`; no row is rewritten) and appends `projects-annotations-1` to an append-only `schema_migrations`
ledger. `node_config.schema_version` is untouched. Tests start from the exact pre-change schema (`tests/fixtures/schema_pre_projects.sql`)
and assert every old row, head, edge, review and event is identical afterwards.

## Flying-fish draft
`python3 scripts/build_flying_fish_project.py` rebuilds `projects/flying-fish.draft.json` from the committed catalog/snapshot. Its 13
member refs are copied verbatim from `site/data/catalog.json` (namespace `snapshot`); the script refuses to invent one. All twelve
scales are stated; macromolecular, subcellular, tissue, neural, collective and evolutionary are explicit gaps. Before submitting to a
live node, `repin(draft, store, token)` rewrites each ref to the node's current head by kind+id or raises. No artifact digest is pinned
(the catalog lists none) and no causal bridge is declared.

## Limits
No resolved/accepted lifecycle for annotations exists (deliberate gap). The existing seven-dimension `Assessment` was written for
claims; applying it to a Project is allowed by the code but its dimensions fit loosely. Annotation order is by head creation time;
threading is a display concern. A node that has not merged this code rejects bundles containing the new kinds (version skew).
Postgres only. Nothing is wired into the web/MCP/site layers here.
