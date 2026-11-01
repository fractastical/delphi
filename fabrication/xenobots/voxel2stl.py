"""Voxel xenobot genome -> watertight STL for Formlabs (PreForm) printing.

A design is the direct encoding used by test-data/claim-tests/levin-papers/levin-2020-xenobots-06/voxsim.py:
a flat list of NX*NY*NZ cells in C order over a (NX, NY, NZ) workspace, each 0 (empty), 1 (passive)
or 3 (contractile). Only the largest face-connected component is meant to be present (the evolver
enforces that), so the solid is one piece.

Two mesh styles are produced:
  blocky  exact union of voxel cubes (manifold3d boolean), optionally shrunk by `gap` per voxel so
          the "cell" boundaries read on the print, and with a chamfer-free, true-to-genome shape;
  smooth  the occupancy sampled on a fine grid, Gaussian-blurred and isosurfaced (marching cubes),
          which gives the rounded, organic silhouette the living xenobots have and removes the
          edge-only contacts between diagonal voxels that are hard to print.

Frame: millimetres, Z up (the simulator's ground is z = 0), design min corner at the origin.
Units are a choice: the simulator is dimensionless (voxel edge = 1). `pitch` mm per voxel is a
print-scale decision, not a biological one. The real organisms are ~0.5-1 mm across in total.
"""
from __future__ import annotations

import numpy as np
import trimesh
from scipy import ndimage
from skimage import measure

EMPTY, PASSIVE, CONTRACTILE = 0, 1, 3


def to_grid(mat, shape=(5, 5, 4)):
    m = np.asarray(mat, dtype=int)
    if m.ndim == 1:
        m = m.reshape(shape)
    return m


def largest_component(cells: np.ndarray) -> np.ndarray:
    lab, n = ndimage.label(cells, structure=ndimage.generate_binary_structure(3, 1))
    if n <= 1:
        return cells.astype(bool)
    sizes = ndimage.sum(cells, lab, range(1, n + 1))
    return lab == (1 + int(np.argmax(sizes)))


def _boxes(cells: np.ndarray, pitch: float, gap: float) -> trimesh.Trimesh:
    """Union of one cube per present cell. gap shrinks each cube by gap/2 on every side; the
    faces of neighbouring cubes then no longer touch, so the result is only one solid when gap=0.
    """
    parts = []
    size = pitch - gap
    for x, y, z in zip(*np.nonzero(cells)):
        b = trimesh.creation.box(extents=(size, size, size))
        b.apply_translation(((x + 0.5) * pitch, (y + 0.5) * pitch, (z + 0.5) * pitch))
        parts.append(b)
    if not parts:
        raise ValueError("empty design")
    if len(parts) == 1:
        return parts[0]
    return trimesh.boolean.union(parts, engine="manifold")


def blocky_mesh(grid: np.ndarray, pitch: float = 4.0, gap: float = 0.0,
                material: int | None = None) -> trimesh.Trimesh:
    """Whole body (material=None) or only the cells of one material (1 or 3)."""
    cells = grid > 0 if material is None else grid == material
    return _boxes(cells, pitch, gap)  # manifold output is already watertight; do not re-merge


def smooth_mesh(grid: np.ndarray, pitch: float = 4.0, sub: int = 8, sigma_vox: float = 0.35,
                iso: float = 0.4, material: int | None = None) -> trimesh.Trimesh:
    """Isosurface of the blurred occupancy. sigma is in voxel units. The defaults (0.35, 0.4) keep
    every voxel as a visible lobe, fuse face-neighbours into a continuous skin and preserve ~97%
    of the voxel volume on champion 1 (0.45/0.5 would lose half of it). The volume is padded by
    one voxel so the surface closes.
    """
    cells = (grid > 0 if material is None else grid == material).astype(float)
    fine = np.repeat(np.repeat(np.repeat(cells, sub, 0), sub, 1), sub, 2)
    fine = np.pad(fine, sub, constant_values=0.0)
    field = ndimage.gaussian_filter(fine, sigma=sigma_vox * sub, mode="constant")
    verts, faces, _, _ = measure.marching_cubes(field, level=iso, spacing=(pitch / sub,) * 3)
    verts = verts - pitch  # undo the one-voxel pad so the frame matches blocky_mesh
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
    mesh.fix_normals()
    # keep the largest shell only; blur can pinch off a sliver at a diagonal-only contact
    shells = mesh.split(only_watertight=False)
    if len(shells) > 1:
        mesh = max(shells, key=lambda s: s.volume)
    return mesh


def check(mesh: trimesh.Trimesh) -> dict:
    ext = mesh.bounding_box.extents
    return {
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "volume_mm3": round(float(mesh.volume), 3),
        "bbox_mm": [round(float(v), 3) for v in ext],
        "faces": int(len(mesh.faces)),
        "bodies": int(mesh.body_count),
    }


def preview(grid: np.ndarray, path: str, title: str = "", pitch: float = 4.0) -> None:
    """Three orthographic views with contractile cells in red and passive cells in grey-blue."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(10, 3.4))
    views = [("top (x,y)", (0, 1), 2), ("side (x,z)", (0, 2), 1), ("front (y,z)", (1, 2), 0)]
    for i, (name, (a, b), depth) in enumerate(views):
        ax = fig.add_subplot(1, 3, i + 1)
        # draw back to front so the nearest cell wins
        order = np.argsort(-np.array([c[depth] for c in zip(*np.nonzero(grid))]))
        cells = list(zip(*np.nonzero(grid)))
        for k in order:
            c = cells[k]
            col = "#c0392b" if grid[c] == CONTRACTILE else "#8fa3b8"
            ax.add_patch(plt.Rectangle((c[a] * pitch, c[b] * pitch), pitch, pitch,
                                       facecolor=col, edgecolor="k", linewidth=0.6))
        ax.set_xlim(-pitch, (grid.shape[a] + 1) * pitch)
        ax.set_ylim(-pitch, (grid.shape[b] + 1) * pitch)
        ax.set_aspect("equal")
        ax.set_title(name, fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    import argparse, json, os
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("design", help="JSON file with a 'mat' field (flat list) or a flat JSON list")
    ap.add_argument("--out", required=True, help="output path prefix, e.g. out/mybot")
    ap.add_argument("--pitch", type=float, default=4.0, help="mm per voxel (default 4)")
    ap.add_argument("--shape", default="5,5,4")
    a = ap.parse_args()
    raw = json.load(open(a.design))
    mat = raw["mat"] if isinstance(raw, dict) else raw
    grid = to_grid(mat, tuple(int(v) for v in a.shape.split(",")))
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    rep = {}
    for name, fn in (("blocky", blocky_mesh), ("smooth", smooth_mesh)):
        m = fn(grid, pitch=a.pitch)
        m.export(f"{a.out}_{name}.stl")
        rep[name] = check(m)
    preview(grid, f"{a.out}_preview.png", os.path.basename(a.out), a.pitch)
    print(json.dumps(rep, indent=1))
