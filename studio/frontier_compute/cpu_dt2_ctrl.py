"""Protocol 8 local CPU control: solver A (numpy) at dt = 0.01 with fields on the 48 atlas control ids (<= 2 processes). Usage: python3 frontier_compute/cpu_dt2_ctrl.py OUTDIR"""
import json, os, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1")
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from frontier_compute import cols
from frontier_compute.cpu_reference import run_a


def w(c):
    m, u, _ = run_a(c, 0.01); m["id"] = c["id"]; return m, u


if __name__ == "__main__":
    cells, extra = cols.decode("inputs/atlas_cols.xz"); ctrl = set(extra["control_ids"]); sel = [c for c in cells if c["id"] in ctrl]
    out = sys.argv[1]; os.makedirs(out, exist_ok=True); t0 = time.time()
    with Pool(2) as p:
        res = list(p.imap(w, sel, chunksize=1))
    with open(os.path.join(out, "cpu_A_dt2_ctrl.jsonl"), "w") as f:
        for m, _ in sorted(res, key=lambda x: x[0]["id"]):
            f.write(json.dumps(m, sort_keys=True, allow_nan=False) + "\n")
    np.savez_compressed(os.path.join(out, "cpu_A_dt2_fields.npz"), **{f"{m['id']}_A_dt2_u": u for m, u in res if u is not None})
    json.dump({"wall_s": round(time.time() - t0, 1), "n": len(res)}, open(os.path.join(out, "meta.json"), "w"))
    print("done", round(time.time() - t0, 1), "s")
