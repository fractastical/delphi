"""GPU job entry: (1) controls on the GPU (Taylor-Green + mean flow exact solution; cross-check against the CPU run), (2) dt-halving and grid checks,
(3) the demo: doubly periodic double shear layer at N x N, float64, frames of the actual vorticity (spectrally low-passed to 128x128, 8-bit) and diagnostics.
Output in $COPS_OUT. Env: FLOW_N (2048), FLOW_T (8.0), FLOW_NU (1e-4), FLOW_DT (1.2e-3), FLOW_NFRAMES (72), FLOW_BUDGET_S (1500)."""
import json, math, os, sys, time
import numpy as np
import torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flow2d.solver import NS2D, tg_exact, shear_layer_w0, rand_w0
from frontier_compute.telemetry import Telemetry

OUT = os.environ.get("COPS_OUT", ".")
N = int(os.environ.get("FLOW_N", "2048")); T = float(os.environ.get("FLOW_T", "8.0")); NU = float(os.environ.get("FLOW_NU", "1e-4"))
DT = float(os.environ.get("FLOW_DT", "1.2e-3")); NF = int(os.environ.get("FLOW_NFRAMES", "72")); BUDGET = float(os.environ.get("FLOW_BUDGET_S", "1500"))
NC = int(os.environ.get("FLOW_CHK_N", "512")); TC = float(os.environ.get("FLOW_CHK_T", "2.0"))
dev = "cuda" if torch.cuda.is_available() else "cpu"
T0 = time.time()
if os.environ.get("PREFLIGHT"):
    np.load("flow2d/flow_cpu_ref_rand64.npy"); print("preflight ok: imports and reference file"); sys.exit(0)
R = {"check_grid": [NC, 2 * NC], "check_T": TC, "device": dev, "torch": torch.__version__, "params": {"N": N, "T": T, "nu": NU, "dt": DT, "nframes": NF}}
if dev == "cuda":
    R["gpu"] = torch.cuda.get_device_name(0)


def sync():
    if dev == "cuda":
        torch.cuda.synchronize()


def save():
    json.dump(R, open(os.path.join(OUT, "flow_results.json"), "w"), indent=1, default=str, allow_nan=False)


def advance(s, wh, n):
    for _ in range(n):
        wh = s.step(wh)
    return wh


def lowpass(wh, n_out=128):
    N_ = wh.shape[0]
    h = n_out // 2
    c = torch.fft.fftshift(wh) / N_ ** 2
    c0 = N_ // 2
    sub = c[c0 - h:c0 + h, c0 - h:c0 + h] * n_out ** 2
    return torch.fft.ifft2(torch.fft.ifftshift(sub)).real


def run_shear(Nn, dt, Tend, nu, store=False):
    s = NS2D(Nn, nu, dt, device=dev)
    X, Y = s.grid()
    wh = s.to_hat(shear_layer_w0(X, Y))
    n = int(round(Tend / dt))
    return s, wh, n


with Telemetry(OUT, max_s=int(BUDGET) + 600):
    # ---- 1. GPU controls
    nu_c, U0 = 0.01, (1.0, 0.5)
    NTG = int(os.environ.get("FLOW_TG_N", "512"))
    s = NS2D(NTG, nu_c, 0.01, device=dev, U0=U0)
    X, Y = s.grid()
    wh = advance(s, s.to_hat(tg_exact(X, Y, 0.0, nu_c, U0)), 100); sync()
    err_tg = float((torch.fft.ifft2(wh).real - tg_exact(X, Y, 1.0, nu_c, U0)).abs().max())
    s64 = NS2D(64, nu_c, 0.01, device=dev)
    w64 = torch.fft.ifft2(advance(s64, s64.to_hat(rand_w0(64).to(dev)), 50)).real.cpu().numpy()
    cpu_ref = np.load("flow2d/flow_cpu_ref_rand64.npy")
    R["controls_gpu"] = {f"taylor_green_mean_flow_max_err_N{NTG}": err_tg, "gpu_vs_cpu_nonlinear_N64_max_abs_diff": float(np.abs(w64 - cpu_ref).max()),
                         "cpu_ref_sha_note": "flow_cpu_ref_rand64.npy produced by flow2d/controls.py (CPU)"}
    save()
    # ---- 2. dt-halving and grid checks (shear layer, N=512 vs 1024, to T=2)
    chk = {}
    s, wh, n = run_shear(NC, 2 * DT, TC, NU)
    wA = advance(s, wh, n)
    s2, wh2, n2 = run_shear(NC, DT, TC, NU)
    wB = advance(s2, wh2, n2)
    d = lambda a, b: float(torch.linalg.norm(torch.fft.ifft2(a).real - torch.fft.ifft2(b).real) / torch.linalg.norm(torch.fft.ifft2(b).real))
    chk[f"dt_halving_N{NC}_T{TC}_rel_L2"] = d(wA, wB)
    s3, wh3, n3 = run_shear(2 * NC, DT, TC, NU)
    wC = advance(s3, wh3, n3)
    # compare N=512 and N=1024 by projecting the 1024 field onto the 512 grid (low-pass, same normalization)
    c = torch.fft.fftshift(wC) / (2 * NC) ** 2; c0 = NC; h = NC // 2
    wC512 = torch.fft.ifft2(torch.fft.ifftshift(c[c0 - h:c0 + h, c0 - h:c0 + h] * NC ** 2))
    wB_ = torch.fft.ifft2(wB).real
    chk[f"grid_N{NC}_vs_N{2*NC}_T{TC}_rel_L2"] = float(torch.linalg.norm(wB_ - wC512.real) / torch.linalg.norm(wC512.real))
    sync(); R["convergence_checks"] = chk; save()
    # ---- 3. demo
    s = NS2D(N, NU, DT, device=dev)
    X, Y = s.grid()
    wh = s.to_hat(shear_layer_w0(X, Y))
    n = int(round(T / DT))
    every = max(1, n // NF)
    frames, ftimes, series = [], [], []
    t_demo = time.time()
    E0 = s.diag(wh)["E"]
    stopped = None
    for k in range(1, n + 1):
        wh = s.step(wh)
        if k % every == 0 or k == n:
            sync()
            dg = s.diag(wh)
            dg.update(t=k * DT, cfl=dg["umax"] * DT / (2 * math.pi / N), step=k, wall_s=round(time.time() - t_demo, 1))
            series.append(dg)
            frames.append(lowpass(wh).cpu().numpy().astype(np.float32)); ftimes.append(k * DT)
            if not math.isfinite(dg["E"]) or dg["umax"] > 50:
                stopped = {"step": k, "reason": "non-finite or umax>50"}; break
            if time.time() - T0 > BUDGET:
                stopped = {"step": k, "reason": "wall budget"}; break
    sync()
    # energy budget: E(t_end) - E(0) vs -2 nu int Z dt (trapezoid on the sampled Z; coarse by construction)
    ts = [0.0] + [d_["t"] for d_ in series]; Zs = [s.diag(s.to_hat(shear_layer_w0(X, Y)))["Z"]] + [d_["Z"] for d_ in series]
    integ = sum(0.5 * (Zs[i] + Zs[i + 1]) * (ts[i + 1] - ts[i]) for i in range(len(ts) - 1))
    Eend = series[-1]["E"]
    wh_abs = wh.abs() ** 2
    k_ = torch.sqrt(s.k2)
    hi = float(wh_abs[k_ > 0.66 * (N // 3)].sum() / wh_abs.sum())
    R["demo"] = {"n_steps_done": series[-1]["step"], "n_steps_planned": n, "stopped": stopped, "wall_s": round(time.time() - t_demo, 1), "E0": E0, "E_end": Eend,
                 "energy_budget_residual_rel": ((Eend - E0) - (-2 * NU * integ)) / abs(Eend - E0) if Eend != E0 else None,
                 "max_cfl": max(d_["cfl"] for d_ in series), "max_divergence": max(d_["divmax"] for d_ in series),
                 "enstrophy_end": series[-1]["Z"], "spectral_fraction_of_enstrophy_above_0.66kmax_at_end": hi,
                 "frames": len(frames), "frame_resolution": 128, "frame_note": "actual vorticity, spectrally low-passed to 128x128 for return; the run used N x N", "series": series}
    fr = np.stack(frames)
    vmax = float(np.percentile(np.abs(fr), 99.5))
    q = np.clip((fr / vmax + 1) * 127.5, 0, 255).astype(np.uint8)
    np.savez_compressed(os.path.join(OUT, "flow_frames_q8.npz"), q=q, t=np.array(ftimes), vmax=vmax, N=N, nu=NU, dt=DT)
    R["demo"]["frame_quantization"] = {"vmax_abs_vorticity_clip_99.5pct": vmax, "levels": 256, "mapping": "q = clip((w/vmax + 1)*127.5, 0, 255)"}
    R["total_wall_s"] = round(time.time() - T0, 1)
    save()
print("DONE", json.dumps({k: R[k] for k in ("controls_gpu", "convergence_checks")}, default=str)[:500], flush=True)
