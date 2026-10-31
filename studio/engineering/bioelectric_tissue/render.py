"""Animation and poster rendered from the saved BETSE trajectories (one frame per saved sample; no interpolation, no synthetic frames)."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter, FuncAnimation

from .analysis import WINDOW, load

PANELS = [("baseline", "baseline (no intervention)"), ("k_up", "K+ permeability x5 in targeted cells"), ("gj_block", "gap junctions blocked (all)"), ("k_up_gj_block", "both")]
LABEL = "SIMULATED: BETSE 1.5.0, generic 2-D cell patch with default parameters. Not measured, not calibrated, not a fish fin."


def render(work: Path, out: Path, res: dict | None = None) -> dict:
    work, out = Path(work), Path(out)
    D = {n: load(work / n / f"{n}.npz") for n, _ in PANELS}
    b = D["baseline"]; t = b["time_s"]; xy = b["cell_centres_m"] * 1e6; tgt = np.asarray(b["spot_cells"], dtype=int)
    allv = np.concatenate([D[n]["vm_cell_V"].ravel() for n in D]) * 1e3
    lo, hi = float(np.floor(allv.min())), float(np.ceil(allv.max()))
    fig = plt.figure(figsize=(12.5, 7.4), dpi=100)
    gs = fig.add_gridspec(2, 4, height_ratios=[3, 1.6], hspace=0.28, wspace=0.30)
    axes, sc = [], []
    area = (np.pi * (0.5 * 10.0) ** 2)                      # marker area in points^2, sized for ~10 um cell diameter at this scale (visual only)
    for j, (n, title) in enumerate(PANELS):
        ax = fig.add_subplot(gs[0, j]); axes.append(ax)
        s = ax.scatter(xy[:, 0], xy[:, 1], c=D[n]["vm_cell_V"][0] * 1e3, s=area * 3.0, cmap="viridis", vmin=lo, vmax=hi, edgecolors="none")
        if len(tgt): ax.scatter(xy[tgt, 0], xy[tgt, 1], s=area * 3.6, facecolors="none", edgecolors="#c0392b", linewidths=1.1)
        ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([]); ax.set_title(title, fontsize=9)
        sc.append(s)
    cb = fig.colorbar(sc[0], ax=axes, fraction=0.025, pad=0.01); cb.set_label("cell membrane potential Vm (mV, inside minus outside)")
    axv = fig.add_subplot(gs[1, :2]); axg = fig.add_subplot(gs[1, 2:])
    cols = {"baseline": "#7f8c8d", "k_up": "#c0392b", "gj_block": "#2471a3", "k_up_gj_block": "#7d3c98"}
    for n, title in PANELS:
        axv.plot(t, (D[n]["vm_cell_V"][:, tgt].mean(axis=1) if len(tgt) else D[n]["vm_cell_V"].mean(axis=1)) * 1e3, color=cols[n], label=title, lw=1.4)
        axg.plot(t, D[n]["gj_open_fraction_mem"].mean(axis=1), color=cols[n], lw=1.4)
    for ax in (axv, axg): ax.axvspan(*WINDOW, color="#f5b041", alpha=0.18, lw=0)
    axv.set_xlabel("time (s)"); axv.set_ylabel("mean Vm, targeted cells (mV)"); axg.set_xlabel("time (s)"); axg.set_ylabel("gap-junction open fraction")
    axv.legend(fontsize=7, loc="lower left", frameon=False)
    cur = [ax.axvline(t[0], color="k", lw=0.8) for ax in (axv, axg)]
    ttl = fig.suptitle("", fontsize=10); fig.text(0.5, 0.012, LABEL + "  Red rings: cells targeted by the K+ permeability change. Shaded: intervention window.", ha="center", fontsize=8)

    def frame(i):
        for s, (n, _) in zip(sc, PANELS): s.set_array(D[n]["vm_cell_V"][i] * 1e3)
        for c in cur: c.set_xdata([t[i], t[i]])
        ttl.set_text(f"t = {t[i]:.1f} s    ({len(xy)} cells; intervention window {WINDOW[0]:.0f} to {WINDOW[1]:.0f} s)")
        return sc
    frame(len(t) // 2 + 1); fig.savefig(out / "poster.png", dpi=110)
    anim = FuncAnimation(fig, frame, frames=len(t), blit=False)
    anim.save(out / "bioelectric_tissue.mp4", writer=FFMpegWriter(fps=5, codec="libx264", extra_args=["-pix_fmt", "yuv420p"]))
    plt.close(fig)
    return {"video": "bioelectric_tissue.mp4", "poster": "poster.png", "frames": int(len(t))}
