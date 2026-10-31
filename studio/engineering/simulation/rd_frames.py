"""Bounded RERUN of two cells of the frozen delphi-evolve nonlinear sweep with every saved state kept (the sweep itself saved only final states).
Solver A of that protocol (Strang splitting, exact cosine-mode diffusion via an orthonormal DCT-II matrix, RK4 reaction, dt_tau 0.02, 1-D zero-flux),
re-implemented here as pinned-source reuse (origin: kganjam/delphi-evolve work/rethink-nca scopedesk/oracles/nonlinear_sweep, prereg cb27cf2; same licence as that repo).
A receipt compares the rerun's final dominant mode and amplitude with the frozen sweep row; saved fields are float64 at every 2 tau; nothing is interpolated.
RD model time tau = gamma*t is DIMENSIONLESS reaction-diffusion model time and has no relation to glide seconds. Evidence kind: simulated.
Usage: python3 -m engineering.simulation.rd_frames OUTDIR"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from fractions import Fraction as F
from pathlib import Path

import numpy as np
from scipy.fft import dct

SAVE_EVERY_TAU = 2.0


def steady(model, p):
    if model == "schnakenberg":
        a, b = p["a"], p["b"]
        return a + b, b / (a + b) ** 2
    return p["A"], p["B"] / p["A"]


def react(model, p, u, v):
    w = u * u * v
    if model == "schnakenberg":
        return p["a"] - u + w, p["b"] - w
    return p["A"] - (p["B"] + 1) * u + w, p["B"] * u - w


def ic_modal(seed, K, L, N, amp_u, amp_v):
    rng = np.random.default_rng(seed)
    cu, cv = rng.standard_normal(K), rng.standard_normal(K)
    x = (np.arange(N) + 0.5) * L / N
    M = np.cos(np.outer(x, np.arange(1, K + 1)) * math.pi / L)
    return [amp * (M @ c) / math.sqrt(0.5 * float(np.sum(c * c))) for c, amp in ((cu, amp_u), (cv, amp_v))]


def dominant_mode(u):
    c = np.abs(dct(u - u.mean(), type=2, norm="ortho"))
    c[0] = 0
    return int(c.argmax())


def run_cell(c, dt=0.02, save_every=SAVE_EVERY_TAU):
    p = {k: float(F(v)) for k, v in c["params"].items()}
    model, N, L, K, T = c["model"], c["NA"], c["L"], c["K"], c["T_tau"]
    ust, vst = steady(model, p)
    pu, pv = ic_modal(c["seed"], K, L, N, c["eps"] * abs(ust), c["eps"] * abs(vst))
    u, v = ust + pu, vst + pv
    D = dct(np.eye(N), type=2, norm="ortho", axis=0)
    q = (np.arange(N) * math.pi / L) ** 2
    mu, mv = np.exp(-q * dt / 2), np.exp(-float(F(c["Dv"])) * q * dt / 2)
    dif = lambda x, m: ((x @ D.T) * m) @ D
    n = int(round(T / dt)); every = int(round(save_every / dt))
    times, U, V = [0.0], [u.copy()], [v.copy()]
    for k in range(1, n + 1):
        u, v = dif(u, mu), dif(v, mv)
        k1u, k1v = react(model, p, u, v)
        k2u, k2v = react(model, p, u + .5 * dt * k1u, v + .5 * dt * k1v)
        k3u, k3v = react(model, p, u + .5 * dt * k2u, v + .5 * dt * k2v)
        k4u, k4v = react(model, p, u + dt * k3u, v + dt * k3v)
        u = u + dt / 6 * (k1u + 2 * k2u + 2 * k3u + k4u); v = v + dt / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)
        u, v = dif(u, mu), dif(v, mv)
        if k % every == 0:
            times.append(k * dt); U.append(u.copy()); V.append(v.copy())
    return np.array(times), np.array(U), np.array(V), ust


def main(outdir):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    doc = json.loads((Path(__file__).parent / "rd" / "cells.json").read_text())
    receipts = []
    for c in doc["cells"]:
        t0 = time.time()
        t, U, V, ust = run_cell(c)
        final = U[-1]
        ref = c["reference_row"]["A"]
        mode, amp = dominant_mode(final), float(final.std())
        mode90 = dominant_mode(U[int(0.9 * (len(U) - 1))])
        f = out / f"cell_{c['cell_id']}_frames.npz"
        np.savez_compressed(f, t_tau=t, u=U, v=V, x_m=(np.arange(c["NA"]) + 0.5) * c["L"] / c["NA"], u_star=ust)
        receipts.append({"cell_id": c["cell_id"], "label": c["label"], "frames_file": f.name, "frames_sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "n_frames": len(t),
                         "save_every_tau": SAVE_EVERY_TAU, "T_tau": c["T_tau"], "dt_tau": 0.02, "N": c["NA"], "L_length_units": c["L"],
                         "rerun_final": {"mode": mode, "amp_std_u": amp, "mode_at_0.9T": mode90},
                         "frozen_sweep_row_A": {k: ref[k] for k in ("mode", "amp", "pattern", "settled")},
                         "reproduces_frozen_row": bool(mode == ref["mode"] and abs(amp - ref["amp"]) / ref["amp"] < 1e-6),
                         "relative_amp_difference": abs(amp - ref["amp"]) / ref["amp"], "seconds": time.time() - t0})
    rc = {"kind": "RD field time-series rerun", "evidence_kind": "simulated", "source": doc["source"], "cells": receipts, "tau_note": "tau = gamma t is dimensionless RD model time; unrelated to glide seconds; no coupling",
          "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "cells_json_sha256": hashlib.sha256((Path(__file__).parent / "rd" / "cells.json").read_bytes()).hexdigest()}
    (out / "receipt.json").write_text(json.dumps(rc, indent=1))
    print(json.dumps([{k: r[k] for k in ("cell_id", "reproduces_frozen_row", "relative_amp_difference", "n_frames", "seconds")} for r in receipts]))


if __name__ == "__main__":
    main(sys.argv[1])
