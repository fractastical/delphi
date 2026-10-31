"""fish3d v3: ray-fan fins, hypocercal caudal and sourced meristics on the N1 Cypselurus body.  ENGINEERED FORM.

    python -m engineering.fishv3.build [--out artifacts/fish3d] [--only <variant>] [--no-render]

Three candidates (VARIANTS) share one body, one anatomy and one source table and differ only in the knobs each
names.  The v1 candidate fish3d-N1-cypselurus-baseline stays as it was; nothing here writes into its directory.

Per candidate, artifacts/fish3d/<candidate_id>/ holds:
  candidate.json   every parameter with status (sourced | derived | figure_read | assumed | aesthetic | numerical) and,
                   for sourced ones, the source key and the range read; candidate_sha256 = sha256 of its bytes
  components/<id>.stl (metres), components.json, fish.glb (glTF +Y up; one node per component id)
  rays.json        every fin ray as polylines in metres in the fish frame, with length and tributary membrane width
  panels.json      per fin: membrane outline (3-D, metres) and a ray-aligned quad lattice for panel / VLM codes
  sections.json    2-D cuts of the actual meshes (a 2-D proxy for flow, not 3-D aerodynamics)
  scales.json, surface_map.json, build.json, preview.png (matplotlib, from the exported triangles)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh

from engineering.fish3d import build as B1
from engineering.fishv3 import appearance as AP
from engineering.fishv3 import fins as FN
from engineering.geometry import forms as F
from engineering.geometry import mesh as M

ROOT = Path(__file__).resolve().parents[2]
SPEC_ID = "N1-cypselurus-baseline"
BASELINE_ID = "fish3d-N1-cypselurus-baseline"
COMPONENTS = ("body", "operculum_L", "operculum_R", "eye_L", "eye_R", "pectoral_L", "pectoral_R",
              "pelvic_L", "pelvic_R", "dorsal", "anal", "caudal", "scales")
FINS = ("pectoral_L", "pectoral_R", "pelvic_L", "pelvic_R", "dorsal", "anal", "caudal")

SOURCES = {
    "fao_wca_exocoetidae": {
        "citation": "Parin, N.V. 2002. Exocoetidae (after Gibbs 1978). In: Carpenter, K.E. (ed.) The living marine "
                    "resources of the Western Central Atlantic, Vol. 2. FAO Species Identification Guide for Fishery "
                    "Purposes, pp. 1116-1134.",
        "url": "https://www.fao.org/4/y4161e/y4161e35.pdf",
        "sha256": "f1a35c8617602df6fedb6cd9c78105f288b4f4ecdf4df153e62f530076d779a5",  # fetched 2026-10-31
        "read_level": "full-text (pdftotext -layout of the family pages and species sheets)",
        "used_for": "Cheilopogon furcatus sheet: dorsal 12-14, anal 8-11 soft rays (anal origin under dorsal ray "
                    "5-7), pectoral 14-17 soft rays with the first unbranched, pectoral 1.3-1.5 and pelvic 2.7-3.3 "
                    "in SL, pelvic insertion nearer the opercle than the caudal base, predorsal scales 26-33 "
                    "(usually 27-30), eye 2.8-3.1 in head length; family: caudal deeply forked with the lower lobe "
                    "longer, pectorals high on the sides, dorsal and anal set far back with short opposed bases, "
                    "scales large and cycloid, lateral line low, snout shorter than eye; Atlantic Cheilopogon head "
                    "length 3.8-4.9 in SL (C. exsiliens 3.8-4.2, C. heterurus 4.3-4.9, key couplet 12 3.9-4.9)"},
    "daane2021": dict(B1.DAANE_PDF, used_for="hypocercal caudal fin with a 'stiffened and elongated ventral lobe'; "
                      "segmented lepidotrichia; S1A pectoral and pelvic length / SL (Cheilopogon furcatus, n = 12 "
                      "and 11) via engineering.geometry.sources"),
    "fish1990": {"citation": "Fish, F.E. 1990. Wing design and scaling of flying fish with regard to flight "
                             "performance. J. Zool., Lond. 221: 391-403.",
                 "used_for": "SL, wing area, span, pectoral share, hypocaudal area and share (Cypselurus fits, via "
                             "engineering.geometry.forms N1); fin positions figure-read",
                 "read_level": "as recorded in engineering/geometry/sources.py"},
    "park_choi_2010": {"citation": "Park, H. & Choi, H. 2010. Aerodynamic characteristics of flying fish in gliding "
                                   "flight. J. Exp. Biol. 213: 3269-3279. doi:10.1242/jeb.046052",
                       "read_level": "could-not-access (Cloudflare challenge on the publisher page and PDF, also "
                                     "via r.jina.ai); press summaries only",
                       "used_for": "nothing numeric; dihedral and camber stay assumed"},
}
DISAGREEMENTS = [
    {"quantity": "pectoral fin length / SL",
     "values": {"Fish 1990 span fit (N1, derived: (b - body width) / 2)": 0.584,
                "Daane 2021 S1A, Cheilopogon furcatus median (n = 12)": 0.677,
                "FAO WCA, C. furcatus sheet: 1.3-1.5 in SL": [0.667, 0.769]},
     "handling": "variants a and b keep the Fish value (the NCA comparison geometry); variant c uses Daane S1A"},
    {"quantity": "pelvic fin length / SL",
     "values": {"Daane 2021 S1A, C. furcatus median (n = 11)": 0.43,
                "FAO WCA, C. furcatus sheet: 2.7-3.3 in SL": [0.303, 0.370]},
     "handling": "all variants keep Daane S1A (as v1); the FAO range is shorter and is recorded, not reconciled"},
    {"quantity": "head length / SL",
     "values": {"FAO WCA, C. furcatus sheet: 2.8-3.1 in SL": [0.323, 0.357],
                "FAO WCA, other Atlantic Cheilopogon: 3.8-4.9 in SL": [0.204, 0.263]},
     "handling": "the C. furcatus value repeats that sheet's eye ratio (2.8-3.1), as the C. cyanopterus sheet "
                 "repeats its depth ratio as head length; taken as a likely copy slip and not used: head length "
                 "1/4.3 SL from the other Atlantic Cheilopogon"},
]


def A(value, status, note="", source=None, range_read=None):
    d = {"value": value, "status": status}
    if note:
        d["note"] = note
    if source:
        d["source"] = source
    if range_read is not None:
        d["range_read"] = range_read
    return d


FAO = "fao_wca_exocoetidae"
ANATOMY = {
    "head_length_over_sl": A(1 / 4.3, "sourced", "Atlantic Cheilopogon range; C. furcatus value excluded (see "
                             "disagreements)", FAO, [1 / 4.9, 1 / 3.8]),
    "eye_diameter_over_head": A(1 / 2.95, "sourced", "C. furcatus 2.8-3.1 in head length", FAO, [1 / 3.1, 1 / 2.8]),
    "snout_over_eye": A(0.8, "assumed", "family: snout shorter than eye; 0.8 is ours", FAO, [0.0, 1.0]),
    "eye_phi_deg": A(62.0, "aesthetic", "eye on the side of the head, above the midline"),
    "operculum_start_over_head": A(0.62, "assumed", "gill cover from 62% of head length to the head's end"),
    "operculum_phi_deg": A([30.0, 150.0], "aesthetic"),
    "operculum_thickness_mm": A(0.3, "assumed"),
    "pectoral_rays": A(15, "sourced", "value chosen inside 14-17", FAO, [14, 17]),
    "pectoral_unbranched_leading_rays": A(1, "sourced", "first pectoral ray unbranched (Cypselurus, Cheilopogon)",
                                          FAO),
    "pectoral_root_height": A(0.45, "assumed", "fraction of local upper half-height; family: pectorals 'high on "
                              "sides'", FAO),
    "pectoral_base_over_half_height": A(0.55, "assumed", "fin base length / local upper body half-height"),
    "pelvic_rays": A(6, "assumed", "not read for Exocoetidae; exposed as a parameter"),
    "pelvic_root_height": A(-0.55, "assumed", "fraction of local lower half-height"),
    "pelvic_base_over_half_height": A(0.35, "assumed"),
    "dorsal_rays": A(13, "sourced", "C. furcatus 12-14", FAO, [12, 14]),
    "anal_rays": A(10, "sourced", "C. furcatus 8-11", FAO, [8, 11]),
    "anal_origin_under_dorsal_ray": A(6, "sourced", "C. furcatus: anal origin under dorsal ray 5-7", FAO, [5, 7]),
    "dorsal_origin_s": A(0.66, "aesthetic", "carried from v1; family: dorsal and anal set far back", FAO),
    "median_ray_spacing_over_sl": A(0.0105, "assumed", "dorsal and anal ray root spacing; family: short bases",
                                    FAO),
    "dorsal_ray_max_over_sl": A(0.07, "assumed", "C. furcatus: 'dorsal fin low' (qualitative)", FAO),
    "anal_ray_max_over_sl": A(0.06, "assumed"),
    "median_rake_deg": A([35.0, 62.0], "assumed", "ray angle from the vertical, first to last ray"),
    "caudal_rays_upper_lower": A([7, 8], "assumed", "principal caudal rays not read for Exocoetidae"),
    "caudal_fan_deg": A([-42.0, 42.0], "assumed", "ray angles at the hypural plate, dorsal-most to ventral-most"),
    "caudal_fork_over_shorter_lobe": A(0.30, "assumed", "family: caudal 'deeply forked' (qualitative)", FAO),
    "caudal_lower_ray_radius_scale": A(1.4, "assumed", "Daane 2021: ventral lobe 'stiffened' (qualitative)",
                                       "daane2021"),
    "branching": A({"branch_at": 0.55, "half_angle_frac": 0.25}, "assumed",
                   "branched rays split once; only the pectoral's first-ray rule is sourced"),
    "paired_ray_profile": A({"lead_frac": 0.86, "peak_at": 0.2, "trail_frac": 0.42}, "assumed",
                            "ray length leading -> trailing as a fraction of the longest ray"),
    "pelvic_ray_profile": A({"lead_frac": 0.9, "peak_at": 0.25, "trail_frac": 0.5}, "assumed"),
    "margin_inset": A(0.08, "assumed", "membrane margin drawn in between ray tips (scalloped edge)"),
    "membrane_thickness_mm": A(0.10, "assumed"),
    "ray_radius_mm": A([0.30, 0.07], "assumed", "root, tip; each ray is one tapered rod (hemitrichia not split)"),
    "predorsal_scales": A(28.5, "sourced", "C. furcatus 26-33, usually 27-30; midpoint of 'usually'", FAO,
                          [26, 33]),
    "scale_radius_over_spacing": A(0.68, "assumed", "> 0.5 makes scales overlap; family: scales large, cycloid", FAO),
    "scale_tilt_deg": A(7.0, "assumed"), "scale_thickness_mm": A(0.12, "assumed"),
    "lateral_line_phi_deg": A(118.0, "assumed", "family: lateral line low on body", FAO),
}
NUMERICAL = {"stations": A(160, "numerical"), "ring": A(96, "numerical"), "ray_circular": A(10, "numerical"),
             "camber_refine_mm": A(3.0, "numerical", "fin triangle edge cap (camber warp and appearance)"), "body_min_half_size_mm": A(0.05, "numerical"),
             "panel_chordwise": A(6, "numerical"), "scale_mesh": A({"rings": 2, "segments": 10}, "numerical")}

# Deployment / placement / outline knobs.  Everything not named here is shared by all three candidates.
VARIANTS = {
    "a-fan": {"title": "v3a: ray-fan fins, Fish 1990 lengths and areas, flat spread",
              "knobs": {"pectoral_length_source": "fish1990", "pectoral_lead_angle_deg": 8.0,
                        "pectoral_dihedral_deg": 7.0, "pectoral_camber": 0.0, "pelvic_x_over_sl": 0.55,
                        "pelvic_lead_angle_deg": 22.0, "pelvic_dihedral_deg": 4.0, "pelvic_camber": 0.0}},
    "b-glide-pose": {"title": "v3b: same fins as v3a, posed: more sweep and dihedral, cambered",
                     "knobs": {"pectoral_length_source": "fish1990", "pectoral_lead_angle_deg": 16.0,
                               "pectoral_dihedral_deg": 12.0, "pectoral_camber": 0.06, "pelvic_x_over_sl": 0.55,
                               "pelvic_lead_angle_deg": 30.0, "pelvic_dihedral_deg": 8.0, "pelvic_camber": 0.04}},
    "c-daane-length": {"title": "v3c: pectoral length from Daane S1A (C. furcatus), pelvics further forward",
                       "knobs": {"pectoral_length_source": "daane2021", "pectoral_lead_angle_deg": 8.0,
                                 "pectoral_dihedral_deg": 7.0, "pectoral_camber": 0.0, "pelvic_x_over_sl": 0.48,
                                 "pelvic_lead_angle_deg": 22.0, "pelvic_dihedral_deg": 4.0, "pelvic_camber": 0.0}},
}
KNOB_STATUS = {
    "pectoral_length_source": "sourced (which published value; see disagreements)",
    "pectoral_lead_angle_deg": "assumed (deployment)", "pectoral_dihedral_deg": "assumed (deployment)",
    "pectoral_camber": "assumed (deployment; max offset / ray length; Park & Choi 2010 not readable)",
    "pelvic_x_over_sl": "figure_read 0.55 (Fish 1990) or placed inside the FAO rule: insertion nearer the opercle "
                        "than the caudal base",
    "pelvic_lead_angle_deg": "assumed (deployment)", "pelvic_dihedral_deg": "assumed (deployment)",
    "pelvic_camber": "assumed (deployment)",
}


def code_hash() -> str:
    h = hashlib.sha256()
    for f in sorted(Path(__file__).parent.glob("*.py")):
        h.update(f.name.encode() + f.read_bytes())
    for rel in ("engineering/fish3d/build.py", "engineering/geometry/forms.py", "engineering/geometry/mesh.py",
                "engineering/geometry/sources.py"):
        h.update(rel.encode() + (ROOT / rel).read_bytes())
    return h.hexdigest()


# ------------------------------------------------------------------ candidate
def candidate(variant: str) -> dict:
    spec = F.FORMS_BY_ID[SPEC_ID]
    bio = F.complete_point(spec, F.biological_point(spec), None, profile=M.body_profile)
    var = VARIANTS[variant]
    sl = F._v(bio["standard_length_m"])
    if var["knobs"]["pectoral_length_source"] == "daane2021":
        r = F.daane_ratio("flying fish | Cheilopogon furcatus", "pectoral")
        pect = A(r["value"] * sl, "sourced", r["note"], "daane2021")
    else:
        lay = F._v(bio["fin_layout_bio"])
        pect = A(lay["pectoral_length_m"], "derived", "Fish 1990 span fit: (b - body width at fin) / 2 (N1)",
                 "fish1990")
    return {
        "schema": "frontier.fish3d.candidate/2",
        "id": f"fish3d-v3{variant}",
        "variant": variant, "title": var["title"],
        "label": ("Engineered illustrative flying-fish form at biological scale, with source-conditioned fin rays. "
                  "Not an organism, not an ancestor, not a validated aerodynamic or hydrodynamic shape."),
        "baseline_candidate": BASELINE_ID, "from_print_form": SPEC_ID, "genus_fits": spec.genus,
        "mass_kg": spec.mass_kg, "biology": bio, "shape_params": spec.params,
        "pectoral_length_m": pect,
        "anatomy": ANATOMY, "numerical": NUMERICAL,
        "knobs": {k: {"value": val, "status": KNOB_STATUS[k]} for k, val in var["knobs"].items()},
        "sources": SOURCES, "disagreements": DISAGREEMENTS,
        "status_vocabulary": {"sourced": "read from the named source (value chosen inside range_read when given)",
                              "derived": "computed from sourced values", "figure_read": "read off a figure",
                              "assumed": "our choice, exposed as a parameter", "aesthetic": "appearance only",
                              "numerical": "meshing resolution, no physical meaning"},
    }


def v(p):
    return p["value"] if isinstance(p, dict) and "value" in p else p


# ------------------------------------------------------------------ fins
def _paired_fan(n, L_max, profile, base_len, lead_deg, spread_deg, unbranched, an, membrane, radii, camber):
    roots = np.column_stack([np.zeros(n), np.linspace(0, base_len, n)])
    lengths = FN.paired_lengths(n, L_max, profile["lead_frac"], profile["peak_at"], profile["trail_frac"])
    alpha = lead_deg + np.linspace(0, spread_deg, n)
    br = np.arange(n) >= unbranched
    return FN.Fan(roots, alpha, lengths, br, membrane, radii[0], radii[1], branch_at=v(an["branching"])["branch_at"],
                  branch_half_angle_frac=v(an["branching"])["half_angle_frac"], margin_inset=v(an["margin_inset"]),
                  camber=camber)


def paired_fin(cand, body, which, L_max_mm, area_mm2, x_over_sl, lead_deg, dihedral_deg, camber):
    an = cand["anatomy"]
    n = v(an[f"{which}_rays"])
    xs = x_over_sl
    w0, hu0, hd0 = body.half_sizes(xs)
    zf = v(an[f"{which}_root_height"])
    z0 = zf * (hu0 if zf >= 0 else hd0)
    y0 = w0 * math.sqrt(max(1 - zf * zf, 0.05)) * 0.92  # root inset into the body wall
    base = v(an[f"{which}_base_over_half_height"]) * (hu0 if zf >= 0 else hd0)
    prof = v(an["paired_ray_profile"] if which == "pectoral" else an["pelvic_ray_profile"])
    unb = v(an["pectoral_unbranched_leading_rays"]) if which == "pectoral" else 1
    mem, radii = v(an["membrane_thickness_mm"]), v(an["ray_radius_mm"])
    # rays are anatomy, solved once in the reference pose (flat, lead angle 8 deg) to the area target; a pose
    # variant then changes angles, dihedral and camber but never the ray lengths
    spread, _ = FN.solve_spread(lambda s: _paired_fan(n, L_max_mm, prof, base, 8.0, s, unb, an, mem, radii, 0.0),
                                  area_mm2)
    fan = _paired_fan(n, L_max_mm, prof, base, lead_deg, spread, unb, an, mem, radii, -camber)  # frame n is down
    d = math.radians(dihedral_deg)
    origin = np.array([xs * body.sl - 0.3 * base, y0, z0])
    e_u, e_w = np.array([0.0, math.cos(d), math.sin(d)]), np.array([1.0, 0, 0])
    frame = (origin, e_u, e_w, np.cross(e_u, e_w))
    rep = {"rays": an[f"{which}_rays"],
           "longest_ray_mm": A(L_max_mm, "derived" if which == "pelvic" else cand["pectoral_length_m"]["status"]),
           "area_target_mm2": A(area_mm2, "derived", "Fish 1990 (N1 layout); for variant c scaled by length^2"),
           "area_built_flat_mm2": A(fan.area_mm2(), "derived"),
           "spread_deg_reference": A(spread, "derived", "fan spread solved so the flat reference fin has the area "
                                                         "target"),
           "lead_angle_deg": A(lead_deg, "assumed"), "dihedral_deg": A(dihedral_deg, "assumed"),
           "camber": A(camber, "assumed"),
           "x_over_sl": A(xs, "figure_read" if xs in (0.27, 0.55) else "assumed", "Fish 1990 figure-read positions are "
                          "0.27 (pectoral) and 0.55 (pelvic); other values are placed inside the FAO pelvic rule"),
           "root_mm": A(origin.tolist(), "derived"), "base_length_mm": A(base, "assumed"),
           "ray_lengths_mm": A(fan.lengths.tolist(), "derived", "longest ray x the assumed profile")}
    return fan, frame, rep


def median_fin(cand, body, which):
    an = cand["anatomy"]; sl = body.sl
    nd, na = v(an["dorsal_rays"]), v(an["anal_rays"])
    dx = v(an["median_ray_spacing_over_sl"]) * sl
    x_d0 = v(an["dorsal_origin_s"]) * sl
    if which == "dorsal":
        n, x0, sign, Lmax = nd, x_d0, 1, v(an["dorsal_ray_max_over_sl"]) * sl
    else:
        n, x0, sign, Lmax = na, x_d0 + (v(an["anal_origin_under_dorsal_ray"]) - 1) * dx, -1, v(an["anal_ray_max_over_sl"]) * sl
    xs = x0 + dx * np.arange(n)
    h = np.array([body.half_sizes(x / sl)[1 if sign > 0 else 2] for x in xs])
    roots = np.column_stack([h * 0.9, xs - x0])  # u = height above (below) the axis, inset into the body
    r0, r1 = v(an["median_rake_deg"])
    alpha = np.linspace(r0, r1, n)
    lengths = FN.paired_lengths(n, Lmax, 0.8, 0.12, 0.38)
    fan = FN.Fan(roots, alpha, lengths, np.arange(n) >= 1, v(an["membrane_thickness_mm"]), *v(an["ray_radius_mm"]),
                 branch_at=v(an["branching"])["branch_at"], branch_half_angle_frac=v(an["branching"])["half_angle_frac"],
                 margin_inset=v(an["margin_inset"]))
    e_u = np.array([0.0, 0, sign]); e_w = np.array([1.0, 0, 0])
    frame = (np.array([x0, 0, 0]), e_u, e_w, np.cross(e_u, e_w))
    rep = {"rays": an[f"{which}_rays"], "origin_x_mm": A(x0, "derived"),
           "longest_ray_mm": A(Lmax, "assumed"), "area_mm2": A(fan.area_mm2(), "derived"),
           "rake_deg": an["median_rake_deg"], "ray_spacing_mm": A(dx, "assumed")}
    if which == "anal":
        rep["origin_under_dorsal_ray"] = an["anal_origin_under_dorsal_ray"]
    return fan, frame, rep


def caudal_fin(cand, body):
    an, bio, a = cand["anatomy"], cand["biology"], cand["shape_params"]
    sl, W = body.sl, body.W
    ped_half = W * body.hw * F._v(a["peduncle_fraction"])
    nu, nl = v(an["caudal_rays_upper_lower"]); n = nu + nl
    hypo = F._v(bio["hypocaudal_area_m2"]) * 1e6
    total = hypo / F._v(bio["hypocaudal_share"])
    upper_t = total - hypo
    a0, a1 = v(an["caudal_fan_deg"])
    alpha = np.linspace(a0, a1, n)
    roots = np.column_stack([np.zeros(n), np.linspace(-0.8 * ped_half, 0.8 * ped_half, n)])
    fork = v(an["caudal_fork_over_shorter_lobe"])
    scale = np.where(np.arange(n) >= nu, v(an["caudal_lower_ray_radius_scale"]), 1.0)

    def lengths(U, Lw):
        Fk = fork * min(U, Lw)
        up = np.interp(np.arange(nu), [0, 1, nu - 1], [0.8 * U, U, Fk])
        lo = np.interp(np.arange(nl), [0, nl - 2, nl - 1], [Fk, Lw, 0.85 * Lw])
        return np.concatenate([up, lo])

    def make(U, Lw):
        return FN.Fan(roots, alpha, lengths(U, Lw), np.ones(n, bool), v(an["membrane_thickness_mm"]),
                      *v(an["ray_radius_mm"]), ray_radius_scale=scale, branch_at=v(an["branching"])["branch_at"],
                      branch_half_angle_frac=v(an["branching"])["half_angle_frac"], margin_inset=v(an["margin_inset"]))

    def lobe_areas(fan):
        T = fan.tips()
        up = abs(FN.signed_area(np.vstack([fan.roots[:nu], T[:nu][::-1]])))
        lo = abs(FN.signed_area(np.vstack([fan.roots[nu:], T[nu:][::-1]])))
        mid = abs(FN.signed_area(np.array([fan.roots[nu - 1], T[nu - 1], T[nu], fan.roots[nu]])))
        return up + 0.5 * mid, lo + 0.5 * mid

    U, Lw = 0.3 * sl, 0.5 * sl
    for _ in range(60):  # areas scale ~ length^2 per lobe; fixed-point on each
        au, al = lobe_areas(make(U, Lw))
        U, Lw = U * math.sqrt(upper_t / au), Lw * math.sqrt(hypo / al)
    fan = make(U, Lw)
    au, al = lobe_areas(fan)
    x0 = 0.97 * sl
    e_u, e_w = np.array([1.0, 0, 0]), np.array([0.0, 0, -1])
    frame = (np.array([x0, 0, 0]), e_u, e_w, np.cross(e_u, e_w))
    rep = {"rays_upper_lower": an["caudal_rays_upper_lower"],
           "upper_lobe_longest_ray_mm": A(U, "derived"), "lower_lobe_longest_ray_mm": A(Lw, "derived"),
           "upper_area_mm2": A(au, "derived", f"target {upper_t:.1f} (Fish 1990 total - hypocaudal)"),
           "hypocaudal_area_mm2": A(al, "derived", f"target {hypo:.1f} (Fish 1990 hypocaudal fit)"),
           "hypocaudal_share_built": A(al / (au + al), "derived", "target from Fish 1990 Table IV"),
           "fork": an["caudal_fork_over_shorter_lobe"], "lower_lobe_ray_scale": an["caudal_lower_ray_radius_scale"]}
    return fan, frame, rep


# ------------------------------------------------------------------ components
def build_components(cand: dict):
    bio, a, an, nm = cand["biology"], cand["shape_params"], cand["anatomy"], cand["numerical"]
    k = {kk: v(vv) for kk, vv in cand["knobs"].items()}
    sl = F._v(bio["standard_length_m"]) * 1000
    W = F._v(bio["body_half_width_max_m"]) * 1000
    hw, flat, ped = F._v(a["body_height_over_width"]), F._v(a["ventral_flattening"]), F._v(a["peduncle_fraction"])
    body = B1.Body(sl, W, hw, flat, ped)
    comps, rep, fans = {}, {}, {}
    r_min = v(nm["body_min_half_size_mm"])
    s = 0.5 * (1 - np.cos(np.linspace(0, np.pi, v(nm["stations"]))))
    f = body.f(s)
    comps["body"] = M.loft(s * sl, np.maximum(W * f, r_min), np.maximum(W * hw * f, r_min),
                           np.maximum(W * hw * flat * f, r_min), np.zeros_like(s), v(nm["ring"]), nose_x=-0.6 * r_min)
    depth = max(W * hw * (1 + flat) * float(body.f([q])[0]) for q in np.linspace(0, 1, 401))
    rep["body"] = {"standard_length_mm": A(sl, "derived", "Fish 1990 Cypselurus length fit at 0.05 kg"),
                   "max_half_width_mm": A(W, "derived", "body volume = mass / density"),
                   "max_depth_over_sl": A(depth / sl, "derived", "C. furcatus depth 4.8-6.1 in SL = 0.164-0.208 "
                                                                "(FAO); this check is reported, not forced"),
                   "height_over_width": A(hw, "aesthetic"), "ventral_flattening": A(flat, "aesthetic",
                                                                                   "FAO: 'almost flat ventrally'")}

    # head: eye and gill cover positioned from sourced head and eye ratios
    HL = v(an["head_length_over_sl"]) * sl
    eye_d = v(an["eye_diameter_over_head"]) * HL
    s_eye = (v(an["snout_over_eye"]) * eye_d + 0.5 * eye_d) / sl
    _, hu_e, _ = body.half_sizes(s_eye)
    r_e = 0.5 * eye_d
    for side, suf in ((1, "L"), (-1, "R")):
        phi = math.radians(v(an["eye_phi_deg"])) * side
        c = body.point(s_eye, phi); nrm = body.normal(s_eye, phi)
        centre = c - nrm * 0.78 * r_e  # mostly inside the head: a flush eye, not a bead
        comps[f"eye_{suf}"] = mf.Manifold.sphere(r_e, 40).translate(tuple(float(q) for q in centre))
        rep[f"eye_{suf}"] = {"diameter_mm": A(eye_d, "derived", "head length x FAO eye ratio"),
                             "centre_s": A(s_eye, "derived", "snout + half an eye"), "centre_mm": A(centre.tolist(), "derived"),
                             "head_half_height_mm": A(hu_e, "derived")}
    s_lo, s_hi = v(an["operculum_start_over_head"]) * HL / sl, HL / sl
    p_lo, p_hi = [math.radians(q) for q in v(an["operculum_phi_deg"])]
    for side, suf in ((1, "L"), (-1, "R")):
        V, T = B1.surface_slab(body, 0.5 * (s_lo + s_hi), side * 0.5 * (p_lo + p_hi), 0.5 * (s_hi - s_lo),
                               0.5 * (p_hi - p_lo), lambda u: 0.3 * np.clip(u, 0, None), 0.05,
                               v(an["operculum_thickness_mm"]), 6, 40)
        comps[f"operculum_{suf}"] = B1.to_manifold(V, T)
        rep[f"operculum_{suf}"] = {"s_range": A([s_lo, s_hi], "derived", "head length (sourced) x assumed start"),
                                   "note": "gill cover as a thin shell ending at the head's posterior margin"}

    # paired fins
    lay = F._v(bio["fin_layout_bio"])
    Lp = v(cand["pectoral_length_m"]) * 1000
    Ap = lay["pectoral_area_per_fin_m2"] * 1e6 * (Lp / (lay["pectoral_length_m"] * 1000)) ** 2
    xp = F._v(bio["fin_x_over_sl"])["pectoral"]
    if xp * sl <= HL:
        raise ValueError("pectoral root falls inside the head")
    for which, L, Ar, x, lead, dih, cam in (
            ("pectoral", Lp, Ap, xp, k["pectoral_lead_angle_deg"], k["pectoral_dihedral_deg"], k["pectoral_camber"]),
            ("pelvic", lay["pelvic_length_m"] * 1000, lay["pelvic_area_per_fin_m2"] * 1e6, k["pelvic_x_over_sl"],
             k["pelvic_lead_angle_deg"], k["pelvic_dihedral_deg"], k["pelvic_camber"])):
        # FAO: pelvic insertion nearer the posterior margin of the opercle than the caudal base
        if which == "pelvic" and not abs(x * sl - HL) < abs(0.97 * sl - x * sl):
            raise ValueError(f"pelvic insertion at {x} SL breaks the FAO placement rule")
        fan, frame, r = paired_fin(cand, body, which, L, Ar, x, lead, dih, cam)
        solid = FN.place(fan.solid(v(nm["ray_circular"]), v(nm["camber_refine_mm"])), *frame)
        comps[f"{which}_L"] = solid
        comps[f"{which}_R"] = solid.mirror((0, 1, 0))
        fans[f"{which}_L"] = (fan, frame, 1); fans[f"{which}_R"] = (fan, frame, -1)
        rep[f"{which}_L"] = rep[f"{which}_R"] = r
    for which in ("dorsal", "anal"):
        fan, frame, r = median_fin(cand, body, which)
        comps[which] = FN.place(fan.solid(v(nm["ray_circular"]), v(nm["camber_refine_mm"])), *frame); fans[which] = (fan, frame, 1); rep[which] = r
    fan, frame, r = caudal_fin(cand, body)
    comps["caudal"] = FN.place(fan.solid(v(nm["ray_circular"]), v(nm["camber_refine_mm"])), *frame); fans["caudal"] = (fan, frame, 1)
    rep["caudal"] = r

    # scales: spacing from the sourced predorsal count (head end -> dorsal origin)
    d_mm = (v(an["dorsal_origin_s"]) - HL / sl) * sl / v(an["predorsal_scales"])
    zone = [HL / sl, 0.95]
    n_ll = round((zone[1] - zone[0]) * sl / d_mm)
    fid = {"scale_zone_s": A(zone, "derived"), "scale_lateral_count": A(n_ll, "derived"),
           "scale_radius_over_spacing": an["scale_radius_over_spacing"]}
    srec = B1.place_scales(body, fid)
    ll = math.radians(v(an["lateral_line_phi_deg"]))
    for row in sorted({q["row"] for q in srec["scales"]}):
        in_row = [q for q in srec["scales"] if q["row"] == row]
        for tgt in (ll, 2 * math.pi - ll):  # left flank, right flank (phi 0 dorsal, pi/2 left)
            min(in_row, key=lambda q: abs(math.remainder(q["phi_rad"] - tgt, 2 * math.pi)))["lateral_line"] = True
    rings, segs = v(nm["scale_mesh"])["rings"], v(nm["scale_mesh"])["segments"]
    tilt = math.tan(math.radians(v(an["scale_tilt_deg"])))
    Vs, Ts, off = [], [], 0
    for sc in srec["scales"]:
        r = sc["radius_mm"]
        V, T = B1.surface_slab(body, sc["s"], sc["phi_rad"], r / sl, r / sc["local_radius_mm"],
                               lambda u, r=r: tilt * r * (u + 1), 0.02, v(an["scale_thickness_mm"]), rings, segs)
        Vs.append(V); Ts.append(T + off); off += len(V)
    comps["scales"] = B1.to_manifold(np.concatenate(Vs), np.concatenate(Ts))
    rep["scales"] = {"spacing_mm": A(d_mm, "derived", "predorsal length / predorsal scale count (FAO, C. furcatus)"),
                     "lateral_rows": A(n_ll, "derived"), "count": A(len(srec["scales"]), "derived"),
                     "lateral_line_scales": A(sum(1 for q in srec["scales"] if q.get("lateral_line")), "derived"),
                     "radius_over_spacing": an["scale_radius_over_spacing"], "tilt_deg": an["scale_tilt_deg"],
                     "pattern": A("staggered lattice", "assumed", "spacing is sourced; the lattice, overlap and tilt "
                                  "are ours; the order of scale formation is not sourced for Exocoetidae")}
    srec["spacing_source"] = rep["scales"]["spacing_mm"]
    rep["head"] = {"head_length_mm": A(HL, "derived", "SL x sourced head ratio")}
    return comps, rep, fans, srec, body


# ------------------------------------------------------------------ interface files
def rays_json(fans: dict) -> dict:
    out = {}
    for cid, (fan, frame, side) in fans.items():
        mir = np.array([1.0, side, 1.0])
        warp = fan.warp_fn()
        rows = []
        for ray in fan.ray_polylines():
            segs = []
            for seg in ray["segments_uw_mm"]:
                pts = np.linspace(seg[0], seg[1], 6)
                segs.append((FN.to_fish(pts, *frame, warp=warp) * mir / 1000).round(7).tolist())
            rows.append({"index": ray["index"], "branched": ray["branched"], "length_m": ray["length_mm"] / 1000,
                         "tributary_width_m": ray["tributary_width_mm"] / 1000,
                         "tributary_area_m2": ray["tributary_area_mm2"] / 1e6,
                         "root_m": segs[0][0], "polylines_m": segs})
        out[cid] = {"n_rays": len(rows), "rays": rows,
                    "order": "leading (or dorsal-most) ray first"}
    return out


def panels_json(fans: dict, nc: int) -> dict:
    """Ray-aligned quad lattice: between neighbouring rays i, i+1, nc quads from base to tips.  Corners in metres."""
    out = {}
    for cid, (fan, frame, side) in fans.items():
        mir = np.array([1.0, side, 1.0])
        warp = fan.warp_fn()
        R, T = fan.roots, fan.tips()
        t = np.linspace(0, 1, nc + 1)
        quads = []
        for i in range(len(T) - 1):
            a = R[i][None] + t[:, None] * (T[i] - R[i])[None]
            b = R[i + 1][None] + t[:, None] * (T[i + 1] - R[i + 1])[None]
            A3 = FN.to_fish(a, *frame, warp=warp) * mir / 1000
            B3 = FN.to_fish(b, *frame, warp=warp) * mir / 1000
            for j in range(nc):
                quads.append([A3[j].round(7).tolist(), A3[j + 1].round(7).tolist(),
                              B3[j + 1].round(7).tolist(), B3[j].round(7).tolist()])
        outline = FN.to_fish(fan.outline(), *frame, warp=warp) * mir / 1000
        out[cid] = {"outline_m": outline.round(7).tolist(), "quads_m": quads,
                    "fin_plane": {"origin_m": (frame[0] * mir / 1000).tolist(), "e_u": (frame[1] * mir).tolist(),
                                  "e_w": (frame[2] * mir).tolist()},
                    "area_flat_m2": fan.area_mm2() / 1e6,
                    "note": "mid-surface of the membrane (rays and thickness not included); quads follow the rays"}
    return out


def sections(comps: dict) -> dict:
    def polys(cs):
        return [(np.asarray(p, float) / 1000).round(7).tolist() for p in cs.to_polygons()]
    out = {}
    sag = mf.Manifold.batch_boolean([comps[q] for q in ("body", "dorsal", "anal", "caudal")], mf.OpType.Add)
    cs = sag.transform([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0]]).slice(0.0)
    out["body_sagittal"] = {"plane": "y = 0 through body + dorsal + anal + caudal", "axes": ["x", "z"],
                            "polygons_m": polys(cs)}
    pl = mf.Manifold.batch_boolean([comps[q] for q in ("body", "pectoral_L", "pectoral_R", "pelvic_L", "pelvic_R")],
                                   mf.OpType.Add).project()
    out["planform"] = {"plane": "projection onto z = 0 (top view) of body + paired fins", "axes": ["x", "y"],
                       "polygons_m": polys(pl), "area_m2": float(pl.area() / 1e6)}
    for q in out.values():
        q["label"] = "2-D cut of the 3-D mesh; flow on it is a 2-D proxy, not 3-D aero/hydrodynamics."
    return out


def preview(parts, path, title: str, dpi: int = 120) -> None:
    """Flat-shaded matplotlib views of the exported triangles, coloured by the appearance layer (cheap; no
    path tracing).  Same views as engineering.geometry.render."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    from engineering.geometry.render import VIEWS
    allv = np.concatenate([p[0] for p in parts]); lo, hi = allv.min(axis=0), allv.max(axis=0)
    light = np.array([0.35, -0.45, 0.82]); light /= np.linalg.norm(light)
    fig = plt.figure(figsize=(13.5, 4.6), dpi=dpi)
    for i, (name, elev, azim) in enumerate(VIEWS):
        ax = fig.add_subplot(1, 3, i + 1, projection="3d")
        for V, T, C in parts:
            tri = V[T]
            nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
            nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
            k = 0.40 + 0.60 * np.abs(nrm @ light)
            fc = np.clip(C[T, :3].mean(axis=1) / 255.0 * k[:, None], 0, 1)
            ax.add_collection3d(Poly3DCollection(tri, facecolors=fc, edgecolors="none", linewidths=0))
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect(hi - lo); ax.view_init(elev=elev, azim=azim); ax.set_axis_off()
        ax.set_title(name, fontsize=8)
    size = hi - lo
    fig.suptitle(f"{title}\nflat-shaded from the exported mesh (not a photograph, not a measurement); extent "
                 f"{size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, metadata={"Software": None, "Creation Time": None})
    plt.close(fig)


def build_one(variant: str, out_root: Path, render: bool) -> dict:
    cand = candidate(variant)
    cb = B1.canon(cand); csha = B1.sha(cb)
    out = out_root / cand["id"]
    (out / "components").mkdir(parents=True, exist_ok=True)
    (out / "candidate.json").write_bytes(cb)
    comps, rep, fans, srec, body = build_components(cand)
    checks, files = {}, {}
    scene = trimesh.Scene()
    arrays = {}
    for cid in COMPONENTS:
        V, T = B1.mesh_arrays(comps[cid]); arrays[cid] = (V, T)
        tm = trimesh.Trimesh(V / 1000.0, T, process=False)
        checks[cid] = B1.check(comps[cid])
        checks[cid]["signed_volume_mm3"] = float(trimesh.Trimesh(V, T, process=False).volume)
        if cid != "scales":  # as v1: scales live in the GLB and are regenerated from scales.json
            p = out / "components" / f"{cid}.stl"
            p.write_bytes(tm.export(file_type="stl")); files[f"components/{cid}.stl"] = B1.sha(p.read_bytes())
        scene.add_geometry(trimesh.Trimesh((V / 1000.0) @ B1.GLTF_FROM_FISH.T, T, process=False), node_name=cid,
                           geom_name=cid)
    glb = scene.export(file_type="glb"); (out / "fish.glb").write_bytes(glb); files["fish.glb"] = B1.sha(glb)
    nc = v(cand["numerical"]["panel_chordwise"])
    docs = {
        "components.json": {"schema": "frontier.fish3d.components/2", "candidate_sha256": csha,
                            "units": "STL and GLB in metres", "frame": "x snout->tail, y left, z dorsal; snout at x=0",
                            "glb_frame": "glTF +Y up: glb (x, y, z) = fish (x, z, -y)",
                            "components": {cid: {"params": rep[cid], "check": checks[cid],
                                                 "stl": None if cid == "scales" else f"components/{cid}.stl",
                                                 "stl_sha256": files.get(f"components/{cid}.stl")}
                                           for cid in COMPONENTS},
                            "overlap_note": "fin roots are inset into the body; union before volume or flow use"},
        "rays.json": {"schema": "frontier.fish3d.rays/1", "candidate_sha256": csha, "units": "m",
                      "use": "fin-ray loads (e.g. engineering.fin_mechanics): length_m and tributary_width_m per ray",
                      "fins": rays_json(fans)},
        "panels.json": {"schema": "frontier.fish3d.panels/1", "candidate_sha256": csha, "units": "m",
                        "fins": panels_json(fans, nc)},
        "sections.json": {"schema": "frontier.fish3d.sections/1", "candidate_sha256": csha, **sections(comps)},
        "scales.json": {"schema": "frontier.fish3d.scales/1", "candidate_sha256": csha, **srec,
                        "status": "spacing from the FAO predorsal count; lattice, overlap and tilt assumed"},
        "surface_map.json": {"schema": "frontier.fish3d.surface_map/1", "candidate_sha256": csha,
                             "SL_mm": body.sl, "W_mm": body.W, "height_over_width": body.hw,
                             "ventral_flattening": body.flat, "peduncle_fraction": body.ped,
                             "profile": "engineering.geometry.mesh.body_profile",
                             "point": "x = s SL; y = w(s) sin(phi); z = h(s) cos(phi)"},
    }
    for name, obj in docs.items():
        b = B1.canon(obj); (out / name).write_bytes(b); files[name] = B1.sha(b)
    head_end = v(rep["head"]["head_length_mm"]) / body.sl
    for opt in AP.OPTIONS:
        cols = {c: AP.vertex_colors(c, arrays[c][0], fans, body, opt, head_end) for c in COMPONENTS}
        rec = AP.record(opt, csha); rec["glb"] = rec["glb_sha256"] = None
        if opt == AP.DEFAULT or variant == "a-fan":  # the design option ships as a GLB on the homepage candidate only
            sc = trimesh.Scene()
            for cid in COMPONENTS:
                V, T = arrays[cid]
                sc.add_geometry(trimesh.Trimesh((V / 1000.0) @ B1.GLTF_FROM_FISH.T, T, vertex_colors=cols[cid],
                                                process=False), node_name=cid, geom_name=cid)
            g = sc.export(file_type="glb"); (out / f"fish-{opt}.glb").write_bytes(g)
            files[f"fish-{opt}.glb"] = B1.sha(g)
            rec["glb"], rec["glb_sha256"] = f"fish-{opt}.glb", files[f"fish-{opt}.glb"]
        rec["geometry_glb_sha256"] = files["fish.glb"]
        b = B1.canon(rec); (out / f"appearance-{opt}.json").write_bytes(b); files[f"appearance-{opt}.json"] = B1.sha(b)
        if render:
            name = f"preview-{opt}.png"
            preview([(arrays[c][0], arrays[c][1], cols[c]) for c in COMPONENTS], out / name,
                    f"{cand['id']}  candidate {csha[:12]}  |  {cand['title']}\nappearance: {AP.OPTIONS[opt]['title']}")
            files[name] = B1.sha((out / name).read_bytes())
    build = {"schema": "frontier.fish3d.build/2", "candidate": "candidate.json", "candidate_sha256": csha,
             "code_sha256": code_hash(), "libraries": {"numpy": np.__version__, "trimesh": trimesh.__version__},
             "files": files, "checks": checks,
             "all_closed": all(c["closed_two_manifold"] and c["consistently_oriented"] and c["signed_volume_mm3"] > 0
                               for c in checks.values())}
    (out / "build.json").write_bytes(B1.canon(build))
    return {"id": cand["id"], "candidate_sha256": csha, "all_closed": build["all_closed"],
            "knobs": {kk: vv["value"] for kk, vv in cand["knobs"].items()},
            "pectoral": {kk: v(rep["pectoral_L"][kk]) for kk in ("longest_ray_mm", "area_target_mm2",
                                                                 "area_built_flat_mm2", "spread_deg_reference")},
            "caudal": {kk: v(rep["caudal"][kk]) for kk in ("upper_lobe_longest_ray_mm", "lower_lobe_longest_ray_mm",
                                                           "hypocaudal_share_built")},
            "scales": v(rep["scales"]["count"]), "files": files}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "fish3d"))
    ap.add_argument("--only", choices=sorted(VARIANTS), default=None)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out)
    rows = [build_one(k, out, not a.no_render) for k in VARIANTS if a.only in (None, k)]
    if a.only is None:
        idx = {"schema": "frontier.fish3d.v3_index/1", "baseline": BASELINE_ID, "code_sha256": code_hash(),
               "candidates": {r["id"]: {kk: r[kk] for kk in ("candidate_sha256", "knobs", "all_closed")} for r in rows},
               "shared": "body, anatomy, sources and disagreements are identical across the three; only knobs differ"}
        (out / "v3-index.json").write_bytes(B1.canon(idx))
    print(json.dumps([{kk: r[kk] for kk in ("id", "candidate_sha256", "all_closed", "pectoral", "caudal", "scales")}
                      for r in rows], indent=1))
    return 0 if all(r["all_closed"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
