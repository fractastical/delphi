"""Rasterize actual STL triangle projection; no illustrative fish generator."""

from __future__ import annotations

import hashlib
import math
import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MESHES = {
    name: ROOT / f"artifacts/print/stl/{name}.stl"
    for name in ("N1-cypselurus-baseline", "N2-area-x1.3", "N3-area-x1.3-ar-x1.2")
}


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mask_from_mesh(mesh_id, length_cells, aoa_deg, thickness_scale):
    if mesh_id not in MESHES:
        raise ValueError("unsupported pinned mesh id")
    path = MESHES[mesh_id]
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + count * 50 or count > 200000:
        raise ValueError("expected bounded binary STL")
    dtype = np.dtype(
        [("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")]
    )
    triangles = np.frombuffer(data, dtype=dtype, offset=84)["vertices"].astype(
        np.float64
    )
    if not np.isfinite(triangles).all():
        raise ValueError("nonfinite mesh")
    low, high = triangles.min(axis=(0, 1)), triangles.max(axis=(0, 1))
    extent = high[0] - low[0]
    x = (triangles[:, :, 0] - (low[0] + high[0]) / 2) / extent
    z = triangles[:, :, 2] / extent * thickness_scale
    angle = math.radians(aoa_deg)
    # x goes snout -> tail. Clockwise pitch puts the snout up.
    projected = (
        np.stack(
            [
                math.cos(angle) * x + math.sin(angle) * z,
                -math.sin(angle) * x + math.cos(angle) * z,
            ],
            axis=-1,
        )
        * length_cells
    )
    projected += np.array([3.5 * length_cells, 3 * length_cells])
    nx, ny = 12 * length_cells, 6 * length_cells
    mask = np.zeros((nx, ny), dtype=bool)
    for triangle in projected:
        a, b, c = triangle
        edge1, edge2 = b - a, c - a
        area = edge1[0] * edge2[1] - edge1[1] * edge2[0]
        if abs(area) < 1e-12:
            continue
        lo = np.maximum(np.floor(triangle.min(axis=0) - 0.5).astype(int), 0)
        hi = np.minimum(
            np.ceil(triangle.max(axis=0) - 0.5).astype(int), [nx - 1, ny - 1]
        )
        if np.any(hi < lo):
            continue
        xx = np.arange(lo[0], hi[0] + 1)[:, None] + 0.5
        yy = np.arange(lo[1], hi[1] + 1)[None, :] + 0.5
        cross = [
            (v[0] - u[0]) * (yy - u[1]) - (v[1] - u[1]) * (xx - u[0])
            for u, v in ((a, b), (b, c), (c, a))
        ]
        inside = (
            (cross[0] >= -1e-10) & (cross[1] >= -1e-10) & (cross[2] >= -1e-10)
        ) | ((cross[0] <= 1e-10) & (cross[1] <= 1e-10) & (cross[2] <= 1e-10))
        mask[lo[0] : hi[0] + 1, lo[1] : hi[1] + 1] |= inside
    if mask.sum() < 8:
        raise ValueError("mesh projection is under-resolved")
    return mask, {
        "mesh_id": mesh_id,
        "path": str(path.relative_to(ROOT)),
        "sha256": file_sha(path),
        "mesh_triangles": count,
        "mesh_units": "print millimetres; normalized before declared physical rescaling",
        "source_bounds_mm": [low.tolist(), high.tolist()],
        "projection": "sagittal x-z triangle union, span ignored",
        "positive_aoa": "snout up",
        "solid_cells": int(mask.sum()),
        "mask_sha256": hashlib.sha256(mask.tobytes()).hexdigest(),
        "geometry_warning": "print-modified candidate silhouette, staircase binary mask, infinite 2D extrusion; not observed animal",
    }
