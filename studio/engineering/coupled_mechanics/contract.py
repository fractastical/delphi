"""Port contract between a flow model and a fin-ray beam, with structured refusals.

A flow model publishes `frontier.coupled.member-pressure/1`:

    {"schema": "frontier.coupled.member-pressure/1",
     "source": {"producer", "evidence_kind": "simulated"|"analytic", "receipt_sha256", "fields_sha256",
                "geometry_sha256"},          # 64-hex each; analytic sources may use null fields/geometry
     "dimensionality": "3d" | "2d-extrusion" | "analytic",
     "frame": {"id": str, "length_unit": "m"},
     "member": {"id": str, "root_m": [x, y, z], "tip_m": [x, y, z], "normal": [nx, ny, nz]},
     "pressure": {"unit": "Pa", "kind": "dimensional", "reference": str},
     "stations": [{"s_m": str, "p_pos_Pa": str, "p_neg_Pa": str}, ...],
     "tributary": {"width_m": str, "status": "declared"|"from_geometry", "source": str},
     "time": {"kind": "static"|"time_mean", "window_s": [a, b] | null},
     "resolution": {"cells_across_member_thickness": int | null, "cells_along_member": int | null}}

`stations[*].s_m` is arc length from the root along the straight member, `p_pos_Pa` is the gauge
pressure on the face the unit `normal` points out of, `p_neg_Pa` the pressure on the opposite face.
The net traction p_neg - p_pos pushes the member along +normal.

All physical numbers are exact decimal/rational strings (floats refused, as in fin_mechanics).
Units are checked, never converted: lattice units, model units or a non-metre frame are refused.
"""
from __future__ import annotations

from fractions import Fraction

from engineering.fin_mechanics.load_bridge import Refusal, exact

from . import SCHEMA_PRESSURE, SCHEMA_TARGET

HEX = set("0123456789abcdef")

# Declared, not derived: a member needs at least this many flow cells across its thickness before a
# face pressure on each side means anything. Fewer cells -> the member is not resolved by the field.
MIN_CELLS_ACROSS_MEMBER = 2


def _hex64(v, name, allow_null=False):
    if v is None and allow_null:
        return None
    if not (isinstance(v, str) and len(v) == 64 and set(v) <= HEX):
        raise Refusal("BAD_HASH", f"{name} must be a 64-hex sha256")
    return v


def _vec(v, name):
    if not (isinstance(v, list) and len(v) == 3):
        raise Refusal("BAD_VECTOR", f"{name} must be a list of 3 exact numbers")
    return tuple(exact(c, f"{name}[{i}]") for i, c in enumerate(v))


def _norm2(v):
    return sum(c * c for c in v)


def _pos(v, name):
    x = exact(v, name)
    if x <= 0:
        raise Refusal("NON_POSITIVE", f"{name} must be > 0, got {x}")
    return x


def parse_target(t: dict) -> dict:
    """frontier.coupled.member-target/1: the straight clamped-free ray the load is applied to."""
    if not isinstance(t, dict) or t.get("schema") != SCHEMA_TARGET:
        raise Refusal("BAD_SCHEMA", f"target schema must be {SCHEMA_TARGET}")
    root, tip = _vec(t.get("root_m"), "target.root_m"), _vec(t.get("tip_m"), "target.tip_m")
    L = _norm2(tuple(b - a for a, b in zip(root, tip)))
    if L == 0:
        raise Refusal("ZERO_LENGTH", "target root == tip")
    ei = t.get("EI") or {}
    lo, hi = _pos(ei.get("lo_Nm2"), "target.EI.lo_Nm2"), _pos(ei.get("hi_Nm2"), "target.EI.hi_Nm2")
    if lo > hi:
        raise Refusal("BAD_EI_RANGE", f"EI lo {lo} > hi {hi}")
    if ei.get("status") not in ("assumed", "context_only", "measured"):
        raise Refusal("EI_STATUS", "target.EI.status must be assumed | context_only | measured")
    section = t.get("section")
    if section is not None:
        section = {"c_m": _pos(section.get("c_m"), "section.c_m"),
                   "I_m4": _pos(section.get("I_m4"), "section.I_m4"),
                   "status": section.get("status", "assumed")}
    if t.get("frame_length_unit") != "m":
        raise Refusal("WRONG_LENGTH_UNIT", f"target.frame_length_unit={t.get('frame_length_unit')!r}, need 'm'")
    return {"id": t.get("member_id"), "frame_id": t.get("frame_id"), "root": root, "tip": tip,
            "L2": L, "EI_lo": lo, "EI_hi": hi, "EI_status": ei["status"], "EI_source": ei.get("source", ""),
            "section": section, "claim": t.get("claim", "member_scenario"),
            "n_elements": int(t.get("n_elements", 64))}


def parse_pressure(rec: dict, target: dict) -> dict:
    """Validate a member-pressure record against the target. Returns stations as exact q(s) [N/m].

    Refusal codes (each a test): BAD_SCHEMA, WRONG_PRESSURE_UNIT, WRONG_LENGTH_UNIT, FRAME_MISMATCH,
    GEOMETRY_MISMATCH, BAD_NORMAL, STATION_COVERAGE, MEMBER_UNRESOLVED, SAGITTAL_2D_NOT_3D, BAD_HASH,
    FLOAT_INPUT, TRIBUTARY_WIDTH, BAD_TIME.
    """
    if not isinstance(rec, dict) or rec.get("schema") != SCHEMA_PRESSURE:
        raise Refusal("BAD_SCHEMA", f"pressure schema must be {SCHEMA_PRESSURE}")
    src = rec.get("source") or {}
    kind = src.get("evidence_kind")
    if kind not in ("simulated", "analytic"):
        raise Refusal("BAD_SOURCE", "source.evidence_kind must be simulated | analytic")
    analytic = kind == "analytic"
    _hex64(src.get("receipt_sha256"), "source.receipt_sha256")
    _hex64(src.get("fields_sha256"), "source.fields_sha256", allow_null=analytic)
    _hex64(src.get("geometry_sha256"), "source.geometry_sha256", allow_null=analytic)

    pr = rec.get("pressure") or {}
    if pr.get("unit") != "Pa" or pr.get("kind") != "dimensional":
        raise Refusal("WRONG_PRESSURE_UNIT",
                      f"pressure must be dimensional Pa, got unit={pr.get('unit')!r} kind={pr.get('kind')!r}; "
                      "lattice or model units are never read as Pa")
    fr = rec.get("frame") or {}
    if fr.get("length_unit") != "m":
        raise Refusal("WRONG_LENGTH_UNIT", f"frame.length_unit={fr.get('length_unit')!r}, need 'm'")
    if fr.get("id") != target["frame_id"]:
        raise Refusal("FRAME_MISMATCH", f"pressure frame {fr.get('id')!r} != target frame {target['frame_id']!r}")

    dim = rec.get("dimensionality")
    if dim not in ("3d", "2d-extrusion", "analytic"):
        raise Refusal("BAD_DIMENSIONALITY", f"dimensionality={dim!r}")
    if dim == "analytic" and not analytic:
        raise Refusal("BAD_DIMENSIONALITY", "a simulated source cannot declare dimensionality 'analytic'")
    if target["claim"] == "whole_fin_3d" and dim != "3d":
        raise Refusal("SAGITTAL_2D_NOT_3D",
                      f"target claims whole_fin_3d but the field is {dim!r}; a 2D section is not a 3D fin")

    m = rec.get("member") or {}
    if m.get("id") != target["id"]:
        raise Refusal("GEOMETRY_MISMATCH", f"member id {m.get('id')!r} != target {target['id']!r}")
    root, tip = _vec(m.get("root_m"), "member.root_m"), _vec(m.get("tip_m"), "member.tip_m")
    if root != target["root"] or tip != target["tip"]:
        raise Refusal("GEOMETRY_MISMATCH",
                      "member root/tip must equal the target's exactly; a load integrated over other geometry "
                      "is not this member's load")
    normal = _vec(m.get("normal"), "member.normal")
    axis = tuple(b - a for a, b in zip(root, tip))
    if _norm2(normal) != 1 or sum(a * n for a, n in zip(axis, normal)) != 0:
        raise Refusal("BAD_NORMAL", "member.normal must be an exact unit vector perpendicular to the member")

    res = rec.get("resolution") or {}
    across = res.get("cells_across_member_thickness")
    if not analytic:
        if across is None or not isinstance(across, int) or across < MIN_CELLS_ACROSS_MEMBER:
            raise Refusal("MEMBER_UNRESOLVED",
                          f"cells_across_member_thickness={across!r} < {MIN_CELLS_ACROSS_MEMBER} (declared minimum): "
                          "the field does not resolve the member, so its two face pressures are not defined")

    t = rec.get("time") or {}
    if t.get("kind") not in ("static", "time_mean"):
        raise Refusal("BAD_TIME", "time.kind must be static | time_mean (concurrent coupling is not supported)")
    if t.get("kind") == "time_mean":
        w = t.get("window_s")
        if not (isinstance(w, list) and len(w) == 2 and exact(w[0], "t0") < exact(w[1], "t1")):
            raise Refusal("BAD_TIME", "time_mean needs window_s [t0, t1] with t0 < t1")

    trib = rec.get("tributary") or {}
    if trib.get("status") not in ("declared", "from_geometry"):
        raise Refusal("TRIBUTARY_WIDTH", "tributary.status must be declared | from_geometry")
    width = _pos(trib.get("width_m"), "tributary.width_m")

    st = rec.get("stations")
    if not isinstance(st, list) or len(st) < 2:
        raise Refusal("STATION_COVERAGE", "need >= 2 stations")
    s = [exact(x.get("s_m"), f"stations[{i}].s_m") for i, x in enumerate(st)]
    # The target length is compared squared so no square root (and no rounding) enters the check.
    if s[0] != 0 or s[-1] * s[-1] != target["L2"] or any(b <= a for a, b in zip(s, s[1:])):
        raise Refusal("STATION_COVERAGE",
                      "stations must start at s=0, end exactly at the target length and increase strictly")
    jump = [exact(x.get("p_neg_Pa"), f"stations[{i}].p_neg_Pa") - exact(x.get("p_pos_Pa"), f"stations[{i}].p_pos_Pa")
            for i, x in enumerate(st)]
    q = [j * width for j in jump]  # Pa * m = N/m, exact
    return {"s_m": s, "jump_Pa": jump, "q_N_per_m": q, "width_m": width, "L_m": s[-1],
            "dimensionality": dim, "evidence_kind": kind, "source": src, "time": t,
            "scope": ("3d member traction" if dim == "3d" else
                      "2d-extrusion section scenario: not a finite 3D fin" if dim == "2d-extrusion" else
                      "analytic pressure: adapter check only, no flow model")}


def as_fraction_list(xs) -> list[str]:
    return [str(Fraction(x)) for x in xs]
