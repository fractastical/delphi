"""Controls of PROTOCOL.md: Poiseuille profile, Taylor-Green viscous decay, mass conservation, grid refinement. Usage: python3 -m engineering.flow.controls OUT.json [device]"""

from __future__ import annotations

import json
import math
import sys
import time

import numpy as np
import torch

from .lbm import LBM


def poiseuille(H, tau=0.8, umax=0.02, device="cpu"):
    ny = H + 2
    solid = torch.zeros(4, ny, dtype=torch.bool)
    solid[:, 0] = True
    solid[:, -1] = True
    nu = (tau - 0.5) / 3
    F = 8 * nu * umax / H**2  # u_max = F H^2 / (8 nu)
    L = LBM(4, ny, tau, solid=solid, force=(F, 0.0), device=device)
    L.init()
    m0 = L.total_mass()
    nsteps = int(6 * H * H / nu)
    for _ in range(nsteps):
        L.step()
    rho, ux, uy = L.macro()
    prof = ux[1, 1:-1].cpu().numpy()
    y = np.arange(1, ny - 1) - 0.5  # distance from the lower wall at y = 1/2
    exact = F / (2 * nu) * y * (H - y)
    err = float(np.linalg.norm(prof - exact) / np.linalg.norm(exact))
    return {
        "H": H,
        "tau": tau,
        "steps": nsteps,
        "rel_L2_error": err,
        "mass_drift": abs(L.total_mass() - m0) / m0,
        "u_max_numeric": float(prof.max()),
        "u_max_exact": float(exact.max()),
        "transverse_velocity_max": float(uy.abs().max()),
    }


def taylor_green(N, tau=0.8, U0=0.02, device="cpu"):
    nu = (tau - 0.5) / 3
    k = 2 * math.pi / N
    x = (torch.arange(N, dtype=torch.float64) + 0.5)[:, None].expand(N, N)
    y = (torch.arange(N, dtype=torch.float64) + 0.5)[None, :].expand(N, N)
    ux = -U0 * torch.cos(k * x) * torch.sin(k * y)
    uy = U0 * torch.sin(k * x) * torch.cos(k * y)
    L = LBM(N, N, tau, device=device)
    L.init(1.0, ux, uy)
    m0 = L.total_mass()
    T = int(0.7 / (2 * nu * k * k))  # amplitude decays to about 0.5
    amp = []
    steps = [0, T // 4, T // 2, 3 * T // 4, T]
    cur = 0
    for s in steps:
        while cur < s:
            L.step()
            cur += 1
        rho, a, b = L.macro()
        amp.append(float(torch.sqrt((a * a + b * b).mean())))
    t = np.array(steps, float)
    rate = -np.polyfit(t, np.log(np.array(amp)), 1)[
        0
    ]  # decay rate of the rms speed = 2 nu k^2 for TG
    nu_eff = rate / (2 * k * k)
    return {
        "N": N,
        "tau": tau,
        "steps": T,
        "nu_exact": nu,
        "nu_eff": float(nu_eff),
        "nu_rel_error": abs(nu_eff - nu) / nu,
        "mass_drift": abs(L.total_mass() - m0) / m0,
        "amp_ratio": amp[-1] / amp[0],
    }


def run(out, device="cpu"):
    t0 = time.time()
    P = [poiseuille(H, device=device) for H in (16, 32, 64)]
    TG = [taylor_green(N, device=device) for N in (32, 64, 128)]
    e = [p["rel_L2_error"] for p in P]
    order = math.log(e[0] / e[2]) / math.log(64 / 16)
    ok = {
        "C1_poiseuille_err_H64_le_1e-3": bool(e[2] <= 1e-3),
        "C1_monotone": bool(e[0] > e[1] > e[2]),
        "C1_order_ge_1.5": bool(order >= 1.5),
        "C2_nu_err_N128_le_1e-2": bool(TG[2]["nu_rel_error"] <= 1e-2),
        "C2_monotone": bool(
            TG[0]["nu_rel_error"] > TG[1]["nu_rel_error"] > TG[2]["nu_rel_error"]
        ),
        "C3_mass_drift_le_1e-10": bool(
            max([p["mass_drift"] for p in P] + [t["mass_drift"] for t in TG]) <= 1e-10
        ),
    }
    res = {
        "poiseuille": P,
        "poiseuille_observed_order_H16_to_H64": order,
        "taylor_green": TG,
        "checks": ok,
        "all_pass": all(ok.values()),
        "device": device,
        "seconds": time.time() - t0,
        "torch": torch.__version__,
    }
    open(out, "w").write(json.dumps(res, indent=1))
    print(
        json.dumps(
            {
                "checks": ok,
                "order": order,
                "poiseuille_err": e,
                "tg_err": [t["nu_rel_error"] for t in TG],
                "seconds": res["seconds"],
            }
        )
    )
    return res


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "cpu")
