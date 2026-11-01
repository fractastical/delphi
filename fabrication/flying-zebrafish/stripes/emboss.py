"""Emboss the Nakamasu-2009 Turing stripe field onto a body mesh (shared frame, see SPEC.md).

    from stripes.emboss import emboss_stripes
    body2 = emboss_stripes(body_mesh)        # raised dark-stripe bands, 0.15 mm

Only lateral flank faces behind the head (x in [x_front, x_back]) are displaced, along the vertex normal,
where the melanophore field u is high (the dark stripes). Fins and wings should be unioned AFTER embossing.
"""
from pathlib import Path
import numpy as np
import trimesh

FIELD = Path(__file__).parent / "stripes_u.npz"


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def emboss_stripes(mesh, height=0.15, x_front=-24.0, x_back=-78.0, max_edge=0.6, lateral_min=0.45,
                   field=FIELD, verbose=True):
    d = np.load(field)
    u = d["u"]                      # rows: dorsal -> ventral (0 = dorsal), cols: anterior -> posterior
    ny, nx = u.shape
    m = mesh.copy()
    v, f = trimesh.remesh.subdivide_to_size(m.vertices, m.faces, max_edge=max_edge)
    m = trimesh.Trimesh(v, f, process=True)
    m.fix_normals()
    V, N = m.vertices, m.vertex_normals

    # local dorsal/ventral extent per x bin (from the mesh itself)
    bins = np.linspace(x_back, x_front, 80)
    idx = np.digitize(V[:, 0], bins)
    zmax = np.full(len(bins) + 1, np.nan); zmin = zmax.copy()
    for i in range(len(bins) + 1):
        s = V[idx == i, 2]
        if len(s):
            zmax[i], zmin[i] = s.max(), s.min()
    ok = ~np.isnan(zmax)
    xc = np.concatenate([[bins[0] - (bins[1] - bins[0])], bins])[ok[: len(bins) + 1]] if False else None
    # interpolate over bin centres
    centres = 0.5 * (np.concatenate([[bins[0]], bins]) + np.concatenate([bins, [bins[-1]]]))
    good = ok & ~np.isnan(zmax)
    zt = np.interp(V[:, 0], centres[good], zmax[good])
    zb = np.interp(V[:, 0], centres[good], zmin[good])

    # flank coordinates: fx 0..1 front->back, fy 0..1 dorsal->ventral (inset 6% so stripes avoid the ridge/keel)
    fx = (x_front - V[:, 0]) / (x_front - x_back)
    fy = (zt - V[:, 2]) / np.maximum(zt - zb, 1e-6)
    inset = (fy > 0.08) & (fy < 0.92)
    sel = (fx > 0.0) & (fx < 1.0) & inset & (np.abs(N[:, 1]) > lateral_min)
    col = np.clip((fx * (nx - 1)).astype(int), 0, nx - 1)
    row = np.clip((fy * (ny - 1)).astype(int), 0, ny - 1)
    h = _smooth((u[row, col] - 1.0) / 0.35) * height
    # fade out near the ends of the flank patch so there is no cliff
    fade = _smooth(fx / 0.06) * _smooth((1 - fx) / 0.06)
    disp = np.where(sel, h * fade, 0.0)
    m.vertices = V + N * disp[:, None]
    if verbose:
        print(f"emboss: {sel.sum()} / {len(V)} verts on flank, max disp {disp.max():.3f} mm, "
              f"watertight={m.is_watertight}")
    return m


if __name__ == "__main__":
    # self-test on a stand-in fish-shaped ellipsoid, 80 x 19 x 10 mm
    sph = trimesh.creation.icosphere(subdivisions=5)
    sph.apply_scale([40, 5, 9.5]); sph.apply_translation([-40, 0, 0])
    out = emboss_stripes(sph)
    out.export(Path(__file__).parent / "emboss_selftest.stl")
