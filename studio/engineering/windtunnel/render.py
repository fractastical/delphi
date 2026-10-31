"""Velocity, pressure and force views from actual saved lattice states."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .geometry import file_sha  # noqa: E402


def render(directory, case="baseline"):
    directory = Path(directory)
    result = json.loads((directory / case / "result.json").read_text())
    summary = (
        json.loads((directory / "summary.json").read_text())
        if (directory / "summary.json").exists()
        else {"label": "REFINEMENT PENDING"}
    )
    if not result["checks"]["stable"] or not result["checks"]["positive_drag"]:
        raise ValueError("no video from a failing configuration")
    data = np.load(directory / case / "fields.npz")
    p = result["request_echo"]
    x, y = data["x_over_L"], data["y_over_L"]
    speed = np.sqrt(data["ux"] ** 2 + data["uy"] ** 2) / p["lattice_speed"]
    pressure = (data["rho"] - 1) / (1.5 * p["lattice_speed"] ** 2)
    solid = data["solid"]
    speed[:, solid] = np.nan
    pressure[:, solid] = np.nan
    scale = float(np.nanpercentile(abs(pressure), 99))
    scale = max(scale, 0.1)
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    grid = fig.add_gridspec(2, 2, height_ratios=(1.15, 1))
    velocity_ax = fig.add_subplot(grid[0, :])
    pressure_ax = fig.add_subplot(grid[1, 0])
    force_ax = fig.add_subplot(grid[1, 1])
    extent = (x[0], x[-1], y[0], y[-1])
    speed_image = velocity_ax.imshow(
        speed[0].T,
        origin="lower",
        extent=extent,
        vmin=0,
        vmax=float(np.nanpercentile(speed, 99.5)),
        cmap="viridis",
        interpolation="nearest",
        aspect="auto",
    )
    pressure_image = pressure_ax.imshow(
        pressure[0].T,
        origin="lower",
        extent=extent,
        vmin=-scale,
        vmax=scale,
        cmap="coolwarm",
        interpolation="nearest",
        aspect="auto",
    )
    for ax in (velocity_ax, pressure_ax):
        ax.contour(x, y, solid.T, levels=[0.5], colors="black", linewidths=0.8)
        ax.set(xlabel="x / reference body length", ylabel="z / reference body length")
        ax.set_xlim(2.0, 7.0)
        ax.set_ylim(1.9, 4.1)
    velocity_ax.set_title(
        "Actual velocity magnitude |u| / U · black outline = mesh-derived no-slip mask"
    )
    pressure_ax.set_title("Actual pressure coefficient Cp (color saturates at p99)")
    fig.colorbar(speed_image, ax=velocity_ax, label="|u|/U", fraction=0.025, pad=0.02)
    fig.colorbar(pressure_image, ax=pressure_ax, label="Cp", fraction=0.035, pad=0.025)
    skip = (slice(None, None, 6), slice(None, None, 6))
    xx, yy = np.meshgrid(x, y, indexing="ij")
    quiver = velocity_ax.quiver(
        xx[skip],
        yy[skip],
        data["ux"][0][skip] / p["lattice_speed"],
        data["uy"][0][skip] / p["lattice_speed"],
        color="white",
        alpha=0.6,
        scale=50,
        width=0.0017,
    )
    history = result["force_history"]
    times = [r["convective_time"] for r in history]
    force_ax.plot(
        times, [r["Cd"] for r in history], label="drag coefficient Cd", color="#147d86"
    )
    force_ax.plot(
        times, [r["Cl"] for r in history], label="lift coefficient Cl", color="#d35932"
    )
    cursor = force_ax.axvline(0, color="black", lw=0.8)
    force_ax.set(
        xlabel="convective time tU/L",
        ylabel="2D force coefficient",
        title="Integrated wall momentum exchange · transient",
    )
    force_ax.legend(fontsize=9)
    status_label = summary["label"]
    if status_label == "FAIL" and any(
        "runtime budget" in (c.get("failure") or "")
        for c in summary.get("cases", {}).values()
    ):
        status_label = "FAIL — CPU grid refinement incomplete"
    fig.suptitle(
        f"SIMULATED 2D low-Re wind tunnel · {status_label}\n{p['mesh_id']} · Re={result['Re']:.0f} · AoA={p['aoa_deg']:g}° · U={p['speed_m_s']:g} m/s",
        fontsize=14,
    )
    clock = fig.text(0.5, 0.07, "", ha="center", fontsize=10)
    fig.text(
        0.5,
        0.025,
        "Print-modified STL silhouette, infinite spanwise extrusion. Not 3D fish aerodynamics, flight Reynolds numbers or calibrated lift/drag.",
        ha="center",
        fontsize=9,
    )
    fig.subplots_adjust(
        left=0.065, right=0.94, bottom=0.17, top=0.84, hspace=0.48, wspace=0.38
    )
    indices = np.rint(np.linspace(0, len(data["t_s"]) - 1, 180)).astype(int)
    command = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        "1280x720",
        "-r",
        "15",
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-threads",
        "2",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(directory / "windtunnel.mp4"),
    ]
    with subprocess.Popen(command, stdin=subprocess.PIPE) as proc:
        for index in indices:
            speed_image.set_data(speed[index].T)
            pressure_image.set_data(pressure[index].T)
            quiver.set_UVC(
                data["ux"][index][skip] / p["lattice_speed"],
                data["uy"][index][skip] / p["lattice_speed"],
            )
            t = float(data["convective_time"][index])
            cursor.set_xdata([t, t])
            previous = [r for r in history if r["convective_time"] <= t + 1e-12]
            force_text = "force not yet sampled"
            if previous:
                latest = previous[-1]
                force_text = f"latest force at tU/L={latest['convective_time']:.2f}: drag={latest['drag_N_per_m_span']:.3g}, lift={latest['lift_N_per_m_span']:.3g} N/m span"
            clock.set_text(
                f"tU/L={t:.2f} · proxy t={data['t_s'][index]:.2f} s · {force_text}"
            )
            fig.canvas.draw()
            proc.stdin.write(
                np.ascontiguousarray(
                    np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
                ).tobytes()
            )
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg failed")
    fig.savefig(directory / "poster.png")
    plt.close(fig)
    manifest = {
        "schema": "frontier.windtunnel.render-manifest/1",
        "evidence_kind": "render_of_simulation",
        "case": case,
        "label": summary["label"],
        "mesh": result["geometry"],
        "inputs": {
            "fields.npz": file_sha(directory / case / "fields.npz"),
            "result.json": file_sha(directory / case / "result.json"),
        },
        "render_code_sha256": file_sha(__file__),
        "matplotlib": matplotlib.__version__,
        "n_frames": 180,
        "fps": 15,
        "source_frame_indices": indices.tolist(),
        "source_frames": "actual saved node values, no temporal/spatial interpolation; repeated indices extend playback",
        "pressure_color_limit_abs_Cp": scale,
        "not_established": result["not_established"],
        "outputs": {
            name: {
                "sha256": file_sha(directory / name),
                "byte_size": (directory / name).stat().st_size,
            }
            for name in ("windtunnel.mp4", "poster.png")
        },
    }
    (directory / "render-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("directory", nargs="?", default="artifacts/windtunnel")
    parser.add_argument("--case", default="baseline")
    args = parser.parse_args()
    render(args.directory, args.case)
