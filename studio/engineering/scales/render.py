"""Render saved simulation states of one scale to MP4 / GIF / poster.  Every pixel comes from simulated state;
nothing is drawn to look like a micrograph (no fluorescence colouring, no cells, no texture)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from engineering.geometry.turntable import encode_gif, encode_mp4, probe  # noqa: E402

SETTINGS = {
    "width_px": 960, "height_px": 540, "dpi": 100, "fps": 12,
    "E_cmap": "viridis", "E_range": [0.0, 0.8], "growth_cmap": "cividis",
    "mp4": {"codec": "libx264", "preset": "slow", "crf": 24, "pix_fmt": "yuv420p", "threads": 1},
    "gif": {"width_px": 640, "height_px": 360, "frame_step": 3, "colors": 96},
    "poster_frame_h": 40.0,
}
LIMITS = {"mp4_max_bytes": 4_000_000, "gif_max_bytes": 6_000_000, "poster_max_bytes": 400_000}

CAPTION = [
    "SIMULATED Erk activity on one regenerating zebrafish scale (520 um radius). Model: Hayden et al. 2021, Table 1 parameters.",
    "Growth: cell area +0.006/h after each Erk peak (measured, De Simone et al. 2021); 24 h growth window assumed.",
    "Rendering of model state in reference (material) coordinates, not a microscope image. Transfer to flying-fish scales unknown.",
]


def _frame(res: dict, s: dict, i: int, gmax: float) -> np.ndarray:
    st = SETTINGS
    g = res["run"].geometry
    half = g.domain_um / 2
    ext = [-half, half, -half, half]
    fig = plt.figure(figsize=(st["width_px"] / st["dpi"], st["height_px"] / st["dpi"]), dpi=st["dpi"])
    fig.patch.set_facecolor("white")
    ax1 = fig.add_axes([0.02, 0.24, 0.31, 0.66]); ax2 = fig.add_axes([0.35, 0.24, 0.31, 0.66])
    ax3 = fig.add_axes([0.74, 0.30, 0.24, 0.56])
    mask = ~res["scale"]
    E = np.ma.array(res["E"][i], mask=mask)
    G = np.ma.array(np.exp(res["loga"][i].astype(float)), mask=mask)
    im1 = ax1.imshow(E, origin="lower", extent=ext, cmap=st["E_cmap"], vmin=st["E_range"][0], vmax=st["E_range"][1],
                     interpolation="nearest")
    im2 = ax2.imshow(G, origin="lower", extent=ext, cmap=st["growth_cmap"], vmin=1.0, vmax=gmax, interpolation="nearest")
    th = np.linspace(0, 2 * np.pi, 200)
    for ax in (ax1, ax2):
        ax.plot(g.scale_radius_um * np.cos(th), g.scale_radius_um * np.sin(th), color="0.3", lw=0.8)
        ax.plot(-g.source_offset_um + g.source_radius_um * np.cos(th), g.source_radius_um * np.sin(th),
                color="white", lw=0.8)
        ax.set_xlim(-560, 560); ax.set_ylim(-560, 560); ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.plot([-500, -300], [-540, -540], color="k", lw=2)
        ax.text(-400, -525, "200 um", ha="center", va="bottom", fontsize=7)
    ax1.set_title("Erk activity E (fraction of total Erk)", fontsize=9)
    ax2.set_title("cumulative cell-area ratio a/a0", fontsize=9)
    ax1.text(-g.source_offset_um, g.source_radius_um + 15, "source", color="white", fontsize=7, ha="center")
    ax1.text(-540, 520, "anterior", fontsize=7, color="0.3"); ax1.text(540, 520, "posterior", fontsize=7, color="0.3", ha="right")
    c1 = fig.colorbar(im1, ax=ax1, fraction=0.04, pad=0.01); c1.ax.tick_params(labelsize=6)
    c2 = fig.colorbar(im2, ax=ax2, fraction=0.04, pad=0.01); c2.ax.tick_params(labelsize=6)
    t = res["t_h"]; area = res["area_um2"] / res["area_um2"][0]
    ax3.plot(t, area, color="0.75", lw=1)
    ax3.plot(t[: i + 1], area[: i + 1], color="k", lw=1.5)
    for ta in s["rim_arrival_times_h"]:
        ax3.axvline(ta, color="tab:green", lw=0.6, ls=":")
    ax3.set_xlim(0, t[-1]); ax3.set_ylim(0.98, area.max() * 1.02)
    ax3.set_xlabel("simulated time (h)", fontsize=8); ax3.set_ylabel("scale area / initial", fontsize=8)
    ax3.tick_params(labelsize=7)
    ax3.set_title(f"t = {t[i]:5.1f} h   R_eff = {np.sqrt(res['area_um2'][i] / np.pi):4.0f} um", fontsize=9)
    ax3.text(0.02, 0.97, "dotted: wave reaches posterior rim", transform=ax3.transAxes, fontsize=6, va="top",
             color="tab:green")
    for k, line in enumerate(CAPTION):
        fig.text(0.02, 0.15 - 0.05 * k, line, fontsize=7.4, weight="bold" if k == 0 else "normal")
    fig.canvas.draw()
    rgb = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
    plt.close(fig)
    return rgb


def render(res: dict, s: dict, out: Path) -> dict:
    gmax = float(np.exp(res["loga"][-1][res["scale"]].astype(float)).max())
    frames = [_frame(res, s, i, gmax) for i in range(len(res["t_h"]))]
    mp4, gif, poster = out / "erk_growth.mp4", out / "erk_growth.gif", out / "poster.png"
    encode_mp4(frames, mp4, SETTINGS)
    encode_gif(frames, gif, SETTINGS)
    pi = int(np.argmin(np.abs(res["t_h"] - SETTINGS["poster_frame_h"])))
    Image.fromarray(frames[pi]).save(poster, optimize=False)
    pr = probe(mp4)
    sizes = {"mp4": mp4.stat().st_size, "gif": gif.stat().st_size, "poster": poster.stat().st_size}
    h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    return {
        "video": {"file": mp4.name, "sha256": h(mp4), "bytes": sizes["mp4"], "codec": pr["codec_name"],
                  "width": pr["width"], "height": pr["height"], "fps": SETTINGS["fps"],
                  "n_frames": int(pr["nb_read_frames"]), "sim_hours_per_frame": float(res["t_h"][1] - res["t_h"][0])},
        "gif": {"file": gif.name, "sha256": h(gif), "bytes": sizes["gif"]},
        "poster": poster.name, "poster_sha256": h(poster), "poster_sim_time_h": float(res["t_h"][pi]),
        "settings": SETTINGS, "limits": LIMITS, "caption": CAPTION,
        "checks": {"frames_match": int(pr["nb_read_frames"]) == len(frames),
                   "within_size_limits": sizes["mp4"] <= LIMITS["mp4_max_bytes"] and sizes["gif"] <= LIMITS["gif_max_bytes"]
                   and sizes["poster"] <= LIMITS["poster_max_bytes"]},
    }
