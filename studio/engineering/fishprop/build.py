"""Printable display props from the v3 ray-fan fish candidates (ENGINEERED FORM; print preparation UNVALIDATED).

    python -m engineering.fishprop.build [--set v3|v4] [--only FORM] [--min-wall-mm 1.0] [--no-render]

Two sets (SETS).  v3 (artifacts/print-v3, frozen at aaa71f8): v3a and v3b at display scale 0.55.  v4
(artifacts/print-v4): three props from v3c, whose pectoral length is read from Daane S1A, at display scale 0.50 (v3c's
227 mm span does not fit the 120 mm box at 0.55): a display prop, a reinforced prop (1.5 mm wall rule and tapered
fin-root gussets) and a glide-pose prop (v3b's assumed pose knobs on v3c's fins).  v4 adds manufacturing checks to
every file (dense wall sampling, extremity stoutness, mirror symmetry, sliver triangles) and a material-conditioned
mass at the material card's cured density.

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
import itertools
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
from engineering.glider import mass as MP

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = ("a-fan", "b-glide-pose")  # the v3 set's forms
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

# Pose knobs a pose alteration may copy from another candidate.  Fin anatomy (pectoral length source, ray lengths,
# area) and placement (pelvic_x_over_sl) are never copied.
POSE_KNOBS = ("pectoral_lead_angle_deg", "pectoral_dihedral_deg", "pectoral_camber", "pelvic_lead_angle_deg",
              "pelvic_dihedral_deg", "pelvic_camber")
# v4 manufacturing checks (prop mm).  Thresholds are design rules stated here, not printer settings.
DENSE_WALL_SAMPLES, DENSE_WALL_SEED = 12000, 11
TIP_BALL_MM = 3.0          # extremity test: material inside a ball of this radius at each convex-hull vertex ...
TIP_CLUSTER_MM = 2.0       # ... hull vertices closer than this are one extremity
SLIVER_AREA_MM2 = 1e-6     # reported: triangles smaller than this (the validator's degenerate cut is 1e-10)
MIRROR_MAX_FRACTION = 1e-3  # smooth files: volume of (M minus its y-mirror) / volume of M
CLEAN_TOL_MM = 1e-4        # v4: simplify after the grid snap; removes ~1e-5 mm triangles the snap leaves (relief)
# root's material card (the glider's density source), read from the commit that pins it
CARD = {"path": "data/materials/formlabs-studio-2026-10-31.json", "commit": "f1796ec",
        "sha256": "44b6b07f5ff30f5d072a387745383ea08d375b5170f7448c70b7f6482dc72ebc",
        "id": "alpha-grey-v1-default-post-cure", "density_kg_m3": 1220.0}


def form(variant, scale=DISPLAY_SCALE, wall=None, suffix="", short=None, gusset=None, pose_from=None, title=None,
         why=None, trials=None, membrane_over_wall=None) -> dict:
    """One prop: candidate variant, display scale, wall rule (None: the --min-wall-mm value), id suffix,
    root gusset {"factor", "length_mm"} (prop mm), a candidate whose pose knobs replace this one's, and design
    trials that were rejected (kept so the choice can be audited), and a membrane thickness / wall rule other than
    MEMBRANE_OVER_WALL."""
    return {"variant": variant, "scale": scale, "wall": wall, "suffix": suffix, "short": short, "gusset": gusset,
            "pose_from": pose_from, "title": title, "why": why, "trials": trials or [],
            "membrane_over_wall": membrane_over_wall}


SETS = {
    "v3": {"out": "artifacts/print-v3", "manifest_schema": "frontier.print.v3prop-manifest/1",
           "set_id": "fish3d-v3-props", "title": "v3 ray-fan fish display props",
           "note": "one display scale for both, so sizes compare", "checks_v4": False,
           "forms": {"a-fan": form("a-fan", short="v3a prop"), "b-glide-pose": form("b-glide-pose", short="v3b prop")}},
    "v4": {"out": "artifacts/print-v4", "manifest_schema": "frontier.print.v4prop-manifest/1",
           "set_id": "fish3d-v4-props", "title": "v3c (Daane S1A pectoral length) display props",
           "note": "one display scale for every form, so sizes compare; 0.50 because v3c's 227 mm span exceeds the "
                   "120 mm box at the v3 props' 0.55",
           "checks_v4": True,
           "findings": [{
               "id": "relief_degenerate_triangles_before_cleanup", "status": "fixed in these bytes, kept on record",
               "detail": "The first v4 build (not committed) wrote scale-relief STLs that FAILED the validator: 3 "
                         "triangles each under the 1e-10 mm2 degenerate cut (edges ~1e-5 mm, left by the 1e-5 mm "
                         "grid snap), and the build did not gate relief validity. Fixes: the relief file is now gated "
                         "on the validator, and every v4 export is simplified at 1e-4 mm after the snap and snapped "
                         "again (volume change recorded per file). The v3 relief files were not re-exported; their "
                         "smallest triangle is 1.07e-10 mm2, just above the cut."},
               {"id": "glide_pose_prop_failed_dense_wall", "status": "withheld from this set; unresolved",
                "detail": "fish3d-v3c-daane-length-prop-glide-pose (v3b's assumed glide pose on v3c, membrane 1.2 x "
                          "wall) was built and FAILED the 12,000-sample wall gate: minimum 0.975 mm against the 1.0 "
                          "mm rule on its cambered fins (its 3,000-sample minimum was 1.066 mm, a pass). The camber "
                          "is a vertical offset, so a membrane of thickness t measures t cos(slope) across its "
                          "surface. It is not published. A thicker membrane (1.5 x wall) is proposed in V4_PENDING "
                          "and will be built and checked as an additive revision. The frozen v3b prop uses the same "
                          "camber with a 1.2 x membrane; its own 3,000-sample minimum is 1.079 mm."}],
           "forms": {
               "c-display": form("c-daane-length", 0.50, short="v3c prop",
                                 title="Display prop of fish3d-v3c-daane-length",
                                 why="v3c had no prop; same alterations and wall rule as the v3 props"),
               "c-reinforced": form("c-daane-length", 0.50, wall=1.5, suffix="-reinforced", short="v3c reinforced",
                                    gusset={"factor": 0.5, "length_mm": 8.0},
                                    title="Reinforced display prop of fish3d-v3c-daane-length",
                                    why="stronger handling prop: 1.5 mm wall rule (membranes 1.8 mm, rays 3.3 to 2.4 "
                                        "mm) and every fin 1.5 x as thick at its root, tapering to the plain fin 8 mm "
                                        "out, where a cantilevered fin's bending moment is largest",
                                    trials=[{"gusset": {"factor": 1.0, "length_mm": 6.0}, "fins": "all, and paired only",
                                             "result": "rejected: the 12,000-sample wall check found 0.006-0.09 mm "
                                                       "readings where the doubled roots met the body (pectoral root, "
                                                       "caudal peduncle); the 3,000-sample check missed some of them"},
                                            {"gusset": {"factor": 0.5, "length_mm": 8.0}, "fins": "all",
                                             "result": "kept: sampled minimum 1.80 mm (the membrane) at 3,000 and "
                                                       "12,000 samples"}])}},
}

# Not built or published: the first build of this form FAILED its 12,000-sample wall gate (finding in the v4
# manifest).  The 1.5 x membrane below is the proposed fix, to be built and checked as an additive revision.
V4_PENDING = {
    "c-glide-pose": form("c-daane-length", 0.50, suffix="-glide-pose", short="v3c glide pose",
                         pose_from="b-glide-pose", membrane_over_wall=1.5,
                         trials=[{"membrane_over_wall": 1.2,
                                  "result": "rejected: 12,000-sample wall minimum 0.975 mm against the "
                                            "1.0 mm rule on the cambered fins (3,000 samples: 1.066 mm). "
                                            "The camber is a vertical offset, so a membrane of thickness t "
                                            "measures t cos(slope) across its surface"},
                                 {"membrane_over_wall": 1.5, "result": "kept (see validation)"}],
                         title="Glide-pose display prop of fish3d-v3c-daane-length",
                         why="posed alternative: v3b's assumed glide pose (more sweep and dihedral, "
                             "cambered pectorals and pelvics) on v3c's fins; a design assumption, not an "
                             "observed posture"),
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def code_hash() -> str:
    h = hashlib.sha256()
    for rel in sorted([*(f"engineering/fishprop/{p.name}" for p in Path(__file__).parent.glob("*.py")),
                       *(f"engineering/fishv3/{p.name}" for p in (ROOT / "engineering/fishv3").glob("*.py")),
                       "engineering/fish3d/build.py", "engineering/geometry/validate.py",
                       "engineering/geometry/stand.py", "engineering/geometry/render.py",
                       "engineering/geometry/mesh.py", "engineering/geometry/forms.py", "engineering/glider/mass.py"]):
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


def alterations(cand: dict, scale: float, wall: float, spec: dict | None = None) -> tuple[dict, list[dict]]:
    """The candidate with prop thicknesses written back in biological mm (the builder works at 1:1 and the
    result is scaled once), and the list of what changed.  A v4 form can also replace the pose knobs (a design
    assumption) and add root gussets (a manufacturing alteration)."""
    spec = spec or {}
    an = cand["anatomy"]
    mow = spec.get("membrane_over_wall") or MEMBRANE_OVER_WALL
    mem_p = mow * wall
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
         mem_p / (mem_b * scale), "rule": f"{mow} x min wall"
                                          + ("; thicker than the v3 props' 1.2 so the cambered membrane keeps the "
                                             "wall rule across its surface" if mow != MEMBRANE_OVER_WALL else "")},
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
    if spec.get("gusset"):
        g = spec["gusset"]
        rows.append({"what": "fin root gusset", "candidate": "fin thickness uniform up to the body",
                     "prop": f"fin thickness x{1 + g['factor']:g} at the ray roots, tapering linearly to x1 at "
                             f"{g['length_mm']:g} mm from the root line",
                     "note": "every fin; outline, rays and placement unchanged; reinforces the fin-body joint",
                     "status": "manufacturing alteration"})
    if spec.get("pose_from"):
        donor = V3.VARIANTS[spec["pose_from"]]["knobs"]
        for k in POSE_KNOBS:
            alt["knobs"][k] = {"value": donor[k], "status": f"design assumption: pose copied from v3{spec['pose_from']}"
                                                            f" ({V3.KNOB_STATUS[k]} there)"}
        rows.append({"what": "pose", "candidate": {k: V3.v(cand["knobs"][k]) for k in POSE_KNOBS},
                     "prop": {k: donor[k] for k in POSE_KNOBS},
                     "note": f"pose knobs from v3{spec['pose_from']}; ray lengths and fin areas stay v3c's (rays are "
                             "solved in the reference pose); pectoral length source and pelvic position unchanged",
                     "status": "design assumption"})
    return alt, rows


def rim_fin(fan: FN.Fan, circular: int, refine_mm: float, gusset: tuple[float, float] | None = None) -> mf.Manifold:
    """The candidate's fin (same outline, rays and camber) with a rounded rim along its margin.  The candidate bends a
    cambered fin by a vertical offset, which leaves its thickened edge walls vertical while the membrane tilts by up
    to ~25 deg: an acute edge that fails the wall rule.  A rim of tapered-ray construction, laid before the same
    offset, rounds that edge.  The mid-surface is the candidate's.  `gusset` = (factor, length) in the fin's own mm
    scales the fin's thickness by 1 + factor at the root line, tapering to 1 at `length` from it, before the camber."""
    flat = copy.copy(fan)
    flat.camber = 0.0
    r = 0.5 * RIM_OVER_MEMBRANE * fan.membrane_mm
    O = fan.outline()
    parts = [flat.solid(circular, refine_mm)]
    for a, b in zip(O, np.roll(O, -1, axis=0)):
        ends = [mf.Manifold.sphere(r, circular).translate((float(p[0]), float(p[1]), 0.0)) for p in (a, b)]
        parts.append(mf.Manifold.batch_hull(ends))
    if gusset is None:
        m = mf.Manifold.batch_boolean(parts, mf.OpType.Add).refine_to_length(refine_mm)
    else:
        factor, length = gusset
        m = mf.Manifold.batch_boolean(parts, mf.OpType.Add).refine_to_length(min(refine_mm, 0.25 * length))
        m = m.warp_batch(lambda P, a=fan.roots, k=factor, L=length: root_thicken(P, a, k, L))
    f = fan.warp_fn()
    return m.warp_batch(f) if f is not None else m


def root_thicken(P, roots: np.ndarray, factor: float, length: float) -> np.ndarray:
    """z *= 1 + factor * max(0, 1 - d / length), d the in-plane distance from (u, w) to the root polyline."""
    P = np.array(P, dtype=float, copy=True)
    q = P[:, :2]
    d = np.full(len(P), np.inf)
    for a, b in itertools.pairwise(roots):
        ab = b - a
        t = np.clip(((q - a) @ ab) / max(float(ab @ ab), 1e-18), 0, 1)
        d = np.minimum(d, np.linalg.norm(q - (a + t[:, None] * ab), axis=1))
    P[:, 2] *= 1 + factor * np.clip(1 - d / length, 0, None)
    return P


def relief(body, scale: float, s0, phi0, half_ds, half_dphi, lift_fn, height_mm: float) -> mf.Manifold:
    """A slab on the body surface whose underside sits SINK_MM (prop) inside the body everywhere."""
    sink = SINK_MM / scale
    rings, segs = 2, 10
    return B1.to_manifold(*B1.surface_slab(body, s0, phi0, half_ds, half_dphi, lift_fn, -sink,
                                           sink + height_mm / scale, rings, segs))


def prop_arrays(m: mf.Manifold, clean: bool = False):
    """Mesh arrays for the STL.  Vertices are snapped to a WELD_GRID_MM grid first: the reliefs' boolean leaves vertex
    pairs ~1e-6 mm apart that make zero-area slivers, which a float32 weld alone does not merge.  With `clean` (v4)
    the snapped mesh is simplified at CLEAN_TOL_MM and snapped again: the snap itself can leave triangles with ~1e-5 mm
    edges under the validator's 1e-10 mm2 degenerate cut."""
    mesh = m.to_mesh64()
    V = np.round(np.asarray(mesh.vert_properties)[:, :3] / WELD_GRID_MM) * WELD_GRID_MM + 0.0  # + 0.0: no -0.0
    V, T, info = VAL.weld_float32(V, np.asarray(mesh.tri_verts).astype(np.int64))
    info = {**info, "grid_mm": WELD_GRID_MM}
    if not clean:
        return V, T, info
    first = as_manifold(V, T)
    V2, T2, info2 = prop_arrays(first.simplify(CLEAN_TOL_MM))
    return V2, T2, {**info2, "first_pass": info, "clean_simplify_tol_mm": CLEAN_TOL_MM,
                    "clean_volume_change_mm3": float(as_manifold(V2, T2).volume() - first.volume()),
                    "clean_triangles_before_after": [len(T), len(T2)]}


def one_piece(m: mf.Manifold, what: str) -> tuple[mf.Manifold, list[dict]]:
    """Simplified at the stand's tolerance; the union of ~1,300 overlapping reliefs leaves a few zero-volume shells
    where slab edges graze.  Keep the solid, refuse a second piece with volume, and record what was dropped."""
    pieces = sorted(m.simplify(ST.SIMPLIFY_TOL_MM).decompose(), key=lambda q: -abs(q.volume()))
    dropped = [{"volume_mm3": q.volume(), "bounds_mm": [round(b, 3) for b in q.bounding_box()]} for q in pieces[1:]]
    if any(abs(d["volume_mm3"]) > DROP_MAX_MM3 for d in dropped):
        raise ValueError(f"{what}: union has a second piece with volume: {dropped}")
    return pieces[0], dropped


def build_prop(variant: str, wall: float, scale: float, spec: dict | None = None) -> dict:
    """Two solids per prop: `smooth` (body, eyes, membranes and rays; the wall rule is gated on it) and `relief`
    (smooth plus the scale and gill-cover relief; texture below the wall rule by design).  Plus the stand envelope."""
    cand, csha, src = source_candidate(variant)
    spec = spec or {}
    alt, rows = alterations(cand, scale, wall, spec)
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
        g = spec.get("gusset")
        solid = FN.place(rim_fin(fan, V3.v(nm["ray_circular"]), V3.v(nm["camber_refine_mm"]),
                                 (g["factor"], g["length_mm"] / scale) if g else None), *frame)
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


def stand_for(envelope: mf.Manifold, V, T, body, scale: float, wall: float, clean: bool = False):
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
        SV, STt, weld = prop_arrays(m, clean)
        checks = VAL.check(SV, STt, BOX_MM, thickness=True, min_wall_mm=wall)
        checks["float32_weld"] = weld
        attempts.append({"saddle_half_length_mm": half, "ok": checks["ok"],
                         "min_sampled_wall_mm": checks["wall_thickness"]["min_mm"]})
        if checks["ok"]:
            return m, SV, STt, checks, {**info, "attempts": attempts}
    raise ValueError(f"no stand passed the full check: {attempts}")


def as_manifold(V, T) -> mf.Manifold:
    return mf.Manifold(mf.Mesh(vert_properties=V.astype(np.float32), tri_verts=T.astype(np.uint32)))


def extremities(m: mf.Manifold, wall: float) -> dict:
    """At every convex-hull vertex cluster, the material inside a TIP_BALL_MM ball must be at least that of a rod of
    wall-rule diameter and TIP_BALL_MM length: no extremity thinner than the wall rod (no needle tips)."""
    hull = np.asarray(m.hull().to_mesh().vert_properties)[:, :3].astype(np.float64)
    reps: list[np.ndarray] = []
    for q in hull[np.lexsort(hull.T[::-1])]:
        if all(np.linalg.norm(q - r) >= TIP_CLUSTER_MM for r in reps):
            reps.append(q)
    rod = math.pi * (0.5 * wall) ** 2 * TIP_BALL_MM
    ball = mf.Manifold.sphere(TIP_BALL_MM, 48)
    vols = np.array([(m ^ ball.translate(tuple(float(x) for x in q))).volume() for q in reps])
    k = int(np.argmin(vols))
    return {"ball_radius_mm": TIP_BALL_MM, "cluster_mm": TIP_CLUSTER_MM, "hull_vertices": len(hull),
            "extremities_tested": len(reps), "wall_rule_mm": wall, "rod_reference_mm3": rod,
            "min_material_mm3": float(vols[k]), "min_at_mm": [round(float(x), 3) for x in reps[k]],
            "ok": bool(vols[k] >= rod),
            "rule": "material within the ball at each convex-hull extremity >= a rod of wall-rule diameter and "
                    "ball-radius length; a design rule, not a printer limit; extremities inside the hull (e.g. the "
                    "caudal fork's inner corner) are not tested"}


def mirror_fraction(m: mf.Manifold) -> float:
    """Volume of the mesh not covered by its own y-mirror, over its volume (0 for a mirror-symmetric solid)."""
    return float((m - m.mirror((0, 1, 0))).volume() / m.volume())


def manufacturing_checks(V, T, wall: float, mirror_gated: bool, wall_gated: bool) -> dict:
    """v4 checks on the exported triangles.  Dense wall sampling (DENSE_WALL_SAMPLES, a second seed); extremity
    stoutness (at every convex-hull vertex cluster, the material inside a TIP_BALL_MM ball is at least that of a rod
    of wall-rule diameter and TIP_BALL_MM length, so no extremity is thinner than the wall rod: no needle tips);
    mirror symmetry (the right side is the left side mirrored); sliver triangles (reported)."""
    m = as_manifold(V, T)
    tri = V[T].astype(np.float64)
    areas = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    ang = []
    for i in range(3):
        a, b = tri[:, (i + 1) % 3] - tri[:, i], tri[:, (i + 2) % 3] - tri[:, i]
        c = np.einsum("ij,ij->i", a, b) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-30)
        ang.append(np.degrees(np.arccos(np.clip(c, -1, 1))))
    min_ang = np.min(ang, axis=0)
    w = VAL.thickness_samples(V, T, DENSE_WALL_SAMPLES, DENSE_WALL_SEED)
    mirror_frac = mirror_fraction(m)
    out = {
        "dense_wall": {**w, "min_wall_mm_required": wall if wall_gated else None,
                       "ok": (bool(w["min_mm"] is not None and w["min_mm"] >= wall and w["no_hit"] == 0)
                              if wall_gated else None),
                       "scope": "sampled faces only (second, denser sample); a thinner region between samples can "
                                "be missed" + ("" if wall_gated else "; texture file, reported not gated")},
        "extremities": extremities(m, wall),
        "mirror_symmetry": {"fraction": float(mirror_frac), "max_fraction": MIRROR_MAX_FRACTION if mirror_gated else None,
                            "ok": bool(mirror_frac <= MIRROR_MAX_FRACTION) if mirror_gated else None,
                            "meaning": "volume of the mesh not covered by its own y-mirror, over its volume: the "
                                       "right fins are the left fins mirrored" + (
                                           "" if mirror_gated else "; reported only (the scale lattice need not be "
                                                                    "mirror symmetric)")},
        "slivers": {"area_below_mm2": SLIVER_AREA_MM2, "count": int((areas < SLIVER_AREA_MM2).sum()),
                    "min_area_mm2": float(areas.min()), "min_angle_deg": float(min_ang.min()),
                    "count_min_angle_below_1deg": int((min_ang < 1.0).sum()),
                    "note": "reported; the gated degenerate cut is the validator's (area < 1e-10 mm2 or a repeated "
                            "vertex)"},
    }
    out["ok"] = all(v["ok"] is not False for v in (out["dense_wall"], out["extremities"], out["mirror_symmetry"]))
    return out


def conditional_mass(V, T) -> dict:
    p = MP.properties(V, T, CARD["density_kg_m3"])
    return {"density_kg_m3": CARD["density_kg_m3"], "material_id": CARD["id"],
            "card": {k: CARD[k] for k in ("path", "commit", "sha256")}, "volume_mm3": p["volume_mm3"],
            "mass_g": p["mass_g"], "cg_mm": p["cg_mm"],
            "status": "calculated, not weighed: IF printed fully dense in a resin of this cured density (Alpha Grey "
                      "V1 card value); the prop resin is not chosen"}


def lineage(spec: dict, setc: dict) -> dict:
    out = {"builder": "engineering/fishprop/build.py (the v3 prop builder, extended)",
           "builder_parent_commit": "aaa71f8",
           "parent_set": {"path": "artifacts/print-v3/manifest.json",
                          "sha256": sha(ROOT / "artifacts/print-v3/manifest.json"),
                          "note": "v3a and v3b props; read, not rebuilt"}}
    if spec.get("pose_from"):
        c = V3.candidate(spec["pose_from"])
        out["pose_source_candidate"] = {"id": c["id"], "path": f"artifacts/fish3d/{c['id']}/candidate.json",
                                        "sha256": sha(ROOT / "artifacts/fish3d" / c["id"] / "candidate.json"),
                                        "knobs_copied": list(POSE_KNOBS)}
    return out


def build_one(variant: str, out: Path, wall: float, scale: float, render: bool, run: dict, spec: dict | None = None,
              setc: dict | None = None) -> dict:
    spec, setc = spec or form(variant, scale), setc or SETS["v3"]
    v4 = setc["checks_v4"]
    P = build_prop(variant, wall, scale, spec)
    cand, csha, body = P["cand"], P["csha"], P["body"]
    pid = f"{cand['id']}-prop{spec['suffix']}"
    for d in ("stl", "web", "img", "design"):
        (out / d).mkdir(parents=True, exist_ok=True)
    meshes, checks, roundtrip, files = {}, {}, {}, {}
    for kind, suffix, gate in (("smooth", "", wall), ("relief", "-scales", None)):
        V, T, weld = prop_arrays(P[kind], v4)
        c = VAL.check(V, T, BOX_MM, thickness=True, min_wall_mm=gate)
        c["float32_weld"] = weld
        p = out / "stl" / f"{pid}{suffix}.stl"
        stl = VAL.stl_bytes(V, T, f"Delphi Frontier v3 fish prop {pid}{suffix}, units mm")
        p.write_bytes(stl)
        rt = VAL.check(*VAL.read_stl(stl), BOX_MM, thickness=False)
        if v4:
            c["manufacturing"] = manufacturing_checks(V, T, wall, kind == "smooth", kind == "smooth")
            c["mass_conditional"] = conditional_mass(V, T)
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
    stand_m, SV, STt, stand_checks, stand_info = stand_for(P["envelope"], V, T, body, scale, wall, v4)
    stand_path = out / "stl" / f"{pid}-stand.stl"
    stand_path.write_bytes(VAL.stl_bytes(SV, STt, f"Delphi Frontier stand for {pid}, units mm"))
    if v4:
        stand_checks["manufacturing"] = manufacturing_checks(SV, STt, wall, False, True)
        stand_checks["mass_conditional"] = conditional_mass(SV, STt)
    overlap = {k: (P[k] ^ stand_m).volume() for k in ("smooth", "relief")}
    import trimesh
    RV, RT = meshes["relief"]
    files["glb"] = out / "web" / f"{pid}-scales.glb"
    files["glb"].write_bytes(trimesh.Trimesh(RV, RT, process=False).export(file_type="glb"))
    if render:
        files["image"] = out / "img" / f"{pid}-scales.png"
        R.render([(RV, RT, PROP_COLOR)], files["image"],
                 f"{pid}-scales (display scale {scale}; candidate {csha[:12]}; membranes and rays thickened"
                 + (f"; wall rule {wall:g} mm" if v4 else "") + ")")
        files["image_on_stand"] = out / "img" / f"{pid}-on-stand.png"
        R.render([(V, T, PROP_COLOR), (SV, STt, STAND_COLOR)], files["image_on_stand"],
                 f"{pid} (smooth) on its stand")
    sl_b = body.sl
    design = {
        "schema": "frontier.print.v3prop/1", "id": pid, "title": spec["title"] or f"Display prop of {cand['id']}",
        "short": spec["short"] or f"v3{variant[0]} prop", "label": LABEL, "may_not_say": MAY_NOT_SAY,
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
        "unchanged": ["fin outlines, ray counts, ray roots and lengths, branching",
                      "fin placement" + (" (pose: see alterations)" if spec.get("pose_from") else " and pose (knobs)"),
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
    if v4:
        design.update({
            "set": setc["set_id"], "why": spec["why"], "design_trials": spec["trials"], "lineage": lineage(spec, setc),
            "mass_conditional": {k: checks[k]["mass_conditional"] for k in ("smooth", "relief")}
            | {"stand": stand_checks["mass_conditional"]},
            "checks_stated_separately": {
                "smooth": "gated: validator (closed, oriented, one piece, no degenerate triangle, box) + sampled wall "
                          f">= {wall:g} mm (3,000 and {DENSE_WALL_SAMPLES:,} samples) + extremities + mirror symmetry",
                "relief": "gated: validator (incl. no degenerate triangle) + extremities; wall and mirror symmetry "
                          "reported only (texture)",
                "stand": f"gated: validator + sampled wall >= {wall:g} mm (3,000 samples, then every face when the "
                         f"stand has fewer than {DENSE_WALL_SAMPLES:,}) + extremities; symmetry reported"},
            "limitations": [
                "Not printed, sliced, weighed or loaded into PreForm; printer and resin are unknown.",
                ("Wall readings are sampled; a thinner region between samples can be missed. Self-intersection is not "
                "checked."),
                "Mass is calculated from the mesh at the card density; the resin is not chosen.",
                "Membranes and rays are thickened for printing; nicer or stronger geometry is not a biological claim.",
                "Not a flight article: no lift, drag, launch or fin-strength law is applied to a display prop."]
            + (["The pose is v3b's assumed glide pose on v3c's fins: a design assumption, not an observed posture."]
               if spec.get("pose_from") else [])
            + (["The root gussets are a manufacturing reinforcement; the fin-root strength is not computed."]
               if spec.get("gusset") else [])})
    wjson(out / "design" / f"{pid}.json", design)
    return design


def downloads(out: Path, designs: list[dict], run: dict, setc: dict | None = None) -> dict:
    """Same shape as engineering.geometry.build's downloads (frontier.print.downloads/1) so one menu reads both."""
    setc = setc or SETS["v3"]

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
        row = {"id": d["id"], "short": d["short"], "title": d["title"], "set": setc["set_id"],
               "label": d["label"], "source_candidate": d["source_candidate"]["id"],
               "source_candidate_sha256": d["source_candidate"]["sha256"],
               "display_scale": d["display_scale"]["value"], "prop_size_mm": d["validation"]["bounds_mm"]["size"],
               "files": rows, "prop_checks": GB._check_summary(d["validation"]),
               "scale_relief_checks": {**GB._check_summary(d["validation_relief"]),
                                       "relief": d["validation_relief"]["relief"]},
               "stand_checks": GB._check_summary(d["stand"]["validation"])}
        if setc["checks_v4"]:
            row.update(why=d["why"], wall_rule_mm=d["wall_rule"]["min_wall_mm"], lineage=d["lineage"],
                       mass_conditional_g={k: v["mass_g"] for k, v in d["mass_conditional"].items()},
                       mass_density_kg_m3=CARD["density_kg_m3"], mass_material_id=CARD["id"],
                       mass_basis="calculated: mesh volume x the card's cured density; not weighed; resin not chosen")
            for key, v in (("prop_checks", d["validation"]), ("scale_relief_checks", d["validation_relief"]),
                           ("stand_checks", d["stand"]["validation"])):
                row[key]["manufacturing"] = v["manufacturing"]
        forms.append(row)
    limitations = [
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
        "Engineered illustrative forms: not organisms and not a living or bio-printed construct."]
    if setc["checks_v4"]:
        limitations[1] = ("Wall rules are provisional, configurable prop choices (1.0 mm; 1.5 mm for the reinforced "
                          "prop), checked on sampled faces only (3,000 plus 12,000 samples, or every face of a "
                          "mesh with fewer faces); a thinner region between samples can be missed.")
        limitations.append("Masses are calculated from mesh volume at the Alpha Grey V1 card density (1220 kg/m3, "
                           "cured); the prop resin is not chosen and nothing was weighed.")
    return {"schema": "frontier.print.downloads/1", "code_sha256": run["code_sha256"], "base": GB._base(out),
            "sets": {setc["set_id"]: {"title": setc["title"], "note": setc["note"]}},
            "printer_resin": GB.PRINTER_RESIN, "forms": forms, "limitations": limitations}


def comparison(designs: list[dict]) -> list[dict]:
    """The new props beside the v3 props (read from the frozen print-v3 records)."""
    rows = []
    v3 = json.loads((ROOT / "artifacts/print-v3/manifest.json").read_text())["props"]
    for pid, r in sorted(v3.items()):
        rows.append({"id": pid, "set": "fish3d-v3-props", "display_scale": DISPLAY_SCALE, "wall_rule_mm": 1.0,
                     "bounds_mm": r["bounds_mm"], "smooth_volume_mm3": r["volume_mm3"],
                     "smooth_mass_g_at_1220": r["volume_mm3"] * CARD["density_kg_m3"] * 1e-6,
                     "source": "artifacts/print-v3/manifest.json (frozen)"})
    for d in designs:
        rows.append({"id": d["id"], "set": d["set"], "display_scale": d["display_scale"]["value"],
                     "wall_rule_mm": d["wall_rule"]["min_wall_mm"], "bounds_mm": d["validation"]["bounds_mm"]["size"],
                     "smooth_volume_mm3": d["validation"]["signed_volume_mm3"],
                     "smooth_mass_g_at_1220": d["mass_conditional"]["smooth"]["mass_g"],
                     "smooth_min_wall_sampled_mm": min(d["validation"]["wall_thickness"]["min_mm"],
                                                       d["validation"]["manufacturing"]["dense_wall"]["min_mm"]),
                     "source": f"design/{d['id']}.json"})
    return rows


V4_DOC = ROOT / "docs" / "fish-print-v4.md"


def v4_doc(out: Path | None = None) -> str:
    """Human-readable page for the v4 set, generated from its committed records (downloads.json, design/*.json and
    manifest.json); tests compare the committed page with this output."""
    out = out or ROOT / SETS["v4"]["out"]
    dl = json.loads((out / "downloads.json").read_text())
    man = json.loads((out / "manifest.json").read_text())
    L = ["# v3c fish display props (print-v4)", "",
         ("Generated by `python -m engineering.fishprop.build --set v4 --doc` from `artifacts/print-v4/` (manifest "
          f"sha256 `{sha(out / 'manifest.json')}`). Do not edit by hand."), "",
         "**Status.** " + LABEL + " Nothing here has been printed, sliced or weighed. Nicer or stronger geometry is "
         "not a biological claim: the source candidate's sourced and assumed values keep the status they have in "
         "its `candidate.json`.", "",
         "## The props", "",
         ("Both are built from `fish3d-v3c-daane-length` (pectoral length from Daane S1A, *C. furcatus*) at one "
         "display scale, 0.50, so sizes compare. The v3 props used 0.55, but v3c's 227 mm span does not fit the "
         "120 mm box at 0.55."), ""]
    for f in dl["forms"]:
        d = json.loads((out / "design" / f"{f['id']}.json").read_text())
        mc = d["mass_conditional"]
        L += [f"### {f['short']}: `{f['id']}`", "", d["why"] + ".", "",
              (f"- Size {' x '.join(f'{x:.1f}' for x in f['prop_size_mm'])} mm (x along the fish, y span, z height); "
              f"wall rule {f['wall_rule_mm']:g} mm."),
              (f"- Mass if printed fully dense at {CARD['density_kg_m3']:g} kg/m³ (Alpha Grey V1 card, cured; resin "
              f"not chosen): smooth {mc['smooth']['mass_g']:.2f} g, with scales {mc['relief']['mass_g']:.2f} g, "
              f"stand {mc['stand']['mass_g']:.2f} g. Calculated from mesh volume; not weighed."),
              "- Changes from the candidate:"]
        for r in d["alterations"]:
            if r["what"] == "pose":
                L.append("  - **pose** (design assumption): " + ", ".join(
                    f"{k} {r['candidate'][k]} -> {r['prop'][k]}" for k in POSE_KNOBS if r["candidate"][k] != r["prop"][k]))
            else:
                L.append(f"  - {r['what']}: {r['prop']}")
        for t in d.get("design_trials", []):
            what = ", ".join(f"{k} {v}" for k, v in t.items() if k != "result")
            L.append(f"- Design trial ({what}): {t['result']}.")
        L += ["", "| file | kind | bytes | sha256 |", "|---|---|---|---|"]
        for e in f["files"]:
            L.append(f"| `{e['path']}` | {e['kind']} | {e['bytes']:,} | `{e['sha256']}` |")
        L += ["", "| check | smooth | scales | stand |", "|---|---|---|---|"]
        vs = [d["validation"], d["validation_relief"], d["stand"]["validation"]]

        def cell(v, key):
            m = v["manufacturing"]
            if key == "valid":
                return "pass" if (v["closed_two_manifold"] and v["consistently_oriented"] and
                                  v["face_connected_components"] == 1 and v["degenerate_triangles"] == 0 and
                                  v["fits_box"]) else "FAIL"
            x = {"wall3000": (v.get("min_wall_ok"), (v.get("wall_thickness") or {}).get("min_mm")),
                 "wall12000": (m["dense_wall"]["ok"], m["dense_wall"]["min_mm"]),
                 "tips": (m["extremities"]["ok"], m["extremities"]["min_material_mm3"]),
                 "mirror": (m["mirror_symmetry"]["ok"], m["mirror_symmetry"]["fraction"]),
                 "slivers": (None, m["slivers"]["count"])}[key]
            word = {True: "pass", False: "FAIL", None: "reported"}[x[0]]
            return f"{word} ({x[1]:.3g})" if isinstance(x[1], float) else f"{word} ({x[1]})"
        for key, title in (("valid", "closed, oriented, one piece, no degenerate triangle, fits 120 mm"),
                           ("wall3000", "sampled wall, 3,000 samples (min mm)"),
                           ("wall12000", "sampled wall, 12,000 samples (min mm)"),
                           ("tips", f"extremities: least material within {TIP_BALL_MM:g} mm (mm³)"),
                           ("mirror", "mirror symmetry (unmatched volume fraction)"),
                           ("slivers", f"triangles under {SLIVER_AREA_MM2:g} mm² (count)")):
            L.append(f"| {title} | " + " | ".join(cell(v, key) for v in vs) + " |")
        L.append("")
    L += ["## Compared with the earlier props", "",
          "| prop | scale | wall rule | size mm | smooth volume mm³ | smooth mass at 1220 kg/m³ |",
          "|---|---|---|---|---|---|"]
    for r in man["comparison"]:
        L.append(f"| `{r['id']}` | {r['display_scale']} | {r['wall_rule_mm']:g} mm | "
                 f"{' x '.join(f'{x:.1f}' for x in r['bounds_mm'])} | {r['smooth_volume_mm3']:.0f} | "
                 f"{r['smooth_mass_g_at_1220']:.2f} g |")
    L += ["", "## What is checked and what is not", "",
          ("- Smooth file: gated on the validator, the 3,000- and 12,000-sample wall readings, extremities and mirror "
          "symmetry."),
          ("- Scale-relief file: gated on the validator and extremities. Its 0.2–0.4 mm scale relief is texture below "
          "the wall rule by design, so its wall readings and symmetry are reported, not gated."),
          "- Stand: gated on the validator, both wall samples and extremities.",
          *[f"- {x}" for x in dl["limitations"]], "", "## Findings kept on record", "",
          *[f"- **{x['id']}** ({x['status']}): {x['detail']}" for x in man.get("findings", [])], ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=sorted(SETS), default="v3")
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", default=None, help="one form key of the set")
    ap.add_argument("--min-wall-mm", type=float, default=MIN_WALL_MM)
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--doc", action="store_true", help="v4 only: rewrite docs/fish-print-v4.md from the records")
    a = ap.parse_args(argv)
    setc = SETS[a.set]
    if a.doc:
        if a.set != "v4":
            ap.error("--doc is for --set v4")
        V4_DOC.write_text(v4_doc())
        return 0
    if a.only is not None and a.only not in setc["forms"]:
        ap.error(f"--only must be one of {sorted(setc['forms'])}")
    out = Path(a.out or ROOT / setc["out"]).resolve()
    scales = sorted({f["scale"] for f in setc["forms"].values()})
    run = {"code_sha256": code_hash(), "libraries": GB.library_versions(), "min_wall_mm": a.min_wall_mm,
           "display_scale": scales[0] if len(scales) == 1 else scales, "box_mm": BOX_MM,
           "command": "python -m engineering.fishprop.build" + (f" --set {a.set}" if a.set != "v3" else "")
           + (f" --min-wall-mm {a.min_wall_mm:g}" if a.min_wall_mm != MIN_WALL_MM else "")}
    designs = [build_one(f["variant"], out, f["wall"] or a.min_wall_mm, f["scale"], not a.no_render, run, f, setc)
               for k, f in setc["forms"].items() if a.only in (None, k)]
    if a.only is None:
        wjson(out / "downloads.json", downloads(out, designs, run, setc))
        manifest = {"schema": setc["manifest_schema"], "run": run, "label": LABEL,
                    "printer_resin": GB.PRINTER_RESIN,
                    "props": {d["id"]: {"source_candidate_sha256": d["source_candidate"]["sha256"],
                                        "valid": d["validation"]["ok"], "stand_valid": d["stand"]["validation"]["ok"],
                                        "bounds_mm": d["validation"]["bounds_mm"]["size"],
                                        "volume_mm3": d["validation"]["signed_volume_mm3"],
                                        "mesh_sha256": d["validation"]["mesh_sha256"]} for d in designs},
                    "files": {}}
        if setc["checks_v4"]:
            for d in designs:
                manifest["props"][d["id"]].update(
                    manufacturing_ok={k: v["manufacturing"]["ok"] for k, v in (
                        ("smooth", d["validation"]), ("relief", d["validation_relief"]),
                        ("stand", d["stand"]["validation"]))},
                    wall_rule_mm=d["wall_rule"]["min_wall_mm"], display_scale=d["display_scale"]["value"])
            manifest["comparison"] = comparison(designs)
            manifest["findings"] = setc["findings"]
        for p in sorted(out.rglob("*")):
            if p.is_file() and p.name != "manifest.json":
                manifest["files"][str(p.relative_to(out))] = sha(p)
        wjson(out / "manifest.json", manifest)
        if setc["checks_v4"] and a.out is None:
            V4_DOC.write_text(v4_doc(out))
    summary = {d["id"]: {"valid": d["validation"]["ok"], "stand_valid": d["stand"]["validation"]["ok"],
                         "relief_valid": d["validation_relief"]["ok"],
                         "manufacturing_ok": (d["validation"].get("manufacturing") or {}).get("ok"),
                         "relief_manufacturing_ok": (d["validation_relief"].get("manufacturing") or {}).get("ok"),
                         "stand_manufacturing_ok": (d["stand"]["validation"].get("manufacturing") or {}).get("ok"),
                         "bounds_mm": d["validation"]["bounds_mm"]["size"],
                         "min_wall_sampled_mm": d["validation"]["wall_thickness"]["min_mm"],
                         "components": d["validation"]["face_connected_components"],
                         "triangles": d["validation"]["triangles"]} for d in designs}
    print(json.dumps(summary, indent=1))
    ok = all(v["valid"] and v["stand_valid"] and (v["relief_valid"] or not setc["checks_v4"])
             and v["manufacturing_ok"] is not False
             and v["relief_manufacturing_ok"] is not False and v["stand_manufacturing_ok"] is not False
             for v in summary.values())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
