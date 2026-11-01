"""Fins part: hypocercal caudal fin + dorsal fin + anal fin (shared frame, mm).

+X nose, Z up, Y left.  Fins are vertical plates (thin in y), outlines are shapely polygons
in the (x, z) plane, smoothed with buffers, extruded, then tapered in thickness.
build() returns one trimesh with three separate watertight shells (assembler fuses them).
"""
import os
import numpy as np
import trimesh
from shapely.geometry import Polygon

HERE = os.path.dirname(os.path.abspath(__file__))


def smooth(poly, r_convex=0.9, r_concave=1.5):
    p = poly.buffer(-r_convex, join_style=1).buffer(r_convex, join_style=1)  # round convex corners
    p = p.buffer(r_concave, join_style=1).buffer(-r_concave, join_style=1)   # round concave corners
    return p


def curve(p0, p1, bulge, n=8):
    """points from p0 to p1 (exclusive of p1) bowed sideways by `bulge` mm (quadratic)."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    d = p1 - p0
    nrm = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-9)
    out = []
    for t in np.linspace(0, 1, n, endpoint=False):
        out.append(p0 + d * t + nrm * bulge * 4 * t * (1 - t))
    return out


def extrude_fin(poly, t_func):
    """Extrude (x,z) polygon in y, thickness t_func(x,z) (full thickness, linear in x,z so caps stay planar)."""
    m = trimesh.creation.extrude_polygon(poly, height=1.0)  # coords (x, z, e) with e in [0,1]
    v = m.vertices.copy()
    x, z, e = v[:, 0], v[:, 1], v[:, 2]
    t = t_func(x, z)
    y = (e - 0.5) * t
    new = np.column_stack([x, y, z])
    faces = m.faces[:, ::-1]  # axis swap mirrors; restore outward winding
    out = trimesh.Trimesh(new, faces, process=True)
    out.fix_normals()
    return out


def rounded_edges(poly, thick, steps=(0.0, 0.25, 0.5)):
    """not used (kept simple); placeholder for lens-section edges."""
    return None


def ridge(x0, x1, zc, half_t, half_h):
    s = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    s.apply_scale([(x0 - x1) / 2.0 if x0 > x1 else (x1 - x0) / 2.0, half_t, half_h])
    s.apply_translation([(x0 + x1) / 2.0, 0, zc])
    return s


def union(a, b):
    return trimesh.boolean.union([a, b], engine="manifold")


def caudal():
    # hypocercal: lower lobe tip x=-102 (24 mm from root at -78), upper lobe 18.5 mm (ratio 1.3)
    root_x = -78.0
    up_tip = (-96.5, 10.0)
    lo_tip = (-102.0, -13.5)
    notch = (-87.8, -0.8)  # fork depth ~60 % of the 24 mm lobe length
    pts = []
    pts += [(root_x, 3.6)]
    pts += curve((root_x, 3.6), (up_tip[0] + 1.0, up_tip[1] - 0.5), 0.8)
    pts += [(up_tip[0] + 1.0, up_tip[1] - 0.5), (up_tip[0], up_tip[1] + 0.6), (up_tip[0] - 1.8, up_tip[1] - 0.8)]
    pts += curve((up_tip[0] - 1.8, up_tip[1] - 0.8), notch, -0.9)
    pts += curve(notch, (lo_tip[0] - 0.0, lo_tip[1] + 1.2), -1.2)
    pts += [(lo_tip[0], lo_tip[1] + 1.2), (lo_tip[0] + 1.6, lo_tip[1]), (lo_tip[0] + 3.2, lo_tip[1] + 0.8)]
    pts += curve((lo_tip[0] + 3.2, lo_tip[1] + 0.8), (root_x, -3.6), 1.0)
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    poly = smooth(poly, 0.9, 1.5)
    # thickness 1.2 at root tapering to 1.0 mm at x=-102 (never below 1.0)
    f = lambda x, z: np.clip(1.2 - 0.2 * (root_x - x) / 24.0, 1.0, 1.2)
    fin = extrude_fin(poly, f)
    # thickened rounded root (embedded in peduncle): ellipsoid 2.4 mm thick
    base = ridge(root_x + 1.5, root_x - 3.0, 0.0, 1.3, 4.2)
    fin = union(fin, base)
    return fin, poly


def dorsal():
    z0 = 6.0  # root bottom, 3 mm below nominal surface z~9 (>=2.5 mm embed incl. rear taper)
    pts = [(-40.0, z0), (-40.0, 9.0)]
    pts += curve((-40.0, 9.0), (-45.0, 18.0), -0.6)
    pts += [(-45.0, 18.0), (-47.2, 17.6)]
    pts += curve((-47.2, 17.6), (-51.0, 8.0), 1.2)
    pts += [(-51.0, 8.0), (-51.0, z0)]
    poly = smooth(Polygon(pts), 0.7, 1.2)
    f = lambda x, z: np.full_like(x, 0.9)
    fin = extrude_fin(poly, f)
    fin = union(fin, ridge(-39.5, -51.5, z0 + 1.0, 1.0, 2.2))
    return fin, poly


def anal():
    z0 = -5.5
    pts = [(-46.0, z0), (-46.0, -8.0)]
    pts += curve((-46.0, -8.0), (-52.0, -16.0), 0.6)
    pts += [(-52.0, -16.0), (-54.8, -15.6)]
    pts += curve((-54.8, -15.6), (-61.0, -8.0), -1.2)
    pts += [(-61.0, -8.0), (-61.0, z0)]
    poly = smooth(Polygon(pts), 0.7, 1.2)
    f = lambda x, z: np.full_like(x, 0.9)
    fin = extrude_fin(poly, f)
    fin = union(fin, ridge(-45.5, -61.5, z0 - 1.0, 1.0, 2.2))
    return fin, poly


def shells():
    return [caudal()[0], dorsal()[0], anal()[0]]


def build():
    parts = shells()
    return trimesh.util.concatenate(parts)


def check(parts, names=("caudal", "dorsal", "anal")):
    for n, p in zip(names, parts):
        print(f"{n}: watertight={p.is_watertight} volume={p.volume:.2f} mm3 faces={len(p.faces)} "
              f"bbox={np.round(p.bounds[0],2)}..{np.round(p.bounds[1],2)} bodies={len(p.split(only_watertight=False))}")


def preview(mesh, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa
    fig = plt.figure(figsize=(15, 5.5))
    views = [("top (x,y)", 90, -90), ("side (x,z)", 0, -90), ("front (y,z)", 0, 0)]
    v, f = mesh.vertices, mesh.faces
    tri = v[f]
    nrm = mesh.face_normals
    light = np.array([0.4, -0.5, 0.8]); light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.clip(nrm @ light, 0, 1)
    cols = np.column_stack([shade * 0.35, shade * 0.6, shade * 0.9, np.ones_like(shade)])
    for i, (title, elev, azim) in enumerate(views, 1):
        ax = fig.add_subplot(1, 3, i, projection="3d")
        pc = Poly3DCollection(tri, facecolors=cols, edgecolor="none")
        ax.add_collection3d(pc)
        lo, hi = mesh.bounds
        c = (lo + hi) / 2
        r = (hi - lo).max() / 2 + 2
        ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(title)
        ax.set_xlabel("x"); ax.set_ylabel("y"); ax.set_zlabel("z")
    plt.tight_layout()
    plt.savefig(path, dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    parts = shells()
    check(parts)
    m = trimesh.util.concatenate(parts)
    print("combined bbox", m.bounds.round(2).tolist(), "watertight", m.is_watertight)
    m.export(os.path.join(HERE, "tail.stl"))
    preview(m, os.path.join(HERE, "tail_preview.png"))
