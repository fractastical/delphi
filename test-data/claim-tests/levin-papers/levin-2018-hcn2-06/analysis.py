#!/usr/bin/env python3
"""levin-2018-hcn2-06: does HCN2 act as a voltage-controlled switch that amplifies small Vmem
gradients in the Pai et al. 2018 neurula model?

Minimal re-implementation (numpy only) of the bioelectric model stated in Pai et al. 2018,
Supplementary Note 1, Table 1 and Fig. 2a, with BETSE's gap-junction formulation. Model inputs
are pinned by fetch.py (data/manifest.json); the numbers below are transcribed from those
sources. Writes derived/measured.json.

Usage: python3 fetch.py && python3 analysis.py
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

F, R, T = 96485.0, 8.3145, 310.0
VT = R * T / F
CM = 0.05  # F/m2

IONS = ["Na", "K", "Cl", "Ca", "M"]
Z = np.array([1, 1, -1, 2, -1])
C_CELL = np.array([21.3, 91.0, 40.2, 50e-6, 15.1])  # mol/m3 (= mM), Table 1 intracellular
C_MMR = np.array([10.0, 0.5, 9.0, 0.1, 1.5])  # Table 1, 0.1x MMR
C_ECM = np.array([101.8, 3.7, 37.6, 1.5, 47.9])  # Table 1, extracellular (intercellular) space
DO = np.array([1.33e-9, 1.96e-9, 2.03e-9, 1.0e-10, 1.0e-9])  # BETSE free diffusion, m2/s
GJ_LEN = 26.0e-9  # BETSE cell spacing used as GJ length, m

HCN_WT, HCN_OE = 6.7e-10, 6.7e-8  # m/s
KIR_PMAX, MG, K0_MG, Z_MG = 3.33e-9, 0.5, 0.025, 1.5
LEAK_RATIO = {"tube": (1, 1, 2), "folds": (1, 1, 15), "ecto": (1, 1, 15)}  # Na:K:Cl, Fig. 2a

GJ_VTHRESH, GJ_MIN = 15.0, 0.10
GJ_LAMB, GJ_A1, GJ_A2 = 0.0013, 0.077, 0.14


def ghk_flux(P, z, V, cin, cout):
    """Outward GHK flux density, mol/m2/s. P, V broadcast over cells."""
    u = z * V / VT
    small = np.abs(u) < 1e-6
    us = np.where(small, 1.0, u)
    eu = np.exp(-us)
    f = P * us * (cin - cout * eu) / (1.0 - eu)
    return np.where(small, P * (cin - cout), f)


def hcn_minf(V):
    return 1.0 / (1.0 + np.exp((V * 1e3 + 79.0) / 6.2))


def kir_frac(V):
    k_mg = K0_MG * np.exp(-V * Z_MG / VT)
    return 1.0 / (1.0 + MG / k_mg)


def membrane_current(V, leak, hcn_pmax, cout):
    """Outward transmembrane current density (A/m2) per cell. leak: (n,3) Na,K,Cl permeabilities."""
    P = np.zeros((len(V), len(IONS)))
    P[:, 0:3] = leak
    P[:, 1] += KIR_PMAX * kir_frac(V)
    m = hcn_minf(V)
    pk = hcn_pmax * m
    P[:, 1] += pk
    P[:, 0] += 0.2 * pk
    P[:, 3] += 0.05 * pk
    I = np.zeros(len(V))
    for i in range(len(IONS)):
        I += Z[i] * F * ghk_flux(P[:, i], Z[i], V, C_CELL[i], cout[i])
    return I


def hcn_reversal(cout):
    Vs = np.linspace(-0.2, 0.1, 30001)
    I = sum(Z[i] * F * ghk_flux(np.array([0.2, 1.0, 0, 0.05, 0])[i], Z[i], Vs, C_CELL[i], cout[i])
            for i in range(len(IONS)))
    k = np.where(np.diff(np.sign(I)) != 0)[0][0]
    return float(Vs[k] - I[k] * (Vs[k + 1] - Vs[k]) / (I[k + 1] - I[k]))


def gj_open(dv):
    v1 = np.abs(dv) * 1e3
    a = GJ_LAMB * np.exp(-GJ_A1 * (v1 - GJ_VTHRESH))
    b = GJ_LAMB * np.exp(GJ_A2 * (v1 - GJ_VTHRESH))
    b = b / (1 + 50 * b)
    return np.minimum(a / (a + b) + GJ_MIN, 1.0)


def gj_conductance(gj_surface):
    """Ohmic GJ conductance per unit membrane area (S/m2) for identical cytosol on both sides."""
    return float(np.sum(Z ** 2 * F ** 2 * DO * gj_surface * C_CELL / (R * T * GJ_LEN)))


def build_sheet(radius=14):
    pts = []
    for row in range(-radius - 1, radius + 2):
        y = row * np.sqrt(3) / 2
        for col in range(-radius - 2, radius + 3):
            x = col + 0.5 * (row % 2)
            if x * x + y * y <= radius * radius:
                pts.append((x, y))
    pts = np.array(pts)
    x, y = pts[:, 0], pts[:, 1]
    region = np.full(len(pts), "ecto", dtype=object)
    folds = (x / (0.55 * radius)) ** 2 + ((y - 0.1 * radius) / (0.8 * radius)) ** 2 <= 1
    region[folds] = "folds"
    tube = (np.abs(x) <= 1.6) & (y >= -0.35 * radius) & (y <= 0.95 * radius)
    region[tube] = "tube"
    d = np.hypot(x[:, None] - x[None, :], y[:, None] - y[None, :])
    adj = (d > 0.5) & (d < 1.1)
    return pts, region, adj


def steady_state(leak, hcn_pmax, cout, adj, G, V0=None, max_steps=400):
    """Pseudo-transient implicit Euler from V0 (default 0) to steady state."""
    n = len(leak)
    V = np.zeros(n) if V0 is None else V0.copy()
    ei, ej = np.nonzero(adj)
    nnb = 6.0

    def gj_terms(V):
        dv = V[ei] - V[ej]
        w = G * gj_open(dv) / nnb
        Igj = np.zeros(n)
        np.add.at(Igj, ei, w * dv)
        return w, Igj

    # Implicit Euler in time from V0; the membrane I-V slope is floored at 0 in the Newton
    # matrix (Kir and HCN2 have negative-slope regions) and steps whose Newton loop does not
    # converge are rejected with a smaller dt, so the result follows the trajectory from V0.
    dt = 1e-3
    for _ in range(max_steps * 4):
        Vold = V.copy()
        converged = False
        for _newton in range(40):
            w, Igj = gj_terms(V)
            Im = membrane_current(V, leak, hcn_pmax, cout)
            res = CM * (V - Vold) / dt + Im + Igj
            h = 1e-6
            dIm = np.maximum((membrane_current(V + h, leak, hcn_pmax, cout) - Im) / h, 0.0)
            if len(ei):
                J = np.zeros((n, n))
                J[ei, ej] = -w
                diag = np.zeros(n)
                np.add.at(diag, ei, w)
                J[np.diag_indices(n)] = diag + dIm + CM / dt
                step = np.linalg.solve(J, -res)
            else:
                step = -res / (dIm + CM / dt)
            step = np.clip(step, -0.005, 0.005)
            V = V + step
            if np.max(np.abs(step)) < 1e-9:
                converged = True
                break
        if not converged:
            V = Vold
            dt /= 4
            continue
        dVdt = np.max(np.abs(V - Vold)) / dt
        if dt > 1e3 and dVdt < 1e-9:
            break
        dt = min(dt * 1.5, 1e6)
    _, Igj = gj_terms(V)
    resid = np.max(np.abs(membrane_current(V, leak, hcn_pmax, cout) + Igj)) / CM
    return V, float(resid)


def leak_matrix(region, P0):
    return np.array([[P0 * r for r in LEAK_RATIO[g]] for g in region], dtype=float)


def summarize(V, region, hcn_pmax):
    out = {}
    for g in ("tube", "folds", "ecto"):
        sel = region == g
        out[g] = float(V[sel].mean() * 1e3)
        out[g + "_m"] = float(hcn_minf(V[sel]).mean())
    out["lateral"] = 0.5 * (out["folds"] + out["ecto"])
    return out


def calibrate(region, adj, G, cout, grid):
    best = None
    for P0 in grid:
        V, _ = steady_state(leak_matrix(region, P0), HCN_WT, cout, adj, G)
        s = summarize(V, region, HCN_WT)
        cost = (s["tube"] + 50) ** 2 + (s["lateral"] + 5) ** 2
        if best is None or cost < best[0]:
            best = (cost, P0, s)
    _, P0, s = best
    ok = (-60 <= s["tube"] <= -40) and all(-10 <= s[g] <= 0 for g in ("folds", "ecto"))
    return P0, s, ok


def criteria(ctrl, hcn, E_hcn):
    d_tube = hcn["tube"] - ctrl["tube"]
    d_lat = max(abs(hcn["folds"] - ctrl["folds"]), abs(hcn["ecto"] - ctrl["ecto"]))
    d_grad = (hcn["lateral"] - hcn["tube"]) - (ctrl["lateral"] - ctrl["tube"])
    m_ratio = hcn["tube_m"] / max(hcn["ecto_m"], 1e-300)
    c = {
        "d_tube_mV": d_tube, "d_lateral_max_mV": d_lat, "d_gradient_mV": d_grad,
        "m_ratio_tube_over_ecto": m_ratio,
        "a": E_hcn * 1e3 < ctrl["tube"], "b": d_tube <= -15, "c": d_lat <= 5,
        "d": d_grad >= 15, "e": m_ratio >= 5,
        "fail_i": E_hcn * 1e3 > ctrl["tube"], "fail_ii": d_tube > -5,
        "fail_iii": d_lat >= 0.5 * abs(d_tube),
    }
    c["bcd"] = c["b"] and c["c"] and c["d"]
    c["primary_pass"] = all(c[k] for k in "abcde")
    return c


def run_model(cout, gj_surfaces, pts, region, adj, label):
    grid = np.logspace(-11, -7, 25)
    E_hcn = hcn_reversal(cout)
    rows = []
    for gs in gj_surfaces:
        G = gj_conductance(gs)
        P0, s_ctrl, ok = calibrate(region, adj, G, cout, grid)
        leak = leak_matrix(region, P0)
        V_c, r1 = steady_state(leak, HCN_WT, cout, adj, G)
        V_0, r2 = steady_state(leak, 0.0, cout, adj, G)
        V_h, r3 = steady_state(leak, HCN_OE, cout, adj, G)
        ctrl, ctrl0, hcn = (summarize(V_c, region, HCN_WT), summarize(V_0, region, 0.0),
                            summarize(V_h, region, HCN_OE))
        row = {"gj_surface": gs, "G_gj_S_per_m2": G, "P0_m_per_s": float(P0), "calibrated": ok,
               "control_wt_hcn2": ctrl, "control_no_hcn2": ctrl0, "hcn2_overexpressed": hcn,
               "max_residual_V_per_s": max(r1, r2, r3),
               "criteria_vs_wt_control": criteria(ctrl, hcn, E_hcn),
               "criteria_vs_no_hcn2_control": criteria(ctrl0, hcn, E_hcn)}
        print(f"[{label}] gj={gs:.0e} P0={P0:.2e} cal={ok} ctrl tube/folds/ecto="
              f"{ctrl['tube']:.1f}/{ctrl['folds']:.1f}/{ctrl['ecto']:.1f} "
              f"HCN2 {hcn['tube']:.1f}/{hcn['folds']:.1f}/{hcn['ecto']:.1f}", flush=True)
        rows.append(row)
    return E_hcn, rows


def main():
    pts, region, adj = build_sheet()
    counts = {g: int((region == g).sum()) for g in ("tube", "folds", "ecto")}
    print("cells", counts, flush=True)
    gj_surfaces = [5e-8, 1e-8, 5e-9, 1e-9, 5e-10, 1e-10, 1e-11, 0.0]

    E_hcn, rows = run_model(C_MMR, gj_surfaces, pts, region, adj, "MMR")
    cal = [r for r in rows if r["calibrated"]]
    primary = cal[0] if cal else None

    expr_sweep = []
    if primary:
        G = primary["G_gj_S_per_m2"]
        leak = leak_matrix(region, primary["P0_m_per_s"])
        ctrl = primary["control_wt_hcn2"]
        for mult in np.logspace(-2, 2, 17):
            V, res = steady_state(leak, HCN_OE * mult, C_MMR, adj, G)
            s = summarize(V, region, HCN_OE * mult)
            c = criteria(ctrl, s, E_hcn)
            expr_sweep.append({"multiple_of_6.7e-8": float(mult), "summary": s, "bcd": c["bcd"],
                               "d_tube_mV": c["d_tube_mV"], "d_lateral_max_mV": c["d_lateral_max_mV"]})
        mults = [e["multiple_of_6.7e-8"] for e in expr_sweep if e["bcd"]]
        # longest contiguous run of passing grid points, in decades
        best, cur, start = 0.0, None, None
        for e in expr_sweep:
            if e["bcd"]:
                start = e["multiple_of_6.7e-8"] if start is None else start
                best = max(best, np.log10(e["multiple_of_6.7e-8"] / start))
            else:
                start = None
        expr_span_decades = float(best)
    else:
        expr_span_decades = None

    single = []
    if primary:
        P0 = primary["P0_m_per_s"]
        one = np.zeros((1, 1), dtype=bool)
        for cl in (2, 15):
            for kmul in np.logspace(-2, 2, 41):
                leak = np.array([[P0, P0 * kmul, P0 * cl]])
                V0, _ = steady_state(leak, HCN_WT, C_MMR, one, 0.0)
                V1, _ = steady_state(leak, HCN_OE, C_MMR, one, 0.0)
                single.append({"cl_ratio": cl, "k_mult": float(kmul), "v_ctrl_mV": float(V0[0] * 1e3),
                               "v_hcn_mV": float(V1[0] * 1e3), "shift_mV": float((V1[0] - V0[0]) * 1e3)})
    hyper = [s for s in single if s["v_ctrl_mV"] <= -40]
    depol = [s for s in single if s["v_ctrl_mV"] >= -15]
    single_pass = bool(hyper and depol and any(s["shift_mV"] <= -15 for s in hyper)
                       and all(abs(s["shift_mV"]) <= 5 for s in depol))

    E_ecm, rows_ecm = run_model(C_ECM, [primary["gj_surface"]] if primary else [0.0], pts, region, adj, "ECM")

    out = {"cells": counts, "E_hcn2_reversal_mV_mmr": E_hcn * 1e3, "E_hcn2_reversal_mV_ecm": E_ecm * 1e3,
           "gj_sweep": rows, "primary_gj_surface": primary["gj_surface"] if primary else None,
           "expression_sweep": expr_sweep, "expression_span_decades": expr_span_decades,
           "single_cell": single, "single_cell_pass": single_pass,
           "single_cell_ctrl_range_mV": [min(s["v_ctrl_mV"] for s in single), max(s["v_ctrl_mV"] for s in single)] if single else None,
           "sensitivity_ecm_facing": rows_ecm}

    if primary is None:
        verdict = "inconclusive"
    else:
        cw, c0 = primary["criteria_vs_wt_control"], primary["criteria_vs_no_hcn2_control"]
        fail = any(c[k] for c in (cw, c0) for k in ("fail_i", "fail_ii", "fail_iii")) or not any(
            e["bcd"] for e in expr_sweep)
        passed = cw["primary_pass"] and c0["primary_pass"] and single_pass and expr_span_decades >= 1.0
        verdict = "refutes" if fail else ("supports" if passed else "mixed")
    out["verdict_by_preregistered_rule"] = verdict
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("E_hcn2 (0.1x MMR) = %.1f mV; (ECM) = %.1f mV" % (E_hcn * 1e3, E_ecm * 1e3))
    if primary:
        print(json.dumps({k: primary[k] for k in ("gj_surface", "P0_m_per_s", "criteria_vs_wt_control",
                                                  "criteria_vs_no_hcn2_control")}, indent=1))
    print("expression span (decades):", expr_span_decades, "single-cell pass:", single_pass,
          "ctrl range", out["single_cell_ctrl_range_mV"])
    print("VERDICT:", verdict)


if __name__ == "__main__":
    main()
