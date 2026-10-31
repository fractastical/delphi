"""Generate (never run) a PARAMETERIZED Lean 4 + Mathlib theorem from a validated proposal.

Family: unit-rescaling invariance of each comparison constraint.  For a constraint  lhs OP rhs  whose symbols have
declared SI dimensions, rescale the base units (kg -> s_kg times, m -> s_m times, ...) so that a symbol with
dimension vector d has its numeric value multiplied by prod s_b^d_b.  If lhs and rhs have the same dimension F
(= prod s_b^dim) then both sides get multiplied by the SAME positive factor, so the constraint holds after
rescaling iff it held before.  The generated theorem states exactly that, quantified over ALL rational values
and ALL nonzero (equalities) / positive (inequalities) scale factors.  Lean proves it by `field_simp`.

If the law is dimensionally inconsistent (e.g. L^3 replaced by L^2) the SAME generator (using the declared
units) produces a statement whose factor identity is FALSE, and Lean rejects it: that is the mutant control.

What this establishes: the constraint, AS WRITTEN with the declared units, is invariant under a change of unit
system -- a Lean-checked statement about the written constraint.  It does NOT establish that the constraint
encodes the source, that the units are right for the physical situation, or anything biological.
"""
from __future__ import annotations

import hashlib
import re
from fractions import Fraction

from . import dims as D
from .grammar import is_literal, parse_literal

LEAN_PREAMBLE = "import Mathlib.Tactic\n\n"


def _lit(x) -> str:
    f = parse_literal(x)
    return f"({f.numerator} : ℚ)" if f.denominator == 1 else f"(({f.numerator} : ℚ) / {f.denominator})"


def term_lean(term, scaled: bool, sdim: dict, used_scale: dict) -> str:
    if isinstance(term, dict):
        op = term["op"]
        if op in ("+", "*"):
            return "(" + f" {op} ".join(term_lean(a, scaled, sdim, used_scale) for a in term["args"]) + ")"
        if op == "-":
            a = [term_lean(x, scaled, sdim, used_scale) for x in term["args"]]
            return f"(-{a[0]})" if len(a) == 1 else "(" + " - ".join(a) + ")"
        if op == "/":
            return f"({term_lean(term['args'][0], scaled, sdim, used_scale)} / {_lit(term['args'][1])})"
        if op == "pow":
            return f"({term_lean(term['base'], scaled, sdim, used_scale)} ^ {term['exp']})"
    if is_literal(term):
        return _lit(term)
    name = "v_" + term
    return scale_expr(name, sdim[term]) if scaled else name


def factor_expr(d) -> str:
    """prod s_b^e as a Lean expression (negative exponents as inverse of positive power); '1' when dimensionless."""
    num, den = [], []
    for b, e in zip(D.BASE, d):
        if e > 0:
            num.append(f"s_{b} ^ {e}")
        elif e < 0:
            den.append(f"s_{b} ^ {-e}")
    n = " * ".join(num) or "1"
    if den:
        return f"({n}) * ({' * '.join(den)})⁻¹"
    return f"({n})"


def scale_expr(name: str, d) -> str:
    if not any(d):
        return name
    return f"({name} * ({factor_expr(d)}))"


def _ident(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


def constraint_theorem(c: dict, sdim: dict, names_used: list) -> tuple:
    """Return (theorem_name, lean_text) for one comparison constraint, or raise DimError-free ValueError."""
    e = c["expr"]
    op = e["op"]
    lhs_d = D.term_dim(e["lhs"], sdim, is_literal, parse_literal)
    rhs_d = D.term_dim(e["rhs"], sdim, is_literal, parse_literal)
    # The factor is taken from the lhs dimension (or rhs if lhs is the literal 0).  For an inconsistent law this
    # makes one side's factor identity false -- exactly what the mutant needs.
    F = lhs_d if lhs_d != D.ANY else rhs_d
    if F == D.ANY:
        F = (0,) * len(D.BASE)
    fac = factor_expr(F)
    bases = sorted({b for b, x in zip(D.BASE, F) if x} | {b for n in names_used for b, x in zip(D.BASE, sdim[n]) if x})
    sc = {b: None for b in bases}
    L0 = term_lean(e["lhs"], False, sdim, sc)
    R0 = term_lean(e["rhs"], False, sdim, sc)
    L1 = term_lean(e["lhs"], True, sdim, sc)
    R1 = term_lean(e["rhs"], True, sdim, sc)
    vars_ = " ".join("v_" + n for n in names_used)
    pos = op != "=="
    hyps = " ".join(f"(h_{b} : {'0 < ' if pos else ''}s_{b}{'' if pos else ' ≠ 0'})" for b in bases)
    scales = " ".join(f"s_{b}" for b in bases)
    scales_decl = f"({scales} : ℚ) " if bases else ""
    vdecl = f"({vars_} : ℚ)" if names_used else ""
    sym = {"==": "=", "<=": "≤", "<": "<", ">=": "≥", ">": ">"}[op]
    name = f"unit_rescaling_invariance_{_ident(c['id'])}"
    iff_stmt = f"({L1} {sym} {R1}) ↔ ({L0} {sym} {R0})"
    tail = {"==": "mul_right_inj' hF", "<=": "mul_le_mul_iff_of_pos_left hF", ">=": "mul_le_mul_iff_of_pos_left hF",
            "<": "Rat.mul_lt_mul_left hF", ">": "Rat.mul_lt_mul_left hF"}[op]
    hF = f"(0 : ℚ) < ({fac})" if pos else f"({fac}) ≠ 0"
    body = (f"  have hL : {L1} = ({fac}) * {L0} := by\n    field_simp <;> ring\n"
            f"  have hR : {R1} = ({fac}) * {R0} := by\n    field_simp <;> ring\n"
            f"  have hF : {hF} := by positivity\n"
            f"  rw [hL, hR]\n  exact {tail}\n")
    text = (f"/-- Generated from constraint {c['id']} (op `{op}`). Rescaling base units multiplies both sides by the same factor\n"
            f"    ({fac}); so the constraint is invariant. ALL rational values and all {'positive' if pos else 'nonzero'} scales. -/\n"
            f"theorem {name} {scales_decl}{hyps}\n    {vdecl} :\n    {iff_stmt} := by\n{body}")
    return name, text


def symbols_used(term, acc: list):
    if isinstance(term, dict):
        if term["op"] == "pow":
            acc.append(term["base"])
        else:
            for a in term["args"]:
                symbols_used(a, acc)
    elif isinstance(term, str) and not is_literal(term):
        acc.append(term)


def generate(ctx: dict, only: list | None = None) -> dict:
    """Return {'text': full Lean source, 'theorems': [names], 'sha256': ...} for the dimensionally consistent
    comparison constraints of a validated ctx.  Constraints that fail the dimension check are skipped by the
    caller (they would not be provable); pass them explicitly via `only` to build mutants."""
    sdim = {n: D.parse_unit(s["unit"]) for n, s in ctx["symbols"].items()}
    out, names = [], []
    for c in ctx["constraints"]:
        if only is not None and c["id"] not in only:
            continue
        used = []
        symbols_used(c["expr"]["lhs"], used)
        symbols_used(c["expr"]["rhs"], used)
        used = sorted(set(used))
        n, t = constraint_theorem(c, sdim, used)
        out.append(t)
        names.append(n)
    text = LEAN_PREAMBLE + "\n\n".join(out) + "\n"
    return {"text": text, "theorems": names, "sha256": hashlib.sha256(text.encode()).hexdigest()}
