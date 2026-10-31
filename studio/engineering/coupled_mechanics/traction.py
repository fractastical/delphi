"""Exact integration of a piecewise-linear line load q(s) [N/m] and its transfer to the beam mesh.

Between stations q is linear (the record carries no information about its shape in between, and
linear is the lowest-order reconstruction that keeps every station value). On a segment [a, b] with
end values qa, qb and h = b - a:

    F_seg = h (qa + qb) / 2                            [N]
    M_seg = h (qa (2a + b) + qb (a + 2b)) / 6          [N m]   moment about the root, = int q(s) s ds

Both are exact in rational arithmetic. The beam FEM (fin_mechanics.beam) takes one load value per
element; each element receives the exact mean of q over the element, so the total force carried by
the mesh equals F exactly, and the root moment differs from M by O(h^2) (reported, never hidden).
"""
from __future__ import annotations

from fractions import Fraction


def resultants(s: list[Fraction], q: list[Fraction]) -> dict:
    F = Fraction(0)
    M = Fraction(0)
    for a, b, qa, qb in zip(s, s[1:], q, q[1:]):
        h = b - a
        F += h * (qa + qb) / 2
        M += h * (qa * (2 * a + b) + qb * (a + 2 * b)) / 6
    return {"F_N": F, "M_root_Nm": M}


def _q_at(s, q, x):
    for a, b, qa, qb in zip(s, s[1:], q, q[1:]):
        if a <= x <= b:
            return qa + (qb - qa) * (x - a) / (b - a)
    raise ValueError(f"x={x} outside stations")


def element_means(s: list[Fraction], q: list[Fraction], n_el: int) -> list[Fraction]:
    """Exact mean of the piecewise-linear q over each of n_el equal elements of [0, L]."""
    L = s[-1]
    h = L / n_el
    out = []
    for e in range(n_el):
        lo, hi = e * h, (e + 1) * h
        cuts = sorted({lo, hi, *(x for x in s if lo < x < hi)})
        total = Fraction(0)
        for a, b in zip(cuts, cuts[1:]):
            total += (b - a) * (_q_at(s, q, a) + _q_at(s, q, b)) / 2
        out.append(total / h)
    return out


def mesh_resultants(q_el: list[Fraction], L: Fraction) -> dict:
    """Force and root moment of the element-constant load the FEM actually receives (exact)."""
    n = len(q_el)
    h = L / n
    F = sum((qe * h for qe in q_el), Fraction(0))
    M = sum((qe * h * (e * h + h / 2) for e, qe in enumerate(q_el)), Fraction(0))
    return {"F_N": F, "M_root_Nm": M}


def bending_moment(s: list[Fraction], q: list[Fraction], x: Fraction) -> Fraction:
    """Exact static bending moment at x for a clamped-free member: M(x) = int_x^L q(t) (t - x) dt."""
    M = Fraction(0)
    for a, b, qa, qb in zip(s, s[1:], q, q[1:]):
        if b <= x:
            continue
        a2 = max(a, x)
        qa2 = qa + (qb - qa) * (a2 - a) / (b - a)
        h = b - a2
        # int over [a2,b] of (linear q)(t)(t - x) dt, shift u = t - x
        ua, ub = a2 - x, b - x
        M += h * (qa2 * (2 * ua + ub) + qb * (ua + 2 * ub)) / 6
    return M
