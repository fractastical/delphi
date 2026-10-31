"""Summarise cfd3d cases: grid pairs, time-window stationarity, and simulated vs intended Reynolds regime.

    python engineering/cfd3d/summarize.py artifacts/cfd3d OUT.json CASE_ID [CASE_ID ...]

The regime table is the point: a low-Re numerical demo is never presented as the fish's real flow regime.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

L_REF = 0.230699   # m, fish3d total length
# Kinematic viscosities at ~20 C: textbook values, recalled, not re-read from a primary table here.
MEDIA = {"air_20C": {"rho": 1.204, "nu": 1.516e-5}, "water_20C": {"rho": 998.2, "nu": 1.004e-6}}
# Intended speeds are illustrative ranges, NOT sourced measurements; replace with a cited source before use.
INTENDED = {"air_glide": {"medium": "air_20C", "U_m_s": [10.0, 20.0], "status": "assumed, unsourced"},
            "water_burst_before_takeoff": {"medium": "water_20C", "U_m_s": [5.0, 10.0], "status": "assumed, unsourced"}}


def regime(re_sim: float) -> dict:
    sim = {m: {"U_m_s": re_sim * v["nu"] / L_REF,
               "q_Pa": 0.5 * v["rho"] * (re_sim * v["nu"] / L_REF) ** 2} for m, v in MEDIA.items()}
    intended = {}
    for k, v in INTENDED.items():
        nu = MEDIA[v["medium"]]["nu"]
        intended[k] = dict(v, Re_L=[u * L_REF / nu for u in v["U_m_s"]])
        intended[k]["gap_factor"] = [r / re_sim for r in intended[k]["Re_L"]]
    return {"simulated_Re_L": re_sim, "same_Re_in_each_medium": sim, "intended": intended,
            "label": "LOW-Re NUMERICAL DEMO: not swimming-, taxiing- or flight-validated; no free surface; "
                     "fixed rigid body; fins sub-grid",
            "note": "incompressible: the same Re_L gives the same Cp in air and water; only U and Pa differ"}


def stationarity(forces: dict, q: float) -> dict:
    t, f = forces["t"], [-x[0] / q for x in forces["F_total_grid"]]
    w = {k: [c for s, c in zip(t, f) if a <= s < b] for k, (a, b) in {"2-3": (2, 3), "3-4": (3, 4.5)}.items()}
    m = {k: sum(v) / len(v) for k, v in w.items() if v}
    return {"Cd_mean_tUL_2_3": m.get("2-3"), "Cd_mean_tUL_3_4": m.get("3-4"),
            "rel_change": abs(m["3-4"] - m["2-3"]) / abs(m["3-4"]) if len(m) == 2 else None}


def main(root: Path, out: Path, ids: list[str]) -> dict:
    cases = {}
    for cid in ids:
        c = json.loads((root / cid / "case.json").read_text())
        f = json.loads((root / cid / "forces.json").read_text())
        L = c["grid"]["L_cells"]
        cases[cid] = {"L_cells": L, "Re_L": c["nondim"]["Re_L"], "coefficients": c["coefficients"],
                      "stationarity": stationarity(f, 0.5 * L * L), "steps": c["steps"], "wall_s": c["wall_s"],
                      "fin_thickness_cells": c["resolution"]["fin_thickness_cells"],
                      "shell_simulated_thickness_mm": c["resolution"]["shell_simulated_thickness_mm"],
                      "regime": regime(c["nondim"]["Re_L"]), "case_json": f"{cid}/case.json"}
    pairs = []
    by_re: dict = {}
    for cid, v in cases.items():
        by_re.setdefault(v["Re_L"], []).append((v["L_cells"], cid))
    for re_, lst in by_re.items():
        lst.sort()
        for (l1, a), (l2, b) in zip(lst, lst[1:]):
            ca, cb = cases[a]["coefficients"]["Cd_total"], cases[b]["coefficients"]["Cd_total"]
            d = abs(cb - ca) / abs(cb)
            pairs.append({"Re_L": re_, "coarse": a, "fine": b, "Cd_coarse": ca, "Cd_fine": cb, "rel_diff": d,
                          "grid_rule_met": d <= 0.10,
                          "reading": "pair within 10%" if d <= 0.10 else "NOT grid-independent: no force claim"})
    s = {"schema": "cfd3d-summary-0.1", "cases": cases, "grid_pairs": pairs}
    out.write_text(json.dumps(s, indent=1))
    return s


if __name__ == "__main__":
    r = main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:])
    print(json.dumps(r["grid_pairs"], indent=1))
