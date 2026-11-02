#!/usr/bin/env python3
"""Trigonometric lift of integer equations, rule 30/110 formulas, and Cauchy's bound.

Criteria in result.json were committed before this script was run.
"""
import itertools
import json
import math
import os
from fractions import Fraction

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def formula30(a):
    return a ^ (((a | (a << 1)) << 1))


def formula110(a):
    return (a & (a << 1) & (a << 2)) ^ ((a << 1) | (a << 2))


def table_step(rule, a):
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


def trim(coeffs):
    coeffs = [Fraction(a) for a in coeffs]
    i = 0
    while i < len(coeffs) - 1 and coeffs[i] == 0:
        i += 1
    return coeffs[i:]


def deriv(coeffs):
    coeffs = trim(coeffs)
    n = len(coeffs) - 1
    if n <= 0:
        return [Fraction(0)]
    return trim([coeffs[i] * (n - i) for i in range(n)])


def rem(f, g):
    f = trim(f)
    g = trim(g)
    while len(f) >= len(g):
        shift = (len(f) - 1) - (len(g) - 1)
        lead = f[0] / g[0]
        shifted = list(g) + [Fraction(0)] * shift
        f = trim([f[i] - lead * shifted[i] for i in range(len(f))])
        if f == [Fraction(0)]:
            return [Fraction(0)]
    return f


def sturm(coeffs):
    s0 = trim(coeffs)
    s1 = deriv(s0)
    seq = [s0]
    if s1 != [Fraction(0)]:
        seq.append(s1)
    while len(seq[-1]) > 1:
        nxt = trim([-a for a in rem(seq[-2], seq[-1])])
        if nxt == [Fraction(0)]:
            break
        seq.append(nxt)
    return seq


def peval(coeffs, x):
    acc = Fraction(0)
    for a in coeffs:
        acc = acc * x + a
    return acc


def variations(seq, x):
    signs = []
    for poly in seq:
        if x == "inf":
            lead = poly[0]
        elif x == "-inf":
            lead = poly[0] * ((-1) ** (len(poly) - 1))
        else:
            lead = peval(poly, x)
        if lead > 0:
            signs.append(1)
        elif lead < 0:
            signs.append(-1)
    return sum(1 for i in range(len(signs) - 1) if signs[i] != signs[i + 1])


def band(value):
    mag = abs(value)
    if mag < 1e-8:
        return "zero"
    if mag <= 1e-6:
        return "ambiguous"
    return "nonzero"


def part_formulas():
    bad30 = bad110 = 0
    for a in range(65536):
        if formula30(a) != table_step(30, a):
            bad30 += 1
        if formula110(a) != table_step(110, a):
            bad110 += 1
    return bad30, bad110


def part_trig():
    py_bad = py_amb = 0
    py_n = 0
    for x, y, z in itertools.product(range(31), repeat=3):
        py_n += 1
        poly = (x * x + y * y - z * z) ** 2
        expr = (
            math.sin(math.pi * x) ** 2
            + math.sin(math.pi * y) ** 2
            + math.sin(math.pi * z) ** 2
            + poly
        )
        kind = band(expr)
        is_py = x * x + y * y == z * z
        if kind == "ambiguous":
            py_amb += 1
        elif is_py != (kind == "zero"):
            py_bad += 1
    half_bad = half_amb = half_n = 0
    grid = [i / 2 for i in range(41)]
    for x, y, z in itertools.product(grid, repeat=3):
        if x == int(x) and y == int(y) and z == int(z):
            continue
        half_n += 1
        poly = (x * x + y * y - z * z) ** 2
        expr = (
            math.sin(math.pi * x) ** 2
            + math.sin(math.pi * y) ** 2
            + math.sin(math.pi * z) ** 2
            + poly
        )
        kind = band(expr)
        if kind == "ambiguous":
            half_amb += 1
        elif kind != "nonzero":
            half_bad += 1
    lift_bad = lift_amb = 0
    max_b = 0
    for a in range(501):
        b = formula30(a)
        max_b = max(max_b, b)
        expr = math.sin(math.pi * a) ** 2 + math.sin(math.pi * b) ** 2
        wrong = math.sin(math.pi * a) ** 2 + math.sin(math.pi * (b + 1)) ** 2 + 1
        half = math.sin(math.pi * (a + 0.5)) ** 2
        if band(expr) == "ambiguous" or (wrong < 1 and band(wrong - 1) == "ambiguous"):
            lift_amb += 1
        elif band(expr) != "zero" or wrong < 1:
            lift_bad += 1
        if half <= 0.5:
            lift_bad += 1
    return {
        "pythagorean_n": py_n,
        "pythagorean_disagreements": py_bad,
        "pythagorean_ambiguous": py_amb,
        "half_grid_n": half_n,
        "half_grid_disagreements": half_bad,
        "half_grid_ambiguous": half_amb,
        "rule30_lift_disagreements": lift_bad,
        "rule30_lift_ambiguous": lift_amb,
        "max_rule30_image_on_0_to_500": max_b,
    }


def step_int(rule, state, width=8):
    out = 0
    mask = (1 << width) - 1
    state &= mask
    for i in range(width):
        left = (state >> ((i - 1) % width)) & 1
        center = (state >> i) & 1
        right = (state >> ((i + 1) % width)) & 1
        if (rule >> ((left << 2) | (center << 1) | right)) & 1:
            out |= 1 << i
    return out


def step_list(rule, bits):
    width = len(bits)
    out = [0] * width
    for i in range(width):
        left = bits[(i - 1) % width]
        center = bits[i]
        right = bits[(i + 1) % width]
        out[i] = (rule >> ((left << 2) | (center << 1) | right)) & 1
    return out


def pack(bits):
    value = 0
    for i, bit in enumerate(bits):
        if bit:
            value |= 1 << i
    return value


def part_periodic():
    stepper_bad = 0
    pigeon_bad = 0
    event_bad = 0
    event_amb = 0
    event_yes = {"30": 0, "110": 0}
    for rule in (30, 110):
        for init in range(256):
            bits = [(init >> i) & 1 for i in range(8)]
            state = init
            for _ in range(512):
                nxt_bits = step_list(rule, bits)
                nxt_state = step_int(rule, state)
                if pack(nxt_bits) != nxt_state:
                    stepper_bad += 1
                bits = nxt_bits
                state = nxt_state
            # event within 256 steps versus within 512, on the integer stepper
            def ever(limit):
                s = init
                seen = set()
                hit = None
                for t in range(limit):
                    if s & 1:
                        return True, t, s
                    if s in seen:
                        return False, None, None
                    seen.add(s)
                    s = step_int(rule, s)
                return False, None, None

            yes256, t256, _ = ever(256)
            yes512, _, _ = ever(512)
            if yes256 != yes512:
                pigeon_bad += 1
            if yes256:
                event_yes[str(rule)] += 1
                traj = []
                s = init
                for _ in range(t256 + 1):
                    traj.append(s)
                    s = step_int(rule, s)
                residual = 0.0
                for value in traj:
                    residual += math.sin(math.pi * value) ** 2
                for i in range(len(traj) - 1):
                    residual += (traj[i + 1] - step_list_packed(rule, traj[i])) ** 2
                residual += (1 - (traj[-1] & 1)) ** 2
                kind = band(residual)
                if kind == "ambiguous":
                    event_amb += 1
                elif kind != "zero":
                    event_bad += 1
    return {
        "stepper_disagreements": stepper_bad,
        "pigeonhole_disagreements": pigeon_bad,
        "event_witness_disagreements": event_bad,
        "event_witness_ambiguous": event_amb,
        "event_initial_conditions": event_yes,
    }


def step_list_packed(rule, state, width=8):
    bits = [(state >> i) & 1 for i in range(width)]
    return pack(step_list(rule, bits))


def part_polynomials():
    cauchy_sturm = 0
    sign_disagree = 0
    numpy_viol = 0
    n_poly = 0
    n_with_real = 0
    for degree in range(1, 6):
        for lead in (-2, -1, 1, 2):
            for rest in itertools.product((-2, -1, 0, 1, 2), repeat=degree):
                coeffs = [lead, *rest]
                n_poly += 1
                seq = sturm(coeffs)
                total = variations(seq, "-inf") - variations(seq, "inf")
                if total:
                    n_with_real += 1
                lower = max((abs(a) for a in coeffs[1:]), default=0)
                bound = Fraction(1) + Fraction(lower, abs(lead))
                right = variations(seq, bound) - variations(seq, Fraction(100))
                left = variations(seq, Fraction(-100)) - variations(seq, -bound)
                if peval(seq[0], -bound) == 0:
                    left -= 1
                if peval(seq[0], Fraction(100)) == 0:
                    right -= 1
                window = variations(seq, Fraction(-100)) - variations(seq, Fraction(100))
                if left < 0 or right < 0 or window != total or left + right > total:
                    sign_disagree += 1
                outside = max(left, 0) + max(right, 0)
                if window < total:
                    outside += total - window
                cauchy_sturm += outside
                bound_f = float(bound)
                for root in np.roots(coeffs):
                    if abs(root) > bound_f + 1e-4 and abs(np.polyval(coeffs, root)) <= 1e-6:
                        numpy_viol += 1
    return {
        "n_polynomials": n_poly,
        "n_with_a_real_root": n_with_real,
        "cauchy_violations_sturm": cauchy_sturm,
        "cauchy_violations_numpy": numpy_viol,
        "sturm_sign_disagreements": sign_disagree,
    }


def main():
    bad30, bad110 = part_formulas()
    trig = part_trig()
    periodic = part_periodic()
    poly = part_polynomials()
    formula_bad = bad30 + bad110
    trig_bad = (
        trig["pythagorean_disagreements"]
        + trig["half_grid_disagreements"]
        + trig["rule30_lift_disagreements"]
    )
    trig_amb = (
        trig["pythagorean_ambiguous"]
        + trig["half_grid_ambiguous"]
        + trig["rule30_lift_ambiguous"]
        + periodic["event_witness_ambiguous"]
    )
    periodic_bad = periodic["stepper_disagreements"] + periodic["pigeonhole_disagreements"]
    event_bad = periodic["event_witness_disagreements"]
    cauchy_bad = poly["cauchy_violations_sturm"] + poly["cauchy_violations_numpy"]
    sign_bad = poly["sturm_sign_disagreements"]
    # Branches are the ones written in result.json. An event-encoding failure
    # blocks support and is not the named refutation (formula or trigonometric
    # lift) and not the mixed branch (that branch requires E to pass).
    if trig_amb:
        verdict, confidence, reason = "inconclusive", 0.45, "other"
    elif formula_bad or trig_bad:
        verdict, confidence, reason = "refutes", 0.86, None
    elif periodic_bad or event_bad:
        verdict, confidence, reason = "inconclusive", 0.45, "other"
    elif cauchy_bad or sign_bad:
        verdict, confidence, reason = "mixed", 0.72, None
    else:
        verdict, confidence, reason = "supports", 0.90, None

    measured = {
        "value": formula_bad + trig_bad + periodic_bad + event_bad + cauchy_bad + sign_bad,
        "unit": "disagreements in the formula, trigonometric, periodic-event, and polynomial checks",
        "n": poly["n_polynomials"],
        "uncertainty": "exact on the integer checks; sine values use math.sin with the pre-registered bands",
        "extra": {
            "formula30_mismatches": bad30,
            "formula110_mismatches": bad110,
            **trig,
            **periodic,
            **poly,
            "cauchy_violations": cauchy_bad,
        },
    }
    method = (
        "analysis.py checks four frozen comparisons. The rule 30 and rule 110 bitwise formulas are "
        "compared with an independent truth-table scan for every integer from 0 through 65535, using "
        "neighborhood (bit k, bit k-1, bit k-2). The sine-squared lift of x^2+y^2=z^2 is evaluated on "
        "every integer triple from 0 through 30 and on the half-integer grid from 0 to 20, and the same "
        "lift is applied to one rule-30 step for every seed from 0 through 500. On a periodic ring of "
        "width 8, two steppers evolve rules 30 and 110 from every seed for 512 steps, and a sine-squared "
        "witness is plugged in whenever cell 0 becomes 1. Every polynomial of degree 1 through 5 with "
        "coefficients in -2..2 and nonzero leading coefficient is tested by an exact Sturm sequence: "
        "real roots strictly outside Cauchy's bound are counted by sign variations, and numpy.roots is "
        "applied with the pre-registered acceptance band. Criteria were frozen in commit "
        "093ca8002a77b774b469b965ff599d123fdaefbb before this run."
    )
    datasets = [{
        "id": "trig-integer-lift-and-eca-formula",
        "name": "Sine-squared lifts, rule 30 and rule 110 formulas, periodic rings, and the low-degree polynomial family, generated by analysis.py",
        "landing_url": "https://www.wolframscience.com/nks/p731--the-validity-of-the-principle/",
        "doi": None,
        "version": "generated",
        "license": None,
        "generator": "analysis.py",
        "program_family": (
            "rules 30 and 110; formulas a XOR ((a OR 2a)<<1) and (a AND 2a AND 4a) XOR (2a OR 4a); "
            "Pythagorean grid 0..30 and half-integer grid 0,0.5,..,20; periodic width 8; "
            "polynomials degree 1..5, coefficients -2..2"
        ),
        "files": [],
        "role": "the equations and automata compared in the test",
    }]
    caveats = [
        "The computation shows that these equations and automata agree as mathematics. It does not show that organisms follow the claim.",
        "The periodic ring makes 'does cell 0 ever become black' a question about an unbounded number of steps whose answer is settled by the pigeonhole principle within 256 states. It is not an infinite-line cellular automaton with an uncomputable limit.",
        "Cauchy's bound and Sturm's theorem are applied to one explicit family of low-degree univariate polynomials, which is the algebraic half of the claim on that family, not a survey of every polynomial equation.",
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
        json.dump({"verdict": verdict, "confidence": confidence, "measured": measured}, f, indent=2)
        f.write("\n")
    summary = {
        "verdict": verdict,
        "confidence": confidence,
        "formula30_mismatches": bad30,
        "formula110_mismatches": bad110,
        "trig_bad": trig_bad,
        "trig_amb": trig_amb,
        "periodic_bad": periodic_bad,
        "event_bad": event_bad,
        "cauchy_bad": cauchy_bad,
        "sign_bad": sign_bad,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
