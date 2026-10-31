"""Printable display props from the v3 ray-fan fish candidates (ENGINEERED FORM; print preparation UNVALIDATED).

    python -m engineering.fishprop.build [--only a-fan|b-glide-pose] [--min-wall-mm 1.0] [--no-render]

Each prop is rebuilt from a v3 candidate (engineering.fishv3) after checking that the committed
artifacts/fish3d/<id>/candidate.json is byte-identical to what the code produces.  Fin outlines, ray counts, ray
lengths, branching, placement, pose and body are the candidate's.  What differs is listed in `alterations`, each
with its biological value: one uniform display scale, membranes and rays thickened to a wall rule, and the gill
cover and scales turned into relief sunk into the body so the prop is one solid.  The 1:1 candidate files that CFD,
the fin-ray adapter and the viewer read are not touched; a prop is never a flow input.

Printer and resin are unknown.  The wall rule is a configurable, conservative prop choice, not a printer setting;
nothing here has been sliced or printed.  Run under a capped scope, single-threaded, e.g.
    systemd-run --user --scope -p TasksMax=64 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=1200 \
        --setenv=OMP_NUM_THREADS=1 --setenv=OPENBLAS_NUM_THREADS=1 nice -n 19 python -m engineering.fishprop.build
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from unittest.mock import patch

import manifold3d as mf
import numpy as np

from engineering.fish3d import build as B1
from engineering.fishv3 import build as V3
from engineering.fishv3 import fins as FN
from engineering.geometry import build as GB
from engineering.geometry import mesh as M
from engineering.geometry import render as R
from engineering.geometry import stand as ST
from engineering.geometry import validate as VAL

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = ("a-fan", "b-glide-pose")
DISPLAY_SCALE = 0.55  # prop mm per biological mm; the largest v3 extent (199 mm, v3a span) becomes 109 mm
MIN_WALL_MM = GB.MIN_WALL_MM  # 1.0 mm, provisional prop choice shared with the v1/v2 print forms
BOX_MM = GB.BOX_MM
# Manufacturing alterations, in prop mm.  Wall-like parts are multiples of the wall rule so a stricter rule thickens
# them; relief heights are absolute (they are surface texture, not walls).
MEMBRANE_OVER_WALL = 1.2
RAY_DIAMETER_OVER_WALL = (2.2, 1.6)  # root, tip; rays stand >= 0.2 mm proud of the membrane each side (no grazing joins)
RIM_OVER_MEMBRANE = 1.3              # rounded margin rim diameter / membrane thickness (no acute edge on a cambered fin)
SCALE_RELIEF_MM = 0.20               # anterior edge height above the body; the posterior edge adds the candidate tilt
OPERCULUM_RELIEF_MM = 0.30
SINK_MM = 0.35                        # relief parts reach this far into the body, so nothing overhangs or floats
WELD_GRID_MM = 1e-5                   # vertex snap before welding (10 nm)
DROP_MAX_MM3 = 1e-3                   # a boolean fragment at most this big is dropped (recorded); larger refuses
STAND_CLIP_MM = 22.0                  # half-length of the prop slice the stand cavity is swept from
ENVELOPE_MARGIN_MM = 0.05             # stand envelope clearance above the tallest relief
SADDLE_HALF_LENGTHS_MM = (6.0, 4.5, 3.5)  # stand.py's default first
PROP_COLOR, STAND_COLOR = (0.30, 0.42, 0.62), (0.7, 0.7, 0.66)
LABEL = ("Engineered illustrative flying-fish display prop from a source-conditioned v3 candidate, at display "
         "scale with listed manufacturing alterations. Not an organism, not a validated aerodynamic shape, "
         "print preparation unvalidated (printer and resin unknown).")
MAY_NOT_SAY = ["ready to print on a named printer", "tested print", "validated resin settings", "bioprint",
               "living", "organism", "aerodynamically faithful", "flight-tested", "biological thickness"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def code_hash() -> str:
    h = hashlib.sha256()
    for rel in sorted([*(f"engineering/fishprop/{p.name}" for p in Path(__file__).parent.glob("*.py")),
                       *(f"engineering/fishv3/{p.name}" for p in (ROOT / "engineering/fishv3").glob("*.py")),
                       "engineering/fish3d/build.py", "engineering/geometry/validate.py",
                       "engineering/geometry/stand.py", "engineering/geometry/render.py",
                       "engineering/geometry/mesh.py", "engineering/geometry/forms.py"]):
        h.update(rel.encode() + b"\0" + (ROOT / rel).read_bytes())
    return h.hexdigest()


def wjson(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def source_candidate(variant: str) -> tuple[dict, str, Path]:
    """The committed candidate, refused unless the code reproduces its bytes and its build.json names it."""
    cand = V3.candidate(variant)
    d = ROOT / "artifacts/fish3d" / cand["id"]
    committed = (d / "candidate.json").read_bytes()
    if B1.canon(cand) != committed:
        raise ValueError(f"{cand['id']}: candidate.json differs from what engineering.fishv3 produces")
    csha = hashlib.sha256(committed).hexdigest()
    if json.loads((d / "build.json").read_text())["candidate_sha256"] != csha:
        raise ValueError(f"{cand['id']}: build.json names a different candidate")
    return cand, csha, d


def alterations(cand: dict, scale: float, wall: float) -> tuple[dict, list[dict]]:
    """The candidate with prop thicknesses written back in biological mm (the builder works at 1:1 and the
    result is scaled once), and the list of what changed."""
    an = cand["anatomy"]
    mem_p = MEMBRANE_OVER_WALL * wall
    ray_p = [0.5 * k * wall for k in RAY_DIAMETER_OVER_WALL]
    alt = copy.deepcopy(cand)
    alt["anatomy"]["membrane_thickness_mm"] = V3.A(mem_p / scale, "manufacturing")
    alt["anatomy"]["ray_radius_mm"] = V3.A([r / scale for r in ray_p], "manufacturing")
    mem_b, ray_b = V3.v(an["membrane_thickness_mm"]), V3.v(an["ray_radius_mm"])
    sc_b = V3.v(an["scale_thickness_mm"])
    rows = [
        {"what": "display scale", "candidate": 1.0, "prop": scale,
         "note": "uniform; every length below is the candidate's times this"},
        {"what": "fin membrane thickness (mm)", "candidate": mem_b, "prop": mem_p, "factor_vs_scaled":
         mem_p / (mem_b * scale), "rule": f"{MEMBRANE_OVER_WALL} x min wall"},
        {"what": "fin ray diameter root, tip (mm)", "candidate": [2 * r for r in ray_b],
         "prop": [2 * r for r in ray_p], "factor_vs_scaled": [2 * p / (2 * b * scale) for p, b in zip(ray_p, ray_b)],
         "rule": f"{RAY_DIAMETER_OVER_WALL} x min wall; the lower caudal lobe keeps its x"
                 f"{V3.v(an['caudal_lower_ray_radius_scale'])} ray scale"},
        {"what": "fin margin", "candidate": "membrane edge cut square to the fin plane",
         "prop": f"rounded rim, diameter {RIM_OVER_MEMBRANE} x membrane ({RIM_OVER_MEMBRANE * mem_p:.2f} mm)",
         "note": "same outline; avoids the acute edge a thickened, cambered membrane gets"},
        {"what": "scales", "candidate": f"separate {sc_b} mm shingles floating 0.02 mm off the body",
         "prop": f"relief {SCALE_RELIEF_MM} mm at the anterior edge plus the candidate's tilt, sunk {SINK_MM} mm "
                 "into the body", "note": "same lattice, count, spacing and tilt; fused, so no overhang or loose part"},
        {"what": "gill cover", "candidate": f"{V3.v(an['operculum_thickness_mm'])} mm shell, lifted at its rear edge",
         "prop": f"relief {OPERCULUM_RELIEF_MM} mm plus the candidate's lift, sunk {SINK_MM} mm",
         "note": "same extent on the head"},
        {"what": "assembly", "candidate": "13 overlapping components", "prop": "one boolean union",
         "note": "fin roots and eyes were already inset into the body"},
    ]
    for r in rows:
        r["status"] = "manufacturing alteration"
    return alt, rows


def rim_fin(fan: FN.Fan, circular: int, refine_mm: float) -> mf.Manifold:
    """The candidate's fin (same outline, rays and camber) with a rounded rim along its margin.  The candidate bends a
    cambered fin by a vertical offset, which leaves its thickened edge walls vertical while the membrane tilts by up
    to ~25 deg: an acute edge that fails the wall rule.  A rim of tapered-ray construction, laid before the same
    offset, rounds that edge.  The mid-surface is the candidate's."""
    flat = copy.copy(fan)
    flat.camber = 0.0
    r = 0.5 * RIM_OVER_MEMBRANE * fan.membrane_mm
    O = fan.outline()
    parts = [flat.solid(circular, refine_mm)]
    for a, b in zip(O, np.roll(O, -1, axis=0)):
        ends = [mf.Manifold.sphere(r, circular).translate((float(p[0]), float(p[1]), 0.0)) for p in (a, b)]
        parts.append(mf.Manifold.batch_hull(ends))
    m = mf.Manifold.batch_boolean(parts, mf.OpType.Add).refine_to_length(refine_mm)
    f = fan.warp_fn()
    return m.warp_batch(f) if f is not None else m


def relief(body, scale: float, s0, phi0, half_ds, half_dphi, lift_fn, height_mm: float) -> mf.Manifold:
    """A slab on the body surface whose underside sits SINK_MM (prop) inside the body everywhere."""
    sink = SINK_MM / scale
    rings, segs = 2, 10
    return B1.to_manifold(*B1.surface_slab(body, s0, phi0, half_ds, half_dphi, lift_fn, -sink,
                                           sink + height_mm / scale, rings, segs))


def prop_arrays(m: mf.Manifold):
    """Mesh arrays for the STL.  Vertices are snapped to a WELD_GRID_MM grid first: the reliefs' boolean leaves vertex
    pairs ~1e-6 mm apart that make zero-area slivers, which a float32 weld alone does not merge."""
    mesh = m.to_mesh64()
    V = np.round(np.asarray(mesh.vert_properties)[:, :3] / WELD_GRID_MM) * WELD_GRID_MM + 0.0  # + 0.0: no -0.0
    V, T, info = VAL.weld_float32(V, np.asarray(mesh.tri_verts).astype(np.int64))
    return V, T, {**info, "grid_mm": WELD_GRID_MM}


def one_piece(m: mf.Manifold, what: str) -> tuple[mf.Manifold, list[dict]]:
    """Simplified at the stand's tolerance; the union of ~1,300 overlapping reliefs leaves a few zero-volume shells
    where slab edges graze.  Keep the solid, refuse a second piece with volume, and record what was dropped."""
    pieces = sorted(m.simplify(ST.SIMPLIFY_TOL_MM).decompose(), key=lambda q: -abs(q.volume()))
    dropped = [{"volume_mm3": q.volume(), "bounds_mm": [round(b, 3) for b in q.bounding_box()]} for q in pieces[1:]]
    if any(abs(d["volume_mm3"]) > DROP_MAX_MM3 for d in dropped):
        raise ValueError(f"{what}: union has a second piece with volume: {dropped}")
    return pieces[0], dropped


def build_prop(variant: str, wall: float, scale: float) -> dict:
    """Two solids per prop: `smooth` (body, eyes, membranes and rays; the wall rule is gated on it) and `relief`
    (smooth plus the scale and gill-cover relief; texture below the wall rule by design).  Plus the stand envelope."""
    cand, csha, src = source_candidate(variant)
    alt, rows = alterations(cand, scale, wall)
    comps, rep, fans, srec, body = V3.build_components(alt)
    # identity: the alteration changes thickness only; every ray keeps the candidate's root, length and branching
    src_rays = json.loads((src / "rays.json").read_text())["fins"]
    built = V3.rays_json(fans)
    dev = max(abs(a["length_m"] - b["length_m"]) for f in src_rays for a, b in zip(src_rays[f]["rays"],
                                                                                    built[f]["rays"]))
    if any(len(src_rays[f]["rays"]) != len(built[f]["rays"]) for f in src_rays) or dev > 1e-12:
        raise ValueError(f"{cand['id']}: rays changed under the alteration (max length change {dev} m)")
    an, nm = cand["anatomy"], cand["numerical"]
    k = (scale, scale, scale)
    for cid in V3.FINS:  # replace each fin by its rimmed print version, placed exactly as the candidate places it
        fan, frame, side = fans[cid]
        solid = FN.place(rim_fin(fan, V3.v(nm["ray_circular"]), V3.v(nm["camber_refine_mm"])), *frame)
        comps[cid] = solid if side == 1 else solid.mirror((0, 1, 0))
    structure = mf.Manifold.batch_boolean(
        [comps[c] for c in V3.COMPONENTS if c not in ("scales", "operculum_L", "operculum_R")], mf.OpType.Add)
    tilt = math.tan(math.radians(V3.v(an["scale_tilt_deg"])))
    reliefs = [relief(body, scale, sc["s"], sc["phi_rad"], sc["radius_mm"] / body.sl,
                      sc["radius_mm"] / sc["local_radius_mm"], lambda u, r=sc["radius_mm"]: tilt * r * (u + 1),
                      SCALE_RELIEF_MM) for sc in srec["scales"]]
    s_lo, s_hi = V3.v(rep["operculum_L"]["s_range"])
    p_lo, p_hi = (math.radians(q) for q in V3.v(an["operculum_phi_deg"]))
    for side in (1, -1):
        reliefs.append(relief(body, scale, 0.5 * (s_lo + s_hi), side * 0.5 * (p_lo + p_hi), 0.5 * (s_hi - s_lo),
                              0.5 * (p_hi - p_lo), lambda u: 0.3 * np.clip(u, 0, None), OPERCULUM_RELIEF_MM))
    smooth, drop_s = one_piece(structure.scale(k), cand["id"])
    textured, drop_r = one_piece(mf.Manifold.batch_boolean([structure, *reliefs], mf.OpType.Add).scale(k),
                                 cand["id"] + " relief")
    # the stand's cavity is cut from a smooth envelope (body grown by the tallest relief, plus the fins), so the
    # texture does not cut sub-wall grooves into the saddle and either file drops in
    lift = max(2 * tilt * sc["radius_mm"] for sc in srec["scales"]) * scale
    grow = (SCALE_RELIEF_MM + lift + ENVELOPE_MARGIN_MM) / scale
    st = 0.5 * (1 - np.cos(np.linspace(0, np.pi, V3.v(cand["numerical"]["stations"]))))
    f = body.f(st)
    shell = M.loft(st * body.sl, body.W * f + grow, body.W * body.hw * f + grow,
                   body.W * body.hw * body.flat * f + grow, np.zeros_like(st), V3.v(cand["numerical"]["ring"]),
                   nose_x=-grow, tail_x=body.sl + grow)
    envelope = mf.Manifold.batch_boolean([shell, *(comps[c] for c in V3.FINS)], mf.OpType.Add).scale(k)
    return {"cand": cand, "csha": csha, "rows": rows, "body": body, "smooth": smooth, "relief": textured,
            "envelope": envelope, "dropped": {"smooth": drop_s, "relief": drop_r},
            "relief_heights_mm": [SCALE_RELIEF_MM, SCALE_RELIEF_MM + lift]}


def stand_for(envelope: mf.Manifold, V, T, body, scale: float, wall: float):
    """engineering.geometry.stand on this prop, cut from a slice of the envelope around the prop's volume centroid.
    stand.py's own search samples 1,500 faces; the full check here can still find a lip where a fin root meets the
    saddle end, so shorter saddles are tried until the full check passes.  Every attempt is recorded."""
    cx = float(ST.centroid(V, T)[0])
    bb = envelope.bounding_box()
    w = scale * body.W + 8.0
    clip = mf.Manifold.cube((2 * STAND_CLIP_MM, 2 * w, bb[5] - bb[2] + 2)).translate(
        (cx - STAND_CLIP_MM, -w, bb[2] - 1))
    sl = scale * body.sl

    def hw_at(x):
        return scale * body.half_sizes(x / sl)[0]

    def bottom_at(x):
        return -scale * body.half_sizes(x / sl)[2]
    attempts = []
    for half in SADDLE_HALF_LENGTHS_MM:
        with patch.dict(ST.STAND, {"saddle_half_length_mm": half}):
            try:
                m, info = ST.build_stand(envelope ^ clip, V, T, hw_at, bottom_at)
            except ValueError as e:
                attempts.append({"saddle_half_length_mm": half, "result": str(e)[:200]})
                continue
        SV, STt, weld = prop_arrays(m)
        checks = VAL.check(SV, STt, BOX_MM, thickness=True, min_wall_mm=wall)
        checks["float32_weld"] = weld
        attempts.append({"saddle_half_length_mm": half, "ok": checks["ok"],
                         "min_sampled_wall_mm": checks["wall_thickness"]["min_mm"]})
        if checks["ok"]:
            return m, SV, STt, checks, {**info, "attempts": attempts}
    raise ValueError(f"no stand passed the full check: {attempts}")


def build_one(variant: str, out: Path, wall: float, scale: float, render: bool, run: dict) -> dict:
    P = build_prop(variant, wall, scale)
    cand, csha, body = P["cand"], P["csha"], P["body"]
    pid = f"{cand['id']}-prop"
    for d in ("stl", "web", "img", "design"):
        (out / d).mkdir(parents=True, exist_ok=True)
    meshes, checks, roundtrip, files = {}, {}, {}, {}
    for kind, suffix, gate in (("smooth", "", wall), ("relief", "-scales", None)):
        V, T, weld = prop_arrays(P[kind])
        c = VAL.check(V, T, BOX_MM, thickness=True, min_wall_mm=gate)
        c["float32_weld"] = weld
        p = out / "stl" / f"{pid}{suffix}.stl"
        stl = VAL.stl_bytes(V, T, f"Delphi Frontier v3 fish prop {pid}{suffix}, units mm")
        p.write_bytes(stl)
        rt = VAL.check(*VAL.read_stl(stl), BOX_MM, thickness=False)
        meshes[kind], checks[kind], files[f"stl_{kind}"] = (V, T), c, p
        roundtrip[kind] = {k: rt[k] for k in ("ok", "triangles", "closed_two_manifold", "consistently_oriented",
                                              "face_connected_components", "signed_volume_mm3", "mesh_sha256")}
    w = checks["relief"]["wall_thickness"]
    checks["relief"]["relief"] = {
        "wall_rule_gated": False, "heights_mm": P["relief_heights_mm"],
        "sampled_min_mm": w["min_mm"], "fraction_below_wall": float(w["fraction_below_1mm"]) if wall == 1.0 else None,
        "note": "scale and gill-cover relief is texture, below the wall rule by design; the structure under it is "
                "the smooth file, which is gated, and a union only adds material to it"}
    V, T = meshes["smooth"]
    stand_m, SV, STt, stand_checks, stand_info = stand_for(P["envelope"], V, T, body, scale, wall)
    stand_path = out / "stl" / f"{pid}-stand.stl"
    stand_path.write_bytes(VAL.stl_bytes(SV, STt, f"Delphi Frontier stand for {pid}, units mm"))
    overlap = {k: (P[k] ^ stand_m).volume() for k in ("smooth", "relief")}
    import trimesh
    RV, RT = meshes["relief"]
    files["glb"] = out / "web" / f"{pid}-scales.glb"
    files["glb"].write_bytes(trimesh.Trimesh(RV, RT, process=False).export(file_type="glb"))
    if render:
        files["image"] = out / "img" / f"{pid}-scales.png"
        R.render([(RV, RT, PROP_COLOR)], files["image"],
                 f"{pid}-scales (display scale {scale}; candidate {csha[:12]}; membranes and rays thickened)")
        files["image_on_stand"] = out / "img" / f"{pid}-on-stand.png"
        R.render([(V, T, PROP_COLOR), (SV, STt, STAND_COLOR)], files["image_on_stand"],
                 f"{pid} (smooth) on its stand")
    sl_b = body.sl
    design = {
        "schema": "frontier.print.v3prop/1", "id": pid, "title": f"Display prop of {cand['id']}",
        "short": f"v3{variant[0]} prop", "label": LABEL, "may_not_say": MAY_NOT_SAY,
        "source_candidate": {"id": cand["id"], "path": f"artifacts/fish3d/{cand['id']}/candidate.json",
                             "sha256": csha, "title": cand["title"], "knobs": cand["knobs"],
                             "check": "committed bytes equal engineering.fishv3 output; build.json names this hash; "
                                      "every ray's length is unchanged by the alterations"},
        "cfd_geometry": {"path": f"artifacts/fish3d/{cand['id']}/", "scale": "1:1, metres, unaltered",
                         "note": "flow, the fin-ray adapter and the viewer read the candidate files; this prop is "
                                 "not a flow input"},
        "display_scale": {"value": scale, "meaning": f"1 mm of fish = {scale} mm of prop",
                          "biological_standard_length_mm": sl_b, "prop_standard_length_mm": scale * sl_b,
                          "status": "display choice: the largest v3 extent fits the provisional box"},
        "alterations": P["rows"],
        "unchanged": ["fin outlines, ray counts, ray roots and lengths, branching", "fin placement and pose (knobs)",
                      "body shape, eye and gill-cover positions", "scale lattice, count, spacing and tilt"],
        "printer_resin": GB.PRINTER_RESIN,
        "wall_rule": {"min_wall_mm": wall, "status": "provisional prop choice, configurable with --min-wall-mm; "
                      "not a certified printer or resin setting", "box_mm": BOX_MM,
                      "gated_on": ["smooth prop", "stand"], "not_gated_on": "scale-relief prop (texture)"},
        "variants": {"smooth": {"stl": str(files["stl_smooth"].relative_to(out)),
                                "what": "body, eyes, fin membranes and rays; no scale texture"},
                     "relief": {"stl": str(files["stl_relief"].relative_to(out)),
                                "what": "the smooth prop plus raised scales (same lattice as the candidate) and gill "
                                        "covers"}},
        "validation": checks["smooth"], "validation_relief": checks["relief"],
        "boolean_fragments_dropped": {"max_abs_volume_mm3": DROP_MAX_MM3, **P["dropped"]},
        "stl_roundtrip": roundtrip,
        "stand": {"stl": {"path": str(stand_path.relative_to(out)), "sha256": sha(stand_path)},
                  "validation": stand_checks, "placement": stand_info, "assembly_overlap_mm3": overlap,
                  "note": "separate part; cut from an envelope that clears both prop files; the prop resting "
                          "balanced in the saddle is not tested"},
        "files": {k: {"path": str(p.relative_to(out)), "sha256": sha(p)} for k, p in files.items()},
        "not_checked": ["global self-intersection", "slicing, supports, cups, minima (orientation-dependent)",
                        "resin-specific thin-wall and relief limits",
                        "whether the 0.2-0.4 mm relief resolves on the chosen printer", "physical print",
                        "aerodynamics of the prop"],
        "run": run,
    }
    wjson(out / "design" / f"{pid}.json", design)
    return design


def downloads(out: Path, designs: list[dict], run: dict) -> dict:
    """Same shape as engineering.geometry.build's downloads (frontier.print.downloads/1) so one menu reads both."""
    def entry(kind, rel, units=None):
        p = out / rel
        e = {"kind": kind, "path": rel, "bytes": p.stat().st_size, "sha256": sha(p)}
        return {**e, "units": units} if units else e
    forms = []
    for d in designs:
        f = d["files"]
        rows = [entry("stl_prop", f["stl_smooth"]["path"], "mm"),
                entry("stl_prop_scale_relief", f["stl_relief"]["path"], "mm"),
                entry("stl_stand", d["stand"]["stl"]["path"], "mm"), entry("glb_prop", f["glb"]["path"], "mm")]
        rows += [entry(k, f[n]["path"]) for k, n in (("png_prop", "image"), ("png_on_stand", "image_on_stand"))
                 if n in f]
        rows.append(entry("design_json", f"design/{d['id']}.json"))
        forms.append({"id": d["id"], "short": d["short"], "title": d["title"], "set": "fish3d-v3-props",
                      "label": d["label"], "source_candidate": d["source_candidate"]["id"],
                      "source_candidate_sha256": d["source_candidate"]["sha256"],
                      "display_scale": d["display_scale"]["value"], "prop_size_mm": d["validation"]["bounds_mm"]["size"],
                      "files": rows, "prop_checks": GB._check_summary(d["validation"]),
                      "scale_relief_checks": {**GB._check_summary(d["validation_relief"]),
                                              "relief": d["validation_relief"]["relief"]},
                      "stand_checks": GB._check_summary(d["stand"]["validation"])})
    return {"schema": "frontier.print.downloads/1", "code_sha256": run["code_sha256"], "base": GB._base(out),
            "sets": {"fish3d-v3-props": {"title": "v3 ray-fan fish display props",
                                          "note": "one display scale for both, so sizes compare"}},
            "printer_resin": GB.PRINTER_RESIN, "forms": forms,
            "limitations": [
                ("Print preparation is unvalidated: printer and resin are unknown; nothing has been sliced, loaded "
                 "into PreForm or printed."),
                (f"Minimum wall {run['min_wall_mm']} mm is a provisional, configurable prop choice, checked on "
                 "sampled faces only; a thinner region between samples can be missed."),
                ("Membranes and rays are thickened for printing; they are not biological thickness. Flow and fin-ray "
                 "work use the 1:1 candidate files, not these props."),
                ("The -scales file adds 0.2-0.4 mm scale and gill-cover relief: texture below the wall rule by "
                 "design, not gated by it; whether it resolves depends on the unknown printer. The smooth file is "
                 "the gated one."),
                ("Closed, oriented, single-piece manifold, positive volume and box fit are checked on every file; "
                 "global self-intersection is not checked."),
                "Engineered illustrative forms: not organisms and not a living or bio-printed construct."]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "print-v3"))
    ap.add_argument("--only", choices=VARIANTS, default=None)
    ap.add_argument("--min-wall-mm", type=float, default=MIN_WALL_MM)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    run = {"code_sha256": code_hash(), "libraries": GB.library_versions(), "min_wall_mm": a.min_wall_mm,
           "display_scale": DISPLAY_SCALE, "box_mm": BOX_MM,
           "command": "python -m engineering.fishprop.build" + (f" --min-wall-mm {a.min_wall_mm:g}"
                                                                 if a.min_wall_mm != MIN_WALL_MM else "")}
    designs = [build_one(k, out, a.min_wall_mm, DISPLAY_SCALE, not a.no_render, run)
               for k in VARIANTS if a.only in (None, k)]
    if a.only is None:
        wjson(out / "downloads.json", downloads(out, designs, run))
        manifest = {"schema": "frontier.print.v3prop-manifest/1", "run": run, "label": LABEL,
                    "printer_resin": GB.PRINTER_RESIN,
                    "props": {d["id"]: {"source_candidate_sha256": d["source_candidate"]["sha256"],
                                        "valid": d["validation"]["ok"], "stand_valid": d["stand"]["validation"]["ok"],
                                        "bounds_mm": d["validation"]["bounds_mm"]["size"],
                                        "volume_mm3": d["validation"]["signed_volume_mm3"],
                                        "mesh_sha256": d["validation"]["mesh_sha256"]} for d in designs},
                    "files": {}}
        for p in sorted(out.rglob("*")):
            if p.is_file() and p.name != "manifest.json":
                manifest["files"][str(p.relative_to(out))] = sha(p)
        wjson(out / "manifest.json", manifest)
    summary = {d["id"]: {"valid": d["validation"]["ok"], "stand_valid": d["stand"]["validation"]["ok"],
                         "bounds_mm": d["validation"]["bounds_mm"]["size"],
                         "min_wall_sampled_mm": d["validation"]["wall_thickness"]["min_mm"],
                         "components": d["validation"]["face_connected_components"],
                         "triangles": d["validation"]["triangles"]} for d in designs}
    print(json.dumps(summary, indent=1))
    return 0 if all(v["valid"] and v["stand_valid"] for v in summary.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
