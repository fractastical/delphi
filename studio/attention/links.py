"""Coupled links taken from SOURCE FIELDS only. No link is inferred from prose.

For each Problem:
  concerns_claim      <- payload.original.claim_ids  (resolved to the exact head version of that Claim in the same namespace)
  depends_on          <- payload.dependencies         (store-typed Refs); compared with payload.original.depends_on
  declared_downstream <- payload.original.unlocks     (prose, carried verbatim; NOT typed, no target)
`role` (theory_fit | design_goal) comes only from a store `approach` field when it says exactly that; otherwise it is None with the reason.
A coupling is a Claim concerned by two or more Problems (exact shared version), or a Problem pair joined by depends_on.
"""
from __future__ import annotations

from collections import defaultdict

ROLES = ("theory_fit", "design_goal")


def _ref(r):
    return {k: r[k] for k in ("namespace", "kind", "id", "version")}


def resolve_ref(ref: dict, versions: set | None, heads_by_key: dict | None, namespaces_read: set | None) -> dict:
    """Where does an exact reference point, relative to what this snapshot actually read?
    exact_version_present | namespace_head_is_other_version | namespace_not_read | not_found | unknown_scope (when no scope was supplied)."""
    if versions is None:
        return {"status": "unknown_scope"}
    key = (ref["namespace"], ref["kind"], ref["id"], ref["version"])
    if key in versions:
        return {"status": "exact_version_present"}
    if namespaces_read is not None and ref["namespace"] not in namespaces_read:
        return {"status": "namespace_not_read", "namespace": ref["namespace"]}
    h = (heads_by_key or {}).get((ref["namespace"], ref["kind"], ref["id"]))
    if h is not None:
        return {"status": "namespace_head_is_other_version", "head_version": h}
    return {"status": "not_found"}


def coupled_links(problem_heads: dict, claim_heads: dict, *, all_versions: set | None = None, heads_by_key: dict | None = None,
                  namespaces_read: set | None = None) -> dict:
    """problem_heads / claim_heads: {(namespace, id): head record}. Keys keep the namespace, so equal ids on different nodes stay distinct.
    A claim id resolves ONLY inside the Problem's own namespace; the same id in another namespace is listed as `same_id_elsewhere`, never linked.
    Every typed reference carries a `resolution` saying whether its exact target was read (cross-namespace references are never assumed)."""
    links, issues = [], []
    by_claim = defaultdict(list)
    for pkey in sorted(problem_heads):
        rec = problem_heads[pkey]
        pid = f"{pkey[0]}/Problem/{pkey[1]}"
        p = rec["payload"]
        orig = p.get("original") or {}
        approach = p.get("approach")
        role = {"value": approach if approach in ROLES else None,
                "source": ("payload.approach" if approach in ROLES else "no store `approach` field stating theory_fit or design_goal; not inferred")}
        for cid in orig.get("claim_ids", []) or []:
            c = claim_heads.get((rec["namespace"], cid))
            if c is None:
                issues.append({"problem": pid, "issue": f"claim id {cid!r} in original.claim_ids has no Claim in this namespace"})
                continue
            elsewhere = sorted(({"namespace": k[0], "version": v["version"]} for k, v in claim_heads.items() if k[1] == cid and k[0] != rec["namespace"]),
                               key=lambda x: (x["namespace"], x["version"]))
            links.append({"link_kind": "concerns_claim", "from": _ref(rec), "to": _ref(c), "source_field": "payload.original.claim_ids", "role": role,
                          "resolution": resolve_ref(_ref(c), all_versions, heads_by_key, namespaces_read), "same_id_elsewhere": elsewhere})
            by_claim[(rec["namespace"], cid)].append(pid)
        store_dep_ids = []
        for d in p.get("dependencies", []):
            store_dep_ids.append(d["id"])
            links.append({"link_kind": "depends_on", "from": _ref(rec), "to": {k: d[k] for k in ("namespace", "kind", "id", "version")},
                          "source_field": "payload.dependencies", "role": role,
                          "pinned_to_current_head": d["kind"] == "Problem" and (d["namespace"], d["id"]) in problem_heads and problem_heads[(d["namespace"], d["id"])]["version"] == d["version"],
                          "cross_namespace": d["namespace"] != rec["namespace"], "resolution": resolve_ref(d, all_versions, heads_by_key, namespaces_read)})
        if sorted(store_dep_ids) != sorted(orig.get("depends_on", []) or []):
            issues.append({"problem": pid, "issue": f"store dependencies {sorted(store_dep_ids)} differ from original.depends_on {sorted(orig.get('depends_on', []) or [])}"})
        for u in orig.get("unlocks", []) or []:
            links.append({"link_kind": "declared_downstream", "from": _ref(rec), "to": None, "text": u, "source_field": "payload.original.unlocks",
                          "role": role, "typed": False})
    couplings = [{"claim": _ref(claim_heads[c]), "problems": sorted(ps), "via": "shared payload.original.claim_ids"} for c, ps in sorted(by_claim.items()) if len(ps) >= 2]
    return {"links": links, "couplings": couplings, "issues": issues,
            "meaning": "links come from fields the records carry; declared_downstream is untyped prose; roles are null unless the store states them"}
