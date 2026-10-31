"""Render actual atom coordinates and saved metrics; no invented molecular motion."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
from mpl_toolkits.mplot3d.art3d import Line3DCollection
import numpy as np
from openmm.app import PDBFile

RENDER_SOURCE = Path(__file__).read_bytes()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render(trajectory, metrics_path, atoms_path, prepared_pdb, output, seed=1731):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    data = np.load(trajectory)
    frames = data["positions_nm"]
    indices = data["atom_indices"]
    times = data["times_ps"]
    metrics = json.loads(Path(metrics_path).read_text())
    receipt_path = Path(metrics_path).parent / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    run = next(item for item in receipt["runs"] if item["seed"] == seed)
    atoms = json.loads(Path(atoms_path).read_text())
    lookup = {int(index): i for i, index in enumerate(indices)}
    assert len(frames) == len(metrics) == len(times) and np.isfinite(frames).all()
    if not np.allclose(
        times, [item["time_ps"] for item in metrics], rtol=0, atol=1e-12
    ):
        raise ValueError("Trajectory and metric times differ")
    if not np.isclose(float(times[-1]), run["production_ps"]):
        raise ValueError("Trajectory and simulation receipt duration differ")
    pdb = PDBFile(str(prepared_pdb))
    bonds = [
        (lookup[a.index], lookup[b.index])
        for a, b in pdb.topology.bonds()
        if a.index in lookup and b.index in lookup
    ]
    reference = frames[0].astype(float)
    center = reference.mean(0)
    _, _, principal = np.linalg.svd(reference - center, full_matrices=False)
    reference = (reference - center) @ principal.T
    # Each frame receives only a proper rigid alignment to its initial frame.
    aligned = []
    raw_reference = frames[0] - frames[0].mean(0)
    for frame in frames:
        x = frame - frame.mean(0)
        left, _, right = np.linalg.svd(x.T @ raw_reference)
        rotation = left @ np.diag([1, 1, np.linalg.det(left @ right)]) @ right
        aligned.append(x @ rotation @ principal.T)
    aligned = np.asarray(aligned)
    plt.rcParams.update(
        {"font.size": 11, "axes.titlesize": 13, "figure.facecolor": "#f6f7fa"}
    )
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    grid = fig.add_gridspec(2, 2, width_ratios=[2.0, 1], hspace=0.40, wspace=0.27)
    ax = fig.add_subplot(grid[:, 0], projection="3d")
    rms = fig.add_subplot(grid[0, 1])
    end = fig.add_subplot(grid[1, 1])
    colors = {"C": "#6d7680", "N": "#2478b7", "O": "#d34a45", "S": "#bd9c20"}
    atom_colors = [colors.get(atoms[int(i)]["element"], "#777777") for i in indices]
    points = ax.scatter(*aligned[0].T, s=13, c=atom_colors, depthshade=False)
    lines = Line3DCollection(
        [aligned[0][list(pair)] for pair in bonds],
        colors="#929ca5",
        linewidths=0.7,
        alpha=0.7,
    )
    ax.add_collection3d(lines)
    ca_chains = []
    for chain, color in zip(("A", "B", "C"), ("#1b82b1", "#e17e28", "#748b35")):
        ids = [
            lookup[a["index"]]
            for a in atoms
            if a["chain"] == chain and a["name"] == "CA"
        ]
        (line,) = ax.plot(
            *aligned[0][ids].T, color=color, lw=2.1, label="Chain " + chain
        )
        ca_chains.append((line, ids))
    bounds = np.ptp(aligned.reshape(-1, 3), axis=0)
    middle = aligned.reshape(-1, 3).mean(0)
    for dim, setter in enumerate((ax.set_xlim, ax.set_ylim, ax.set_zlim)):
        radius = max(bounds[dim] * 0.58, 0.9)
        setter(middle[dim] - radius, middle[dim] + radius)
    ax.set_box_aspect((max(bounds[0], 1), max(bounds[1], 1.8), max(bounds[2], 1.8)))
    ax.set_yticks([-0.5, 0, 0.5])
    ax.set_zticks([-0.5, 0, 0.5])
    ax.view_init(elev=15, azim=-70)
    ax.set_xlabel("nm")
    ax.set_ylabel("nm")
    ax.set_zlabel("nm")
    ax.legend(loc="upper left", frameon=False)
    ax.set_title("Actual atomistic states · 1K6F collagen mimetic", pad=20)
    rms.plot(times, [m["CA_RMSD_nm"] for m in metrics], color="#286ca5")
    rms.set_ylabel("Cα RMSD (nm)")
    rms.set_xlabel("Production time (ps)")
    rms.set_title("Aligned to production start")
    for i, color in enumerate(("#1b82b1", "#e17e28", "#748b35")):
        end.plot(
            times,
            [m["chain_end_to_end_nm"][i] for m in metrics],
            color=color,
            label="ABC"[i],
        )
    end.set_ylabel("Terminal Cα distance (nm)")
    end.set_xlabel("Production time (ps)")
    end.set_title("Three chain lengths · no modulus inferred")
    cursor1 = rms.axvline(0, color="#999", ls="--")
    cursor2 = end.axvline(0, color="#999", ls="--")
    fig.suptitle(
        "Molecular dynamics: computed motion, not observed fish biology",
        fontsize=17,
        y=0.97,
    )
    subtitle = fig.text(0.05, 0.885, "", fontsize=11)
    fig.text(
        0.05,
        0.04,
        f"{run['backend']} short trajectory · ff14SB / explicit TIP3P · 300 K target · 1 fs timestep · seed {seed}",
        fontsize=11,
    )
    fig.text(
        0.05,
        0.015,
        "Rigid view alignment only. Short preliminary thermalization and production do not establish equilibrium or tissue mechanics.",
        fontsize=10,
        color="#555",
    )
    writer = FFMpegWriter(
        fps=12, codec="libx264", extra_args=["-pix_fmt", "yuv420p", "-threads", "1"]
    )
    with writer.saving(fig, str(out / "trajectory.mp4"), 100):
        for k, frame in enumerate(aligned):
            points._offsets3d = tuple(frame.T)
            lines.set_segments([frame[list(pair)] for pair in bonds])
            for line, ids in ca_chains:
                line.set_data_3d(*frame[ids].T)
            cursor1.set_xdata([times[k]] * 2)
            cursor2.set_xdata([times[k]] * 2)
            subtitle.set_text(
                f"Actual production time {times[k]:.3f} ps / {times[-1]:.3f} ps · frame {k + 1}/{len(frames)} · playback greatly slowed"
            )
            if k == len(frames) - 1:
                fig.savefig(out / "poster.png", dpi=100)
            writer.grab_frame()
    plt.close(fig)
    (out / "producer-render.py").write_bytes(RENDER_SOURCE)
    manifest = {
        "schema": "frontier.molecular.render/1",
        "kind": "rendered from actual simulation states",
        "trajectory_sha256": sha(trajectory),
        "metrics_sha256": sha(metrics_path),
        "atoms_sha256": sha(atoms_path),
        "topology_PDB_sha256": sha(prepared_pdb),
        "render_code_sha256": hashlib.sha256(RENDER_SOURCE).hexdigest(),
        "simulation_receipt_sha256": sha(receipt_path),
        "backend": run["backend"],
        "seed": seed,
        "preliminary_thermalization_ps": run["equilibration_ps"],
        "coordinate_storage_dtype": str(frames.dtype),
        "frames": len(frames),
        "simulation_duration_ps": float(times[-1]),
        "display_fps": 12,
        "coordinate_transform": "translation and proper rigid least-squares alignment to initial frame, then fixed principal-axis camera frame; no deformation invented",
        "outputs": {f.name: sha(f) for f in out.iterdir() if f.name != "render.json"},
    }
    (out / "render.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--trajectory",
        default="artifacts/molecular/cpu-trajectory-final/trajectory-1731.npz",
    )
    p.add_argument(
        "--metrics",
        default="artifacts/molecular/cpu-trajectory-final/metrics-1731.json",
    )
    p.add_argument("--atoms", default="artifacts/molecular/prepared/atoms.json")
    p.add_argument("--pdb", default="artifacts/molecular/prepared/prepared.pdb")
    p.add_argument("--output", default="artifacts/molecular/cpu-render")
    p.add_argument("--seed", type=int, default=1731)
    a = p.parse_args()
    render(a.trajectory, a.metrics, a.atoms, a.pdb, a.output, a.seed)
