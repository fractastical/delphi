"""Deterministic attention view over exported records: what is known, what is open, typed unlocks, who is working, next bounded action.

Inputs are plain exported records (envelopes) and events plus optional annotation documents. Store vocabulary stays tagged as the
store's; register labels stay tagged as the register's; this layer's labels stay its own. Truth (the Assessment decision) is its own
column and nothing here derives priority from it.
"""
from __future__ import annotations

from collections import defaultdict

from . import annotation as ann, vocab
from .ledger import action_ledger
from .rank import DOES_NOT_IMPLY
from .records import heads, ref_key
from .voi import unlock_value


def _label(rec: dict, field: str):
    v = ((rec or {}).get(field) or {}).get("value") if isinstance((rec or {}).get(field), dict) else None
    if v is None:
        return None, None
    try:
        return vocab.tag("morphoswarm-register", field, v), None
    except vocab.VocabularyError:
        return None, {"field": field, "value": v}


def key_of(ns: str, kind: str, id: str) -> str:
    """Display/identity key that keeps the namespace: two nodes may use the same id for different records."""
    return f"{ns}/{kind}/{id}"


def assessment_block(assessments: list[dict], target: dict, local_status: dict | None) -> dict:
    """What has been ASSERTED about this exact target version, by whom and from where, kept apart from local acceptance.
    An Assessment record that was imported (local state imported_unreviewed) is another node's assertion, not this node's review.
    `local_acceptance.target_local_status` is this node's own state for the target version; it is only reported when the caller
    supplied local states, and only accepted/disputed/rejected there are local review outcomes. This view never calls any of it truth."""
    same = [x for x in assessments if (x["payload"]["target"]["namespace"], x["payload"]["target"]["kind"], x["payload"]["target"]["id"]) ==
            (target["namespace"], target["kind"], target["id"])]
    cur = [x for x in same if x["payload"]["target"]["version"] == target["version"]]
    asserts = []
    for x in cur:
        rls = (local_status or {}).get(x["version"]) if local_status is not None else None
        asserts.append({"assessment_ref": {k: x[k] for k in ("namespace", "kind", "id", "version")}, "issuer": x["issuer"], "source_uri": x["source_uri"],
                        "record_namespace": x["namespace"], "created_at": x["created_at"],
                        "decision": vocab.tag_lenient("frontier-store", "assessment_decision", x["payload"]["decision"]),
                        "record_local_status": rls,
                        "imported_from_another_node": rls == "imported_unreviewed" or x["namespace"] != target["namespace"]})
    provided = local_status is not None
    tls = (local_status or {}).get(target["version"]) if provided else None
    return {"assertions": asserts, "latest_assertion": asserts[-1] if asserts else None, "assessments_on_older_versions": len(same) - len(cur),
            "local_acceptance": {"provided": provided, "target_local_status": tls,
                                 "is_local_review_outcome": tls in ("accepted", "disputed", "rejected"),
                                 "note": "local states not supplied to this view" if not provided else "this node's own state for this exact version"},
            "label": "assessment ASSERTION (issuer and source shown); not called truth. Local acceptance is separate and only where local states are supplied."}


def build_view(records: list[dict], events: list[dict], annotations: list[dict], now: str, local_status: dict | None = None) -> dict:
    h = heads(records)
    problems = {(k[0], k[2]): v for k, v in h.items() if k[1] == "Problem"}
    verified = []
    rejected = []
    for doc in annotations:
        try:
            verified.append(ann.verify(doc) | {"annotation_sha256": doc["annotation_sha256"]})
        except Exception as exc:                      # a bad annotation is a finding, not a crash
            rejected.append({"error": str(exc)[:300]})
    ann_by_target: dict[tuple, list] = defaultdict(list)
    for a in verified:
        ann_by_target[(a["target"]["namespace"], a["target"]["id"])].append(a)
    interests = [v["head"] for k, v in h.items() if k[1] == "Interest"]
    assessments = sorted((r for r in records if r["kind"] == "Assessment"), key=lambda r: (r["created_at"], r["version"]))
    applied_by_version = {}
    rows = []
    for pkey in sorted(problems):
        ns_, pid = pkey
        rec = problems[pkey]["head"]
        p = rec["payload"]
        ref = {k: rec[k] for k in ("namespace", "kind", "id", "version")}
        cands = ann_by_target.get((ns_, pid), [])
        current = [a for a in cands if a["target"]["version"] == rec["version"]]
        current.sort(key=lambda a: (a["created_at"], a["annotation_sha256"]))
        if current:
            a = current[-1]
            ann_status = {"status": "applied", "sha256": a["annotation_sha256"], "annotator_operator": a["annotator_operator"],
                          "superseded_applicable_annotations": len(current) - 1}
            applied_by_version[rec["version"]] = a
        elif cands:
            ann_status = {"status": "stale", "reason": "pinned to an older Problem version; not applied", "sha256": cands[-1]["annotation_sha256"]}
            a = None
        else:
            ann_status, a = {"status": "none", "reason": "no annotation: unlocks, bounded action and utilities are unknown"}, None
        reg = (p.get("original") or {}).get("register_record") or {}
        imp, bad1 = _label(reg, "importance")
        tra, bad2 = _label(reg, "tractability")
        decisions = {d: m for d, m in (a["decisions"] if a else {}).items()}
        uv = unlock_value([e for e in a["unlocks"]] if a else [], decisions) if a else None
        if uv is None or not (uv["decisions_valued"] or uv["decisions_unknown_utility"]):
            utility = {"status": "unknown", "evpi": None, "reason": "no annotation" if a is None else "no unlock edge names a decision"}
        elif uv["value"] is None:
            utility = {"status": "unknown", "evpi": None, "reason": "no unlocked decision has a declared utility", "decisions_unknown_utility": uv["decisions_unknown_utility"]}
        else:
            utility = {"status": "partial" if uv["decisions_unknown_utility"] else "declared", "evpi": uv["value"], "unit": uv["unit"],
                       "prior_meaning": "annotator-declared belief about the state of a DECISION, used only inside EVPI; it is not the probability that any claim or theory is true",
                       "decisions_unknown_utility": uv["decisions_unknown_utility"], "breakdown": uv["breakdown"], "caveats": uv["caveats"]}
        assessment = assessment_block(assessments, ref, local_status)
        sig = defaultdict(set)
        older = 0
        for i in interests:
            t = i["payload"]["target"]
            if t["id"] == pid and t["namespace"] == rec["namespace"]:
                if t["version"] == rec["version"]:
                    sig[i["payload"]["signal"]].add(i["issuer"])
                else:
                    older += 1
        row = {
            "ref": ref, "key": key_of(ns_, "Problem", pid), "head_ambiguous_fork": problems[pkey]["ambiguous"],
            "store": {"problem_kind": vocab.tag_lenient("frontier-store", "problem_kind", p["problem_kind"]),
                      "completeness": vocab.tag_lenient("frontier-store", "completeness", p["completeness"]),
                      "question": p["question"], "known_state": p["known_state"], "next_action_text": p.get("next_action"),
                      "cost_stop_bounds_text": p.get("cost_stop_bounds"), "downstream_uses_untyped": list(p.get("downstream_uses", [])),
                      # whiteboard facets as the store declares them; verbatim, NOT validated or translated by this layer
                      "approach": p.get("approach"), "scales": p.get("scales"), "context_tags": p.get("context_tags"),
                      "dependencies": list(p.get("dependencies", []))},
            "register_labels": {"importance": imp, "tractability": tra, "unrecognised": [x for x in (bad1, bad2) if x]},
            "assessment": assessment, "annotation": ann_status,
            "typed_unlocks": list(a["unlocks"]) if a else [], "typed_next_action": (a["next_action"] if a else None),
            "bounded_cost": (a["next_action"]["resource_estimate"] if a and a["next_action"] else None),
            "utility": utility,
            "unlock_reasons": [{"relation": e.get("relation"), "kind": e["kind"], "target": e.get("target"), "decision_id": e.get("decision_id"),
                                "reason": e.get("reason"), "provenance": e["provenance"],
                                "counted_in_value": e["kind"] in ("logical_necessity", "empirical_relevance") and e.get("decision_id") is not None}
                               for e in (a["unlocks"] if a else [])],
            "interest_issuers": {k: sorted(v) for k, v in sorted(sig.items())}, "interests_on_older_versions": older,
        }
        rows.append(row)
    dependents: dict[tuple, list] = defaultdict(list)
    for pkey, v in problems.items():
        for dep in v["head"]["payload"].get("dependencies", []):
            if dep.get("kind") == "Problem":
                dependents[(dep["namespace"], dep["id"])].append({"dependent": key_of(pkey[0], "Problem", pkey[1]), "pinned_version": dep["version"]})
    for row in rows:
        ds = dependents.get((row["ref"]["namespace"], row["ref"]["id"]), [])
        row["dependents"] = sorted({d["dependent"] for d in ds})
        row["dependents_pinned_to_older_version"] = sum(1 for d in ds if d["pinned_version"] != row["ref"]["version"])
    ledger = action_ledger(records, events, now, {v: a for v, a in applied_by_version.items()}, local_status)
    by_problem = defaultdict(list)
    for L in ledger:
        by_problem[(L["target"]["namespace"], L["target"]["id"])].append(L)
    for row in rows:
        acts = by_problem.get((row["ref"]["namespace"], row["ref"]["id"]), [])
        row["actions"] = [{"key": L["key"], "id": L["action"]["id"], "version": L["action"]["version"], "state": L["state"], "lease_live_at_now": L["lease_live_at_now"],
                           "lease_operator": (L["lease"] or {}).get("operator"), "targets_current_problem_version": L["target"]["version"] == row["ref"]["version"],
                           "flags": L["flags"]} for L in acts]
        row["why_priority"] = _why(row)
    facets = {"design_requirement": [], "theory_challenge": [], "both": [], "neither_stated": []}
    for row in rows:
        rel = {u["relation"] for u in row["unlock_reasons"] if u["relation"]}
        facets["both" if len(rel) == 2 else (next(iter(rel)) if rel else "neither_stated")].append(row["key"])
    return {"now": now, "n_problems": len(rows), "rows": rows, "whiteboard_facets": facets, "action_ledger": ledger, "annotations_rejected": rejected,
            "meaning": ("priority fields and the assessment column are independent: no ranking reads an Assessment, and no annotation changes one. "
                        "Unknown utility is reported as unknown."), "does_not_imply": DOES_NOT_IMPLY}


def _why(row) -> list[dict]:
    w = []
    c = row["store"]["completeness"]
    w.append({"field": "frontier-store.completeness", "value": c["value"],
              "effect": ("has the four actionability fields; an Action may target it" if c["value"] == "actionable"
                         else "recorded only: the store refuses an Action against it until acceptance criteria, falsifiers, next action and stop bounds exist")})
    a = row["annotation"]
    w.append({"field": "annotation.status", "value": a["status"], "effect": {"applied": "typed unlocks, bounded action and utilities below come from this annotation",
              "stale": "an annotation exists for an older Problem version and is NOT applied", "none": "no typed unlocks, no bounded action, utility unknown"}[a["status"]]})
    if row["typed_unlocks"]:
        g = {e["independent_group"] for e in row["typed_unlocks"] if e["kind"] in ("logical_necessity", "empirical_relevance")}
        w.append({"field": "annotation.unlocks", "value": f"{len(row['typed_unlocks'])} edges, {len(g)} independent groups", "effect": "structural consequence; proposed_connection edges excluded from the count"})
    u = row["utility"]
    w.append({"field": "annotation.decisions", "value": u["status"], "effect": ("declared EVPI %.6g %s" % (u["evpi"], u.get("unit")) if u["evpi"] is not None
                                                                                  else "utility is UNKNOWN; nothing is imputed")})
    if row["bounded_cost"]:
        w.append({"field": "annotation.next_action.resource_estimate", "value": f"{row['bounded_cost']['amount']} {row['bounded_cost']['unit']} (estimate)", "effect": "bounded cost; not a measurement"})
    for u in row["unlock_reasons"]:
        if u["relation"]:
            what = ("unlocks a design requirement" if u["relation"] == "design_requirement" else "challenges a theory")
            to = u["decision_id"] or (u["target"] or {}).get("id")
            w.append({"field": "annotation.unlocks.relation", "value": f"{what}: {to}", "effect": u["reason"] + (" [counts toward declared value]" if u["counted_in_value"] else " [reason shown; not part of any value]")})
    for f in ("importance", "tractability"):
        lab = row["register_labels"][f]
        if lab:
            w.append({"field": f"morphoswarm-register.{f}", "value": lab["value"], "effect": "curator label in the register's own vocabulary"})
    live = [x for x in row["actions"] if x["lease_live_at_now"]]
    if live:
        w.append({"field": "action_ledger", "value": f"{len(live)} live lease(s)", "effect": "someone holds an active lease"})
    return w
