"""Mechanical pilot analysis, per PROTOCOL.md.
  python3 -m frontier_compute.compare tolerances CELLS.json CPU_DIR OUT.json     (freeze 2: tolerances from CPU step refinement)
  python3 -m frontier_compute.compare pilot CELLS.json CPU_DIR GPU_DIR TOL.json OUT.json     (controls C1-C3, verdict)
No outcome is defined here; categorical outcomes come from the vendored NCA metrics."""
import json, sys
import numpy as np
from . import VENDOR  # noqa: F401
from scopedesk.oracles import kinetics

CAT = ("pattern", "mode", "settled")


def load_cpu(cpu_dir):
    rows = {json.loads(l)["id"]: json.loads(l) for l in open(f"{cpu_dir}/cpu_ref.jsonl")}
    return rows, np.load(f"{cpu_dir}/cpu_ref_fields.npz")


def ust_of(c):
    return float(kinetics.steady(c["model"], kinetics.params(c["model"], c["params"]))[0])


def tolerances(cells_path, cpu_dir, out):
    cells = json.load(open(cells_path))["cells"]
    rows, F = load_cpu(cpu_dir)
    res = {}
    for c in cells:
        i = c["id"]
        ka, kb = f"{i}_A_dt_u", f"{i}_A_dt2_u"
        if ka in F and kb in F:
            e = float(np.abs(F[ka] - F[kb]).max() / abs(ust_of(c)))
            res[str(i)] = {"e_dt": e, "tol": max(1e-9, 2 * e), "step_converged": bool(e <= 0.01), "cpu_diverged": False}
        else:
            res[str(i)] = {"e_dt": None, "tol": None, "step_converged": False, "cpu_diverged": True}
    json.dump({"rule": "tol=max(1e-9,2*e_dt); step_converged iff e_dt<=0.01; e_dt=max|uA(0.02)-uA(0.01)|/|u*|", "cells": res},
              open(out, "w"), indent=1, sort_keys=True, allow_nan=False)
    print("cells", len(res), "step_converged", sum(v["step_converged"] for v in res.values()))


def pilot(cells_path, cpu_dir, gpu_dir, tol_path, out):
    cells = {c["id"]: c for c in json.load(open(cells_path))["cells"]}
    cpu, CF = load_cpu(cpu_dir)
    tol = json.load(open(tol_path))["cells"]
    gpu = {}
    for l in open(f"{gpu_dir}/gpu_results.jsonl"):
        r = json.loads(l)
        gpu[(r["id"], r["arm"])] = r
    GF = np.load(f"{gpu_dir}/gpu_fields.npz")
    per, c1_fail = {}, []
    for i, c in cells.items():
        g = gpu.get((i, "base"))
        a = cpu[i]["A_dt"]
        t = tol[str(i)]
        rec = {"model": c["model"], "draw": c["draw"], "x": c["x"], "rho": c["rho"], "eps": c["eps"], "linear": c["linear"],
               "cpu_pattern": a.get("pattern"), "gpu_pattern": None if g is None else g.get("pattern"), "step_converged": t["step_converged"]}
        if g is None or g.get("diverged") or a.get("diverged"):
            rec.update(cat_equal=(g is not None and bool(g.get("diverged")) == bool(a.get("diverged"))), err=None)
        else:
            rec["cat_equal"] = all(g[k] == a[k] for k in CAT)
            rec["err"] = float(np.abs(GF[f"{i}_base_u_final"] - CF[f"{i}_A_dt_u"]).max() / abs(ust_of(c)))
            rec["tol"] = t["tol"]
        rec["within_tol"] = rec.get("err") is not None and rec["err"] <= (t["tol"] or 0)
        per[str(i)] = rec
        if t["step_converged"] and not (rec["cat_equal"] and rec["within_tol"]):
            c1_fail.append(i)
    conv = [r for r in per.values() if r["step_converged"]]
    not_conv_frac = 1 - len(conv) / len(per)
    C1 = not c1_fail
    homo = [r for r in per.values() if r["rho"] == 0.7 and r["eps"] == 0.01]
    C2 = all(r["cpu_pattern"] is False and r["gpu_pattern"] is False for r in homo)
    uns = [r for r in per.values() if r["rho"] == 3.0]
    C3_sat = any(r["cpu_pattern"] for r in uns)
    C3 = all(r["cpu_pattern"] == r["gpu_pattern"] for r in uns) and C3_sat
    inconclusive = not_conv_frac > 0.25
    verdict = "INCONCLUSIVE" if inconclusive else ("PASS" if (C1 and C2 and C3) else "FAIL")
    summary = {"verdict": verdict, "C1_agreement": C1, "C1_failing_ids": c1_fail, "C2_homogeneous": C2, "n_homogeneous": len(homo),
               "C3_unstable_agree_and_patterned_exists": C3, "C3_satisfiable": C3_sat, "n_unstable": len(uns),
               "not_step_converged_fraction": not_conv_frac, "n_cells": len(per),
               "max_err_over_step_converged": max([r["err"] for r in conv if r.get("err") is not None], default=None)}
    json.dump({"summary": summary, "cells": per}, open(out, "w"), indent=1, sort_keys=True, allow_nan=False)
    print(json.dumps(summary, indent=1))
    return verdict


if __name__ == "__main__":
    a = sys.argv[1:]
    tolerances(*a[1:4]) if a[0] == "tolerances" else pilot(*a[1:6])
