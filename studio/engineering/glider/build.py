"""Launch-prototype glider fish: printable parts at 1:1 from the v3a ray-fan fish, with measured mass properties.

LAUNCH PROTOTYPE, UNTESTED.  Nothing here has been printed, weighed, glided or thrown, and no printer or resin
compatibility is claimed.  Every number that is not read from a mesh is a provisional default, labelled as such.

What it builds (per revision, never overwriting an earlier one):
- body: a hollow shell of the v3a body loft with the dorsal, anal and caudal fins integral; a forward ballast bay
  with a ventral port; a lined transverse catch slot for the launch band; one socket per paired fin; drain holes.
- four removable paired fins (pectoral L/R, pelvic L/R), laid flat for printing: a thin membrane, a root doubler,
  a leading-edge spar under ray 0, ridges under the other rays, and a keyed root tongue.  Pelvic fins come at
  several incidence keys (the trim knob).
- mass, CG and inertia per part and assembled (divergence theorem, engineering.glider.mass), a ballast table for
  the CG window, the checks each part passes, and a flight_model.json for the trim/dynamics owner.

Frame (the v3 frame): mm, x from the snout tip towards the tail, z dorsal, y towards the side v3 names "_L".  The
triple is an ordinary right-handed Cartesian set.  With the snout facing -x and the back +z, +y is the fish's
ANATOMICAL RIGHT, so v3's "_L" suffix names the anatomical right side.  Part ids keep v3's suffixes.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import subprocess
import sys
from pathlib import Path

import manifold3d as mf
import numpy as np

from engineering.fish3d import build as B1
from engineering.fishv3 import build as V3
from engineering.fishv3 import fins as FN
from engineering.geometry import mesh as M
from engineering.geometry import validate as VAL
from engineering.glider import mass as MP

ROOT = Path(__file__).resolve().parents[2]
SOURCE_VARIANT = "a-fan"
SCHEMA = "frontier.glider.revision/1"
LABEL = ("LAUNCH PROTOTYPE, UNTESTED: not printed, weighed, glided or thrown; printer and resin compatibility not "
         "claimed; all non-mesh numbers are provisional defaults.")
MAY_NOT_SAY = ["flight-tested", "flightworthy", "validated structure", "ready to print on a named printer",
               "compatible with Form Studio 1", "tested print", "range achieved", "bioprint", "living"]
NOT_CHECKED = ["physical print", "slicing, supports, cupping and peel forces (PreForm's job)", "printed mass",
               "fin stiffness or strength (claude-07's beam check reads these bytes)", "fit of tongue in socket",
               "aerodynamics beyond the hand estimates named in the manifest", "impact survival", "any flight"]

# Root's material card (integration branch, data/materials/formlabs-studio-2026-10-31.json @ f1796ec): read there,
# copied here as a provisional default because this branch predates the card.
MATERIAL = {"id": "alpha-grey-v1-default-post-cure", "density_kg_m3": 1220.0, "flexural_modulus_Pa": 2.08e9,
            "ultimate_tensile_strength_Pa": 43e6, "status": "manufacturer-reported (default post-cure), provisional "
            "scenario resin; printer, cartridge and cure hardware unconfirmed",
            "source": "data/materials/formlabs-studio-2026-10-31.json @ f1796ec (root), Formlabs Alpha Grey V1 TDS"}
PRINTER = {"assumed": "Form Studio 1", "status": "assumed by root; compatibility NOT claimed",
           "build_envelope_mm": [200.0, 125.0, 235.0], "envelope_status": "confirmed by root",
           "margin_mm_per_side": 5.0, "margin_status": "assumed allowance for supports and raft"}

COMMON = {
    "scale": {"value": 1.0, "status": "root's provisional default (not user-confirmed)"},
    "fin_construction": {"value": "printed membrane + printed ridges (option A)",
                         "status": "root's provisional default (not user-confirmed)"},
    "membrane_mm": {"value": 0.5, "status": "claude-07 R1/R2 recommendation (provisional)"},
    "root_doubler": {"value": {"thickness_mm": 1.2, "full_to_u_mm": 12.0, "taper_end_u_mm": 16.0},
                     "status": "claude-07 R1 (provisional)"},
    "pectoral_spar": {"value": {"width_mm": 1.6, "height_mm": 2.0, "tip_height_mm": 1.2, "taper_from": 0.7},
                      "status": "claude-07 R1 recommended section (height = total section depth from the membrane's "
                                "upper face; spar under the membrane)"},
    "pelvic_spar": {"value": {"width_mm": 1.2, "height_mm": 1.2, "tip_height_mm": 1.2, "taper_from": 0.7},
                    "status": "claude-07 R2 (provisional)"},
    "ridge": {"value": {"width_mm": 0.8, "height_mm": 1.0}, "status": "claude-07 R1: other rays as ridges >= 0.8 "
                                                                     "mm deep; 1.0 total chosen (provisional)"},
    "ridge_fillet_mm": {"value": 1.0, "status": "claude-07 R1: r >= 1.0 where a ridge meets the membrane; built as "
                                                "a straight taper (chamfer-like), not a true radius"},
    "median_ridge": {"value": {"width_mm": 0.8, "height_mm": 0.9}, "status": "assumed: centred ridges on the "
                                                                             "dorsal, anal and caudal fins"},
    "tongue": {"value": {"pectoral": {"thickness_mm": 2.0, "length_mm": 10.0, "depth_mm": 6.0, "out_mm": 4.0},
                         "pelvic": {"thickness_mm": 2.0, "length_mm": 6.0, "depth_mm": 6.0, "out_mm": 4.0}},
               "status": "claude-07 R1: keyed tongue >= 2 mm thick, >= 6 mm engagement (provisional)"},
    "socket_clearance_mm": {"value": 0.10, "status": "assumed per side; printer tolerance unknown; glue advised"},
    "socket_boss_wall_mm": {"value": 2.0, "status": "assumed"},
    "root_fairing": {"value": {"wall_mm": 1.2, "out_mm": 2.5}, "status": "assumed: a block round each socket mouth, "
                                                                        "proud of the body (manufacturing alteration)"},
    "fin_body_clearance_mm": {"value": 0.15, "status": "assumed gap between a removable fin's root edge and the body"},
    "pectoral_incidence_deg": {"value": 2.0, "status": "assumed; leading edge up, about the fin's span axis"},
    "decalage_keys_deg": {"value": [-1.0, 0.0, 1.0, 2.0, 3.0, 4.0],
                          "status": "claude-07 §1.3: keys at -1..4 deg; pelvic incidence = pectoral - decalage"},
    "default_decalage_deg": {"value": 2.0, "status": "assumed nominal key for the assembled model"},
    "catch": {"value": {"x_mm": 28.0, "below_cg_mm": 1.5, "slot_mm": 3.5, "rake_deg": 30.0, "liner_mm": 2.0},
              "status": "claude-07 R3: x 17-32 mm, seat 0.5-2.5 mm below the CG, contact radius >= 1.5 mm, "
                        "bulkhead >= 1.5 mm; slot raked so a forward pull seats the band (provisional)"},
    "ballast_bay": {"value": {"x_mm": [6.0, 23.0], "port_diameter_mm": 5.0, "port_x_mm": 14.0},
                    "status": "assumed; port closed with tape or putty after filling"},
    "main_cavity_x_mm": {"value": [24.0, 150.0], "status": "assumed; 1 mm bulkhead behind the bay; the catch liner "
                                                           "is solid inside it; peduncle aft of 150 mm solid for the "
                                                           "caudal"},
    "drain_holes": {"value": {"diameter_mm": 2.5, "x_mm": [60.0, 140.0]},
                    "status": "assumed; ventral; SLA hollow bodies need drains, size not validated"},
    "ballast_bulk_density_g_cm3": {"value": 4.7, "status": "assumed: steel shot set in glue (~60% packing of 7.8)"},
    "cg_window_mm": {"value": [44.0, 60.0], "status": "claude-07 R4: measured CG must be reachable over 44-60 mm"},
    "nominal_cg_target_mm": {"value": 52.0, "status": "claude-07 R4 hand NP bracket 54.5-59.0, SM 10-20% "
                                                      "(provisional; the VLM replaces it)"},
    "min_wall_mm": {"value": 0.45, "status": "provisional rule, sampled: the 0.5 mm design membrane less 0.05 mm "
                                             "for the sampler's float32 resolution; the Form 4 / Grey V5 0.2 mm guide "
                                             "is not taken as evidence for this printer or resin"},
}
REVISIONS = {
    "r1-strong": {"parent": None, "title": "r1 strong: 0.8 mm body shell, reinforced fin roots and spars",
                  "body_wall_mm": {"value": 0.8, "status": "provisional default (conservative)"}},
    "r1-light": {"parent": "r1-strong", "title": "r1 light: as r1-strong with a 0.5 mm body shell",
                 "body_wall_mm": {"value": 0.5, "status": "provisional; first mass-reduction step"}},
    "r2-light": {"parent": "r1-light", "title": "r2 light: r1-light with the adjustable catch claude-07's R3 "
                                                "correction asks for (two slots x four seat heights)",
                 "body_wall_mm": {"value": 0.5, "status": "provisional"},
                 "catch": {"value": {"x_mm": [20.0, 34.0], "seat_offsets_mm": [-1.5, 0.0, 1.5, 3.0], "slot_mm": 3.5,
                                     "rake_deg": 30.0, "liner_mm": 2.0, "plug_clearance_mm": 0.1,
                                     "nominal": {"slot_x_mm": 20.0, "offset_mm": 0.0}},
                           "status": "claude-07 R3 correction: seat at -1.5/0/+1.5/+3.0 mm from the design CG "
                                     "height, two arms ~15 mm apart (25 and 40 mm ahead of a CG near 60 mm); start "
                                     "tests at 0 and +1.5; slot shape, rake and plug fit assumed"},
                 "ballast_bay": {"value": {"x_mm": [6.0, 30.0], "port_diameter_mm": 5.0, "port_x_mm": 11.0},
                                 "status": "assumed; the loft range, clipped behind by the forward slot's axis plane "
                                           "(its liner is the bay's rear wall)"},
                 "main_cavity_x_mm": {"value": [6.0, 150.0], "status": "assumed; the loft range, clipped in front by "
                                                                       "the forward slot's axis plane"}},
    "r3-daane": {"parent": "r2-light", "source_variant": "c-daane-length",
                 "title": "r3 Daane: r2-light built on v3c (Daane/FAO pectoral length, +28% paired-fin area, "
                          "pelvics at 0.48 SL) to raise the area per gram",
                 "body_wall_mm": {"value": 0.5, "status": "provisional"},
                 "catch": {"value": {"x_mm": [20.0, 34.0], "seat_offsets_mm": [-1.5, 0.0, 1.5, 3.0], "slot_mm": 3.5,
                                     "rake_deg": 30.0, "liner_mm": 2.0, "plug_clearance_mm": 0.1,
                                     "nominal": {"slot_x_mm": 20.0, "offset_mm": 0.0}},
                           "status": "claude-07 R3 correction: seat at -1.5/0/+1.5/+3.0 mm from the design CG "
                                     "height, two arms ~15 mm apart (25 and 40 mm ahead of a CG near 60 mm); start "
                                     "tests at 0 and +1.5; slot shape, rake and plug fit assumed"},
                 "ballast_bay": {"value": {"x_mm": [6.0, 30.0], "port_diameter_mm": 5.0, "port_x_mm": 11.0},
                                 "status": "assumed; the loft range, clipped behind by the forward slot's axis plane "
                                           "(its liner is the bay's rear wall)"},
                 "main_cavity_x_mm": {"value": [6.0, 150.0], "status": "assumed; the loft range, clipped in front by "
                                                                       "the forward slot's axis plane"}},
    "r4-daane-printfix": {"parent": "r3-daane", "source_variant": "c-daane-length",
                          "title": "r4 Daane print fix: r3-daane with correct right-hand print files (proper rotation, "
                                   "mirrored right parts); geometry and parameters as r3",
                 "body_wall_mm": {"value": 0.5, "status": "provisional"},
                 "catch": {"value": {"x_mm": [20.0, 34.0], "seat_offsets_mm": [-1.5, 0.0, 1.5, 3.0], "slot_mm": 3.5,
                                     "rake_deg": 30.0, "liner_mm": 2.0, "plug_clearance_mm": 0.1,
                                     "nominal": {"slot_x_mm": 20.0, "offset_mm": 0.0}},
                           "status": "claude-07 R3 correction: seat at -1.5/0/+1.5/+3.0 mm from the design CG "
                                     "height, two arms ~15 mm apart (25 and 40 mm ahead of a CG near 60 mm); start "
                                     "tests at 0 and +1.5; slot shape, rake and plug fit assumed"},
                 "ballast_bay": {"value": {"x_mm": [6.0, 30.0], "port_diameter_mm": 5.0, "port_x_mm": 11.0},
                                 "status": "assumed; the loft range, clipped behind by the forward slot's axis plane "
                                           "(its liner is the bay's rear wall)"},
                 "main_cavity_x_mm": {"value": [6.0, 150.0], "status": "assumed; the loft range, clipped in front by "
                                                                       "the forward slot's axis plane"}},
}
PAIRED = ("pectoral", "pelvic")
RIDGE_INSET_MM = 0.08     # a ridge's top sits this far inside the membrane (no tangent faces in the union)
RIM_OVER_MEMBRANE = 1.3   # outline bead diameter / local slab thickness
OPPOSED_DOT = 0.7         # exit . entry face normals below -this (faces >= 135 deg apart, i.e. a wedge of 45 deg or
#                           less, a feather edge) counts as a wall; a blunter edge's short reading measures the corner
MASS_LIMIT_G = {"value": 10.5, "status": "claude-07 §0: V_trim <= 8 m/s at C_L 0.5 on 52.9 cm2 (hand number)"}


def v(p):
    return p["value"] if isinstance(p, dict) and "value" in p else p


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def code_hash() -> str:
    h = hashlib.sha256()
    for rel in sorted([*(f"engineering/glider/{p.name}" for p in Path(__file__).parent.glob("*.py")),
                       *(f"engineering/fishv3/{p.name}" for p in (ROOT / "engineering/fishv3").glob("*.py")),
                       "engineering/fish3d/build.py", "engineering/geometry/validate.py",
                       "engineering/geometry/mesh.py", "engineering/geometry/forms.py"]):
        h.update(rel.encode() + b"\0" + (ROOT / rel).read_bytes())
    return h.hexdigest()


def wjson(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=float) + "\n")


def source_candidate(variant: str = SOURCE_VARIANT) -> tuple[dict, str]:
    cand = V3.candidate(variant)
    d = ROOT / "artifacts/fish3d" / cand["id"]
    committed = (d / "candidate.json").read_bytes()
    if B1.canon(cand) != committed:
        raise ValueError(f"{cand['id']}: candidate.json differs from what engineering.fishv3 produces")
    return cand, hashlib.sha256(committed).hexdigest()


# ------------------------------------------------------------------ body lofts
def loft_offset(body, delta_mm: float, x0: float, x1: float, n: int = 120, ring: int = 96) -> mf.Manifold:
    """The body loft between x0 and x1 with every half-size moved by delta (positive grows), corrected for the
    profile's slope so the offset is roughly normal to the surface.  Ends are flat (closed by a centre vertex)."""
    xs = np.linspace(x0, x1, n)
    hs = np.array([body.half_sizes(x / body.sl) for x in xs])        # (n, 3): w, hu, hd
    slope = np.gradient(hs, xs, axis=0)
    hs = np.maximum(hs + delta_mm * np.sqrt(1 + slope ** 2), 0.05)
    return M.loft(xs, hs[:, 0], hs[:, 1], hs[:, 2], np.zeros(n), ring)


def frame_matrix(frame) -> np.ndarray:
    o, eu, ew, en = frame
    R = np.column_stack([eu, ew, en])
    return np.vstack([np.column_stack([R, o]), [0, 0, 0, 1]])


def affine(m: mf.Manifold, A: np.ndarray) -> mf.Manifold:
    return m.transform(A[:3, :].tolist())


def mirror_y(A: np.ndarray) -> np.ndarray:
    return np.diag([1.0, -1.0, 1.0, 1.0]) @ A


def right_pose(A_left: np.ndarray) -> np.ndarray:
    """Print-to-fish transform for a right (-y) part whose left twin has print-to-fish A_left.

    The right part is the left part mirrored in y.  Its frame is the mirrored frame with the normal flipped
    (e_u' = M e_u, e_w' = M e_w, e_n' = -M e_n), so the transform is a PROPER rotation (det +1) and the flat print
    of the right part is the left one's mirror image (z -> -z), as a mirror-image part must be.
    Until r4 the exporter used mirror_y(A_left) (det -1): inverting a mirror on mirrored geometry cancels the
    mirror, so every _R print STL of r1-r3 holds the LEFT part's vertices (found by reviewer claude-13 on r1 and by
    root on r3; recorded in artifacts/glider/KNOWN_DEFECTS.json)."""
    return mirror_y(A_left) @ np.diag([1.0, 1.0, -1.0, 1.0])


def box(lo, hi) -> mf.Manifold:
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    return mf.Manifold.cube(tuple(hi - lo)).translate(tuple(lo))


# ------------------------------------------------------------------ fins (in the fin's own frame: u span, w chord, n down)
def ridge(p0, p1, width0, height0, width1, height1, top_n, fillet, clip=None, circular=12) -> mf.Manifold:
    """A ridge along p0 -> p1 (u, w) hanging below the membrane's upper face (n = top_n, n positive down): a rounded
    rod whose top stays RIDGE_INSET_MM inside the membrane (no tangent faces for the union to sliver), plus, when
    fillet > 0, a taper from width + 2 fillet at the membrane's mid-plane down to the rod.  The taper is clipped to
    the membrane outline (`clip`, a prism) so it leaves no flange outside the membrane; the rod is kept whole (the
    leading-edge spar sits on the outline)."""
    rod, taper = [], []
    for (u, w), wd, ht in ((p0, width0, height0), (p1, width1, height1)):
        r = 0.5 * wd
        bottom = mf.Manifold.sphere(r, circular).translate((float(u), float(w), top_n + max(ht - r, r)))
        rod += [bottom, mf.Manifold.sphere(r, circular).translate((float(u), float(w), top_n + r + RIDGE_INSET_MM))]
        taper += [bottom, mf.Manifold.sphere(1.0, circular).scale((r + fillet, r + fillet, 0.02))
                  .translate((float(u), float(w), 0.0))]
    m = mf.Manifold.batch_hull(rod)
    if fillet > 0:
        t = mf.Manifold.batch_hull(taper)
        m = m + (t ^ clip if clip is not None else t)
    return m


def rim(outline: np.ndarray, thickness_at, circular: int = 12, step_mm: float = 0.5) -> mf.Manifold:
    """A rounded bead along the outline, diameter RIM_OVER_MEMBRANE x the local slab thickness (thickness_at(u)), so
    pointed ray tips, scallops and the thicker root doubler's edge have no in-plane sliver or square corner whose
    neighbouring face cuts a wall sample short.  Edges are subdivided where the thickness changes."""
    segs = []
    for a, b in zip(outline, np.roll(outline, -1, axis=0)):
        n = max(1, math.ceil(np.linalg.norm(b - a) / step_mm)) if min(a[0], b[0]) < 20 else 1
        pts = [a + (b - a) * k / n for k in range(n + 1)]
        sph = [mf.Manifold.sphere(0.5 * RIM_OVER_MEMBRANE * thickness_at(q[0]), circular)
               .translate((float(q[0]), float(q[1]), 0.0)) for q in pts]
        segs += [mf.Manifold.batch_hull([s0, s1]) for s0, s1 in itertools.pairwise(sph)]
    return mf.Manifold.batch_boolean(segs, mf.OpType.Add)


def fin_solid(fan: FN.Fan, which: str, p: dict, median: bool) -> tuple[mf.Manifold, list[dict]]:
    """Membrane (with the root doubler as one thickness-graded slab) + rim + spar (paired fins) + ridges, flat,
    centred on n = 0.  Returns the solid and the ridge records (fin-plane polylines and sections)."""
    t = v(p["membrane_mm"])
    outline = fan.outline()
    cs = mf.CrossSection([outline.tolist()], mf.FillRule.Positive)
    prism = mf.Manifold.extrude(cs, 20.0).translate((0, 0, -10.0))
    ridges = []
    tips = fan.tips()
    if median:
        parts = [mf.Manifold.extrude(cs, t).translate((0, 0, -0.5 * t)), rim(outline, lambda u: t)]
        rd = v(p["median_ridge"])
        for i, (r0, tp) in enumerate(zip(fan.roots, tips)):
            d = tp - r0
            L = np.linalg.norm(d)
            p1 = r0 + d * (L - 0.6 * rd["width_mm"]) / L
            parts.append(ridge(r0, p1, rd["width_mm"], rd["height_mm"], rd["width_mm"], rd["height_mm"],
                               -0.5 * rd["height_mm"] - RIDGE_INSET_MM, 0.0))
            ridges.append({"ray": i, "polyline_uw_mm": [r0.tolist(), p1.tolist()], "width_mm": rd["width_mm"],
                           "height_mm": rd["height_mm"], "placement": "centred"})
        return mf.Manifold.batch_boolean(parts, mf.OpType.Add), ridges
    dbl = v(p["root_doubler"])
    t0, u0, u1 = dbl["thickness_mm"], dbl["full_to_u_mm"], dbl["taper_end_u_mm"]

    def graded(P):  # n scaled so the slab is t0 thick out to u0, tapers to t at u1, and is t beyond
        P = np.array(P, float, copy=True)
        k = np.clip((P[:, 0] - u0) / (u1 - u0), 0, 1)
        P[:, 2] *= (t0 - (t0 - t) * k) / t0
        return P
    slab = mf.Manifold.extrude(cs, t0).translate((0, 0, -0.5 * t0)).refine_to_length(0.8).warp_batch(graded)
    parts = [slab, rim(outline, lambda u: t0 - (t0 - t) * min(max((u - u0) / (u1 - u0), 0.0), 1.0))]
    sp, rd, fil = v(p[f"{which}_spar"]), v(p["ridge"]), v(p["ridge_fillet_mm"])
    top = -0.5 * t
    for i, (r0, tp) in enumerate(zip(fan.roots, tips)):
        dvec = tp - r0
        L = np.linalg.norm(dvec)
        if i == 0:
            wd, h0, h1, kf = sp["width_mm"], sp["height_mm"], sp["tip_height_mm"], sp["taper_from"]
            pend = r0 + dvec * (L - 0.5 * wd - fil) / L
            pm = r0 + dvec * kf
            parts.append(ridge(r0, pm, wd, h0, wd, h0, top, fil, prism))
            parts.append(ridge(pm, pend, wd, h0, wd, h1, top, fil, prism))
            ridges.append({"ray": 0, "role": "leading-edge spar", "polyline_uw_mm": [r0.tolist(), pm.tolist(),
                                                                                     pend.tolist()],
                           "width_mm": wd, "height_mm": [h0, h0, h1], "placement": "under the membrane"})
        else:
            wd, h = rd["width_mm"], rd["height_mm"]
            pend = r0 + dvec * (L - 0.5 * wd - fil) / L
            parts.append(ridge(r0, pend, wd, h, wd, h, top, fil, prism))
            ridges.append({"ray": i, "role": "ridge", "polyline_uw_mm": [r0.tolist(), pend.tolist()], "width_mm": wd,
                           "height_mm": h, "placement": "under the membrane"})
    return mf.Manifold.batch_boolean(parts, mf.OpType.Add), ridges


def root_cut(grown: mf.Manifold, A: np.ndarray, n_range) -> mf.Manifold:
    """The body's footprint on the fin plane, extruded along the fin normal: the grown body (in the fin's frame)
    within the fin's thickness band, projected onto the plane.  Cutting with it leaves root faces perpendicular to
    the membrane (no acute wedge where an oblique body surface would meet the fin) and clears the body everywhere
    in the band."""
    local = affine(grown, np.linalg.inv(A)) ^ box((-200, -200, n_range[0]), (200, 200, n_range[1]))
    return mf.Manifold.extrude(local.project(), 20.0).translate((0, 0, -10.0))


def incidence_matrix(fan: FN.Fan, deg: float) -> np.ndarray:
    """Rotation of the fin (not its tongue) about the span axis through the root centre: leading edge up.  In the
    fin frame w is aft and n is down, so w' = wc + dw cos i - n sin i, n' = dw sin i + n cos i."""
    wc = 0.5 * (fan.roots[0, 1] + fan.roots[-1, 1])
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    T = np.eye(4)
    T[1:3, 1:3] = [[c, -s], [s, c]]
    T[1, 3] = wc - c * wc
    T[2, 3] = -s * wc
    return T


def fairing_box(fan: FN.Fan, tg: dict, p: dict, grow: float = 0.0) -> mf.Manifold:
    """A small block round the socket mouth, standing proud of the body: the slot then opens through the block's
    end face, square to the tongue, instead of through an oblique body surface (which left a feather-edge sliver of
    shell beside the pelvic slot).  The fin's root edge is trimmed clear of it."""
    f = v(p["root_fairing"])
    wc = 0.5 * (fan.roots[0, 1] + fan.roots[-1, 1])
    hw = 0.5 * tg["length_mm"] + v(p["socket_clearance_mm"]) + f["wall_mm"] + grow
    hn = 0.5 * tg["thickness_mm"] + v(p["socket_clearance_mm"]) + f["wall_mm"] + grow
    # starts half the tongue's depth inside the body: on the pelvic's lower flank the body surface rises towards the
    # side, and a fairing starting at the surface left 0.2-0.4 mm of shell under the slot just inboard of it
    return box((-0.5 * tg["depth_mm"] - grow, wc - hw, -hn), (f["out_mm"] + grow, wc + hw, hn))


def tongue_box(fan: FN.Fan, tg: dict, grow: float = 0.0, out_extra: float = 0.0) -> mf.Manifold:
    wc = 0.5 * (fan.roots[0, 1] + fan.roots[-1, 1])
    return box((-tg["depth_mm"] - grow, wc - 0.5 * tg["length_mm"] - grow, -0.5 * tg["thickness_mm"] - grow),
               (tg["out_mm"] + grow + out_extra, wc + 0.5 * tg["length_mm"] + grow, 0.5 * tg["thickness_mm"] + grow))


# ------------------------------------------------------------------ assembly
def build(rev: str) -> dict:
    p = {**COMMON, **REVISIONS[rev]}
    cand, csha = source_candidate(REVISIONS[rev].get("source_variant", SOURCE_VARIANT))
    comps, rep, fans, _srec, body = V3.build_components(cand)
    wall = v(p["body_wall_mm"])
    sl = body.sl

    outer = comps["body"]
    # median fins, integral with the body
    median = []
    for cid in ("dorsal", "anal", "caudal"):
        fan, frame, _ = fans[cid]
        solid, rr = fin_solid(fan, cid, p, median=True)
        median.append(affine(solid, frame_matrix(frame)))
        rep[cid]["glider_ridges"] = rr

    cat = v(p["catch"])
    bay = v(p["ballast_bay"])
    cav = v(p["main_cavity_x_mm"])
    # paired-fin geometry, sockets and assembled fin placements
    pr = {}
    tgs = v(p["tongue"])
    clr, bw, fclr = v(p["socket_clearance_mm"]), v(p["socket_boss_wall_mm"]), v(p["fin_body_clearance_mm"])
    grown = loft_offset(body, fclr, 0.0, sl)
    bosses, slots = [], []
    i_pect = v(p["pectoral_incidence_deg"])
    keys = v(p["decalage_keys_deg"])
    for which in PAIRED:
        fan, frame, _ = fans[f"{which}_L"]
        F = frame_matrix(frame)
        tg = tgs[which]
        solid, rr = fin_solid(fan, which, p, median=False)
        settings = [i_pect] if which == "pectoral" else [i_pect - k for k in keys]
        fair = affine(fairing_box(fan, tg, p), F)
        cut_by = grown + affine(fairing_box(fan, tg, p, grow=fclr), F)
        per = {}
        for inc in settings:
            A = F @ incidence_matrix(fan, inc)
            lo, hi = solid.bounding_box()[2], solid.bounding_box()[5]
            fin_fish = affine(solid - root_cut(cut_by, A, (lo - 0.2, hi + 0.2)), A)  # trimmed to body + fairing
            tongue_fish = affine(tongue_box(fan, tg), F)
            part = fin_fish + tongue_fish
            pieces = sorted(part.decompose(), key=lambda q: -q.volume())
            dropped = [q.volume() for q in pieces[1:]]
            if any(d > 1e-3 for d in dropped):
                raise ValueError(f"{which} at {inc} deg: trimmed fin is not one piece: {dropped}")
            per[round(inc, 6)] = {"fish": pieces[0], "dropped_mm3": dropped}
        boss = affine(tongue_box(fan, tg, grow=bw), F)
        slot = affine(tongue_box(fan, tg, grow=clr, out_extra=10.0), F)
        for A in (np.eye(4), np.diag([1.0, -1.0, 1.0, 1.0])):
            bosses.append((affine(boss, A) ^ outer) + affine(fair, A))
            slots.append(affine(slot, A))
        pr[which] = {"fan": fan, "frame": frame, "F": F, "solid_flat": solid, "ridges": rr, "settings": per,
                     "tongue": tg}

    def shell_body(cavities=None):
        cavities = cavities or [loft_offset(body, -wall, bay["x_mm"][0], bay["x_mm"][1]),
                                loft_offset(body, -wall, cav[0], cav[1])]
        shell = mf.Manifold.batch_boolean([outer, *median], mf.OpType.Add) - mf.Manifold.batch_boolean(cavities,
                                                                                                   mf.OpType.Add)
        port = mf.Manifold.cylinder(30.0, 0.5 * bay["port_diameter_mm"], 0.5 * bay["port_diameter_mm"], 32) \
            .translate((bay["port_x_mm"], 0, -30.0))
        drains = [mf.Manifold.cylinder(30.0, 0.5 * v(p["drain_holes"])["diameter_mm"],
                                       0.5 * v(p["drain_holes"])["diameter_mm"], 24).translate((x, 0, -30.0))
                  for x in v(p["drain_holes"])["x_mm"]]
        return shell, [port, *drains]

    r = 0.5 * cat["slot_mm"]
    rk = math.radians(cat["rake_deg"])
    down = np.array([math.sin(rk), -math.cos(rk)])          # along the slot from a seat towards its mouth

    def slot_hull(x, z, rr, length=20.0):
        """Hull of two cylinders along y: the seat circle at (x, z) and one `length` further down the raked axis."""
        cyl = mf.Manifold.cylinder(60.0, rr, rr, 32).rotate((90.0, 0.0, 0.0)).translate((0, 30.0, 0))
        lo = np.array([x, z]) + length * down
        return mf.Manifold.batch_hull([cyl.translate((x, 0, z)), cyl.translate((float(lo[0]), 0, float(lo[1])))])

    def assemble_body(z_catch: float):
        """Fixed catch (r1): one slot whose seat is at (x, z_catch)."""
        low = (cat["x_mm"] + 20 * math.sin(rk), z_catch - 20 * math.cos(rk))
        liner = slot_hull(cat["x_mm"], z_catch, r + cat["liner_mm"]) ^ outer
        shell, holes = shell_body()
        b = mf.Manifold.batch_boolean([shell, liner, *bosses], mf.OpType.Add)
        cut = mf.Manifold.batch_boolean([slot_hull(cat["x_mm"], z_catch, r), *holes, *slots], mf.OpType.Add)
        return b - cut, (low, r)

    def assemble_adjustable(z_ref: float):
        """Adjustable catch (r2 on): one slot per x position, its top seat at the highest offset above z_ref (the
        design CG height); a plug pressed into the slot top lowers the seat to each other offset (the seat moves
        down AND aft along the raked axis).  The band's pull seats the plug against the slot top."""
        offs = sorted(cat["seat_offsets_mm"])
        z_top = z_ref + offs[-1]
        # the forward slot's liner is the bulkhead: the bay is everything ahead of the slot's axis plane less r, the
        # main cavity everything behind it plus r (the liner fills the overlap), so no sealed pocket of resin is left
        # between a flat bulkhead and a raked liner
        nrm = np.array([math.cos(rk), 0.0, math.sin(rk)])   # normal of the slot's axis plane, pointing aft-up
        a0 = np.array([cat["x_mm"][0], 0.0, z_top])

        def half(sign, offset):
            """The half-space n.(p - a0) >= offset (sign > 0) or <= offset (sign < 0), as a 200 mm slab along n."""
            lo = offset if sign > 0 else offset - 200.0
            slab = box((lo, -100, -100), (lo + 200.0, 100, 100))
            # rotating about y by -atan2(n_z, n_x) carries +x onto n
            return slab.rotate((0.0, -math.degrees(math.atan2(nrm[2], nrm[0])), 0.0)).translate(tuple(a0))
        bay_cav = loft_offset(body, -wall, bay["x_mm"][0], bay["x_mm"][1]) ^ half(-1, -r)
        main_cav = loft_offset(body, -wall, cav[0], cav[1]) ^ half(+1, r)
        shell, holes = shell_body([bay_cav, main_cav])
        liners = [slot_hull(x, z_top, r + cat["liner_mm"], 25.0) ^ outer for x in cat["x_mm"]]
        b = mf.Manifold.batch_boolean([shell, *liners, *bosses], mf.OpType.Add)
        cut = mf.Manifold.batch_boolean([*(slot_hull(x, z_top, r, 25.0) for x in cat["x_mm"]), *holes, *slots],
                                        mf.OpType.Add)
        inner = loft_offset(body, -cat["plug_clearance_mm"], 0.0, sl)
        seats, plugs = [], {}
        for x in cat["x_mm"]:
            top = np.array([x, z_top])
            for off in offs:
                d = (offs[-1] - off) / math.cos(rk)
                seat = top + d * down
                seats.append({"slot_x_mm": x, "offset_from_design_cg_z_mm": off, "seat_mm": seat.tolist(),
                              "plug": None if d == 0 else plug_id(x, off)})
                if d > 0:
                    rp = r - cat["plug_clearance_mm"]
                    plug = mf.Manifold.batch_hull([
                        mf.Manifold.cylinder(60.0, rp, rp, 32).rotate((90.0, 0.0, 0.0)).translate((0, 30.0, 0))
                        .translate((float(q[0]), 0, float(q[1]))) for q in (top, seat)]) ^ inner
                    plugs[plug_id(x, off)] = plug
        return b - cut, {"z_top_mm": z_top, "seats": seats, "plugs": plugs, "radius_mm": r, "bay_cavity": bay_cav}

    nominal_dec = v(p["default_decalage_deg"])
    if isinstance(cat["x_mm"], list):
        nom_plug = plug_id(cat["nominal"]["slot_x_mm"], cat["nominal"]["offset_mm"])
        z_ref, z_hist = 0.0, []
        for _ in range(4):  # the seat heights are set from the assembled CG height, which the slots move slightly
            body_part, catch = assemble_adjustable(z_ref)
            parts = assembled_parts(body_part, pr, i_pect, i_pect - nominal_dec)
            if nom_plug in catch["plugs"]:
                parts["catch_plug"] = catch["plugs"][nom_plug]
            props = {k: MP.properties(*arrays(m), MATERIAL["density_kg_m3"]) for k, m in parts.items()}
            cg = MP.combine(list(props.values()))
            z_hist.append(z_ref)
            if abs(cg["cg_mm"][2] - z_ref) < 0.02:
                break
            z_ref = cg["cg_mm"][2]
        return {"rev": rev, "params": p, "cand": cand, "csha": csha, "body": body, "fans": fans, "rep": rep,
                "body_part": body_part, "paired": pr, "parts": parts, "props": props, "dry": cg, "z_catch": z_ref,
                "z_catch_iterations": z_hist, "catch": catch, "outer": outer, "median": median}

    z_catch, z_hist = 0.0, []
    for _ in range(3):  # the catch seat sits a fixed distance below the assembled CG, which the slot moves slightly
        body_part, slot_geom = assemble_body(z_catch)
        parts = assembled_parts(body_part, pr, i_pect, i_pect - nominal_dec)
        props = {k: MP.properties(*arrays(m), MATERIAL["density_kg_m3"]) for k, m in parts.items()}
        cg = MP.combine(list(props.values()))
        z_new = cg["cg_mm"][2] - cat["below_cg_mm"]
        z_hist.append(z_catch)
        if abs(z_new - z_catch) < 0.02:
            break
        z_catch = z_new
    return {"rev": rev, "params": p, "cand": cand, "csha": csha, "body": body, "fans": fans, "rep": rep,
            "body_part": body_part, "paired": pr, "parts": parts, "props": props, "dry": cg, "z_catch": z_catch,
            "z_catch_iterations": z_hist, "slot": slot_geom, "outer": outer, "median": median}


def plug_id(x: float, off: float) -> str:
    return f"catch_plug-x{x:.0f}-dz{off:+.1f}"


def assembled_parts(body_part, pr, i_pect, i_pelv) -> dict:
    out = {"body": body_part}
    for which, inc in (("pectoral", i_pect), ("pelvic", i_pelv)):
        m = pr[which]["settings"][round(inc, 6)]["fish"]
        out[f"{which}_L"] = m
        out[f"{which}_R"] = m.mirror((0, 1, 0))
    return out


def arrays(m: mf.Manifold):
    g = m.to_mesh64()
    V = np.round(np.asarray(g.vert_properties)[:, :3] / 1e-5) * 1e-5 + 0.0
    V, T, _ = VAL.weld_float32(V, np.asarray(g.tri_verts).astype(np.int64))
    return V, T


# ------------------------------------------------------------------ ballast, envelope, hand aero
def ballast_table(g: dict) -> dict:
    p = g["params"]
    bay = v(p["ballast_bay"])
    wall = v(p["body_wall_mm"])
    cavity = g["catch"]["bay_cavity"] if "catch" in g else loft_offset(g["body"], -wall, bay["x_mm"][0], bay["x_mm"][1])
    rho_b = v(p["ballast_bulk_density_g_cm3"])
    dry = g["dry"]
    bay_vol = cavity.volume()

    def fill(mass_g):
        """Ballast packed from the front of the bay: the fill's volume, its centroid, and whether it fits."""
        vol = mass_g / rho_b * 1e3
        if vol <= 0:
            return 0.0, np.array(dry["cg_mm"]), True
        lo, hi = bay["x_mm"][0], bay["x_mm"][1]
        if vol >= bay_vol:
            return vol, centroid(cavity), vol <= bay_vol
        a, b = lo, hi
        for _ in range(40):
            mid = 0.5 * (a + b)
            if (cavity ^ box((lo - 1, -50, -50), (mid, 50, 50))).volume() < vol:
                a = mid
            else:
                b = mid
        return vol, centroid(cavity ^ box((lo - 1, -50, -50), (b, 50, 50))), True

    rows = []
    M0, x0 = dry["mass_g"], dry["cg_mm"][0]
    for xt in np.arange(v(p["cg_window_mm"])[0], v(p["cg_window_mm"])[1] + 1e-9, 1.0):
        if xt >= x0:
            rows.append({"cg_target_x_mm": float(xt), "ballast_g": 0.0, "feasible": False,
                         "note": "target is at or behind the dry CG; nose ballast cannot move the CG aft"})
            continue
        mb, c = 0.0, centroid(cavity)
        for it in range(30):
            if it:
                _, c, _ = fill(mb)
            mb_new = M0 * (x0 - xt) / (xt - c[0])
            if abs(mb_new - mb) < 1e-4:
                break
            mb = mb_new
        vol, c, fits = fill(mb)
        rows.append({"cg_target_x_mm": float(xt), "ballast_g": float(mb), "fill_volume_mm3": float(vol),
                     "fill_centroid_mm": [float(q) for q in c], "feasible": bool(fits and vol <= bay_vol),
                     "total_mass_g": float(M0 + mb)})
    return {"bay_x_mm": bay["x_mm"], "bay_volume_mm3": float(bay_vol), "bulk_density_g_cm3": rho_b,
            "bulk_density_status": p["ballast_bulk_density_g_cm3"]["status"],
            "fill_model": "packed from the front of the bay; point mass at the fill's centroid",
            "step_g": 0.5, "rows": rows,
            "reachable_cg_x_mm": [min((r["cg_target_x_mm"] for r in rows if r["feasible"]), default=None), x0]}


def centroid(m: mf.Manifold) -> np.ndarray:
    V, T = arrays(m)
    return np.array(MP.properties(V, T, 1000.0)["cg_mm"])


def envelope_fit(V: np.ndarray) -> dict:
    size = V.max(axis=0) - V.min(axis=0)
    env = np.array(PRINTER["build_envelope_mm"]) - 2 * PRINTER["margin_mm_per_side"]
    fits = bool(np.all(np.sort(size) <= np.sort(env)))
    return {"size_mm": [float(s) for s in size], "envelope_mm": PRINTER["build_envelope_mm"],
            "margin_mm_per_side": PRINTER["margin_mm_per_side"], "fits_axis_aligned": fits,
            "method": "sorted part extents against sorted envelope minus margins (an axis-permutation fit; a "
                      "tilted print orientation is PreForm's choice)"}


def strip_geometry(fan: FN.Fan, frame, inc_deg: float, side: int, nstrip: int = 200) -> dict:
    """Chord distribution of a flat fin in its plane (strips along u), and its MAC and quarter-chord x in the fish
    frame at zero incidence.  Hand-aero input only."""
    O = fan.outline()
    us = np.linspace(O[:, 0].min(), O[:, 0].max(), nstrip + 1)
    um = 0.5 * (us[1:] + us[:-1])
    du = us[1] - us[0]
    le, te = [], []
    for u in um:
        ws = []
        for a, b in zip(O, np.roll(O, -1, axis=0)):
            if (a[0] - u) * (b[0] - u) <= 0 and a[0] != b[0]:
                ws.append(a[1] + (u - a[0]) * (b[1] - a[1]) / (b[0] - a[0]))
        le.append(min(ws)); te.append(max(ws))
    le, te = np.array(le), np.array(te)
    c = te - le
    S = float((c * du).sum())
    mac = float((c * c * du).sum() / S)
    w_qc = float(((le + 0.25 * c) * c * du).sum() / S)
    o, _eu, ew, _en = frame
    span = float(O[:, 0].max() - O[:, 0].min())
    return {"area_mm2": S, "mac_mm": mac, "quarter_chord_x_mm": float(o[0] + w_qc * ew[0]), "span_in_plane_mm": span,
            "root_chord_mm": float(c[0]), "max_chord_mm": float(c.max())}


def hand_np(g: dict) -> dict:
    """Neutral point bracket by hand (Helmbold lift slopes, declared downwash range, Munk body couple).  Reported
    beside claude-07's R4 bracket; the VLM replaces both."""
    pe = strip_geometry(*g["fans"]["pectoral_L"][:2], 0.0, 1)
    pv = strip_geometry(*g["fans"]["pelvic_L"][:2], 0.0, 1)
    Ve = g["outer"].volume()

    def helm(AR):
        return 2 * math.pi * AR / (2 + math.sqrt(AR * AR + 4))
    b1 = 2 * (pe["span_in_plane_mm"] + g["fans"]["pectoral_L"][1][0][1])
    b2 = 2 * (pv["span_in_plane_mm"] + g["fans"]["pelvic_L"][1][0][1])
    S1, S2 = 2 * pe["area_mm2"], 2 * pv["area_mm2"]
    a1, a2 = helm(b1 * b1 / S1), helm(b2 * b2 / S2)
    out = []
    for de in (0.2, 0.6):
        for k in (0.80, 0.95):
            La = a1 * S1 + a2 * S2 * (1 - de)
            xnp = (a1 * S1 * pe["quarter_chord_x_mm"] + a2 * S2 * (1 - de) * pv["quarter_chord_x_mm"]) / La \
                - 2 * Ve * k / La
            out.append(xnp)
    return {"np_x_mm_bracket": [min(out), max(out)], "pectoral": pe, "pelvic": pv, "body_volume_mm3": Ve,
            "method": "Helmbold slopes on each pair (span incl. body), downwash 0.2-0.6, Munk k2-k1 0.80-0.95; "
                      "hand estimate, not claimed", "pectoral_mac_mm": pe["mac_mm"]}


# ------------------------------------------------------------------ wall check
def wall_samples(V: np.ndarray, T: np.ndarray, rule_mm: float, n: int = 3000, seed: int = 7) -> dict:
    """engineering.geometry.validate's inward-ray wall sampler (same sampling: area-weighted face centroids, seed 7),
    with one addition: each ray's EXIT face normal is recorded, and a reading counts as a wall thickness only when
    the exit face roughly opposes the entry face (normals' dot < -OPPOSED_DOT).  Otherwise the ray left through a
    neighbouring face of an acute edge (a socket opening, the catch slot's mouth, a tapered slab's edge): the short
    distance measures the corner, not a wall, and is reported separately as edge-limited, never dropped."""
    m = mf.Manifold(mf.Mesh(vert_properties=V.astype(np.float32), tri_verts=T.astype(np.uint32)))
    tri = V[T]
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = 0.5 * np.linalg.norm(nrm, axis=1)
    nrm = nrm / np.maximum(2 * area[:, None], 1e-30)
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(T), size=min(n, int((area > 0).sum())), replace=False, p=area / area.sum())
    eps, far = 1e-3, 500.0
    wall, edge, nohit = [], [], []
    for r in idx:
        c = tri[r].mean(axis=0)
        o = c - nrm[r] * eps
        hit = next((h for h in m.ray_cast(tuple(o), tuple(o - nrm[r] * far)) if h.distance * far > 1e-6), None)
        if hit is None:
            nohit.append(c.tolist())
            continue
        d = hit.distance * far + eps
        hn = np.asarray(hit.normal, float)
        hn = hn / max(np.linalg.norm(hn), 1e-30)
        (wall if float(hn @ nrm[r]) < -OPPOSED_DOT else edge).append((d, c.tolist()))
    wd = np.array([w[0] for w in wall])
    thin_edge = sorted((e for e in edge if e[0] < rule_mm), key=lambda q: q[0])
    return {"method": "inward ray from area-weighted face centroids (manifold3d ray_cast); a reading is a wall "
                      f"only when the exit face opposes the entry face (dot < -{OPPOSED_DOT})",
            "samples": len(idx), "seed": seed, "no_hit": len(nohit), "wall_readings": len(wd),
            "wall_min_mm": float(wd.min()) if len(wd) else None,
            "wall_p01_mm": float(np.percentile(wd, 1)) if len(wd) else None,
            "wall_median_mm": float(np.median(wd)) if len(wd) else None,
            "edge_limited_readings": len(edge), "edge_limited_below_rule": len(thin_edge),
            "edge_limited_min_mm": float(thin_edge[0][0]) if thin_edge else None,
            "edge_limited_below_rule_at_mm": [[round(x, 2) for x in e[1]] for e in thin_edge[:20]],
            "raw_min_mm": float(min([w[0] for w in wall] + [e[0] for e in edge])),
            "rule_mm": rule_mm,
            "min_wall_ok": bool(len(wd) and wd.min() >= rule_mm and not nohit),
            "scope": "sampled faces only; a thinner region between samples can be missed"}


# ------------------------------------------------------------------ outputs
def write_stl(path: Path, V, T, header: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(VAL.stl_bytes(V, T, header))
    V2, T2 = VAL.read_stl(path.read_bytes())
    c = VAL.check(V2, T2, None, thickness=False)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path), "roundtrip_ok": c["ok"],
            "mesh_sha256": c["mesh_sha256"]}


def build_rev(rev: str, out_root: Path, render: bool) -> dict:
    g = build(rev)
    p = g["params"]
    out = out_root / rev
    rule = v(p["min_wall_mm"])
    density = MATERIAL["density_kg_m3"]
    files, parts_rec = {}, []

    def emit(pid, m_print, m_fish, kind, A_print_to_fish, extra):
        V, T = arrays(m_print)
        chk = VAL.check(V, T, None, thickness=False)
        wall_chk = wall_samples(V, T, rule)
        rel = f"stl/{pid}.stl"
        st = write_stl(out / rel, V, T, f"glider {rev} {pid} mm LAUNCH PROTOTYPE UNTESTED")
        st["path"] = rel
        Vf, Tf = arrays(m_fish)
        mp = MP.properties(Vf, Tf, density)
        rec = {"id": pid, "kind": kind, "stl": rel, "stl_sha256": st["sha256"], "units": "mm",
               "print_pose": "as written (fins flat: membrane in the XY plane)" if kind == "fin" else
               "fish frame (orient in the slicer)", "print_to_fish_transform": A_print_to_fish.tolist(),
               "validation": {k: chk[k] for k in ("ok", "closed_two_manifold", "consistently_oriented",
                                                  "face_connected_components", "degenerate_triangles",
                                                  "signed_volume_mm3", "genus") if k in chk},
               "wall": wall_chk, "min_wall_ok": wall_chk["min_wall_ok"], "min_wall_rule_mm": rule,
               "envelope": envelope_fit(V), "stl_file": st, "mass_properties": mp, "material": MATERIAL["id"],
               "printed": False, **extra}
        parts_rec.append(rec)
        files[rel] = st["sha256"]
        return rec

    I4 = np.eye(4)
    emit("body", g["body_part"], g["body_part"], "shell", I4,
         {"note": "hollow shell with integral dorsal, anal and caudal fins, ballast bay, catch slot, sockets"})
    nominal = v(p["pectoral_incidence_deg"]) - v(p["default_decalage_deg"])
    for which in PAIRED:
        pr = g["paired"][which]
        F = pr["F"]
        for inc, rec in sorted(pr["settings"].items()):
            Ai = F @ incidence_matrix(pr["fan"], inc)  # print pose: the membrane flat, the tongue tilted by inc
            for side in ("L", "R"):
                A = Ai if side == "L" else right_pose(Ai)
                fish = rec["fish"] if side == "L" else rec["fish"].mirror((0, 1, 0))
                flat = affine(fish, np.linalg.inv(A))
                key = "" if which == "pectoral" else f"-dec{v(p['pectoral_incidence_deg']) - inc:+.0f}"
                emit(f"{which}_{side}{key}", flat, fish, "fin", A,
                     {"incidence_deg": inc, "assembled_nominal": bool(which == "pectoral" or abs(inc - nominal) < 1e-9),
                      "fragments_dropped_mm3": rec["dropped_mm3"]})
    nominal_ids = ["body", "pectoral_L", "pectoral_R",
                   f"pelvic_L-dec{v(p['default_decalage_deg']):+.0f}", f"pelvic_R-dec{v(p['default_decalage_deg']):+.0f}"]
    if "catch" in g:  # adjustable catch: every seat plug is a part; the nominal one is in the nominal assembly
        cat = v(p["catch"])
        nom_plug = plug_id(cat["nominal"]["slot_x_mm"], cat["nominal"]["offset_mm"])
        for pid, plug in sorted(g["catch"]["plugs"].items()):
            emit(pid, plug, plug, "plug", I4, {"assembled_nominal": pid == nom_plug,
                                               "note": "pressed into the top of its catch slot to lower the seat"})
        if nom_plug in g["catch"]["plugs"]:
            nominal_ids.append(nom_plug)
    by_id = {r["id"]: r for r in parts_rec}
    dry = MP.combine([by_id[i]["mass_properties"] for i in nominal_ids])
    # interference of the nominal assembly (fins must not overlap the body)
    asm = g["parts"]
    overlap = {k: float((asm["body"] ^ m).volume()) for k, m in asm.items() if k != "body"}
    ballast = ballast_table({**g, "dry": dry})
    aero = hand_np(g)
    target = v(p["nominal_cg_target_mm"])
    row = min(ballast["rows"], key=lambda r: abs(r["cg_target_x_mm"] - target))
    loaded_mass = dry["mass_g"] + row["ballast_g"]
    S = 2 * aero["pectoral"]["area_mm2"] + 2 * aero["pelvic"]["area_mm2"]

    def vtrim(m_g, CL):
        return math.sqrt(2 * m_g * 1e-3 * 9.81 / (1.225 * S * 1e-6 * CL))
    trim = {"paired_flat_area_mm2": S, "dry_mass_g": dry["mass_g"], "ballasted_mass_g_at_nominal_cg": loaded_mass,
            "v_trim_m_s": {f"CL {cl}": {"dry": vtrim(dry["mass_g"], cl), "ballasted": vtrim(loaded_mass, cl)}
                           for cl in (0.4, 0.5, 0.6)},
            "mass_limit_g": MASS_LIMIT_G, "within_mass_limit": bool(loaded_mass <= v(MASS_LIMIT_G)),
            "mass_for_v_trim_8_m_s_at_CL_0.5_on_this_area_g": 0.5 * 1.225 * 64.0 * 0.5 * S * 1e-6 / 9.81 * 1e3,
            "method": "V = sqrt(2 m g / (rho S C_L)), rho 1.225, S = paired flat area; hand number, not claimed"}
    # catch geometry relative to the CG
    hook = catch_record(g, dry, target) if "catch" in g else None
    seat = [v(p["catch"])["x_mm"], g["z_catch"]] if hook is None else None
    hook = hook or {"seat_mm": seat, "contact_radius_mm": 0.5 * v(p["catch"])["slot_mm"],
            "seat_below_dry_cg_mm": dry["cg_mm"][2] - g["z_catch"],
            "ahead_of_dry_cg_mm": dry["cg_mm"][0] - seat[0], "ahead_of_nominal_target_mm": target - seat[0],
            "slot": {"width_mm": v(p["catch"])["slot_mm"], "rake_deg_from_vertical": v(p["catch"])["rake_deg"],
                     "mouth": "aft and below the seat", "across": "full body width (band loop lies across the body)"},
            "liner_wall_mm": v(p["catch"])["liner_mm"],
            "kinematics": "a forward band pull drives the loop up the slot's aft (bearing) face into the seat; when "
                          "the model outruns the band the loop slides down that face and out of the mouth. This is "
                          "the recessed form of a rear-raked hook; claude-07's D1 should check it.",
            "boss_section": {"what": "liner bearing wall aft of the slot", "thickness_x_mm": v(p["catch"])["liner_mm"],
                             "spans": "the full shell width at the seat; bonded to the shell all round"}}
    contacts = ground_contacts(g, asm)
    manifest = {
        "schema": SCHEMA, "revision": rev, "parent_revision": REVISIONS[rev]["parent"], "title": REVISIONS[rev]["title"],
        "label": LABEL, "may_not_say": MAY_NOT_SAY, "not_checked": NOT_CHECKED,
        "source_candidate": {"id": g["cand"]["id"], "sha256": g["csha"],
                             "path": f"artifacts/fish3d/{g['cand']['id']}/candidate.json"},
        "code_sha256": code_hash(), "builder": "python -m engineering.glider.build", "library_versions": libs(),
        "material": MATERIAL, "printer": PRINTER, "parameters": p, "mass_limit": MASS_LIMIT_G,
        "decisions_provenance": "scale 1:1 and printed fins are ROOT's provisional engineering defaults under the "
                                "user's request for a printable, strong-finned, sling-launched fish; size and material "
                                "are not user-confirmed",
        "frame": {"units": "mm", "x": "snout tip -> tail", "z": "dorsal", "y": "towards the side v3 names _L",
                  "handedness": "right-handed Cartesian; with the snout facing -x and dorsal +z, +y is the fish's "
                                "anatomical RIGHT side, so v3's _L suffix names the anatomical right"},
        "export": {"right_parts": "proper rotation of the mirrored fish-frame part (det +1); the flat print is the "
                                  "left part's mirror image", "print_to_fish_det": "+1 for every part",
                   "fixed_in": "r4-daane-printfix (earlier revisions: artifacts/glider/KNOWN_DEFECTS.json)"},
        "parts": parts_rec, "nominal_assembly": {"parts": nominal_ids, "dry": dry,
                                                 "fin_body_overlap_mm3": overlap},
        "ballast": ballast, "hand_neutral_point": aero, "trim_speed_hand": trim, "launch_catch": hook,
        "ground_contact_points_mm": contacts,
        "biological_constraints": {
            "kept": "v3a outline, ray count, ray roots, angles and lengths, fin positions and dihedral",
            "altered": ["fin thickness: membrane, root doubler, spar, ridges (manufacturing)",
                        "branched rays printed as one straight ridge each", "removable paired fins with root tongues",
                        "paired-fin root edges trimmed to the body contour with a gap",
                        "pectoral incidence and pelvic incidence keys", "hollow body with bay, port, drains",
                        "transverse catch slot under the head", "eyes, gill covers and scales omitted"],
            "outline_check": outline_check(g)},
        "files": files,
    }
    glb = write_glb(out / "web/assembled.glb", asm)
    files["web/assembled.glb"] = glb
    if render:
        from engineering.geometry import render as R
        cols = {"body": (0.62, 0.66, 0.70), "pectoral": (0.35, 0.55, 0.80), "pelvic": (0.80, 0.55, 0.30),
                "catch": (0.85, 0.25, 0.25)}
        (out / "img").mkdir(parents=True, exist_ok=True)
        R.render([(*arrays(m), cols[k.split("_")[0]]) for k, m in asm.items()], out / "img/assembled.png",
                 f"glider {rev}: launch prototype, untested ({dry['mass_g']:.1f} g dry)")
        files["img/assembled.png"] = sha(out / "img/assembled.png")
    flight = flight_model(g, manifest, by_id, nominal_ids, dry, ballast)
    wjson(out / "flight_model.json", flight)
    files["flight_model.json"] = sha(out / "flight_model.json")
    wjson(out / "manifest.json", manifest)
    return manifest


def catch_record(g: dict, dry: dict, target: float) -> dict:
    cat = v(g["params"]["catch"])
    c = g["catch"]
    seats = [{**st, "below_dry_cg_mm": dry["cg_mm"][2] - st["seat_mm"][1],
              "ahead_of_dry_cg_mm": dry["cg_mm"][0] - st["seat_mm"][0],
              "ahead_of_nominal_target_mm": target - st["seat_mm"][0]} for st in c["seats"]]
    return {"adjustable": True, "design_cg_z_mm": g["z_catch"], "slot_top_z_mm": c["z_top_mm"],
            "contact_radius_mm": c["radius_mm"] - cat["plug_clearance_mm"], "seats": seats,
            "nominal": cat["nominal"],
            "slot": {"width_mm": cat["slot_mm"], "rake_deg_from_vertical": cat["rake_deg"], "x_positions_mm": cat["x_mm"],
                     "mouth": "aft and below the seat", "across": "full body width (band loop lies across the body)"},
            "liner_wall_mm": cat["liner_mm"],
            "plugs": "one part per (slot, lower offset); the top offset is the bare slot top; plug clearance "
                     f"{cat['plug_clearance_mm']} mm a side (assumed); retain with tape or a drop of glue",
            "kinematics": "a forward band pull drives the loop up the slot's aft (bearing) face into the seat (the "
                          "slot top or a plug's rounded underside); when the model outruns the band the loop slides "
                          "down that face and out of the mouth. The recessed form of a rear-raked hook; claude-07's "
                          "D1 should check it.",
            "boss_section": {"what": "liner walls round each slot", "thickness_mm": cat["liner_mm"],
                             "spans": "the full shell width; bonded to the shell all round"},
            "record_per_flight": "slot x, seat offset (plug id), ballast, pelvic key"}


def outline_check(g: dict) -> dict:
    """The printed fins' ray layout is v3a's: ray lengths and roots re-read from the committed rays.json."""
    src = json.loads((ROOT / "artifacts/fish3d" / g["cand"]["id"] / "rays.json").read_text())["fins"]
    built = V3.rays_json(g["fans"])
    ok = {fin: bool([r["length_m"] for r in rec["rays"]] == [r["length_m"] for r in built[fin]["rays"]]
                    and np.allclose([r["root_m"] for r in rec["rays"]], [r["root_m"] for r in built[fin]["rays"]],
                                    rtol=0, atol=1e-9)) for fin, rec in src.items()}
    return {"rays_match_committed_rays_json": ok, "all": bool(all(ok.values()))}


def ground_contacts(g: dict, asm: dict) -> dict:
    out = {}
    Vb, _ = arrays(asm["body"])
    out["nose_tip"] = Vb[Vb[:, 0].argmin()].tolist()
    keel = Vb[Vb[:, 0] < 150]
    out["belly_lowest"] = keel[keel[:, 2].argmin()].tolist()
    tail = Vb[Vb[:, 0] > 150]
    out["caudal_lowest"] = tail[tail[:, 2].argmin()].tolist()
    mid = Vb[(Vb[:, 0] > 110) & (Vb[:, 0] < 135)]
    out["anal_lowest"] = mid[mid[:, 2].argmin()].tolist()
    for k in ("pectoral_L", "pectoral_R", "pelvic_L", "pelvic_R"):
        V, _ = arrays(asm[k])
        out[f"{k}_tip"] = V[np.abs(V[:, 1]).argmax()].tolist()
        out[f"{k}_lowest"] = V[V[:, 2].argmin()].tolist()
    return out


def flight_model(g, manifest, by_id, nominal_ids, dry, ballast) -> dict:
    p = g["params"]
    surf = []
    for which in PAIRED:
        pr = g["paired"][which]
        o, eu, ew, en = pr["frame"]
        surf.append({"id": which, "sides": ["L", "R (mirror in y)"], "outline_uw_mm": pr["fan"].outline().tolist(),
                     "frame_L": {"origin_mm": o.tolist(), "e_u": eu.tolist(), "e_w": ew.tolist(), "normal": en.tolist()},
                     "incidence_about_span_axis_deg": sorted(pr["settings"]),
                     "dihedral_deg": float(math.degrees(math.atan2(eu[2], eu[1]))),
                     "camber": "none (flat plate with ridges under the membrane)",
                     "membrane_mm": v(p["membrane_mm"]), "root_doubler": v(p["root_doubler"]), "ridges": pr["ridges"]})

    def si(r):
        mp = r["mass_properties"]
        return {"id": r["id"], "stl": r["stl"], "stl_sha256": r["stl_sha256"], "material": MATERIAL["id"],
                "kind": r["kind"], "volume_m3": mp["volume_m3"], "mass_kg": mp["mass_kg"], "cg_m": mp["cg_m"],
                "inertia_cg_kg_m2": mp["inertia_cg_kg_m2"], "printed": False,
                "print_to_fish_transform_mm": r["print_to_fish_transform"]}
    Vo, To = arrays(g["outer"])
    return {"schema": "frontier.glider.flight-model/1", "revision": manifest["revision"],
            "candidate_sha256": parts_hash(manifest),
            "candidate_sha256_note": "sha256 of the sorted {stl path: sha256} map of this revision's parts",
            "source_candidate_sha256": g["csha"], "builder_code_sha256": manifest["code_sha256"],
            "frame": {**manifest["frame"], "length_unit": "m for SI fields, mm where the key says _mm",
                      "origin": "snout tip of the v3 body loft (x = 0)"},
            "material": {"card_id": MATERIAL["id"], "density_kg_m3": MATERIAL["density_kg_m3"],
                         "source": MATERIAL["source"], "status": MATERIAL["status"]},
            "parts": [si(by_id[i]) for i in nominal_ids],
            "spare_parts": [si(r) for r in manifest["parts"] if r["id"] not in nominal_ids],
            "non_mesh": [{"id": "adhesive", "mass_kg_range": [0.0, 0.0005], "status": "assumed"},
                         {"id": "port_tape", "mass_kg_range": [0.0, 0.0002], "status": "assumed",
                          "position_mm": [v(p["ballast_bay"])["port_x_mm"], 0, None]},
                         {"id": "ballast", "status": "user-set; see ballast block"}],
            "ballast": {"bay_x_range_m": [x / 1000 for x in ballast["bay_x_mm"]],
                        "mass_range_kg": [0.0, max(r.get("ballast_g", 0) for r in ballast["rows"] if r["feasible"]) / 1000
                                          if any(r["feasible"] for r in ballast["rows"]) else 0.0],
                        "step_kg": 0.0005, "fill_model": ballast["fill_model"], "rows": ballast["rows"]},
            "assembled_dry": {"mass_kg": dry["mass_kg"], "cg_m": dry["cg_m"], "inertia_cg_kg_m2": dry["inertia_cg_kg_m2"]},
            "lifting_surfaces": surf,
            "body": {"outer_stl": "not separately written; the shell STL's outer surface is the v3a loft",
                     "enclosed_volume_m3": g["outer"].volume() * 1e-9,
                     "wetted_area_m2": float(MP_area(Vo, To) * 1e-6),
                     "max_depth_m": float((Vo[:, 2].max() - Vo[:, 2].min()) * 1e-3),
                     "max_width_m": float((Vo[:, 1].max() - Vo[:, 1].min()) * 1e-3)},
            "launch": {**manifest["launch_catch"], "grip_zone_x_mm": [140.0, 156.0],
                       "keepout": "band strands run forward from the slot's side openings, clear of the head"},
            "ground_contact_points_mm": manifest["ground_contact_points_mm"], "label": LABEL}


def parts_hash(manifest: dict) -> str:
    stl = {r["stl"]: r["stl_sha256"] for r in manifest["parts"]}
    return hashlib.sha256(json.dumps(stl, sort_keys=True).encode()).hexdigest()


def MP_area(V, T) -> float:
    tri = V[T]
    return float(0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1).sum())


def write_glb(path: Path, asm: dict) -> str:
    import trimesh
    sc = trimesh.Scene()
    for k, m in asm.items():
        V, T = arrays(m)
        sc.add_geometry(trimesh.Trimesh(V * 1e-3 @ B1.GLTF_FROM_FISH.T, T, process=False), node_name=k, geom_name=k)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(sc.export(file_type="glb"))
    return sha(path)


def libs() -> dict:
    import trimesh
    return {"numpy": np.__version__, "manifold3d": getattr(mf, "__version__", "unknown"), "trimesh": trimesh.__version__}


def git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


PRINT_SET = ["stl/body.stl", "stl/pectoral_L.stl", "stl/pectoral_R.stl", "stl/pelvic_L-dec+2.stl",
             "stl/pelvic_R-dec+2.stl", "stl/catch_plug-x20-dz+0.0.stl"]


def bundle(rev: str, out_root: Path) -> Path:
    """One deterministic ZIP of a revision's nominal print set, its manifest, the assembly notes, the defect registry
    and a SHA256SUMS list (fixed timestamps and permissions, so the same files give the same ZIP bytes)."""
    import zipfile
    d = out_root / rev
    rels = [*PRINT_SET, "manifest.json", "ASSEMBLY.md", "img/assembled.png"]
    files = [(rel, (d / rel).read_bytes()) for rel in rels]
    files.append(("KNOWN_DEFECTS.json", (out_root / "KNOWN_DEFECTS.json").read_bytes()))
    sums = "".join(f"{hashlib.sha256(b).hexdigest()}  {rel}\n" for rel, b in files)
    files.append(("SHA256SUMS", sums.encode()))
    path = d / f"print-set-{rev}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, b in files:
            info = zipfile.ZipInfo(f"glider-{rev}/{rel}", date_time=(2026, 10, 31, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, b)
    zb = path.read_bytes()
    # sidecar outside the ZIP, so pinning the ZIP never edits a file the ZIP holds
    side = {"schema": "frontier.glider.download/1", "revision": rev,
            "path": f"artifacts/glider/{rev}/{path.name}", "bytes": len(zb), "sha256": hashlib.sha256(zb).hexdigest(),
            "manifest_sha256": hashlib.sha256((d / "manifest.json").read_bytes()).hexdigest(),
            "known_defects": "artifacts/glider/KNOWN_DEFECTS.json",
            "label": "LAUNCH PROTOTYPE, UNTESTED, OVERWEIGHT; fit/balance test print; printer compatibility not claimed"}
    (d / "download.json").write_text(json.dumps(side, indent=2) + "\n")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / "artifacts/glider"))
    ap.add_argument("--only", choices=sorted(REVISIONS), action="append")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--bundle", choices=sorted(REVISIONS), help="only write print-set-<rev>.zip for a built revision")
    a = ap.parse_args(argv)
    if a.bundle:
        print(bundle(a.bundle, Path(a.out)))
        return 0
    for rev in a.only or sorted(REVISIONS):
        out = Path(a.out) / rev
        if (out / "manifest.json").exists() and Path(a.out).resolve() == (ROOT / "artifacts/glider").resolve():
            prior = json.loads((out / "manifest.json").read_text())
            if prior.get("code_sha256") != code_hash():
                print(f"{rev}: refusing to overwrite a published revision built by other code; add a new revision")
                return 2
        m = build_rev(rev, Path(a.out), not a.no_render)
        d = m["nominal_assembly"]["dry"]
        print(f"{rev}: dry {d['mass_g']:.2f} g, CG x {d['cg_mm'][0]:.1f} z {d['cg_mm'][2]:.2f} mm; "
              f"parts ok {all(r['validation']['ok'] and r['min_wall_ok'] for r in m['parts'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
