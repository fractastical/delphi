#!/usr/bin/env python3
"""Published exponential Diophantine system for rule 110 (NKS note, p. 1160),
wolfram2002-ch12-34. Writes derived/measured.json.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

TABLE_110 = {
    (1, 1, 1): 0, (1, 1, 0): 1, (1, 0, 1): 1, (1, 0, 0): 0,
    (0, 1, 1): 1, (0, 1, 0): 1, (0, 0, 1): 1, (0, 0, 0): 0,
}


def step_bit(a):
    return (a & (2 * a) & (4 * a)) ^ ((2 * a) | (4 * a))


def rule110(p, q, r):
    return TABLE_110[(p, q, r)]


def truth_table_matches_bitwise():
    """Output bit i of step_bit depends on (bit i, bit i-1, bit i-2) as (left, centre, right)."""
    bad = 0
    checked = 0
    for a in range(1 << 12):
        out = step_bit(a)
        for i in range(12):
            p = (a >> i) & 1
            q = (a >> (i - 1)) & 1 if i >= 1 else 0
            r = (a >> (i - 2)) & 1 if i >= 2 else 0
            checked += 1
            if ((out >> i) & 1) != rule110(p, q, r):
                bad += 1
    code = 0
    for nb in range(8):
        p, q, r = (nb >> 2) & 1, (nb >> 1) & 1, nb & 1
        code |= rule110(p, q, r) << nb
    return {"neighborhoods_checked": checked, "mismatches": bad, "wolfram_code": code}


def evolve(n, t):
    rows = [n]
    a = n
    for _ in range(t):
        a = step_bit(a)
        rows.append(a)
    return rows


def pack_x6(x1, n, t):
    if t == 0:
        return 0
    rows = evolve(n, t - 1)
    gap = x1 + 2 * t + 1
    x6 = 0
    for k in range(t):
        shift = 1 + (t - 1 - k) * gap
        x6 += rows[k] << shift
    return x6


def witness(x1, n, t):
    """Build every published variable from (x1, x2=n+1, x3=t) and report which equations hold."""
    x2 = n + 1
    x3 = t
    w = x1 + 2 * t
    rows = evolve(n, t)
    x6 = pack_x6(x1, n, t)
    x7 = x6 & (2 * x6)
    x8 = x6 | (2 * x6)
    x9 = x6 & (2 * x7)
    x19 = x6 | (2 * x7)
    x10 = x9 & (2 * x8)
    x11 = x9 | (2 * x8)
    step = x11 - x10
    u = 1 + x3 * (1 + w)
    # equation (7) solves for x4 once x6 is known, if the right-hand side is even and non-negative
    rhs7 = (1 << u) * (x2 - 1) + step
    if rhs7 < 0 or rhs7 % 2:
        return {"ok": False, "reason": "eq7-not-even"}
    x4 = rhs7 // 2
    expo = (1 + x3) * w
    if x4 >= 1 << expo:
        return {"ok": False, "reason": "eq1-bound"}
    x12 = (1 << expo) - 1 - x4
    if not (0 <= x2 <= 1 << x1):
        return {"ok": False, "reason": "eq2-range"}
    x13 = (1 << x1) - x2
    # decompose x4 as equation (4)
    x16 = x4 % (1 << x3) if x3 else 0
    mid = x4 >> x3
    x5 = mid % (1 << x1)
    mid2 = mid >> x1
    x15 = mid2 % (1 << x3) if x3 else 0
    x6_back = mid2 >> x3 if x3 else mid2
    x14 = (1 << x1) - 1 - x5
    x17 = ((1 << x3) - 1 - x15) if x3 else 0
    x18 = ((1 << x3) - 1 - x16) if x3 else 0
    eqs = {
        "eq1": 1 + x4 + x12 == 1 << expo,
        "eq2": x2 + x13 == 1 << x1,
        "eq3": 1 + x5 + x14 == 1 << x1,
        "eq4": (1 << x3) * x5 + (1 << (x1 + 2 * x3)) * x6 + (1 << (x1 + x3)) * x15 + x16 == x4,
        "eq5": (1 + x15 + x17 == 1 << x3) if x3 else True,
        "eq6": (1 + x16 + x18 == 1 << x3) if x3 else True,
        "eq7": (1 << u) * (x2 - 1) - x10 + x11 == 2 * x4,
        "x6_roundtrip": x6_back == x6,
        "step_identity": step == step_bit(x6),
        "nonnegative": min(x4, x5, x6, x7, x8, x9, x10, x11, x12, x13, x14, x15, x16, x17, x18, x19) >= 0,
    }
    final = x4 % (1 << w)
    return {
        "ok": all(eqs.values()) and final == rows[-1],
        "equations": eqs,
        "final": final,
        "expected_final": rows[-1],
        "x4": x4,
        "x6": x6,
        "literal_final_of_x2": evolve(x2, t)[-1],
        "literal_low_x1_bits_of_x2": evolve(x2 % (1 << x1), t)[-1],
    }


def flip_fails(x1, n, t, x4):
    u = 1 + t * (1 + x1 + 2 * t)
    x6 = pack_x6(x1, n, t)
    x7 = x6 & (2 * x6)
    x8 = x6 | (2 * x6)
    x9 = x6 & (2 * x7)
    x10 = x9 & (2 * x8)
    x11 = x9 | (2 * x8)
    flipped = x4 ^ 1
    lhs = (1 << u) * n - x10 + x11
    return lhs != 2 * flipped


def count_solutions(x1, n, t):
    """Exhaustive count of x6 whose induced x4 stays inside the equation-(1) bound."""
    x2 = n + 1
    x3 = t
    w = x1 + 2 * t
    u = 1 + x3 * (1 + w)
    expo = (1 + x3) * w
    limit = 1 << (x3 * w) if x3 else 1
    hits = 0
    hit_x6 = None
    for x6 in range(limit):
        step = step_bit(x6)
        rhs = (1 << u) * (x2 - 1) + step
        if rhs < 0 or rhs & 1:
            continue
        x4 = rhs // 2
        if x4 < 0 or x4 >= 1 << expo:
            continue
        x6_back = (x4 >> w)
        # equation (4) puts x6 exactly at bit W, with the low W bits split into x16,x5,x15
        if x6_back == x6:
            hits += 1
            hit_x6 = x6
            if hits > 1:
                break
    return hits, hit_x6


def binomial_identity(bmax=8):
    ok = 0
    bad = 0
    false_accept = 0
    checked = 0
    for b in range(bmax + 1):
        n = (1 << b) + 1
        for c in range(b + 1):
            checked += 1
            true = math.comb(b, c)
            mod = n ** c
            val = (n + 1) ** b
            e = val % mod
            q = val // mod
            a = q % n
            if a == true and 0 <= e < mod and a < n:
                ok += 1
            else:
                bad += 1
            a_wrong = true + 1
            if a_wrong < n and (val // mod) % n == a_wrong:
                false_accept += 1
    return {"pairs": checked, "recovered": ok, "bad": bad, "false_accept_of_binomial_plus_one": false_accept}


def lucas_check(xmax=32):
    bad = 0
    checked = 0
    for x in range(xmax + 1):
        for y in range(x + 1):
            checked += 1
            odd = (math.comb(x, y) & 1) == 1
            submask = (x & y) == y
            if odd != submask:
                bad += 1
    return {"pairs": checked, "mismatches": bad}


def main():
    tt = truth_table_matches_bitwise()
    grid_ok = 0
    grid_n = 0
    literal_match = 0
    literal_low_bits_match = 0
    corrupt_fail = 0
    reasons = {}
    for x1 in range(1, 7):
        for t in range(1, 5):
            for n in range(1 << x1):
                grid_n += 1
                w = witness(x1, n, t)
                if w.get("ok"):
                    grid_ok += 1
                    if w["final"] == w["literal_final_of_x2"]:
                        literal_match += 1
                    if w["final"] == w["literal_low_x1_bits_of_x2"]:
                        literal_low_bits_match += 1
                    if flip_fails(x1, n, t, w["x4"]):
                        corrupt_fail += 1
                else:
                    reasons[w.get("reason", "mismatch")] = reasons.get(w.get("reason", "mismatch"), 0) + 1
    uniq_checked = 0
    uniq_exactly_one = 0
    uniq_matches_witness = 0
    uniq_more = 0
    for x1 in range(1, 4):
        for t in (1, 2):
            for n in range(1 << x1):
                uniq_checked += 1
                hits, hx = count_solutions(x1, n, t)
                if hits == 1:
                    uniq_exactly_one += 1
                    if hx == pack_x6(x1, n, t):
                        uniq_matches_witness += 1
                elif hits > 1:
                    uniq_more += 1
    measured = {
        "truth_table": tt,
        "grid": {
            "x1": "1..6",
            "T": "1..4",
            "points": grid_n,
            "witness_matches_evolution_of_x2_minus_1": grid_ok,
            "witness_matches_evolution_of_integer_x2": literal_match,
            "witness_matches_evolution_of_low_x1_bits_of_x2": literal_low_bits_match,
            "one_bit_flip_breaks_eq7": corrupt_fail,
            "failure_reasons": reasons,
        },
        "uniqueness_x1_le_3_T_le_2": {
            "points": uniq_checked,
            "exactly_one_x6": uniq_exactly_one,
            "that_x6_is_the_witness": uniq_matches_witness,
            "more_than_one": uniq_more,
        },
        "binomial_identity_b_le_8": binomial_identity(8),
        "lucas_parity_x_le_32": lucas_check(32),
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump(measured, f, indent=2)
        f.write("\n")
    print(json.dumps({k: measured[k] for k in measured if k != "truth_table"}, indent=2))
    print("truth", measured["truth_table"])


if __name__ == "__main__":
    main()
