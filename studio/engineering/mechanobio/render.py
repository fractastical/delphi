"""Render existing computed trajectories; never changes simulation data."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .model import digest  # noqa: E402
from .sweep import artifact, write_json  # noqa: E402


def render(directory):
    root = Path(directory)
    trajectory_path = root / "feedback-trajectory.json"
    if not trajectory_path.exists():
        trajectory_path = root / "trajectory.json"
    trajectory = json.loads(trajectory_path.read_text())
    frames = trajectory["frames"]
    t = np.array([f["t_s"] for f in frames])
    force = np.array([f["traction_pN"] for f in frames])
    flow = np.array([f["retrograde_nm_s"] for f in frames])
    xs = np.array([f["substrate_nm"] for f in frames])
    n = len(frames[0]["clutches"])
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 7.2), dpi=100)
    fig.patch.set_facecolor("#f5f5ef")
    for ax in axes.ravel():
        ax.set_facecolor("#fffefa")
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("SIMULATED · cell–ECM motor clutches\nForce slows actin; tensile load accelerates bond rupture", fontsize=17, color="#123d43")
    ax = axes[0, 0]
    ax.plot(t, force, color="#147d86", lw=2)
    cursor = ax.axvline(0, color="#d35932")
    ax.set(xlabel="time (s)", ylabel="traction (pN)", title="Traction from actual bound springs")
    ax = axes[0, 1]
    bars = ax.bar(np.arange(n), [c["force_pN"] for c in frames[0]["clutches"]], color="#147d86")
    max_clutch = max(abs(c["force_pN"]) for f in frames for c in f["clutches"])
    ax.set(xlabel="clutch index", ylabel="force (pN)", ylim=(-0.1 * max_clutch, 1.15 * max_clutch), title="Orange = engaged; gray = disengaged")
    ax = axes[1, 0]
    ax.plot(t, flow, color="#8254a2")
    cursor2 = ax.axvline(0, color="#d35932")
    ax.set(xlabel="time (s)", ylabel="retrograde actin flow (nm/s)", title="Motor force–velocity feedback")
    ax = axes[1, 1]
    ax.plot(t, xs, color="#147d86", label="substrate displacement (nm)")
    ax.set(xlabel="time (s)", ylabel="substrate displacement (nm)", title="Relaxing standard-linear-solid contact")
    cursor3 = ax.axvline(0, color="#d35932")
    counter = fig.text(0.5, 0.062, "", ha="center", fontsize=11)
    fig.text(0.5, 0.018, "Published equations: Gong et al., PNAS 2018, doi:10.1073/pnas.1716620115 · scenario parameters; no fish calibration", ha="center", fontsize=9)
    fig.tight_layout(rect=(0.01, 0.09, 0.99, 0.88))
    indices = np.rint(np.linspace(0, len(frames) - 1, 180)).astype(int)
    command = ["ffmpeg", "-loglevel", "error", "-y", "-threads", "2", "-f", "rawvideo", "-vcodec", "rawvideo",
               "-pix_fmt", "rgb24", "-s", "1280x720", "-r", "15", "-i", "-", "-an", "-c:v", "libx264",
               "-threads", "2", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(root / "mechanobio.mp4")]
    with subprocess.Popen(command, stdin=subprocess.PIPE) as proc:
        for frame_index in indices:
            frame = frames[frame_index]
            for line in (cursor, cursor2, cursor3):
                line.set_xdata([frame["t_s"], frame["t_s"]])
            for bar, clutch in zip(bars, frame["clutches"], strict=True):
                bar.set_height(clutch["force_pN"])
                bar.set_color("#d35932" if clutch["bound"] else "#c8ccca")
            counter.set_text(f"t = {frame['t_s']:.2f} s   ·   {frame['bound_clutches']}/{n} engaged   ·   F = {frame['traction_pN']:.2f} pN   ·   v = {frame['retrograde_nm_s']:.1f} nm/s")
            fig.canvas.draw()
            rgba = np.asarray(fig.canvas.buffer_rgba())
            proc.stdin.write(np.ascontiguousarray(rgba[:, :, :3]).tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg render failed")
    fig.savefig(root / "poster.png", dpi=100)
    plt.close(fig)
    sweep = json.loads((root / "sweep.json").read_text())
    rows = sweep["rows"]
    stiffness = sorted({row["long_term_stiffness_pN_nm"] for row in rows})
    viscosity = sorted({row["viscosity_pN_s_nm"] for row in rows})
    z = np.array([[next(row["mean_traction_pN"] for row in rows if row["long_term_stiffness_pN_nm"] == k and row["viscosity_pN_s_nm"] == v)
                   for v in viscosity] for k in stiffness])
    fig, ax = plt.subplots(figsize=(9, 6), dpi=140)
    def log_edges(values):
        logs = np.log(values)
        return np.exp(np.r_[logs[0] - (logs[1] - logs[0]) / 2,
                            (logs[:-1] + logs[1:]) / 2,
                            logs[-1] + (logs[-1] - logs[-2]) / 2])

    xedges, yedges = log_edges(viscosity), log_edges(stiffness)
    image = ax.pcolormesh(xedges, yedges, z, shading="flat", cmap="viridis")
    ax.set(xscale="log", yscale="log", xlabel="viscosity (pN s/nm)", ylabel="long-term contact stiffness (pN/nm)",
           title=f"SIMULATED · mean traction\n{rows[0]['n']} stochastic replicates per cell; assumed cell parameters")
    ax.set_xlim(xedges[0], xedges[-1])
    ax.set_ylim(yedges[0], yedges[-1])
    fig.colorbar(image, ax=ax, label="time-mean traction (pN)")
    fig.text(0.5, 0.01, "Monte Carlo variation only · not biological uncertainty · no modulus conversion or fish calibration", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(root / "response-surface.png")
    plt.close(fig)
    manifest = {"schema": "frontier.mechanobio.render-manifest/1", "evidence_kind": "render_of_simulation",
                "input_trajectory": artifact(trajectory_path, "input"),
                "input_sweep": artifact(root / "sweep.json", "input"),
                "frame_indices_sha256": digest(indices.tolist()), "frames": len(indices), "fps": 15,
                "render_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "matplotlib": matplotlib.__version__,
                "ffmpeg": subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0],
                "artifacts": [artifact(root / name, "output", media) for name, media in
                              [("mechanobio.mp4", "video/mp4"), ("poster.png", "image/png"), ("response-surface.png", "image/png")]]}
    write_json(root / "render-manifest.json", manifest)
    print(json.dumps({"rendered_frames": len(indices), "trajectory_sha256": manifest["input_trajectory"]["sha256"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("directory", type=Path)
    render(parser.parse_args().directory)
