"""CPU reference for a list of cells using the vendored NCA oracle: solver A at dt and dt/2 (with fields) and independent solver B.
Run as a Nebius CPU job entry or locally (<=2 procs). Usage: python3 frontier_compute/cpu_reference.py CELLS.json OUTDIR [PROCS]
Output: OUTDIR/cpu_ref.jsonl (metrics per cell), OUTDIR/cpu_ref_fields.npz (u_final, u_snap for A at dt and dt/2), OUTDIR/env.json."""
import json, math, os, platform, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from fractions import Fraction as F
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
from scopedesk.oracles import kinetics, pde
from scopedesk.oracles.nonlinear_sweep import solvers as S


def run_a(c, dt):
    pp = kinetics.params(c["model"], c["params"])
    ust, vst = (float(z) for z in kinetics.steady(c["model"], pp))
    pu, pv = S.ic_modal(c["seed"], c["K"], c["L"], c["NA"], c["eps"] * abs(ust), c["eps"] * abs(vst))
    t = time.time()
    res = pde._run(c["model"], pp, F(1), F(c["Dv"]), 1, "neumann", [c["L"]], [c["NA"]], [c["K"]], c["T"], dt, c["seed"], ic=(pu, pv))
    if res["diverged"]:
        return {"diverged": True, "seconds": time.time() - t}, None, None
    m = S.metrics(res["u"], res["snap"], res["ust"])
    m.update(diverged=False, seconds=round(time.time() - t, 2), maxabs=res["maxabs"])
    return m, res["u"], res["snap"]


def one(c):
    out = {"id": c["id"]}
    fields = {}
    for tag, dt in (("A_dt", 0.02), ("A_dt2", 0.01)):
        m, u, sn = run_a(c, dt)
        out[tag] = m
        if u is not None:
            fields[f"{c['id']}_{tag}_u"], fields[f"{c['id']}_{tag}_snap"] = u, sn
    pp = kinetics.params(c["model"], c["params"])
    ust, vst = (float(z) for z in kinetics.steady(c["model"], pp))
    t = time.time()
    out["B"] = S.run_cell_b(c["model"], pp, F(c["Dv"]), c["L"], c["NB"], c["T"], c["eps"] * abs(ust), c["eps"] * abs(vst), c["seed"], c["K"])
    out["B"]["seconds"] = round(time.time() - t, 2)
    return out, fields


if __name__ == "__main__":
    cells = json.load(open(sys.argv[1]))["cells"]
    outdir = sys.argv[2]
    procs = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    os.makedirs(outdir, exist_ok=True)
    t0 = time.time()
    allf, rows = {}, []
    with Pool(procs) as p:
        for o, f in p.imap(one, cells, chunksize=1):
            rows.append(o)
            allf.update(f)
            print("cell", o["id"], "A", o["A_dt"].get("pattern"), "B", o["B"].get("pattern"), flush=True)
    rows.sort(key=lambda r: r["id"])
    with open(os.path.join(outdir, "cpu_ref.jsonl"), "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, allow_nan=False) + "\n")
    np.savez_compressed(os.path.join(outdir, "cpu_ref_fields.npz"), **allf)
    json.dump({"python": platform.python_version(), "numpy": np.__version__, "wall_s": round(time.time() - t0, 1), "procs": procs,
               "nproc": os.cpu_count(), "platform": platform.platform()}, open(os.path.join(outdir, "env.json"), "w"))
    print("done", len(rows), "cells", round(time.time() - t0, 1), "s")
