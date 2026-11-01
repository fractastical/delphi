"""Deterministic AUTHORED demo annotations. A demonstration of the interface, kept apart from the actual snapshot.

They are judgements by the market worker, written from the Problems' own fields, not reviewed by anyone. Every edge is `proposed_connection`
(a suggestion, never counted toward any value), every decision has utility_status 'unknown' (no number is invented), and no next action is
given (that would need a real estimate and reviewer). Pinned to the exact current head version of each Problem and Claim, so they go stale
if either changes. Same store content -> byte-identical output (fixed created_at, sorted order).
"""
from __future__ import annotations

from . import annotation as A
from .records import heads

DEMO_OPERATOR = "demo-market-authored"
DEMO_CREATED = "2026-10-31T00:00:00+00:00"
LIMIT = ["DEMO: authored by the market worker to exercise the attention interface; not reviewed by anyone",
         "Edges are proposed_connection (suggestions) and no utility is estimated; nothing here is a rating or a finding"]


def _ref(r):
    return {k: r[k] for k in ("namespace", "kind", "id", "version")}


def demo_annotations(records: list[dict]) -> list[dict]:
    h = heads(records)
    prob = {k[2]: x["head"] for k, x in h.items() if k[1] == "Problem"}
    claim = {k[2]: x["head"] for k, x in h.items() if k[1] == "Claim"}
    out = []
    if "F003" in prob and "turing-ddi" in claim:
        f3 = prob["F003"]
        out.append(A.make_annotation({
            "target": _ref(f3), "annotator_operator": DEMO_OPERATOR, "created_at": DEMO_CREATED, "limitations": LIMIT,
            "decisions": {"demo:simulation-explorer-scope": {"utility_status": "unknown", "description": "what an honest simulation explorer may state about nonlinear outcomes"}},
            "unlocks": [
                {"kind": "proposed_connection", "target": _ref(claim["turing-ddi"]), "independent_group": "demo-F003-theory", "relation": "theory_challenge",
                 "provenance": "demo-authored from F003.question and its claim_ids",
                 "reason": "A converged nonlinear comparison in a frozen ensemble would show where the linear finite-domain prediction recorded in this Claim stops predicting the simulated outcome."},
                {"kind": "proposed_connection", "decision_id": "demo:simulation-explorer-scope", "independent_group": "demo-F003-design", "relation": "design_requirement",
                 "provenance": "demo-authored from F003.unlocks ('An honest simulation explorer')",
                 "reason": "An explorer that labels linear and nonlinear outcomes separately needs to know where they differ."}]}))
    if "F001" in prob and "fisher-ftns" in claim:
        f1 = prob["F001"]
        out.append(A.make_annotation({
            "target": _ref(f1), "annotator_operator": DEMO_OPERATOR, "created_at": DEMO_CREATED, "limitations": LIMIT,
            "decisions": {"demo:reuse-price-derivation": {"utility_status": "unknown", "description": "whether the existing Price derivation may be reused for the Fisher record"}},
            "unlocks": [
                {"kind": "proposed_connection", "decision_id": "demo:reuse-price-derivation", "independent_group": "demo-F001-design", "relation": "design_requirement",
                 "provenance": "demo-authored from F001.unlocks ('Scoped reuse of the Price derivation')",
                 "reason": "Reusing the derivation requires a faithful statement of which genetic projection and fixed-average-effect assumptions the Fisher record uses."}]}))
    return out
