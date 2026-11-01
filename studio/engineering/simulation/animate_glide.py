"""Glide trajectory animation from ACTUAL integrated trajectories (no interpolated evidence beyond resampling onto a common time grid for plotting).
Three geometry candidates at the SAME release (12 m/s, 1 m, level), nominal polar P1 plus a Monte Carlo band over the declared P1 prior ranges.
Panels: side-view path with q10-q90 band, speed V(t), lift/weight L/W (t), specific mechanical energy E/(m g) = h + V^2/(2g) (t).
Time axis = GLIDE SECONDS (physical). Evidence kind: simulated; coefficients are design assumptions; not a biological claim.
Usage: python3 -m engineering.simulation.animate_glide OUTDIR"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import glide
from .controlled import POLARS, RHO, H0, baseline
from .evaluate import DT, PRIORS
from .schema import G

V0 = 12.0
POL = POLARS["P1_nominal"]
CANDIDATES = [("baseline (Fish Cypselurus fit, 0.05 kg)", 1.0, 1.0, "#1f77b4"), ("area x1.3", 1.3, 1.0, "#d62728"), ("area x1.3, AR x1.2", 1.3, 1.2, "#2ca02c")]
N_MC, SEED = 60, 20261031
FPS, SECONDS = 24, 16
W, H = 1280, 720


def traj(m, S, AR, CLm, CD0, e, stride=10):
    CL = glide.cl_command(CLm, CD0, e, AR)
    r = glide.integrate(m, S, AR, RHO, CL, CD0, e, H0, V0, dt=DT, record_stride=stride)
    return r, CL


def build():
    b = baseline("Cypselurus", 0.05)
    out = []
    rng = np.random.default_rng(SEED)
    d = {k: rng.uniform(lo, hi, N_MC) for k, (lo, hi) in PRIORS.items()}
    for name, fs, fa, col in CANDIDATES:
        S, AR = b["S"] * fs, b["AR"] * fa
        m = b["m"]
        r, CL = traj(m, S, AR, POL["CL_max"], POL["CD0"], POL["e"])
        t = np.array([s[0] for s in r["series"]]); st = np.array([s[1][:, 0] for s in r["series"]]); act = np.array([s[2][0] for s in r["series"]])
        n = int(act.sum()) if act.any() else len(t)
        t, st = t[:n], st[:n]
        x, h, V, g_ = st[:, 0], st[:, 1], st[:, 2], st[:, 3]
        q = 0.5 * RHO * V ** 2 * S
        LW = q * float(CL) / (m * G)
        E = h + V ** 2 / (2 * G)
        # Monte Carlo under declared P1 priors (paired draws), same release
        CLd = glide.cl_command(d["CL_max"], d["CD0"], d["e"], AR)
        mc = glide.integrate(m, S, AR, RHO, CLd, d["CD0"], d["e"], H0, V0, dt=DT, record_stride=10)
        T = np.array([s[0] for s in mc["series"]])
        X = np.array([s[1][0] for s in mc["series"]]); Hh = np.array([s[1][1] for s in mc["series"]]); A = np.array([s[2] for s in mc["series"]])
        out.append({"name": name, "color": col, "fS": fs, "fAR": fa, "S": S, "b": math.sqrt(AR * S), "AR": AR, "m": m, "CL": float(CL), "t": t, "x": x, "h": h, "V": V, "LW": LW, "E": E,
                    "range_nominal": float(r["range_m"][0]), "time_nominal": float(r["time_s"][0]), "mc_T": T, "mc_X": X, "mc_H": Hh, "mc_A": A,
                    "mc_range": mc["range_m"], "V_stall": float(glide.stall_speed(m, S, RHO, POL["CL_max"]))})
    return out


def band(c, grid_x):
    """q10/q50/q90 of height over x for the MC set (cases that have ended contribute 0 beyond contact). Resampled for plotting only."""
    ys = []
    for j in range(c["mc_X"].shape[1]):
        act = c["mc_A"][:, j]
        n = int(act.sum()) if act.any() else len(act)
        x, h = c["mc_X"][:n, j], c["mc_H"][:n, j]
        y = np.interp(grid_x, x, h, left=np.nan, right=np.nan)
        y = np.where(grid_x > c["mc_range"][j], np.nan, y)
        ys.append(y)
    ys = np.array(ys)
    with np.errstate(all="ignore"):
        return np.nanquantile(ys, 0.1, axis=0), np.nanquantile(ys, 0.5, axis=0), np.nanquantile(ys, 0.9, axis=0)


def main(outdir):
    out = Path(outdir); frames = out / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    cs = build()
    Tmax = max(c["time_nominal"] for c in cs) * 1.02
    Xmax = max(max(c["range_nominal"] for c in cs), max(float(np.nanmax(c["mc_range"])) for c in cs)) * 1.03
    gx = np.linspace(0, Xmax, 300)
    bands = [band(c, gx) for c in cs]
    nfr = FPS * SECONDS
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.15, 1], hspace=0.38, wspace=0.28, left=0.06, right=0.985, top=0.88, bottom=0.11)
    axp = fig.add_subplot(gs[0, :]); axv = fig.add_subplot(gs[1, 0]); axl = fig.add_subplot(gs[1, 1]); axe = fig.add_subplot(gs[1, 2])
    for c, (lo, md, hi) in zip(cs, bands):
        axp.fill_between(gx, lo, hi, color=c["color"], alpha=0.15, lw=0)
        axp.plot(c["x"], c["h"], color=c["color"], lw=1, alpha=0.25)
    axp.axhline(0, color="#9bbfdc", lw=3, zorder=0); axp.text(Xmax*0.005, -0.2, "water", fontsize=7, color="#5b86a8"); axp.set_xlim(0, Xmax); axp.set_ylim(-0.3, max(float(c["h"].max()) for c in cs) * 1.08)
    axp.set_xlabel("distance x (m)"); axp.set_ylabel("height above water (m)")
    for ax, key, lab in ((axv, "V", "speed V (m/s)"), (axl, "LW", "lift / weight (1)"), (axe, "E", "E/(m g) = h + V^2/2g (m)")):
        for c in cs:
            ax.plot(c["t"], c[key], color=c["color"], lw=1, alpha=0.25)
        ax.set_xlim(0, Tmax); ax.set_xlabel("glide time t (s)"); ax.set_ylabel(lab)
        ymin = min(float(np.min(c[key])) for c in cs); ymax = max(float(np.max(c[key])) for c in cs)
        ax.set_ylim(ymin - 0.05 * (ymax - ymin), ymax + 0.08 * (ymax - ymin))
    axv.axhline(cs[0]["V_stall"], color="k", ls=":", lw=0.8); axv.text(Tmax * 0.5, cs[0]["V_stall"], " baseline level stall speed", fontsize=6, va="bottom")
    lines = []
    for c in cs:
        lp, = axp.plot([], [], color=c["color"], lw=2.2, label=f"{c['name']}: S={c['S']*1e4:.0f} cm2, b={c['b']*100:.0f} cm, AR={c['AR']:.1f}, range {c['range_nominal']:.1f} m (MC q10-q90 {np.quantile(c['mc_range'],0.1):.1f}-{np.quantile(c['mc_range'],0.9):.1f})")
        dp, = axp.plot([], [], "o", color=c["color"], ms=7)
        ls = [ax.plot([], [], color=c["color"], lw=2.2)[0] for ax in (axv, axl, axe)]
        lines.append((lp, dp, ls))
    axp.legend(loc="upper right", fontsize=7, framealpha=0.9)
    title = fig.suptitle("", fontsize=10)
    fig.text(0.5, 0.012, "SIMULATED point-mass glide, SAME release for all (12 m/s, 1 m, level). Coefficients are design assumptions (CD0 0.06, e 0.8, CL_max 1.2); bands = Monte Carlo over declared prior ranges.\n"
             "Not a biological result; no fin-tissue coupling; time axes are glide seconds; dotted line = baseline level-flight stall speed at CL_max (the commanded CL is lower).", ha="center", fontsize=7, color="#444")
    for k in range(nfr):
        tcur = Tmax * k / (nfr - 1)
        for c, (lp, dp, ls) in zip(cs, lines):
            n = max(1, int(np.searchsorted(c["t"], tcur, side="right")))
            lp.set_data(c["x"][:n], c["h"][:n]); dp.set_data([c["x"][n - 1]], [c["h"][n - 1]])
            for l, key in zip(ls, ("V", "LW", "E")):
                l.set_data(c["t"][:n], c[key][:n])
        title.set_text(f"Fixed-launch glide comparison: glide time t = {tcur:5.2f} s   (frame {k+1}/{nfr}, {FPS} fps = {Tmax/nfr*FPS:.2f} glide-s per video-s)")
        fig.savefig(frames / f"f{k:04d}.png")
    poster = out / "poster.png"
    for l in lines:
        pass
    shutil.copy(frames / f"f{nfr-1:04d}.png", poster)
    mp4 = out / "glide_fixed_launch.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames / "f%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "30", "-preset", "slow", "-movflags", "+faststart", str(mp4)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
    man = {"kind": "glide trajectory animation", "evidence_kind": "simulated", "video": mp4.name, "video_sha256": sha(mp4), "video_bytes": mp4.stat().st_size, "poster": poster.name, "poster_sha256": sha(poster),
           "fps": FPS, "frames": nfr, "duration_video_s": nfr / FPS, "resolution": [W, H], "ffmpeg_exit": p.returncode, "ffmpeg_cmd": " ".join(cmd),
           "time_units": {"axis": "glide seconds (physical time of the point-mass trajectory)", "video_time_to_glide_time": Tmax / SECONDS, "separate_from": "reaction-diffusion model time (see RD animation manifest); the two clocks are unrelated and not coupled"},
           "release": {"V0_ms": V0, "h0_m": H0, "gamma0": 0}, "polar": POL, "polar_status": "design assumption; not a measured fish polar", "mc": {"n": N_MC, "seed": SEED, "priors": PRIORS},
           "candidates": [{k: c[k] for k in ("name", "fS", "fAR", "m", "S", "b", "AR", "CL", "range_nominal", "time_nominal", "V_stall")} | {"mc_range_q10_q50_q90": [float(x) for x in np.quantile(c["mc_range"], [0.1, 0.5, 0.9])]} for c in cs],
           "code": {"module": "engineering/simulation/animate_glide.py", "sha256": sha(Path(__file__)), "git_commit_note": "record `git rev-parse HEAD` of the Frontier branch alongside this manifest"},
           "frames_sha256_of_first_middle_last": [sha(frames / f"f{i:04d}.png") for i in (0, nfr // 2, nfr - 1)],
           "not_established": ["biological feasibility", "calibrated lift/drag", "fin-tissue coupling or any genetic mechanism", "which geometry is better: ranking flips with release speed (see results_controlled)"]}
    (out / "manifest.json").write_text(json.dumps(man, indent=1))
    shutil.rmtree(frames)
    print(json.dumps({k: man[k] for k in ("video", "video_bytes", "duration_video_s", "ffmpeg_exit", "video_sha256")}))


if __name__ == "__main__":
    main(sys.argv[1])
