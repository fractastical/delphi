"""Biological-scale 3D flying fish: one candidate, one hash, separate editable components.  ENGINEERED FORM.

    python -m engineering.fish3d.build [--out artifacts/fish3d]

Candidate: the NCA corrected comparison-set baseline (print form N1: Cypselurus fits, 0.05 kg).  Every sourced
number comes from engineering.geometry.forms (Fish 1990 fits, Daane 2021 S1A, the NCA set), so the dimensions are
the print form's dimensions at 1:1, WITHOUT the print-only thickening.  What is added here (thin fins, eyes,
opercula, scales) is labelled `assumed` or `aesthetic` in candidate.json.

Writes artifacts/fish3d/<candidate_id>/:
  candidate.json   every shape parameter with status + source; candidate_sha256 = sha256 of its bytes
  components/<id>.stl, components.json, fish.glb (one node per component, node name = component id)
  scales.json      the scale pattern on the body surface: (s, phi), xyz, normal, radius, tilt per scale
  surface_map.json body surface parameterisation (s, phi) -> xyz
  sections.json    2-D cuts of the actual meshes, for the 2-D flow worker (a 2-D proxy, not 3-D aerodynamics)
  build.json       code sha256, library versions, mesh checks, output sha256s
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

from engineering.geometry import forms as F
from engineering.geometry import mesh as M
from engineering.geometry import sources as SRC

ROOT = Path(__file__).resolve().parents[2]
SPEC_ID = "N1-cypselurus-baseline"
COMPONENTS = ("body", "operculum_L", "operculum_R", "eye_L", "eye_R", "pectoral_L", "pectoral_R",
              "pelvic_L", "pelvic_R", "dorsal", "anal", "caudal", "scales")
DAANE_PDF = {"url": "https://www.daanelab.org/pdfs/papers/Daane-CurrBio-2021.pdf",
             "sha256": "e0d4e61d74ab982efa5a3e861103bdc9b1b3ce8c25f01854799dba7b0b22c2e2",  # fetched 2026-10-31
             "doi": "10.1016/j.cub.2021.08.054", "read_level": "full-text (main text); data in Data S1A",
             "used_for": "pectoral fin allometry fixed across two- and four-wing flying fishes; hypocercal caudal "
                         "fin with an elongated ventral lobe; S1A fin-length/SL ratios (via engineering.geometry)"}


GLTF_FROM_FISH = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]])  # fish (x, y left, z dorsal) -> glTF (x, z, -y)


def A(value, status, note=""):
    """A labelled parameter.  status: derived | measured | assumed | aesthetic | numerical."""
    d = {"value": value, "status": status}
    if note:
        d["note"] = note
    return d


FIDELITY = {
    "fin_thickness_mm": A(0.5, "assumed", "flat fin plates; real fin thickness, camber and ray structure not modelled"),
    "fin_open_radius_mm": A(0.05, "numerical", "removes slivers narrower than 0.1 mm; not the print 1 mm opening"),
    "body_min_half_size_mm": A(0.05, "numerical"),
    "stations": A(160, "numerical"), "ring": A(96, "numerical"), "span_pts": A(64, "numerical"),
    "circular": A(24, "numerical"),
    "eye_s": A(0.07, "aesthetic", "eye centre as a fraction of SL from the snout"),
    "eye_radius_over_head_half_height": A(0.42, "aesthetic"),
    "operculum_s_range": A([0.13, 0.21], "aesthetic", "gill cover extent along the body"),
    "operculum_phi_deg": A([35.0, 150.0], "aesthetic", "angle around the body, 0 = dorsal, 90 = left flank"),
    "operculum_thickness_mm": A(0.35, "assumed"),
    "scale_lateral_count": A(50, "assumed", "scales along the lateral series; no Cypselurus count was read"),
    "scale_zone_s": A([0.21, 0.95], "assumed", "scaled region along the body (behind the opercula)"),
    "scale_radius_over_spacing": A(0.68, "assumed", "radius / centre spacing; > 0.5 makes scales overlap"),
    "scale_tilt_deg": A(7.0, "assumed", "posterior edge lifted off the body, so each scale overlaps the next"),
    "scale_thickness_mm": A(0.12, "assumed"),
    "scale_mesh": A({"rings": 3, "segments": 14}, "numerical"),
}


def v(p):
    return p["value"] if isinstance(p, dict) and "value" in p else p


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def code_hash() -> str:
    h = hashlib.sha256()
    for f in sorted((Path(__file__).parent).glob("*.py")):
        h.update(f.name.encode() + f.read_bytes())
    for f in ("forms.py", "mesh.py", "sources.py"):
        h.update(f.encode() + (ROOT / "engineering/geometry" / f).read_bytes())
    return h.hexdigest()


def canon(obj) -> bytes:
    return (json.dumps(obj, indent=1, sort_keys=True) + "\n").encode()


# ------------------------------------------------------------------ candidate
def candidate() -> dict:
    spec = F.FORMS_BY_ID[SPEC_ID]
    bio = F.complete_point(spec, F.biological_point(spec), None, profile=M.body_profile)  # corrected, not v1
    daane_pdf = dict(DAANE_PDF)
    return {
        "schema": "frontier.fish3d.candidate/1",
        "id": "fish3d-" + SPEC_ID,
        "label": ("Engineered illustrative flying-fish form at biological scale. Not an organism, not an ancestor, "
                  "not a validated aerodynamic shape."),
        "from_print_form": SPEC_ID,
        "set": spec.set_id, "genus_fits": spec.genus, "mass_kg": spec.mass_kg,
        "nca_comparison": {"branch": "work/nca-glide", "commit": SRC.NCA_CONTROLLED["commit"],
                           "csv_sha256": SRC.NCA_CONTROLLED.get("sha256"), "variant": "A baseline (fS 1.0, fAR 1.0)"},
        "biology": bio,
        "shape_params": spec.params,
        "fidelity": FIDELITY,
        "sources_extra": {"daane2021_pdf": daane_pdf},
        "status_vocabulary": {"functional/derived/measured": "from a source or computed from sourced values",
                              "figure_read": "read off a published figure",
                              "assumed": "our choice, no source", "aesthetic": "appearance only",
                              "numerical": "meshing resolution, no physical meaning",
                              "design_assumption": "a modelling choice stated in its note"},
    }


# ------------------------------------------------------------------ geometry helpers
class Body:
    """The body loft as an analytic surface: x = s SL; y = w(s) cos t; z = h(s) sin t, h = hu above, hd below.
    phi (contract): 0 dorsal, +90 deg left flank (y > 0)  ->  t = 90 deg - phi."""

    def __init__(self, sl, W, hw, flat, ped):
        self.sl, self.W, self.hw, self.flat, self.ped = sl, W, hw, flat, ped

    def f(self, s):
        return M.body_profile(np.clip(np.asarray(s, dtype=float), 0, 1), self.ped)

    def point(self, s, phi):
        s = np.asarray(s, float); t = np.pi / 2 - np.asarray(phi, float)
        f = self.f(s)
        w = self.W * f
        h = np.where(np.sin(t) >= 0, self.W * self.hw * f, self.W * self.hw * self.flat * f)
        return np.stack([s * self.sl, w * np.cos(t), h * np.sin(t)], axis=-1)

    def normal(self, s, phi, eps=1e-4):
        ds = self.point(s + eps, phi) - self.point(s - eps, phi)
        dp = self.point(s, phi + eps) - self.point(s, phi - eps)
        n = np.cross(dp, ds)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        c = self.point(s, phi) - np.stack([np.asarray(s, float) * self.sl, 0 * np.asarray(s, float),
                                            0 * np.asarray(s, float)], axis=-1)
        flip = np.sum(n * c, axis=-1) < 0
        n[flip] *= -1
        return n

    def half_sizes(self, s):
        f = float(self.f([s])[0])
        return self.W * f, self.W * self.hw * f, self.W * self.hw * self.flat * f


def slab_mesh(top: np.ndarray, bottom: np.ndarray, nr: int, nt: int):
    """Closed slab from two (1 + nr*nt, 3) point sets laid out centre-first, ring by ring.  Returns V, T."""
    n = 1 + nr * nt
    V = np.concatenate([top, bottom])
    T = []
    def ring(i, j):
        return 1 + i * nt + (j % nt)
    for off, flip in ((0, False), (n, True)):
        for j in range(nt):
            tri = (off, off + ring(0, j), off + ring(0, j + 1))
            T.append(tri[::-1] if flip else tri)
        for i in range(nr - 1):
            for j in range(nt):
                a, b = off + ring(i, j), off + ring(i, j + 1)
                c, d = off + ring(i + 1, j + 1), off + ring(i + 1, j)
                q = [(a, d, c), (a, c, b)]
                T += [t[::-1] for t in q] if flip else q
    for j in range(nt):
        a, b = ring(nr - 1, j), ring(nr - 1, j + 1)
        T += [(a, a + n, b + n), (a, b + n, b)]
    T = np.array(T)
    tri = V[T]
    vol = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6
    if vol < 0:
        T = T[:, ::-1]
    return V, T


def surface_slab(body: Body, s0, phi0, half_ds, half_dphi, lift_fn, off_mm, thick_mm, nr, nt):
    """A thin closed slab lying on the body surface, centred at (s0, phi0), elliptical in (s, phi)."""
    rho = np.linspace(0, 1, nr + 1)[1:]
    th = np.linspace(0, 2 * np.pi, nt, endpoint=False)
    us = np.concatenate([[0.0], (rho[:, None] * np.cos(th)[None]).ravel()])
    up = np.concatenate([[0.0], (rho[:, None] * np.sin(th)[None]).ravel()])
    s = s0 + half_ds * us; phi = phi0 + half_dphi * up
    P = body.point(s, phi); N = body.normal(s, phi)
    e = off_mm + lift_fn(us)
    return slab_mesh(P + N * (e + thick_mm)[:, None], P + N * e[:, None], nr, nt)


def to_manifold(V, T) -> mf.Manifold:
    m = mf.Manifold(mf.Mesh(vert_properties=np.ascontiguousarray(V, np.float32),
                            tri_verts=np.ascontiguousarray(T, np.uint32)))
    if m.status() != mf.Error.NoError:
        raise ValueError(f"not a manifold: {m.status()}")
    return m


# ------------------------------------------------------------------ components
def build_components(cand: dict) -> tuple[dict, dict, dict, Body]:
    """Return ({id: Manifold in mm}, {id: report}, scales_record, body).  Biological scale: 1 mm = 1 mm."""
    bio, a, fid = cand["biology"], cand["shape_params"], cand["fidelity"]
    res = M.Resolution(stations=v(fid["stations"]), ring=v(fid["ring"]), span_pts=v(fid["span_pts"]),
                       circular=v(fid["circular"]))
    t = v(fid["fin_thickness_mm"]); r_open = v(fid["fin_open_radius_mm"]); r_min = v(fid["body_min_half_size_mm"])
    sl = F._v(bio["standard_length_m"]) * 1000
    W = F._v(bio["body_half_width_max_m"]) * 1000
    hw, flat, ped = F._v(a["body_height_over_width"]), F._v(a["ventral_flattening"]), F._v(a["peduncle_fraction"])
    body = Body(sl, W, hw, flat, ped)
    comps, rep = {}, {}

    s = 0.5 * (1 - np.cos(np.linspace(0, np.pi, res.stations)))
    f = body.f(s)
    comps["body"] = M.loft(s * sl, np.maximum(W * f, r_min), np.maximum(W * hw * f, r_min),
                           np.maximum(W * hw * flat * f, r_min), np.zeros_like(s), res.ring, nose_x=-0.6 * r_min)
    rep["body"] = {"standard_length_mm": A(sl, "derived", "Fish 1990 Cypselurus length fit at 0.05 kg"),
                   "max_half_width_mm": A(W, "derived", "body volume = mass / density with the profile below"),
                   "height_over_width": A(hw, "aesthetic"), "ventral_flattening": A(flat, "aesthetic"),
                   "peduncle_fraction": A(ped, "aesthetic")}

    lay = F._v(bio["fin_layout_bio"]); xf = F._v(bio["fin_x_over_sl"])
    for fin, key in (("pectoral", "pectoral"), ("pelvic", "pelvic")):
        xs = xf[fin]
        w0, hu0, hd0 = body.half_sizes(xs)
        zf = F._v(a[f"{fin}_root_height"])
        z0 = zf * (hu0 if zf >= 0 else hd0)
        y0 = w0 * math.sqrt(max(1 - zf * zf, 0.05))
        L = lay[f"{key}_length_m"] * 1000; Aa = lay[f"{key}_area_per_fin_m2"] * 1e6
        c, cs, area = M.solve_cmax(Aa, L, F._v(a[f"{fin}_base_fraction"]), F._v(a[f"{fin}_s_max"]),
                                   F._v(a[f"{fin}_sweep_deg"]), y0 * 0.9, r_open, res)
        base = F._v(a[f"{fin}_base_fraction"]) * c
        x_le = xs * sl - 0.3 * base
        dih = F._v(a[f"{fin}_dihedral_deg"])
        for side, suf in ((1, "L"), (-1, "R")):
            comps[f"{fin}_{suf}"] = M.place_fin(cs, t, x_le, y0, z0, dih, side)
        rep[f"{fin}_L"] = rep[f"{fin}_R"] = {
            "length_mm": A(L, "derived", "Fish 1990 wing area/span fits split by Table IV share (pectoral) or "
                                         "Daane 2021 S1A pelvic length/SL (Cheilopogon substitution)"),
            "area_target_mm2": A(Aa, "derived"), "area_built_mm2": A(area, "derived"),
            "max_chord_mm": A(c, "derived"), "base_chord_mm": A(base, "derived"),
            "root": A({"x_le": x_le, "y": y0, "z": z0}, "derived"), "x_over_sl": A(xs, "figure_read"),
            "sweep_deg": A(F._v(a[f"{fin}_sweep_deg"]), "aesthetic"), "dihedral_deg": A(dih, "aesthetic"),
            "thickness_mm": fid["fin_thickness_mm"], "section": A("flat plate", "assumed")}

    ped_half = W * hw * ped
    x0, up, lo = F.caudal_lengths(sl, ped_half, a, F._v(bio["hypocaudal_area_m2"]) * 1e6, F._v(bio["hypocaudal_share"]))
    cpoly = M.caudal_planform(x0, ped_half, up, lo, F._v(a["caudal_angle_deg"]), F._v(a["caudal_notch_fraction"]) * up)
    comps["caudal"], c_area = M.xz_plate(cpoly, t, r_open, res.circular)
    ua, la = M.lobe_areas(cpoly)
    rep["caudal"] = {"hypocaudal_area_mm2": A(F._v(bio["hypocaudal_area_m2"]) * 1e6, "derived", "Fish 1990 fit"),
                     "hypocaudal_share_built": A(la / (ua + la), "derived", "target from Fish 1990 Table IV"),
                     "upper_lobe_mm": A(up, "derived"), "lower_lobe_mm": A(lo, "derived"),
                     "fork_angle_deg": A(F._v(a["caudal_angle_deg"]), "aesthetic"), "thickness_mm": fid["fin_thickness_mm"]}

    for sign, (s0, s1), name in ((1, (0.66, 0.84), "dorsal"), (-1, (0.64, 0.80), "anal")):
        _, hu0, hd0 = body.half_sizes(s0); _, hu1, hd1 = body.half_sizes(s1)
        h0 = (hu0 if sign > 0 else hd0) * 0.6; h1 = (hu1 if sign > 0 else hd1) * 0.6
        tip = 0.075 * sl
        poly = np.array([(s0 * sl, sign * h0), (s1 * sl, sign * h1), (s1 * sl + 0.02 * sl, sign * (h1 + tip * 0.45)),
                         (s0 * sl + 0.05 * sl, sign * (h0 + tip))])
        comps[name], ar = M.xz_plate(poly, t, r_open, res.circular)
        rep[name] = {"span_s": A([s0, s1], "aesthetic"), "height_mm": A(tip, "aesthetic"),
                     "area_mm2": A(ar, "derived"), "thickness_mm": fid["fin_thickness_mm"],
                     "note": "same planform as the print forms; not part of the wing area"}

    es = v(fid["eye_s"]); _, hu_e, _ = body.half_sizes(es)
    r_e = v(fid["eye_radius_over_head_half_height"]) * hu_e
    for side, suf in ((1, "L"), (-1, "R")):
        phi = math.radians(70.0) * side
        c = body.point(es, phi); n = body.normal(es, phi)
        centre = c - n * 0.35 * r_e
        comps[f"eye_{suf}"] = mf.Manifold.sphere(r_e, 32).translate(tuple(float(q) for q in centre))
        rep[f"eye_{suf}"] = {"radius_mm": A(r_e, "aesthetic"), "s": fid["eye_s"], "centre_mm": A(centre.tolist(), "derived")}

    s_lo, s_hi = v(fid["operculum_s_range"]); p_lo, p_hi = [math.radians(q) for q in v(fid["operculum_phi_deg"])]
    for side, suf in ((1, "L"), (-1, "R")):
        sc, pc = 0.5 * (s_lo + s_hi), side * 0.5 * (p_lo + p_hi)
        V, T = surface_slab(body, sc, pc, 0.5 * (s_hi - s_lo), 0.5 * (p_hi - p_lo),
                            lambda u: 0.25 * np.clip(u, 0, None), 0.05, v(fid["operculum_thickness_mm"]), 6, 32)
        comps[f"operculum_{suf}"] = to_manifold(V, T)
        rep[f"operculum_{suf}"] = {"s_range": fid["operculum_s_range"], "phi_deg": fid["operculum_phi_deg"],
                                   "thickness_mm": fid["operculum_thickness_mm"],
                                   "note": "gill cover as a thin shell on the head; gill arches not modelled"}

    scales_rec = place_scales(body, fid)
    rings, segs = v(fid["scale_mesh"])["rings"], v(fid["scale_mesh"])["segments"]
    Vs, Ts, off = [], [], 0
    tilt = math.tan(math.radians(v(fid["scale_tilt_deg"])))
    for sc in scales_rec["scales"]:
        r = sc["radius_mm"]
        V, T = surface_slab(body, sc["s"], sc["phi_rad"], r / sl, r / sc["local_radius_mm"],
                            lambda u, r=r: tilt * r * (u + 1), 0.02, v(fid["scale_thickness_mm"]), rings, segs)
        Vs.append(V); Ts.append(T + off); off += len(V)
    comps["scales"] = to_manifold(np.concatenate(Vs), np.concatenate(Ts))
    rep["scales"] = {"count": A(len(scales_rec["scales"]), "derived", "from the assumed lateral count and the lattice"),
                     "lateral_count": fid["scale_lateral_count"], "radius_over_spacing": fid["scale_radius_over_spacing"],
                     "tilt_deg": fid["scale_tilt_deg"], "thickness_mm": fid["scale_thickness_mm"],
                     "growth_link": scales_rec["growth_link"]}
    return comps, rep, scales_rec, body


def place_scales(body: Body, fid: dict) -> dict:
    """Staggered (hexagonal) lattice on the body surface, in arc length.  An ASSUMED pattern: the lattice and its
    count are ours; the per-scale growth time course links to the S1 Erk-wave layer (zebrafish, transfer unknown)."""
    s_lo, s_hi = v(fid["scale_zone_s"])
    n_ll = v(fid["scale_lateral_count"])
    d = (s_hi - s_lo) * body.sl / n_ll
    ratio = v(fid["scale_radius_over_spacing"])
    out = []
    for i in range(n_ll):
        s = s_lo + (i + 0.5) * (s_hi - s_lo) / n_ll
        phis = np.linspace(0, 2 * np.pi, 721)
        pts = body.point(np.full_like(phis, s), phis)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        perim = float(seg.sum())
        n_around = max(6, int(round(perim / d)))
        cum = np.concatenate([[0], np.cumsum(seg)])
        for j in range(n_around):
            arc = (j + 0.5 * (i % 2)) * perim / n_around
            phi = float(np.interp(arc, cum, phis))
            p = body.point(s, phi); n = body.normal(s, phi)
            lr = float(np.linalg.norm(p[1:]))
            r = ratio * min(d, perim / n_around)
            if lr < 2 * r:
                continue
            out.append({"row": i, "col": j, "s": round(float(s), 6), "phi_rad": round(phi, 6),
                        "xyz_mm": [round(float(q), 4) for q in p], "normal": [round(float(q), 6) for q in n],
                        "radius_mm": round(float(r), 4), "local_radius_mm": round(lr, 4)})
    s1 = ROOT / "artifacts/scales/erk-wave/receipt.json"
    return {"spacing_along_mm": d, "scales": out,
            "growth_link": {"status": "assumed transfer",
                            "s1_receipt": "artifacts/scales/erk-wave/receipt.json",
                            "s1_receipt_sha256": sha(s1.read_bytes()) if s1.exists() else None,
                            "meaning": ("each scale's growth time course may be drawn from the S1 Erk-wave model "
                                        "(regenerating zebrafish scale, 520 um); the final radius here is set by "
                                        "the lattice, not by S1")}}


# ------------------------------------------------------------------ outputs
def mesh_arrays(m: mf.Manifold):
    g = m.to_mesh()
    return np.asarray(g.vert_properties[:, :3], np.float64), np.asarray(g.tri_verts, np.int64)


def check(m: mf.Manifold) -> dict:
    V, T = mesh_arrays(m)
    tm = trimesh.Trimesh(V, T, process=False)
    return {"triangles": int(len(T)), "closed_two_manifold": bool(tm.is_watertight),
            "consistently_oriented": bool(tm.is_winding_consistent), "volume_mm3": float(m.volume()),
            "components": int(len(m.decompose())), "bbox_mm": [list(map(float, m.bounding_box()[:3])),
                                                               list(map(float, m.bounding_box()[3:]))]}


def sections(comps: dict, rep: dict) -> dict:
    """2-D cuts of the actual meshes, polygons in metres."""
    def polys(cs: mf.CrossSection):
        return [(np.asarray(p, float) / 1000).round(7).tolist() for p in cs.to_polygons()]
    out = {}
    root = v(rep["pectoral_L"]["root"]); L = v(rep["pectoral_L"]["length_mm"]); dih = math.radians(v(rep["pectoral_L"]["dihedral_deg"]))
    # rotate the dihedral away, then map the spanwise axis (y) onto z and slice at mid-semispan
    fin = comps["pectoral_L"].translate((0, -root["y"], -root["z"])).rotate((-math.degrees(dih), 0, 0))
    fin = fin.transform([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0]])
    cs = fin.slice(0.5 * L)
    out["pectoral_mid"] = {"plane": "pectoral_L, 50% of exposed semispan, normal along the fin span (dihedral removed)",
                           "axes": ["x: chordwise, aft +", "second: fin thickness"], "polygons_m": polys(cs),
                           "chord_m": float((cs.bounds()[2] - cs.bounds()[0]) / 1000)}
    sag = mf.Manifold.batch_boolean([comps[k] for k in ("body", "dorsal", "anal", "caudal")], mf.OpType.Add)
    cs = sag.transform([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0]]).slice(0.0)
    out["body_sagittal"] = {"plane": "y = 0 (midsagittal) through body + dorsal + anal + caudal",
                            "axes": ["x: snout to tail", "z: dorsal"], "polygons_m": polys(cs),
                            "chord_m": float((cs.bounds()[2] - cs.bounds()[0]) / 1000)}
    pl = mf.Manifold.batch_boolean([comps[k] for k in ("body", "pectoral_L", "pectoral_R", "pelvic_L", "pelvic_R")],
                                   mf.OpType.Add).project()
    out["planform"] = {"plane": "projection onto z = 0 of body + pectorals + pelvics (top view)",
                       "axes": ["x: snout to tail", "y: left +"], "polygons_m": polys(pl),
                       "area_m2": float(pl.area() / 1e6)}
    for k in out:
        out[k]["label"] = "2-D cut of the 3-D mesh. Flow on it is a 2-D proxy, not 3-D aerodynamics of the fish."
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "fish3d"))
    ap.add_argument("--daane-pdf", default=None, help="local copy of the Daane 2021 author PDF, checked against the recorded sha256")
    a = ap.parse_args(argv)
    cand = candidate()
    if a.daane_pdf and sha(Path(a.daane_pdf).read_bytes()) != DAANE_PDF["sha256"]:
        raise SystemExit("the local Daane 2021 PDF does not match the recorded sha256")
    cb = canon(cand); csha = sha(cb)
    out = Path(a.out) / cand["id"]
    (out / "components").mkdir(parents=True, exist_ok=True)
    (out / "candidate.json").write_bytes(cb)
    comps, rep, scales_rec, body = build_components(cand)
    checks, files = {}, {}
    scene = trimesh.Scene()
    for cid in COMPONENTS:
        V, T = mesh_arrays(comps[cid])
        tm = trimesh.Trimesh(V / 1000.0, T, process=False)
        checks[cid] = check(comps[cid])
        if cid != "scales":
            p = out / "components" / f"{cid}.stl"
            p.write_bytes(tm.export(file_type="stl"))
            files[f"components/{cid}.stl"] = sha(p.read_bytes())
        # glTF is +Y up (spec 3.4): store (x, z, -y) so any glTF viewer, and Blender's importer, shows dorsal up
        scene.add_geometry(trimesh.Trimesh((V / 1000.0) @ GLTF_FROM_FISH.T, T, process=False),
                           node_name=cid, geom_name=cid)
    glb = scene.export(file_type="glb")
    (out / "fish.glb").write_bytes(glb); files["fish.glb"] = sha(glb)
    comp_json = {"schema": "frontier.fish3d.components/1", "candidate_sha256": csha, "units": "STL and GLB in metres",
                 "frame": "x snout->tail, y left, z dorsal; snout at x = 0 (STL, JSON)",
                 "glb_frame": "glTF +Y up: glb (x, y, z) = fish (x, z, -y); Blender's importer maps it back to fish axes",
                 "components": {cid: {"params": rep[cid], "check": checks[cid],
                                      "stl": None if cid == "scales" else f"components/{cid}.stl",
                                      "stl_sha256": files.get(f"components/{cid}.stl"),
                                      "editable": "change the params in candidate.json (fidelity / shape_params) and rebuild"}
                                for cid in COMPONENTS},
                 "overlap_note": "fin roots are inset into the body, so components overlap; union them before slicing"}
    sc_json = {"schema": "frontier.fish3d.scales/1", "candidate_sha256": csha, **scales_rec,
               "status": "ASSUMED lattice pattern (count, spacing, overlap and tilt are ours); not a grown pattern "
                         "simulation and not a measured scale map"}
    surf = {"schema": "frontier.fish3d.surface_map/1", "candidate_sha256": csha,
            "s": "x / SL, 0 at the snout", "phi": "angle around the body axis, 0 dorsal, +pi/2 left flank",
            "point": "x = s SL; y = w(s) sin(phi); z = h(s) cos(phi), h = h_up for cos(phi) >= 0 else h_down",
            "SL_mm": body.sl, "W_mm": body.W, "height_over_width": body.hw, "ventral_flattening": body.flat,
            "profile": "engineering.geometry.mesh.body_profile(s, peduncle_fraction)", "peduncle_fraction": body.ped,
            "table": [{"s": float(s), "w_mm": float(body.W * body.f([s])[0]),
                       "h_up_mm": float(body.W * body.hw * body.f([s])[0]),
                       "h_down_mm": float(body.W * body.hw * body.flat * body.f([s])[0])}
                      for s in np.linspace(0, 1, 101)]}
    secs = {"schema": "frontier.fish3d.sections/1", "candidate_sha256": csha, **sections(comps, rep)}
    for name, obj in (("components.json", comp_json), ("scales.json", sc_json), ("surface_map.json", surf),
                      ("sections.json", secs)):
        b = canon(obj); (out / name).write_bytes(b); files[name] = sha(b)
    build = {"schema": "frontier.fish3d.build/1", "candidate": "candidate.json", "candidate_sha256": csha,
             "code_sha256": code_hash(), "libraries": {"manifold3d": mf.__version__ if hasattr(mf, "__version__") else "3.5.4",
                                                       "numpy": np.__version__, "trimesh": trimesh.__version__},
             "files": files, "checks": checks,
             "all_closed": all(c["closed_two_manifold"] and c["consistently_oriented"] for c in checks.values())}
    (out / "build.json").write_bytes(canon(build))
    print(json.dumps({"candidate_sha256": csha, "all_closed": build["all_closed"],
                      "triangles": {k: c["triangles"] for k, c in checks.items()},
                      "scales": len(scales_rec["scales"]), "SL_mm": body.sl}, indent=1))
    return 0 if build["all_closed"] else 1


if __name__ == "__main__":
    sys.exit(main())
