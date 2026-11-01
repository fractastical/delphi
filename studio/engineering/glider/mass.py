"""Mass properties of a closed, outward-wound triangle mesh, computed exactly with the divergence theorem.

Each triangle and the origin span a signed tetrahedron; summing the tetrahedra's volume, first moments and second
moments gives the solid's volume, centroid and inertia tensor (uniform density).  The formulas are the standard
closed forms for a tetrahedron with one vertex at the origin.  Controls (`controls()`) compare against solids whose answers are known in closed form.
"""
from __future__ import annotations

import numpy as np

_CANON = np.array([[2.0, 1.0, 1.0], [1.0, 2.0, 1.0], [1.0, 1.0, 2.0]]) / 120.0  # tetra covariance, unit det


def properties(V: np.ndarray, T: np.ndarray, density_kg_m3: float, length_unit_m: float = 1e-3) -> dict:
    """Volume, mass, centre of mass and inertia tensor about the centre of mass (body axes of the mesh frame).
    V in mesh units (mm by default); results in SI (m3, kg, m, kg m2) and also mm3/g/mm for reading."""
    tri = V[T].astype(np.float64) * length_unit_m             # (n, 3 vertices, 3 coords), metres
    det = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2]))  # 6 x signed tetra volume
    vol = det.sum() / 6.0
    if vol <= 0:
        raise ValueError(f"mesh is not outward-wound or not closed: signed volume {vol}")
    first = (det[:, None] * tri.sum(axis=1)).sum(axis=0) / 24.0
    cg = first / vol
    # second moment  C = sum det * A^T K A,  A rows = the three vertices, K = _CANON
    C = np.einsum("n,nai,ab,nbj->ij", det, tri, _CANON, tri)
    m = density_kg_m3 * vol
    Cc = density_kg_m3 * C - m * np.outer(cg, cg)              # covariance about the centre of mass
    I = np.trace(Cc) * np.eye(3) - Cc
    return {"volume_m3": float(vol), "volume_mm3": float(vol / length_unit_m ** 3),
            "mass_kg": float(m), "mass_g": float(m * 1e3), "density_kg_m3": float(density_kg_m3),
            "cg_m": [float(c) for c in cg], "cg_mm": [float(c * 1e3) for c in cg],
            "inertia_cg_kg_m2": [[float(x) for x in row] for row in I]}


def combine(parts: list[dict]) -> dict:
    """Assembled mass, CG and inertia about the assembled CG (parallel-axis theorem) from per-part records."""
    M = sum(p["mass_kg"] for p in parts)
    cg = sum(p["mass_kg"] * np.asarray(p["cg_m"]) for p in parts) / M
    I = np.zeros((3, 3))
    for p in parts:
        d = np.asarray(p["cg_m"]) - cg
        I += np.asarray(p["inertia_cg_kg_m2"]) + p["mass_kg"] * (d @ d * np.eye(3) - np.outer(d, d))
    return {"mass_kg": float(M), "mass_g": float(M * 1e3), "cg_m": [float(c) for c in cg],
            "cg_mm": [float(c * 1e3) for c in cg], "inertia_cg_kg_m2": [[float(x) for x in row] for row in I]}


def point_mass(mass_kg: float, at_m) -> dict:
    return {"mass_kg": float(mass_kg), "cg_m": [float(c) for c in at_m], "inertia_cg_kg_m2": np.zeros((3, 3)).tolist()}


def controls() -> list[dict]:
    """Analytic controls: an offset box, a polygonal prism standing in for a cylinder (exact for the polygon),
    and a hollow box (outer minus inner, i.e. a shell).  Each row reports the relative error of the worst
    quantity; the mesh solids come from manifold3d so the same mesh path as the parts is exercised."""
    import manifold3d as mf

    def arr(m):
        g = m.to_mesh64()
        return np.asarray(g.vert_properties)[:, :3], np.asarray(g.tri_verts).astype(np.int64)

    rho, rows = 1000.0, []
    a, b, c, off = 30.0, 20.0, 10.0, np.array([5.0, -7.0, 3.0])
    p = properties(*arr(mf.Manifold.cube((a, b, c)).translate(tuple(off))), rho)
    m = rho * a * b * c * 1e-9
    I = m / 12 * np.array([b * b + c * c, a * a + c * c, a * a + b * b]) * 1e-6
    rows.append(_row("box 30x20x10 mm offset", p, m, off + 0.5 * np.array([a, b, c]), np.diag(I)))

    n, r, h = 64, 10.0, 40.0
    p = properties(*arr(mf.Manifold.cylinder(h, r, r, n)), rho)
    area = 0.5 * n * r * r * np.sin(2 * np.pi / n)                    # regular n-gon
    m = rho * area * h * 1e-9
    # polar area moment of a regular n-gon: n r^4 sin(2pi/n) (2 + cos(2pi/n)) / 12; Ixx is half of it
    Ixx_poly = rho * h * 1e-9 * (n * r ** 4 / 24) * np.sin(2 * np.pi / n) * (2 + np.cos(2 * np.pi / n)) * 1e-6
    Izz = 2 * Ixx_poly
    Ixx = Ixx_poly + m * h * h / 12 * 1e-6
    rows.append(_row("64-gon prism r 10 h 40 mm", p, m, np.array([0, 0, h / 2]), np.diag([Ixx, Ixx, Izz])))

    A, t = np.array([40.0, 30.0, 20.0]), 1.0
    shell = mf.Manifold.cube(tuple(A), True) - mf.Manifold.cube(tuple(A - 2 * t), True)
    p = properties(*arr(shell), rho)
    Bi = A - 2 * t
    mo, mi = rho * A.prod() * 1e-9, rho * Bi.prod() * 1e-9

    def Ibox(mm, d):
        return mm / 12 * np.array([d[1] ** 2 + d[2] ** 2, d[0] ** 2 + d[2] ** 2, d[0] ** 2 + d[1] ** 2]) * 1e-6
    rows.append(_row("hollow box 40x30x20, wall 1 mm", p, mo - mi, np.zeros(3), np.diag(Ibox(mo, A) - Ibox(mi, Bi))))
    return rows


def _row(name, p, m, cg_mm, I):
    em = abs(p["mass_kg"] - m) / m
    ecg = float(np.abs(np.asarray(p["cg_mm"]) - cg_mm).max())
    eI = float(np.abs(np.asarray(p["inertia_cg_kg_m2"]) - I).max() / np.abs(I).max())
    return {"control": name, "mass_rel_err": float(em), "cg_abs_err_mm": ecg, "inertia_rel_err": eI,
            "ok": bool(em < 1e-9 and ecg < 1e-9 and eI < 1e-9)}
