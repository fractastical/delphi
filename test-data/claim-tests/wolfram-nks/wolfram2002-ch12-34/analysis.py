#!/usr/bin/env python3
"""Check Wolfram's rule 30/110 integer formulas and the Diophantine gadgets
quoted in the NKS note on the universal Diophantine equation.

Criteria in result.json were committed before this script was run.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def formula30(a):
    return a ^ (((a | (a << 1)) << 1))


def formula110(a):
    return (a & (a << 1) & (a << 2)) ^ ((a << 1) | (a << 2))


def table_step(rule, a):
    """Output bit k = rule(left=bit k, center=bit k-1, right=bit k-2), absent bits 0."""
    width = a.bit_length() + 2
    out = 0
    for k in range(width):
        left = (a >> k) & 1
        center = (a >> (k - 1)) & 1 if k >= 1 else 0
        right = (a >> (k - 2)) & 1 if k >= 2 else 0
        idx = (left << 2) | (center << 1) | right
        if (rule >> idx) & 1:
            out |= 1 << k
    return out


def part_f():
    bad30 = bad110 = 0
    first = []
    for a in range(65536):
        t30 = table_step(30, a)
        t110 = table_step(110, a)
        if formula30(a) != t30:
            bad30 += 1
            if len(first) < 5:
                first.append({"rule": 30, "a": a, "formula": formula30(a), "table": t30})
        if formula110(a) != t110:
            bad110 += 1
            if len(first) < 5:
                first.append({"rule": 110, "a": a, "formula": formula110(a), "table": t110})
    return bad30, bad110, first


def part_h():
    bad = 0
    first = None
    for a in range(256):
        f = t = a
        for step in range(8):
            f = formula110(f)
            t = table_step(110, t)
            if f != t:
                bad += 1
                if first is None:
                    first = {"a": a, "step": step + 1, "formula": f, "table": t}
                break
    return bad, first


def part_g():
    cex = 0
    examples = []

    def fail(kind, detail):
        nonlocal cex
        cex += 1
        if len(examples) < 8:
            examples.append({"kind": kind, **detail})

    for a in range(41):
        for b in range(41):
            if (a * a + b * b == 0) != (a == 0 and b == 0):
                fail("sum_squares", {"a": a, "b": b})
            if ((a * b) == 0) != (a == 0 or b == 0):
                fail("product", {"a": a, "b": b})
            if (a + b == 0) != (a == 0 and b == 0):
                fail("sum", {"a": a, "b": b})
            exists = any(b == a + c + 1 for c in range(41))
            if exists != (a < b):
                fail("less", {"a": a, "b": b, "exists": exists})
    for a in range(41):
        for b in range(41):
            for c in range(1, 41):
                exists_mod = any(b == a + c * d and a < c for d in range((b // c) + 2))
                if exists_mod != (a == (b % c)):
                    fail("mod", {"a": a, "b": b, "c": c})
                exists_q = any(b == a * c + d and 0 <= d < c for d in range(c))
                if exists_q != (a == (b // c)):
                    fail("quotient", {"a": a, "b": b, "c": c})
    return cex, examples


def part_b():
    cex = 0
    examples = []
    by_b0 = 0
    checked = 0
    for b in range(9):
        for c in range(9):
            n = 2 * b + 1
            comb = math.comb(b, c)
            nc = n ** c
            npow = (n + 1) ** b
            candidates = set(range(n + 1))
            candidates.add(comb)
            for a in sorted(candidates):
                if nc == 0:
                    ok = False
                else:
                    e = npow % nc
                    quot = npow // nc
                    ok = (a < n) and (e < nc) and (quot >= a) and ((quot - a) % n == 0)
                should = a == comb
                checked += 1
                if ok != should:
                    cex += 1
                    if b == 0:
                        by_b0 += 1
                    if len(examples) < 12:
                        examples.append({
                            "a": a, "b": b, "c": c, "n": n, "comb": comb,
                            "encoding_accepts": ok, "should": should,
                        })
    return cex, by_b0, checked, examples


def lucas_table(limit):
    odd = [[False] * (limit + 1) for _ in range(limit + 1)]
    for x in range(limit + 1):
        for y in range(limit + 1):
            odd[x][y] = (math.comb(x, y) % 2) == 1
    return odd


def part_l(odd):
    cex = 0
    examples = []
    for x in range(129):
        for y in range(129):
            subset = (y & x) == y
            if odd[x][y] != subset:
                cex += 1
                if len(examples) < 5:
                    examples.append({"x": x, "y": y, "odd": odd[x][y], "subset": subset})
    return cex, examples


def part_a(odd):
    cex = 0
    examples = []
    checked_pairs = 0
    for c in range(65):
        for d in range(65):
            good_a = c & d
            good_b = c | d
            for a in range(65):
                for b in range(65):
                    checked_pairs += 1
                    holds = (
                        odd[c][a] and odd[d][a] and odd[b][c] and odd[b][d] and (a + b == c + d)
                    )
                    should = a == good_a and b == good_b
                    if holds != should:
                        cex += 1
                        if len(examples) < 8:
                            examples.append({
                                "c": c, "d": d, "a": a, "b": b,
                                "holds": holds, "should": should,
                            })
    return cex, checked_pairs, examples


def main():
    bad30, bad110, first_f = part_f()
    bad_h, first_h = part_h()
    g_cex, g_ex = part_g()
    b_cex, b_b0, b_checked, b_ex = part_b()
    odd = lucas_table(128)
    # part A only needs parity through 64, which the 0..128 table includes
    l_cex, l_ex = part_l(odd)
    a_cex, a_checked, a_ex = part_a(odd)
    counts = {
        "formula30_mismatches": bad30,
        "formula110_mismatches": bad110,
        "history8_mismatches": bad_h,
        "gadget_counterexamples": g_cex,
        "binomial_counterexamples": b_cex,
        "binomial_counterexamples_b0": b_b0,
        "lucas_counterexamples": l_cex,
        "bitand_counterexamples": a_cex,
    }
    if bad30 or bad110 or bad_h:
        verdict, confidence, reason = "refutes", 0.90, None
    elif g_cex or b_cex or l_cex or a_cex:
        verdict, confidence, reason = "mixed", 0.74, None
    else:
        verdict, confidence, reason = "supports", 0.88, None
    measured = {
        "value": bad110 + bad_h + b_cex + a_cex + g_cex + l_cex + bad30,
        "unit": "counterexamples across the rule formulas, the 8-step histories, and the Diophantine gadgets",
        "n": 65536,
        "uncertainty": "exact",
        "extra": {
            **counts,
            "binomial_pairs_checked": b_checked,
            "bitand_quadruples_checked": a_checked,
            "formula_mismatch_examples": first_f,
            "history_mismatch_example": first_h,
            "gadget_examples": g_ex,
            "binomial_examples": b_ex,
            "lucas_examples": l_ex,
            "bitand_examples": a_ex,
        },
    }
    method = (
        "analysis.py compares two implementations of one infinite-line step. The bitwise formulas are "
        "BitXor[a, 2 BitOr[a, 2a]] for rule 30 and BitXor[BitAnd[a, 2a, 4a], BitOr[2a, 4a]] for rule 110. "
        "The other implementation sets bit k from the Wolfram truth table on neighbors (bit k, bit k-1, bit k-2). "
        "They are compared for every integer from 0 through 65535, and the rule 110 formula is iterated "
        "eight steps from every integer from 0 through 255. The note's gadgets (sums of squares, products, "
        "strict inequality, mod, quotient, the base-(2b+1) binomial equation, Lucas parity, and the "
        "BitAnd/BitOr translation) are checked by exhaustive enumeration on the pre-registered boxes. "
        "Criteria were frozen in commit 093ca8002a77b774b469b965ff599d123fdaefbb before this run."
    )
    datasets = [{
        "id": "rule110-diophantine-gadgets",
        "name": "Integer checks of the NKS rule 30 and rule 110 formulas and the note's Diophantine gadgets, generated by analysis.py",
        "landing_url": "https://www.wolframscience.com/nks/p785--implications-for-mathematics-and-its-foundations/",
        "doi": None,
        "version": "generated",
        "license": None,
        "generator": "analysis.py",
        "program_family": (
            "elementary rules 30 and 110; integer formulas "
            "a XOR ((a OR 2a) << 1) and (a AND 2a AND 4a) XOR (2a OR 4a); "
            "bit k reads neighborhood (bit k, bit k-1, bit k-2); "
            "seeds 0..65535 and 8-step histories from 0..255; "
            "gadget boxes a,b in 0..40, c in 1..40, binomial b,c in 0..8, Lucas x,y in 0..128, BitAnd c,d,a,b in 0..64"
        ),
        "files": [],
        "role": "the finite integer boxes on which the rule 110 encoding is checked",
    }]
    caveats = [
        "The computation shows whether these integer encodings match the cellular automaton and the stated arithmetic relations. It does not show that organisms follow the claim.",
        "Rule 110's universality is Cook's theorem and was not re-proved here. No search for a sentence independent of Peano arithmetic was run, so the step from an emulated universal cellular automaton to Gödel's theorem is not a measured implication of this test.",
        "Wolfram's note says the exponential equation can be rewritten as a polynomial in 2154 variables. That figure is quoted from the note and was not recomputed.",
        (
            f"The bitwise formulas matched the truth table on every seed from 0 through 65535 "
            f"({bad30} rule-30 mismatches, {bad110} rule-110 mismatches) and on every 8-step history "
            f"({bad_h} mismatches). Lucas parity and the BitAnd/BitOr translation had {l_cex} and {a_cex} "
            f"counterexamples. The base-(2b+1) binomial equation had {b_cex} counterexamples on the checked "
            f"candidates, {b_b0} of them at b=0, where the base n=1 is degenerate; the rest are values such as "
            f"C(6,2)=15 and C(6,3)=20, which are larger than n=13, so the coefficient is not a single digit."
        ),
    ]
    path = os.path.join(HERE, "result.json")
    with open(path) as f:
        result = json.load(f)
    frozen_keys = (
        "claim_id", "claim_iri", "project", "hypothesis", "pass_criterion", "fail_criterion",
        "planned_datasets", "interpretation", "test_contract", "agent",
    )
    frozen = {k: result[k] for k in frozen_keys}
    result.update({
        "status": "complete",
        "data_kind": "computational",
        "verdict": verdict,
        "confidence": confidence,
        "measured": measured,
        "method": method,
        "datasets": datasets,
        "caveats": caveats,
    })
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    for k, v in frozen.items():
        result[k] = v
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump({"verdict": verdict, "measured": measured}, f, indent=2)
        f.write("\n")
    print(json.dumps({"verdict": verdict, "confidence": confidence, **counts}, indent=2))


if __name__ == "__main__":
    main()
