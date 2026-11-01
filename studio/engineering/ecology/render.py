"""Render saved states with original v3a body mesh and articulated fin panels."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
from matplotlib.collections import PolyCollection
import numpy as np
import trimesh

from .model import ART, FINS, FLIP, GEOM, dump


def quat_matrix(q):
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def parts(cg):
    arrays = []
    body = trimesh.load(GEOM / "components/body.stl", process=True)
    # Rendering-only vertex clustering; original source and physics are unchanged.
    # Biological component STLs are already in metres. Print STLs are separate.
    vertices = np.asarray(body.vertices)
    cells = np.round(vertices / 0.0008).astype(int)
    _, inverse = np.unique(cells, axis=0, return_inverse=True)
    counts = np.bincount(inverse)
    clustered = np.stack(
        [np.bincount(inverse, weights=vertices[:, k]) / counts for k in range(3)],
        axis=1,
    )
    faces = inverse[np.asarray(body.faces)]
    keep = (
        (faces[:, 0] != faces[:, 1])
        & (faces[:, 1] != faces[:, 2])
        & (faces[:, 0] != faces[:, 2])
    )
    triangles = clustered[faces[keep]]
    triangles = (triangles - np.array([cg, 0, 0])) @ FLIP
    arrays.append(("body", triangles, None))
    panels = json.loads((GEOM / "panels.json").read_text())["fins"]
    for name, fin in panels.items():
        quads = (np.asarray(fin["quads_m"]) - np.array([cg, 0, 0])) @ FLIP
        root = FLIP @ (np.array(fin["fin_plane"]["origin_m"]) - np.array([cg, 0, 0]))
        arrays.append((name, quads, root))
    return arrays


def draw_mesh(ax, frame, parts_data, school=False):
    positions = np.asarray([x["position_m"] for x in frame["fish"]])
    center = positions.mean(axis=0)
    horizontal = np.array([1.0, 0, 0])
    vertical = np.array([0, 0.65, 0.76])
    vertical /= np.linalg.norm(vertical)
    depth = np.cross(horizontal, vertical)
    allpolys = []
    colors = []
    zorder = []
    for fish in frame["fish"]:
        rotation = quat_matrix(fish["orientation_wxyz"])
        pos = np.asarray(fish["position_m"])
        for name, polys, root in parts_data:
            vertices = polys.copy()
            if name in FINS:
                angle = fish["fin_angle_rad"][name]
                c, s = np.cos(angle), np.sin(angle)
                hinge = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
                vertices = (vertices - root) @ hinge.T + root
            vertices = vertices @ rotation.T + pos - center
            projected = np.stack([vertices @ horizontal, vertices @ vertical], axis=-1)
            color = matplotlib.colors.to_rgba(
                "#4bbed2" if name == "body" else "#9cdedb"
            )
            color = np.array(color)
            color[3] = 1 if name == "body" else 0.88
            if fish["escape_triggered"] and name == "body":
                color = np.array(matplotlib.colors.to_rgba("#f3b64e"))
            allpolys.extend(projected)
            colors.extend([color] * len(projected))
            zorder.extend((vertices @ depth).mean(axis=1))
        if fish["fluid_force_world_N"] is not None:
            force = np.asarray(fish["fluid_force_world_N"]) * 0.15
            start = pos - center
            ax.arrow(
                start @ horizontal,
                start @ vertical,
                force @ horizontal,
                force @ vertical,
                color="#eb5e55",
                width=0.001 if school else 0.0004,
                head_width=0.008 if school else 0.003,
                length_includes_head=True,
            )
    order = np.argsort(zorder)
    collection = PolyCollection(
        [allpolys[i] for i in order],
        facecolors=np.asarray(colors)[order],
        edgecolors="none",
    )
    ax.add_collection(collection)
    ax.set_aspect("equal")
    if school:
        ax.set_xlim(-0.8, 0.8)
        ax.set_ylim(-0.42, 0.42)
    else:
        ax.set_xlim(-0.15, 0.15)
        ax.set_ylim(-0.085, 0.085)
    ax.set_facecolor("#071c2d")
    ax.tick_params(colors="#cbd5df", labelsize=8)
    ax.set_xlabel(
        "World X offset from tracking camera (m)", color="#cbd5df", fontsize=8
    )
    ax.set_ylabel("Oblique world Y/Z projection (m)", color="#cbd5df", fontsize=8)


def render(run, out, school=False):
    names = (
        ["escape-neighbors", "escape-no-neighbors"]
        if school
        else ["glide-passive", "glide-feedback"]
    )
    trajectories = [
        json.loads((run / name / "trajectory.json").read_text()) for name in names
    ]
    parts_data = parts(trajectories[0]["geometry"]["cg_from_nose_m"])
    maxtime = max(x["frames"][-1]["time_s"] for x in trajectories)
    # Each video sample selects one actual saved state; no state interpolation.
    times = sorted(
        {
            round(x["time_s"], 8)
            for trajectory in trajectories
            for x in trajectory["frames"]
        }
    )
    fig = plt.figure(figsize=(12.8, 7.2), facecolor="#071321")
    grid = fig.add_gridspec(2, 2, height_ratios=[2, 1], hspace=0.34, wspace=0.22)
    axs = [fig.add_subplot(grid[0, k]) for k in range(2)]
    plots = [fig.add_subplot(grid[1, k]) for k in range(2)]
    writer = FFMpegWriter(
        fps=15, codec="libx264", extra_args=["-pix_fmt", "yuv420p", "-threads", "2"]
    )
    out.mkdir(parents=True, exist_ok=True)
    video = out / ("school.mp4" if school else "glide.mp4")
    poster = video.with_suffix(".png")
    with writer.saving(fig, str(video), 100):
        for index, t in enumerate(times):
            for k, (ax, plot, trajectory, name) in enumerate(
                zip(axs, plots, trajectories, names, strict=True)
            ):
                ax.clear()
                plot.clear()
                actual = [f for f in trajectory["frames"] if f["time_s"] <= t + 1e-7][
                    -1
                ]
                draw_mesh(ax, actual, parts_data, school)
                ended = t > trajectory["frames"][-1]["time_s"] + 1e-7
                ax.set_title(
                    name
                    + " | saved t="
                    + f"{actual['time_s']:.3f}s"
                    + (" | STOPPED" if ended else ""),
                    color="white",
                    fontsize=11,
                )
                history = [
                    f
                    for f in trajectory["frames"]
                    if f["time_s"] <= actual["time_s"] + 1e-8
                ]
                tt = [f["time_s"] for f in history]
                if school:
                    for fishid in range(len(history[0]["fish"])):
                        plot.step(
                            tt,
                            [
                                float(f["fish"][fishid]["escape_triggered"]) + fishid
                                for f in history
                            ],
                            where="post",
                            lw=1.2,
                        )
                    plot.set_ylabel(
                        "Fish ID + response flag", color="white", fontsize=9
                    )
                    plot.set_ylim(-0.1, 8.2)
                else:
                    plot.plot(
                        tt,
                        [f["fish"][0]["position_m"][2] for f in history],
                        color="#7fe3d8",
                        label="height m",
                    )
                    plot.set_ylim(0, 4.2)
                    plot.set_ylabel("Height (m)", color="white", fontsize=9)
                    work = history[-1]["fish"][0]["positive_actuator_work_J"]
                    plot.text(
                        0.03,
                        0.09,
                        f"Positive actuator work: {work:.5f} J",
                        transform=plot.transAxes,
                        color="#f3b64e",
                        fontsize=9,
                    )
                plot.set_xlim(0, max(maxtime, 0.1))
                plot.set_xlabel("Actual simulation time (s)", color="white", fontsize=9)
                plot.set_facecolor("#102336")
                plot.tick_params(colors="white", labelsize=8)
                plot.grid(alpha=0.15)
                reason = trajectory["summary"]["termination_reason"]
                ax.text(
                    0.01,
                    0.02,
                    reason,
                    transform=ax.transAxes,
                    color="#f3b64e",
                    fontsize=8,
                )
            fig.suptitle(
                "Actual v3a geometry • "
                + (
                    "Local airborne escape proxy"
                    if school
                    else "Passive vs bounded fin feedback"
                ),
                color="white",
                fontsize=16,
                y=0.98,
            )
            fig.text(
                0.5,
                0.018,
                "MuJoCo rigid bodies + reduced VLM-derived forces | assumed mass/control | not CFD or biological validation | camera tracks actual states",
                ha="center",
                color="#a5b7cb",
                fontsize=8,
            )
            writer.grab_frame()
            if index == len(times) - 1:
                fig.savefig(poster, dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)
    dump(
        video.with_suffix(".provenance.json"),
        {
            "schema": "frontier.ecology.render-receipt/1",
            "code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_trajectories": [
                {
                    "path": str(run / name / "trajectory.json"),
                    "sha256": sha256(
                        (run / name / "trajectory.json").read_bytes()
                    ).hexdigest(),
                }
                for name in names
            ],
            "geometry": "Original v3a body STL vertex-clustered at0.8mm for rendering only; exact original fin panels articulated at saved angles; no physics mesh replacement",
            "frame_method": "Actual saved-state selection without interpolation; stopped panels explicitly hold final observed state for comparison display, not new physics evidence",
            "video_frames": len(times),
            "video_sha256": sha256(video.read_bytes()).hexdigest(),
            "poster_sha256": sha256(poster.read_bytes()).hexdigest(),
            "force_arrow_scale_m_per_N": 0.15,
        },
    )
    print(video, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=ART / "run-v2")
    parser.add_argument("--out", type=Path, default=ART / "render-v2")
    parser.add_argument("--school", action="store_true")
    args = parser.parse_args()
    render(args.run, args.out, args.school)
