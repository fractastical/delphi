"""Run a REAL dx-guilds solver witness (engineering/constraints.py, z3, independent verify_certificate) through this package and compare it with the
Fish genus fit at the witness mass. Requires z3-solver and a checkout of the guilds branch on PYTHONPATH (read-only import).
Usage (isolated venv with z3-solver==5.3.3.0): GUILDS_CONSTRAINTS_PY=<path to guilds engineering/constraints.py> PYTHONPATH=. python -m engineering.simulation.witness_check OUT.json"""
from __future__ import annotations

import json
import sys
from fractions import Fraction

from . import controlled
from .evaluate import evaluate
from .schema import G, digest


def main(out):
    import importlib.util
    import os
    path = os.environ.get("GUILDS_CONSTRAINTS_PY", "/data/worktrees/delphi-frontier/guilds/engineering/constraints.py")   # guilds module, loaded by path, read-only
    spec = importlib.util.spec_from_file_location("guilds_constraints", path)
    C = importlib.util.module_from_spec(spec)
    sys.modules["guilds_constraints"] = C
    spec.loader.exec_module(C)
    M = C.flying_fish_model(rho="1.225", CL="6/5", assume_pectoral_ar_applies_to_wing=True)
    q = [C.q_speed_max("12")]
    res = C.solve(M, q)
    d = res.to_json()
    ver = C.verify_certificate(M, d, q)
    cand = {"schema": "frontier.glide.candidate/1", "solver_result": d,
            "units": {"m": "kg", "S": "m^2", "b": "m", "V": "m/s"},
            "flight_assumptions": {"rho": {"value": "1.225", "unit": "kg/m^3", "source": "design_assumption"},
                                   "CL_max": {"value": "6/5", "unit": "1", "source": "design_assumption"},
                                   "CD0": {"value": "3/50", "unit": "1", "source": "design_assumption"},
                                   "e": {"value": "4/5", "unit": "1", "source": "design_assumption"},
                                   "release_height_m": {"value": "1", "unit": "m", "source": "design_assumption"}},
            "release_speed_from_witness": True}
    rec = evaluate(cand, mc_n=200)
    w = {k: Fraction(v) for k, v in d["witness"].items()}
    m, S, b = float(w["m"]), float(w["S"]), float(w["b"])
    fit = {g: {"S_fit_m2": controlled.FISH[g]["area"][0] * m ** controlled.FISH[g]["area"][1], "b_fit_m": controlled.FISH[g]["span"][0] * m ** controlled.FISH[g]["span"][1]} for g in controlled.FISH}
    for g in fit:
        fit[g]["AR_fit"] = fit[g]["b_fit_m"] ** 2 / fit[g]["S_fit_m2"]
        fit[g]["witness_area_over_fit"] = S / fit[g]["S_fit_m2"]
        fit[g]["witness_AR"] = b * b / S
    out_d = {"solver": d["solver"], "z3_version": d.get("z3_version"), "query": "flying_fish_model(rho=1.225, CL=6/5, assume_pectoral_ar_applies_to_wing=True) + q_speed_max(12)",
             "solver_status": d["status"], "witness": d["witness"], "witness_wing_loading_N_m2": m * G / S, "independent_verify_certificate": ver,
             "solver_result_sha256": digest(d), "receipt": rec, "comparison_to_Fish_genus_fit_at_witness_mass": fit,
             "reading": "The witness is feasible for the declared constraints but sits at the wing-loading lower bound with a wing area far larger than the Fish genus fit at that mass: a source envelope is not a feasibility region for a real fish. NOT a print candidate."}
    open(out, "w").write(json.dumps(out_d, indent=1, default=str))
    print(json.dumps({k: out_d[k] for k in ("solver_status", "witness", "independent_verify_certificate")}, default=str))
    print(json.dumps({"verdict": rec["verdict"], "results": rec["results"], "comparison": fit}, indent=0, default=str)[:1500])


if __name__ == "__main__":
    main(sys.argv[1])
