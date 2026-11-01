"""v3a pectoral fin geometry for a fin-ray load: the member, its frame, and chordwise sections.

Source: artifacts/fish3d/fish3d-v3a-fan/{rays,panels,components}.json, built in fish3d v3 (8dc5cc4).
Every file is read only after its sha256 matches the pin below, and the candidate sha256 must agree
across all three files.

Frames:
  fish frame   x snout->tail, y left, z dorsal, metres (components.json "frame").
  fin plane    panels.json fin_plane: origin, e_w = chordwise (+x, the free-stream direction of the
               head-on v1 CFD), e_u = spanwise. Fin-plane normal n = e_w x e_u (dorsal-pointing).
  ray-local    origin at the ray root, e_s along root->tip, normal n, b = n x e_s. The member is
               root (0,0,0), tip (L,0,0) with L = rays.json length_m as an exact decimal, so it meets
               the transfer contract's exact-geometry rule without any rounding of an irrational length.

Only ray 0 is a straight member: rays 1-14 branch (rays.json `branched: true`), and a straight
Euler-Bernoulli member is not their geometry. Ray 0 is also the fin's leading edge (panels.json
leading_edge_m lies on it), which decides its load: the leading-edge suction of a thin plate.
"""
from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import numpy as np

from .contract import canonical_sha

ROOT = Path(__file__).resolve().parents[2]
V3A = ROOT / "artifacts" / "fish3d" / "fish3d-v3a-fan"
FIN = "pectoral_L"
PINS = {  # sha256 of the committed v3a files at 8dc5cc4, read with sha256sum before this was written
    "rays.json": "e644ff48d23e3ab6d616b1bdcbbaea532ed16b36f28970dda5eb75dfa8cb26e8",
    "panels.json": "1f64a9759de289118e22e6a9edc5d76c63e6daef5c4a5b84e294e80021a1d33d",
    "components.json": "5ec2c13d65de88d875c1f8c5bc8f5bd202cf058efed900ebf9ffcf02a09574b7",
    "components/pectoral_L.stl": "220d22253ce104aea9b9be7b23892941e328e7317a19486162f36a2214c309c5",
}
CANDIDATE = "e8c2b666874a0658bf5be95a6603b68463e68dd67ac2c0a0be8728abb7e5763e"
SOURCE_COMMIT = "8dc5cc47c9e3b512f8a838d7e3fa9fde8d8bd2c6"


class GeometryError(RuntimeError):
    pass


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(base: Path = V3A) -> dict:
    got = {name: sha256_file(base / name) for name in PINS}
    for name, pin in PINS.items():
        if got[name] != pin:
            raise GeometryError(f"{name} sha256 {got[name]} != pin {pin}")
    rays = json.loads((base / "rays.json").read_text())
    panels = json.loads((base / "panels.json").read_text())
    comps = json.loads((base / "components.json").read_text())
    for name, doc in (("rays", rays), ("panels", panels), ("components", comps)):
        if doc.get("candidate_sha256") != CANDIDATE:
            raise GeometryError(f"{name}.json candidate {doc.get('candidate_sha256')} != {CANDIDATE}")
    if comps["components"][FIN]["stl_sha256"] != PINS["components/pectoral_L.stl"]:
        raise GeometryError("components.json pectoral_L stl_sha256 does not pin the STL read")
    return {"rays": rays["fins"][FIN], "panels": panels["fins"][FIN], "component": comps["components"][FIN],
            "frame": comps["frame"], "sha256": got}


def fin_plane(g: dict) -> dict:
    fp = g["panels"]["fin_plane"]
    o, eu, ew = (np.array(fp[k], dtype=float) for k in ("origin_m", "e_u", "e_w"))
    n = np.cross(ew, eu)
    n /= np.linalg.norm(n)
    return {"origin": o, "e_u": eu, "e_w": ew, "n": n}


def to_plane(fp: dict, p) -> tuple[float, float]:
    d = np.asarray(p, dtype=float) - fp["origin"]
    return float(d @ fp["e_u"]), float(d @ fp["e_w"])


def ray0(g: dict) -> dict:
    """Ray 0 as a straight member, with the measured straightness and the length discrepancy."""
    r = g["rays"]["rays"][0]
    if r["index"] != 0 or r["branched"] or len(r["polylines_m"]) != 1:
        raise GeometryError("ray 0 must be a single unbranched polyline")
    P = np.array(r["polylines_m"][0], dtype=float)
    axis = P[-1] - P[0]
    e_s = axis / np.linalg.norm(axis)
    off = max(float(np.linalg.norm((p - P[0]) - ((p - P[0]) @ e_s) * e_s)) for p in P)
    fp = fin_plane(g)
    u_tip, w_tip = to_plane(fp, P[-1])
    return {"index": 0, "root_m": P[0], "tip_m": P[-1], "e_s": e_s,
            "L_exact": Fraction(repr(r["length_m"])), "L_polyline_m": float(np.linalg.norm(axis)),
            "max_off_axis_m": off, "sweep_rad": float(np.arctan2(w_tip, u_tip)),
            "tributary_width_m": r["tributary_width_m"], "tributary_area_m2": r["tributary_area_m2"],
            "normal_in_plane_check": float(abs(e_s @ fp["n"]))}


def _chord_interval(outline_uw: np.ndarray, u: float) -> tuple[float, float]:
    """[w_min, w_max] where the line u = const cuts the closed outline polygon (fin plane)."""
    ws = []
    n = len(outline_uw)
    for i in range(n):
        (u1, w1), (u2, w2) = outline_uw[i], outline_uw[(i + 1) % n]
        if (u1 - u) * (u2 - u) <= 0 and u1 != u2:
            ws.append(w1 + (w2 - w1) * (u - u1) / (u2 - u1))
        elif u1 == u2 == u:
            ws += [w1, w2]
    if len(ws) < 2:
        raise GeometryError(f"section u={u} misses the outline")
    return min(ws), max(ws)


def _ray_w_at(fp, polylines, u):
    """Chordwise positions where a (possibly branched) ray crosses the section u = const."""
    out = []
    for pl in polylines:
        uw = [to_plane(fp, p) for p in pl]
        for (u1, w1), (u2, w2) in zip(uw, uw[1:]):
            if (u1 - u) * (u2 - u) <= 0 and u1 != u2:
                out.append(w1 + (w2 - w1) * (u - u1) / (u2 - u1))
    return out


def section(g: dict, s_over_L: float) -> dict:
    """The chordwise section through ray 0 at s/L, in the fin plane (chord along +x, the stream).

    The local tributary of ray 0 is the leading-edge strip from ray 0 back to the midpoint between
    ray 0 and the nearest crossing of ray 1. Ray 0 has no neighbour ahead: it is the leading edge."""
    fp = fin_plane(g)
    r0 = ray0(g)
    p = r0["root_m"] + s_over_L * (r0["tip_m"] - r0["root_m"])
    u, w0 = to_plane(fp, p)
    outline = np.array([to_plane(fp, q) for q in g["panels"]["outline_m"]])
    w_le, w_aft = (float(v) for v in _chord_interval(outline, u))
    c = w_aft - w_le
    ray1 = _ray_w_at(fp, g["rays"]["rays"][1]["polylines_m"], u)
    ahead = [w for w in ray1 if w > w0 + 1e-12]
    if not ahead:
        raise GeometryError(f"ray 1 does not cross section s/L={s_over_L}")
    w1 = min(ahead)
    strip = (w1 - w0) / 2.0 + (w0 - w_le)
    return {"s_over_L": s_over_L, "u_m": u, "w_ray0_m": w0, "w_le_m": w_le, "w_aft_m": w_aft,
            "chord_m": c, "ray0_offset_from_le_m": w0 - w_le, "w_ray1_m": w1,
            "tributary_local_m": (w1 - w0) / 2.0, "xi_strip": strip / c,
            "strip_chordwise_m": strip, "width_per_ds_m": strip * float(np.cos(r0["sweep_rad"]))}


def tributary_v2(g: dict, stations: list[tuple[str, float]]) -> dict:
    """member-pressure/2 tributary block: ray 0's local width at each station, from the pinned geometry.

    `stations` is [(s_m exact string, s/L)]. The width is dA/ds of ray 0's tributary strip: the strip
    is bounded by chordwise lines (u = const), so over ds along the swept ray it covers du = cos(lambda) ds
    of span and dA = (chordwise strip width) cos(lambda) ds. The strip runs from the leading edge (ray 0)
    back to the midpoint between ray 0 and ray 1, as in `section`."""
    widths = [{"s_m": s_m, "width_m": repr(section(g, f)["width_per_ds_m"])} for s_m, f in stations]
    return {"status": "from_geometry", "unit": "m",
            "source": ("ray 0 local strip width per station: (leading edge -> midpoint to ray 1, along the "
                       "chord) * cos(sweep), from panels.json outline_m and rays.json polylines_m"),
            "geometry_sha256": canonical_sha(g["sha256"]), "geometry_files_sha256": g["sha256"],
            "widths": widths, "widths_sha256": canonical_sha(widths)}


def member_json(g: dict) -> dict:
    """The ray-0 member in its exact ray-local frame, with the hashes it is defined from."""
    r0 = ray0(g)
    fp = fin_plane(g)
    frame_def = {"origin_fish_m": r0["root_m"].tolist(), "e_s": r0["e_s"].tolist(), "n": fp["n"].tolist(),
                 "b": np.cross(fp["n"], r0["e_s"]).tolist(), "fish_frame": g["frame"],
                 "rays_sha256": g["sha256"]["rays.json"], "panels_sha256": g["sha256"]["panels.json"]}
    frame_sha = canonical_sha(frame_def)
    m = {"member_id": f"fish3d-v3a/{FIN}/ray0", "frame_id": f"fish3d-v3a/{FIN}/ray0-local@{frame_sha[:16]}",
         "frame_length_unit": "m", "root_m": ["0", "0", "0"], "tip_m": [str(r0["L_exact"]), "0", "0"],
         "frame_definition": frame_def, "frame_sha256": frame_sha,
         "candidate_sha256": CANDIDATE, "source_commit": SOURCE_COMMIT}
    m["member_sha256"] = canonical_sha({k: m[k] for k in ("member_id", "frame_id", "root_m", "tip_m")})
    return m
