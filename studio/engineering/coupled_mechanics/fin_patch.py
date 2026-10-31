"""The resolved local fin-patch case for the v3a leading-edge ray, and its transfer to the contract.

Why a patch: the global 3D CFD (cfd3d v1) carries the 0.10 mm membrane as a 3.7-cell shell at
h = 1.8-7.2 mm, so its fin jumps are smeared and refused. A load on ray 0 needs the pressure on both
faces of a member that the grid actually resolves. The patch is a set of chordwise sections through
ray 0 at the contract's station positions, each resolved to >= 2 cells across the membrane, in
which the membrane, and optionally the ray-0 rod at the leading edge, is a real solid.

What it is not: a 2D section is a strip, so the records it yields are `2d-extrusion` and the
contract refuses them for any `whole_fin_3d` target. The finite-span effect enters only through the
declared alpha_eff (lifting line, assumed). The frozen protocol says so, and the gates do not change
after a result is seen.

Resolution is computed here from the producer's own h_m and thickness_m and never copied from a
producer's claim. EI and the ray section stay UNKNOWN: this module transfers loads, never deflections.
"""
from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np

from engineering.fin_mechanics.load_bridge import Refusal

from . import SCHEMA_PRESSURE, SCHEMA_TARGET
from . import fin_geometry as fg
from . import thin_airfoil as ta
from .contract import MIN_CELLS_ACROSS_MEMBER, parse_member, parse_pressure
from .traction import resultants

PROTOCOL_SCHEMA = "frontier.coupled.fin-patch-protocol/1"
SECTION_SCHEMA = "frontier.coupled.fin-patch-section/1"
# Declared before any patch result, never relaxed after one (same thresholds as cfd3d/windtunnel).
GATES = {
    "resolution_cells_across_membrane_min": MIN_CELLS_ACROSS_MEMBER,
    "grid_pair_rel_diff_max": 0.10,
    "stationarity_rel_change_last_two_windows_max": 0.05,
    "zero_alpha_control_jump_over_alpha_case_max": 0.02,
    "sign": "strip-mean jump p_ventral - p_dorsal > 0 for alpha > 0",
}


def member_target(g: dict, claim: str = "member_scenario") -> dict:
    m = fg.member_json(g)
    return {"schema": SCHEMA_TARGET, **{k: m[k] for k in ("member_id", "frame_id", "frame_length_unit",
                                                          "root_m", "tip_m")},
            "claim": claim, "EI": {"status": "unknown"}, "section": {"status": "unknown"}}


def transfer_load(record: dict, target_json: dict) -> dict:
    """Load-only transfer through the UNCHANGED contract: parse_pressure, then exact resultants."""
    p = parse_pressure(record, parse_member(target_json))
    res = resultants(p["s_m"], p["q_N_per_m"])
    return {"scope": p["scope"], "dimensionality": p["dimensionality"], "evidence_kind": p["evidence_kind"],
            "s_m": [str(x) for x in p["s_m"]], "q_N_per_m": [float(x) for x in p["q_N_per_m"]],
            "F_N": float(res["F_N"]), "M_root_Nm": float(res["M_root_Nm"]),
            "F_exact": str(res["F_N"]), "M_root_exact": str(res["M_root_Nm"]),
            "deflection": "NOT COMPUTED: EI of the v3a ray is unknown (preserved, not filled)",
            "stress": "NOT COMPUTED: ray cross-section (c, I) is unknown (preserved, not filled)"}


def fan_width_gap(ref: dict, transferred: dict) -> dict:
    """Contract load (strip-mean jump x one declared width) against the strip's own load."""
    s = [Fraction(x) for x in transferred["s_m"]]
    q_true = [Fraction(repr(st["q_true_N_per_m"])) for st in ref["stations"]]
    true = resultants(s, q_true)
    Ft, Mt = float(true["F_N"]), float(true["M_root_Nm"])
    return {"F_contract_N": transferred["F_N"], "F_strip_N": Ft,
            "F_contract_over_strip": transferred["F_N"] / Ft,
            "M_contract_over_strip": transferred["M_root_Nm"] / Mt,
            "local_width_chordwise_m": [st["tributary_local_m"] for st in ref["stations"]],
            "declared_width_m": ref["tributary_width_declared_m"],
            "meaning": ("the contract carries one tributary width per member; on a fan the local width "
                        "grows from root to tip, so the contract load moves force toward the root. "
                        "Reported, not corrected: the contract is unchanged")}


def protocol(g: dict | None = None) -> dict:
    """The frozen patch case. Cost figures are this module's arithmetic, not a measured run time."""
    g = g or fg.load()
    ref = ta.reference(g)
    comp = g["component"]["params"]
    t_mem = comp["thickness_mm"]["value"]["membrane"] / 1000.0
    d_ray = comp["thickness_mm"]["value"]["ray_max"] / 1000.0
    h = t_mem / MIN_CELLS_ACROSS_MEMBER
    flow = ref["flow"]
    nu_air = {"value": 1.5e-5, "status": "assumed", "source": "windtunnel protocol air viscosity (declared)"}
    sections = []
    for st in ref["stations"]:
        c = st["chord_m"]
        cells_chord = c / h
        domain = {"upstream_c": 2, "downstream_c": 4, "half_height_c": 2.5}
        n_cells = (domain["upstream_c"] + 1 + domain["downstream_c"]) * cells_chord * 2 * domain["half_height_c"] * cells_chord
        sections.append({
            "station_s_over_L": st["s_over_L"], "chord_m": c, "ray0_at_leading_edge": True,
            "tributary_strip_xi": [0.0, st["xi_strip"]],
            "Re_c_at_declared_U": flow["U_m_s"]["value"] * c / nu_air["value"],
            "cells_along_chord_at_h": cells_chord, "cells_2d_at_h": n_cells,
            "analytic_reference_strip_mean_jump_Pa": st["dp_strip_mean_Pa"]})
    m = fg.member_json(g)
    proto = {
        "schema": PROTOCOL_SCHEMA, "frozen_before_runs": True,
        "purpose": "resolve ray 0's membrane in chordwise sections so the two face pressures exist",
        "inputs": {"source_commit": fg.SOURCE_COMMIT, "candidate_sha256": fg.CANDIDATE, "files_sha256": g["sha256"]},
        "member": {k: m[k] for k in ("member_id", "frame_id", "frame_sha256", "member_sha256", "root_m", "tip_m")},
        "frame_definition": m["frame_definition"],
        "section_geometry": {
            "plane": "fin plane (panels.json fin_plane); chord along e_w = +x, normal n = e_w x e_u (dorsal)",
            "solid": "flat plate of thickness t_membrane over [leading edge, trailing edge] of the outline cut",
            "variants": {"membrane_only": {"t_m": t_mem},
                         "membrane_plus_ray0_rod": {"t_m": t_mem, "rod_diameter_m": d_ray,
                                                    "rod_center": "on the leading edge"}},
            "thickness_status": "assumed (components.json thickness_mm: membrane 0.10, ray_max 0.6; taper unknown)",
            "camber": comp["camber"],
        },
        "flow": {"medium": "air", "rho_kg_m3": flow["rho_kg_m3"], "nu_m2_s": nu_air, "U_m_s": flow["U_m_s"],
                 "alpha_deg": flow["alpha_deg"],
                 "alpha_eff_rad_lifting_line": ref["alpha_eff_rad"], "alpha_eff_status": "assumed (elliptic lifting line on a non-elliptic fan, AR %.2f)" % ref["aspect"]["AR"],
                 "Re_ladder": [1000, "declared-U Re_c per section (see sections)"],
                 "regime_gap": "declared U is unsourced; flight/taxi regimes are not established; no free surface"},
        "grid": {"h_m": h, "h_rule": "coarse h = t_membrane / %d (the resolution gate)" % MIN_CELLS_ACROSS_MEMBER,
                 "h_fine_m": t_mem / 3,
                 "grid_pair": "coarse t/2 and fine t/3 (ratio 1.5); both members of the pair pass the gate, "
                              "so no coarse result is ever an unresolved one; fine costs 2.25x the cells"},
        "controls": {"alpha_zero": "same section at alpha 0; symmetric plate gives a jump near 0",
                     "analytic_reference": "thin-airfoil strip mean (reported ratio, not a pass gate: viscous "
                                           "sections at finite Re are expected to differ)"},
        "gates": GATES,
        "solver_requirements": {
            "owner": "cfd3d (claude-04) chooses the solver; dispatch by infra only",
            "reference_gate": "the solver's own reference gate must be reported; cfd3d C1 sphere is FAILED as of "
                              "Update 1 and that blocks any physical-validation wording",
            "thin_boundary": "resolved solid, >= 2 cells across t_membrane; an immersed-boundary smoothing band "
                             "wider than the plate is NOT resolution"},
        "output_contract": {
            "per_section_file": "case.json + surface rows, cfd3d 10-column float32 layout, one row per wall "
                                "segment of the DORSAL face (normal +n), Cp_plus at +offset n, Cp_minus at "
                                "-(offset + thickness) n, so both faces are sampled outside the wall",
            "case_json_required": ["schema", "station_s_over_L", "member_sha256", "frame_sha256", "candidate_sha256",
                                   "h_m", "thickness_m", "medium", "rho_kg_m3", "U_m_s", "alpha_deg", "Re_c",
                                   "p_ref", "time_window_s", "gates", "solver", "surface_sha256"],
            "transfer": "engineering.coupled_mechanics.fin_patch.record_from_sections -> member-pressure/1 "
                        "(dimensionality 2d-extrusion), contract unchanged",
        },
        "sections": sections,
        "cost_estimate_note": "cells only; run time must be measured on a small case by the solver owner",
        "not_established": ["a 3D fin load (sections are strips)", "EI(x) or the ray section", "flight regime",
                            "any calibrated organism claim"],
    }
    proto["protocol_sha256"] = fg.canonical_sha(proto)
    return proto


def _section(case: dict, surface: np.ndarray, proto: dict) -> dict:
    """Strip-mean jump on ray 0's tributary for one resolved section, with resolution computed here."""
    if case.get("schema") != SECTION_SCHEMA:
        raise Refusal("BAD_SCHEMA", f"section case schema must be {SECTION_SCHEMA}")
    for k in ("member_sha256", "frame_sha256", "candidate_sha256"):
        want = proto["member"].get(k) if k != "candidate_sha256" else proto["inputs"]["candidate_sha256"]
        if case.get(k) != want:
            raise Refusal("GEOMETRY_MISMATCH", f"section {k} {case.get(k)!r} != protocol {want!r}")
    if case.get("medium") in (None, "none"):
        raise Refusal("WRONG_PRESSURE_UNIT", "section has no physical medium; Cp cannot become Pa")
    h, t = float(case["h_m"]), float(case["thickness_m"])
    cells = int(math.floor(t / h + 1e-9))
    st = next(s for s in proto["sections"] if s["station_s_over_L"] == case["station_s_over_L"])
    c = st["chord_m"]
    xi = (surface[:, 0] - surface[:, 0].min()) / c  # chordwise position from the leading edge, plane coords
    strip = (xi >= st["tributary_strip_xi"][0]) & (xi <= st["tributary_strip_xi"][1])
    if strip.sum() < 2:
        raise Refusal("STATION_COVERAGE", "fewer than 2 surface rows inside ray 0's tributary strip")
    ln = surface[strip, 6]
    jump_cp = float(np.sum((surface[strip, 8] - surface[strip, 7]) * ln) / np.sum(ln))
    q = 0.5 * float(case["rho_kg_m3"]) * float(case["U_m_s"]) ** 2
    return {"jump_Pa": jump_cp * q, "cells_across": cells, "time_window_s": case["time_window_s"],
            "case_sha256": fg.canonical_sha(case), "surface_sha256": case["surface_sha256"]}


def record_from_sections(cases: list[dict], surfaces: list[np.ndarray], proto: dict, g: dict | None = None) -> dict:
    """Resolved sections -> frontier.coupled.member-pressure/1, dimensionality 2d-extrusion."""
    g = g or fg.load()
    ref = ta.reference(g)
    L = ref["L_exact"]
    secs = [_section(c, s, proto) for c, s in zip(cases, surfaces)]
    order = sorted(range(len(cases)), key=lambda i: cases[i]["station_s_over_L"])
    t0 = max(float(s["time_window_s"][0]) for s in secs)
    t1 = min(float(s["time_window_s"][1]) for s in secs)
    rec = {"schema": SCHEMA_PRESSURE,
           "source": {"producer": "resolved fin-patch sections (strip theory over ray 0)", "evidence_kind": "simulated",
                      "receipt_sha256": fg.canonical_sha([s["case_sha256"] for s in secs]),
                      "fields_sha256": fg.canonical_sha([s["surface_sha256"] for s in secs]),
                      "geometry_sha256": proto["member"]["member_sha256"],
                      "candidate_sha256": proto["inputs"]["candidate_sha256"],
                      "frame_sha256": proto["member"]["frame_sha256"], "protocol_sha256": proto["protocol_sha256"]},
           "dimensionality": "2d-extrusion",
           "frame": {"id": proto["member"]["frame_id"], "length_unit": "m"},
           "member": {"id": proto["member"]["member_id"], "root_m": proto["member"]["root_m"],
                      "tip_m": proto["member"]["tip_m"], "normal": ["0", "0", "1"]},
           "pressure": {"unit": "Pa", "kind": "dimensional",
                        "reference": "strip-mean (Cp_minus - Cp_plus) * 0.5 rho U^2 over ray 0's tributary"},
           "stations": [{"s_m": str(Fraction(cases[i]["station_s_over_L"]).limit_denominator(1000) * L),
                         "p_pos_Pa": "0", "p_neg_Pa": repr(secs[i]["jump_Pa"])} for i in order],
           "tributary": {"width_m": repr(ref["tributary_width_declared_m"]), "status": "from_geometry",
                         "source": "rays.json ray 0 tributary_width_m (a fan mean)"},
           "time": {"kind": "time_mean", "window_s": [repr(t0), repr(t1)]},
           "resolution": {"cells_across_member_thickness": min(s["cells_across"] for s in secs),
                          "cells_along_member": len(secs)}}
    rec["source"]["pressure_sha256"] = fg.canonical_sha(rec["stations"])
    return rec


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")
