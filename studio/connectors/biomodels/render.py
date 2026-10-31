"""Render the replay's trajectory CSVs as a captioned MP4, a still poster and a manifest.

Every plotted number is a row of a committed replay CSV, read after checking its sha256 against the
receipt. Nothing is interpolated, smoothed or generated: a frame at video time k shows CSV row
`row_index(k)`. The drawing is two-cell Delta-Notch concentrations against model time, and the
(Notch, Delta) phase portrait of each cell, for the three replay scenarios. It draws no cell, tissue
or morphology: the model has none, and no observed cell shape exists in this repository.

The reusable parts (`encode_mp4`, `file_record`, `ffmpeg_version`) know nothing about this model; a
renderer for another simulation can import them and supply its own frames.

  PYTHONPATH=. python3 -m connectors.biomodels.render --receipt-dir <dir with receipt.json and CSVs> --out-dir <dir>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402

FFMPEG, FFPROBE = "/usr/bin/ffmpeg", "/usr/bin/ffprobe"
W, H, DPI, FPS = 1280, 720, 100, 24
MOTION_FRAMES, HOLD_FRAMES = 336, 48          # 14 s of motion over the whole model-time range, then a 2 s hold
MAX_VIDEO_BYTES = 8_000_000
SCENARIOS = (
    ("as_published", "trajectory_as_published.csv"),
    ("symmetric_baseline", "trajectory_symmetric_baseline.csv"),
    ("no_notch_feedback_b0", "trajectory_no_notch_feedback_b0.csv"),
)
C1, C2 = "#0072B2", "#D55E00"                   # cell 1 blue, cell 2 orange (distinguishable under common colour-vision deficiencies)
CAPTION = ("SIMULATION computed from the published SBML model; not an observation.  Time and concentrations are non-dimensional (model time).  "
           "Two abstract cells: this is not tissue, not a fin, and no cell shape is modelled or observed.")


# ---- reusable, model-independent -----------------------------------------------------------


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_record(path: Path) -> dict:
    return {"file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size}


def ffmpeg_version() -> str:
    return subprocess.run([FFMPEG, "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]


def probe(path: Path) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,pix_fmt,width,height,nb_frames,r_frame_rate:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    s = d["streams"][0]
    return {"codec": s["codec_name"], "pix_fmt": s["pix_fmt"], "width": s["width"], "height": s["height"], "frames": int(s["nb_frames"]),
            "r_frame_rate": s["r_frame_rate"], "duration_s": float(d["format"]["duration"])}


def encode_mp4(frames, out: Path, *, width: int, height: int, fps: int, threads: int = 2) -> str:
    """Pipe RGBA frames (bytes) to ffmpeg (H.264, yuv420p). Returns the sha256 of the raw frame stream.

    That digest depends only on what was drawn, not on the encoder build, so it can be compared across machines.
    """
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
           "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-preset", "medium", "-threads", str(threads),
           "-fflags", "+bitexact", "-flags:v", "+bitexact", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    h = hashlib.sha256()
    try:
        for fr in frames:
            h.update(fr)
            proc.stdin.write(fr)
    finally:
        proc.stdin.close()
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg exited {rc}")
    return h.hexdigest()


# ---- this model ------------------------------------------------------------------------------


class RenderRefused(ValueError):
    pass


def load(receipt_dir: Path) -> tuple[dict, dict]:
    """The receipt and the three scenario arrays, each CSV checked against the receipt's digest first."""
    receipt = json.loads((receipt_dir / "receipt.json").read_text())
    data = {}
    for name, fname in SCENARIOS:
        got, want = sha256_file(receipt_dir / fname), receipt["output_sha256"].get(fname)
        if got != want:
            raise RenderRefused(f"{fname}: sha256 {got} != receipt {want}; refusing to draw data the receipt does not describe")
        with open(receipt_dir / fname, newline="") as fh:
            rows = list(csv.reader(fh))
        header, body = rows[0], np.array(rows[1:], dtype=float)
        if header != ["time", "delta1", "delta2", "notch1", "notch2"]:
            raise RenderRefused(f"{fname}: unexpected columns {header}")
        data[name] = body
    lens = {len(v) for v in data.values()}
    if len(lens) != 1 or not all(np.array_equal(v[:, 0], data["as_published"][:, 0]) for v in data.values()):
        raise RenderRefused("scenarios do not share one time grid")
    return receipt, data


def row_index(k: int, n_rows: int) -> int:
    """CSV row shown at video frame k: motion frames sweep rows 0..n-1 (nearest row, no interpolation); hold frames stay on the last."""
    k = min(k, MOTION_FRAMES - 1)
    return round(k * (n_rows - 1) / (MOTION_FRAMES - 1))


def _titles(data: dict) -> dict:
    a = data["as_published"][0]
    pct = 100 * (a[1] - a[2]) / a[1]
    return {"as_published": f"As published: cell 2 starts {pct:.1f}% below cell 1",
            "symmetric_baseline": "Baseline: no perturbation (cells identical)",
            "no_notch_feedback_b0": "Counterfactual b = 0 (added here, not in the source)"}


def build_figure(receipt: dict, data: dict):
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor="white")
    gs = GridSpec(2, 3, figure=fig, left=0.055, right=0.985, top=0.835, bottom=0.175, wspace=0.22, hspace=0.50)
    titles = _titles(data)
    t = data["as_published"][:, 0]
    artists = []
    fig.text(0.5, 0.955, "Two-cell Delta–Notch lateral inhibition  —  BioModels BIOMD0000001047 (Collier et al. 1996)  —  SIMULATION",
             ha="center", va="center", fontsize=14, fontweight="bold")
    clock = fig.text(0.5, 0.905, "", ha="center", va="center", fontsize=12)
    for j, (name, _) in enumerate(SCENARIOS):
        d = data[name]
        ax = fig.add_subplot(gs[0, j])
        ax.set_title(titles[name], fontsize=9.5, loc="left")
        ax.set_xlim(t[0], t[-1]); ax.set_ylim(-0.03, 1.06)
        ax.set_xlabel("model time (non-dimensional)", fontsize=8.5); ax.set_ylabel("concentration (non-dim.)", fontsize=8.5)
        ax.tick_params(labelsize=8); ax.grid(alpha=0.25)
        ln = [ax.plot([], [], color=c, ls=ls, lw=2)[0] for c, ls in ((C1, "-"), (C2, "-"), (C1, "--"), (C2, "--"))]   # delta1, delta2, notch1, notch2
        cur = ax.axvline(t[0], color="0.35", lw=1)
        ax2 = fig.add_subplot(gs[1, j])
        ax2.set_xlim(-0.03, 1.06); ax2.set_ylim(-0.03, 1.06)
        ax2.set_xlabel("Notch (non-dim.)", fontsize=8.5); ax2.set_ylabel("Delta (non-dim.)", fontsize=8.5)
        ax2.tick_params(labelsize=8); ax2.grid(alpha=0.25)
        tr2 = ax2.plot([], [], color=C2, lw=4.5, alpha=0.45)[0]      # cell 2 drawn wider underneath so coincident cells stay visible
        tr1 = ax2.plot([], [], color=C1, lw=1.8)[0]
        m2 = ax2.plot([], [], "o", mfc="white", mec=C2, mew=2, ms=8)[0]
        m1 = ax2.plot([], [], "o", color=C1, ms=5)[0]
        ax2.plot(d[0, 3], d[0, 1], "s", color=C1, ms=5, mfc="none"); ax2.plot(d[0, 4], d[0, 2], "s", color=C2, ms=7, mfc="none")
        gap = float(np.max(np.abs(d[:, 1] - d[:, 2])))
        # centre of the axes: every trace hugs the bottom and right edges, and the final states sit in the corners
        ax2.text(0.5, 0.58, f"max |Delta1 − Delta2| = {gap:.2g}", transform=ax2.transAxes, ha="center", fontsize=8,
                 bbox=dict(fc="white", ec="0.7", alpha=0.9))
        artists.append((d, ln, cur, tr1, tr2, m1, m2))
    h = [plt.Line2D([], [], color=C1, lw=2), plt.Line2D([], [], color=C2, lw=2), plt.Line2D([], [], color="0.2", ls="-", lw=2),
         plt.Line2D([], [], color="0.2", ls="--", lw=2), plt.Line2D([], [], marker="s", color="0.2", mfc="none", ls="", ms=6)]
    fig.legend(h, ["cell 1", "cell 2", "Delta", "Notch", "initial state"], loc="upper left", bbox_to_anchor=(0.005, 0.905), ncol=5, fontsize=8.5,
               frameon=False, handlelength=1.6, columnspacing=1.0)
    fig.text(0.5, 0.075, CAPTION, ha="center", va="center", fontsize=8.6, wrap=True)
    fig.text(0.5, 0.032, f"model file sha256 {receipt['model']['sha256'][:16]}…   replay: libroadrunner {receipt['engine']['version']}, one run per panel, "
             "every point is a row of the replay CSV (no interpolation)", ha="center", va="center", fontsize=8, color="0.3")
    return fig, artists, clock


def draw(artists, clock, rows_k: int, t_row: float):
    clock.set_text(f"model time t = {t_row:5.1f}   (non-dimensional; unit not declared by the model)")
    for d, ln, cur, tr1, tr2, m1, m2 in artists:
        s = d[: rows_k + 1]
        for line, col in zip(ln, (1, 2, 3, 4)):
            line.set_data(s[:, 0], s[:, col])
        cur.set_xdata([s[-1, 0]])
        tr1.set_data(s[:, 3], s[:, 1]); tr2.set_data(s[:, 4], s[:, 2])
        m1.set_data([s[-1, 3]], [s[-1, 1]]); m2.set_data([s[-1, 4]], [s[-1, 2]])


def render(receipt_dir: Path, out_dir: Path, *, stem: str = "delta_notch_replay", enforce_bounds: bool = True) -> dict:
    receipt, data = load(receipt_dir)
    fig, artists, clock = build_figure(receipt, data)
    n_rows = len(data["as_published"])
    t = data["as_published"][:, 0]
    total = MOTION_FRAMES + HOLD_FRAMES    # read at call time so a test can shorten the clip

    def frames():
        for k in range(total):
            i = row_index(k, n_rows)
            draw(artists, clock, i, t[i])
            fig.canvas.draw()
            buf = np.asarray(fig.canvas.buffer_rgba())
            if buf.shape != (H, W, 4):
                raise RenderRefused(f"canvas is {buf.shape}, expected {(H, W, 4)}")
            yield buf.tobytes()

    out_dir.mkdir(parents=True, exist_ok=True)
    video, poster = out_dir / f"{stem}.mp4", out_dir / f"{stem}_poster.png"
    frames_sha = encode_mp4(frames(), video, width=W, height=H, fps=FPS)
    draw(artists, clock, n_rows - 1, t[-1])
    fig.savefig(poster, dpi=DPI, facecolor="white")
    plt.close(fig)
    info = probe(video)
    if enforce_bounds and (video.stat().st_size >= MAX_VIDEO_BYTES or not 10 <= info["duration_s"] <= 20):
        raise RenderRefused(f"video out of bounds: {video.stat().st_size} bytes, {info['duration_s']} s")
    csvs = {fname: {"sha256": receipt["output_sha256"][fname], "bytes": (receipt_dir / fname).stat().st_size, "rows": n_rows, "scenario": name}
            for name, fname in SCENARIOS}
    manifest = {
        "manifest_schema": "biomodels-video-manifest-0.1 (connector-local)",
        "evidence_kind": "simulated: a rendering of replay output; not an observation of any biological system",
        "claims": {"shows": "two-cell Delta-Notch concentrations vs model time and (Notch, Delta) phase portraits for three replay scenarios",
                   "does_not_show": ["observed cell shape or morphology", "tissue", "a fin", "any flying-fish structure", "real time or physical concentration units"],
                   "captions": {"header": "Two-cell Delta-Notch lateral inhibition - BioModels BIOMD0000001047 (Collier et al. 1996) - SIMULATION", "footer": CAPTION}},
        "inputs": {"model_sha256": receipt["model"]["sha256"], "receipt_sha256": sha256_file(receipt_dir / "receipt.json"),
                   "replay_code_sha256": receipt["run"]["code_sha256"], "csv": csvs},
        "render": {"code_file": "connectors/biomodels/render.py", "code_sha256": sha256_file(Path(__file__)), "matplotlib": matplotlib.__version__,
                   "numpy": np.__version__, "python": platform.python_version(), "ffmpeg": ffmpeg_version(), "threads": 2,
                   "frames_sha256": frames_sha, "frames_sha256_note": "sha256 of the raw RGBA stream sent to the encoder; depends on the drawing, not the encoder build"},
        "time_mapping": {"fps": FPS, "motion_frames": MOTION_FRAMES, "hold_frames": HOLD_FRAMES, "total_frames": total,
                         "model_time_range": [float(t[0]), float(t[-1])], "csv_rows": n_rows,
                         "rule": "frame k < motion_frames shows csv row round(k*(rows-1)/(motion_frames-1)); later frames repeat the last row",
                         "model_time_per_motion_frame": float((t[-1] - t[0]) / (MOTION_FRAMES - 1)),
                         "interpolation": "none: only rows present in the CSV are drawn", "linear_in_model_time": True,
                         "note": "most of the change happens before model time 30; the second half of the video is the settled state"},
        "dimensions": {"width": W, "height": H, "dpi": DPI},
        "video": {**file_record(video), **info}, "poster": {**file_record(poster), "width": W, "height": H, "frame": "last row (model time %.1f), not a separate simulation" % t[-1]},
    }
    (out_dir / f"{stem}_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True))
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="connectors.biomodels.render")
    ap.add_argument("--receipt-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        m = render(a.receipt_dir, a.out_dir)
    except RenderRefused as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({"video": m["video"], "poster": m["poster"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
