"""Independent numpy re-implementation of SPM's DEM_morphogenesis.m (Friston, Levin, Sengupta &
Pezzulo 2015, "Knowing one's place").

The generative model, generative process, precisions, time ramp, initial conditions and split-half
procedure follow DEM_morphogenesis.m (SPM12 r7679, identical logic on spm/spm main). Integration is
not spm_ADEM's generalised filter: within each of the N time bins, internal states (identity
expectations v) and action (positions a.x, released signals a.s) follow the gradient flow of the
Laplace free energy for one unit of time (spm_ADEM's dt = 1), with Euler sub-steps. Generalised
motion (embedding order 2) is dropped because the model has a point attractor.
"""

import hashlib
import itertools
import json
import re
import time
import urllib.request
from pathlib import Path

import numpy as np

SOURCES = {
    "spm12": "https://raw.githubusercontent.com/spm/spm12/main/toolbox/DEM/DEM_morphogenesis.m",
    "spm-main": "https://raw.githubusercontent.com/spm/spm/main/toolbox/DEM/DEM_morphogenesis.m",
    "spm12-adem": "https://raw.githubusercontent.com/spm/spm12/main/spm_ADEM.m",
}

LOG_PI_Y = 3.0     # M(1).V = exp(3): sensory precision of the model
LOG_PI_V = -2.0    # M(2).V = exp(-2): prior precision on identity causes
LOG_PI_A = 2.0     # G(1).U = exp(2): precision used for action
N_BINS = 32        # N = 32
SUBSTEPS = 200


def fetch_sources(cache=Path("/tmp/delphi-spm-morphogenesis")):
    cache.mkdir(parents=True, exist_ok=True)
    records, texts = {}, {}
    for key, url in SOURCES.items():
        path = cache / f"{key}.m"
        if not path.exists():
            with urllib.request.urlopen(url, timeout=60) as r:
                path.write_bytes(r.read())
            retrieved = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        else:
            retrieved = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime))
        data = path.read_bytes()
        records[key] = {"download_url": url, "retrieved_at": retrieved, "byte_size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()}
        texts[key] = data.decode("utf-8", "replace")
    return records, texts


def parse_demo(text):
    """Target matrix T for L == 2 and the SPLIT / N defaults, read from DEM_morphogenesis.m."""
    split = int(re.search(r"^SPLIT\s*=\s*(\d+)", text, re.M).group(1))
    nbins = int(re.search(r"^N\s*=\s*(\d+)", text, re.M).group(1))
    level = int(re.search(r"^L\s*=\s*(\d+)", text, re.M).group(1))
    block = re.search(r"if L == 2\s*\n\s*T\s*=\s*\[(.*?)\];", text, re.S).group(1)
    T = np.array([[int(v) for v in row.split()] for row in block.strip().split(";")])
    header_cells = re.findall(r"of (\d+) cells", text)
    return {"SPLIT": split, "N": nbins, "L": level, "T": T, "header_cells": header_cells}


def softmax(v):
    e = np.exp(v - v.max(axis=0, keepdims=True))
    return e / e.sum(axis=0, keepdims=True)


def sensed(x, s, y=None, k=1.0):
    """morphogenesis(): signal at sample locations y from cells at x releasing s."""
    y = x if y is None else y
    d = np.sqrt(((y[:, :, None] - x[:, None, :]) ** 2).sum(0))
    return s @ np.exp(-k * d).T


class Target:
    def __init__(self, T):
        p = np.stack([T > 0, (T == 2) | (T == 1), (T == 3) | (T == 1), T == 4], axis=2)
        rows, cols = np.nonzero(p[:, :, 0].T)   # MATLAB find is column-major
        cols, rows = rows, cols
        xy = np.stack([cols + 1, rows + 1]).astype(float)
        self.X = (xy - xy.mean(axis=1, keepdims=True)) / 2       # P.x
        self.S = np.stack([p[rows, cols, i] for i in range(4)]).astype(float)  # P.s
        self.C = sensed(self.X, self.S)                           # P.c
        self.type = T[rows, cols]
        self.n = self.X.shape[1]
        d = np.sqrt(((self.X[:, :, None] - self.X[:, None, :]) ** 2).sum(0))
        self.min_spacing = d[~np.eye(self.n, dtype=bool)].min()
        self.perms = np.array(list(itertools.permutations(range(self.n))))


def ramp(step, nbins=N_BINS):
    return 1.0 - np.exp(-2.0 * step / nbins)


def free_energy(tg, v, ax, as_, sig):
    """spm_ADEM's -J at one bin (static terms): E'iS E/2 - logdet(qu.c) - logdet(iS)/2."""
    n = tg.n
    W = np.vstack([tg.X, tg.S, sig * tg.C])
    p = softmax(v)
    y = np.vstack([ax, as_, sig * sensed(ax, as_)])
    eps = y - W @ p
    pi_y, pi_v = np.exp(LOG_PI_Y), np.exp(LOG_PI_V)
    F = 0.5 * pi_y * (eps ** 2).sum() + 0.5 * pi_v * (v ** 2).sum()
    logdet_H = 0.0
    for i in range(n):
        Jg = W @ (np.diag(p[:, i]) - np.outer(p[:, i], p[:, i]))
        H = pi_y * Jg.T @ Jg + pi_v * np.eye(n)
        logdet_H += np.linalg.slogdet(H)[1]
    logdet_iS = W.shape[0] * n * LOG_PI_Y + n * n * LOG_PI_V
    return F + logdet_H - 0.5 * logdet_iS


def flow(tg, v, ax, as_, sig, substeps=SUBSTEPS, noise=None):
    """Gradient flow of free energy for one time unit (one bin). `noise` (10 x n) is sensory
    noise of the generative process, held for the bin (G(1).V = exp(16) in the SPM file)."""
    pi_y, pi_v, pi_a = np.exp(LOG_PI_Y), np.exp(LOG_PI_V), np.exp(LOG_PI_A)
    W = np.vstack([tg.X, tg.S, sig * tg.C])
    h = 1.0 / substeps
    z = 0.0 if noise is None else noise
    for _ in range(substeps):
        p = softmax(v)
        diff = ax[:, :, None] - ax[:, None, :]                 # 2 x n x n
        d = np.sqrt((diff ** 2).sum(0) + 1e-12)
        K = np.exp(-d)
        c = as_ @ K.T
        eps = np.vstack([ax, as_, sig * c]) + z - W @ p        # 10 x n
        ex, es, ec = eps[:2], eps[2:6], eps[6:]
        # internal states: dv/dt = -dF/dv
        g = W.T @ eps                                          # n x n (identity k, cell i)
        dv = pi_y * (p * g - p * (p * g).sum(0, keepdims=True)) - pi_v * v
        # action restricted to each cell's own sensations: da/dt = -U (dy_i/da_i)' eps_i
        # dc_i/dx_i = -sum_j s_j K_ij (x_i - x_j)/d_ij   (4 x 2 per cell)
        off = ~np.eye(tg.n, dtype=bool)
        wgt = np.where(off, K / d, 0.0)                        # n x n
        # (dc_i/dx_i)' ec_i = -sum_j (s_j . ec_i) K_ij/d_ij (x_i - x_j)
        se = ec.T @ as_                                        # n x n: [i, j] = ec_i . s_j
        grad_x_c = -(diff * (se * wgt)[None]).sum(2)           # 2 x n
        dax = -pi_a * (ex + sig * grad_x_c)
        das = -pi_a * (es + sig * ec)
        v = v + h * dv
        ax = ax + h * dax
        as_ = as_ + h * das
    return v, ax, as_


def initial_state(tg, rng, init_sd):
    v = rng.standard_normal((tg.n, tg.n)) * init_sd
    p = softmax(v)
    return v, tg.X @ p, tg.S @ p          # Mg([],v,P) with t empty: s = 0


def assess(tg, v, ax):
    """Best one-to-one assignment of cells to target positions, and identity typing."""
    d2 = ((ax[:, :, None] - tg.X[:, None, :]) ** 2).sum(0)   # cell x target
    cost = d2[np.arange(tg.n)[None, :], tg.perms].sum(1)
    best = tg.perms[cost.argmin()]
    rms = float(np.sqrt(cost.min() / tg.n))
    mean_dist = float(np.sqrt(d2[np.arange(tg.n), best]).mean())
    p = softmax(v)
    ident = p.argmax(0)
    correct = int((tg.type[ident] == tg.type[best]).sum())
    return {"rms": rms, "mean_dist": mean_dist, "correct_types": correct,
            "mean_max_p": float(p.max(0).mean())}


def run(tg, v, ax, as_, nbins=N_BINS, substeps=SUBSTEPS, noise_rng=None):
    """One spm_ADEM call: nbins bins with t = iY/nY. Returns per-bin trajectory. With
    `noise_rng`, sensory noise of precision exp(16) is drawn for each bin."""
    traj = [dict(step=0, **assess(tg, v, ax), F=None)]
    states = [(v.copy(), ax.copy(), as_.copy())]
    for step in range(1, nbins + 1):
        sig = ramp(step, nbins)
        F = free_energy(tg, v, ax, as_, sig)   # evaluated on entry, as J(iY) in spm_ADEM
        z = None if noise_rng is None else noise_rng.standard_normal((10, tg.n)) * np.exp(-8.0)
        v, ax, as_ = flow(tg, v, ax, as_, sig, substeps, noise=z)
        traj.append(dict(step=step, **assess(tg, v, ax), F=float(F)))
        states.append((v.copy(), ax.copy(), as_.copy()))
    return traj, states


def assembled(tg, a):
    return a["rms"] < 0.5 * tg.min_spacing and a["correct_types"] >= tg.n - 1


def split_half(tg, state, upper, rng):
    """SPLIT branch of DEM_morphogenesis.m: keep half the cells by position on the body axis,
    duplicate them (identities and signals copied), jitter action by randn/512."""
    v, ax, as_ = state
    order = np.argsort(-ax[0]) if upper else np.argsort(ax[0])
    j = np.concatenate([order[: tg.n // 2], order[: tg.n // 2]])
    return (v[:, j].copy(), ax[:, j] + rng.standard_normal(ax.shape) / 512,
            as_[:, j] + rng.standard_normal(as_.shape) / 512)


def load_source_info():
    records, texts = fetch_sources()
    demo12, demomain = parse_demo(texts["spm12"]), parse_demo(texts["spm-main"])
    assert np.array_equal(demo12["T"], demomain["T"])
    adem_t = re.search(r"^\s*t\s*=\s*iY/nY;", texts["spm12-adem"], re.M) is not None
    return records, demo12, demomain, adem_t


def dump(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1) + "\n")
