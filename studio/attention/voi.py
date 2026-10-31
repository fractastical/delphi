"""Value of information for the decisions an answer would unlock (ported from delphi-evolve frontier_attention.voi, pure Python).

EVPI = E_s[max_a U(a,s)] - max_a E_s[U(a,s)]; EVSI for an experiment with likelihood L(o|s). Utilities and priors are DECLARED
with a source in an annotation; a decision with utility_status 'unknown' contributes nothing and is listed as unknown.
"""
from __future__ import annotations

import math

TOL = 1e-9


class DecisionModelError(ValueError):
    pass


def check(prior: dict, utilities: dict):
    if not prior or not utilities:
        raise DecisionModelError("a decision needs states with a prior and at least one action with utilities")
    for s, p in prior.items():
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or p < 0:
            raise DecisionModelError(f"prior[{s!r}] must be a finite probability >= 0")
    if abs(sum(prior.values()) - 1.0) > TOL:
        raise DecisionModelError(f"prior sums to {sum(prior.values())}, not 1")
    for a, row in utilities.items():
        if set(row) != set(prior):
            raise DecisionModelError(f"action {a!r} must give a utility for exactly the states {sorted(prior)}")
        for s, u in row.items():
            if isinstance(u, bool) or not isinstance(u, (int, float)) or not math.isfinite(u):
                raise DecisionModelError(f"utility[{a!r}][{s!r}] must be a finite number")


def best_action(prior: dict, utilities: dict):
    check(prior, utilities)
    scored = sorted((-sum(prior[s] * u for s, u in row.items()), a) for a, row in utilities.items())
    return scored[0][1], -scored[0][0]


def evpi(prior: dict, utilities: dict) -> float:
    check(prior, utilities)
    return float(sum(p * max(row[s] for row in utilities.values()) for s, p in prior.items()) - best_action(prior, utilities)[1])


def evsi(prior: dict, utilities: dict, likelihood: dict) -> float:
    check(prior, utilities)
    for s in prior:
        tot = sum(likelihood[o][s] for o in likelihood)
        if abs(tot - 1.0) > TOL:
            raise DecisionModelError(f"likelihood for state {s!r} sums to {tot}, not 1")
    value = 0.0
    for col in likelihood.values():
        value += max(sum(prior[s] * col[s] * u for s, u in row.items()) for row in utilities.values())
    return float(value - best_action(prior, utilities)[1])


def unlock_value(edges: list[dict], decisions: dict) -> dict:
    """Summed EVPI over DISTINCT unlocked decisions. Several routes to one decision count once; decisions sharing an
    `independent_group` are not additive (the group contributes its maximum); `proposed_connection` edges never count; decisions with
    utility_status 'unknown' are listed, never valued; mixed units are not summed."""
    counted = [e for e in edges if e["kind"] in ("logical_necessity", "empirical_relevance") and e.get("decision_id")]
    first: dict[str, str] = {}
    for e in counted:
        first.setdefault(e["decision_id"], e["independent_group"])
    est, unknown = {}, []
    for d, g in sorted(first.items()):
        m = decisions.get(d)
        if m is None or m["utility_status"] != "declared":
            unknown.append(d)
            continue
        est[d] = {"evpi": evpi(m["prior"], m["utilities"]), "unit": m["unit"], "group": g, "prior_source": m["prior_source"], "utility_source": m["utility_source"]}
    out = {"n_edges": len(edges), "decisions_valued": sorted(est), "decisions_unknown_utility": unknown,
           "proposed_only_decisions": sorted({e["decision_id"] for e in edges if e["kind"] == "proposed_connection" and e.get("decision_id")} - set(first)),
           "breakdown": est, "caveats": []}
    units = sorted({v["unit"] for v in est.values()})
    if not est:
        return {**out, "value": None, "unit": None}
    if len(units) != 1:
        out["caveats"].append(f"decision utilities use units {units}; not summed")
        return {**out, "value": None, "unit": None}
    groups: dict[str, float] = {}
    for v in est.values():
        groups[v["group"]] = max(groups.get(v["group"], 0.0), v["evpi"])
    if unknown:
        out["caveats"].append(f"{len(unknown)} unlocked decision(s) have unknown utility; value is a lower bound over the valued ones")
    return {**out, "value": float(sum(groups.values())), "unit": units[0], "groups": groups}
