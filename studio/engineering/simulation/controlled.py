"""Controlled comparison of a bounded design family against dataset-grounded baseline species dimensions (PROTOCOL_CONTROLLED.md).
Same release speed and height for every geometry within a scenario; speed must be >= level-flight stall speed (level proxy constraint);
designs outside the source envelope are flagged and cannot 'win'. Evidence kind: simulated. No calibrated claim: coefficients are assumptions.
Usage: python3 -m engineering.simulation.controlled run OUTDIR"""
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
from .evaluate import DT
from .schema import G

# Fish 1990 (J. Zool. 221:391-403) Table I, r.m.a. fits y = a M^b (M in kg): wing span (m) and wing area (m^2). Area = pectoral + pelvic fins +
# intervening segments (Fig. 1 caption; ventral body area not continuous between fins is excluded, p.394). The scan prints some 'a' values
# without a decimal point (0651, 0039); read as 0.651, 0.039 and cross-checked below against Table II (wing loading) at M = 0.2 kg.
# Table II: wing loading WL = a M^b (N/m^2) and the observed WL range per genus.
FISH = {
    "Cypselurus": {"span": (0.651, 0.375), "area": (0.039, 0.642), "WL_fit": (285.015, 0.400), "WL_range": (16.1, 205.5), "AR_pectoral_range": (3.0, 12.2), "N": 113},
    "Exocoetus": {"span": (0.774, 0.380), "area": (0.046, 0.741), "WL_fit": (300.101, 0.360), "WL_range": (40.3, 139.2), "AR_pectoral_range": (8.9, 19.9), "N": 26},
}
MASSES = [0.05, 0.1, 0.2, 0.4]
F_S = [0.7, 0.85, 1.0, 1.15, 1.3]
F_AR = [0.8, 0.9, 1.0, 1.1, 1.2]
RELEASE_SPEEDS = {"12": ("design_assumption", 12.0), "16": ("Fish 1990 p.397, citing Shoulejkin et al.: taxi speed rise 10 -> 16-20 m/s (not a measured flight envelope)", 16.0),
                  "20": ("Fish 1990 p.397, citing Shoulejkin et al.", 20.0)}
POLARS = {"P1_nominal": {"CL_max": 1.2, "CD0": 0.06, "e": 0.8, "source": "design_assumption"},
          "P2_high_drag": {"CL_max": 1.03, "CD0": 0.25, "e": 0.8, "source": "design_assumption informed by a SECONDARY source (Deng et al. 2019 numerical study of a C. hiraii pectoral-fin model: "
                                                                      "max CL 1.03, max L/D 4.7, seen at search-snippet level only; not Park & Choi data)"}}
RHO, H0 = 1.225, 1.0
WIN_RANGE, WIN_SINK = 1.02, 0.98


def baseline(genus, M):
    f = FISH[genus]
    S = f["area"][0] * M ** f["area"][1]
    b = f["span"][0] * M ** f["span"][1]
    WLd = M * G / S
    WLf = f["WL_fit"][0] * M ** f["WL_fit"][1]
    return {"genus": genus, "m": M, "S": S, "b": b, "AR": b * b / S, "WL": WLd, "WL_table2_fit": WLf, "WL_in_range": f["WL_range"][0] <= WLd <= f["WL_range"][1],
            "WL_cross_check_rel_diff": abs(WLd - WLf) / WLf}


def metrics(d, V0, pol):
    CL = float(glide.cl_command(pol["CL_max"], pol["CD0"], pol["e"], d["AR"]))
    Vs = float(glide.stall_speed(d["m"], d["S"], RHO, pol["CL_max"]))
    eq = glide.equilibrium(d["m"], d["S"], d["AR"], RHO, CL, pol["CD0"], pol["e"])
    return CL, Vs, float(eq["sink_ms"]), float(eq["L_over_D"])


def run(outdir):
    t0 = time.time()
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    bases = [baseline(g, M) for g in FISH for M in MASSES]
    excluded = [b for b in bases if not b["WL_in_range"]]
    bases = [b for b in bases if b["WL_in_range"]]
    rows = []
    for bs in bases:
        for fs, fa in itertools.product(F_S, F_AR):
            S = bs["S"] * fs; AR = bs["AR"] * fa; b = math.sqrt(AR * S)
            d = {"m": bs["m"], "S": S, "AR": AR, "b": b, "WL": bs["m"] * G / S, "fS": fs, "fAR": fa, "baseline": fs == 1.0 and fa == 1.0}
            d["in_envelope"] = FISH[bs["genus"]]["WL_range"][0] <= d["WL"] <= FISH[bs["genus"]]["WL_range"][1]
            for vk, (vsrc, V0) in RELEASE_SPEEDS.items():
                for pk, pol in POLARS.items():
                    CL, Vs, sink, LoD = metrics(d, V0, pol)
                    feasible = Vs <= V0
                    r = glide.integrate(d["m"], S, AR, RHO, CL, pol["CD0"], pol["e"], H0, V0, dt=DT)
                    h = glide.integrate(d["m"], S, AR, RHO, CL, pol["CD0"], pol["e"], H0, V0, dt=DT / 2)
                    rel = abs(float(r["range_m"][0]) - float(h["range_m"][0])) / max(float(h["range_m"][0]), 1e-12)
                    rows.append({"genus": bs["genus"], "m": d["m"], "fS": fs, "fAR": fa, "S": S, "b": b, "AR": AR, "WL": d["WL"], "is_baseline": d["baseline"],
                                 "in_envelope": d["in_envelope"], "V0": V0, "polar": pk, "CL_cmd": CL, "V_stall": Vs, "stall_feasible": feasible,
                                 "range_m": float(r["range_m"][0]), "end_reason": int(r["end_reason"][0]), "sink_eq_ms": sink, "LoD_eq": LoD, "dt_half_rel": rel,
                                 "converged": rel <= 1e-4})
    # compare to the baseline of the same genus/mass/scenario
    key = lambda r: (r["genus"], r["m"], r["V0"], r["polar"])
    base = {key(r): r for r in rows if r["is_baseline"]}
    for r in rows:
        b0 = base[key(r)]
        r["range_ratio"] = r["range_m"] / b0["range_m"] if b0["range_m"] > 0 else float("nan")
        r["sink_ratio"] = r["sink_eq_ms"] / b0["sink_eq_ms"]
        r["baseline_feasible"] = b0["stall_feasible"]
        r["win"] = bool(r["stall_feasible"] and r["in_envelope"] and r["converged"] and not r["is_baseline"] and r["range_ratio"] >= WIN_RANGE and r["sink_ratio"] <= WIN_SINK)
    # robust: wins in every scenario in which the baseline itself is feasible, and that set is nonempty; flips are listed
    summary_designs = []
    for (genus, m, fs, fa) in sorted({(r["genus"], r["m"], r["fS"], r["fAR"]) for r in rows}):
        sc = [r for r in rows if (r["genus"], r["m"], r["fS"], r["fAR"]) == (genus, m, fs, fa) and r["baseline_feasible"]]
        if not sc or (fs == 1.0 and fa == 1.0):
            continue
        wins = [r["win"] for r in sc]
        summary_designs.append({"genus": genus, "m": m, "fS": fs, "fAR": fa, "scenarios_evaluated": len(sc), "scenarios_won": int(sum(wins)), "robust_win": bool(all(wins)),
                                "flips": bool(any(wins) and not all(wins)),
                                "range_ratio_min": min(r["range_ratio"] for r in sc), "range_ratio_max": max(r["range_ratio"] for r in sc),
                                "sink_ratio_min": min(r["sink_ratio"] for r in sc), "sink_ratio_max": max(r["sink_ratio"] for r in sc),
                                "any_infeasible_for_design": bool(any(not r["stall_feasible"] for r in sc)), "any_outside_envelope": bool(any(not r["in_envelope"] for r in sc))})
    with open(out / "comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    summ = {"model_version": MODEL_VERSION, "evidence_kind": "simulated", "protocol": "engineering/simulation/PROTOCOL_CONTROLLED.md",
            "baselines": bases, "baselines_excluded_wl_outside_genus_range": excluded,
            "n_rows": len(rows), "n_unconverged": int(sum(not r["converged"] for r in rows)),
            "baseline_infeasible_scenarios": sorted({(r["genus"], r["m"], r["V0"], r["polar"]) for r in rows if r["is_baseline"] and not r["stall_feasible"]}),
            "designs": summary_designs, "n_designs": len(summary_designs), "n_robust_wins": int(sum(d["robust_win"] for d in summary_designs)),
            "n_any_win": int(sum(d["scenarios_won"] > 0 for d in summary_designs)), "n_flip": int(sum(d["flips"] for d in summary_designs)),
            "win_rule": f"feasible (V0 >= level stall speed), inside genus WL range, converged, range >= {WIN_RANGE}x and sink <= {WIN_SINK}x the genus/mass baseline in the same scenario",
            "polars": POLARS, "release_speeds": {k: v[0] for k, v in RELEASE_SPEEDS.items()}, "release_height_m": H0,
            "calibrated": False, "claim": "NO calibrated aerodynamic claim: no sourced polar; Park & Choi 2010 not readable (publisher 403, author PDF host TLS certificate expired, IUTAM host refused, Europe PMC abstract only)",
            "seconds": time.time() - t0}
    (out / "summary.json").write_text(json.dumps(summ, indent=1, default=str))
    print(json.dumps({k: v for k, v in summ.items() if k not in ("designs", "baselines", "polars")}, indent=1, default=str))


if __name__ == "__main__":
    {"run": run}[sys.argv[1]](sys.argv[2])
