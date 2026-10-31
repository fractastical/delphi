"""Warm-worker workload for Protocol 8: run solver A (GPU float64) arms on a columnar cell table. Usage: dt_entry.py CELLS.xz --arms base,dt2 [--budget-s N]
Metrics only (no series); fields (u_final) only for ids in extra.control_ids. Cells batched by (model, grid-size bin). A batch not run in budget is recorded, not dropped."""
import json, os, platform, subprocess, sys, time
import numpy as np
import torch
try:
    import scipy  # noqa: F401
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "scipy"], capture_output=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from frontier_compute import cols, gpu_neumann as G
cells, extra = cols.decode(sys.argv[1])
if os.environ.get("PREFLIGHT"):
    print("preflight ok: imports, decode", len(cells), "cells"); sys.exit(0)
arms = (sys.argv[sys.argv.index("--arms") + 1] if "--arms" in sys.argv else "base").split(",")
budget = float(sys.argv[sys.argv.index("--budget-s") + 1]) if "--budget-s" in sys.argv else 600.0
out = os.environ.get("COPS_OUT", ".")
ctrl = set(extra.get("control_ids", []))
dev = "cuda" if torch.cuda.is_available() else "cpu"
t0 = time.time(); meta = {"arms": {}, "device": dev, "budget_s": budget, "n_cells": len(cells), "torch": torch.__version__}
rows, fields = [], {}
SPEC = {"base": (0.02, 1), "dt2": (0.01, 1), "dt4": (0.005, 1), "grid2": (0.02, 2)}
for arm in arms:
    dt, gf = SPEC[arm]
    for model in ("schnakenberg", "brusselator"):
        for binname, pick in (("smallN", lambda c: c["NA"] <= 100), ("largeN", lambda c: c["NA"] > 100)):
            sub = [c for c in cells if c["model"] == model and pick(c)]
            if not sub:
                continue
            if time.time() - t0 > budget:
                meta["arms"].setdefault(arm, {})[f"{model}_{binname}"] = {"status": "not_run_out_of_budget", "B": len(sub)}
                rows += [{"id": c["id"], "arm": arm, "diverged": True, "out_of_budget": True, "not_run": True} for c in sub]; continue
            res, m = G.simulate(sub, dt=dt, grid_factor=gf, device=dev, deadline=t0 + budget, log=lambda s: print(s, flush=True))
            meta["arms"].setdefault(arm, {})[f"{model}_{binname}"] = {k: v for k, v in m.items() if k != "series_t"}
            for r in res:
                for k in ("u_final", "v_final", "u_snap"):
                    if k in r:
                        v = r.pop(k)
                        if k == "u_final" and r["id"] in ctrl:
                            fields[f"{r['id']}_{arm}_u_final"] = v
                r.pop("std_series", None); r["arm"] = arm; rows.append(r)
            print("arm", arm, model, binname, "B", m["B"], "steps", m["steps"], "wall_s", round(m["wall_s"], 1), "timed_out", m["timed_out"], flush=True)
with open(os.path.join(out, "results.jsonl"), "w") as fh:
    for r in rows:
        fh.write(json.dumps(r, sort_keys=True) + "\n")
np.savez_compressed(os.path.join(out, "fields.npz"), **fields)
meta["wall_s"] = round(time.time() - t0, 1)
json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=1)
print("done", len(rows), "rows", meta["wall_s"], "s", flush=True)
