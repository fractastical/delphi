"""Render saved BETSE sensitivity trajectories; this module never simulates."""
from __future__ import annotations

from pathlib import Path

import numpy as np


PANELS = [
    ("baseline", "No intervention"),
    ("k2_open", "Dm_K ×2 · junctions open"),
    ("k2_blocked", "Dm_K ×2 · junctions blocked"),
    ("k5_open", "Dm_K ×5 · junctions open"),
    ("k5_blocked", "Dm_K ×5 · junctions blocked"),
    ("k10_open", "Dm_K ×10 · junctions open"),
    ("k10_blocked", "Dm_K ×10 · junctions blocked"),
    ("k10_open_half_dt", "Dm_K ×10 · open · half dt"),
]


def render(out: Path, result: dict) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter, FuncAnimation

    data = {name: np.load(out / result["files"][name]["trajectory"])
            for name, _ in PANELS}
    t = np.asarray(data["baseline"]["time_s"], dtype=float)
    xy = np.asarray(data["baseline"]["cell_centres_m"], dtype=float) * 1e6
    targeted = np.asarray(data["baseline"]["spot_cells"], dtype=int)
    states = {name: np.asarray(item["vm_cell_V"], dtype=float) * 1e3 for name, item in data.items()}
    vmin = min(float(arr.min()) for arr in states.values())
    vmax = max(float(arr.max()) for arr in states.values())
    # Keep the animation frame 16:9 with even pixel dimensions for yuv420p.
    # At 110 dpi this produces 1760x990; the old 16x8.5 figure emitted an odd
    # height (1760x935), which libx264 correctly refused to encode.
    fig, axes = plt.subplots(2, 4, figsize=(16, 9), constrained_layout=True)
    scatters = []
    for ax, (name, title) in zip(axes.flat, PANELS):
        sc = ax.scatter(xy[:, 0], xy[:, 1], c=states[name][0], s=48, cmap="coolwarm", vmin=vmin, vmax=vmax,
                        edgecolors="#293241", linewidths=0.2)
        if len(targeted):
            ax.scatter(xy[targeted, 0], xy[targeted, 1], s=72, facecolors="none", edgecolors="#111111", linewidths=1.2)
        ax.set_title(title, fontsize=10)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        scatters.append(sc)
    colorbar = fig.colorbar(scatters[0], ax=axes, fraction=0.02, pad=0.02)
    colorbar.set_label("cell membrane potential Vm (mV; simulated)")
    title = fig.suptitle("BETSE 1.5.0 · generic patch · same initialized world · not fin-calibrated", fontsize=13)
    footer = fig.text(0.5, 0.005, "Target cells outlined. Dm_K multipliers are dimensionless sensitivity settings, not channel measurements.",
                      ha="center", fontsize=9)

    def update(i: int):
        for scatter, (name, _) in zip(scatters, PANELS):
            scatter.set_array(states[name][i])
        title.set_text(f"BETSE 1.5.0 · same initialized world · t = {t[i]:.1f} s · simulated, not fin-calibrated")
        return [*scatters, title, footer]

    update(len(t) // 2)
    out.mkdir(parents=True, exist_ok=True)
    poster = out / "sensitivity-poster.png"
    fig.savefig(poster, dpi=125)
    animation = FuncAnimation(fig, update, frames=len(t), blit=False)
    video = out / "sensitivity.mp4"
    writer = FFMpegWriter(fps=8, codec="libx264", extra_args=["-pix_fmt", "yuv420p", "-threads", "2"])
    animation.save(video, writer=writer, dpi=110)
    plt.close(fig)
    return {
        "video": {"path": video.name, "sha256": __import__("hashlib").sha256(video.read_bytes()).hexdigest(), "bytes": video.stat().st_size},
        "poster": {"path": poster.name, "sha256": __import__("hashlib").sha256(poster.read_bytes()).hexdigest(), "bytes": poster.stat().st_size},
        "frames": len(t), "fps": 8,
    }
