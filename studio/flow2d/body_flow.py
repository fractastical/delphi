"""Rigid body in a uniform stream on the periodic spectral solver with volume penalization (flow2d.penalized). Records the penalization force (fluid force on the body) every step.
Default body: a disk (diameter D = 2r) at Re = U D / nu. A different rigid body enters ONLY as a mask array (--mask-npy, shape N x N, values 0..1, 1 inside), whose provenance the caller owns.
Usage: python3 flow2d/body_flow.py OUT_DIR --N 256 --T 100 --dt 0.01 [--re 100] [--r 0.25] [--frames 72] [--tag NAME]
Evidence kind: simulated. Output: OUT_DIR/<tag>_series.npz (t, Fx, Fy), <tag>_summary.json, optional <tag>_frames_q8.npz."""
import argparse, json, math, os, sys, time
import numpy as np
import torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flow2d.penalized import NS2DPen, disk_mask


def run(N, T, dt, re=100.0, r=0.25, eta=1e-3, device="cpu", frames=0, mask=None, cx=None, cy=None, seed=1, log=None):
    D, U = 2 * r, 1.0
    nu = U * D / re
    dx = 2 * math.pi / N
    cx = math.pi / 2 if cx is None else cx
    cy = (math.pi + 0.3 * dx) if cy is None else cy            # slight off-grid offset breaks the up/down symmetry so shedding can start
    chi = disk_mask(N, cx, cy, r) if mask is None else torch.as_tensor(mask, dtype=torch.float64)
    s = NS2DPen(N, nu, dt, chi, eta=eta, U0=(U, 0.0), device=device, dynamic_mean=False)
    g = torch.Generator().manual_seed(seed)
    w0 = 1e-3 * torch.randn(N, N, generator=g, dtype=torch.float64)       # tiny seeded noise (shedding trigger); zero-mean after dealiasing
    wh = s.to_hat(w0.to(device))
    n = int(round(T / dt)); every = max(1, n // frames) if frames else 0
    Fx, Fy, fr, ft = np.zeros(n), np.zeros(n), [], []
    t0 = time.time()
    for k in range(n):
        wh = s.step(wh)
        Fx[k], Fy[k] = s.last_force
        if every and ((k + 1) % every == 0):
            c = torch.fft.fftshift(wh) / N ** 2; h = 64; c0 = N // 2
            fr.append(torch.fft.ifft2(torch.fft.ifftshift(c[c0 - h:c0 + h, c0 - h:c0 + h] * 128 ** 2)).real.cpu().numpy().astype(np.float32)); ft.append((k + 1) * dt)
        if log and (k + 1) % 2000 == 0:
            log(f"step {k + 1}/{n} wall {time.time() - t0:.0f}s")
    if device == "cuda":
        torch.cuda.synchronize()
    t = (np.arange(n) + 1) * dt
    return t, Fx, Fy, (np.array(ft), np.stack(fr) if fr else None), {"N": N, "T": T, "dt": dt, "Re": re, "D": D, "nu": nu, "eta": eta, "wall_s": round(time.time() - t0, 1), "finite": bool(np.isfinite(Fx).all() and np.isfinite(Fy).all())}


def analyse(t, Fx, Fy, D, U=1.0, frac=0.5):
    """Cd from the mean streamwise force, Cl rms, Strouhal from the dominant lift frequency over the last (1-frac) of the record (needs >= 6 shedding periods)."""
    m = t >= t[0] + frac * (t[-1] - t[0])
    cd = 2 * Fx[m].mean() / (U ** 2 * D)
    y = Fy[m] - Fy[m].mean(); dt = t[1] - t[0]
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y)))); fr = np.fft.rfftfreq(len(y), dt)
    spec[0] = 0; k = int(spec.argmax())
    if 0 < k < len(spec) - 1:                                  # parabolic peak interpolation
        a, b, c = np.log(spec[k - 1] + 1e-300), np.log(spec[k] + 1e-300), np.log(spec[k + 1] + 1e-300)
        dlt = 0.5 * (a - c) / (a - 2 * b + c); f = fr[k] + dlt * (fr[1] - fr[0])
    else:
        f = fr[k]
    return {"Cd_mean": float(cd), "Cl_rms": float(2 * y.std() / (U ** 2 * D)), "St": float(f * D / U), "f_shed": float(f), "n_periods_in_window": float(f * (t[m][-1] - t[m][0])), "window": [float(t[m][0]), float(t[m][-1])]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--N", type=int, default=256); ap.add_argument("--T", type=float, default=100.0); ap.add_argument("--dt", type=float, default=0.01)
    ap.add_argument("--re", type=float, default=100.0); ap.add_argument("--r", type=float, default=0.25); ap.add_argument("--frames", type=int, default=0); ap.add_argument("--tag", default="run")
    ap.add_argument("--device", default="cpu"); ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args(); torch.set_num_threads(a.threads); os.makedirs(a.out, exist_ok=True)
    t, Fx, Fy, (ft, fr), meta = run(a.N, a.T, a.dt, a.re, a.r, device=a.device, frames=a.frames, log=lambda s: print(s, flush=True))
    res = {**meta, **analyse(t, Fx, Fy, meta["D"])}
    np.savez_compressed(os.path.join(a.out, f"{a.tag}_series.npz"), t=t, Fx=Fx, Fy=Fy)
    if fr is not None:
        np.savez_compressed(os.path.join(a.out, f"{a.tag}_frames.npz"), t=ft, w=fr)
    json.dump(res, open(os.path.join(a.out, f"{a.tag}_summary.json"), "w"), indent=1, allow_nan=False); print(json.dumps(res, indent=1))
