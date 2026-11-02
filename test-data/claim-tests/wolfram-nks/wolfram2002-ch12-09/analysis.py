#!/usr/bin/env python3
"""Trigonometric encoding of an unbounded cyclic elementary-CA question,
and a Sturm decision procedure for a box of pure polynomials
(wolfram2002-ch12-09). Writes derived/measured.json.
"""
import itertools
import json
import math
import os
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
W = 5
B = 1 << W
RULES = (0, 90, 110, 204)


def step_int(rule, c):
    out = 0
    for i in range(W):
        left = (c >> ((i + 1) % W)) & 1
        center = (c >> i) & 1
        right = (c >> ((i - 1) % W)) & 1
        nb = (left << 2) | (center << 1) | right
        out |= ((rule >> nb) & 1) << i
    return out


def step_array(rule, bits):
    out = []
    for i in range(W):
        left = bits[(i + 1) % W]
        center = bits[i]
        right = bits[(i - 1) % W]
        nb = (left << 2) | (center << 1) | right
        out.append((rule >> nb) & 1)
    return out


def bits_of(c):
    return [(c >> i) & 1 for i in range(W)]


def int_of(bits):
    v = 0
    for i, b in enumerate(bits):
        v |= b << i
    return v


def self_check():
    # Known Sturm counts, used to catch an isolator that steps over a root.
    known = {
        (-2, 0, 1): 2,       # x^2 - 2
        (1, 0, 1): 0,        # x^2 + 1
        (1, -2, 1): 1,       # (x-1)^2, one distinct root
        (0, -1, 0, 1): 3,    # x^3 - x
        (1,): 0,             # nonzero constant
    }
    assert sturm_real_roots((0, 0, 0, 0, 0)) is None
    assert isolate_count((0, 0, 0, 0, 0)) is None
    for coefs, nroots in known.items():
        assert sturm_real_roots(coefs) == nroots
        assert isolate_count(coefs) == nroots
    # rule 90 is left XOR right; rule 204 is the centre bit; rule 110 is the standard table.
    assert step_int(0, 0b11111) == 0
    for c in range(B):
        assert step_int(204, c) == c
        bits = bits_of(c)
        expect = []
        for i in range(W):
            left = bits[(i + 1) % W]
            right = bits[(i - 1) % W]
            expect.append(left ^ right)
        assert step_int(90, c) == int_of(expect)
        assert step_array(90, bits) == expect
    table110 = {(1, 1, 1): 0, (1, 1, 0): 1, (1, 0, 1): 1, (1, 0, 0): 0,
                (0, 1, 1): 1, (0, 1, 0): 1, (0, 0, 1): 1, (0, 0, 0): 0}
    for p, q, r in itertools.product((0, 1), repeat=3):
        nb = (p << 2) | (q << 1) | r
        assert ((110 >> nb) & 1) == table110[(p, q, r)]


def first_hit(rule, c):
    """Return (t, rows) for the first zero row, or (None, rows of the cycle prefix)."""
    seen = {}
    rows = []
    state = c
    for t in range(B + 1):
        if state in seen:
            return None, rows
        rows.append(state)
        if state == 0:
            return t, rows
        seen[state] = t
        nxt = step_int(rule, state)
        bits = step_array(rule, bits_of(state))
        if int_of(bits) != nxt:
            raise RuntimeError("steppers disagree")
        state = nxt
    raise RuntimeError("pigeonhole failed")


def history_integer(rows):
    h = 0
    for k, r in enumerate(rows):
        h += r * (B ** k)
    return h


def residuals_zero(rule, c, t, h):
    if t == 0:
        return c == 0 and h == 0
    if h < 0 or t < 0:
        return False
    digits = []
    x = h
    for _ in range(t + 1):
        digits.append(x % B)
        x //= B
    if x != 0 or len(digits) != t + 1:
        return False
    if digits[0] != c or digits[t] != 0:
        return False
    if any(digits[k] == 0 for k in range(t)):
        return False
    for k in range(t):
        if step_int(rule, digits[k]) != digits[k + 1]:
            return False
    return True


# ---------------------------------------------------------------- polynomials
def trim(p):
    a = list(p)
    while len(a) > 1 and a[-1] == 0:
        a.pop()
    return a


def deriv(p):
    return trim([p[i] * i for i in range(1, len(p))]) or [Fraction(0)]


def pmod(a, b):
    a = trim([Fraction(c) for c in a])
    b = trim([Fraction(c) for c in b])
    if b == [Fraction(0)]:
        raise ZeroDivisionError
    while len(a) >= len(b) and a != [Fraction(0)]:
        shift = len(a) - len(b)
        factor = a[-1] / b[-1]
        for i, coef in enumerate(b):
            a[i + shift] -= factor * coef
        a = trim(a)
    return a


def pdiv_quot(a, b):
    a = trim([Fraction(c) for c in a])
    b = trim([Fraction(c) for c in b])
    q = [Fraction(0)] * max(1, len(a) - len(b) + 1)
    if a == [Fraction(0)]:
        return [Fraction(0)]
    while len(a) >= len(b) and a != [Fraction(0)]:
        shift = len(a) - len(b)
        factor = a[-1] / b[-1]
        q[shift] = factor
        for i, coef in enumerate(b):
            a[i + shift] -= factor * coef
        a = trim(a)
    return trim(q)


def pgcd(a, b):
    a, b = trim(a), trim(b)
    while b != [Fraction(0)]:
        a, b = b, pmod(a, b)
    return trim(a)


def square_free(p):
    p = trim([Fraction(c) for c in p])
    if p == [Fraction(0)] or len(p) == 1:
        return p
    g = pgcd(p, deriv(p))
    if g == [Fraction(1)] or (len(g) == 1 and g[0] != 0):
        # divide by content-like gcd; if gcd is constant, p is square-free
        if len(g) == 1:
            return trim([c / g[0] for c in p])
    q = pdiv_quot(p, g)
    lead = q[-1]
    return trim([c / lead for c in q])


def eval_poly(p, x):
    y = Fraction(0)
    power = Fraction(1)
    x = Fraction(x)
    for c in p:
        y += c * power
        power *= x
    return y


def sign_changes(vals):
    prev = 0
    n = 0
    for v in vals:
        if v == 0:
            continue
        s = 1 if v > 0 else -1
        if prev and s != prev:
            n += 1
        prev = s
    return n


def sturm_seq(p):
    p = trim([Fraction(c) for c in p])
    s0 = p
    s1 = deriv(p)
    seq = [s0]
    if s1 == [Fraction(0)]:
        return seq
    seq.append(s1)
    while True:
        rem = pmod(seq[-2], seq[-1])
        nxt = trim([-c for c in rem])
        if nxt == [Fraction(0)]:
            break
        seq.append(nxt)
        if len(seq) > len(p) + 2:
            break
    return seq


def var_inf(seq, positive):
    vals = []
    for s in seq:
        s = trim(s)
        lead = s[-1]
        deg = len(s) - 1
        vals.append(lead if positive or deg % 2 == 0 else -lead)
    return sign_changes(vals)


def var_at(seq, x):
    return sign_changes([eval_poly(s, x) for s in seq])


def sturm_real_roots(p):
    """Number of distinct real roots. The zero polynomial returns None."""
    raw = trim([Fraction(c) for c in p])
    if raw == [Fraction(0)]:
        return None
    sf = square_free(raw)
    if len(sf) == 1:
        return 0
    seq = sturm_seq(sf)
    return var_inf(seq, False) - var_inf(seq, True)


def _bracket_root(sf, seq, root, a, b):
    """Return (left, right) with a < left < root < right < b, the polynomial
    nonzero at both ends, and exactly one root in (left, right): the root
    already found at `root`. Shrinking until the Sturm variation is 1 keeps
    the split from jumping over a nearby root.
    """
    sl = (root - a) / 2
    sr = (b - root) / 2
    for _ in range(80):
        left = root - sl
        right = root + sr
        if left <= a or right >= b:
            sl /= 2
            sr /= 2
            continue
        if eval_poly(sf, left) == 0 or eval_poly(sf, right) == 0:
            sl /= 2
            sr /= 2
            continue
        if var_at(seq, left) - var_at(seq, right) == 1:
            return left, right
        sl /= 2
        sr /= 2
    raise RuntimeError("could not separate a root")


def isolate_count(p):
    raw = trim([Fraction(c) for c in p])
    if raw == [Fraction(0)]:
        return None
    sf = square_free(raw)
    if len(sf) == 1:
        return 0
    seq = sturm_seq(sf)
    lead = abs(sf[-1])
    radius = 1 + max((abs(c) / lead for c in sf[:-1]), default=Fraction(0))
    lo = -(radius + 1)
    hi = radius + 1

    found = 0
    if eval_poly(sf, lo) == 0:
        found += 1
        _, lo = _bracket_root(sf, seq, lo, lo - 1, hi)
    if eval_poly(sf, hi) == 0:
        found += 1
        hi, _ = _bracket_root(sf, seq, hi, lo, hi + 1)
    stack = [(lo, hi)]
    guard = 0
    while stack:
        a, b = stack.pop()
        guard += 1
        if guard > 20000:
            raise RuntimeError("isolation did not finish")
        if eval_poly(sf, a) == 0 or eval_poly(sf, b) == 0:
            raise RuntimeError("endpoint landed on a root")
        count = var_at(seq, a) - var_at(seq, b)
        if count <= 0:
            continue
        mid = (a + b) / 2
        if eval_poly(sf, mid) == 0:
            found += 1
            left, right = _bracket_root(sf, seq, mid, a, b)
            stack.append((a, left))
            stack.append((right, b))
            continue
        if count == 1 and b - a < Fraction(1, 1 << 20):
            found += 1
            continue
        stack.append((a, mid))
        stack.append((mid, b))
    return found


def polynomial_box():
    disagree = 0
    n = 0
    zero = 0
    root_total = 0
    for coefs in itertools.product((-1, 0, 1), repeat=5):
        n += 1
        p = list(coefs)
        s = sturm_real_roots(p)
        iso = isolate_count(p)
        if s is None:
            zero += 1
            if iso is not None:
                disagree += 1
            continue
        root_total += s
        if s != iso:
            disagree += 1
    return {"polynomials": n, "identically_zero": zero, "disagreements": disagree,
            "distinct_real_roots_sum": root_total}


def separation():
    # x^2 - 2. Rational root candidates ±1, ±2.
    vals = {c: c * c - 2 for c in (-2, -1, 1, 2)}
    integer_roots = [c for c, v in vals.items() if v == 0]
    sturm = sturm_real_roots([-2, 0, 1])
    return {
        "polynomial": "x^2 - 2",
        "sturm_real_roots": sturm,
        "rational_root_candidates_that_vanish": integer_roots,
        "trig_equation_sin2_plus_poly2_has_real_solution": False if sturm == 2 and not integer_roots else True,
        "pure_polynomial_has_real_solution": sturm > 0,
    }


def float_sin_crosscheck():
    worst = 0.0
    for n in range(1001):
        worst = max(worst, abs(math.sin(math.pi * n)))
    return {"n_max": 1000, "max_abs_math_sin_pi_n": worst, "sin_pi_half": math.sin(math.pi / 2)}


def main():
    self_check()
    mismatches = 0
    stepper_disagreements = 0
    by_rule = {}
    hit = 0
    instances = 0
    for rule in RULES:
        died = 0
        for c in range(B):
            instances += 1
            try:
                t, rows = first_hit(rule, c)
            except RuntimeError:
                stepper_disagreements += 1
                mismatches += 1
                continue
            if t is None:
                # the only digit history allowed by the step relation is `rows` followed
                # by further steps; none of the first B+1 rows is zero, and the state repeated.
                for tt in range(len(rows)):
                    h = history_integer(rows[: tt + 1])
                    if residuals_zero(rule, c, tt, h) and rows[tt] == 0:
                        mismatches += 1
                continue
            died += 1
            hit += 1
            h = history_integer(rows)
            if not residuals_zero(rule, c, t, h):
                mismatches += 1
            # a non-integer t is excluded by sin(pi*t)=0; recorded as the identity, not a float.
            if t != int(t) or h != int(h):
                mismatches += 1
        by_rule[str(rule)] = {"died": died, "never": B - died}
    box = polynomial_box()
    sep = separation()
    measured = {
        "width": W,
        "instances": instances,
        "hit_zero": hit,
        "mismatches": mismatches,
        "stepper_disagreements": stepper_disagreements,
        "by_rule": by_rule,
        "polynomial_box": box,
        "separation": sep,
        "float_sin_crosscheck": float_sin_crosscheck(),
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump(measured, f, indent=2)
        f.write("\n")
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
