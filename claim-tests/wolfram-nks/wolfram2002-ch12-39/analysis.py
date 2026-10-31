#!/usr/bin/env python3
"""Test of wolfram2002-ch12-39: 'complete and consistent iff exactly half of the strings of
each length are generated', for length-preserving involutive negations.

Part 1: exhaustive sets and involutions. Part 2: small multiway systems with exactly
computable generated sets. Writes derived/measurements.json.
"""
import itertools
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ part 1
def all_involutions(m):
    """All involutions of range(m) as permutation lists."""
    out = []

    def rec(perm, i):
        while i < m and perm[i] is not None:
            i += 1
        if i == m:
            out.append(list(perm))
            return
        perm[i] = i
        rec(perm, i + 1)
        for j in range(i + 1, m):
            if perm[j] is None:
                perm[i], perm[j] = j, i
                rec(perm, i + 1)
                perm[j] = None
        perm[i] = None

    rec([None] * m, 0)
    return out


def random_involution(rng, m):
    k = int(rng.integers(0, m // 2 + 1))  # number of 2-cycles
    els = rng.permutation(m)
    perm = list(range(m))
    for t in range(k):
        a, b = int(els[2 * t]), int(els[2 * t + 1])
        perm[a], perm[b] = b, a
    return perm


def evaluate_sets(perm, m):
    """For every subset S of range(m) (bitmask), evaluate complete, consistent, |S| vs half."""
    perm = np.asarray(perm)
    S = np.arange(1 << m, dtype=np.int64)
    inS = ((S[:, None] >> np.arange(m)) & 1).astype(bool)  # [2^m, m]
    inNeg = inS[:, perm]
    complete = np.all(inS | inNeg, axis=1)
    consistent = ~np.any(inS & inNeg, axis=1)
    size = inS.sum(axis=1)
    half = m // 2
    cc = complete & consistent
    exact = size == half
    return {
        "n_sets": int(len(S)),
        "fixed_points": int(np.sum(perm == np.arange(m))),
        "n_complete_and_consistent": int(cc.sum()),
        "n_exactly_half": int(exact.sum()),
        "cex_cc_but_not_half": int(np.sum(cc & ~exact)),
        "cex_half_but_not_cc": int(np.sum(exact & ~cc)),
        "cex_more_than_half_but_consistent": int(np.sum((size > half) & consistent)),
        "cex_less_than_half_but_complete": int(np.sum((size < half) & complete)),
    }


def part1():
    out = {}
    m = 8
    invs = all_involutions(m)
    rows = [evaluate_sets(p, m) for p in invs]
    out["n3_all_involutions"] = summarise(rows, len(invs))
    m = 16
    rng = np.random.default_rng(20261031)
    strings = ["".join(b) for b in itertools.product("01", repeat=4)]
    idx = {s: i for i, s in enumerate(strings)}
    complement = [idx["".join("1" if c == "0" else "0" for c in s)] for s in strings]
    reversal = [idx[s[::-1]] for s in strings]
    identity = list(range(m))
    special = {"complement": complement, "reversal": reversal, "identity": identity}
    rows = [evaluate_sets(p, m) for p in special.values()]
    out["n4_special_involutions"] = {name: r for name, r in zip(special, rows)}
    rand = [random_involution(rng, m) for _ in range(300)]
    rows_r = [evaluate_sets(p, m) for p in rand]
    out["n4_random_involutions"] = summarise(rows_r, len(rand))
    return out


def summarise(rows, n_inv):
    fpf = [r for r in rows if r["fixed_points"] == 0]
    wfp = [r for r in rows if r["fixed_points"] > 0]
    keys = ["cex_cc_but_not_half", "cex_half_but_not_cc", "cex_more_than_half_but_consistent", "cex_less_than_half_but_complete", "n_complete_and_consistent", "n_exactly_half"]
    return {
        "n_involutions": n_inv, "n_fixed_point_free": len(fpf), "n_with_fixed_points": len(wfp),
        "n_sets_per_involution": rows[0]["n_sets"],
        "fixed_point_free_totals": {k: sum(r[k] for r in fpf) for k in keys},
        "with_fixed_points_totals": {k: sum(r[k] for r in wfp) for k in keys},
        "n_involutions_with_cex_half_but_not_cc": sum(r["cex_half_but_not_cc"] > 0 for r in rows),
    }


# ------------------------------------------------------------------ part 2
MAXLEN = 6


def generated_sets(rules, start="A", maxlen=MAXLEN):
    """Closure of {start} under the rules, restricted to strings of length <= maxlen.
    Exact because every rule is length-non-decreasing."""
    seen = {start}
    frontier = [start]
    while frontier:
        new = []
        for s in frontier:
            for lhs, rhs in rules:
                k = len(lhs)
                for i in range(len(s) - k + 1):
                    if s[i:i + k] == lhs:
                        t = s[:i] + rhs + s[i + k:]
                        if len(t) <= maxlen and t not in seen:
                            seen.add(t)
                            new.append(t)
        frontier = new
    return seen


def part2():
    alphabet = "AB"
    rule_list = []
    for k in (1, 2):
        for lhs in itertools.product(alphabet, repeat=k):
            for r in (k, k + 1):
                for rhs in itertools.product(alphabet, repeat=r):
                    if "".join(lhs) != "".join(rhs):
                        rule_list.append(("".join(lhs), "".join(rhs)))
    systems = [(r,) for r in rule_list] + list(itertools.combinations(rule_list, 2))
    negs = {
        "complement": lambda s: "".join("B" if c == "A" else "A" for c in s),
        "reversal": lambda s: s[::-1],
    }
    counts = {name: {n: {"n_systems": 0, "n_cc": 0, "n_half": 0, "cex_cc_not_half": 0, "cex_half_not_cc": 0,
                         "cex_more_consistent": 0, "cex_less_complete": 0, "examples_half_not_cc": []} for n in range(2, MAXLEN + 1)} for name in negs}
    for rules in systems:
        gen = generated_sets(rules)
        for n in range(2, MAXLEN + 1):
            allstr = ["".join(b) for b in itertools.product(alphabet, repeat=n)]
            S = {s for s in gen if len(s) == n}
            for name, neg in negs.items():
                complete = all((s in S) or (neg(s) in S) for s in allstr)
                consistent = not any((s in S) and (neg(s) in S) for s in allstr)
                half = len(allstr) // 2
                c = counts[name][n]
                c["n_systems"] += 1
                cc = complete and consistent
                c["n_cc"] += cc
                c["n_half"] += len(S) == half
                c["cex_cc_not_half"] += cc and len(S) != half
                if len(S) == half and not cc:
                    c["cex_half_not_cc"] += 1
                    if len(c["examples_half_not_cc"]) < 3:
                        c["examples_half_not_cc"].append({"rules": [f"{a}->{b}" for a, b in rules], "generated": sorted(S), "complete": complete, "consistent": consistent})
                c["cex_more_consistent"] += len(S) > half and consistent
                c["cex_less_complete"] += len(S) < half and complete
    return {"n_rules": len(rule_list), "n_systems": len(systems), "by_negation": {k: {str(n): v for n, v in d.items()} for k, d in counts.items()}}


def main():
    p1 = part1()
    p2 = part2()
    tot = lambda key: (p1["n3_all_involutions"]["fixed_point_free_totals"][key] + p1["n3_all_involutions"]["with_fixed_points_totals"][key]
                       + p1["n4_random_involutions"]["fixed_point_free_totals"][key] + p1["n4_random_involutions"]["with_fixed_points_totals"][key]
                       + sum(r[key] for r in p1["n4_special_involutions"].values()))
    p2tot = lambda key: sum(v[key] for d in p2["by_negation"].values() for v in d.values())
    crit = {
        "cex_more_than_half_but_consistent": tot("cex_more_than_half_but_consistent") + p2tot("cex_more_consistent"),
        "cex_less_than_half_but_complete": tot("cex_less_than_half_but_complete") + p2tot("cex_less_complete"),
        "cex_complete_consistent_but_not_half": tot("cex_cc_but_not_half") + p2tot("cex_cc_not_half"),
        "cex_half_but_not_complete_consistent_sets": tot("cex_half_but_not_cc"),
        "cex_half_but_not_complete_consistent_multiway": p2tot("cex_half_not_cc"),
        "cc_possible_with_fixed_points_n3": p1["n3_all_involutions"]["with_fixed_points_totals"]["n_complete_and_consistent"],
    }
    forward_ok = crit["cex_more_than_half_but_consistent"] == 0 and crit["cex_less_than_half_but_complete"] == 0 and crit["cex_complete_consistent_but_not_half"] == 0
    converse_fails = crit["cex_half_but_not_complete_consistent_sets"] > 0 and crit["cex_half_but_not_complete_consistent_multiway"] > 0
    if forward_ok and not converse_fails and crit["cex_half_but_not_complete_consistent_sets"] == 0:
        verdict = "supports"
    elif forward_ok and converse_fails:
        verdict = "mixed"
    else:
        verdict = "refutes"
    res = {"part1": p1, "part2": p2, "criteria": crit, "verdict": verdict}
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measurements.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({"part1": p1, "criteria": crit, "verdict": verdict}, indent=1))
    for name, d in p2["by_negation"].items():
        for n, v in d.items():
            print(name, n, {k: v[k] for k in v if k != "examples_half_not_cc"})
        print(name, "examples:", json.dumps(d["4"]["examples_half_not_cc"], indent=1))


if __name__ == "__main__":
    sys.exit(main())
