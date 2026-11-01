"""Render actual saved joint states; body chain is a normalized kinematic glyph."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def midline(angles):
    orientation = np.cumsum(angles)
    points = np.vstack(([0., 0.], np.cumsum(np.column_stack((np.cos(orientation), np.sin(orientation))) / len(angles), axis=0)))
    return points[:, 0], points[:, 1]


def render(folder: Path):
    names = ["baseline", "coupling_removed", "feedback_removed"]
    results = [json.loads((folder / (name + ".json")).read_text()) for name in names]
    times = np.array(results[0]["time_s"])
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor="#091820")
    grid = fig.add_gridspec(2, 2, left=.07, right=.96, top=.81, bottom=.14, hspace=.42, wspace=.25)
    body, wave, tracking, comparison = [fig.add_subplot(grid[index]) for index in [(0, 0), (0, 1), (1, 0), (1, 1)]]
    fig.text(.07, .95, "A rhythm controller with an explicit mechanical feedback loop", fontsize=19, weight="bold")
    fig.text(.07, .90, "SIMULATED · source-form CPG + designed joint servo · no brain/genotype/swimming-force claim", fontsize=11, color="#64e0d5")
    fig.text(.07, .05, "Normalized hinge-chain glyph, no translation/hydrodynamics. Zebrafish context DOI10.7554/eLife.67453; oscillator DOI10.1126/science.1138353.", fontsize=8)
    fig.text(.07, .02, "Phase kick0.8s; imposed torque1.1–1.3s. Current wind tunnel is static; no dynamic force coupling established.", fontsize=9, color="#b7c5cd")
    body.set_xlim(-.05, 1.05)
    body.set_ylim(-.28, .28)
    body.set_aspect("equal")
    body.set_title("Baseline: actual chain and commanded angle chain", fontsize=10)
    body.set_xlabel("normalized chain length (not measured fish length)", fontsize=8)
    body.set_ylabel("normalized lateral position", fontsize=8)
    actual_line, = body.plot([], [], "o-", color="#64e0d5", lw=3, ms=4, label="actual joint proxy")
    reference_line, = body.plot([], [], "--", color="#efb26f", lw=1.3, label="CPG setpoint")
    body.legend(fontsize=7, loc="upper right")
    volt = np.array(results[0]["actual_angle_rad"])
    wave.imshow(volt.T, origin="lower", extent=[times[0], times[-1], -.5, 7.5], aspect="auto", cmap="coolwarm", vmin=-.12, vmax=.12)
    wave.set_title("Actual local joint angle (rad); coarse segments, not somites", fontsize=9)
    wave.set_xlabel("model time [s]", fontsize=9)
    wave.set_ylabel("segment index", fontsize=9)
    wave_cursor = wave.axvline(0, color="white", lw=1)
    tracking.plot(times, np.array(results[0]["reference_angle_rad"])[:, -1], "--", color="#efb26f", lw=1, label="setpoint")
    tracking.plot(times, volt[:, -1], color="#64e0d5", lw=1, label="actual")
    tracking.set_xlim(.65, 1.45)
    tracking.set_ylim(-.15, .15)
    tracking.set_title("Caudal proxy segment: angle tracking", fontsize=10)
    tracking.set_xlabel("model time [s]", fontsize=9)
    tracking.set_ylabel("angle [rad]", fontsize=9)
    tracking.legend(fontsize=7, loc="upper right")
    trace_cursor = tracking.axvline(0, color="white", lw=1)
    colors = ["#64e0d5", "#c99be8", "#ee8f66"]
    for result, name, color in zip(results, names, colors):
        errors = np.sqrt(np.mean((np.array(result["actual_angle_rad"]) - result["reference_angle_rad"])**2, axis=1))
        comparison.semilogy(times, np.maximum(errors, 1e-8), color=color, label=name.replace("_", " "))
    comparison.set_ylim(1e-8, 4)
    comparison.set_xlim(0, 2)
    comparison.set_title("Angle error; no-feedback case exceeds declared angle envelope", fontsize=9)
    comparison.set_xlabel("model time [s]", fontsize=9)
    comparison.set_ylabel("RMS across joints [rad]", fontsize=9)
    comparison.legend(fontsize=7, loc="lower right")
    clock = fig.text(.07, .845, "", fontsize=11)
    available = np.flatnonzero((times >= .65) & (times <= 1.45))
    indices = available[np.round(np.linspace(0, len(available) - 1, 240)).astype(int)]
    command = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "1280x720", "-r", "30", "-i", "-", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-threads", "1", "-crf", "24", "-preset", "fast", "-movflags", "+faststart", str(folder / "behavior.mp4")]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for index in indices:
            actual_line.set_data(*midline(volt[index]))
            reference_line.set_data(*midline(np.array(results[0]["reference_angle_rad"][index])))
            wave_cursor.set_xdata([times[index], times[index]])
            trace_cursor.set_xdata([times[index], times[index]])
            clock.set_text(f"t={times[index]:.3f}s · 35Hz nominal drive · output frames are actual computed states, slowed for inspection")
            fig.canvas.draw()
            process.stdin.write(fig.canvas.buffer_rgba())
        process.stdin.close()
        if process.wait():
            raise RuntimeError("ffmpeg failed")
        fig.savefig(folder / "poster.png", facecolor=fig.get_facecolor())
    finally:
        plt.close(fig)
        if process.poll() is None:
            process.stdin.close()
            process.wait()
    return {"kind": "render", "frames": len(indices), "fps": 30, "duration_s": len(indices) / 30,
            "actual_state_frame_indices": indices.tolist(), "time_interpolation": "none", "model_window_s": [.65, 1.45],
            "input_hashes": {name + ".json": sha256((folder / (name + ".json")).read_bytes()).hexdigest() for name in names},
            "render_code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(), "outputs": ["behavior.mp4", "poster.png"],
            "command": command, "scope": "Actual saved joint states rendered as a normalized kinematic glyph, not empirical fish motion"}
