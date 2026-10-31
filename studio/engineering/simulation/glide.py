"""Point-mass glide in a vertical plane, fixed commanded lift coefficient, batch RK4.

Equations (standard flight mechanics; verified here by internal tests, NOT by a page-level citation re-read in this session):
    m dV/dt   = -D - m g sin(gam)                 gam < 0 = descending
    m V dgam/dt = L - m g cos(gam)
    dx/dt = V cos(gam),  dh/dt = V sin(gam)
    L = 1/2 rho V^2 S CL,   D = 1/2 rho V^2 S CD,   CD = CD0 + CL^2 / (pi e AR),   AR = b^2/S
Commanded CL = min(CL_max, CL_opt) with CL_opt = sqrt(pi e AR CD0) (maximum L/D). Equilibrium glide: tan(gam_eq) = -CD/CL,
V_eq = sqrt(2 m g cos(gam_eq) / (rho S CL)). Stall speed (level): V_s = sqrt(2 m g / (rho S CL_max)).
Units: SI (kg, m, s, N). Coefficients CD0, e, CL_max are DESIGN ASSUMPTIONS (Fish 1990 gives allometry, not polars).
Termination: h <= 0 (water contact, x interpolated), t >= T_MAX, V <= 0.2 V_s (stalled), or non-finite state.
"""
from __future__ import annotations

import math

import numpy as np

from .schema import G

T_MAX = 120.0


def cl_command(CL_max, CD0, e, AR):
    return np.minimum(CL_max, np.sqrt(np.pi * e * AR * CD0))


def drag_coeff(CL, CD0, e, AR):
    return CD0 + CL ** 2 / (np.pi * e * AR)


def equilibrium(m, S, AR, rho, CL, CD0, e, g=G):
    CD = drag_coeff(CL, CD0, e, AR)
    gam = -np.arctan2(CD, CL)
    V = np.sqrt(2 * m * g * np.cos(gam) / (rho * S * CL))
    return {"gamma_rad": gam, "V_ms": V, "L_over_D": CL / CD, "sink_ms": -V * np.sin(gam)}


def stall_speed(m, S, rho, CL_max, g=G):
    return np.sqrt(2 * m * g / (rho * S * CL_max))


def _rhs(state, m, S, rho, CL, CD, g):
    x, h, V, gam = state
    q = 0.5 * rho * V * V * S
    L, D = q * CL, q * CD
    return np.stack([V * np.cos(gam), V * np.sin(gam), -D / m - g * np.sin(gam), L / (m * V) - g * np.cos(gam) / V])


def integrate(m, S, AR, rho, CL, CD0, e, h0, V0, gam0=0.0, dt=0.002, record_stride=0, g=G, stall_floor=None, drag=True, lift=True):
    """Vectorised over cases (all arguments broadcastable to 1-D arrays). Returns dict of arrays: range_m, time_s, end_reason code, plus optional series.
    end_reason: 0 water contact, 1 time limit, 2 stalled, 3 non-finite. `drag=False` and `lift=False` give controls (ballistic / energy)."""
    m, S, AR, rho, CL, CD0, e, h0, V0 = [np.atleast_1d(a).copy() for a in np.broadcast_arrays(*[np.asarray(a, float) for a in (m, S, AR, rho, CL, CD0, e, h0, V0)])]
    n = m.size
    CD = drag_coeff(CL, CD0, e, AR) * (1.0 if drag else 0.0)
    CLe = CL * (1.0 if lift else 0.0)
    Vs = stall_speed(m, S, rho, np.maximum(CL, 1e-9), g)
    st = np.stack([np.zeros(n), h0.copy(), V0.copy(), np.full(n, float(gam0))])
    active = np.ones(n, bool)
    rng = np.zeros(n)
    tend = np.zeros(n)
    reason = np.full(n, 1)
    floor = (0.2 * Vs) if stall_floor is None else stall_floor
    series = [] if record_stride else None
    steps = int(T_MAX / dt)
    for k in range(steps):
        if not active.any():
            break
        prev = st.copy()
        k1 = _rhs(st, m, S, rho, CLe, CD, g)
        k2 = _rhs(st + 0.5 * dt * k1, m, S, rho, CLe, CD, g)
        k3 = _rhs(st + 0.5 * dt * k2, m, S, rho, CLe, CD, g)
        k4 = _rhs(st + dt * k3, m, S, rho, CLe, CD, g)
        new = st + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        new = np.where(active, new, st)
        bad = ~np.isfinite(new).all(axis=0) & active
        hit = (new[1] <= 0) & active & ~bad
        stalled = (new[2] <= floor) & active & ~bad & ~hit
        frac = np.where(hit, prev[1] / np.maximum(prev[1] - new[1], 1e-300), 0.0)
        rng = np.where(hit, prev[0] + frac * (new[0] - prev[0]), rng)
        tend = np.where(hit, (k + frac) * dt, tend)
        reason = np.where(hit, 0, reason)
        for mask, code in ((stalled, 2), (bad, 3)):
            rng = np.where(mask, np.nan_to_num(prev[0]), rng)
            tend = np.where(mask, k * dt, tend)
            reason = np.where(mask, code, reason)
        active &= ~(hit | stalled | bad)
        st = np.where(active, new, st)
        if series is not None and k % record_stride == 0:
            series.append((k * dt, st.copy(), active.copy()))
    timeout = active
    rng = np.where(timeout, st[0], rng)
    tend = np.where(timeout, steps * dt, tend)
    out = {"range_m": rng, "time_s": tend, "end_reason": reason, "V_stall_ms": Vs}
    if series is not None:
        out["series"] = series
    return out
