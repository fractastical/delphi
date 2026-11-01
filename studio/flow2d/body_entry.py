"""Warm-worker workload for Protocol 10: penalized disk in a uniform stream with an outflow fringe, Re = 100. Runs (a) N=1024 dt=0.0015, (b) N=512 dt=0.003, (c) N=512 dt=0.0015 (equal end time T=100),
records forces every step, analyses Cd, Cl_rms, Strouhal, and returns summaries, series and 72 q8 vorticity frames of run (a). PREFLIGHT=1: imports only."""
import json, os, sys, time
import numpy as np
import torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flow2d.body_flow import run, analyse
if os.environ.get("PREFLIGHT"):
    print("preflight ok: imports"); sys.exit(0)
OUT = os.environ.get("COPS_OUT", "."); dev = "cuda" if torch.cuda.is_available() else "cpu"
T = float(os.environ.get("BODY_T", "100")); R = {"device": dev, "torch": torch.__version__, "runs": {}}
if dev == "cuda":
    R["gpu"] = torch.cuda.get_device_name(0)
for tag, N, dt, fr in (("N1024_dt0.0015", 1024, 0.0015, 72), ("N512_dt0.003", 512, 0.003, 0), ("N512_dt0.0015", 512, 0.0015, 0)):
    t0 = time.time()
    t, Fx, Fy, (ft, frames), meta = run(N, T, dt, device=dev, frames=fr, log=lambda s: print(tag, s, flush=True))
    res = {**meta, **analyse(t, Fx, Fy, meta["D"])}
    R["runs"][tag] = res
    np.savez_compressed(os.path.join(OUT, f"{tag}_series.npz"), t=t[::5], Fx=Fx[::5], Fy=Fy[::5])        # every 5th step kept for size; analysis used all steps
    if frames is not None:
        vmax = float(np.percentile(np.abs(frames), 99.5))
        np.savez_compressed(os.path.join(OUT, "flow_frames_q8.npz"), q=np.clip((frames / vmax + 1) * 127.5, 0, 255).astype(np.uint8), t=ft, vmax=vmax, N=N, nu=meta["nu"], dt=dt)
    print(tag, json.dumps({k: res[k] for k in ("Cd_mean", "Cl_rms", "St", "wall_s", "finite")}), flush=True)
    json.dump(R, open(os.path.join(OUT, "body_results.json"), "w"), indent=1, allow_nan=False)
