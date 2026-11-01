"""Left pectoral wing (y > 0) of the flying zebrafish. Shared frame: mm, +X nose, +Y left, +Z up.

Lofted from spanwise airfoil-like sections. Each section has chord, sweep offset, camber, thickness
and twist. Root is extended 3 mm inward (rounded, thickened root block) so a union with the body fuses.
build() -> watertight trimesh.Trimesh; mirrored() -> right wing.
"""
import os
import numpy as np
import trimesh
import mapbox_earcut as earcut

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- parameters (mm / degrees) ----
ROOT = np.array([-20.0, 5.0, 3.0])   # insertion: mid-chord of root section
C_ROOT, C_TIP = 16.0, 8.0
SPREAD = np.radians(80.0)            # span axis angle from +X (body axis)
DIHEDRAL = np.radians(7.0)
SWEEP = np.radians(36.0)             # LE sweep back relative to the span axis (net ~26 deg from lateral)
CAMBER_ROOT, CAMBER_TIP = 3.2, 2.0   # dorsal camber (mm)
TM_ROOT, TM_TIP = 2.3, 1.9           # max section thickness at LE hump
TE_RATIO = 0.70                      # trailing-edge thickness / max thickness (tip TE ~1.3 mm)
TWIST_ROOT, TWIST_TIP = 3.0, 0.0     # TE-down pitch (deg) washing out toward the tip
EMBED = 3.0                          # root extension (mm, along the span axis)
TIP_TAPER_LEN = 6.0                  # last mm over which planform narrows to a point
TIP_MIN_CHORD = 0.35                 # fraction of tip chord left at the final cap
TIP_Y = 60.0                         # target max |y| of the wing
N_RAYS = 14                          # radial ray ridges on the upper surface
RAY_H = 0.12                         # ridge height (mm)
NC = 128                             # chordwise samples per surface
DS = 0.35                            # span station spacing (mm)


def _smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def _profile(xi):
    """Thickness shape g(xi) in [TE_RATIO..1.25]: round LE, rigid thick LE hump, thin TE."""
    xi = np.asarray(xi, float)
    le = np.sqrt(np.clip(1 - (1 - np.clip(xi / 0.12, 0, 1)) ** 2, 0, 1))
    fall = 1 - (1 - TE_RATIO) * _smooth((xi - 0.12) / 0.88)
    hump = 1 + 0.25 * np.clip(1 - (xi - 0.12) / 0.40, 0, 1)
    return le * fall * hump


def _frame(s, theta):
    """Return span axis u, chord (LE->TE) cb and normal n (up) for pitch theta (rad)."""
    u = np.array([np.cos(SPREAD) * np.cos(DIHEDRAL), np.sin(SPREAD) * np.cos(DIHEDRAL), np.sin(DIHEDRAL)])
    cb0 = np.array([-np.sin(SPREAD), np.cos(SPREAD), 0.0])
    n0 = np.cross(u, cb0)
    n0 /= np.linalg.norm(n0)
    cb = cb0 * np.cos(theta) - n0 * np.sin(theta)   # TE down
    n = n0 * np.cos(theta) + cb0 * np.sin(theta)
    return u, cb, n


def _stations(L):
    s_main = np.arange(0.0, L - TIP_TAPER_LEN, DS)
    # finer spacing in the tip taper
    s_tip = np.linspace(L - TIP_TAPER_LEN, L, 24)
    s_root = np.linspace(-EMBED, 0.0, 9)[:-1]
    return np.concatenate([s_root, s_main, s_tip])


def _section(s, L, ridge=True):
    """Loop of 3D points for station s: upper LE->TE then lower TE->LE (LE shared)."""
    f = np.clip(s, 0, L) / L
    c = C_ROOT + (C_TIP - C_ROOT) * f
    tm = TM_ROOT + (TM_TIP - TM_ROOT) * f
    cam = CAMBER_ROOT + (CAMBER_TIP - CAMBER_ROOT) * f
    theta = np.radians(TWIST_ROOT + (TWIST_TIP - TWIST_ROOT) * f)
    sweep_off = np.tan(SWEEP) * max(s, 0.0)
    cmult = 1.0
    tmult = 1.0
    # scalloped (pointed) trailing edge
    scal = 0.0
    if s > 3.0:
        scal = 0.06 * (1 - abs(np.sin(np.pi * s / 7.5)))
    # planform tip taper: narrow chord to a point-ish end
    if s > L - TIP_TAPER_LEN:
        a = (s - (L - TIP_TAPER_LEN)) / TIP_TAPER_LEN
        cmult = TIP_MIN_CHORD + (1 - TIP_MIN_CHORD) * np.sqrt(max(1 - a * a, 0.0))
        sweep_off += 0.0
    if s < 0:  # embedded root block: thicker, slightly narrower, rounded
        a = -s / EMBED
        tmult = 1 + 0.45 * _smooth(a)
        cmult = 1 - 0.12 * _smooth(a)
        sweep_off = 0.0
    c = c * cmult * (1 - scal)
    tm = tm * tmult
    # keep camber line tapering at the planform tip
    u, cb, n = _frame(s, theta)
    O = ROOT - _frame(0, np.radians(TWIST_ROOT))[1] * (C_ROOT / 2)
    # chordwise cosine spacing
    t = np.linspace(0, np.pi, NC + 1)
    xi = 0.5 * (1 - np.cos(t))
    zc = cam * 4 * xi * (1 - xi) * (cmult if s <= L else 1)
    half = 0.5 * tm * _profile(xi)
    base = O + u * s + cb * sweep_off
    # optional ridges on upper surface only
    ridge_dz = np.zeros_like(xi)
    if ridge and s > 2.0 and s < L - 3.0:
        win = _smooth((xi - 0.14) / 0.08) * _smooth((0.96 - xi) / 0.06) * _smooth((s - 2.0) / 3.0) * _smooth((L - 3.0 - s) / 3.0)
        ridge_dz = RAY_H * win * (0.5 + 0.5 * np.cos(2 * np.pi * N_RAYS * xi))
    up = base + np.outer(xi * c, cb) + np.outer(zc + half + ridge_dz, n)
    lo = base + np.outer(xi * c, cb) + np.outer(zc - half, n)
    loop = np.vstack([up, lo[::-1][:-1]])  # upper LE..TE, lower TE..xi_1 (LE shared)
    loc2 = np.column_stack([np.concatenate([xi * c, (xi * c)[::-1][:-1]]),
                            np.concatenate([zc + half + ridge_dz, (zc - half)[::-1][:-1]])])
    return loop, loc2


def _solve_L():
    # choose span length so that the wing's max y equals TIP_Y
    lo, hi = 30.0, 70.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        y = _tip_ymax(mid)
        if y > TIP_Y:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def _tip_ymax(L):
    ys = []
    for s in (L - TIP_TAPER_LEN, L):
        loop, _ = _section(s, L, ridge=False)
        ys.append(loop[:, 1].max())
    return max(ys)


def build(ridge=True) -> trimesh.Trimesh:
    L = _solve_L()
    S = _stations(L)
    loops, locs = [], []
    for s in S:
        lp, l2 = _section(float(s), L, ridge=ridge)
        loops.append(lp)
        locs.append(l2)
    M = len(loops[0])
    V = np.vstack(loops)
    faces = []
    for i in range(len(S) - 1):
        a = i * M
        b = (i + 1) * M
        j = np.arange(M)
        j2 = (j + 1) % M
        faces.append(np.column_stack([a + j, a + j2, b + j2]))
        faces.append(np.column_stack([a + j, b + j2, b + j]))
    faces = np.vstack(faces)
    caps = []
    for idx, rev in ((0, True), (len(S) - 1, False)):
        tri = earcut.triangulate_float64(locs[idx].astype(np.float64), np.array([M], dtype=np.uint32)).reshape(-1, 3)
        tri = tri + idx * M
        caps.append(tri[:, ::-1] if rev else tri)
    faces = np.vstack([faces] + caps)
    xi_all = 0.5 * (1 - np.cos(np.linspace(0, np.pi, NC + 1)))
    ups = np.vstack([np.column_stack([V[i * M:i * M + NC + 1], xi_all, np.full(NC + 1, S[i])]) for i in range(len(S))])
    m = trimesh.Trimesh(V, faces, process=True)
    m.metadata["upper_samples"] = ups  # x, y, z, xi, s of every upper-surface vertex
    m.merge_vertices()
    trimesh.repair.fix_inversion(m)
    trimesh.repair.fix_normals(m)
    if m.volume < 0:
        m.invert()
    m.metadata["span_length"] = L
    return m


def mirrored(mesh=None) -> trimesh.Trimesh:
    m = (mesh if mesh is not None else build()).copy()
    v = m.vertices.copy()
    v[:, 1] *= -1
    m = trimesh.Trimesh(v, m.faces[:, ::-1], process=False)
    return m


def _vertical_hits(m, pts):
    """For each (x, y) in pts, z of all triangle crossings along a vertical line (no rtree needed)."""
    tri = m.triangles
    mn = tri[:, :, :2].min(1)
    mx = tri[:, :, :2].max(1)
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    d = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
    ok = np.abs(d) > 1e-12
    res = []
    for p in pts:
        cand = np.where((mn[:, 0] <= p[0]) & (mx[:, 0] >= p[0]) & (mn[:, 1] <= p[1]) & (mx[:, 1] >= p[1]) & ok)[0]
        zs = []
        for i in cand:
            dd = d[i]
            u = ((p[0] - a[i, 0]) * (c[i, 1] - a[i, 1]) - (c[i, 0] - a[i, 0]) * (p[1] - a[i, 1])) / dd
            v = ((b[i, 0] - a[i, 0]) * (p[1] - a[i, 1]) - (p[0] - a[i, 0]) * (b[i, 1] - a[i, 1])) / dd
            if u >= -1e-9 and v >= -1e-9 and u + v <= 1 + 1e-9:
                zs.append(a[i, 2] + u * (b[i, 2] - a[i, 2]) + v * (c[i, 2] - a[i, 2]))
        zs = np.sort(zs)[::-1]
        # merge duplicate hits on shared edges
        zs = [z for k, z in enumerate(zs) if k == 0 or abs(z - zs[k - 1]) > 1e-6]
        res.append(np.array(zs))
    return res


def min_thickness(m, xi_lo=0.10, xi_hi=0.96, tip_span=15.0, stride=5):
    """Vertical-ray thickness (top surface to the next surface below) over the outer `tip_span` mm of wing,
    excluding the rounded LE (xi<xi_lo), the last 4% of chord at the TE rim and the last 3 mm of the tip rim."""
    ups = m.metadata["upper_samples"]
    ymax = m.vertices[:, 1].max()
    sel = (ups[:, 3] >= xi_lo) & (ups[:, 3] <= xi_hi) & (ups[:, 1] > ymax - tip_span) & (ups[:, 1] < ymax - 3.0)
    pts = ups[sel][::stride]
    hits = _vertical_hits(m, pts[:, :2])
    th, keep = [], []
    for p, z in zip(pts, hits):
        if len(z) < 2:
            continue
        k = int(np.argmin(np.abs(z - p[2])))
        if k + 1 < len(z):
            th.append(z[k] - z[k + 1]); keep.append(p)
    return np.array(th), np.array(keep)


def _preview(m, pair, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(14, 10))
    views = [("top (+Z)", 90, -90), ("side (-Y)", 0, -90), ("front (+X)", 0, 0), ("oblique", 28, -55)]
    allv = m.vertices
    mid = (allv.max(0) + allv.min(0)) / 2
    r = (allv.max(0) - allv.min(0)).max() / 2 * 1.05
    for k, (title, el, az) in enumerate(views):
        ax = fig.add_subplot(2, 2, k + 1, projection="3d")
        tris = m.vertices[m.faces]
        nrm = m.face_normals
        light = np.array([0.4, -0.3, 0.85]); light /= np.linalg.norm(light)
        shade = 0.35 + 0.65 * np.clip(nrm @ light, 0, 1)
        cols = np.column_stack([shade * 0.55, shade * 0.75, shade * 0.95, np.ones_like(shade)])
        ax.add_collection3d(Poly3DCollection(tris, facecolors=cols, edgecolor="none"))
        ax.set_xlim(mid[0] - r, mid[0] + r); ax.set_ylim(mid[1] - r, mid[1] + r); ax.set_zlim(mid[2] - r, mid[2] + r)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=el, azim=az)
        ax.set_title(title); ax.set_xlabel("x"); ax.set_ylabel("y"); ax.set_zlabel("z")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    left = build()
    right = mirrored(left)
    pair = trimesh.util.concatenate([left, right])
    left.export(os.path.join(HERE, "pectoral.stl"))
    pair.export(os.path.join(HERE, "pectoral_pair.stl"))
    _preview(left, pair, os.path.join(HERE, "pectoral_preview.png"))
    print("faces", len(left.faces), "watertight", left.is_watertight, "winding", left.is_winding_consistent,
          "volume", round(left.volume, 2))
    print("bounds", left.bounds.round(2).tolist(), "span L", round(left.metadata["span_length"], 2))
    th, pts = min_thickness(left)
    print("tip-region (y>45) vertical thickness: min", round(th.min(), 3), "p5", round(float(np.percentile(th, 5)), 3),
          "median", round(float(np.median(th)), 3), "n", len(th))
    i = int(np.argmin(th)); print("min at", pts[i].round(2))
