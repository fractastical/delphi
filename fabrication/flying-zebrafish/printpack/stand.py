"""Display stand for the flying zebrafish. Frame/units: see ../SPEC.md (mm, +X nose, Z up).

build_stand() -> watertight trimesh.Trimesh: round base, slim rod, saddle pad under the belly.
One surface of revolution about the vertical axis x=rod_x, y=0.

Parameters
  rod_x      x of the rod axis (mm)                          default -38
  belly_z    z of the lowest belly surface at rod_x          default -9.5
  rod_h      visible rod length, base top -> pad underside   default 18
  detach_gap 0.0 -> pad dish centre sinks `overlap` (1.5) mm INTO the belly (fuses on union).
             >0  -> pad top sits `detach_gap` mm BELOW the belly (separate part, glue / press).
  base_d (36), base_h (3), base_edge_r (1.5, fully rounded rim), rod_d (3), pad_d (9),
  pad_h (2), overlap (1.5), dish (0.6: pad rim is higher than centre so it cups the belly)
Base bottom z = belly_z + overlap - pad_h - rod_h - base_h (see stand_info()['bounds']).
"""
import numpy as np
import trimesh


def _profile(belly_z, rod_h, detach_gap, base_d, base_h, base_edge_r, rod_d, pad_d, pad_h,
             overlap, dish, n_arc=10):
    R, r, rp = base_d / 2, rod_d / 2, pad_d / 2
    top_c = belly_z + overlap if detach_gap <= 0 else belly_z - detach_gap
    top_rim = top_c + dish
    pad_bot = top_c - pad_h
    z_base_top = pad_bot - rod_h
    z0 = z_base_top - base_h
    er = min(base_edge_r, base_h / 2)
    pts = [(0.0, z0), (R - er, z0)]
    cz = z0 + er  # bottom edge rounded
    for a in np.linspace(-np.pi / 2, 0, n_arc)[1:]:
        pts.append((R - er + er * np.cos(a), cz + er * np.sin(a)))
    ct = z_base_top - er  # top edge rounded
    if ct > cz:
        pts.append((R, ct))
    for a in np.linspace(0, np.pi / 2, n_arc)[1:]:
        pts.append((R - er + er * np.cos(a), ct + er * np.sin(a)))
    f = 0.8  # fillet rod/base
    pts.append((r + f, z_base_top))
    for a in np.linspace(0, np.pi / 2, 6)[1:]:
        pts.append((r + f - f * np.sin(a), z_base_top + f - f * np.cos(a)))
    pts.append((r, pad_bot - 1.5))
    pts.append((rp, pad_bot))  # flare
    pts.append((rp, top_rim - 0.3))
    pts.append((rp - 0.3, top_rim))
    for t in np.linspace(1, 0, 9)[1:-1]:
        rr = (rp - 0.3) * t
        pts.append((rr, top_c + dish * t ** 2))
    pts.append((0.0, top_c))
    out = [pts[0]]
    for p in pts[1:]:
        if np.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    return np.array(out)


def build_stand(rod_x=-38.0, belly_z=-9.5, rod_h=18.0, detach_gap=0.0, base_d=36.0, base_h=3.0,
                base_edge_r=1.5, rod_d=3.0, pad_d=9.0, pad_h=2.0, overlap=1.5, dish=0.6,
                sections=128):
    prof = _profile(belly_z, rod_h, detach_gap, base_d, base_h, base_edge_r, rod_d, pad_d, pad_h,
                    overlap, dish)
    m = trimesh.creation.revolve(prof, sections=sections)
    m.merge_vertices()
    m.update_faces(m.nondegenerate_faces())
    m.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(m)
    if m.volume < 0:
        m.invert()
    m.apply_translation([rod_x, 0, 0])
    return m


def stand_info(**kw):
    m = build_stand(**kw)
    return dict(watertight=bool(m.is_watertight), winding=bool(m.is_winding_consistent),
                volume_mm3=round(float(m.volume), 2), bounds=m.bounds.round(3).tolist())


def _preview(m, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(12, 4.5))
    for i, (t, el, az) in enumerate([("side", 0, -90), ("top", 90, -90), ("iso", 20, -55)]):
        ax = fig.add_subplot(1, 3, i + 1, projection="3d")
        ax.add_collection3d(Poly3DCollection(m.vertices[m.faces], facecolor="#9bb7d4",
                                             edgecolor="#335", linewidth=0.1))
        c, e = m.bounds.mean(0), (m.bounds[1] - m.bounds[0]).max() / 2
        ax.set_xlim(c[0] - e, c[0] + e); ax.set_ylim(c[1] - e, c[1] + e); ax.set_zlim(c[2] - e, c[2] + e)
        ax.view_init(el, az); ax.set_title(t); ax.set_box_aspect((1, 1, 1))
    fig.suptitle("stand (mm)")
    fig.savefig(path, dpi=110, bbox_inches="tight")


if __name__ == "__main__":
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    s = build_stand()
    s.export(os.path.join(here, "stand.stl"))
    _preview(s, os.path.join(here, "stand_preview.png"))
    print("fused:", stand_info())
    print("detach 0.4:", stand_info(detach_gap=0.4))
