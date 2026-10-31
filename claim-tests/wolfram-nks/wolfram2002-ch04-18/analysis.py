#!/usr/bin/env python3
"""Test of wolfram2002-ch04-18: axis crossings of sin(x) + sin(a x) versus the
continued-fraction-driven generalized substitution system.

Everything is generated here; no download. Writes derived/measurements.json.
"""
import json
import math
import os
import sys
from fractions import Fraction

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
N_CROSSINGS = 20000
SUB_LEN = 200000
MAX_FACTOR = 24
TIE_TOL = 1e-9
ZERO_TOL = 1e-8


# ---------------------------------------------------------------- exact surds
class Surd:
    """a + b*sqrt(d) with a, b rational, d a positive non-square integer."""

    def __init__(self, a, b, d):
        self.a, self.b, self.d = Fraction(a), Fraction(b), int(d)

    def value(self):
        return float(self.a) + float(self.b) * math.sqrt(self.d)

    def key(self):
        return (self.a, self.b, self.d)

    def __sub__(self, n):
        return Surd(self.a - n, self.b, self.d)

    def __add__(self, n):
        return Surd(self.a + n, self.b, self.d)

    def mul(self, other):
        return Surd(self.a * other.a + self.b * other.b * self.d, self.a * other.b + self.b * other.a, self.d)

    def inv(self):
        den = self.a * self.a - self.b * self.b * self.d  # (a + b r)(a - b r)
        return Surd(self.a / den, -self.b / den, self.d)

    def div(self, other):
        return self.mul(other.inv())

    def is_nonneg(self):
        # a + b sqrt(d) >= 0 exactly
        if self.b == 0:
            return self.a >= 0
        if self.a >= 0 and self.b >= 0:
            return True
        if self.a < 0 and self.b < 0:
            return False
        # opposite signs: compare a^2 and b^2 d
        if self.a >= 0:  # b < 0
            return self.a * self.a >= self.b * self.b * self.d
        return self.b * self.b * self.d >= self.a * self.a  # a < 0, b > 0

    def floor(self):
        n = math.floor(self.value())
        for cand in (n - 1, n, n + 1):
            if (self - cand).is_nonneg() and not (self - (cand + 1)).is_nonneg():
                return cand
        raise ArithmeticError("floor failed")


def cf_exact_surd(theta, max_terms=60):
    """Continued fraction of a quadratic surd in (0,1) with exact period detection.
    Returns (terms, preperiod_length, period_length)."""
    terms = []
    seen = {}
    x = theta
    for i in range(max_terms):
        k = x.key()
        if k in seen:
            start = seen[k]
            return terms, start, i - start
        seen[k] = i
        x = x.inv()
        c = x.floor()
        terms.append(c)
        x = x - c
    return terms, None, None


def cf_float(theta, max_den):
    """Partial quotients of a float's exact rational value, stopping once the convergent
    denominator exceeds max_den (beyond which double precision is not trusted)."""
    fr = Fraction(theta)
    terms = []
    q_prev, q = 0, 1
    x = fr
    # integer part is 0
    x = x - math.floor(x)
    while True:
        if x == 0:
            break
        x = 1 / x
        c = math.floor(x)
        q_prev, q = q, c * q + q_prev
        terms.append(c)
        if q > max_den:
            break
        x = x - c
    return terms


# ----------------------------------------------------------- substitution word
def substitution_word(terms, length):
    """s_{-1} = B, s_0 = A, s_1 = A^{c1} B, s_n = s_{n-1}^{c_n} s_{n-2}."""
    s_prev, s = "B", "A"
    for i, c in enumerate(terms):
        s_prev, s = s, s * c + s_prev
        if len(s) >= length:
            break
    return s[:length], i + 1


def tau(c, w):
    return "".join(("A" * c + "B") if ch == "A" else "A" for ch in w)


def composition_word(terms, length):
    """tau_{c1} o tau_{c2} o ... o tau_{cn}(A); same limit as substitution_word."""
    w = "A"
    for c in reversed(terms):
        w = tau(c, w)
    return w[:length]


def factor_sets(w, nmax):
    return [set(w[i:i + n] for i in range(len(w) - n + 1)) for n in range(1, nmax + 1)]


# -------------------------------------------------------------- the crossings
def crossing_word(a, n_cross):
    d_a = 2 * math.pi / (1 + a)
    d_b = 2 * math.pi / (a - 1)
    ka = np.arange(1, int(n_cross) + 2)
    za = ka * d_a
    mb = np.arange(0, int(n_cross * d_a / d_b) + 3)
    zb = (2 * mb + 1) * math.pi / (a - 1)
    x = np.concatenate([za, zb])
    lab = np.concatenate([np.zeros(len(za), dtype=np.uint8), np.ones(len(zb), dtype=np.uint8)])
    order = np.argsort(x, kind="stable")
    x, lab = x[order][:n_cross], lab[order][:n_cross]
    f = np.sin(x) + np.sin(a * x)
    gaps = np.diff(x)
    return {
        "word": "".join("AB"[v] for v in lab),
        "max_abs_f_at_zeros": float(np.max(np.abs(f))),
        "min_gap_over_dA": float(gaps.min() / d_a),
        "frac_B": float(lab.mean()),
    }


def main():
    rng = np.random.default_rng(20261031)
    cases = [
        ("sqrt2", Surd(0, 1, 2)), ("sqrt3", Surd(0, 1, 3)), ("sqrt5", Surd(0, 1, 5)), ("sqrt7", Surd(0, 1, 7)),
        ("(1+sqrt5)/2", Surd(Fraction(1, 2), Fraction(1, 2), 5)), ("1+sqrt2", Surd(1, 1, 2)), ("2+sqrt3", Surd(2, 1, 3)),
        ("pi", math.pi), ("e", math.e), ("2^(1/3)", 2 ** (1 / 3)), ("ln10", math.log(10)),
    ] + [(f"random{i}", float(v)) for i, v in enumerate(rng.uniform(1.05, 12, 20))]

    results = []
    for name, alpha in cases:
        quad = isinstance(alpha, Surd)
        a = alpha.value() if quad else alpha
        theta = (a - 1) / (a + 1)
        rec = {"a_name": name, "a": a, "theta": theta, "quadratic": quad}
        if quad:
            th = (alpha - 1).div(alpha + 1)
            terms, pre, per = cf_exact_surd(th)
            rec.update({"cf_terms": terms, "cf_preperiod": pre, "cf_period": per})
            terms_float = cf_float(theta, 10 * N_CROSSINGS)
            if per:
                # the exact routine returns preperiod + one period; unroll the period
                terms = terms[:pre] + terms[pre:pre + per] * (1 + 200 // per)
            rec["cf_float_agrees_on_used_terms"] = terms[:len(terms_float)] == terms_float[:len(terms)]
        else:
            terms = cf_float(theta, 10 * N_CROSSINGS)
            rec.update({"cf_terms": terms, "cf_preperiod": None, "cf_period": None})
        rec["n_cf_terms_available"] = len(terms)

        cw = crossing_word(a, N_CROSSINGS)
        sw, used = substitution_word(terms, SUB_LEN)
        comp = composition_word(terms[:used], min(len(sw), 5000))
        rec["composition_form_agrees"] = sw.startswith(comp)
        rec["cf_terms_used"] = used
        rec["sub_word_len"] = len(sw)
        rec.update({k: v for k, v in cw.items() if k != "word"})

        fw = factor_sets(cw["word"], MAX_FACTOR)
        fs = factor_sets(sw, MAX_FACTOR)
        rec["factor_counts_crossings"] = [len(s) for s in fw]
        rec["factor_counts_substitution"] = [len(s) for s in fs]
        rec["factor_sets_equal_all_n"] = all(x == y for x, y in zip(fw, fs))
        rec["sturmian_complexity"] = all(len(s) == n + 1 for n, s in enumerate(fw, start=1))
        rec["first_mismatch_n"] = next((n for n, (x, y) in enumerate(zip(fw, fs), start=1) if x != y), None)
        rec["tie_suspected"] = cw["min_gap_over_dA"] < TIE_TOL

        if quad and rec["cf_period"]:
            pre, per = rec["cf_preperiod"], rec["cf_period"]
            # tail word u: generated from the periodic part alone; sigma = composite over one period
            tail_terms = (terms[pre:pre + per]) * 40
            u, _ = substitution_word(tail_terms, SUB_LEN)

            def sigma(w):
                for c in reversed(terms[pre:pre + per]):
                    w = tau(c, w)
                return w

            img = sigma(u[:2000])
            rec["tail_is_fixed_point_of_period_substitution"] = u.startswith(img) and len(img) > 2000
            # and the full word is the preperiod substitutions applied to the tail
            pref = u[:5000]
            for c in reversed(terms[:pre]):
                pref = tau(c, pref)
            rec["word_equals_preperiod_applied_to_tail"] = sw.startswith(pref[:min(len(pref), len(sw))])
        results.append(rec)
        print(f"{name:12s} a={a:.6f} theta={theta:.6f} cf={terms[:8]}{'...' if len(terms) > 8 else ''} "
              f"equal={rec['factor_sets_equal_all_n']} sturmian={rec['sturmian_complexity']} "
              f"maxf={cw['max_abs_f_at_zeros']:.1e} mingap/dA={cw['min_gap_over_dA']:.2e}", flush=True)

    n_cases = len(results)
    n_equal = sum(r["factor_sets_equal_all_n"] for r in results)
    n_sturm = sum(r["sturmian_complexity"] for r in results)
    quads = [r for r in results if r["quadratic"]]
    n_quad_periodic = sum(r["cf_period"] is not None for r in quads)
    n_quad_fixed = sum(bool(r.get("tail_is_fixed_point_of_period_substitution")) for r in quads)
    n_quad_pre = sum(bool(r.get("word_equals_preperiod_applied_to_tail")) for r in quads)
    max_f = max(r["max_abs_f_at_zeros"] for r in results)
    ties = sum(r["tie_suspected"] for r in results)
    summary = {
        "n_cases": n_cases, "n_factor_sets_equal_all_n": n_equal, "n_sturmian_complexity": n_sturm,
        "n_quadratic": len(quads), "n_quadratic_cf_eventually_periodic": n_quad_periodic,
        "n_quadratic_tail_fixed_point": n_quad_fixed, "n_quadratic_word_equals_preperiod_applied_to_tail": n_quad_pre,
        "max_abs_f_at_zeros": max_f, "n_tie_suspected": ties,
        "n_composition_form_agrees": sum(r["composition_form_agrees"] for r in results),
    }
    passed = (n_equal == n_cases and n_sturm == n_cases and n_quad_periodic == len(quads)
              and n_quad_fixed == len(quads) and max_f <= ZERO_TOL)
    failed = any((not r["factor_sets_equal_all_n"]) and not r["tie_suspected"] for r in results) or n_quad_periodic < len(quads) or n_quad_fixed < len(quads)
    verdict = "supports" if passed else ("refutes" if failed else "mixed")
    summary["verdict"] = verdict
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measurements.json"), "w") as f:
        json.dump({"summary": summary, "cases": results}, f, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    sys.exit(main())
