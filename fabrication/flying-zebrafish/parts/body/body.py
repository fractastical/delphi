"""Flying-zebrafish body: head + trunk + caudal peduncle (SPEC.md frame, mm).

Nose tip at x=0, peduncle end (flat) at x=-80, +X nose, Z up, Y left.
Lofted superellipse sections with asymmetric dorsal/ventral depth, displaced for
operculum groove, mouth line and (optional) five stripes; ellipsoid eyes unioned.
"""
import os
import numpy as np
import trimesh
from scipy.interpolate import PchipInterpolator

HERE = os.path.dirname(os.path.abspath(__file__))
SL = 80.0

# control stations: s=-x, half-height dorsal, half-height ventral, half-width
CTRL = np.array([
    [6,  3.6, 3.0, 2.6],
    [12, 5.8, 5.6, 4.2],
    [20, 8.4, 8.4, 5.9],
    [30, 9.4, 9.8, 5.9],
    [40, 9.0, 9.6, 5.2],
    [50, 7.8, 8.2, 4.4],
    [60, 6.2, 6.4, 3.6],
    [70, 4.6, 4.6, 2.8],
    [76, 4.0, 4.0, 2.5],
    [80, 4.0, 4.0, 2.5],
])
_f = [PchipInterpolator(CTRL[:, 0], CTRL[:, k]) for k in (1, 2, 3)]
NOSE_L = 6.0
N_DORS, N_VENT = 2.3, 3.2      # superellipse exponents (ventral flatter)


def dims(s):
    """half-heights (top, bottom), half-width, centre-line lift at station s."""
    s = float(s)
    ss = max(s, NOSE_L)
    k = np.sqrt(np.clip(1 - (1 - min(s, NOSE_L) / NOSE_L) ** 2, 0, 1))
    ht, hb, hw = (float(f(ss)) * k for f in _f)
    cz = 0.6 * float(np.clip(1 - s / 12.0, 0, 1))   # nose lifted -> upturned mouth
    return ht, hb, hw, cz


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def body_mesh(stripes=True, nth=240):
    s_st = np.concatenate([[0.05, 0.15], np.arange(0.3, 80.0001, 0.2)])
    s_st[-1] = 80.0
    th = np.linspace(0, 2 * np.pi, nth, endpoint=False)
    c, sn = np.cos(th), np.sin(th)
    ey = np.sign(c) * np.abs(c) ** (2 / N_DORS)
    ezr = np.where(sn >= 0, np.abs(sn) ** (2 / N_DORS), -np.abs(sn) ** (2 / N_VENT))
    M = len(s_st)
    dd = np.array([dims(s) for s in s_st])
    ht_g, hb_g, hw_g, cz_g = (dd[:, k][:, None] for k in range(4))
    X = -s_st[:, None] * np.ones((1, nth))
    Y = hw_g * ey[None, :]
    h = np.where(sn[None, :] >= 0, ht_g, hb_g)
    Z = cz_g + h * ezr[None, :]
    D = np.zeros_like(X)
    S = -X
    zr = Z - cz_g
    flank = np.abs(Y) > 0.35 * hw_g
    # operculum groove (convex backward arc), depth 0.25, half-width 0.45
    sg = 17.0 + 2.0 * (1 - np.clip(zr / 8.0, -1.2, 1.2) ** 2)
    wg = smoothstep(1 - np.abs(S - sg) / 0.45)
    D -= 0.25 * wg * flank * (np.abs(zr) < 7.0)
    # mouth line: slants up toward the front (upturned), both sides
    zl = -1.0 + 0.30 * (5.0 - S)
    wm = smoothstep(1 - np.abs(zr - zl) / 0.40)
    D -= 0.25 * wm * (S > 0.5) * (S < 5.0) * (np.abs(Y) > 0.2)
    if stripes:
        sp = 0.12 * (ht_g + hb_g)
        hwid = 0.22 * sp
        env = smoothstep((S - 22) / 3.0) * smoothstep((76 - S) / 3.0)
        st = np.zeros_like(X)
        for k in range(-2, 3):
            st = np.maximum(st, smoothstep((hwid - np.abs(zr - k * sp)) / (0.45 * hwid)))
        D += 0.18 * st * env * flank
    r = np.sqrt(Y ** 2 + zr ** 2) + 1e-9
    Y2 = Y * (1 + D / r)
    Z2 = cz_g + zr * (1 + D / r)
    Y2[0] = Y[0]; Z2[0] = Z[0]
    Y2[-1] = Y[-1]; Z2[-1] = Z[-1]
    V = np.stack([X, Y2, Z2], -1).reshape(-1, 3)
    V = np.vstack([V, [[0.0, 0.0, dims(0.0)[3]]], [[-80.0, 0.0, 0.0]]])
    inose, icap = len(V) - 2, len(V) - 1
    idx = lambda i, j: i * nth + (j % nth)
    F = []
    for i in range(M - 1):
        for j in range(nth):
            a, b, c_, d = idx(i, j), idx(i, j + 1), idx(i + 1, j + 1), idx(i + 1, j)
            F += [[a, d, c_], [a, c_, b]]
    for j in range(nth):
        F.append([inose, idx(0, j + 1), idx(0, j)])
        F.append([icap, idx(M - 1, j), idx(M - 1, j + 1)])
    m = trimesh.Trimesh(V, np.array(F), process=False)
    trimesh.repair.fix_normals(m)
    return m


def ellipsoid(center, radii, sub=4):
    e = trimesh.creation.icosphere(subdivisions=sub, radius=1.0)
    e.vertices = e.vertices * np.array(radii) + np.array(center)
    return e


def eyes():
    xe = -0.07 * SL          # eye centre x (diameter 5.6 mm)
    ht, hb, hw, cz = dims(-xe)
    ze = cz + 0.9
    ye = hw * 0.78
    return [ellipsoid([xe, sg * ye, ze], [2.8, 2.4, 2.8]) for sg in (1, -1)]


def build(stripes=True):
    b = body_mesh(stripes=stripes)
    m = trimesh.boolean.union([b] + eyes(), engine="manifold")
    m.merge_vertices()
    m.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(m)
    return m


def preview(m, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    tri = m.triangles
    n = m.face_normals
    # (title, axes, depth axis, visibility mask, depth sign: larger = nearer camera)
    views = [("side (x,z) from -y", (0, 2), n[:, 1] < 0, -tri[:, :, 1].mean(1)),
             ("top (x,y) from +z", (0, 1), n[:, 2] > 0, tri[:, :, 2].mean(1)),
             ("front (y,z) from +x", (1, 2), n[:, 0] > 0, tri[:, :, 0].mean(1))]
    fig, axs = plt.subplots(1, 3, figsize=(18, 6), dpi=110)
    light = np.array([0.4, -0.5, 0.8]); light /= np.linalg.norm(light)
    for ax, (name, (a, b), vis, near) in zip(axs, views):
        order = np.argsort(near)
        keep = order[vis[order]]
        polys = tri[keep][:, :, [a, b]]
        shade = 0.35 + 0.65 * np.clip(n[keep] @ light, 0, 1)
        col = np.stack([shade * 0.55, shade * 0.75, shade * 0.9, np.ones_like(shade)], 1)
        ax.add_collection(PolyCollection(polys, facecolors=col, edgecolors="none"))
        ax.set_xlim(polys[:, :, 0].min() - 2, polys[:, :, 0].max() + 2)
        ax.set_ylim(polys[:, :, 1].min() - 2, polys[:, :, 1].max() + 2)
        ax.set_aspect("equal"); ax.set_title(name)
    fig.savefig(path); plt.close(fig)


if __name__ == "__main__":
    m = build(stripes=True)
    ok = m.is_watertight and m.is_winding_consistent and m.volume > 0
    print("stripes: watertight", m.is_watertight, "winding", m.is_winding_consistent, "vol", m.volume)
    nb = build(stripes=False)
    if nb.is_watertight and nb.volume > 0:
        nb.export(os.path.join(HERE, "body_nostripes.stl"))
    if not ok:
        print("stripes failed -> fallback to no stripes")
        m = nb
    m.export(os.path.join(HERE, "body.stl"))
    preview(m, os.path.join(HERE, "body_preview.png"))
    print("faces", len(m.faces), "bbox", m.bounds.tolist(), "volume", m.volume,
          "watertight", m.is_watertight, "winding", m.is_winding_consistent,
          "bodies", len(m.split(only_watertight=False)))
