"""A detachable display stand: base disc, post, and a saddle whose top is cut by the prop's own shape swept
upward, so the prop drops in and lifts out.  Printed separately; validated separately."""
from __future__ import annotations

import manifold3d as mf
import numpy as np

from .validate import thickness_samples

SIMPLIFY_TOL_MM = 1e-3
MIN_WALL_MM = 1.0

STAND = {
    "base_radius_mm": 30.0, "base_thickness_mm": 4.0, "post_radius_mm": 4.5, "saddle_half_length_mm": 6.0,
    "saddle_side_margin_mm": 3.0, "lateral_clearance_mm": 0.3, "clearance_below_prop_mm": 8.0,
}


def centroid(V: np.ndarray, T: np.ndarray) -> np.ndarray:
    tri = V[T]
    v6 = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2]))
    return (v6[:, None] * tri.sum(axis=1)).sum(axis=0) / (4 * v6.sum())


def build_stand(prop: mf.Manifold, V: np.ndarray, T: np.ndarray, body_half_width_at, body_bottom_at,
                circular: int = 48) -> tuple[mf.Manifold, dict]:
    """Stand in the prop's coordinates (assembly pose).  The post sits under the prop's volume centroid -- the
    centroid of a solid resin prop, not a biological centre of gravity."""
    s = STAND
    c = centroid(V, T)
    cx = float(c[0])
    zmin = float(V[:, 2].min())
    base_top = zmin - s["clearance_below_prop_mm"]
    sweep = [prop.translate((0, dy, dz)) for dy in (-s["lateral_clearance_mm"], 0, s["lateral_clearance_mm"])
             for dz in np.linspace(0, 40, 21)]
    cavity = mf.Manifold.batch_boolean(sweep, mf.OpType.Add)
    tried = []
    # Fin slots cut thin lips into the saddle; search saddle positions/heights near the centroid and keep the
    # first that is one piece with every sampled wall >= MIN_WALL_MM.
    for dx in (0, -2, 2, -4, 4, -6, 6, -8, 8, -10, 10):
        x = cx + dx
        z_bottom = body_bottom_at(x)
        w = body_half_width_at(x) + s["saddle_side_margin_mm"]
        saddle_lo = z_bottom - 4.0
        for frac in (0.45, 0.35, 0.25, 0.15):
            top = z_bottom * (1 - frac)
            saddle = mf.Manifold.cube((2 * s["saddle_half_length_mm"], 2 * w, top - saddle_lo)).translate(
                (x - s["saddle_half_length_mm"], -w, saddle_lo))
            post = mf.Manifold.cylinder(saddle_lo - base_top + 1.0, s["post_radius_mm"], s["post_radius_mm"],
                                        circular).translate((x, 0, base_top - 0.5))
            base = mf.Manifold.cylinder(s["base_thickness_mm"], s["base_radius_mm"], s["base_radius_mm"],
                                        circular).translate((x, 0, base_top - s["base_thickness_mm"]))
            stand = (mf.Manifold.batch_boolean([base, post, saddle], mf.OpType.Add) - cavity).simplify(SIMPLIFY_TOL_MM)
            parts = len(stand.decompose())
            mesh = stand.to_mesh()
            SV = np.asarray(mesh.vert_properties)[:, :3].astype(np.float64)
            ST = np.asarray(mesh.tri_verts).astype(np.int64)
            th = thickness_samples(SV, ST, n=1500, seed=11)
            tried.append({"dx_mm": dx, "top_frac": frac, "parts": parts, "min_wall_mm": th["min_mm"]})
            if parts == 1 and th["min_mm"] is not None and th["min_mm"] >= MIN_WALL_MM:
                break
        else:
            continue
        break
    else:
        raise ValueError(f"no saddle placement met the checks: {tried}")
    return stand, {"post_x_mm": x, "post_offset_from_centroid_mm": x - cx,
                   "prop_volume_centroid_mm": c.round(3).tolist(), "saddle_top_z_mm": top,
                   "placement_search": tried, "base_top_z_mm": base_top, "params": dict(s),
                   "note": "post near the solid prop's volume centroid (resin prop, not a biological centre of "
                           "gravity); the prop balancing on the saddle is not tested"}
