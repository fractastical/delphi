"""Exact satisfiability checking for a validated proposal.

What is exact and what is not (stated in every response):
  * `sat` is ONLY reported with a rational witness that was re-evaluated in `fractions.Fraction` against every
    constraint and every declared domain by code independent of the search (`check_point`).
  * `unsat` is ONLY reported by (a) exact interval-arithmetic refutation over the declared box (a sound
    over-approximation: a hull that excludes the truth set proves infeasibility), (b) exhaustive enumeration of
    a small finite integer box, or (c) z3 (nlsat) when importable -- (c) is a solver verdict with no proof object
    and is labelled `independent_check: none`.
  * everything else is `unknown`.  We never guess.
"""
from __future__ import annotations

import itertools
import time
from fractions import Fraction

from .grammar import COMPARISONS, Poly, to_poly

MAX_COMBOS = 20000
ENUM_LIMIT = 200000


def holds(op: str, v: Fraction) -> bool:
    return {"<": v < 0, "<=": v <= 0, ">": v > 0, ">=": v >= 0, "==": v == 0}[op]


def in_domain(sym: dict, x: Fraction) -> bool:
    if sym["lo"] is not None and (x < sym["lo"] or (sym["lo_open"] and x == sym["lo"])):
        return False
    if sym["hi"] is not None and (x > sym["hi"] or (sym["hi_open"] and x == sym["hi"])):
        return False
    if sym["integer"] and x.denominator != 1:
        return False
    return True


class Model:
    def __init__(self, ctx: dict):
        self.names = ctx["names"]
        self.index = {n: i for i, n in enumerate(self.names)}
        self.syms = [ctx["symbols"][n] for n in self.names]
        self.cons = []  # (id, op, Poly lhs-rhs)
        for c in ctx["constraints"]:
            e = c["expr"]
            p = to_poly(e["lhs"], self.index) - to_poly(e["rhs"], self.index)
            self.cons.append((c["id"], e["op"], p))

    def violations(self, pt: list) -> list:
        """Independent exact check of a point against domains and constraints. [] means it satisfies all."""
        bad = [f"domain:{n}" for n, s, x in zip(self.names, self.syms, pt) if not in_domain(s, x)]
        bad += [cid for cid, op, p in self.cons if not holds(op, p.eval(pt))]
        return bad


# ---------------------------------------------------------------- interval arithmetic (exact, sound)
class Iv:
    """Closed interval with optional infinite ends, endpoints Fraction or +-inf (float inf only for ends)."""
    __slots__ = ("lo", "hi")
    NINF, PINF = float("-inf"), float("inf")

    def __init__(self, lo, hi):
        self.lo, self.hi = lo, hi

    def __add__(self, o):
        return Iv(self.lo + o.lo, self.hi + o.hi)

    def __mul__(self, o):
        ps = [_im(a, b) for a in (self.lo, self.hi) for b in (o.lo, o.hi)]
        return Iv(min(ps), max(ps))


def _im(a, b):
    if a == 0 or b == 0:
        return Fraction(0)
    return a * b


def iv_pow(x: Iv, e: int) -> Iv:
    if e == 0:
        return Iv(Fraction(1), Fraction(1))
    r = x
    for _ in range(e - 1):
        r = r * x
    if e % 2 == 0:
        # even power: tighten using sign knowledge (x*x loses x == x correlation)
        if x.lo >= 0:
            return Iv(x.lo ** e, x.hi ** e if x.hi != Iv.PINF else Iv.PINF)
        if x.hi <= 0:
            return Iv(x.hi ** e, x.lo ** e if x.lo != Iv.NINF else Iv.PINF)
        top = max(abs(x.lo) if x.lo != Iv.NINF else Iv.PINF, abs(x.hi) if x.hi != Iv.PINF else Iv.PINF)
        return Iv(Fraction(0), top ** e if top != Iv.PINF else Iv.PINF)
    return r


def poly_range(p: Poly, boxes: list) -> Iv:
    total = Iv(Fraction(0), Fraction(0))
    for k, c in p.t.items():
        m = Iv(Fraction(c), Fraction(c))
        for i, e in enumerate(k):
            if e:
                m = m * iv_pow(boxes[i], e)
        total = total + m
    return total


def boxes_of(model: Model) -> list:
    out = []
    for s in model.syms:
        lo = s["lo"] if s["lo"] is not None else Iv.NINF
        hi = s["hi"] if s["hi"] is not None else Iv.PINF
        out.append(Iv(lo, hi))
    return out


def interval_refutation(model: Model):
    """Return the id of a constraint that cannot hold anywhere in the declared box, else None."""
    bx = boxes_of(model)
    for cid, op, p in model.cons:
        try:
            r = poly_range(p, bx)
        except (ArithmeticError, ValueError):
            continue
        lo, hi = r.lo, r.hi
        if (op == "<" and lo >= 0) or (op == "<=" and lo > 0) or (op == ">" and hi <= 0) or (op == ">=" and hi < 0) \
                or (op == "==" and (lo > 0 or hi < 0)):
            return cid, (str(lo), str(hi))
    return None


# ---------------------------------------------------------------- witness search
def candidates(s: dict) -> list:
    lo, hi = s["lo"], s["hi"]
    out = []
    if lo is not None and hi is not None:
        w = hi - lo
        pts = [lo, hi, lo + w / 2, lo + w / 4, lo + 3 * w / 4, lo + w / 10, lo + 9 * w / 10, lo + w / 100,
               lo + w / 1000, lo + w / 10**4, lo + w / 10**5, lo + w / 10**6]   # fine points near the low end: products of small positive quantities
        if lo < 0 < hi:
            pts.append(Fraction(0))
    elif lo is not None:
        base = abs(lo) if lo != 0 else Fraction(1)
        pts = [lo, lo + base, lo + 2 * base, lo + 10 * base, lo + Fraction(1, 2), lo + 1]
    elif hi is not None:
        base = abs(hi) if hi != 0 else Fraction(1)
        pts = [hi, hi - base, hi - 2 * base, hi - 10 * base, hi - Fraction(1, 2), hi - 1]
    else:
        pts = [Fraction(x) for x in (0, 1, -1, 2, 1, Fraction(1, 2), 10)]
    if s["integer"]:
        import math
        pts = [Fraction(math.floor(x)) for x in pts] + [Fraction(math.ceil(x)) for x in pts]
        if lo is not None and hi is not None and hi - lo <= 60:
            a = math.ceil(lo); b = math.floor(hi)
            pts += [Fraction(i) for i in range(a, b + 1)]
    seen, res = set(), []
    for x in pts:
        if x not in seen and in_domain(s, x):
            seen.add(x)
            res.append(x)
    return res


def _solve_for(p: Poly, i: int, pt: list):
    """If p is linear in variable i, return the value of x_i with p == 0 given the other coordinates in pt."""
    a = Fraction(0); b = Fraction(0)
    for k, c in p.t.items():
        rest = c
        for j, e in enumerate(k):
            if j != i and e:
                if pt[j] is None:
                    return None
                rest *= pt[j] ** e
        if k[i] == 0:
            b += rest
        elif k[i] == 1:
            a += rest
        else:
            return None
    return None if a == 0 else -b / a


def witness_search(model: Model, deadline: float):
    n = len(model.names)
    eqs = [(cid, p) for cid, op, p in model.cons if op == "=="]
    # plan: greedily pick, for each equality, a variable to eliminate by solving (linear in it)
    solved, plan = set(), []
    for cid, p in eqs:
        for i in range(n):
            if i in solved or p.degree_in(i) != 1 or model.syms[i]["integer"]:
                continue
            solved.add(i)
            plan.append((i, p))
            break
    free = [i for i in range(n) if i not in solved]
    cand = [candidates(model.syms[i]) for i in free]
    if any(not c for c in cand):
        return None, 0
    combos = 1
    for c in cand:
        combos *= len(c)
    tried = 0
    for choice in itertools.product(*cand):
        tried += 1
        if tried > MAX_COMBOS or time.monotonic() > deadline:
            break
        pt = [None] * n
        for i, v in zip(free, choice):
            pt[i] = v
        # resolve the eliminated variables in dependency order: an equality may need a variable another equality solves for
        pending, ok = list(plan), True
        while pending and ok:
            progressed = False
            for item in list(pending):
                v = _solve_for(item[1], item[0], pt)
                if v is not None:
                    pt[item[0]] = v
                    pending.remove(item)
                    progressed = True
            if not progressed:
                ok = False
        if ok and not model.violations(pt):
            return pt, tried
    return None, tried


def enumerate_integers(model: Model):
    """Exhaustive search when every symbol is an integer in a finite box of size <= ENUM_LIMIT."""
    import math
    rng = []
    size = 1
    for s in model.syms:
        if not s["integer"] or s["lo"] is None or s["hi"] is None:
            return None
        a, b = math.ceil(s["lo"]), math.floor(s["hi"])
        r = [Fraction(i) for i in range(a, b + 1) if in_domain(s, Fraction(i))]
        rng.append(r)
        size *= max(len(r), 1)
        if size > ENUM_LIMIT:
            return None
    for pt in itertools.product(*rng):
        if not model.violations(list(pt)):
            return list(pt), size
    return None, size


# ---------------------------------------------------------------- z3 (optional)
def z3_check(model: Model, timeout_ms: int):
    try:
        import z3
    except Exception:  # noqa: BLE001
        return "unavailable", None
    xs = [z3.Int(n) if s["integer"] else z3.Real(n) for n, s in zip(model.names, model.syms)]

    def zp(p: Poly):
        tot = z3.RealVal(0) if not any(s["integer"] for s in model.syms) else 0
        expr = None
        for k, c in p.t.items():
            m = z3.RealVal(f"{c.numerator}/{c.denominator}")
            for x, e in zip(xs, k):
                for _ in range(e):
                    m = m * x
            expr = m if expr is None else expr + m
        return expr if expr is not None else z3.RealVal(0)

    s = z3.Solver()
    s.set("timeout", timeout_ms)
    for x, sy in zip(xs, model.syms):
        if sy["lo"] is not None:
            v = z3.RealVal(f"{sy['lo'].numerator}/{sy['lo'].denominator}")
            s.add(x > v if sy["lo_open"] else x >= v)
        if sy["hi"] is not None:
            v = z3.RealVal(f"{sy['hi'].numerator}/{sy['hi'].denominator}")
            s.add(x < v if sy["hi_open"] else x <= v)
    for cid, op, p in model.cons:
        e = zp(p)
        s.add({"<": e < 0, "<=": e <= 0, ">": e > 0, ">=": e >= 0, "==": e == 0}[op])
    r = s.check()
    if r == z3.unsat:
        return "unsat", None
    if r == z3.sat:
        m = s.model()
        pt = []
        for x in xs:
            v = m.eval(x, model_completion=True)
            if z3.is_int_value(v):
                pt.append(Fraction(v.as_long()))
            elif z3.is_rational_value(v):
                pt.append(Fraction(v.numerator_as_long(), v.denominator_as_long()))
            else:
                return "sat-irrational", None
        return "sat", pt
    return "unknown", None


def check(model: Model, timeout_s: float = 6.0) -> dict:
    """One satisfiability record for the conjunction of all constraints and declared domains."""
    t0 = time.monotonic()
    deadline = t0 + timeout_s
    if not model.cons:
        return {"constraint": "ALL", "result": "unknown", "method": "none", "independent_check": "none", "note": "no constraints"}
    ref = interval_refutation(model)
    if ref:
        return {"constraint": "ALL", "result": "unsat", "method": "interval-arithmetic (exact Fractions, sound over-approximation)",
                "independent_check": "ok", "refuted_by": ref[0], "range_of_lhs_minus_rhs": list(ref[1])}
    en = enumerate_integers(model)
    if en is not None:
        pt, size = en
        if pt is not None:
            return _sat(model, pt, "enumeration", {"enumerated_box_size": size})
        return {"constraint": "ALL", "result": "unsat", "method": "enumeration", "independent_check": "ok",
                "enumerated_box_size": size, "note": "exhaustive over the finite integer box"}
    pt, tried = witness_search(model, deadline)
    if pt is not None:
        return _sat(model, pt, "exact-rational (candidate search + linear solve)", {"candidates_tried": tried})
    zr, zpt = z3_check(model, int(max(0.5, deadline - time.monotonic()) * 1000))
    if zr == "sat" and zpt is not None and not model.violations(zpt):
        return _sat(model, zpt, "z3 (nlsat) model, re-checked exactly", {})
    if zr == "unsat":
        return {"constraint": "ALL", "result": "unsat", "method": "z3 (nlsat)", "independent_check": "none",
                "note": "z3 verdict only; no proof object and not re-derived independently"}
    why = {"unavailable": "z3 not importable in the worker; exact search found no witness and no refutation",
           "sat-irrational": "z3 found only an irrational model; no exact rational point passed the exact check"}.get(
        zr, "no witness found and no refutation within limits")
    return {"constraint": "ALL", "result": "unknown", "method": "exact-rational search + interval arithmetic", "independent_check": "none",
            "note": why, "candidates_tried": tried}


def _sat(model, pt, method, extra):
    bad = model.violations(pt)
    if bad:  # defensive: never report an unchecked witness
        return {"constraint": "ALL", "result": "unknown", "method": method, "independent_check": "none",
                "note": f"internal inconsistency: witness failed independent re-check on {bad}"}
    return {"constraint": "ALL", "result": "sat", "method": method, "independent_check": "ok",
            "witness": {n: str(x) for n, x in zip(model.names, pt)}, **extra}
