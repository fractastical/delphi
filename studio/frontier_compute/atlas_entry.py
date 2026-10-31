"""H100-job entry for Protocol 6 (held-out atlas). Usage: python3 frontier_compute/atlas_entry.py ATLAS.json [--budget-s N]
Arms in fixed priority order: base (all cells), dt2 / grid2 / perturb (refine subset only). Cells are batched by (model, grid-size bin) to limit padding.
Output (metrics only, no std series, fields only for the control ids in base and dt2): $COPS_OUT/atlas_results.jsonl, atlas_fields.npz, atlas_meta.json, telemetry_*.
An arm not started within the budget is recorded not_run_out_of_budget; a batch cut by the deadline yields rows with out_of_budget=true. Nothing is dropped silently."""
import json, os, platform, subprocess, sys, time
import numpy as np
import torch
try:
    import scipy  # noqa: F401
except ImportError:
    print("pip install scipy rc", subprocess.run([sys.executable, "-m", "pip", "install", "-q", "scipy"], capture_output=True).returncode, flush=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from frontier_compute import gpu_neumann as G
from frontier_compute.telemetry import Telemetry

A = json.load(open(sys.argv[1]))
cells = A["cells"]
selected_arms = set(sys.argv[sys.argv.index("--arms") + 1].split(",")) if "--arms" in sys.argv else {"base", "dt2", "grid2", "perturb"}
if not selected_arms or not selected_arms <= {"base", "dt2", "grid2", "perturb"}:
    raise ValueError("unknown atlas arm")
lim = int(os.environ.get("ATLAS_LIMIT", "0"))
if lim:
    cells = cells[:lim]
sub_ids, ctrl_ids = set(A["refine_subset_ids"]), set(A["control_ids"])
if os.environ.get("PREFLIGHT"):
    print("preflight ok: imports and atlas file,", len(cells), "cells,", len(sub_ids), "refine ids,", len(ctrl_ids), "control ids"); sys.exit(0)
budget = float(sys.argv[sys.argv.index("--budget-s") + 1]) if "--budget-s" in sys.argv else 540.0
out = os.environ.get("COPS_OUT", ".")
t_start = time.time()
tel = Telemetry(out, max_s=int(budget) + 300)
tel.__enter__()
dev = "cuda" if torch.cuda.is_available() else "cpu"
meta = {"torch": torch.__version__, "device": dev, "python": platform.python_version(), "numpy": np.__version__, "budget_s": budget, "arms": {}}
if dev == "cuda":
    meta["gpu"] = torch.cuda.get_device_name(0)
    meta["smi"] = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
print("env", json.dumps(meta), flush=True)
ARMS = [("base", 0.02, 1, 0.0, False), ("dt2", 0.01, 1, 0.0, True), ("grid2", 0.02, 2, 0.0, True), ("perturb", 0.02, 1, 1e-10, True)]
rows, fields = [], {}
for arm, dt, gf, pert, subset_only in ARMS:
    if arm not in selected_arms:
        continue
    if time.time() - t_start > budget:
        meta["arms"][arm] = {"status": "not_run_out_of_budget"}; print("arm", arm, "NOT RUN (budget)", flush=True); continue
    pool = [c for c in cells if (c["id"] in sub_ids or not subset_only)]
    for model in ("schnakenberg", "brusselator"):
        for binname, pick in (("smallN", lambda c: c["NA"] <= 100), ("largeN", lambda c: c["NA"] > 100)):
            sub = [c for c in pool if c["model"] == model and pick(c)]
            if not sub:
                continue
            if time.time() - t_start > budget:
                meta["arms"].setdefault(arm, {})[f"{model}_{binname}"] = {"status": "not_run_out_of_budget", "B": len(sub)}
                rows += [{"id": c["id"], "arm": arm, "diverged": True, "out_of_budget": True, "not_run": True} for c in sub]
                continue
            res, m = G.simulate(sub, dt=dt, grid_factor=gf, device=dev, deadline=t_start + budget, log=lambda s: print(s, flush=True), perturb=pert)
            meta["arms"].setdefault(arm, {})[f"{model}_{binname}"] = {k: v for k, v in m.items() if k != "series_t"}
            for r in res:
                for k in ("u_final", "v_final", "u_snap"):
                    if k in r:
                        v = r.pop(k)
                        if k == "u_final" and r["id"] in ctrl_ids and arm in ("base", "dt2"):
                            fields[f"{r['id']}_{arm}_u_final"] = v
                r.pop("std_series", None)
                r["arm"] = arm
                rows.append(r)
            print("arm", arm, model, binname, "B", m["B"], "Nmax", m["Nmax"], "steps", m["steps"], "wall_s", round(m["wall_s"], 1), "timed_out", m["timed_out"], flush=True)
with open(os.path.join(out, "atlas_results.jsonl"), "w") as fh:
    for r in rows:
        fh.write(json.dumps(r, sort_keys=True) + "\n")
np.savez_compressed(os.path.join(out, "atlas_fields.npz"), **fields)
tel.__exit__(None, None, None)
meta["total_wall_s"] = round(time.time() - t_start, 1)
json.dump(meta, open(os.path.join(out, "atlas_meta.json"), "w"), indent=1)
print("done", len(rows), "rows", meta["total_wall_s"], "s", flush=True)
