"""Protocol 5 GPU job: refined-step demo with EQUAL-END-TIME paired validation. One entry, no duplicated simulation: the N=2048 demo run provides its own T/4 snapshot,
the N=1024 runs provide the T/4 snapshots for the order check and the grid comparison. Frames in the same q8 format as flow_demo.py (render_flow_video.py reuses them).
Env: FLOW_N (2048), FLOW_NC (1024), FLOW_T (8.0), FLOW_NU (1e-4), FLOW_N0 (13400 steps for the demo; must be divisible by 4), FLOW_NFRAMES (72), FLOW_BUDGET_S (900)."""
import json, math, os, sys, time
import numpy as np
import torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flow2d.solver import NS2D, shear_layer_w0
from frontier_compute.telemetry import Telemetry

OUT = os.environ.get("COPS_OUT", ".")
N = int(os.environ.get("FLOW_N", "2048")); NC = int(os.environ.get("FLOW_NC", "1024")); T = float(os.environ.get("FLOW_T", "8.0"))
NU = float(os.environ.get("FLOW_NU", "1e-4")); N0 = int(os.environ.get("FLOW_N0", "13400")); NF = int(os.environ.get("FLOW_NFRAMES", "72"))
BUDGET = float(os.environ.get("FLOW_BUDGET_S", "900"))
assert N0 % 8 == 0
dev = "cuda" if torch.cuda.is_available() else "cpu"
T0 = time.time()
if os.environ.get("PREFLIGHT"):
    print("preflight ok: imports"); sys.exit(0)
R = {"device": dev, "torch": torch.__version__, "params": {"N": N, "NC": NC, "T": T, "nu": NU, "n0": N0, "dt0": T / N0, "nframes": NF}}
if dev == "cuda":
    R["gpu"] = torch.cuda.get_device_name(0)
TP = T / 4.0


def sync():
    if dev == "cuda":
        torch.cuda.synchronize()


def save():
    json.dump(R, open(os.path.join(OUT, "flow_refine_results.json"), "w"), indent=1, default=str, allow_nan=False)


def rel(a, b):
    A, B = torch.fft.ifft2(a).real, torch.fft.ifft2(b).real
    return float(torch.linalg.norm(A - B) / torch.linalg.norm(B))


def lowpass_hat(wh, n_out):
    N_ = wh.shape[0]; h = n_out // 2
    c = torch.fft.fftshift(wh) / N_ ** 2; c0 = N_ // 2
    return torch.fft.ifftshift(c[c0 - h:c0 + h, c0 - h:c0 + h] * n_out ** 2)        # centred, normalized to n_out grid -> back to fft layout


def run(Nn, n, dt, snap_steps=(), sample_every=0, frames=False):
    """advance n steps of size dt from the shear-layer IC; returns final hat, dict of snapshots at requested step counts, samples."""
    s = NS2D(Nn, NU, dt, device=dev)
    X, Y = s.grid()
    wh = s.to_hat(shear_layer_w0(X, Y))
    snaps, samples, frs, ft = {}, [], [], []
    t_run = time.time()
    for k in range(1, n + 1):
        wh = s.step(wh)
        if k in snap_steps:
            snaps[k] = wh.clone()
        if sample_every and (k % sample_every == 0 or k == n):
            dg = s.diag(wh); dg.update(step=k, t=k * dt, cfl=dg["umax"] * dt / (2 * math.pi / Nn), wall_s=round(time.time() - t_run, 1)); samples.append(dg)
            if frames:
                frs.append(torch.fft.ifft2(lowpass_hat(wh, 128)).real.cpu().numpy().astype(np.float32)); ft.append(k * dt)
            if not math.isfinite(dg["E"]):
                break
    sync()
    return s, wh, snaps, samples, frs, ft


with Telemetry(OUT, max_s=int(BUDGET) + 600):
    dt0 = T / N0
    every = max(1, N0 // NF)
    # --- A: the demo at N (dt0), with its own T/4 snapshot and frames
    sA, whA, snA, smp, frs, ft = run(N, N0, dt0, snap_steps=(N0 // 4,), sample_every=every, frames=True)
    R["demo"] = {"n_steps": N0, "dt": dt0, "wall_s": round(time.time() - T0, 1), "max_cfl": max(d["cfl"] for d in smp), "max_divergence": max(d["divmax"] for d in smp),
                 "umax_max": max(d["umax"] for d in smp), "E0": None, "E_end": smp[-1]["E"], "enstrophy_end": smp[-1]["Z"], "series": smp}
    # energy budget (trapezoid on samples, from the IC)
    s0 = NS2D(N, NU, dt0, device=dev); X, Y = s0.grid(); d0 = s0.diag(s0.to_hat(shear_layer_w0(X, Y)))
    ts = [0.0] + [d["t"] for d in smp]; Zs = [d0["Z"]] + [d["Z"] for d in smp]
    integ = sum(0.5 * (Zs[i] + Zs[i + 1]) * (ts[i + 1] - ts[i]) for i in range(len(ts) - 1))
    R["demo"]["E0"] = d0["E"]
    R["demo"]["energy_budget_residual_rel"] = ((smp[-1]["E"] - d0["E"]) - (-2 * NU * integ)) / abs(smp[-1]["E"] - d0["E"])
    ab = whA.abs() ** 2; kk = torch.sqrt(sA.k2)
    R["demo"]["enstrophy_fraction_above_0.66kmax"] = float(ab[kk > 0.66 * (N // 3)].sum() / ab.sum())
    fr = np.stack(frs); vmax = float(np.percentile(np.abs(fr), 99.5))
    np.savez_compressed(os.path.join(OUT, "flow_frames_q8.npz"), q=np.clip((fr / vmax + 1) * 127.5, 0, 255).astype(np.uint8), t=np.array(ft), vmax=vmax, N=N, nu=NU, dt=dt0)
    save()
    # --- B: paired partner at N, dt0/2, to T/4 only (equal end time)
    sB, whB, _, _, _, _ = run(N, N0 // 2, dt0 / 2)         # n = N0/2 steps of dt0/2 -> T/2?  guard below
    # NOTE: T/4 needs (N0/4)*2 = N0/2 steps of dt0/2
    R["P1_paired_N%d_T/4" % N] = {"end_time": TP, "n_dt0": N0 // 4, "n_dt0/2": N0 // 2, "rel_L2": rel(snA[N0 // 4], whB)}
    save()
    # --- C: N=NC runs: dt1 = 2*dt0 (n = N0/2), dt0 (n = N0), plus dt0/2 to T/4 only (n = N0/2)
    dt1 = 2 * dt0
    sC1, wC1, snC1, _, _, _ = run(NC, N0 // 2, dt1, snap_steps=(N0 // 8,))
    sC2, wC2, snC2, _, _, _ = run(NC, N0, dt0, snap_steps=(N0 // 4,))
    sC3, wC3, _, _, _, _ = run(NC, N0 // 2, dt0 / 2)       # T/4 at dt0/2 : N0/4*2 = N0/2 steps
    e12, e23 = rel(snC1[N0 // 8], snC2[N0 // 4]), rel(snC2[N0 // 4], wC3)
    R["P2_paired_N%d_T" % NC] = {"end_time": T, "n_dt1": N0 // 2, "n_dt1/2": N0, "rel_L2": rel(wC1, wC2)}
    R["P3_order_N%d_T/4" % NC] = {"end_time": TP, "rel_L2_dt1_vs_dt1/2": e12, "rel_L2_dt1/2_vs_dt1/4": e23, "ratio": e12 / e23 if e23 > 0 else None}
    # --- grid comparison at T/4, same dt0: NC (snC2) vs N demo snapshot, low-passed to NC
    R["grid_N%d_vs_N%d_T/4_same_dt0" % (NC, N)] = {"rel_L2": rel(snC2[N0 // 4], lowpass_hat(snA[N0 // 4], NC) * sC2.mask), "note": "reported, no threshold; the N-grid field is low-passed to NC and masked with the NC 2/3 dealiasing mask"}
    R["total_wall_s"] = round(time.time() - T0, 1)
    save()
print("DONE", json.dumps({k: R[k] for k in R if k.startswith("P")}, default=str)[:600], flush=True)
