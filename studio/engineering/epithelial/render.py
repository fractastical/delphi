"""Render one arm as a spatial movie of the ACTUAL CPM lattice with the actual cell tracks on it.

Left panel: frames written by Morpheus' TiffPlotter, i.e. the simulated cell lattice itself,
not a redrawing of logged numbers. Medium is black, each cell keeps its own colour.
Cell-centre tracks come from logger.csv and are the actual logged trajectories.
Right panel: gap area over model time, the same series analyze.py scores.

Nothing is interpolated or smoothed. Frames are at the arm's frame_step; the curve is at
its log_step, so the marker snaps to the nearest logged time at or before the frame.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

NODE_AREA_UM2 = 0.8494869358669834
NODE_LEN_UM = math.sqrt(NODE_AREA_UM2)
TOTAL_NODES = 40000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=8)
    ap.add_argument("--trail", type=int, default=12, help="logged samples of track history to draw")
    a = ap.parse_args()
    d = Path(a.arm_dir)
    arm = json.loads((d / "build.json").read_text())["arm"]

    by = defaultdict(dict)
    with (d / "logger.csv").open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            by[float(r["time"])][int(float(r["cell.id"]))] = (
                float(r["cell.center.x"]), float(r["cell.center.y"]), float(r["cell.volume"]))
    times = sorted(by)
    gap = [(t, (TOTAL_NODES - sum(v for _, _, v in by[t].values())) * NODE_AREA_UM2) for t in times]
    gt, gy = zip(*gap)

    im = Image.open(sorted(d.glob("*.tif*"))[0])
    nfr = getattr(im, "n_frames", 1)
    rng = np.random.default_rng(0)                      # colour map only; no model randomness here
    lut = rng.random((70000, 3)) * 0.65 + 0.3
    lut[0] = (0.04, 0.04, 0.06)                          # medium

    work = Path(a.out).parent / "_frames"
    work.mkdir(parents=True, exist_ok=True)
    for i in range(nfr):
        im.seek(i)
        lat = np.array(im)
        t = i * arm["frame_step"]
        tl = max([x for x in times if x <= t], default=times[0])
        fig, ax = plt.subplots(1, 2, figsize=(11, 5.2), dpi=100,
                               gridspec_kw={"width_ratios": [1, 1.08]})
        ax[0].imshow(lut[np.clip(lat, 0, 69999)], origin="lower",
                     extent=[0, lat.shape[1] * NODE_LEN_UM, 0, lat.shape[0] * NODE_LEN_UM],
                     interpolation="nearest")
        hist = [x for x in times if x <= tl][-a.trail:]
        for cid in by[tl]:
            pts = [(by[h][cid][0], by[h][cid][1]) for h in hist if cid in by[h]]
            # periodic lattice: break a track where it wraps, never draw the wrap segment
            seg, cur = [], [pts[0]] if pts else []
            for p, q in zip(pts, pts[1:]):
                (seg.append(cur), cur := [q])[0] if (abs(p[0] - q[0]) > 50 or abs(p[1] - q[1]) > 50) else cur.append(q)
            seg.append(cur)
            for s in seg:
                if len(s) > 1:
                    xs, ys = zip(*s)
                    ax[0].plot(np.array(xs) * NODE_LEN_UM, np.array(ys) * NODE_LEN_UM,
                               lw=1.1, color="white", alpha=0.75, solid_capstyle="round")
        ax[0].set_xlabel("x (µm)"); ax[0].set_ylabel("y (µm)")
        ax[0].set_title(f"{arm['name']} — CPM lattice, actual cell tracks\nmodel time {t:g}", fontsize=10)
        ax[1].plot(gt, gy, lw=1.8, color="#d1495b")
        ax[1].axvline(tl, color="#444", lw=1, ls="--")
        ax[1].plot([tl], [dict(gap)[tl]], "o", ms=7, color="#d1495b")
        ax[1].set_xlabel("model time (model units — not minutes)")
        ax[1].set_ylabel("gap area (µm², via declared node scale)")
        ax[1].set_ylim(bottom=0); ax[1].grid(alpha=0.25)
        ax[1].set_title("gap area from logged cell volumes", fontsize=10)
        fig.tight_layout()
        fig.savefig(work / f"f{i:04d}.png")
        plt.close(fig)

    out = Path(a.out)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps),
                    "-i", str(work / "f%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", str(out)], check=True)
    poster = out.with_name(out.stem + "_poster.png")
    # poster is a frame of the finished video, not a re-render
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.2", "-i", str(out),
                    "-frames:v", "1", str(poster)], check=True)
    for p in work.glob("*.png"):
        p.unlink()
    work.rmdir()
    print(out, poster, f"{nfr} frames")


if __name__ == "__main__":
    main()
