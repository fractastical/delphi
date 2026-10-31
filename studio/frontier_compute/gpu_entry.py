"""H100-job entry for the frozen replication/sensitivity run. Usage: python3 frontier_compute/gpu_entry.py CELLS.json [--arms base,dt2,grid2] [--budget-s N]
Writes $COPS_OUT/gpu_results.jsonl, gpu_fields.npz, gpu_meta.json. Arms: base (dt=0.02, N), dt2 (dt=0.01, N), grid2 (dt=0.02, 2N).
Runs arms in the order given; an arm not started before the budget is recorded as not_run (out of budget), never silently dropped."""
import json, os, platform, subprocess, sys, time
import numpy as np
import torch
try:
    import scipy  # noqa: F401  (vendored NCA solvers.py imports scipy at module level)
except ImportError:
    print('pip install scipy rc', subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'scipy'], capture_output=True).returncode, flush=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from frontier_compute import gpu_neumann as G

cells = json.load(open(sys.argv[1]))["cells"]
arms = (sys.argv[sys.argv.index("--arms") + 1] if "--arms" in sys.argv else "base").split(",")
budget = float(sys.argv[sys.argv.index("--budget-s") + 1]) if "--budget-s" in sys.argv else 480.0
out = os.environ.get("COPS_OUT", ".")
t_start = time.time()
dev = "cuda" if torch.cuda.is_available() else "cpu"
meta = {"torch": torch.__version__, "device": dev, "python": platform.python_version(), "numpy": np.__version__, "arms": {}, "budget_s": budget}
if dev == "cuda":
    meta["gpu"] = torch.cuda.get_device_name(0)
    meta["cuda"] = torch.version.cuda
    meta["smi"] = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
print("env", json.dumps(meta), flush=True)
rows, fields = [], {}
for arm in arms:
    if time.time() - t_start > budget:
        meta["arms"][arm] = {"status": "not_run_out_of_budget"}
        print("arm", arm, "NOT RUN (budget)", flush=True)
        continue
    dt, gf, pert = {"base": (0.02, 1, 0.0), "dt2": (0.01, 1, 0.0), "grid2": (0.02, 2, 0.0), "perturb": (0.02, 1, 1e-10)}[arm]
    fids = [int(x) for x in sys.argv[sys.argv.index("--frames") + 1].split(",")] if "--frames" in sys.argv and arm == "base" else []
    nfr = int(sys.argv[sys.argv.index("--nframes") + 1]) if "--nframes" in sys.argv else 0
    for model in sorted({c["model"] for c in cells}):
        sub = [c for c in cells if c["model"] == model]
        res, m = G.simulate(sub, dt=dt, grid_factor=gf, device=dev, deadline=t_start + budget, log=lambda s: print(s, flush=True), perturb=pert, frame_ids=fids, nframes=nfr)
        meta["arms"].setdefault(arm, {})[model] = {k: v for k, v in m.items() if k != "series_t"}
        meta["arms"][arm].setdefault("series_t", {})[model] = m["series_t"]
        for r in res:
            for k in ("u_final", "v_final", "u_snap", "frame_t", "frames_u"):
                if k in r:
                    v = r.pop(k)
                    if arm == "base":          # fields kept for the base arm only (size); other arms keep metrics
                        fields[f"{r['id']}_{arm}_{k}"] = v
            r["arm"] = arm
            rows.append(r)
        print("arm", arm, model, "B", m["B"], "steps", m["steps"], "wall_s", round(m["wall_s"], 1), "timed_out", m["timed_out"], flush=True)
with open(os.path.join(out, "gpu_results.jsonl"), "w") as fh:
    for r in rows:
        fh.write(json.dumps(r, sort_keys=True) + "\n")
np.savez_compressed(os.path.join(out, "gpu_fields.npz"), **fields)
meta["total_wall_s"] = round(time.time() - t_start, 1)
json.dump(meta, open(os.path.join(out, "gpu_meta.json"), "w"), indent=1)
print("done", len(rows), "rows", meta["total_wall_s"], "s", flush=True)
