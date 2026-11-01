"""Erk trigger waves and wave-gated osteoblast growth on one regenerating fish scale.  SIMULATED.

Equations (Hayden, Poss, De Simone, Di Talia 2021, Biophys J 120:4287, doi 10.1016/j.bpj.2021.05.004, the
nondimensionalised system printed after their Table 1; E and I are fractions of total Erk, A is activator):

    dE/dt = alpha1 * A^2 / (beta^2 + A^2) * (1 - E) - E * (gamma1 * I + gamma_e)
    dA/dt = alpha2 * [source] + alpha3 * E - gamma2 * A + D * lap(A)
    dI/dt = gamma3 * (alpha4 * E - I)

Units: length um, time h.  Parameters are Table 1 of that paper (the authors' published MATLAB uses the same
numbers).  Scheme: explicit Euler, 5-point Laplacian with zero padding (absorbing edge), E = I = 0 outside the
scale disc, all species 0 at t = 0, as in the paper's Methods.  This file is an independent implementation;
no code was copied from the authors' GPL repository.

Growth (De Simone et al. 2021, Nature 590:129, doi 10.1038/s41586-020-03085-8): during the hypertrophic phase
osteoblasts barely divide and grow in area after the Erk peak passes.  MEASURED: Extended Data Fig. 7b fits a
LINEAR slope to normalised cell area after the peak, d(a/a_peak)/dt = 0.006 +/- 0.002 per h (before the peak
-0.002 +/- 0.002 per h; n = 89 cells, 3 scales).
ASSUMED (ours): the coupling form.  This code integrates d ln(a)/dt = 0.006 per h, i.e. EXPONENTIAL growth that
uses the measured linear slope as a log-rate, for a window W (ASSUMED, 24 h) after each time a cell's Erk crosses
up through E_peak_threshold, compounding over successive waves.  Over one 24 h window the two forms differ by
1.155 (exponential) vs 1.144 (linear) per window; that difference was not tuned or corrected.  Growth is
one-way: the wave field is computed in material (Lagrangian) coordinates and growth does not feed back on it.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import numpy as np

HAYDEN = "10.1016/j.bpj.2021.05.004"
DESIMONE = "10.1038/s41586-020-03085-8"


@dataclass(frozen=True)
class Params:
    # Hayden 2021 Table 1 ("standard simulation"); status: fitted-in-source (chosen by the authors so waves match
    # measured speed, frequency, activation and inactivation times), not measured individually.
    alpha1: float = 12.6      # h^-1   maximal Erk activation rate
    beta: float = 0.35        # 1      Erk activation AC50 (per total Erk)
    gamma1: float = 15.4      # h^-1   inhibitor-dependent Erk inactivation rate
    gamma_e: float = 0.14     # h^-1   autonomous Erk inactivation rate
    alpha2_source: float = 0.112  # h^-1 activator deposition in the source (0 outside)
    alpha3: float = 3.9       # h^-1   Erk-dependent activator production
    gamma2: float = 11.8      # h^-1   activator degradation
    D: float = 566.0          # um^2/h activator diffusion constant (= 0.157 um^2/s)
    gamma3: float = 0.14      # h^-1   inhibitor timescale
    alpha4: float = 0.5       # 1      inhibitor Erk-dependent production


@dataclass(frozen=True)
class Geometry:
    # Hayden 2021 Methods: 1090 um square domain, 520 um scale disc, 40 um source "small off-center circle",
    # 5 um grid, 0.01 h step.  The source OFFSET is assumed (De Simone 2021: "between the centre and the
    # anterior margin"); 150 um toward anterior (-x) is our choice.
    domain_um: float = 1090.0
    scale_radius_um: float = 520.0
    source_radius_um: float = 40.0
    source_offset_um: float = 150.0
    dx_um: float = 5.0
    dt_h: float = 0.01


@dataclass(frozen=True)
class Growth:
    rate_after_peak_per_h: float = 0.006   # used as d ln(a)/dt: ASSUMED exponential form; the value is the MEASURED
    #                                        linear slope of normalised cell area (De Simone 2021 Ext. Data Fig. 7b)
    window_h: float = 24.0                 # ASSUMED: growth lasts this long after each Erk peak
    peak_threshold: float = 0.2            # Hayden 2021 Methods scores an event at Erk prominence > 0.2


@dataclass(frozen=True)
class Run:
    hours: float = 120.0
    save_every_h: float = 1.0
    mode: str = "standard"   # standard | no_source | synchronous | pf_sign_mutant
    sync_period_h: float = 24.0
    sync_pulse_A: float = 1.0          # synchronous control: activator set tissue-wide to this, once a period
    params: Params = field(default_factory=Params)
    geometry: Geometry = field(default_factory=Geometry)
    growth: Growth = field(default_factory=Growth)


PROBE_UM = (0.0, 100.0, 250.0, 400.0)   # probe points on the posterior axis, distance from the source centre
MODES = ("standard", "no_source", "synchronous", "pf_sign_mutant")


def grid(g: Geometry):
    n = int(round(g.domain_um / g.dx_um))
    c = (np.arange(n) + 0.5) * g.dx_um - g.domain_um / 2
    X, Y = np.meshgrid(c, c)            # x posterior (+), y dorsal (+); origin at the scale centre
    scale = X**2 + Y**2 < g.scale_radius_um**2
    source = (X + g.source_offset_um) ** 2 + Y**2 < g.source_radius_um**2
    return X, Y, scale, source


def lap(A: np.ndarray) -> np.ndarray:
    P = np.pad(A, 1)                    # zero padding = absorbing domain edge, as imfilter's default
    return P[:-2, 1:-1] + P[2:, 1:-1] + P[1:-1, :-2] + P[1:-1, 2:] - 4 * A


def rhs(E, A, I, p: Params, src_term):
    hill = A * A / (p.beta**2 + A * A)
    dE = p.alpha1 * hill * (1 - E) - E * (p.gamma1 * I + p.gamma_e)
    dA = src_term + p.alpha3 * E - p.gamma2 * A
    dI = p.gamma3 * (p.alpha4 * E - I)
    return dE, dA, dI


def simulate(run: Run) -> dict:
    if run.mode not in MODES:
        raise ValueError(f"mode {run.mode!r} not in {MODES}")
    p, g, gr = run.params, run.geometry, run.growth
    if p.D * g.dt_h / g.dx_um**2 > 0.25:
        raise ValueError("explicit diffusion step unstable: D dt / dx^2 > 1/4")
    if run.mode == "pf_sign_mutant":
        p = replace(p, alpha3=-p.alpha3)          # Erk now SUPPRESSES its activator: positive feedback removed
    X, Y, scale, source = grid(g)
    src_term = np.where(source, p.alpha2_source, 0.0)
    if run.mode in ("no_source", "synchronous"):
        src_term = np.zeros_like(src_term)
    E = np.zeros_like(X); A = np.zeros_like(X); I = np.zeros_like(X)
    loga = np.zeros_like(X)             # per-cell log area (material coordinates), 0 at t = 0
    last_peak = np.full(X.shape, -np.inf)
    n_peaks = np.zeros(X.shape, dtype=np.int32)
    above = np.zeros(X.shape, dtype=bool)
    steps = int(round(run.hours / g.dt_h))
    save_k = int(round(run.save_every_h / g.dt_h))
    sync_k = int(round(run.sync_period_h / g.dt_h))
    coef = p.D / g.dx_um**2
    t_s, E_s, loga_s, area_s = [], [], [], []
    row = X.shape[0] // 2
    probe_j = [int(np.argmin(np.abs(X[row] - (d - g.source_offset_um)))) for d in PROBE_UM]
    probe = []
    dA0 = g.dx_um**2
    for k in range(steps + 1):
        t = k * g.dt_h
        if k % save_k == 0:
            t_s.append(t); E_s.append(E.astype(np.float32)); loga_s.append(loga.astype(np.float32))
            area_s.append(float(np.exp(loga[scale]).sum() * dA0))
        probe.append(E[row, probe_j])
        if k == steps:
            break
        if run.mode == "synchronous" and k % sync_k == 0:
            A = np.where(scale, run.sync_pulse_A, A)
        dE, dAr, dI = rhs(E, A, I, p, src_term)
        E = E + g.dt_h * dE
        A = A + g.dt_h * (dAr + coef * lap(A))
        I = I + g.dt_h * dI
        E[~scale] = 0.0; I[~scale] = 0.0
        now = E > gr.peak_threshold
        up = now & ~above & scale
        last_peak[up] = t + g.dt_h; n_peaks[up] += 1
        above = now
        growing = scale & (t + g.dt_h - last_peak <= gr.window_h)
        loga[growing] += gr.rate_after_peak_per_h * g.dt_h
    return {"run": run, "t_h": np.array(t_s), "E": np.stack(E_s), "loga": np.stack(loga_s),
            "area_um2": np.array(area_s), "scale": scale, "source": source, "X": X, "Y": Y,
            "n_peaks": n_peaks, "probe_um": PROBE_UM, "probe_E": np.array(probe, dtype=np.float32), "final": {"E": E, "A": A, "I": I}}


# ---------------------------------------------------------------- measurements on the simulated states
def axis_profile(res: dict, frame: int) -> tuple[np.ndarray, np.ndarray]:
    """E along the posterior axis through the source (y = 0 row), from the source centre outward."""
    g = res["run"].geometry
    X = res["X"]; row = X.shape[0] // 2
    x = X[row]; sel = x >= -g.source_offset_um
    return x[sel] + g.source_offset_um, res["E"][frame, row, sel]


def wave_fronts(res: dict) -> list[dict]:
    """Per saved frame, the outermost Erk peak (> threshold) on the posterior axis, distance from the source."""
    th = res["run"].growth.peak_threshold
    out = []
    for i, t in enumerate(res["t_h"]):
        d, e = axis_profile(res, i)
        pk = [j for j in range(1, len(e) - 1) if e[j] > th and e[j] >= e[j - 1] and e[j] >= e[j + 1]]
        out.append({"t_h": float(t), "peaks_um": [float(d[j]) for j in pk],
                    "widths_um": [float(_fwhm(d, e, j)) for j in pk]})
    return out


def _fwhm(d, e, j):
    h = e[j] / 2
    lo = j
    while lo > 0 and e[lo] > h:
        lo -= 1
    hi = j
    while hi < len(e) - 1 and e[hi] > h:
        hi += 1
    return d[hi] - d[lo]


def wave_speed(res: dict, lo_um: float = 130.0, hi_um: float = 330.0) -> dict:
    """Speed of the first wave's leading peak between lo and hi um from the source (away from the source and
    the rim, as De Simone 2021 Methods measured it), by a least-squares line through (t, position)."""
    pts = []
    for f in wave_fronts(res):
        far = [x for x in f["peaks_um"] if lo_um <= x <= hi_um]
        if far:
            pts.append((f["t_h"], max(far)))
    # keep the first monotone run only (the first wave)
    first = []
    for t, x in pts:
        if first and x < first[-1][1]:
            break
        first.append((t, x))
    if len(first) < 3:
        return {"speed_um_per_h": None, "n_points": len(first)}
    tt, xx = np.array(first).T
    v, b = np.polyfit(tt, xx, 1)
    return {"speed_um_per_h": float(v), "n_points": len(first), "t_range_h": [float(tt[0]), float(tt[-1])]}


def rim_arrivals(res: dict, margin_um: float = 20.0) -> list[float]:
    """Times (h) at which a wave reaches the posterior rim (E > threshold within margin of the rim on the axis)."""
    g = res["run"].geometry; th = res["run"].growth.peak_threshold
    X = res["X"]; row = X.shape[0] // 2
    j = int(np.argmin(np.abs(X[row] - (g.scale_radius_um - margin_um))))
    e = res["E"][:, row, j]
    return [float(res["t_h"][i]) for i in range(1, len(e)) if e[i] > th >= e[i - 1]]


def source_peaks(res: dict) -> list[float]:
    g = res["run"].geometry; th = res["run"].growth.peak_threshold
    X = res["X"]; row = X.shape[0] // 2
    j = int(np.argmin(np.abs(X[row] + g.source_offset_um)))
    e = res["E"][:, row, j]
    return [float(res["t_h"][i]) for i in range(1, len(e)) if e[i] > th >= e[i - 1]]


def activation_time(res: dict, at_um: float = 250.0) -> dict | None:
    """Rise (10% -> 90% of peak) and fall (peak -> 10%) times of the FIRST Erk pulse at a probe point, from the
    per-step probe trace.  De Simone 2021 report activation ~3 h and inactivation ~5 h (single-cell tracks)."""
    k = res["probe_um"].index(at_um)
    e = res["probe_E"][:, k].astype(float); dt = res["run"].geometry.dt_h
    th = res["run"].growth.peak_threshold
    if e.max() <= th:
        return None
    i = int(np.argmax(e > th))
    while i + 1 < len(e) and e[i + 1] >= e[i]:
        i += 1
    pk = e[i]
    i10 = int(np.argmax(e[:i + 1] >= 0.1 * pk)); i90 = int(np.argmax(e[:i + 1] >= 0.9 * pk))
    j = i
    while j + 1 < len(e) and e[j] > 0.1 * pk:
        j += 1
    return {"at_um": at_um, "peak_E": float(pk), "rise_10_90_h": (i90 - i10) * dt, "fall_peak_10_h": (j - i) * dt}


def summary(res: dict) -> dict:
    run = res["run"]; g = run.geometry
    a0 = float(np.pi * g.scale_radius_um**2)
    fr = wave_fronts(res)
    widths = [w for f in fr for x, w in zip(f["peaks_um"], f["widths_um"]) if 200 <= x <= 400]
    area = res["area_um2"]
    return {
        "mode": run.mode,
        "wave_speed": wave_speed(res),
        "source_peak_times_h": source_peaks(res),
        "rim_arrival_times_h": rim_arrivals(res),
        "pulse_shape": activation_time(res),
        "front_fwhm_um_median": float(np.median(widths)) if widths else None,
        "max_E_outside_source": float(res["E"][:, res["scale"] & ~res["source"]].max()),
        "peaks_per_cell_max": int(res["n_peaks"].max()),
        "cells_reached_fraction": float((res["n_peaks"][res["scale"]] > 0).mean()),
        "area_initial_um2": float(area[0]),
        "area_final_um2": float(area[-1]),
        "area_ratio": float(area[-1] / area[0]),
        "effective_radius_final_um": float(np.sqrt(area[-1] / np.pi)),
        "disc_area_check_rel": float(abs(area[0] - a0) / a0),
    }


def code_hash() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def run_dict(run: Run) -> dict:
    return asdict(run)
