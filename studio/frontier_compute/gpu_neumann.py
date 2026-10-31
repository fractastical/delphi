"""Batched GPU/CPU replication of NCA solver A (scopedesk.oracles.pde._run, 1-D Neumann, cell-centred).

Same scheme: Strang splitting, EXACT cosine-mode diffusion (orthonormal DCT-II, here applied as a dense matrix product so that cells
with DIFFERENT grid sizes batch together by zero-padding), RK4 reaction substeps, dt fixed, float64. Reaction terms come from the
vendored, previously validated pde_oracle.solver.reaction. Adjacent half-diffusions are merged (identical in exact arithmetic).
Event handling mirrors NCA exactly: snapshot after step round(0.9*n); divergence checked after step k when k%200==0 (k 0-based).
All outputs are SIMULATED (declared model).
"""
from __future__ import annotations

import math
import time
from fractions import Fraction as F

import numpy as np
import torch

from . import VENDOR  # noqa: F401
from pde_oracle.solver import reaction
from scopedesk.oracles import kinetics
from scopedesk.oracles.nonlinear_sweep import solvers as S


def dct2_matrix(N, dtype=np.float64):
    k = np.arange(N)[:, None]
    j = np.arange(N)[None, :]
    C = np.cos(np.pi * k * (j + 0.5) / N) * np.sqrt(2.0 / N)
    C[0, :] = np.sqrt(1.0 / N)
    return C.astype(dtype)


def simulate(cells, dt=0.02, grid_factor=1, device="cuda", deadline=None, log=print, check_every=200, perturb=0.0, frame_ids=(), nframes=0):
    """cells: list of derived cell dicts (one model). Returns list of per-cell result dicts (same order).
    grid_factor=2 doubles the number of cells per side (spatial-refinement arm). dt may be halved by the caller."""
    model = cells[0]["model"]
    assert all(c["model"] == model for c in cells)
    B = len(cells)
    Ns = [c["NA"] * grid_factor for c in cells]
    Nmax = max(Ns)
    pps = [kinetics.params(c["model"], c["params"]) for c in cells]
    steady = [tuple(float(z) for z in kinetics.steady(model, pp)) for pp in pps]
    dtype = torch.float64
    Cm = np.zeros((B, Nmax, Nmax))
    q = np.zeros((B, Nmax))
    X0 = np.zeros((B, Nmax, 2))
    for i, c in enumerate(cells):
        N = Ns[i]
        Cm[i, :N, :N] = dct2_matrix(N)
        q[i, :N] = (np.arange(N) * math.pi / c["L"]) ** 2
        ust, vst = steady[i]
        pu, pv = S.ic_modal(c["seed"], c["K"], c["L"], N, c["eps"] * abs(ust), c["eps"] * abs(vst))
        X0[i, :N, 0] = ust + pu
        X0[i, :N, 1] = vst + pv
    if perturb:      # stability control: relative multiplicative noise on the initial state, fixed per cell id, applied identically to u and v entries
        for i, c in enumerate(cells):
            rg = np.random.default_rng(10 ** 6 + int(c["id"]))
            X0[i, :Ns[i], :] *= 1.0 + perturb * rg.standard_normal((Ns[i], 2))
    Dv = np.array([float(F(c["Dv"])) for c in cells])
    mh = np.stack([np.exp(-1.0 * q * dt / 2), np.exp(-Dv[:, None] * q * dt / 2)], axis=-1)       # (B,Nmax,2); padded q=0 -> 1 but C is 0 there
    mask = np.zeros((B, Nmax))
    for i, N in enumerate(Ns):
        mask[i, :N] = 1.0
    T = lambda a: torch.tensor(a, dtype=dtype, device=device)   # noqa: E731
    Cmat, CmatT = T(Cm), T(Cm).transpose(1, 2).contiguous()
    MH = T(mh)
    MF = MH * MH
    MASK = T(mask)
    P = {}
    for key in pps[0]:
        P[key] = T(np.array([float(pp[key]) for pp in pps]))
    X = T(X0)

    def diff(X, M):
        return torch.bmm(CmatT, torch.bmm(Cmat, X) * M)

    def rk4(X):
        u, v = X[..., 0], X[..., 1]
        f = lambda a, b: reaction(model, a, b, P, 1)          # noqa: E731
        k1u, k1v = f(u, v)
        k2u, k2v = f(u + .5 * dt * k1u, v + .5 * dt * k1v)
        k3u, k3v = f(u + .5 * dt * k2u, v + .5 * dt * k2v)
        k4u, k4v = f(u + dt * k3u, v + dt * k3v)
        return torch.stack([u + dt / 6 * (k1u + 2 * k2u + 2 * k3u + k4u), v + dt / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)], dim=-1)

    n_i = [int(round(c["T"] / dt)) for c in cells]
    chk_i = [int(round(0.9 * n)) for n in n_i]
    nmax = max(n_i)
    frame_steps = {}
    for i, c in enumerate(cells):
        if c["id"] in set(frame_ids) and nframes:
            frame_steps[i] = sorted({int(round(n_i[i] * k / (nframes - 1))) for k in range(nframes)} - {0})
    frames = {i: [] for i in frame_steps}
    ev = set(chk_i) | set(n_i) | set(range(1, nmax + 1, check_every)) | {st for v in frame_steps.values() for st in v}
    ev_steps = sorted(s for s in ev if s <= nmax)
    snap, final, finalv = {}, {}, {}
    diverged = [False] * B
    series = [[] for _ in range(B)]
    series_t = []
    n_t = torch.tensor(n_i, device=device)
    t0 = time.time()
    Y = diff(X, MH)                           # leading half-diffusion
    ev_set = set(ev_steps)
    timed_out = False
    for s in range(1, nmax + 1):
        Xr = rk4(Y)
        if s in ev_set:
            Sx = diff(Xr, MH)                 # NCA state after step s (trailing half-diffusion applied)
            m = torch.maximum(Sx[..., 0].abs().amax(1), Sx[..., 1].abs().amax(1))
            fin = torch.isfinite(Sx).all(dim=2).all(dim=1)
            bad = (~fin) | (m > 1e3)
            if (s - 1) % check_every == 0:
                for i in range(B):
                    if n_i[i] >= s and bool(bad[i]):
                        diverged[i] = True
                sd = []
                U = Sx[..., 0].cpu().numpy()
                for i in range(B):
                    sd.append(float(np.std(U[i, :Ns[i]])) if np.isfinite(U[i, :Ns[i]]).all() else float("nan"))
                series_t.append(s * dt)
                for i in range(B):
                    series[i].append(sd[i])
            Sn = Sx.cpu().numpy()
            for i, sts in frame_steps.items():
                if s in sts:
                    frames[i].append((s * dt, Sn[i, :Ns[i], 0].astype(np.float32)))
            for i in range(B):
                if chk_i[i] == s:
                    snap[i] = Sn[i, :Ns[i], 0].copy()
                if n_i[i] == s:
                    final[i] = Sn[i, :Ns[i], 0].copy()
                    finalv[i] = Sn[i, :Ns[i], 1].copy()
            Y = diff(Sx, MH)
            if deadline is not None and time.time() > deadline:
                timed_out = True
                log(f"deadline reached at step {s}/{nmax}")
                break
        else:
            Y = diff(Xr, MF)
    wall = time.time() - t0
    out = []
    for i, c in enumerate(cells):
        r = {"id": c["id"], "N": Ns[i], "dt": dt, "n_steps": n_i[i], "diverged": bool(diverged[i]) or i not in final, "out_of_budget": timed_out and i not in final}
        if i in final and not diverged[i]:
            ust = steady[i][0]
            r.update(S.metrics(final[i], snap[i], ust))
            r["u_final"] = final[i]
            r["v_final"] = finalv[i]
            r["u_snap"] = snap[i]
        if i in frames and frames[i]:
            r["frame_t"] = np.array([t for t, _ in frames[i]])
            r["frames_u"] = np.stack([f for _, f in frames[i]])
        r["std_series"] = series[i]
        r["ust"] = steady[i][0]
        out.append(r)
    return out, {"wall_s": wall, "steps": nmax, "B": B, "Nmax": Nmax, "series_t": series_t, "timed_out": timed_out}
