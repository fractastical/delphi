"""Rendering consumes saved simulation states; it never reruns the simulator."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .model import code_hashes  # noqa: E402


def render(output: Path):
    paths = [output / f"{name}.json" for name in ("baseline", "sodium_reduced", "disconnected")]
    results = [json.loads(p.read_text()) for p in paths]
    titles = ["Baseline · coupled", "Na conductance × 0.35", "Gap coupling removed"]
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor="#091820")
    layout = fig.add_gridspec(3, 2, left=.07, right=.90, top=.84, bottom=.13,
                             width_ratios=[1.35, 1], wspace=.25, hspace=.4)
    fig.text(.07, .95, "Membrane currents → electrical cell network", fontsize=22, weight="bold")
    fig.text(.07, .89, "SIMULATED · Hodgkin–Huxley squid-axon kinetics · assumed 12-cell gap network", fontsize=11, color="#6ce0de")
    colors = ["#63e8dc", "#f8af57", "#c69aef"]
    cursor_lines, scatters = [], []
    times = np.array(results[0]["time_ms"])
    for row, (result, title, color) in enumerate(zip(results, titles, colors)):
        heat = fig.add_subplot(layout[row, 0])
        volts = np.array(result["voltage_mV"])
        image = heat.imshow(volts.T, origin="lower", aspect="auto", extent=[times[0], times[-1], -.5, 11.5],
                            vmin=-80, vmax=45, cmap="turbo", interpolation="nearest")
        heat.set_title(title + f" · {result['metrics']['cells_crossing_0mV']}/12 cells cross 0 mV", fontsize=10, loc="left")
        heat.set_ylabel("cell index", fontsize=8)
        heat.set_yticks([0, 5, 11])
        if row == 2:
            heat.set_xlabel("model time [ms]")
        cursor_lines.append(heat.axvline(0, color="white", lw=1.3))
        network = fig.add_subplot(layout[row, 1])
        positions = np.arange(12)
        network.plot(positions, np.zeros(12), color="#48616d", lw=3)
        scatter = network.scatter(positions, np.zeros(12), c=volts[0], s=240, cmap="turbo", vmin=-80, vmax=45,
                                  edgecolors="white", linewidths=.5)
        scatters.append(scatter)
        network.set_xlim(-.8, 11.8)
        network.set_ylim(-1, 1)
        network.set_yticks([])
        network.set_xticks([0, 5, 11])
        network.set_title("equal-area cells · sealed boundaries", fontsize=9, color=color)
        if row == 2:
            network.set_xlabel("cell index (no measured geometry)", fontsize=9)
    colorbar_axis = fig.add_axes([.93, .2, .012, .55])
    fig.colorbar(image, cax=colorbar_axis, label="membrane voltage [mV]")
    caption = fig.text(.07, .055, "", fontsize=10)
    fig.text(.07, .02, "DOI: 10.1113/jphysiol.1952.sp004764 · 6.3°C · Fixed ion reservoirs · No calibrated fin-development bridge", fontsize=9, color="#a6bac4")
    indices = np.unique(np.round(np.linspace(0, len(times) - 1, 180)).astype(int))
    command = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "1280x720",
               "-r", "24", "-i", "-", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24",
               "-preset", "fast", "-threads", "1", "-movflags", "+faststart", str(output / "bioelectric.mp4")]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for index in indices:
            for row, result in enumerate(results):
                cursor_lines[row].set_xdata([times[index], times[index]])
                scatters[row].set_array(np.asarray(result["voltage_mV"][index]))
            caption.set_text(f"t = {times[index]:.2f} ms  |  color is computed voltage; cell 0 receives +12 µA/cm² from 5 to 6 ms")
            fig.canvas.draw()
            process.stdin.write(fig.canvas.buffer_rgba())
        process.stdin.close()
        exit_status = process.wait()
        if exit_status:
            raise RuntimeError(f"ffmpeg exited {exit_status}")
        # Saved state at largest baseline excursion, not a generated specimen plate.
        peak_index = int(np.argmax(np.max(results[0]["voltage_mV"], axis=1)))
        for row, result in enumerate(results):
            cursor_lines[row].set_xdata([times[peak_index], times[peak_index]])
            scatters[row].set_array(np.asarray(result["voltage_mV"][peak_index]))
        caption.set_text(f"Snapshot t = {times[peak_index]:.2f} ms · comparisons use the same current pulse and initial voltage")
        fig.savefig(output / "poster.png", facecolor=fig.get_facecolor())
    finally:
        plt.close(fig)
        if process.poll() is None:
            process.stdin.close()
            process.wait()
    return {"kind": "render", "id": "bioelectric-state-render", "exit_status": 0,
            "input_artifacts": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            "code_sha256": code_hashes(), "source_frame_indices": indices.tolist(),
            "n_frames": len(indices), "fps": 24, "wall_playback_seconds": len(indices) / 24,
            "model_horizon_ms": float(times[-1]), "temporal_interpolation": "none; selected actual saved state frames",
            "command": command, "outputs": ["bioelectric.mp4", "poster.png"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/bioelectric"))
    args = parser.parse_args()
    result = render(args.output)
    (args.output / "render_receipt.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
