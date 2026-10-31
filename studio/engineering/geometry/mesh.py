"""Parametric printable solids built from a design JSON, using manifold3d for every boolean.

Two coordinate systems never mix:
  * biological design values are SI (m, m^2, kg) and live in the design JSON;
  * the prop is built in millimetres: prop_mm = biological_m * 1000 * display_scale.
Print-only additions (fin plate thickness, minimum feature radius, stand) are in prop millimetres and are not
scaled from biology.  Axes: x from snout (0) toward the tail, y to the fish's left (+), z up.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import manifold3d as mf
import numpy as np


@dataclass(frozen=True)
class Resolution:
    stations: int = 72  # body loft stations along x
    ring: int = 48  # vertices per body cross-section
    span_pts: int = 48  # samples per fin edge
    circular: int = 32  # segments for rounded offsets


def _manifold_from(verts: np.ndarray, tris: np.ndarray) -> mf.Manifold:
    m = mf.Manifold(mf.Mesh(vert_properties=np.ascontiguousarray(verts, dtype=np.float32),
                            tri_verts=np.ascontiguousarray(tris, dtype=np.uint32)))
    if m.status() != mf.Error.NoError:
        raise ValueError(f"loft is not a valid manifold: {m.status()}")
    return m


_S_MAX = 0.5 / 1.4  # argmax of sqrt(s) (1 - s)^0.9
_G_MAX = math.sqrt(_S_MAX) * (1 - _S_MAX) ** 0.9


def body_profile(s: np.ndarray, peduncle: float) -> np.ndarray:
    """Normalised fusiform half-size along the body, 0 at the snout, `peduncle` at the caudal base.  Pointwise:
    the value at s does not depend on which other points are evaluated with it."""
    g = np.sqrt(np.clip(s, 0, 1)) * (1 - np.clip(s, 0, 1)) ** 0.9 / _G_MAX
    return (1 - peduncle) * g + peduncle * np.clip(s, 0, 1) ** 2


def body_profile_v1(s: np.ndarray, peduncle: float) -> np.ndarray:
    """FROZEN DEFECT, kept only so the published print sets (morphology-v1, nca-comparison-v1) rebuild byte for
    byte.  It normalises by the maximum of its INPUT, so a single-point call returns ~(1 - peduncle) + peduncle s^2
    (near full width) wherever it is evaluated: +3% at the pectoral root (s 0.27), +11% at the pelvic root (s 0.55),
    up to +98% near the tail.  Arrays that span the body's maximum (the loft stations) are nearly unaffected.
    New geometry must use body_profile."""
    g = np.sqrt(np.clip(s, 0, 1)) * (1 - np.clip(s, 0, 1)) ** 0.9
    g = g / g.max()
    return (1 - peduncle) * g + peduncle * np.clip(s, 0, 1) ** 2


def loft(xs, half_w, half_h_up, half_h_down, z_axis, ring: int, nose_x=None, tail_x=None) -> mf.Manifold:
    """Closed loft of elliptical (optionally ventrally flattened) sections.  Each end is closed by a single
    apex vertex, so the mesh is a genus-0 manifold by construction; orientation is fixed by signed volume."""
    th = np.linspace(0, 2 * np.pi, ring, endpoint=False)
    rings = []
    for x, w, hu, hd, z in zip(xs, half_w, half_h_up, half_h_down, z_axis):
        h = np.where(np.sin(th) >= 0, hu, hd)
        rings.append(np.stack([np.full(ring, x), w * np.cos(th), z + h * np.sin(th)], axis=1))
    V = np.concatenate(rings + [np.array([[nose_x if nose_x is not None else xs[0], 0, z_axis[0]]]),
                                np.array([[tail_x if tail_x is not None else xs[-1], 0, z_axis[-1]]])])
    n, k = len(xs), ring
    nose, tail = n * k, n * k + 1
    T = []
    for i in range(n - 1):
        for j in range(k):
            a, b = i * k + j, i * k + (j + 1) % k
            c, d = (i + 1) * k + (j + 1) % k, (i + 1) * k + j
            T += [(a, b, c), (a, c, d)]
    for j in range(k):
        T.append((nose, (j + 1) % k, j))
        T.append((tail, (n - 1) * k + j, (n - 1) * k + (j + 1) % k))
    T = np.array(T)
    tri = V[T]
    vol = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6
    if vol < 0:
        T = T[:, ::-1]
    return _manifold_from(V, T)


def open_polygon(pts_xy: np.ndarray, r: float, circular: int) -> mf.CrossSection:
    """Morphological opening: removes in-plane slivers narrower than 2r (rounded tips, no knife edges)."""
    cs = mf.CrossSection([pts_xy.tolist()], mf.FillRule.Positive)
    if cs.area() <= 0:
        cs = mf.CrossSection([pts_xy[::-1].tolist()], mf.FillRule.Positive)
    return cs.offset(-r, mf.JoinType.Round, 2.0, circular).offset(r, mf.JoinType.Round, 2.0, circular)


def plate(cs: mf.CrossSection, thickness: float) -> mf.Manifold:
    """Extrude a planform (in its XY plane) to a solid plate centred on z = 0."""
    return mf.Manifold.extrude(cs, thickness).translate((0, 0, -thickness / 2))


def fin_chord(s: np.ndarray, base_frac: float, s_max: float) -> np.ndarray:
    """Chord / max chord along the exposed span: narrow fan base, widest at s_max, elliptical outer part."""
    inner = base_frac + (1 - base_frac) * np.sin(0.5 * np.pi * np.clip(s / s_max, 0, 1))
    outer = np.sqrt(np.clip(1 - ((s - s_max) / (1 - s_max)) ** 2, 0, 1))
    return np.where(s <= s_max, inner, outer)


def fin_planform(span_len: float, c_max: float, base_frac: float, s_max: float, sweep_deg: float,
                 root_inset: float, n: int, c_min: float = 0.0) -> np.ndarray:
    """Planform polygon in fin-local (v = chordwise aft, u = spanwise out) coordinates, u = 0 at the body
    surface.  The root is extended `root_inset` into the body so the boolean union overlaps solidly.  `c_min`
    (print-only) keeps the inner fin wide enough to survive the opening, so the fin stays attached."""
    s = np.linspace(0, 1, n)
    c = c_max * fin_chord(s, base_frac, s_max)
    c = np.where(s <= s_max, np.maximum(c, c_min), c)
    le = s * span_len * math.tan(math.radians(sweep_deg))
    u = s * span_len
    c_root = c[0]
    lead = [(le[0], -root_inset)] + list(zip(le, u))
    trail = list(zip(le + c, u))[::-1] + [(le[0] + c_root, -root_inset)]
    return np.array(lead + trail)  # (v, u)


def exposed_area(cs: mf.CrossSection, big: float) -> float:
    """Area of the planform at u >= 0 (outside the body), the part Fish measured."""
    clip = mf.CrossSection.square((big, big)).translate((-big / 2, 0))
    return (cs ^ clip).area()


def place_fin(cs_vu: mf.CrossSection, thickness: float, x_le: float, y_root: float, z_root: float,
              dihedral_deg: float, side: int) -> mf.Manifold:
    """Map a (v, u) planform to world: v -> +x, u -> outward y; tilt by dihedral about the root line."""
    p = plate(cs_vu, thickness)  # x = v, y = u, z = thickness
    p = p.rotate((dihedral_deg, 0, 0))  # tilts +u upward for positive dihedral
    p = p.translate((x_le, y_root, z_root))
    if side < 0:
        p = p.mirror((0, 1, 0))
    return p


def attached(cs: mf.CrossSection, big: float) -> mf.CrossSection:
    """Keep only the planform pieces that reach the root (u < 0, inside the body); an island would print as a
    loose part."""
    root = mf.CrossSection.square((big, big)).translate((-big / 2, -big))
    keep = [p for p in cs.decompose() if not (p ^ root).is_empty()]
    return mf.CrossSection.batch_boolean(keep, mf.OpType.Add) if keep else mf.CrossSection()


def solve_cmax(target_area: float, span_len: float, base_frac: float, s_max: float, sweep: float,
               inset: float, r_open: float, res: Resolution) -> tuple[float, mf.CrossSection, float]:
    """Max chord such that the OPENED, root-attached, exposed planform has the target area (bisection; the area
    is monotone in the chord).  If even the narrowest printable fin exceeds the target, that fin is returned and
    the caller records the print-only area exaggeration."""
    big = 10 * (span_len + 1)
    c_min = 2.5 * r_open

    def opened(cc):
        raw = fin_planform(span_len, cc, base_frac, s_max, sweep, inset, res.span_pts, c_min)
        cs = attached(open_polygon(raw, r_open, res.circular), big)
        return cs, exposed_area(cs, big)
    lo, hi = 0.0, max(target_area / (span_len * 0.5), c_min)
    while opened(hi)[1] < target_area:
        hi *= 1.5
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if opened(mid)[1] < target_area:
            lo = mid
        else:
            hi = mid
    cs, a = opened(hi)
    return hi, cs, a


def caudal_planform(x0: float, ped_half: float, upper_len: float, lower_len: float, angle_deg: float,
                    notch: float) -> np.ndarray:
    """Forked caudal fin in (x, z): peduncle edge at x0, epicaudal (upper) and hypocaudal (lower) lobes."""
    a = math.radians(angle_deg)
    return np.array([(x0, ped_half), (x0 + upper_len * math.cos(a), upper_len * math.sin(a)),
                     (x0 + notch, 0.0),
                     (x0 + lower_len * math.cos(a), -lower_len * math.sin(a)), (x0, -ped_half)])


def lobe_areas(poly: np.ndarray) -> tuple[float, float]:
    def shoelace(p):
        x, y = p[:, 0], p[:, 1]
        return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    x0 = poly[0, 0]
    up = np.array([(x0, 0), poly[0], poly[1], poly[2]])
    lo = np.array([(x0, 0), poly[2], poly[3], poly[4]])
    return shoelace(up), shoelace(lo)


def solve_lobe(target: float, other_len: float, which: str, x0, ped, angle, notch_frac) -> float:
    lo_, hi_ = 1e-6, 50 * math.sqrt(target) + 1
    for _ in range(80):
        mid = 0.5 * (lo_ + hi_)
        if which == "upper":
            p = caudal_planform(x0, ped, mid, other_len, angle, notch_frac * mid)
            a = lobe_areas(p)[0]
        else:
            p = caudal_planform(x0, ped, other_len, mid, angle, notch_frac * other_len)
            a = lobe_areas(p)[1]
        lo_, hi_ = (mid, hi_) if a < target else (lo_, mid)
    return 0.5 * (lo_ + hi_)


def xz_plate(poly_xz: np.ndarray, thickness: float, r_open: float, circular: int) -> tuple[mf.Manifold, float]:
    """A vertical fin: planform in (x, z), thickness along y."""
    cs = open_polygon(poly_xz, r_open, circular)
    p = plate(cs, thickness).rotate((90, 0, 0))  # (x, y, z) -> (x, -z, y): planform y becomes world z
    return p, cs.area()
