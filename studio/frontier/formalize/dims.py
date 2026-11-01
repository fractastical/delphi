"""Dimension tracking over the seven SI base dimensions.  Pure exact integer arithmetic.

Units are parsed from a small closed table (SI base + a few named SI derived units); anything else is
refused rather than guessed (no prefixed units such as cm: the proposal must be stated in SI and say so).
Rules: + - and comparisons need equal dimensions; * adds, / by a constant keeps, pow multiplies.
A nonzero numeric literal is DIMENSIONLESS; the literal 0 is dimension-polymorphic.
"""
from __future__ import annotations

import re
from fractions import Fraction

BASE = ("kg", "m", "s", "A", "K", "mol", "cd")  # first three agree with engineering.constraints.BASE_UNITS
_DERIVED = {  # name -> exponent vector over BASE
    "N": (1, 1, -2, 0, 0, 0, 0), "Pa": (1, -1, -2, 0, 0, 0, 0), "J": (1, 2, -2, 0, 0, 0, 0),
    "W": (1, 2, -3, 0, 0, 0, 0), "Hz": (0, 0, -1, 0, 0, 0, 0), "C": (0, 0, 1, 1, 0, 0, 0),
    "V": (1, 2, -3, -1, 0, 0, 0),
}
_TOK = re.compile(r"^([A-Za-z]+)(\^(-?\d{1,2}))?$")


class UnitError(ValueError):
    pass


def _vec(name: str):
    if name in BASE:
        v = [0] * len(BASE)
        v[BASE.index(name)] = 1
        return tuple(v)
    if name in _DERIVED:
        return _DERIVED[name]
    raise UnitError(f"unit {name!r} is not in the closed table (SI base {BASE} and {sorted(_DERIVED)}); prefixed units are not supported")


def parse_unit(u: str) -> tuple:
    u = u.strip()
    if u in ("", "1"):
        return (0,) * len(BASE)
    num, _, den = u.partition("/")
    if "/" in den:
        raise UnitError("at most one '/' in a unit string")
    out = [0] * len(BASE)
    for part, sign in ((num, 1), (den, -1)):
        for tok in part.replace("*", " ").replace("·", " ").split():
            if tok == "1":
                continue
            m = _TOK.match(tok)
            if not m:
                raise UnitError(f"cannot parse unit token {tok!r}")
            v, e = _vec(m.group(1)), int(m.group(3) or 1)
            for i in range(len(out)):
                out[i] += sign * e * v[i]
    return tuple(out)


def fmt(d: tuple) -> str:
    parts = [(b, e) for b, e in zip(BASE, d) if e]
    return " ".join(b if e == 1 else f"{b}^{e}" for b, e in parts) or "1"


class DimError(Exception):
    pass


ANY = "ANY"  # dimension of the literal zero


def term_dim(term, sdim: dict, is_lit, lit_val):
    """Return a dimension tuple (or ANY) or raise DimError describing the first inconsistency."""
    zero = (0,) * len(BASE)
    if isinstance(term, dict):
        op = term["op"]
        if op in ("+", "-"):
            ds = [term_dim(a, sdim, is_lit, lit_val) for a in term["args"]]
            known = [d for d in ds if d != ANY]
            if known and any(d != known[0] for d in known):
                raise DimError(f"cannot {'add' if op == '+' else 'subtract'} [{fmt(known[0])}] and [{fmt(next(d for d in known if d != known[0]))}]")
            return known[0] if known else ANY
        if op == "*":
            r = zero
            for a in term["args"]:
                d = term_dim(a, sdim, is_lit, lit_val)
                if d == ANY:
                    return ANY if all(term_dim(b, sdim, is_lit, lit_val) == ANY or True for b in term["args"]) else d
                r = tuple(x + y for x, y in zip(r, d))
            return r
        if op == "/":
            return term_dim(term["args"][0], sdim, is_lit, lit_val)
        if op == "pow":
            d = sdim[term["base"]]
            return tuple(x * term["exp"] for x in d)
    if is_lit(term):
        return ANY if lit_val(term) == 0 else zero
    return sdim[term]


def constraint_dim(expr: dict, sdim: dict, is_lit, lit_val) -> tuple:
    """Dimension of a comparison: both sides must agree. Raises DimError with both sides' dimensions."""
    l = term_dim(expr["lhs"], sdim, is_lit, lit_val)
    r = term_dim(expr["rhs"], sdim, is_lit, lit_val)
    if l != ANY and r != ANY and l != r:
        raise DimError(f"lhs has dimension [{fmt(l)}] but rhs has [{fmt(r)}]")
    d = l if l != ANY else r
    return (0,) * len(BASE) if d == ANY else d
