"""Read the returned cfd3d v0.1 3D bundle (job aijob-e00k0jpm34h4na3b99) under the typed contract.

Read-only and bounded: it hashes what it reads, recomputes what the bundle states, and pushes the
pectoral-fin surface samples through `contract.parse_pressure`. It runs no solver and writes only
the inspection JSON.

    python -m engineering.coupled_mechanics.cfd3d_bundle <raw out/ dir> artifacts/coupled-mechanics/cfd3d-v2-inspection.json

What the bundle is, from its own records (each re-read here, not relayed):
- WaterLily 1.10.0, BDIM immersed bodies. Fixed rigid fish, candidate 4a3b912e (not v3a e8c2b666).
- Non-dimensional: medium "none", Cp = (p - p_ref)/(0.5 U^2), grid units.
- Fins are WaterLilyMeshBodies shells. resolved:false, 0.28-0.42 cells across 0.5 mm.
- The C1 sphere reference gate FAILED. That blocks any physical-validation claim.

Nothing here turns these numbers into fin loads, flight loads or a validated field.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

from engineering.fin_mechanics.load_bridge import Refusal

from . import SCHEMA_PRESSURE_V2
from . import fin_geometry as fg
from . import fin_patch as fpch
from .contract import MIN_CELLS_ACROSS_MEMBER, canonical_sha, parse_member, parse_pressure

SCHEMA = "frontier.coupled.cfd3d-bundle-inspection/1"
JOB = "aijob-e00k0jpm34h4na3b99"
# Transport-recorded only: the archive itself is not on this host, so this hash is NOT recomputed here.
ARCHIVE = {"sha256": "30b9fe6143600db8c2e3e536503183704e14e7e98e61223d89021397ec7bfa98", "bytes": 1855111,
           "recorded_in": ["manifest-infra22.json (owned[0].result)", "job.log COPS_RESULT_BEGIN"]}
CASES = ("gpu_fish_L64_Re200", "gpu_fish_L128_Re200", "gpu_fish_L128_Re1000", "gpu_fish_L192_Re1000")
# cfd3d's grid pairs: same Re, two resolutions. Its rule: no convergence claim unless they differ <= 10 %.
PAIRS = (("gpu_fish_L64_Re200", "gpu_fish_L128_Re200"), ("gpu_fish_L128_Re1000", "gpu_fish_L192_Re1000"))
PAIR_RULE = 0.10
FINS = ("pectoral_L", "pectoral_R")
NCOL = 10
# cfd3d contract v0.1 water_20C (cfd3d's recalled standard values, not re-read here)
WATER_20C = {"rho_kg_m3": 998.2, "nu_m2_s": 1.004e-6}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b)


def inventory(out: Path) -> dict:
    return {str(p.relative_to(out)): {"sha256": _sha(p), "bytes": p.stat().st_size}
            for p in sorted(out.rglob("*")) if p.is_file()}


def lineage(out: Path, inv: dict, transport_dir: Path | None) -> dict:
    """Do the bundle's own cross-references agree? Each check is recomputed from files on disk."""
    status = json.loads((out / "status.json").read_text())
    cand = inv["geometry/candidate.json"]["sha256"]
    comps = json.loads((out / "geometry/components.json").read_text())
    checks = {"candidate_json_sha256_is_the_candidate": cand == status["stages"]["geometry"]["candidate"],
              "components_json_names_the_candidate": comps.get("candidate_sha256") == cand}
    for cid in CASES:
        case = json.loads((out / cid / "case.json").read_text())
        checks[f"{cid}: case candidate"] = case["candidate_sha256"] == cand
        checks[f"{cid}: status coeffs == case coeffs"] = status["stages"][f"fish:{cid}"]["coeffs"] == case["coefficients"]
        if "components" in case:
            checks[f"{cid}: STL hashes == components.json"] = all(
                v["stl_sha256"] == comps["components"][k]["stl_sha256"] for k, v in case["components"].items())
        r = out / cid / "render" / "render.json"
        if r.exists():
            rj = json.loads(r.read_text())
            checks[f"{cid}: render.json pins case.json"] = rj["case_json_sha256"] == inv[f"{cid}/case.json"]["sha256"]
    transport = {"archive": ARCHIVE, "archive_present_here": False,
                 "archive_hash_recomputed": False}
    if transport_dir is not None:
        m = json.loads((transport_dir / "manifest-infra22.json").read_text())
        res = next(o["result"] for o in m["owned"] if o["id"] == JOB)
        log = (transport_dir / "results/infra22-cfd3d-geometry-dispatch-repair/job.log").read_text()
        transport.update(manifest_records_it=res["sha256"] == ARCHIVE["sha256"] and res["bytes"] == ARCHIVE["bytes"]
                         and res["truncated"] is False,
                         job_log_records_it=ARCHIVE["sha256"] in log,
                         manifest_sha256=_sha(transport_dir / "manifest-infra22.json"))
    render_inputs_absent = sorted({k for cid in CASES if (out / cid / "render/render.json").exists()
                                   for k in json.loads((out / cid / "render/render.json").read_text())["inputs"]
                                   if not (out / cid / "render" / k).exists() and not (out / cid / k).exists()})
    surf = {cid: sorted(p.name for p in (out / cid / "surface").glob("*.f32")) if (out / cid / "surface").is_dir()
            else [] for cid in CASES}
    return {"checks": checks, "all_agree": all(checks.values()), "transport": transport,
            "surface_files": {cid: len(v) for cid, v in surf.items()},
            "surface_note": "only gpu_fish_L128_Re1000 returned surface samples; the others carry case and forces only",
            "render_inputs_not_in_bundle": len(render_inputs_absent),
            "render_note": "render.json pins its slice inputs by sha256, but the slices are not in the bundle, "
                           "so the videos' frame lineage cannot be re-verified from it (CFD04 owns the videos)"}


def consistency(out: Path) -> dict:
    """Re = U L / nu in grid units, h = L_ref / L_cells, fin cells = t / h, and the resolution flag."""
    rows = {}
    for cid in CASES:
        c = json.loads((out / cid / "case.json").read_text())
        nd, L = c["nondim"], c["case"]["L_cells"]
        U, nu = Fraction(repr(nd["U_grid"])), Fraction(repr(nd["nu_grid"]))
        Re_computed = U * L / nu
        h = c["grid"]["h_m"]
        t_cells = 0.0005 / h
        res = c["resolution"]
        U_water = c["case"]["Re"] * WATER_20C["nu_m2_s"] / nd["L_ref_m"]
        rows[cid] = {
            "L_cells": L, "Re_declared": c["case"]["Re"], "Re_from_U_L_nu": str(Re_computed),
            "Re_consistent": Re_computed == c["case"]["Re"] == nd["Re_L"],
            "h_m": h, "h_equals_L_ref_over_L_cells": math.isclose(h, nd["L_ref_m"] / L, rel_tol=1e-12),
            "fin_cells_recomputed": t_cells,
            "fin_cells_matches_case": math.isclose(t_cells, res["fin_thickness_cells"], rel_tol=1e-9),
            "fins_resolved_declared": res["fins_resolved"],
            "fins_resolved_by_rule": t_cells >= MIN_CELLS_ACROSS_MEMBER,
            "medium": c["medium"], "t_end_reached": c["t_end_reached"], "steps": c["steps"],
            "if_water_20C_U_m_s": U_water,
            "if_water_20C_q_Pa": 0.5 * WATER_20C["rho_kg_m3"] * U_water ** 2,
        }
    L_refs = {json.loads((out / cid / "case.json").read_text())["nondim"]["L_ref_m"] for cid in CASES}
    return {"cases": rows, "one_L_ref_m": len(L_refs) == 1, "L_ref_m": sorted(L_refs),
            "regime": ("Re_L 200 and 1000 in grid units. In water at 20 C that is U 0.9-4.4 mm/s (cfd3d's "
                       "own conversion; medium declared none). Not swimming, taxiing or gliding: air flight "
                       "Re ~1e5 and the free surface are not simulated")}


def forces(out: Path) -> dict:
    """Recompute each case's window mean from its own time series and compare with its coefficients."""
    rows = {}
    for cid in CASES:
        c = json.loads((out / cid / "case.json").read_text())
        f = json.loads((out / cid / "forces.json").read_text())
        t, Fp, Ft = (np.array(f[k], dtype=float) for k in ("t", "F_pressure_grid", "F_total_grid"))
        t0, t1 = c["coefficients"]["avg_window_tUL"]
        w = (t >= t0) & (t <= t1)
        qA = 0.5 * c["nondim"]["U_grid"] ** 2 * c["case"]["L_cells"] ** 2
        got = {"Cd_pressure": -Fp[w, 0].mean() / qA, "Cd_total": -Ft[w, 0].mean() / qA,
               "Cy_total": -Ft[w, 1].mean() / qA, "Cz_total": -Ft[w, 2].mean() / qA}
        rows[cid] = {"recomputed": got, "n_samples": int(w.sum()),
                     "max_rel_diff_vs_case": max(_rel(got[k], c["coefficients"][k]) for k in got),
                     "window_case_json": [t0, t1],
                     "window_field_in_forces_json": f["coefficients"].get("avg_window_tUL"),
                     "forces_json_coeffs_equal_case_otherwise": all(
                         f["coefficients"][k] == c["coefficients"][k] for k in got),
                     "Cd_pressure_final_step": float(-Fp[-1, 0] / qA),
                     "drift_last_half_window": float(_rel(-Fp[w, 0][len(Fp[w]) // 2:].mean() / qA,
                                                          -Fp[w, 0][: len(Fp[w]) // 2].mean() / qA))}
    return rows


def grid_pairs(out: Path) -> list[dict]:
    rows = []
    for a, b in PAIRS:
        ca, cb = (json.loads((out / x / "case.json").read_text()) for x in (a, b))
        keys = ("Cd_total", "Cd_pressure", "Cz_total")
        vs_fine = {k: _rel(ca["coefficients"][k], cb["coefficients"][k]) for k in keys}
        vs_coarse = {k: _rel(cb["coefficients"][k], ca["coefficients"][k]) for k in keys}
        ratio = cb["case"]["L_cells"] / ca["case"]["L_cells"]
        rows.append({"coarse": a, "fine": b, "refinement_ratio": ratio,
                     "rel_diff_vs_fine": vs_fine, "rel_diff_vs_coarse": vs_coarse,
                     "within_cfd3d_10pct_rule": {k: ("yes" if max(vs_fine[k], vs_coarse[k]) <= PAIR_RULE else
                                                     "no" if min(vs_fine[k], vs_coarse[k]) > PAIR_RULE else
                                                     "depends on the denominator") for k in keys},
                     "note": ("a pair within 10 % only permits a convergence statement under cfd3d's rule; it is "
                              "not a convergence proof, and the C1 reference failure still blocks validation")
                     + ("" if ratio == 2 else f"; refinement ratio {ratio:g}, not the rule's L vs L/2")})
    return rows


def closed_face_force(n: np.ndarray, A: np.ndarray, cp: np.ndarray, L_ref_m: float) -> np.ndarray:
    """Pressure force on the body over L_ref^2: -sum Cp n dA / L^2, n outward (cfd3d's body-force sign)."""
    return -(cp[:, None] * n * A[:, None]).sum(0) / L_ref_m ** 2


def _surface(out: Path, cid: str, comp: str, rows_expected: int) -> np.ndarray:
    p = out / cid / "surface" / f"{comp}.f32"
    a = np.fromfile(p, dtype="<f4")
    if a.size != rows_expected * NCOL:
        raise Refusal("BAD_SCHEMA", f"{p.name}: {a.size} floats, case.json says {rows_expected} rows x {NCOL}")
    return a.reshape(-1, NCOL).astype(float)


def surfaces(out: Path, cid: str = "gpu_fish_L128_Re1000") -> dict:
    """Per-component checks, the closed-surface pressure integral against the solver's, fin one-face jumps."""
    c = json.loads((out / cid / "case.json").read_text())
    f = json.loads((out / cid / "forces.json").read_text())
    L = c["nondim"]["L_ref_m"]
    comp_rows, F_sum = {}, np.zeros(3)
    for comp, meta in c["components"].items():
        a = _surface(out, cid, comp, meta["rows"])
        n, A, cpp, cpm, off = a[:, 3:6], a[:, 6], a[:, 7], a[:, 8], a[:, 9]
        closed = meta["thickness_m"] is None
        rule = 2.0 if closed else meta["half_thk_cells"] + 1
        Fc = closed_face_force(n, A, cpp, L)  # every face sampled outside, so a closed integral
        F_sum += Fc
        row = {"rows": int(len(a)), "unit_normals": bool(np.abs(np.linalg.norm(n, axis=1) - 1).max() < 1e-5),
               "closure_sum_nA_over_A": float(np.linalg.norm((n * A[:, None]).sum(0)) / A.sum()),
               "Cp_plus_finite": bool(np.isfinite(cpp).all()),
               "Cp_minus_nan_iff_closed": bool(np.isnan(cpm).all()) if closed else bool(np.isfinite(cpm).all()),
               "offset_cells": [float(off.min()), float(off.max())], "offset_rule_cells": rule,
               "offset_meets_rule": bool(off.min() >= rule - 1e-6), "resolved_declared": meta["resolved"],
               "closed_face_Cp_force_coeff_Lref2": Fc.tolist()}
        if comp in FINS:
            top = n[:, 2] > 0.99  # cfd3d: use one face of the closed plate, else both faces double-count
            jump = cpm[top] - cpp[top]  # below minus above the dorsal-facing face: ventral - dorsal
            row["one_face"] = {"rows": int(top.sum()), "area_m2": float(A[top].sum()),
                               "jump_ventral_minus_dorsal_Cp_area_mean": float((jump * A[top]).sum() / A[top].sum()),
                               "jump_Cp_range": [float(jump.min()), float(jump.max())],
                               "status": "smeared sub-grid shell values (cfd3d's own refusal), not a fin load"}
        comp_rows[comp] = row
    Fp = np.array(f["F_pressure_grid"], dtype=float)
    qA = 0.5 * c["case"]["L_cells"] ** 2
    solver_final = float(-Fp[-1, 0] / qA)
    body = comp_rows["body"]["closed_face_Cp_force_coeff_Lref2"][0]
    return {"case": cid, "components": comp_rows,
            "pressure_drag_from_samples": {"body_only": body, "all_components": float(F_sum[0]),
                                           "solver_Cd_pressure_final_step": solver_final,
                                           "solver_Cd_pressure_window": c["coefficients"]["Cd_pressure"],
                                           "all_components_over_solver_final": float(F_sum[0]) / solver_final},
            "meaning": ("the offset samples (2 cells off the body, 2.9 off the fins, outside the BDIM band) do not "
                        "integrate to the solver's own pressure force, so a load integrated from them is not the "
                        "solver's load, even for the resolved body"),
            "sample_time": "not stated in case.json; forces are compared at the final step and over the window"}


def contract_attempts(out: Path, inv: dict, cid: str = "gpu_fish_L128_Re1000") -> list[dict]:
    """The pectoral_L samples as a member-pressure record for the v3a ray-0 target, as delivered.

    Then a staged chain of COUNTERFACTUAL relabels, each 'fixing' only the previous refusal by
    declaration. It shows that every limit binds on its own, and no stage is a repair of the data.
    The chain must never be accepted."""
    g = fg.load()
    target = parse_member(fpch.member_target(g))
    c = json.loads((out / cid / "case.json").read_text())
    res = c["resolution"]
    rec = {"schema": SCHEMA_PRESSURE_V2,
           "source": {"producer": f"cfd3d v0.1 {cid} surface/pectoral_L.f32 (WaterLily BDIM shell)",
                      "evidence_kind": "simulated", "receipt_sha256": inv[f"{cid}/case.json"]["sha256"],
                      "fields_sha256": inv[f"{cid}/surface/pectoral_L.f32"]["sha256"],
                      "geometry_sha256": inv["geometry/components.json"]["sha256"],
                      "candidate_sha256": c["candidate_sha256"]},
           "dimensionality": "3d",
           "frame": {"id": f"fish3d/{c['candidate_sha256'][:8]}/fish-frame", "length_unit": "m"},
           "member": {"id": f"fish3d/{c['candidate_sha256'][:8]}/pectoral_L", "root_m": None, "tip_m": None,
                      "normal": ["0", "0", "1"]},
           "pressure": {"unit": "Cp", "kind": "nondimensional", "reference": "(p - p_ref)/(0.5 U_grid^2), medium none"},
           "stations": [],
           "tributary": {"status": "from_geometry", "unit": "m", "widths": [], "geometry_sha256": None},
           "time": {"kind": "instantaneous", "window_s": None},
           "resolution": {"cells_across_member_thickness": int(math.floor(res["fin_thickness_cells"])),
                          "cells_along_member": None}}
    tm = fpch.member_target(g)
    stages = [
        ("as delivered", lambda r: None),
        ("declare water_20C Pa (cfd3d's conversion; no values converted, since no stations exist)",
         lambda r: r["pressure"].update(unit="Pa", kind="dimensional")),
        ("relabel the frame as the v3a ray-0 frame", lambda r: r["frame"].update(id=tm["frame_id"])),
        ("relabel the member as v3a ray 0 (candidate differs: 4a3b912e is not e8c2b666)",
         lambda r: r["member"].update(id=tm["member_id"], root_m=tm["root_m"], tip_m=tm["tip_m"])),
        (f"declare {MIN_CELLS_ACROSS_MEMBER} cells across the fin (the bundle has "
         f"{res['fin_thickness_cells']:.3f})",
         lambda r: r["resolution"].update(cells_across_member_thickness=MIN_CELLS_ACROSS_MEMBER)),
        ("declare a time mean (the samples' time is not stated)",
         lambda r: r["time"].update(kind="time_mean", window_s=["3", "4"])),
    ]
    out_rows = []
    for label, edit in stages:
        edit(rec)
        try:
            parse_pressure(json.loads(json.dumps(rec)), target)
            out_rows.append({"stage": label, "verdict": "ACCEPTED"})
        except Refusal as e:
            out_rows.append({"stage": label, "verdict": "refused", "code": e.code, "detail": str(e)})
    out_rows[-1]["after_this"] = ("STATION_COVERAGE is next. Candidate 4a3b912e has no straight ray member, "
                                  "so no stations along v3a ray 0 can be read from this bundle")
    return out_rows


def inspect(out: Path, transport_dir: Path | None = None) -> dict:
    inv = inventory(out)
    status = json.loads((out / "status.json").read_text())
    attempts = contract_attempts(out, inv)
    if any(a["verdict"] == "ACCEPTED" for a in attempts):
        raise AssertionError("a cfd3d v0.1 fin record was accepted; the contract or this reader is broken")
    doc = {"schema": SCHEMA, "job": JOB, "packet_sha256": status["packet_sha256"],
           "inputs": {"files_read_sha256": {k: v["sha256"] for k, v in inv.items()},
                      "inventory_sha256": canonical_sha(inv), "n_files": len(inv)},
           "reference_gate": status["reference_gate"],
           "lineage": lineage(out, inv, transport_dir), "consistency": consistency(out),
           "forces": forces(out), "grid_pairs": grid_pairs(out), "surface": surfaces(out),
           "contract": {"target": "v3a pectoral_L ray 0 (fin_patch.member_target)", "attempts": attempts,
                        "verdict": ("REFUSED at the first gate, and at every later gate when the earlier ones are "
                                    "relabelled. No fin load, ray load or flight load comes from this bundle")},
           "not_established": ["any fin or ray load (fins sub-grid, resolved:false)",
                               "physical validity (C1 sphere reference FAILED)",
                               "grid convergence (pairs reported, not claimed)",
                               "dimensional pressure (medium none)", "the v3a geometry (candidate 4a3b912e)",
                               "flight, taxi or free-surface regime"],
           "solver_runs_by_this_reader": 0,
           "code_sha256": {f"engineering/coupled_mechanics/{m}": _sha(Path(__file__).with_name(m))
                           for m in ("cfd3d_bundle.py", "contract.py", "fin_patch.py", "fin_geometry.py")}}
    return doc


def main(argv):
    out = Path(argv[1])
    dest = Path(argv[2] if len(argv) > 2 else "artifacts/coupled-mechanics/cfd3d-v2-inspection.json")
    transport = out.parent.parent.parent  # .../cfd3d-v2 holds manifest-infra22.json
    doc = inspect(out, transport if (transport / "manifest-infra22.json").exists() else None)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n")
    print(dest, _sha(dest))


if __name__ == "__main__":
    main(sys.argv)
