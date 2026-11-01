#!/usr/bin/env python3
"""Render the saved Voxelyze travelling-wave voxel states as an MP4, a poster and a COM comparison, plus a hashed manifest.

Every frame is one recorded state (trajectory/travelling-voxels.csv, 241 samples); nothing is interpolated or re-simulated.
Time shown is SIMULATION time, never wall time. The controls drawn beside it were run on the LONGITUDINAL pattern, not the
travelling one, and the figure says so. Model-only: 45 toy voxels of a nominal 10 mm, assumed parameters, no cell or tissue.

    python3 -m engineering.reuse_visuals.render_voxel            # render + manifest
    python3 -m engineering.reuse_visuals.render_voxel --manifest # manifest only (media must already exist)

Run under: systemd-run --user --scope -p TasksMax=128 -p MemoryMax=2G -p MemorySwapMax=0 -p RuntimeMaxSec=600 -p CPUQuota=200%
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(k, "1")
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import LineCollection, PolyCollection  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SRC = "artifacts/voxel-actuation"
OUT = "artifacts/reuse-study-visuals/tissue-microcarrier"
FPS = 12
CONTROLS = [("B-passive-cte0", "B passive (CTE 0)", "#7a7a7a", "-"), ("C-zero-amplitude", "C zero amplitude", "#7a7a7a", "--"),
            ("D-frictionless", "D frictionless", "#2a7ab0", "-"), ("E-zero-gravity", "E zero gravity (predeclared bound MISSED)", "#c0392b", "-")]
SOURCES = [f"{SRC}/{p}" for p in ("protocol.json", "summary.json", "trajectory/travelling.json", "trajectory/travelling-voxels.csv", "trajectory/travelling-com.csv",
                                  "candidates/longitudinal-com.csv", "candidates/travelling-com.csv", "run-log.txt", "timings.psv")] + \
          [f"{SRC}/controls/{c[0]}{s}" for c in CONTROLS for s in ("-com.csv", ".json")]
RENDERER = ["engineering/reuse_visuals/render_voxel.py"]
MEDIA = {"video": "travelling-voxels.mp4", "poster": "poster.png", "figure": "com-comparison.png"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load():
    rows = list(csv.DictReader(open(ROOT / SRC / "trajectory/travelling-voxels.csv")))
    steps = sorted({int(r["step"]) for r in rows})
    n = len(rows) // len(steps)
    arr = np.array([[float(r[k]) for k in ("t_s", "ix", "iy", "iz", "x_m", "y_m", "z_m", "temp_C")] for r in rows]).reshape(len(steps), n, 8)
    def com(rel):
        return list(csv.DictReader(open(ROOT / SRC / rel)))
    return arr, com


def com_series(rows):
    t = np.array([float(r["t_s"]) for r in rows])
    x = np.array([float(r["com_x_m"]) for r in rows])
    ph = [r["phase"] for r in rows]
    m0 = ph.index("measure")
    return t, (x - x[m0]) * 1e3, ph


def cell_verts(p, pi, pj, h):
    return [[(p[k, pi] + dx, p[k, pj] + dy) for dx, dy in ((-h, -h), (h, -h), (h, h), (-h, h))] for k in range(len(p))]


def link_segs(frame, pi, pj):
    idx = {(int(v[1]), int(v[2]), int(v[3])): v for v in frame}
    segs = []
    for (ix, iy, iz), v in idx.items():
        for d in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            w = idx.get((ix + d[0], iy + d[1], iz + d[2]))
            if w is not None:
                segs.append([(v[pi], v[pj]), (w[pi], w[pj])])
    return segs


class Scene:
    def __init__(self):
        self.arr, self.com = load()
        self.proto = json.loads((ROOT / SRC / "protocol.json").read_text())
        self.summ = json.loads((ROOT / SRC / "summary.json").read_text())
        self.series = {"travelling": com_series(self.com("trajectory/travelling-com.csv")), "longitudinal": com_series(self.com("candidates/longitudinal-com.csv"))}
        for c in CONTROLS:
            self.series[c[0]] = com_series(self.com(f"controls/{c[0]}-com.csv"))
        self.h = self.proto["parameter_provenance"]["sourced_from_pinned_artifact"]["voxel_m"] * 1e3 / 2
        a = self.arr
        self.lim = {"x": (a[..., 4].min() * 1e3 - 4, a[..., 4].max() * 1e3 + 4), "y": (a[..., 5].min() * 1e3 - 4, a[..., 5].max() * 1e3 + 4), "z": (a[..., 6].min() * 1e3 - 4, a[..., 6].max() * 1e3 + 4)}
        bottom = a[0, a[0, :, 3] == 0, 6].mean() * 1e3
        self.bottom0 = bottom
        self.fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
        f = self.fig
        f.text(0.02, 0.985, "Soft-voxel ground-contact mechanics benchmark (Voxelyze), travelling wave: saved states, MODEL ONLY", fontsize=14, weight="bold", va="top")
        f.text(0.02, 0.945, "Toy body: 45 voxels of nominal 10 mm, 50x30x30 mm envelope (40 mm centre span), 45 g assumed. Not a cell, tissue, frog or fish; no fluid. Assumed parameters.", fontsize=9, va="top", color="#5a4a00")
        self.ax_s = f.add_axes([0.05, 0.53, 0.50, 0.32])
        self.ax_t = f.add_axes([0.05, 0.16, 0.50, 0.28])
        for ax, (a1, a2, title) in ((self.ax_s, ("x", "z", "Side view (x-z), layer iy=1: 10 mm glyphs at voxel CENTRES; lines join centres")), (self.ax_t, ("x", "y", "Top view (x-y), layer iz=2. No orientations, meshes or forces are recorded"))):
            ax.set_xlim(*self.lim[a1])
            ax.set_ylim(*self.lim[a2])
            ax.set_aspect("equal", adjustable="box")
            ax.set_title(title, fontsize=9, loc="left")
            ax.set_xlabel(a1 + " (mm)", fontsize=8)
            ax.set_ylabel(a2 + " (mm)", fontsize=8)
            ax.tick_params(labelsize=7)
            ax.grid(alpha=0.2)
        self.ax_s.axhline(bottom, color="#444", ls=":", lw=0.8)
        self.ax_s.text(self.lim["x"][1] - 0.5, bottom + 0.4, "settled bottom-layer centre height (state-derived)", fontsize=6.5, ha="right", color="#444")
        self.cm = plt.get_cmap("coolwarm")
        self.norm = matplotlib.colors.Normalize(-10, 10)
        self.pc = {}
        for ax, key in ((self.ax_s, "s"), (self.ax_t, "t")):
            pc = PolyCollection([], edgecolors="k", linewidths=0.6, alpha=0.8)
            ax.add_collection(pc)
            lc = LineCollection([], colors="k", linewidths=0.5, alpha=0.5)
            ax.add_collection(lc)
            self.pc[key] = (pc, lc)
        cax = f.add_axes([0.05, 0.095, 0.50, 0.014])
        cb = f.colorbar(plt.cm.ScalarMappable(norm=self.norm, cmap=self.cm), cax=cax, orientation="horizontal")
        cb.set_label("imposed per-voxel drive temperature (C); x CTE 0.01 /C = +/-10% linear strain; ASSUMED", fontsize=7.5)
        cb.ax.tick_params(labelsize=7)
        self.ax_c = f.add_axes([0.63, 0.53, 0.35, 0.32])
        ax = self.ax_c
        t, x, _ = self.series["travelling"]
        ax.plot(t, x, color="#b8651b", lw=2.2, label="travelling (this body)")
        t2, x2, _ = self.series["longitudinal"]
        ax.plot(t2, x2, color="#1b7a4b", lw=1.6, label="longitudinal (active)")
        for key, lab, col, ls in CONTROLS:
            tc, xc, _ = self.series[key]
            ax.plot(tc, xc, color=col, ls=ls, lw=1.2, label=lab + " [longitudinal pattern]")
        ax.axvline(0.25, color="#999", lw=0.8, ls=":")
        ax.text(0.26, ax.get_ylim()[1] * 0.9, "settle | actuate", fontsize=6.5, color="#666")
        self.cur = ax.axvline(0, color="k", lw=1)
        ax.set_xlabel("simulation time (s)", fontsize=8)
        ax.set_ylabel("COM x change since actuation start (mm)", fontsize=8)
        ax.set_title("Centre of mass x: recorded runs, same time axis", fontsize=9, loc="left")
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.2)
        self.ax_n = f.add_axes([0.63, 0.09, 0.35, 0.36])
        self.ax_n.axis("off")
        self.ax_n.legend(*ax.get_legend_handles_labels(), loc="upper left", fontsize=6.6, frameon=False, borderaxespad=0)
        S = self.summ
        lines = ["Net displacement over 5 cycles (BL = 40 mm centre span)", f"travelling {S['arm_A_candidates']['travelling']['body_lengths']:.4f} BL = {math.hypot(S['arm_A_candidates']['travelling']['net_dx_m'], S['arm_A_candidates']['travelling']['net_dy_m']) * 1e3:.3f} mm   longitudinal {S['arm_A_candidates']['longitudinal']['body_lengths']:.4f} BL",
                 f"B passive {S['controls']['B_passive_cte0']['body_lengths']:.6f}   C zero-amp {S['controls']['C_zero_amplitude']['body_lengths']:.6f}   (bound 0.01: met)",
                 f"D frictionless {S['controls']['D_frictionless']['body_lengths']:.1f}  (x,y constant: met)",
                 f"E zero gravity {S['controls']['E_zero_gravity']['body_lengths']:.4f}  bound 0.01: MISSED (recorded, not retuned)",
                 "Spatial refinement G (longitudinal): did not converge, 0.1532 -> 0.0188.", "Post-hoc: odd/even voxel-count parity supported; not a proof.",
                 "Post-hoc travelling, coarse 14.577 mm (0.3644 of 40 mm span) vs fine 16.848 mm", "(0.3744 of 45 mm span): the 2.74% compares different denominators;",
                 "raw SI differs 15.57%. One pattern, two grids: NOT convergence.",
                 "Controls above use the longitudinal pattern; none was run on travelling.", "Damping is a numerical absolute-frame term, not fluid drag or swimming."]
        self.ax_n.text(0, 0.50, "\n".join(lines), fontsize=7.0, va="top", family="DejaVu Sans")
        eng = self.proto["engine"]
        f.text(0.02, 0.018, f"Engine {eng['name']} {eng['commit'][:10]} ({eng['licence_of_record'].split(' ')[0]}). E 1e5 Pa, rho 1e3, nu 0.35, mu 1.0/0.8 sourced from voxcraft demo base.vxa; "
               f"CTE 0.01, amp 10 C, 4 Hz, damping 1.0/0.1/0.8 ASSUMED. CPU, no GPU. Unvalidated against any organism.", fontsize=6.8, color="#333")
        self.clock = f.text(0.02, 0.905, "", fontsize=13, weight="bold", ha="left", va="top", family="DejaVu Sans Mono")
        self.note = f.text(0.98, 0.905, "", fontsize=8.5, ha="right", va="top")

    def draw(self, k):
        fr = self.arr[k]
        mm = fr.copy()
        mm[:, 4:7] *= 1e3
        for key, (pi, pj) in (("s", (4, 6)), ("t", (4, 5))):
            pc, lc = self.pc[key]
            p = mm[mm[:, 2] == 1] if key == "s" else mm[mm[:, 3] == 2]           # one slice per view: the other layers would hide it
            pc.set_verts(cell_verts(p, pi, pj, self.h))
            pc.set_facecolor(self.cm(self.norm(p[:, 7])))
            lc.set_segments(link_segs(p, pi, pj))
        t = fr[0, 0]
        phase = "settle (no drive)" if t < 0.25 else f"actuate, cycle {(t - 0.25) * 4:.2f} of 5"
        self.clock.set_text(f"sim t = {t:6.3f} s")
        self.note.set_text(f"{phase} | state {k + 1} of {len(self.arr)} | playback {self.arr[-1, 0, 0] / (len(self.arr) / FPS):.3f}x real time (slow motion)")
        self.cur.set_xdata([t, t])


def render(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    s = Scene()
    n = len(s.arr)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-threads", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "1280x720", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out / MEDIA["video"])]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k in range(n):
        s.draw(k)
        s.fig.canvas.draw()
        pr.stdin.write(np.asarray(s.fig.canvas.buffer_rgba()).tobytes())
        if k == n // 2:
            s.fig.savefig(out / MEDIA["poster"], dpi=100)
    for _ in range(FPS * 2):                      # hold the last recorded state for 2 s
        pr.stdin.write(np.asarray(s.fig.canvas.buffer_rgba()).tobytes())
    pr.stdin.close()
    assert pr.wait() == 0
    fig = plt.figure(figsize=(8.5, 4.6), dpi=130)
    ax = fig.add_axes([0.09, 0.14, 0.62, 0.72])
    for key, lab, col, ls in [("travelling", "travelling (animated body)", "#b8651b", "-"), ("longitudinal", "longitudinal (active)", "#1b7a4b", "-")] + [(c[0], c[1] + " [longitudinal]", c[2], c[3]) for c in CONTROLS]:
        t, x, _ = s.series[key]
        ax.plot(t, x, color=col, ls=ls, lw=1.8 if key in ("travelling", "longitudinal") else 1.2, label=lab)
    ax.axvline(0.25, color="#999", ls=":")
    ax.set_xlabel("simulation time (s)")
    ax.set_ylabel("COM x change since actuation start (mm)")
    ax.grid(alpha=0.25)
    ax.set_title("Soft-voxel benchmark, recorded COM x (model only; assumed parameters; controls are longitudinal pattern)", fontsize=8.5, loc="left")
    fig.legend(*ax.get_legend_handles_labels(), loc="center right", fontsize=7)
    fig.savefig(out / MEDIA["figure"])
    plt.close(fig)


def posthoc() -> dict:
    """SI displacement and both normalisations for the post-hoc travelling pair, recomputed here from the stored JSON."""
    r = {}
    for k, rel in (("coarse", "candidates/travelling.json"), ("fine", "posthoc/travelling-fine.json")):
        j = json.loads((ROOT / SRC / rel).read_text())
        p = j["params"]
        res = j["result"]
        r[k] = {"lattice": [p["nx"], p["ny"], p["nz"]], "voxel_mm": p["voxel_m"] * 1e3, "net_disp_mm": res["net_disp_m"] * 1e3, "centre_span_mm": res["body_len_m"] * 1e3,
                "stored_normalised": res["disp_in_body_lengths"], "outer_length_mm": p["nx"] * p["voxel_m"] * 1e3}
    for v in r.values():
        v["normalised_by_outer_length"] = v["net_disp_mm"] / v["outer_length_mm"]
    r["reported_ratio_difference_pct"] = abs(r["fine"]["stored_normalised"] / r["coarse"]["stored_normalised"] - 1) * 100
    r["raw_si_difference_pct_of_coarse"] = abs(r["fine"]["net_disp_mm"] / r["coarse"]["net_disp_mm"] - 1) * 100
    r["note"] = "The reported small difference compares different centre-span denominators (40 vs 45 mm). Raw SI and a common outer-length denominator differ by the same larger percentage. Post hoc, one pattern, two grids: not convergence."
    return r


def manifest(out: Path) -> dict:
    def ent(rel):
        return {"path": rel, "sha256": sha(ROOT / rel), "bytes": (ROOT / rel).stat().st_size}
    S = json.loads((ROOT / SRC / "summary.json").read_text())
    P = json.loads((ROOT / SRC / "protocol.json").read_text())
    def rel(name):
        return f"{OUT}/{name}"
    n = len(list(csv.DictReader(open(ROOT / SRC / "trajectory/travelling-com.csv"))))
    return {"schema": "frontier.reuse-study-visuals/1", "visuals": [{
        "id": "voxelyze-travelling-wave", "study": "tissue-microcarrier", "title": "Soft-voxel toy body under a travelling actuation wave (Voxelyze)",
        "evidence_kind": "SimulationResult: model-only computed states from a CPU engine benchmark; not the proposed biological carrier",
        "engine_benchmark": {"engine": P["engine"]["name"], "commit": P["engine"]["commit"], "gpu_required": False, "build_wall_s": S["host_build"]["upstream_make_wall_s"],
                             "travelling_run_wall_s": 0.461, "note": "Timings are the producer's recorded wall seconds on one CPU host. Simulation time is a different quantity and is the only time shown in the media."},
        "biological_carrier": {"status": "proposed, not simulated", "note": "No cell, tissue, cilia, contraction or frog parameter is modelled. The toy body shares only a design pattern with the proposal."},
        "labels": {"model_only": True, "kind": "numerical soft-voxel ground-contact mechanics benchmark; not tissue, not a microcarrier, no fluid", "envelope_mm": [50, 30, 30], "centre_span_mm": 40, "assumed_mass_g": 45,
                   "voxel_nominal_mm": 10, "voxels": 45, "csv_contents": "voxel centres and imposed numerical temperature only; no orientations, deformed meshes or forces", "damping": "global damping is a numerical absolute-frame term, not fluid drag", "time": "simulation time (s), 241 recorded states, 0 to 1.495 s",
                   "assumed_parameters": P["parameter_provenance"]["assumed_not_measured"], "sourced_from_pinned_artifact": P["parameter_provenance"]["sourced_from_pinned_artifact"]},
        "posthoc_denominators": posthoc(), "records_kept": ["E zero-gravity control missed its predeclared bound (0.0175 BL vs 0.01); threshold not changed", "spatial refinement G did not converge (0.1532 -> 0.0188 BL)",
                         "post-hoc parity diagnostic supports an actuator-layout artefact; it is post hoc and not a convergence proof"],
        "caveats": ["Controls B-E were run on the longitudinal pattern; no control was run on the travelling pattern shown in the animation.", "Positions are recorded voxel centres; squares are drawn at nominal size, not deformed outlines.",
                    "Unvalidated against any organism; no simulator-derived relation is a biological law."],
        "sim_time_s": 1.495026, "states": n, "fps": FPS,
        "media": {k: ent(rel(v)) for k, v in MEDIA.items()}, "sources": [ent(p) for p in SOURCES], "renderer": [ent(p) for p in RENDERER],
        "source_commit": "origin/work/xenobot-simulators e6f1033 (files copied unchanged)"}]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", action="store_true")
    a = ap.parse_args()
    out = ROOT / OUT
    if not a.manifest:
        render(out)
    m = manifest(out)
    (ROOT / "artifacts/reuse-study-visuals/manifest.json").write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    print("ok", sys.argv)
