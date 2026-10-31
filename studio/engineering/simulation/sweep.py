"""Frozen parametric sweep (PROTOCOL.md): mass x wing loading x aspect ratio, nominal + paired Monte Carlo, controls, Pareto, time series.
Usage: python3 -m engineering.simulation.sweep controls OUTDIR | sweep OUTDIR"""
from __future__ import annotations

import csv
import itertools
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from . import MODEL_VERSION, glide
from .evaluate import DT, MC_N, MC_SEED, PRIORS, TOL_REL
from .schema import G, digest

M_RANGE, WL_RANGE = (0.003, 0.53), (11.7, 208.9)     # Fish 1990 specimen ranges (kg; N/m^2); WL lower bound belongs to a 0.001 kg specimen
AR_LIST = [3.0, 5.0, 8.0, 12.0, 16.9]                # Fish 1990 pectoral-fin AR range (3.0-16.9), applied to the whole wing: flagged modelling choice
N_M, N_WL = 12, 12
NOMINAL = {"rho": 1.225, "CL_max": 1.2, "CD0": 0.06, "e": 0.8, "h0": 1.0}   # DESIGN ASSUMPTIONS (rho: ISA sea level)
V0_FACTOR = 1.5


def grid():
    ms = np.exp(np.linspace(math.log(M_RANGE[0]), math.log(M_RANGE[1]), N_M))
    wls = np.exp(np.linspace(math.log(WL_RANGE[0]), math.log(WL_RANGE[1]), N_WL))
    rows = []
    for m, wl, ar in itertools.product(ms, wls, AR_LIST):
        S = m * G / wl
        rows.append({"m": float(m), "WL": float(wl), "S": float(S), "AR": ar, "b": float(math.sqrt(ar * S)), "Astar": float(S / m ** (2 / 3))})
    return rows


def run_cases(rows, CLmax, CD0, e, dt=DT):
    m = np.array([r["m"] for r in rows]); S = np.array([r["S"] for r in rows]); AR = np.array([r["AR"] for r in rows])
    CL = glide.cl_command(CLmax, CD0, e, AR)
    Vs = glide.stall_speed(m, S, NOMINAL["rho"], CLmax)
    out = glide.integrate(m, S, AR, NOMINAL["rho"], CL, CD0, e, NOMINAL["h0"], V0_FACTOR * Vs, dt=dt)
    return out, CL, Vs


def controls(outdir):
    out = {}
    m, S, AR = 0.1, 0.02, 8.0
    # 1 ballistic: no lift, no drag, level release -> x = V0 sqrt(2 h0 / g)
    V0 = 10.0
    r = glide.integrate(m, S, AR, 1.225, 1.0, 0.05, 0.8, 1.0, V0, drag=False, lift=False)
    exact = V0 * math.sqrt(2 * 1.0 / G)
    out["ballistic"] = {"range_m": float(r["range_m"][0]), "exact_m": exact, "rel_err": abs(float(r["range_m"][0]) - exact) / exact, "tol": 1e-3}
    # 2 energy: drag off, lift on (does no work) -> E = V^2/2 + g h conserved to the integrator tolerance (series recorded)
    r = glide.integrate(m, S, AR, 1.225, 1.0, 0.05, 0.8, 1.0, 10.0, drag=False, lift=True, record_stride=10)
    E = [float(0.5 * st[2][0] ** 2 + G * st[1][0]) for _, st, act in r["series"] if act[0]]
    out["energy_no_drag"] = {"E0": E[0], "max_rel_drift": max(abs(e - E[0]) for e in E) / E[0], "tol": 1e-4, "n_points": len(E)}
    # 3 equilibrium glide: start on the analytic equilibrium -> straight line, range = h0 / tan(-gam_eq)
    CD0, e, CLm = 0.06, 0.8, 1.2
    CL = float(glide.cl_command(CLm, CD0, e, AR)); eq = glide.equilibrium(m, S, AR, 1.225, CL, CD0, e)
    r = glide.integrate(m, S, AR, 1.225, CL, CD0, e, 1.0, float(eq["V_ms"]), gam0=float(eq["gamma_rad"]))
    exact = 1.0 / math.tan(-float(eq["gamma_rad"]))
    out["equilibrium"] = {"range_m": float(r["range_m"][0]), "exact_m": exact, "rel_err": abs(float(r["range_m"][0]) - exact) / exact, "tol": 1e-4}
    # 4 zero drag-coefficient limit is not a control (infinite range); 4 dt-halving on a mid design
    a, _, _ = run_cases([{"m": m, "S": S, "AR": AR}], CLm, CD0, e, dt=DT)
    b, _, _ = run_cases([{"m": m, "S": S, "AR": AR}], CLm, CD0, e, dt=DT / 2)
    out["dt_halving_single"] = {"rel_diff": abs(float(a["range_m"][0]) - float(b["range_m"][0])) / float(b["range_m"][0]), "tol": TOL_REL}
    out["all_pass"] = bool(out["ballistic"]["rel_err"] <= out["ballistic"]["tol"] and out["energy_no_drag"]["max_rel_drift"] <= out["energy_no_drag"]["tol"]
                           and out["equilibrium"]["rel_err"] <= out["equilibrium"]["tol"] and out["dt_halving_single"]["rel_diff"] <= TOL_REL)
    Path(outdir).mkdir(parents=True, exist_ok=True)
    (Path(outdir) / "controls.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def pareto_mask(objs):
    """objs: (n,k) all MINIMISED. Returns boolean non-dominated mask (exact pairwise)."""
    n = len(objs)
    keep = np.ones(n, bool)
    for i in range(n):
        dom = np.all(objs <= objs[i], axis=1) & np.any(objs < objs[i], axis=1)
        if dom.any():
            keep[i] = False
    return keep


def sweep(outdir):
    t0 = time.time()
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    rows = grid()
    nom, CL, Vs = run_cases(rows, NOMINAL["CL_max"], NOMINAL["CD0"], NOMINAL["e"])
    half, _, _ = run_cases(rows, NOMINAL["CL_max"], NOMINAL["CD0"], NOMINAL["e"], dt=DT / 2)
    eqs = glide.equilibrium(np.array([r["m"] for r in rows]), np.array([r["S"] for r in rows]), np.array([r["AR"] for r in rows]), NOMINAL["rho"], CL,
                            NOMINAL["CD0"], NOMINAL["e"])
    rngs = np.random.default_rng(MC_SEED)
    d = {k: rngs.uniform(lo, hi, MC_N) for k, (lo, hi) in PRIORS.items()}      # paired: same draws for every design
    n = len(rows)
    mcq = np.zeros((n, 3)); frac_st = np.zeros(n); frac_bad = np.zeros(n)
    for chunk in np.array_split(np.arange(n), 12):
        sub = [rows[i] for i in chunk]
        m = np.repeat([r["m"] for r in sub], MC_N); S = np.repeat([r["S"] for r in sub], MC_N); AR = np.repeat([r["AR"] for r in sub], MC_N)
        CLm, c0, ee = (np.tile(d[k], len(sub)) for k in ("CL_max", "CD0", "e"))
        CLd = glide.cl_command(CLm, c0, ee, AR)
        Vsd = glide.stall_speed(m, S, NOMINAL["rho"], CLm)
        res = glide.integrate(m, S, AR, NOMINAL["rho"], CLd, c0, ee, NOMINAL["h0"], V0_FACTOR * Vsd, dt=DT)
        rg = res["range_m"].reshape(len(sub), MC_N); er = res["end_reason"].reshape(len(sub), MC_N)
        for j, i in enumerate(chunk):
            ok = er[j] != 3
            mcq[i] = np.quantile(rg[j][ok], [0.1, 0.5, 0.9]) if ok.any() else np.nan
            frac_st[i] = np.mean(er[j] == 2); frac_bad[i] = np.mean(er[j] == 3)
    rel = np.abs(nom["range_m"] - half["range_m"]) / np.maximum(half["range_m"], 1e-12)
    for i, r in enumerate(rows):
        r.update(range_nominal_m=float(nom["range_m"][i]), time_nominal_s=float(nom["time_s"][i]), end_reason=int(nom["end_reason"][i]),
                 V_stall_ms=float(Vs[i]), CL_cmd=float(CL[i]), LoD_eq=float(eqs["L_over_D"][i]), sink_eq_ms=float(eqs["sink_ms"][i]),
                 range_q10=float(mcq[i, 0]), range_q50=float(mcq[i, 1]), range_q90=float(mcq[i, 2]), frac_stalled=float(frac_st[i]),
                 frac_nonfinite=float(frac_bad[i]), dt_half_rel_diff=float(rel[i]), converged=bool(rel[i] <= TOL_REL))
    # Pareto over (maximise q10 range, minimise sink rate, minimise Astar) among converged, finite designs
    ok = np.array([r["converged"] and np.isfinite(r["range_q10"]) for r in rows])
    objs = np.array([[-r["range_q10"], r["sink_eq_ms"], r["Astar"]] for r in rows])
    mask = np.zeros(n, bool); mask[ok] = pareto_mask(objs[ok])
    for i, r in enumerate(rows):
        r["pareto"] = bool(mask[i])
    keys = list(rows[0].keys())
    with open(out / "designs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    par = [r for r in rows if r["pareto"]]
    # time series for 3 representative Pareto designs (max q10 range, min sink, min Astar)
    picks = {}
    if par:
        picks = {"max_range_q10": max(par, key=lambda r: r["range_q10"]), "min_sink": min(par, key=lambda r: r["sink_eq_ms"]), "min_Astar": min(par, key=lambda r: r["Astar"])}
    series = {}
    for name, r in picks.items():
        g = glide.integrate(r["m"], r["S"], r["AR"], NOMINAL["rho"], r["CL_cmd"], NOMINAL["CD0"], NOMINAL["e"], NOMINAL["h0"], V0_FACTOR * r["V_stall_ms"], dt=DT, record_stride=25)
        series[name] = {"design": {k: r[k] for k in ("m", "S", "b", "AR", "WL")}, "t_s": [s[0] for s in g["series"]],
                        "x_m": [float(s[1][0][0]) for s in g["series"]], "h_m": [float(s[1][1][0]) for s in g["series"]],
                        "V_ms": [float(s[1][2][0]) for s in g["series"]], "gamma_rad": [float(s[1][3][0]) for s in g["series"]], "active": [bool(s[2][0]) for s in g["series"]]}
    summ = {"model_version": MODEL_VERSION, "evidence_kind": "simulated", "n_designs": n, "n_pareto": int(mask.sum()), "n_unconverged": int((~np.array([r['converged'] for r in rows])).sum()),
            "max_dt_half_rel_diff": float(rel.max()), "end_reasons_nominal": {str(k): int((nom["end_reason"] == k).sum()) for k in range(4)},
            "fraction_designs_with_any_stall_in_mc": float(np.mean(frac_st > 0)), "nominal_assumptions": NOMINAL, "priors": PRIORS, "mc_n": MC_N, "mc_seed": MC_SEED,
            "pareto_objectives": ["maximise range_q10 (m)", "minimise equilibrium sink rate (m/s)", "minimise A* = S/m^(2/3) (m^2 kg^-2/3)"],
            "pareto_designs_selected_dimensions": [{k: r[k] for k in ("m", "S", "b", "AR", "WL", "range_q10", "range_q50", "range_q90", "sink_eq_ms", "LoD_eq")} for r in par],
            "seconds": time.time() - t0, "not_established": ["biological feasibility", "fin-tissue coupling", "calibrated lift/drag", "scale/Reynolds validity of the polar"]}
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    (out / "timeseries.json").write_text(json.dumps(series))
    (out / "pareto.json").write_text(json.dumps(par, indent=1))
    print(json.dumps({k: v for k, v in summ.items() if k != "pareto_designs_selected_dimensions"}, indent=1))


if __name__ == "__main__":
    {"controls": controls, "sweep": sweep}[sys.argv[1]](sys.argv[2])
