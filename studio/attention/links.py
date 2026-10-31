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


def coupled_links(problem_heads: dict, claim_heads: dict) -> dict:
    """problem_heads / claim_heads: {(namespace, id): head record}. Keys keep the namespace, so equal ids on different nodes stay distinct."""
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
            links.append({"link_kind": "concerns_claim", "from": _ref(rec), "to": _ref(c), "source_field": "payload.original.claim_ids", "role": role})
            by_claim[(rec["namespace"], cid)].append(pid)
        store_dep_ids = []
        for d in p.get("dependencies", []):
            store_dep_ids.append(d["id"])
            links.append({"link_kind": "depends_on", "from": _ref(rec), "to": {k: d[k] for k in ("namespace", "kind", "id", "version")},
                          "source_field": "payload.dependencies", "role": role,
                          "pinned_to_current_head": d["kind"] == "Problem" and (d["namespace"], d["id"]) in problem_heads and problem_heads[(d["namespace"], d["id"])]["version"] == d["version"]})
        if sorted(store_dep_ids) != sorted(orig.get("depends_on", []) or []):
            issues.append({"problem": pid, "issue": f"store dependencies {sorted(store_dep_ids)} differ from original.depends_on {sorted(orig.get('depends_on', []) or [])}"})
        for u in orig.get("unlocks", []) or []:
            links.append({"link_kind": "declared_downstream", "from": _ref(rec), "to": None, "text": u, "source_field": "payload.original.unlocks",
                          "role": role, "typed": False})
    couplings = [{"claim": _ref(claim_heads[c]), "problems": sorted(ps), "via": "shared payload.original.claim_ids"} for c, ps in sorted(by_claim.items()) if len(ps) >= 2]
    return {"links": links, "couplings": couplings, "issues": issues,
            "meaning": "links come from fields the records carry; declared_downstream is untyped prose; roles are null unless the store states them"}
