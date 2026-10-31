"""Local CPU part of Protocol 6 (<= 2 processes, 1 thread each): independent solver B (scipy BDF) on ALL atlas cells, and solver A (numpy, dt 0.02) with fields on the
control ids. Usage: python3 frontier_compute/cpu_atlas.py ATLAS.json OUTDIR"""
import json, os, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from fractions import Fraction as F
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from frontier_compute import VENDOR  # noqa: F401
from scopedesk.oracles import kinetics
from scopedesk.oracles.nonlinear_sweep import solvers as S
from frontier_compute.cpu_reference import run_a


def work_b(c):
    pp = kinetics.params(c["model"], c["params"])
    ust, vst = (float(z) for z in kinetics.steady(c["model"], pp))
    t = time.time()
    try:
        b = S.run_cell_b(c["model"], pp, F(c["Dv"]), c["L"], c["NB"], c["T"], c["eps"] * abs(ust), c["eps"] * abs(vst), c["seed"], c["K"])
    except Exception as e:                      # recorded as diverged-with-reason, never dropped
        b = {"diverged": True, "message": "exception:" + repr(e)[:100]}
    b["id"] = c["id"]; b["seconds"] = round(time.time() - t, 2)
    return b


def work_a(c):
    m, u, sn = run_a(c, 0.02)
    m["id"] = c["id"]
    return m, (u if u is not None else None)


if __name__ == "__main__":
    A = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
    cells = A["cells"]; ctrl = [c for c in cells if c["id"] in set(A["control_ids"])]
    t0 = time.time()
    with Pool(2) as p:
        rb = list(p.imap(work_b, cells, chunksize=8))
        print("B done", len(rb), round(time.time() - t0, 1), "s", flush=True)
        ra = list(p.imap(work_a, ctrl, chunksize=1))
    with open(os.path.join(out, "cpu_B.jsonl"), "w") as f:
        for b in sorted(rb, key=lambda x: x["id"]):
            f.write(json.dumps(b, sort_keys=True, allow_nan=False) + "\n")
    with open(os.path.join(out, "cpu_A_ctrl.jsonl"), "w") as f:
        for m, _ in sorted(ra, key=lambda x: x[0]["id"]):
            f.write(json.dumps(m, sort_keys=True, allow_nan=False) + "\n")
    np.savez_compressed(os.path.join(out, "cpu_A_fields.npz"), **{f"{m['id']}_A_u": u for m, u in ra if u is not None})
    json.dump({"wall_s": round(time.time() - t0, 1), "procs": 2, "n_B": len(rb), "n_A": len(ra), "numpy": np.__version__}, open(os.path.join(out, "cpu_meta.json"), "w"))
    print("done", round(time.time() - t0, 1), "s")
