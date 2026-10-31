"""Bounded knowledge/asset graph projection and a reproducible reuse measurement, over PUBLIC stored records only.

`view(store, target_ref=None, depth=1, limit=120)` returns {nodes, edges, truncated, scope, counts}. Read-only SQL, public records only.

Rules this module keeps (each has a test):
  * Exact versions, full namespaces. A node id is `namespace/kind/id@version`; the same id in two namespaces, or two versions of one id, are different nodes.
  * Public only, everywhere: every query filters `visibility='public'`. A reference from a public record to something that is not public-and-present becomes an
    `unresolved` placeholder that carries only the ref the public record itself contains; private and absent are indistinguishable. Counts, labels, edges and
    traversal never include a private record, and the incoming-edge query joins the SOURCE record's visibility.
  * Explicit relationships come from the store's own `references()` plus Ref-shaped values in payload fields of kinds this file has never heard of, so a new record
    kind does not need a code change. Declared relations (Evidence supports/refutes/qualifies/reproduces/context_only; Assessment decisions) are the submitter's
    assertion and are marked `asserted`; they are not reviews. A `tentative` edge is an id match from untyped source fields, never an exact reference.
    Similarity edges are not produced at all.
  * Artifact pointers are metadata. Nothing here fetches a URI or reads bytes. One artifact node per sha256; each owning Evidence gets its own ownership edge
    (identical bytes in two contexts are two uses, not two confirmations).
  * Events are a log, not graph nodes (`scope.excluded_kinds`).
  * A dependency edge is not time saved, an imported Action is not executed work: `reuse_report` keeps those apart and measures nothing about benefit.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .models import canonical, digest, references
from .store import FrontierError, Missing

SCHEMA = "frontier-graph-0.1"
DEFAULT_LIMIT, MAX_LIMIT, MAX_DEPTH = 120, 300, 3
EXCLUDED_KINDS = ("Event",)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
RELATION_KINDS = ("supports", "refutes", "qualifies", "reproduces", "context_only")
KNOWN_PREFIXES = ("target", "dependencies", "inputs", "proposal.plan_steps", "produced_by", "dimensions")
LABELS = {"targets": "targets", "supports": "supports (declared)", "refutes": "refutes (declared)", "qualifies": "qualifies (declared)",
          "reproduces": "reproduces (declared)", "context_only": "context only (declared)", "produced_by": "produced by", "uses": "uses as input",
          "depends_on": "depends on", "plans_step": "plan step", "review_evidence": "review cites evidence", "predecessor": "previous version",
          "has_artifact": "has artifact", "assessed": "assessed (assertion)", "refers_to": "refers to", "names_claim_id": "names claim id (tentative)"}


def node_id(ref: dict) -> str:
    return f"{ref['namespace']}/{ref['kind']}/{ref['id']}@{ref['version']}"


def _ref(rec: dict) -> dict:
    return {k: rec[k] for k in ("namespace", "kind", "id", "version")}


def _is_ref(v) -> bool:
    return isinstance(v, dict) and set(v) == {"namespace", "kind", "id", "version"} and all(isinstance(x, str) for x in v.values()) and bool(HEX64.match(v["version"]))


def title_of(rec: dict) -> str:
    p = rec["payload"]
    for k in ("title", "name", "question", "statement", "method"):
        if isinstance(p.get(k), str) and p[k].strip():
            return p[k].strip()[:160]
    return rec["id"]


def _generic_refs(obj, path="", depth=0):
    if depth > 4:
        return
    if _is_ref(obj):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _generic_refs(v, f"{path}.{k}" if path else str(k), depth + 1)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:60]):
            yield from _generic_refs(v, f"{path}[{i}]", depth + 1)


def explicit_edges(rec: dict) -> list[dict]:
    """[{kind, field, to(ref), asserted, tentative?}] for ONE record: the store's typed references, the predecessor, declared relations, and generic Ref-shaped fields."""
    out = []
    p = rec["payload"]
    for relation, ref in references(rec):
        kind = relation
        asserted = False
        if relation == "targets" and rec["kind"] == "Evidence" and p.get("relation") in RELATION_KINDS:
            kind, asserted = p["relation"], True
        elif relation == "targets" and rec["kind"] == "Assessment":
            kind, asserted = "assessed", True
        field = {"targets": "payload.target", "uses": "payload.inputs", "depends_on": "payload.dependencies", "plans_step": "payload.proposal.plan_steps",
                 "review_evidence": "payload.dimensions.*.evidence_links"}.get(relation, "payload." + relation)
        out.append({"kind": kind, "field": field, "to": ref, "asserted": asserted})
    if rec.get("predecessor"):
        out.append({"kind": "predecessor", "field": "predecessor", "to": None, "to_version": rec["predecessor"], "asserted": False})
    for path, ref in _generic_refs(p):
        if path.split("[")[0].split(".")[0] in KNOWN_PREFIXES or path.startswith("proposal.plan_steps"):
            continue
        out.append({"kind": "refers_to", "field": "payload." + path, "to": ref, "asserted": False})
    return out


def artifacts_of(rec: dict) -> list[dict]:
    arts = rec["payload"].get("artifacts")
    return [a for a in arts if isinstance(a, dict) and HEX64.match(str(a.get("sha256", "")))] if isinstance(arts, list) else []


def _node(rec: dict, status, is_head, dist) -> dict:
    p = rec["payload"]
    attrs = {k: p[k] for k in ("evidence_kind", "relation", "problem_kind", "completeness", "approach", "origin", "decision") if isinstance(p.get(k), str)}
    scales = p.get("scales")
    return {"id": node_id(_ref(rec)), "type": rec["kind"], "kind": rec["kind"], "ref": _ref(rec), "artifact_sha256": None, "title": title_of(rec),
            "local_status": status, "scale": scales if isinstance(scales, list) and scales else None, "is_head": is_head, "distance": dist,
            "issuer": rec["issuer"], "attrs": attrs}


def _edge(frm: str, to: str, kind: str, field: str, declared_by: str | None, asserted: bool, basis: str = "explicit_reference", **extra) -> dict:
    e = {"id": "e:" + digest([frm, kind, to, field])[:16], "from": frm, "to": to, "kind": kind, "label": LABELS.get(kind, kind),
         "origin": {"basis": basis, "field": field, "declared_by": declared_by}, "asserted": asserted, "tentative": basis == "source_field_untyped"}
    e.update(extra)
    return e


# ----------------------------------------------------------------------------------------------------------------------------
# pure projection of an already-selected PUBLIC record set
# ----------------------------------------------------------------------------------------------------------------------------
def project(records: dict, status: dict, heads: set, dist: dict, *, public_present: set, budget: int, tentative_heads: dict | None = None) -> dict:
    """records: {version: record} (all PUBLIC, non-Event). public_present: versions known to be public-and-present (selected or not).
    Builds nodes, edges and artifact nodes; references to versions outside `public_present` become unresolved placeholders (budget permitting)."""
    nodes = {}
    for v in sorted(records, key=lambda v: (dist.get(v, 0), records[v]["kind"], records[v]["namespace"], records[v]["id"], v)):
        nodes[node_id(_ref(records[v]))] = _node(records[v], status.get(v), v in heads, dist.get(v, 0))
    edges, omitted, unresolved_refs, artifact_nodes, omitted_nodes = {}, 0, 0, {}, 0
    by_version = {n["ref"]["version"]: nid for nid, n in nodes.items()}

    def room():
        return len(nodes) + len(artifact_nodes) < budget

    for v, rec in sorted(records.items(), key=lambda kv: (kv[1]["kind"], kv[1]["namespace"], kv[1]["id"], kv[0])):
        frm = node_id(_ref(rec))
        for ee in explicit_edges(rec):
            tv = ee["to"]["version"] if ee["to"] else ee["to_version"]
            if tv in by_version:
                e = _edge(frm, by_version[tv], ee["kind"], ee["field"], rec["issuer"], ee["asserted"])
                edges[e["id"]] = e
            elif tv in public_present:
                omitted += 1                                   # exists publicly, outside this view
            else:
                unresolved_refs += 1
                ref = ee["to"] or {"namespace": rec["namespace"], "kind": rec["kind"], "id": rec["id"], "version": tv}
                uid = "unresolved:" + node_id(ref)
                if uid not in nodes and room():
                    nodes[uid] = {"id": uid, "type": "unresolved", "kind": "unresolved", "ref": ref, "artifact_sha256": None, "title": "not available in this public view",
                                  "local_status": None, "scale": None, "is_head": None, "distance": None, "issuer": None, "attrs": {}}
                if uid in nodes:
                    e = _edge(frm, uid, ee["kind"], ee["field"], rec["issuer"], ee["asserted"], basis="unresolved_reference")
                    edges[e["id"]] = e
                else:
                    omitted_nodes += 1
        for cid in ((rec["payload"].get("original") or {}).get("claim_ids") or []) if isinstance(rec["payload"].get("original"), dict) else []:
            hv = (tentative_heads or {}).get((rec["namespace"], cid))
            if hv and hv in by_version:
                e = _edge(frm, by_version[hv], "names_claim_id", "payload.original.claim_ids", rec["issuer"], False, basis="source_field_untyped",
                          note="matched by id to the current head; not an exact-version reference")
                edges[e["id"]] = e
        for a in artifacts_of(rec):
            aid = "artifact:sha256:" + a["sha256"]
            if aid not in artifact_nodes:
                if not room():
                    omitted_nodes += 1
                    continue
                artifact_nodes[aid] = {"id": aid, "type": "Artifact", "kind": "Artifact", "ref": None, "artifact_sha256": a["sha256"], "title": str(a.get("title", ""))[:160],
                                       "local_status": None, "scale": None, "is_head": None, "distance": None, "issuer": None,
                                       "attrs": {"media_type": a.get("media_type"), "byte_size": a.get("byte_size"), "bytes_verified": False, "fetched": False}}
            e = _edge(frm, aid, "has_artifact", "payload.artifacts", rec["issuer"], False, basis="derived_ownership",
                      role=a.get("role"), availability=a.get("availability"), uri=a.get("uri"), license=a.get("license"), use_title=str(a.get("title", ""))[:160])
            edges[e["id"]] = e
    allnodes = {**nodes, **artifact_nodes}
    return {"nodes": list(allnodes.values()), "edges": sorted(edges.values(), key=lambda e: e["id"]),
            "edges_omitted_outside_view": omitted, "unresolved_references": unresolved_refs, "nodes_omitted_for_budget": omitted_nodes}


# ----------------------------------------------------------------------------------------------------------------------------
# bounded read-only loading
# ----------------------------------------------------------------------------------------------------------------------------
PUB = "v.visibility = 'public' AND v.kind <> 'Event'"


def _fetch(c, versions) -> dict:
    if not versions:
        return {}
    rows = c.execute(f"""SELECT v.version, v.envelope, s.status, (h.version IS NOT NULL) AS is_head FROM record_versions v
                         LEFT JOIN local_states s ON s.version = v.version LEFT JOIN heads h ON h.version = v.version
                         WHERE v.version = ANY(%s) AND {PUB}""", (sorted(versions),)).fetchall()
    return {r["version"]: r for r in rows}


def _tentative(c, recs) -> dict:
    """{(namespace, claim_id): head version} for ids named in untyped `original.claim_ids`; PUBLIC heads only. Tentative: an id match, not an exact reference."""
    keys = {(r["namespace"], cid) for r in recs for cid in ((r["payload"].get("original") or {}).get("claim_ids") or [])
            if isinstance(r["payload"].get("original"), dict) and isinstance(cid, str)}
    out = {}
    for ns in {k[0] for k in keys}:
        rows = c.execute(f"""SELECT h.record_id, h.version FROM heads h JOIN record_versions v ON v.version = h.version
                             WHERE h.namespace = %s AND h.kind = 'Claim' AND h.record_id = ANY(%s) AND {PUB}""", (ns, sorted(k[1] for k in keys if k[0] == ns))).fetchall()
        out.update({(ns, r["record_id"]): r["version"] for r in rows})
    return out


def _validate(target_ref, depth, limit):
    if type(depth) is not int or not 0 <= depth <= MAX_DEPTH:
        raise FrontierError(f"depth must be an integer 0..{MAX_DEPTH}")
    if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
        raise FrontierError(f"limit must be an integer 1..{MAX_LIMIT}")
    if target_ref is not None and not _is_ref(target_ref):
        raise FrontierError("target_ref needs exactly namespace, kind, id and a 64-hex version: graph neighborhoods are exact-version")
    if target_ref is not None and target_ref["kind"] in EXCLUDED_KINDS:
        raise FrontierError("events are a log, not graph nodes")


def view(store, target_ref: dict | None = None, depth: int = 1, limit: int = DEFAULT_LIMIT) -> dict:
    """Bounded graph around an exact version, or a bounded overview. Public records only; read-only."""
    _validate(target_ref, depth, limit)
    with store.connection() as c:
        c.execute("SET TRANSACTION READ ONLY")
        total_public = c.execute(f"SELECT count(*) AS n FROM record_versions v WHERE {PUB}").fetchone()["n"]
        selected, dist, truncated, boundary_open = {}, {}, False, False
        if target_ref is None:
            rows = c.execute(f"""SELECT v.version FROM record_versions v JOIN heads h ON h.version = v.version
                    LEFT JOIN LATERAL (SELECT count(*) AS n FROM typed_edges e WHERE (e.source_version = v.version AND e.relation <> 'targets') OR e.target_version = v.version) k ON true
                    WHERE {PUB} ORDER BY k.n DESC, v.kind, v.namespace, v.record_id LIMIT %s""", (limit + 1,)).fetchall()
            versions = [r["version"] for r in rows]
            truncated = len(versions) > limit
            fetched = _fetch(c, versions[:limit])
            selected = {v: fetched[v] for v in versions[:limit] if v in fetched}
            dist = {v: 0 for v in selected}
        else:
            got = _fetch(c, {target_ref["version"]})
            row = got.get(target_ref["version"])
            if row is None or _ref(row["envelope"]) != target_ref:
                raise Missing("No such public record version")           # private and absent look the same
            selected[row["version"]] = row
            dist[row["version"]] = 0
            frontier = [row["version"]]
            for d in range(1, depth + 1):
                cand: dict[str, int] = {}
                out_versions = set()
                for v in frontier:
                    rec = selected[v]["envelope"]
                    for ee in explicit_edges(rec):
                        out_versions.add(ee["to"]["version"] if ee["to"] else ee["to_version"])
                inc = c.execute(f"""SELECT DISTINCT e.source_version AS version FROM typed_edges e JOIN record_versions v ON v.version = e.source_version
                                    WHERE e.target_version = ANY(%s) AND {PUB} ORDER BY e.source_version LIMIT %s""", (frontier, MAX_LIMIT + 1)).fetchall()
                succ = c.execute(f"SELECT v.version FROM record_versions v WHERE {PUB} AND v.predecessor = ANY(%s) ORDER BY v.version LIMIT %s", (frontier, MAX_LIMIT + 1)).fetchall()
                for r in inc + succ:
                    cand[r["version"]] = d
                for v in out_versions | set(_tentative(c, [selected[v]["envelope"] for v in frontier]).values()):
                    cand.setdefault(v, d)
                for v in list(cand):
                    if v in selected:
                        del cand[v]
                found = _fetch(c, set(cand))
                order = sorted(found.values(), key=lambda r: (r["envelope"]["kind"], r["envelope"]["namespace"], r["envelope"]["id"], r["version"]))
                nxt = []
                for r in order:
                    if len(selected) >= limit:
                        truncated = True
                        break
                    selected[r["version"]] = r
                    dist[r["version"]] = d
                    nxt.append(r["version"])
                frontier = nxt
                if not frontier:
                    break
            boundary_open = bool(frontier) and depth >= 1 and len(frontier) > 0
        records = {v: r["envelope"] for v, r in selected.items()}
        status = {v: r["status"] for v, r in selected.items()}
        heads = {v for v, r in selected.items() if r["is_head"]}
        wanted = {ee["to"]["version"] if ee["to"] else ee["to_version"] for rec in records.values() for ee in explicit_edges(rec)}
        present = set(records) | set(_fetch(c, wanted - set(records)))
        tentative = _tentative(c, list(records.values()))
        extra = _fetch(c, set(tentative.values()) - set(records))
        if target_ref is None:
            tentative = {k: v for k, v in tentative.items() if v in records}
    proj = project(records, status, heads, dist, public_present=present | set(extra), budget=limit, tentative_heads=tentative)
    counts = {"nodes": len(proj["nodes"]), "edges": len(proj["edges"]),
              "by_node_type": dict(sorted(Counter(n["type"] for n in proj["nodes"]).items())),
              "by_edge_kind": dict(sorted(Counter(e["kind"] for e in proj["edges"]).items())),
              "unresolved_references": proj["unresolved_references"], "edges_omitted_outside_view": proj["edges_omitted_outside_view"],
              "nodes_omitted_for_budget": proj["nodes_omitted_for_budget"], "public_records_available": total_public,
              "tentative_edges": sum(1 for e in proj["edges"] if e["tentative"]), "asserted_edges": sum(1 for e in proj["edges"] if e["asserted"])}
    truncated = truncated or proj["nodes_omitted_for_budget"] > 0 or (target_ref is None and total_public > len(records))
    return {"schema": SCHEMA, "nodes": proj["nodes"], "edges": proj["edges"], "truncated": bool(truncated), "counts": counts,
            "scope": {"mode": "overview" if target_ref is None else "neighborhood", "target_ref": target_ref, "depth": depth if target_ref else 0, "limit": limit,
                      "visibility": "public records only; private records never appear in nodes, edges, counts or traversal",
                      "excluded_kinds": list(EXCLUDED_KINDS), "namespaces": "all namespaces; node ids keep the namespace",
                      "depth_boundary_open": bool(boundary_open and not truncated),
                      "overview_order": "heads ranked by number of non-'targets' typed edges they take part in (structure first), then kind/namespace/id" if target_ref is None else None,
                      "edge_origin": "explicit_reference: a Ref in the record; declared_relation/asserted: the submitter's assertion, not a review; source_field_untyped/tentative: id match, not an exact reference; derived_ownership: artifact pointer in the record",
                      "similarity_edges": "none produced", "artifact_uri_fetch": "never; pointers are metadata and bytes_verified is always false",
                      "incoming_edges": "store-indexed typed references and predecessor links only"}}


# ----------------------------------------------------------------------------------------------------------------------------
# reuse measurement
# ----------------------------------------------------------------------------------------------------------------------------
EXECUTED_EVENTS = ("action_running", "action_submitted", "action_reviewed", "action_accepted", "action_disputed", "action_failed")
STATE_ORDER = ("action_ready", "action_leased", "action_running", "action_submitted", "action_reviewed", "action_accepted", "action_disputed", "action_failed",
               "action_blocked", "action_expired", "action_cancelled")


def measure_reuse(records: list[dict], events: list[dict], submitters: dict, status: dict) -> dict:
    """Pure measurement over PUBLIC non-Event records.
    events: Event envelopes (or {'envelope':...}); submitters: {version: {'actor','operator'}} (local_states); status: {version: local_status}.

    Definitions (also printed in the result):
      pinned input      = an exact Claim/Evidence version in some Action's `inputs`.
      reused (declared) = referenced by >= 2 DISTINCT Action records (namespace+id; versions of one record count once).
      locally executed  = the store witnessed a lifecycle event of running/submitted/reviewed/accepted/disputed/failed for that Action version.
      imported          = the Action version was imported (record_imported event or local state imported_unreviewed): the producer's declaration, not work done here.
    A dependency or input edge is not time saved; nothing here measures time, cost, benefit or any scaling advantage."""
    envs = [e["envelope"] if "envelope" in e else e for e in events]
    by_target = defaultdict(list)
    for e in envs:
        if e["kind"] == "Event":
            by_target[e["payload"]["target"]["version"]].append(e["payload"])
    actions = [r for r in records if r["kind"] == "Action"]
    rec_by_version = {r["version"]: r for r in records}

    def facts(rec):
        evs = by_target.get(rec["version"], [])
        types = {p["event_type"] for p in evs}
        imported = "record_imported" in types or status.get(rec["version"]) == "imported_unreviewed"
        executed = bool(types & set(EXECUTED_EVENTS))      # store-witnessed lifecycle only; an import event never counts
        sub = submitters.get(rec["version"], {})
        life = max((t for t in types if t in STATE_ORDER), key=STATE_ORDER.index, default=None)
        executors = sorted({p["operator"] for p in evs if p["event_type"] in EXECUTED_EVENTS and p.get("operator")})
        return {"imported": imported, "locally_executed": executed, "operator": sub.get("operator"), "agent": rec["issuer"], "lifecycle_witnessed": life, "executors": executors}

    afacts = {a["version"]: facts(a) for a in actions}
    trace = []
    for a in sorted(actions, key=lambda r: (r["namespace"], r["id"], r["version"])):
        f = afacts[a["version"]]
        for ref in a["payload"].get("inputs", []):
            inp = rec_by_version.get(ref["version"])
            isub = submitters.get(ref["version"], {})
            trace.append({
                "action": _ref(a), "action_agent": a["issuer"], "action_operator": f["operator"],
                "action_origin": "locally_executed" if f["locally_executed"] else ("imported_declaration" if f["imported"] else "proposed_only"), "executed_by_operators": f["executors"],
                "input": {k: ref[k] for k in ("namespace", "kind", "id", "version")}, "input_public_and_present": inp is not None,
                "input_agent": inp["issuer"] if inp else None, "input_operator": isub.get("operator"),
                "same_operator": (f["operator"] == isub.get("operator")) if f["operator"] and isub.get("operator") else None,
                "same_namespace": a["namespace"] == ref["namespace"], "lifecycle_witnessed": f["lifecycle_witnessed"]})

    def ratio(rows, label):
        users = defaultdict(set)
        for t in rows:
            users[t["input"]["version"]].add((t["action"]["namespace"], t["action"]["id"]))      # distinct Action RECORDS: a new version of one Action is not a second user
        den = len(users)
        reused = sorted(v for v, s in users.items() if len(s) >= 2)
        return {"label": label, "numerator": len(reused), "denominator": den, "reused_input_versions": reused,
                "meaning": "numerator = unique pinned inputs (exact versions) referenced by >= 2 distinct Action records (namespace+id); denominator = unique pinned inputs referenced by >= 1 Action in this subset"}

    executed_rows = [t for t in trace if t["action_origin"] == "locally_executed"]
    imported_rows = [t for t in trace if t["action_origin"] == "imported_declaration"]
    with_ops = [t for t in trace if t["same_operator"] is not None]
    evs_with_prod = [r for r in records if r["kind"] == "Evidence" and r["payload"].get("produced_by")]
    ev_exec = [e for e in evs_with_prod if afacts.get(e["payload"]["produced_by"]["version"], {}).get("locally_executed")]
    ev_imp = [e for e in evs_with_prod if afacts.get(e["payload"]["produced_by"]["version"], {}).get("imported")]
    sha_users = defaultdict(set)
    for r in records:
        if r["kind"] == "Evidence":
            for a in artifacts_of(r):
                sha_users[a["sha256"]].add((r["namespace"], r["id"]))                            # distinct Evidence RECORDS, not versions of one record
    reused_sha = sorted(s for s, u in sha_users.items() if len(u) >= 2)
    ops = lambda rows, k: sorted({t[k] for t in rows if t[k]})
    return {
        "metrics": {
            "declared_input_reuse_all_actions": ratio(trace, "all Actions, any origin (a declaration, not executed work)"),
            "declared_input_reuse_imported_actions": ratio(imported_rows, "imported Actions only (producer's declaration; NOT executed here)"),
            "executed_input_reuse_locally_executed_actions": ratio(executed_rows, "Actions with store-witnessed execution events"),
            "cross_operator_reuse_edges": {"numerator": sum(1 for t in with_ops if t["same_operator"] is False), "denominator": len(with_ops),
                                           "meaning": "Action->input edges where both operators are known and differ, over edges where both are known"},
            "evidence_from_locally_executed_actions": {"numerator": len(ev_exec), "denominator": len(evs_with_prod),
                                                       "meaning": "Evidence whose produced_by Action has store-witnessed execution events, over Evidence with produced_by"},
            "evidence_from_imported_actions": {"numerator": len(ev_imp), "denominator": len(evs_with_prod), "meaning": "Evidence whose produced_by Action is an imported declaration"},
            "identical_artifact_bytes_in_multiple_evidence": {"numerator": len(reused_sha), "denominator": len(sha_users), "reused_sha256": reused_sha,
                                                              "meaning": "artifact digests declared by >= 2 distinct Evidence records (namespace+id), over distinct digests; identical bytes in two contexts are two uses, not two confirmations"},
        },
        "populations": {"public_records": len(records), "actions": len(actions), "actions_imported": sum(1 for f in afacts.values() if f["imported"]),
                        "actions_locally_executed": sum(1 for f in afacts.values() if f["locally_executed"]), "input_edges": len(trace),
                        "potential_inputs_claim_or_evidence_versions": sum(1 for r in records if r["kind"] in ("Claim", "Evidence")),
                        "operators_on_actions": ops([{"o": f["operator"]} for f in afacts.values()], "o"), "agents_on_actions": sorted({f["agent"] for f in afacts.values()}),
                        "operators_on_input_edges": ops(trace, "action_operator"), "agents_on_input_edges": ops(trace, "action_agent"),
                        "operators_who_executed": sorted({o for f in afacts.values() for o in f["executors"]})},
        "operators_vs_agents": "operators are the local submitters recorded in local_states; agents are record issuers. Counted separately; many agents can be one operator.",
        "per_edge_trace": trace,
        "not_measured": ["time saved", "cost saved", "quality or benefit of any reuse", "any swarm or scaling advantage (no controlled comparison exists)",
                         "whether an input was actually read by the Action (a pinned input is a declaration)"],
    }


def reuse_report(store, *, max_records: int = 5000, max_events: int = 20000) -> dict:
    """Read PUBLIC non-Event records, their submitters and lifecycle events, read-only, and measure reuse. Refuses (never partial) above the caps."""
    with store.connection() as c:
        c.execute("SET TRANSACTION READ ONLY")
        recs = c.execute(f"SELECT v.version, v.envelope, s.status, s.submitter_actor, s.submitter_operator FROM record_versions v LEFT JOIN local_states s ON s.version = v.version "
                         f"WHERE {PUB} ORDER BY v.created_at, v.version LIMIT %s", (max_records + 1,)).fetchall()
        evs = c.execute("SELECT e.event_version, e.target_version, e.event_type, e.actor, e.operator FROM events e JOIN record_versions t ON t.version = e.target_version "
                        "JOIN record_versions ev ON ev.version = e.event_version WHERE t.visibility = 'public' AND ev.visibility = 'public' ORDER BY e.sequence LIMIT %s",
                        (max_events + 1,)).fetchall()
    if len(recs) > max_records or len(evs) > max_events:
        raise FrontierError("The public record set is larger than this report will read; no partial result is produced")
    records = [r["envelope"] for r in recs]
    events = [{"kind": "Event", "payload": {"event_type": e["event_type"], "target": {"version": e["target_version"]}, "actor": e["actor"], "operator": e["operator"]}} for e in evs]
    out = measure_reuse(records, events, {r["version"]: {"actor": r["submitter_actor"], "operator": r["submitter_operator"]} for r in recs}, {r["version"]: r["status"] for r in recs})
    out["scope"] = {"records_read": len(records), "events_read": len(events), "visibility": "public, non-Event records and events whose target and event record are public",
                    "namespaces": sorted({r["namespace"] for r in records}), "caps": {"records": max_records, "events": max_events}}
    return out


def receipt(store, *, overview_limit: int = DEFAULT_LIMIT, focus_kind: str = "Action", focus_depth: int = 2) -> dict:
    """An actual graph + reuse receipt from a live (read-only) store: overview counts, one real neighborhood, and the reuse measurement with its per-edge trace."""
    ov = view(store, limit=overview_limit)
    with store.connection() as c:
        c.execute("SET TRANSACTION READ ONLY")
        row = c.execute(f"SELECT v.envelope FROM record_versions v WHERE {PUB} AND v.kind = %s ORDER BY v.created_at, v.version LIMIT 1", (focus_kind,)).fetchone()
    focus = view(store, _ref(row["envelope"]), depth=focus_depth, limit=60) if row else None
    return {"schema": "frontier-graph-reuse-receipt-0.1", "overview": {k: ov[k] for k in ("counts", "truncated", "scope")}, "focus_neighborhood": focus,
            "reuse": reuse_report(store),
            "statement": ("A pinned input is a declaration, an imported Action is the producer's declaration and not work done here, and a dependency edge is not time saved. "
                          "Nothing in this receipt measures time, cost, benefit or a swarm/scaling advantage; no controlled comparison exists.")}


def main(argv=None) -> int:
    import argparse
    import json
    from datetime import datetime, timezone
    from .store import Store
    ap = argparse.ArgumentParser(prog="python -m frontier.graph", description="Read-only graph/reuse receipt from a Frontier database.")
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--namespace", required=True, help="the store's own namespace (used only to open the store; reads span all public namespaces)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = receipt(Store(a.dsn, a.namespace))
    out["read_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(a.out, "w") as fh:
        fh.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"out": a.out, "overview_counts": out["overview"]["counts"], "reuse_populations": out["reuse"]["populations"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
