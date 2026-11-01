"""Actual static-iteration geometry and separate saved glide paths; no interpolation."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
from engineering.ecology import render as ecology_render
from engineering.ecology.model import FLIP

from .model import ART, GEOM, dump, protocol


def render(root=ART / "control-slice", out=ART / "render-control", selections=None):
    out.mkdir(parents=True, exist_ok=True)
    names = ["rigid", "one-way-frozen-load", "two-way-static-feedback"]
    selections = selections or {name: name for name in names}
    case = root / selections["two-way-static-feedback"]
    record = json.loads((case / "result.json").read_text())
    states = np.load(case / "static-states.npz")
    arms = {
        name: json.loads((root / selections[name] / "result.json").read_text())
        for name in ["rigid", "one-way-frozen-load", "two-way-static-feedback"]
    }
    flights = {
        name: np.load(root / selections[name] / "glide-main.npz") for name in arms
    }
    source = json.loads((GEOM / "panels.json").read_text())["fins"]
    bodypath = GEOM / "components/body.stl"
    # Reuse coherent rendering-only clustering; reverse its display rotation.
    bodytri = ecology_render.parts(0)[0][1] @ FLIP
    bodyvertices = bodytri.reshape(-1, 3)
    allsource = np.vstack(
        [
            np.asarray(source[name]["quads_m"]).reshape(-1, 3)
            for name in protocol()["geometry"]["fins"]
        ]
    )
    lo = np.minimum(allsource.min(axis=0), bodyvertices.min(axis=0))
    hi = np.maximum(allsource.max(axis=0), bodyvertices.max(axis=0))
    center = (lo + hi) / 2
    extent = (hi - lo) * 1.15
    histories = record["iterations"]
    CL = [x["CL_on_fixed_source_area"] for x in histories]
    frames = []
    all_displacement = []
    for name in protocol()["geometry"]["fins"]:
        q = states[name + "__quads_m"]
        base = np.asarray(source[name]["quads_m"])
        all_displacement.append(
            np.linalg.norm(q - base[None], axis=-1).mean(axis=-1) * 1000
        )
    maximum = max(float(x.max()) for x in all_displacement)
    cmap = plt.get_cmap("viridis")
    norm = matplotlib.colors.Normalize(0, max(maximum, 1e-12))
    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        "1280x720",
        "-r",
        "4",
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-threads",
        "2",
        "-pix_fmt",
        "yuv420p",
        str(out / "coupled-states.mp4"),
    ]
    proc = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for movie_frame, index in enumerate(
            [*range(len(histories)), *[len(histories) - 1] * 8]
        ):
            fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor="#081c2c")
            grid = fig.add_gridspec(
                2,
                2,
                width_ratios=[1.3, 1],
                left=0.02,
                right=0.98,
                bottom=0.13,
                top=0.85,
                hspace=0.38,
                wspace=0.24,
            )
            ax = fig.add_subplot(grid[:, 0], projection="3d")
            ax.set_facecolor("#081c2c")
            ax.add_collection3d(
                Poly3DCollection(
                    bodytri, facecolor="#8499a9", edgecolor="none", alpha=0.85
                )
            )
            for f, name in enumerate(protocol()["geometry"]["fins"]):
                q = states[name + "__quads_m"][index]
                ax.add_collection3d(
                    Poly3DCollection(
                        q,
                        facecolor=cmap(norm(all_displacement[f][index])),
                        edgecolor="#50606b",
                        linewidth=0.3,
                    )
                )
            ax.set(
                xlim=(center[0] - extent[0] / 2, center[0] + extent[0] / 2),
                ylim=(center[1] - extent[1] / 2, center[1] + extent[1] / 2),
                zlim=(
                    center[2] - max(extent[2], 0.04) / 2,
                    center[2] + max(extent[2], 0.04) / 2,
                ),
            )
            ax.set_box_aspect((extent[0], extent[1], max(extent[2], 0.04)))
            ax.view_init(elev=28, azim=-62)
            ax.set_xlabel("source x (m)", color="white", labelpad=7)
            ax.set_ylabel("source y (m)", color="white", labelpad=7)
            ax.set_zlabel("z (m)", color="white", labelpad=7)
            ax.set_zticks([-0.01, 0.01])
            ax.tick_params(colors="white", labelsize=7)
            ax.set_title(
                "Actual deformed fin surfaces; displacement unscaled",
                color="white",
                fontsize=11,
            )
            colorbar = fig.colorbar(
                matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap),
                ax=ax,
                shrink=0.45,
                pad=0.10,
            )
            colorbar.set_label("Mean quad displacement (mm)", color="white")
            colorbar.ax.tick_params(colors="white", labelsize=8)
            chart = fig.add_subplot(grid[0, 1])
            chart.plot(
                range(index + 1), CL[: index + 1], "-o", markersize=3, color="#168aad"
            )
            chart.axhline(
                arms["rigid"]["iterations"][-1]["CL_on_fixed_source_area"],
                linestyle="--",
                color="#f4a261",
                label="rigid",
            )
            chart.axhline(
                arms["one-way-frozen-load"]["iterations"][-1][
                    "CL_on_fixed_source_area"
                ],
                linestyle=":",
                color="#519c6b",
                label="frozen load",
            )
            chart.set(
                xlim=(0, len(histories) - 1),
                xlabel="Static solver iteration (NOT physical time)",
                ylabel="CL on fixed source area",
            )
            chart.xaxis.label.set_color("white")
            chart.yaxis.label.set_color("white")
            chart.legend(fontsize=8)
            chart.tick_params(labelsize=8, colors="white")
            pathax = fig.add_subplot(grid[1, 1])
            for name, flight in flights.items():
                data = flight["state_x_h_V_gamma"]
                pathax.plot(data[:, 0], data[:, 1], label=name.replace("-", " "))
            pathax.set(
                xlabel="Horizontal position (m)",
                ylabel="Height (m)",
                title="Separate fixed-α assumed-release descent",
            )
            pathax.xaxis.label.set_color("white")
            pathax.yaxis.label.set_color("white")
            pathax.title.set_color("white")
            pathax.legend(fontsize=7)
            pathax.tick_params(labelsize=8, colors="white")
            fig.suptitle(
                f"Bending-only, torsion-rigid scaffold → deformation → recomputed force\nActual static iteration {index}"
                + (" • terminal hold" if movie_frame >= len(histories) else ""),
                color="white",
                fontsize=15,
            )
            fig.text(
                0.5,
                0.055,
                f"{record['mesh']} {record['actual_lattice']['span']}×{record['actual_lattice']['chord']} | assumed EI | fixed-α release | no tissue calibration or continuous FSI",
                ha="center",
                color="#b8c8d3",
                fontsize=10,
            )
            fig.canvas.draw()
            rgba = np.asarray(fig.canvas.buffer_rgba())
            proc.stdin.write(rgba[:, :, :3].tobytes())
            if movie_frame == len(histories) - 1:
                fig.savefig(out / "poster.png", facecolor=fig.get_facecolor())
            plt.close(fig)
            frames.append(
                {
                    "movie_frame": movie_frame,
                    "actual_static_iteration": index,
                    "terminal_hold": movie_frame >= len(histories),
                    "interpolated_state": False,
                }
            )
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    refs = [
        case / "result.json",
        case / "static-states.npz",
        bodypath,
        GEOM / "panels.json",
    ] + [root / selections[name] / "glide-main.npz" for name in arms]
    dump(
        out / "provenance.json",
        {
            "schema": "frontier.aeroelastic.render/1",
            "sources": [
                {"path": str(p), "sha256": sha256(p.read_bytes()).hexdigest()}
                for p in refs
            ],
            "code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "body_render_lod_m": 0.0015,
            "body_display_helper_sha256": sha256(
                Path(ecology_render.__file__).read_bytes()
            ).hexdigest(),
            "body_display_transform": "reverse ecology display FLIP to restore source axes",
            "body_units": "source STL already metres; no scale conversion",
            "frames": frames,
            "static_iteration_not_time": True,
            "glide_paths": "actual separately integrated post-step states; shape fixed and not continuously coupled",
            "outputs": [
                {
                    "path": str(out / name),
                    "sha256": sha256((out / name).read_bytes()).hexdigest(),
                    "bytes": (out / name).stat().st_size,
                }
                for name in ["poster.png", "coupled-states.mp4"]
            ],
        },
    )


if __name__ == "__main__":
    render()
