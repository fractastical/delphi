"""Geometry checks on a triangle mesh, computed here from the arrays (not trusted from the mesh library).

What is checked: finite vertices; no degenerate triangles; every undirected edge used by exactly two faces and
each directed edge exactly once (closed, consistently oriented 2-manifold); one face-connected component;
positive signed volume; Euler characteristic and genus; bounds; inward-ray wall thickness on sampled faces,
gated against a minimum wall when one is given.
What is NOT checked: global self-intersection, slicing, supports, cups, minima, resin-specific thin-wall
limits.  Those belong to PreForm (see docs/printing.md).
"""
from __future__ import annotations

import hashlib
import struct

import numpy as np


def mesh_hash(V: np.ndarray, T: np.ndarray) -> str:
    """Canonical content hash: vertices rounded to 1e-6 mm (float64 little-endian) then faces (int64)."""
    h = hashlib.sha256()
    h.update(np.round(V, 6).astype("<f8").tobytes())
    h.update(T.astype("<i8").tobytes())
    return h.hexdigest()


def weld_float32(V: np.ndarray, T: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    """Merge vertices that are identical once stored as float32 (STL's precision) and drop the faces that
    collapse.  Closedness and orientation are NOT assumed afterwards; `check` re-derives them."""
    V32 = V.astype(np.float32)
    U, inv = np.unique(V32, axis=0, return_inverse=True)
    T2 = inv.reshape(-1)[T]
    keep = (T2[:, 0] != T2[:, 1]) & (T2[:, 1] != T2[:, 2]) & (T2[:, 0] != T2[:, 2])
    T2 = T2[keep]
    used = np.unique(T2)
    remap = -np.ones(len(U), dtype=np.int64)
    remap[used] = np.arange(len(used))
    return U[used].astype(np.float64), remap[T2], {"merged_vertices": int(len(V) - len(U)),
                                                   "dropped_faces": int((~keep).sum())}


def stl_bytes(V: np.ndarray, T: np.ndarray, header: str) -> bytes:
    """Deterministic binary STL (fixed header, no timestamp), millimetres."""
    tri = V[T].astype(np.float64)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    out = bytearray(header.encode("ascii")[:80].ljust(80, b" "))
    out += struct.pack("<I", len(T))
    rec = np.zeros(len(T), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, tri
    out += rec.tobytes()
    return bytes(out)


def read_stl(data: bytes) -> tuple[np.ndarray, np.ndarray]:
    """Re-read a binary STL and weld identical vertices (a round-trip check of the written file)."""
    n = struct.unpack_from("<I", data, 80)[0]
    rec = np.frombuffer(data, dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")], count=n, offset=84)
    pts = rec["v"].reshape(-1, 3).astype(np.float64)
    V, inv = np.unique(pts, axis=0, return_inverse=True)
    return V, inv.reshape(-1, 3)


def _components(nf: int, pairs: np.ndarray) -> int:
    parent = np.arange(nf)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    return len({find(i) for i in range(nf)})


def thickness_samples(V: np.ndarray, T: np.ndarray, n: int = 3000, seed: int = 7) -> dict:
    """Distance from a face centroid, along the inward normal, to the next surface.  Uses manifold3d's own
    ray caster on the same mesh.  A sample, not a proof: thin regions between samples can be missed."""
    import manifold3d as mf
    m = mf.Manifold(mf.Mesh(vert_properties=V.astype(np.float32), tri_verts=T.astype(np.uint32)))
    tri = V[T]
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = 0.5 * np.linalg.norm(nrm, axis=1)
    nrm = nrm / np.maximum(2 * area[:, None], 1e-30)
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(T), size=min(n, int((area > 0).sum())), replace=False, p=area / area.sum())
    c = tri[idx].mean(axis=1)
    eps = 1e-3
    o = c - nrm[idx] * eps
    far = 500.0
    e = o - nrm[idx] * far
    d = np.full(len(idx), np.inf)
    for r in range(len(idx)):
        for hit in m.ray_cast(tuple(o[r]), tuple(e[r])):  # sorted; distance is a fraction of the segment
            dd = hit.distance * far
            if dd > 1e-6:
                d[r] = dd + eps
                break
    finite = d[np.isfinite(d)]
    return {"method": "inward ray from area-weighted random face centroids (manifold3d ray_cast)",
            "samples": int(len(idx)), "seed": seed, "no_hit": int((~np.isfinite(d)).sum()),
            "min_mm": float(finite.min()) if len(finite) else None,
            "p01_mm": float(np.percentile(finite, 1)) if len(finite) else None,
            "median_mm": float(np.median(finite)) if len(finite) else None,
            "fraction_below_1mm": float((finite < 1.0).mean()) if len(finite) else None}


def check(V: np.ndarray, T: np.ndarray, box_mm: float | None = None, thickness: bool = True,
          min_wall_mm: float | None = None) -> dict:
    r: dict = {}
    r["vertices"], r["triangles"] = int(len(V)), int(len(T))
    r["finite_vertices"] = bool(np.isfinite(V).all())
    tri = V[T]
    cr = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    areas = 0.5 * np.linalg.norm(cr, axis=1)
    repeated = (T[:, 0] == T[:, 1]) | (T[:, 1] == T[:, 2]) | (T[:, 0] == T[:, 2])
    r["min_triangle_area_mm2"] = float(areas.min())
    r["degenerate_triangles"] = int((repeated | (areas < 1e-10)).sum())
    d_edges = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    _, d_counts = np.unique(d_edges, axis=0, return_counts=True)
    u_edges = np.sort(d_edges, axis=1)
    uniq, inv, u_counts = np.unique(u_edges, axis=0, return_inverse=True, return_counts=True)
    r["edges"] = int(len(uniq))
    r["edges_not_shared_by_exactly_two_faces"] = int((u_counts != 2).sum())
    r["directed_edges_used_more_than_once"] = int((d_counts > 1).sum())
    r["closed_two_manifold"] = r["edges_not_shared_by_exactly_two_faces"] == 0
    r["consistently_oriented"] = r["directed_edges_used_more_than_once"] == 0
    face_of = np.tile(np.arange(len(T)), 3)
    order = np.argsort(inv, kind="stable")
    inv_s, face_s = inv[order], face_of[order]
    same = inv_s[1:] == inv_s[:-1]
    r["face_connected_components"] = _components(len(T), np.stack([face_s[:-1][same], face_s[1:][same]], 1))
    used = np.unique(T)
    r["unreferenced_vertices"] = int(len(V) - len(used))
    chi = len(V) - len(uniq) + len(T)
    r["euler_characteristic"] = int(chi)
    r["genus"] = int((2 - chi) // 2) if r["face_connected_components"] == 1 else None
    r["signed_volume_mm3"] = float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6)
    r["surface_area_mm2"] = float(areas.sum())
    lo, hi = V.min(axis=0), V.max(axis=0)
    r["bounds_mm"] = {"min": lo.round(4).tolist(), "max": hi.round(4).tolist(), "size": (hi - lo).round(4).tolist()}
    if box_mm is not None:
        r["fits_box_mm"] = box_mm
        r["fits_box"] = bool(((hi - lo) <= box_mm).all())
    r["mesh_sha256"] = mesh_hash(V, T)
    if thickness:
        r["wall_thickness"] = thickness_samples(V, T)
    if min_wall_mm is not None:
        w = r.get("wall_thickness") or {}
        r["min_wall_mm_required"] = min_wall_mm
        r["min_wall_ok"] = bool(w.get("min_mm") is not None and w["min_mm"] >= min_wall_mm and w["no_hit"] == 0)
        r["min_wall_scope"] = "sampled faces only; a thinner region between samples can be missed"
    r["self_intersection"] = "not checked"
    r["ok"] = bool(r["finite_vertices"] and r["degenerate_triangles"] == 0 and r["closed_two_manifold"]
                   and r["consistently_oriented"] and r["face_connected_components"] == 1
                   and r["signed_volume_mm3"] > 0 and r["unreferenced_vertices"] == 0
                   and (box_mm is None or r["fits_box"]) and r.get("min_wall_ok", True))
    return r
