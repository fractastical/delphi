"""Matched-budget allocation experiment: harness plus a gate that refuses unusable traces.

Question: does coordinated allocation resolve more preregistered, decision-relevant uncertainty than simple policies within the same
budget? This module only COMPARES arms from real ledger rows with frozen, hashed problem values. It never generates outcomes. If the
traces cannot support the question, `trace_gate` returns the exact blocked reasons instead of a number. Pure Python (no scipy/numpy).
"""
from __future__ import annotations

from math import comb

from frontier.models import canonical, digest

PREREG = {"budget_tolerance": 0.05, "alpha": 0.05, "min_problems": 6, "min_arms": 2,
          "primary_comparison": ["coordinated", "sequential_persistent_agent"]}


DOES_NOT_IMPLY = ("Resolving more declared-value problems at a matched budget says nothing about whether any resolved design or claim is viable or true.")


class EvalError(Exception):
    pass


def frozen_hash(frozen: dict) -> str:
    return digest({"unit": frozen["unit"], "values": frozen["values"]})


def mcnemar_exact(x: list[bool], y: list[bool]) -> dict:
    b = sum(1 for a, c in zip(x, y) if a and not c)
    c = sum(1 for a, d in zip(x, y) if d and not a)
    n = b + c
    p = 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, k) for k in range(0, min(b, c) + 1)) / 2 ** n)
    return {"x_only_right": b, "y_only_right": c, "both_right": sum(1 for a, d in zip(x, y) if a and d),
            "both_wrong": sum(1 for a, d in zip(x, y) if not a and not d), "p_two_sided_exact": p}


def budget_spread(totals: dict[str, float]) -> float:
    lo, hi = min(totals.values()), max(totals.values())
    return hi / lo - 1.0


def evaluate(rows: list[dict], frozen: dict, arms: list[str], prereg: dict | None = None) -> dict:
    """rows: {arm, problem_id, cost, accepted, overturned, duplicate_of, handoff_failed}"""
    prereg = prereg or PREREG
    if frozen_hash(frozen) != frozen.get("sha256"):
        raise EvalError("frozen value table does not match its sha256: values changed after freezing")
    unknown = sorted({r["problem_id"] for r in rows} - set(frozen["values"]))
    if unknown:
        raise EvalError(f"rows reference problems with no frozen value: {unknown}")
    totals = {a: sum(r["cost"] for r in rows if r["arm"] == a) for a in arms}
    if min(totals.values()) <= 0:
        return {"verdict": "REFUSED", "reason": f"an arm has no recorded cost: {totals}"}
    spread = budget_spread(totals)
    if spread > prereg["budget_tolerance"] + 1e-12:
        return {"verdict": "REFUSED", "reason": f"budgets differ by {spread:.1%} > tolerance {prereg['budget_tolerance']:.1%}", "totals": totals}
    problems = sorted(frozen["values"])
    resolved, per_arm = {}, {}
    for a in arms:
        ar = [r for r in rows if r["arm"] == a]
        good = {r["problem_id"] for r in ar if r["accepted"] and not r["overturned"]}
        resolved[a] = {p: p in good for p in problems}
        n_acc = sum(1 for r in ar if r["accepted"])
        per_arm[a] = {"cost": totals[a], "accepted": n_acc, "incorrect_acceptance": sum(1 for r in ar if r["accepted"] and r["overturned"]),
                      "duplicate_effort_cost": sum(r["cost"] for r in ar if r.get("duplicate_of")),
                      "failed_handoffs": sum(1 for r in ar if r.get("handoff_failed")),
                      "problems_resolved": len(good), "problems_total": len(problems),
                      "registered_value_resolved": sum(frozen["values"][p] for p in good)}
    out = {"verdict": "COMPARED", "frozen_sha256": frozen["sha256"], "value_unit": frozen["unit"], "per_arm": per_arm, "comparisons": {}, "does_not_imply": DOES_NOT_IMPLY}
    for x in arms:
        for y in arms:
            if x >= y:
                continue
            m = mcnemar_exact([resolved[x][p] for p in problems], [resolved[y][p] for p in problems])
            if len(problems) < prereg["min_problems"]:
                v = f"INSUFFICIENT PROBLEMS ({len(problems)} < {prereg['min_problems']}): descriptive only"
            elif m["p_two_sided_exact"] >= prereg["alpha"]:
                v = "no detectable difference in problems resolved"
            else:
                better = x if per_arm[x]["problems_resolved"] > per_arm[y]["problems_resolved"] else y
                other = y if better == x else x
                v = f"{better} resolved more problems" + ("; BUT it also had more accepted results later overturned: not a clean win"
                                                           if per_arm[better]["incorrect_acceptance"] > per_arm[other]["incorrect_acceptance"] else "")
            out["comparisons"][f"{x} vs {y}"] = {**m, "verdict": v, "primary": sorted([x, y]) == sorted(prereg["primary_comparison"])}
    return out


def trace_gate(rows: list[dict], prereg: dict | None = None) -> dict:
    """Can these rows support an ALLOCATION comparison? rows: {arm, run, problem_id, cost, accepted, source_path, source_sha256}.
    Returns {usable, blocked_reasons, facts}. A comparison is meaningful only if arms differ in WHICH problems get effort,
    outcomes are not saturated, budgets match, there are enough problems, and every row cites a hashed source."""
    prereg = prereg or PREREG
    reasons, facts = [], {}
    if not rows:
        return {"usable": False, "blocked_reasons": ["no rows"], "facts": {}}
    missing = sum(1 for r in rows if not r.get("source_path") or not r.get("source_sha256"))
    facts["rows"] = len(rows); facts["rows_without_source_hash"] = missing
    if missing:
        reasons.append(f"{missing} rows do not cite a source path and sha256")
    arms = sorted({r["arm"] for r in rows})
    problems = sorted({r["problem_id"] for r in rows})
    facts.update(arms=arms, n_problems=len(problems))
    if len(arms) < prereg["min_arms"]:
        reasons.append(f"{len(arms)} arm(s) < {prereg['min_arms']}")
    if len(problems) < prereg["min_problems"]:
        reasons.append(f"{len(problems)} problems < minimum {prereg['min_problems']}")
    totals = {a: sum(r["cost"] for r in rows if r["arm"] == a) for a in arms}
    facts["cost_by_arm"] = totals
    if len(arms) >= 2 and min(totals.values()) > 0:
        spread = budget_spread(totals)
        facts["budget_spread"] = spread
        if spread > prereg["budget_tolerance"] + 1e-12:
            reasons.append(f"budgets differ by {spread:.1%} > {prereg['budget_tolerance']:.1%}")
    attempted = {a: {r["problem_id"] for r in rows if r["arm"] == a} for a in arms}
    facts["problems_attempted_by_arm"] = {a: len(s) for a, s in attempted.items()}
    if len({frozenset(s) for s in attempted.values()}) == 1:
        reasons.append("every arm attempted the identical set of problems: the arms do not differ in which problems receive effort, so this is not an allocation contrast")
    reps = {}
    for r in rows:
        reps.setdefault((r["arm"], r["problem_id"]), []).append(bool(r["accepted"]))
    rate = {k: sum(v) / len(v) for k, v in reps.items()}
    discordant = [p for p in problems if len({rate.get((a, p)) for a in arms}) > 1]
    facts["problems_where_arms_differ_in_resolution_rate"] = len(discordant)
    if not discordant:
        reasons.append("no problem is resolved differently by any arm (ceiling/floor): outcomes cannot discriminate policies")
    return {"usable": not reasons, "blocked_reasons": reasons, "facts": facts}
