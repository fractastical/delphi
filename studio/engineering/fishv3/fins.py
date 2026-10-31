"""Ray-fan fins: a fan of tapered fin rays (lepidotrichia) joined by a thin membrane.  Geometry only.

A fin is laid out in its own plane, (u, w) in mm: u is outward from the fin base, w is along the base (aft for
paired fins and the caudal, aft for median fins).  Each ray i has a root on the base, a direction angle alpha_i
(degrees from +u towards +w) and a length L_i.  The membrane is the polygon base -> ray tips, with its margin
between neighbouring tips drawn in by `margin_inset` (a scalloped edge).  Branched rays split once at
`branch_at` of their length into two daughters.  An optional camber bends the fin out of its plane.

What is sourced and what is assumed is decided by the caller (engineering.fishv3.build), not here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import manifold3d as mf
import numpy as np


@dataclass
class Fan:
    roots: np.ndarray          # (n, 2) ray roots (u, w), mm
    alpha_deg: np.ndarray      # (n,) ray directions, degrees from +u towards +w
    lengths: np.ndarray        # (n,) ray lengths, mm
    branched: np.ndarray       # (n,) bool
    membrane_mm: float
    ray_root_radius_mm: float
    ray_tip_radius_mm: float
    ray_radius_scale: np.ndarray | None = None  # (n,) per-ray multiplier (e.g. a stiffened lobe)
    branch_at: float = 0.55
    branch_half_angle_frac: float = 0.25        # daughters at +/- this fraction of the gap to the next ray
    margin_inset: float = 0.08                  # margin between tips drawn in by this fraction of the tip gap
    camber: float = 0.0                         # max out-of-plane offset / local ray length

    def dirs(self) -> np.ndarray:
        a = np.radians(self.alpha_deg)
        return np.stack([np.cos(a), np.sin(a)], axis=1)

    def tips(self) -> np.ndarray:
        return self.roots + self.lengths[:, None] * self.dirs()

    def outline(self) -> np.ndarray:
        """Membrane polygon (u, w), counter-clockwise: last root -> ... -> first root along the base, then the tips."""
        T = self.tips()
        pts = [self.roots[0]]
        for i in range(len(T)):
            pts.append(T[i])
            if i + 1 < len(T):
                mid = 0.5 * (T[i] + T[i + 1])
                centre = 0.5 * (self.roots[i] + self.roots[i + 1])
                pts.append(mid + self.margin_inset * (centre - mid) * np.linalg.norm(T[i + 1] - T[i])
                           / max(np.linalg.norm(centre - mid), 1e-9))
        pts.append(self.roots[-1])
        P = np.array(pts)
        return P if signed_area(P) > 0 else P[::-1]

    def area_mm2(self) -> float:
        return abs(signed_area(self.outline()))

    def ray_polylines(self) -> list[dict]:
        """Each ray as polylines in the fin plane (main segment, then daughters if branched), with its
        tributary membrane width (fan area shared by the ray / its length)."""
        D, T = self.dirs(), self.tips()
        n = len(T)
        out = []
        for i in range(n):
            segs = []
            if self.branched[i] and n > 1:
                b = self.roots[i] + self.branch_at * self.lengths[i] * D[i]
                gap = self.alpha_deg[min(i + 1, n - 1)] - self.alpha_deg[max(i - 1, 0)]
                d = self.branch_half_angle_frac * 0.5 * gap
                rest = (1 - self.branch_at) * self.lengths[i]
                segs.append([self.roots[i], b])
                for s in (-1, 1):
                    a = math.radians(self.alpha_deg[i] + s * d)
                    segs.append([b, b + rest * np.array([math.cos(a), math.sin(a)])])
            else:
                segs.append([self.roots[i], T[i]])
            out.append({"index": i, "branched": bool(self.branched[i]), "length_mm": float(self.lengths[i]),
                        "segments_uw_mm": [[list(map(float, p)) for p in sg] for sg in segs]})
        # tributary area: half of each neighbouring inter-ray triangle pair
        tri = [abs(signed_area(np.array([self.roots[i], T[i], T[i + 1], self.roots[i + 1]]))) for i in range(n - 1)]
        for i in range(n):
            a = 0.5 * (tri[i - 1] if i > 0 else 0) + 0.5 * (tri[i] if i < n - 1 else 0)
            out[i]["tributary_area_mm2"] = a
            out[i]["tributary_width_mm"] = a / self.lengths[i]
        return out

    def warp_fn(self):
        """(u, w, z) -> (u, w, z + camber offset).  The offset is zero at the base and the leading/trailing rays and
        grows with distance from the base: z += camber * r * 4 xi (1 - xi), xi the angular position in the fan."""
        if not self.camber:
            return None
        a0, a1 = math.radians(self.alpha_deg[0]), math.radians(self.alpha_deg[-1])
        o = self.roots.mean(axis=0)
        cam = self.camber

        def f(P):
            P = np.array(P, dtype=float, copy=True)
            du, dw = P[:, 0] - o[0], P[:, 1] - o[1]
            r = np.hypot(du, dw)
            xi = np.clip((np.arctan2(dw, du) - a0) / (a1 - a0), 0, 1)
            P[:, 2] += cam * r * 4 * xi * (1 - xi)
            return P
        return f

    def solid(self, circular: int = 10, refine_mm: float = 1.5) -> mf.Manifold:
        """Membrane slab (thickness membrane_mm, centred on z = 0) united with the rays (tapered capsules)."""
        cs = mf.CrossSection([self.outline().tolist()], mf.FillRule.Positive)
        mem = mf.Manifold.extrude(cs, self.membrane_mm).translate((0, 0, -0.5 * self.membrane_mm))
        parts = [mem]
        scale = self.ray_radius_scale if self.ray_radius_scale is not None else np.ones(len(self.lengths))
        for ray in self.ray_polylines():
            i, L = ray["index"], ray["length_mm"]
            r_root, r_tip = scale[i] * self.ray_root_radius_mm, scale[i] * self.ray_tip_radius_mm
            for seg in ray["segments_uw_mm"]:
                p0, p1 = np.array(seg[0]), np.array(seg[1])
                f0 = np.linalg.norm(p0 - self.roots[i]) / L
                f1 = min(np.linalg.norm(p1 - self.roots[i]) / L, 1.0)
                r0, r1 = r_root + (r_tip - r_root) * f0, r_root + (r_tip - r_root) * f1
                s0 = mf.Manifold.sphere(r0, circular).translate((float(p0[0]), float(p0[1]), 0.0))
                s1 = mf.Manifold.sphere(r1, circular).translate((float(p1[0]), float(p1[1]), 0.0))
                parts.append(mf.Manifold.batch_hull([s0, s1]))
        # refined so a camber warp bends smoothly and per-vertex appearance colours resolve on the membrane
        m = mf.Manifold.batch_boolean(parts, mf.OpType.Add).refine_to_length(refine_mm)
        f = self.warp_fn()
        return m.warp_batch(f) if f is not None else m


def signed_area(P: np.ndarray) -> float:
    x, y = P[:, 0], P[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


def paired_lengths(n: int, L_max: float, lead_frac: float, peak_at: float, trail_frac: float) -> np.ndarray:
    """Ray lengths across a paired fin, leading (i = 0) to trailing: lead_frac L_max at the first ray, rising
    linearly to L_max at fractional position peak_at, then falling along a cosine to trail_frac L_max."""
    x = np.linspace(0, 1, n)
    up = lead_frac + (1 - lead_frac) * np.clip(x / max(peak_at, 1e-9), 0, 1)
    t = np.clip((x - peak_at) / max(1 - peak_at, 1e-9), 0, 1)
    down = trail_frac + (1 - trail_frac) * 0.5 * (1 + np.cos(np.pi * t))
    return L_max * np.where(x <= peak_at, up, down)


def solve_spread(make, target_area: float, lo: float = 5.0, hi: float = 170.0) -> tuple[float, Fan]:
    """Fan spread angle (deg) at which make(spread).area_mm2() == target (bisection; area grows with spread)."""
    if make(hi).area_mm2() < target_area:
        raise ValueError(f"target area {target_area:.1f} mm2 not reachable with spread <= {hi} deg")
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if make(mid).area_mm2() < target_area:
            lo = mid
        else:
            hi = mid
    s = 0.5 * (lo + hi)
    return s, make(s)


def place(m: mf.Manifold, origin, e_u, e_w, e_n) -> mf.Manifold:
    """Map fin-plane coordinates (u, w, n) to the fish frame: X = origin + u e_u + w e_w + n e_n."""
    R = np.column_stack([e_u, e_w, e_n])
    o = np.asarray(origin, float)
    return m.transform([[*R[0], o[0]], [*R[1], o[1]], [*R[2], o[2]]])


def to_fish(points_uw, origin, e_u, e_w, e_n, warp=None) -> np.ndarray:
    P = np.asarray(points_uw, float)
    P3 = np.column_stack([P, np.zeros(len(P))])
    if warp is not None:
        P3 = warp(P3)
    R = np.column_stack([e_u, e_w, e_n])
    return np.asarray(origin, float) + P3 @ R.T
