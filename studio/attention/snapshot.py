"""Actual attention snapshot of a store, with every missing priority input stated. Pure over the dict returned by pg.read_store.

Nothing is rated. A Problem with no annotation has utility 'unknown', is unplaced by the value rankings, and carries a `missing_priorities`
list saying which inputs would be needed. Demo annotations (demo.py) are a separate, labelled input and never part of the actual snapshot.
"""
from __future__ import annotations

from collections import Counter

from frontier.models import ACTIONABILITY, digest
from . import rank, view, vocab
from .links import coupled_links
from .records import heads

KIND = ("actual", "with_demo_annotations")


def _missing(row: dict, payload: dict, signals: dict) -> list[dict]:
    m = []
    add = lambda field, needed_for: m.append({"field": field, "status": "missing", "needed_for": needed_for})
    for f in ACTIONABILITY:
        v = payload.get(f)
        if not v:
            add(f"store.Problem.{f}", "an Action may only target an actionable Problem")
    if row["annotation"]["status"] != "applied":
        add("annotation (pinned to this Problem version)", "typed unlock edges, a bounded next action, declared utilities")
    elif row["typed_next_action"] is None:
        add("annotation.next_action", "a bounded, costed, reviewable next action")
    if row["utility"]["status"] == "unknown":
        add("decision model with declared utilities and sources", "any value-of-information ordering; utility stays UNKNOWN, not zero")
    if not row["typed_unlocks"]:
        add("typed unlock edges (design_requirement / theory_challenge with a reason)", "saying why answering it matters")
    if row["store"]["approach"] is None:
        add("store.Problem.approach (theory_fit | design_goal)", "separating bottom-up theory fitting from top-down requirements")
    if row["register_labels"]["importance"] is None:
        add("register importance / tractability label", "the only label-based ordering the register supports")
    if not signals:
        add("interest signals (following / can_contribute / resource_offer / blocked_by_this)", "who wants it and what is blocked by it")
    if not row["actions"]:
        add("any Action targeting this Problem", "who is working on it")
    if row["assessment"]["latest_assertion"] is None:
        add("Assessment assertion for this Problem version", "separate from priority; not required for ranking")
    return m


def build_snapshot(read: dict, annotations: list[dict], now: str, kind: str = "actual") -> dict:
    assert kind in KIND
    records = read["records"]
    status = read["local_status"]
    v = view.build_view(records, read["events"], annotations, now, local_status=status)
    h = heads(records)
    prob = {(k[0], k[2]): x["head"] for k, x in h.items() if k[1] == "Problem"}
    claim = {(k[0], k[2]): x["head"] for k, x in h.items() if k[1] == "Claim"}
    all_versions = {(r["namespace"], r["kind"], r["id"], r["version"]) for r in records}
    heads_by_key = {k: x["head"]["version"] for k, x in h.items()}
    L = coupled_links(prob, claim, all_versions=all_versions, heads_by_key=heads_by_key,
                      namespaces_read=set(read["meta"].get("scope", {}).get("namespaces_read", [])) or None)
    concerned = {}
    for lk in L["links"]:
        if lk["link_kind"] == "concerns_claim":
            concerned.setdefault(f"{lk['to']['namespace']}/Claim/{lk['to']['id']}", []).append(f"{lk['from']['namespace']}/Problem/{lk['from']['id']}")
    for row in v["rows"]:
        pid = (row["ref"]["namespace"], row["ref"]["id"])
        row["local_status"] = vocab.tag_lenient("frontier-store", "local_status", status[row["ref"]["version"]]) if row["ref"]["version"] in status else None
        row["missing_priorities"] = _missing(row, prob[pid]["payload"], row["interest_issuers"])
        row["links"] = [lk for lk in L["links"] if (lk["from"]["namespace"], lk["from"]["id"]) == pid]
    asm = sorted((r for r in records if r["kind"] == "Assessment"), key=lambda r: (r["created_at"], r["version"]))
    claims = []
    for ckey in sorted(claim):
        c = claim[ckey]
        cref = {k: c[k] for k in ("namespace", "kind", "id", "version")}
        claims.append({"ref": cref, "key": view.key_of(ckey[0], "Claim", ckey[1]), "title": c["payload"]["title"],
                       "local_status": vocab.tag_lenient("frontier-store", "local_status", status[c["version"]]) if c["version"] in status else None,
                       "concerned_by_problems": sorted(concerned.get(view.key_of(ckey[0], "Claim", ckey[1]), [])),
                       "source_review_verbatim": c["payload"].get("prior_review"),
                       "assessment": view.assessment_block(asm, cref, status)})
    ranks = rank.all_baselines(v["rows"])
    miss = Counter(m["field"] for r in v["rows"] for m in r["missing_priorities"])
    return {
        "snapshot_kind": kind,
        "store": read["meta"], "now": now,
        "scope_statement": _scope_statement(read["meta"]),
        "n_actions": sum(1 for r in records if r["kind"] == "Action"), "n_evidence": sum(1 for r in records if r["kind"] == "Evidence"),
        "n_claims_all": sum(1 for r in records if r["kind"] == "Claim"),
        "local_status_counts": dict(Counter(status.values())),
        "n_problems": v["n_problems"], "n_claims": len(claims),
        "problems": v["rows"], "claims": claims, "whiteboard_facets": v["whiteboard_facets"],
        "links": L["links"], "couplings": L["couplings"], "link_issues": L["issues"],
        "action_ledger": v["action_ledger"], "annotations_rejected": v["annotations_rejected"],
        "rankings": ranks,
        "missing_priorities_summary": {"problems": v["n_problems"], "by_field": dict(sorted(miss.items(), key=lambda kv: (-kv[1], kv[0])))},
        "does_not_imply": v["does_not_imply"],
        "note": ("Nothing is rated. 'unplaced' in a ranking means the inputs are missing, not that the item is low priority. "
                 "Record states are reported as stored; an assessment is shown as an assertion with its issuer, never as truth."),
    }


def _scope_statement(meta: dict) -> str:
    sc = meta.get("scope", {})
    ex = sc.get("excluded_by_scope", [])
    base = f"Counts below are scoped to namespaces {sc.get('namespaces_read')} ({sc.get('mode')}), public records only."
    if ex:
        base += " NOT READ: " + "; ".join(f"{e['namespace']}/{e['kind']} x{e['record_versions']}" for e in ex) + "."
    return base + " Nothing here is a statement about the whole database unless mode is all_namespaces."
