"""Left (y>0) pelvic wing of the flying zebrafish. Shared frame: mm, +X nose, Y left, Z up.

Lofted superellipse sections (rounded blunt edges, no knife edges) with dorsal camber,
scalloped trailing edge, pointed tip and a 3 mm rounded root block embedded in the body.
"""
import os
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))

P0 = np.array([-40.0, 3.0, -8.0])   # insertion on the belly flank (s = 0)
L = 32.0                            # span along span axis
EMBED = 3.0                         # root block depth toward the body axis
SWEEP = np.radians(30.0)            # leading edge swept back from +y
DIHEDRAL = np.radians(-4.0)         # slight droop, keeps wing below the pectoral plane
SPAN = np.array([-np.sin(SWEEP) * np.cos(DIHEDRAL), np.cos(SWEEP) * np.cos(DIHEDRAL), np.sin(DIHEDRAL)])
CHORD = np.array([-np.cos(SWEEP), -np.sin(SWEEP), 0.0])   # towards trailing edge (back, slightly inward)
ZH = np.cross(CHORD, SPAN); ZH /= np.linalg.norm(ZH)
if ZH[2] < 0:
    ZH = -ZH
N_RING = 56
EXP = 2.6          # superellipse exponent (blunt, rounded edges)


def chord_at(s):
    c = 10.0 - 5.0 * np.clip(s, 0, L) / L
    # pointed tip: chord falls to ~1.6 mm over the last 7 mm
    if s > L - 7:
        f = np.clip((L - s) / 7.0, 0, 1)
        c = (5.0 - 1.6) * f ** 0.8 + 1.6
    # slight scallops on the trailing edge (3 lobes, ~0.5 mm)
    if 4 < s < L - 2:
        c -= 0.55 * (0.5 - 0.5 * np.cos(2 * np.pi * (s - 4) / ((L - 6) / 3.0)))
    return c


def thick_at(s):
    return 1.6 - 0.6 * np.clip(s, 0, L) / L          # 1.6 root -> 1.0 tip


def ring(s):
    scale = 1.0
    if s < -EMBED + 1.5:                              # rounded root block end
        scale = np.sqrt(max(1 - ((-EMBED + 1.5 - s) / 1.5) ** 2, 0.0))
    elif s > L - 1.0:                                 # tip dome
        scale = np.sqrt(max(1 - ((s - (L - 1.0)) / 1.0) ** 2, 0.0))
    sc = np.clip(s, 0, L)
    c = chord_at(sc) * scale
    h = thick_at(sc) * scale
    th = np.linspace(0, 2 * np.pi, N_RING, endpoint=False)
    ct, st = np.cos(th), np.sin(th)
    u = 0.5 + 0.5 * np.sign(ct) * np.abs(ct) ** (2 / EXP)       # chord fraction 0..1 (LE at 0)
    zl = 0.5 * h * np.sign(st) * np.abs(st) ** (2 / EXP)
    camber = 0.175 * chord_at(sc) * 4 * u * (1 - u) * scale + 0.0 * u
    # LE is d=0 (reverse so LE at u=0 is the "front")
    d = u * c
    z = zl + camber * 0.5 * (1 + 0.0)  # half of camber shifts the section up
    return d, z


def build() -> trimesh.Trimesh:
    n_st = 110
    ss = np.concatenate([
        np.linspace(-EMBED, -EMBED + 1.5, 8, endpoint=False),
        np.linspace(-EMBED + 1.5, L - 1.0, n_st, endpoint=False),
        np.linspace(L - 1.0, L, 10),
    ])
    rings = []
    for s in ss:
        d, z = ring(s)
        # camber of the spine: dorsal bow along the span (0.4 mm) added
        zb = 0.4 * np.sin(np.pi * np.clip(s, 0, L) / L) if s > 0 else 0.0
        pts = P0 + np.outer(s * np.ones_like(d), SPAN) + np.outer(d - chord_at(max(s, 0)) * 0.0, CHORD) \
            + np.outer(z + zb, ZH)
        rings.append(pts)
    V = np.vstack(rings)
    n = len(rings)
    F = []
    for i in range(n - 1):
        a = i * N_RING; b = (i + 1) * N_RING
        for j in range(N_RING):
            j2 = (j + 1) % N_RING
            F.append([a + j, b + j, b + j2]); F.append([a + j, b + j2, a + j2])
    # caps: centroid fans (end rings have scale 0 -> collapsed; use centroid anyway)
    for idx, flip in ((0, True), (n - 1, False)):
        base = idx * N_RING
        c = V[base:base + N_RING].mean(0)
        V = np.vstack([V, c]); ci = len(V) - 1
        for j in range(N_RING):
            j2 = (j + 1) % N_RING
            F.append([ci, base + j2, base + j] if flip else [ci, base + j, base + j2])
    m = trimesh.Trimesh(V, np.array(F), process=True)
    m.merge_vertices()
    m.update_faces(m.nondegenerate_faces())
    m.remove_unreferenced_vertices()
    trimesh.repair.fix_winding(m)
    trimesh.repair.fix_normals(m)
    if m.volume < 0:
        m.invert()
    return m


def mirrored(m=None) -> trimesh.Trimesh:
    m = build() if m is None else m
    r = m.copy()
    r.vertices = r.vertices * np.array([1, -1, 1])
    r.invert()
    return r


def min_thickness(m, s_lo, s_hi=None, n=200):
    """Min ray thickness (z direction through section interior) for spans in [s_lo,s_hi]."""
    s_hi = s_hi or L - 1.5
    out = []
    for s in np.linspace(s_lo, s_hi, 30):
        c = chord_at(s)
        for u in np.linspace(0.25, 0.75, 5):
            o = P0 + s * SPAN + u * c * CHORD
            o = o + ZH * 6
            hit, _, _ = m.ray.intersects_location([o], [-ZH])
            if len(hit) >= 2:
                zs = np.sort(np.linalg.norm(hit - o, axis=1))
                out.append(zs[-1] - zs[0])
    return min(out) if out else float("nan")


def preview(m, path, extra=None):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(12, 10))
    views = [("top (XY)", 90, -90), ("side (XZ)", 0, -90), ("front (YZ)", 0, 0), ("oblique", 28, -50)]
    meshes = [m] + ([extra] if extra is not None else [])
    for k, (t, el, az) in enumerate(views):
        ax = fig.add_subplot(2, 2, k + 1, projection="3d")
        for mi, mm in enumerate(meshes):
            tri = mm.vertices[mm.faces]
            nrm = mm.face_normals
            sh = 0.35 + 0.65 * np.clip(nrm @ np.array([0.3, 0.3, 0.9]) / 1.0, 0, 1)
            col = np.outer(sh, [0.2, 0.5, 0.9] if mi == 0 else [0.8, 0.5, 0.2])
            pc = Poly3DCollection(tri, facecolors=np.c_[col, np.ones(len(col))], edgecolor="none")
            ax.add_collection3d(pc)
        allv = np.vstack([mm.vertices for mm in meshes])
        mid = (allv.max(0) + allv.min(0)) / 2; r = (allv.max(0) - allv.min(0)).max() / 2 + 1
        ax.set_xlim(mid[0] - r, mid[0] + r); ax.set_ylim(mid[1] - r, mid[1] + r); ax.set_zlim(mid[2] - r, mid[2] + r)
        ax.set_box_aspect((1, 1, 1)); ax.view_init(el, az); ax.set_title(t)
        ax.set_xlabel("x"); ax.set_ylabel("y"); ax.set_zlabel("z")
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


if __name__ == "__main__":
    m = build()
    mr = mirrored(m)
    m.export(os.path.join(HERE, "pelvic.stl"))
    pair = trimesh.util.concatenate([m, mr])
    pair.export(os.path.join(HERE, "pelvic_pair.stl"))
    preview(m, os.path.join(HERE, "pelvic_preview.png"))
    print("watertight", m.is_watertight, "winding", m.is_winding_consistent, "vol", m.volume, "faces", len(m.faces))
    print("bbox", m.bounds.round(2).tolist())
    print("min thickness s=1..30.5:", min_thickness(m, 1, 30.5), " near tip s=24..30:", min_thickness(m, 24, 30))
