"""Chart video of the full-horizon arms from logged data only. NOT a spatial movie: no cell shapes are drawn."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze  # noqa: E402

ARMS = ("baseline", "nofeedback", "seed2")
COLOR = {"baseline": "#1f77b4", "nofeedback": "#d62728", "seed2": "#2ca02c"}


def series(parts: Path) -> dict:
    out = {}
    for n in ARMS:
        d = analyze.load(parts / n)
        t = sorted(d["recs"])
        out[n] = {"t": t, "n": [len(d["recs"][x]) for x in t],
                  "cdk1": [sum(r["CDK1"] for r in d["recs"][x]) / len(d["recs"][x]) for x in t],
                  "gl": [sum(r["g_l"] for r in d["recs"][x]) / len(d["recs"][x]) for x in t]}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", type=int, default=100)
    ap.add_argument("--workdir", required=True)
    a = ap.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    s = series(Path(a.parts))
    work = Path(a.workdir)
    work.mkdir(parents=True, exist_ok=True)
    keys = [("n", "cells (log)", True), ("cdk1", "mean CDK1 per cell", False), ("gl", "mean g_l per cell (cytokine seen by cell)", False)]
    for i in range(a.frames):
        tc = 2.0 * (i + 1) / a.frames
        fig, axs = plt.subplots(3, 1, figsize=(7, 7), sharex=True)
        for ax, (k, lab, lg) in zip(axs, keys):
            for n in ARMS:
                m = [j for j, x in enumerate(s[n]["t"]) if x <= tc]
                ax.plot([s[n]["t"][j] for j in m], [s[n][k][j] for j in m], color=COLOR[n], lw=1.1, label=n)
            if lg:
                ax.set_yscale("log")
            ax.set_ylabel(lab, fontsize=8)
            ax.set_xlim(0, 2)
        axs[0].legend(loc="upper left", fontsize=8)
        axs[2].set_xlabel("t (example units)")
        fig.suptitle(f"CHART from logged data, not a spatial movie | t = {tc:.2f}\n"
                     "Morpheus cell-cycle/CPM/PDE example, generic, uncalibrated, not fish growth", fontsize=8)
        fig.tight_layout()
        fig.savefig(work / f"f{i:04d}.png", dpi=100)
        plt.close(fig)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "12", "-i", str(work / "f%04d.png"),
                    "-vf", "format=yuv420p", a.out], check=True)
    print(a.out, a.frames)


if __name__ == "__main__":
    main()
