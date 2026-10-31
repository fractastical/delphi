"""Euler-Bernoulli cantilever: analytic solutions and a Hermite-cubic finite-element solver.

Governing equation (small deflection, slender beam, static, lateral load only):
    d^2/dx^2 ( EI(x) d^2 w / dx^2 ) = q(x),   clamped at x=0 (w=w'=0), free at x=L.
Reference: classical Euler-Bernoulli beam theory (Timoshenko & Gere, Mechanics of Materials; not read
directly here).  What WAS read: the Wikipedia article "Euler-Bernoulli beam theory" (first ~100k
characters only: governing equation, cantilever point-load curve w=F(3Lx^2-x^3)/(6EI), small-slope
assumptions).  The uniform-load cantilever result q x^2 (6L^2-4Lx+x^2)/(24EI) was NOT confirmed from that
page; it is verified here by independent integration in tests/test_fin_mechanics.py.

Units: SI.  x, L, w in m; EI in N m^2; P in N; q in N/m; slope in rad.
Everything here is SIMULATED; nothing is observed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Union

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

Num = Union[float, Callable[[np.ndarray], np.ndarray]]


# ---------------------------------------------------------------- analytic (closed form)
def tip_deflection_point_load(P, L, EI):
    """w(L) = P L^3 / (3 EI)   [m]."""
    return P * L**3 / (3.0 * EI)


def tip_deflection_uniform(q, L, EI):
    """w(L) = q L^4 / (8 EI)   [m]."""
    return q * L**4 / (8.0 * EI)


def w_point_load(x, P, L, EI):
    x = np.asarray(x, dtype=float)
    return P * x**2 * (3.0 * L - x) / (6.0 * EI)


def w_uniform(x, q, L, EI):
    x = np.asarray(x, dtype=float)
    return q * x**2 * (6.0 * L**2 - 4.0 * L * x + x**2) / (24.0 * EI)


def max_slope_point_load(P, L, EI):
    """|w'(L)| = P L^2 / (2 EI)   [rad]."""
    return P * L**2 / (2.0 * EI)


def max_slope_uniform(q, L, EI):
    """|w'(L)| = q L^3 / (6 EI)   [rad]."""
    return q * L**3 / (6.0 * EI)


def control_residuals(tip_fn=tip_deflection_point_load, uniform_fn=tip_deflection_uniform):
    """Compare closed-form formulas against independently known values.

    Reference values come from numerical double integration of M(x)/EI (scipy.integrate.quad),
    NOT from the formulas under test, so a mutated formula (e.g. L^3 -> L^2) is detected.
    Returns relative residuals for several (load, L, EI) triples.
    """
    from scipy.integrate import quad

    out = {}
    cases = [(1.0, 1.0, 1.0), (0.37, 0.15, 2.5e-4), (12.0, 2.0, 40.0)]
    for i, (a, L, EI) in enumerate(cases):
        # tip load P=a: M(s)=P (L-s); w(L)=int_0^L M(s)(L-s)/EI ds  (unit-load / moment-area)
        ref_p = quad(lambda s: a * (L - s) * (L - s) / EI, 0, L, epsabs=0, epsrel=1e-13)[0]
        # uniform q=a: M(s)=q (L-s)^2/2
        ref_u = quad(lambda s: a * (L - s) ** 2 / 2.0 * (L - s) / EI, 0, L, epsabs=0, epsrel=1e-13)[0]
        out[f"case{i}"] = {
            "P_or_q": a, "L_m": L, "EI_Nm2": EI,
            "tip_load_rel_residual": abs(tip_fn(a, L, EI) - ref_p) / ref_p,
            "uniform_rel_residual": abs(uniform_fn(a, L, EI) - ref_u) / ref_u,
        }
    return out


# ---------------------------------------------------------------- finite elements
@dataclass(frozen=True)
class Solution:
    L: float
    n_el: int
    x: np.ndarray       # node coordinates (n_el+1,)
    w: np.ndarray       # nodal deflection [m]
    theta: np.ndarray   # nodal slope [rad]

    @property
    def h(self) -> float:
        return self.L / self.n_el

    @property
    def tip(self) -> float:
        return float(self.w[-1])

    @property
    def max_abs_slope(self) -> float:
        return float(np.max(np.abs(self.theta)))

    def evaluate(self, xs):
        """Hermite-cubic interpolation of the FE solution at xs; returns (w, slope)."""
        xs = np.asarray(xs, dtype=float)
        h = self.h
        e = np.minimum((xs / h).astype(int), self.n_el - 1)
        t = (xs - e * h) / h
        w0, w1 = self.w[e], self.w[e + 1]
        t0, t1 = self.theta[e], self.theta[e + 1]
        h00 = 2 * t**3 - 3 * t**2 + 1
        h10 = t**3 - 2 * t**2 + t
        h01 = -2 * t**3 + 3 * t**2
        h11 = t**3 - t**2
        w = h00 * w0 + h10 * h * t0 + h01 * w1 + h11 * h * t1
        d00 = 6 * t**2 - 6 * t
        d10 = 3 * t**2 - 4 * t + 1
        d01 = -6 * t**2 + 6 * t
        d11 = 3 * t**2 - 2 * t
        slope = (d00 * w0 + d01 * w1) / h + d10 * t0 + d11 * t1
        return w, slope


def _per_element(v: Num, xm: np.ndarray) -> np.ndarray:
    if callable(v):
        return np.asarray(v(xm), dtype=float) * np.ones_like(xm)
    return np.full_like(xm, float(v))


def solve_cantilever(L: float, EI: Num, q: Num = 0.0, n_el: int = 32, tip_force: float = 0.0) -> Solution:
    """Hermite-cubic Euler-Bernoulli FEM for a clamped-free beam (scipy sparse direct solve).

    EI and q are constants or callables of x, sampled at element midpoints (element-wise constant).
    For constant EI and q the nodal values are exact (up to round-off); for variable EI the
    midpoint rule gives second-order convergence in h.
    """
    if not (L > 0 and n_el >= 1):
        raise ValueError("L must be > 0 and n_el >= 1")
    h = L / n_el
    xm = (np.arange(n_el) + 0.5) * h
    EIe = _per_element(EI, xm)
    qe = _per_element(q, xm)
    if np.any(EIe <= 0):
        raise ValueError("EI must be > 0")
    ke = np.empty((n_el, 4, 4))
    dim = np.array([[12, 6 * h, -12, 6 * h],
                    [6 * h, 4 * h**2, -6 * h, 2 * h**2],
                    [-12, -6 * h, 12, -6 * h],
                    [6 * h, 2 * h**2, -6 * h, 4 * h**2]])
    ke[:] = dim[None] * (EIe / h**3)[:, None, None]
    fe = np.stack([qe * h / 2, qe * h**2 / 12, qe * h / 2, -qe * h**2 / 12], axis=1)

    n = 2 * (n_el + 1)
    dofs = (2 * np.arange(n_el))[:, None] + np.arange(4)[None, :]
    rows = np.repeat(dofs[:, :, None], 4, axis=2).ravel()
    cols = np.repeat(dofs[:, None, :], 4, axis=1).ravel()
    K = sp.coo_matrix((ke.ravel(), (rows, cols)), shape=(n, n)).tocsc()
    f = np.zeros(n)
    np.add.at(f, dofs.ravel(), fe.ravel())
    f[n - 2] += tip_force
    free = np.arange(2, n)
    u = np.zeros(n)
    u[free] = spla.spsolve(K[free][:, free].tocsc(), f[free])
    x = np.linspace(0.0, L, n_el + 1)
    return Solution(L=L, n_el=n_el, x=x, w=u[0::2].copy(), theta=u[1::2].copy())


# ---------------------------------------------------------------- small-deformation validity
class SmallDeformationViolation(RuntimeError):
    """Raised by require_valid() when the linear small-deformation assumption is violated."""


def check_small_deformation(tip: float, max_slope: float, L: float,
                            tip_over_L_max: float = 0.1, slope_max_rad: float = 0.2) -> dict:
    """Flag (never silently continue) when |tip|/L or |slope| exceeds a DECLARED bound.

    The bounds are declared thresholds for when linear Euler-Bernoulli theory stops being trustworthy
    (small-slope assumption: slope ~ rotation); they are not derived from the material.
    """
    r = abs(tip) / L
    tip_ok = r <= tip_over_L_max
    slope_ok = abs(max_slope) <= slope_max_rad
    return {
        "tip_over_L": r, "tip_over_L_limit": tip_over_L_max, "tip_ok": bool(tip_ok),
        "max_slope_rad": abs(max_slope), "slope_limit_rad": slope_max_rad, "slope_ok": bool(slope_ok),
        "valid": bool(tip_ok and slope_ok),
        "flag": "OK" if (tip_ok and slope_ok) else "LINEAR_MODEL_INVALID_SMALL_DEFORMATION_VIOLATED",
    }


def require_valid(check: dict) -> dict:
    if not check["valid"]:
        raise SmallDeformationViolation(
            f"{check['flag']}: tip/L={check['tip_over_L']:.4g} (limit {check['tip_over_L_limit']}), "
            f"slope={check['max_slope_rad']:.4g} rad (limit {check['slope_limit_rad']})")
    return check


def solve_checked(L, EI, q=0.0, n_el=32, tip_force=0.0, tip_over_L_max=0.1, slope_max_rad=0.2,
                  strict=False):
    """Solve and attach the validity check; strict=True raises instead of returning the flag."""
    sol = solve_cantilever(L, EI, q, n_el, tip_force)
    chk = check_small_deformation(sol.tip, sol.max_abs_slope, L, tip_over_L_max, slope_max_rad)
    if strict:
        require_valid(chk)
    return sol, chk
