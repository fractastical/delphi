"""Read the actual completed 2D wind-tunnel receipt and try to couple it to a fin member.

Source: engineering/windtunnel baseline run (N1-cypselurus-baseline, 24 cells per body length,
Re 80, U = 0.008 m/s, air), artifacts/windtunnel/baseline/{result.json, fields.npz}. The byte pins
are checked against the receipt and against artifacts/windtunnel/simulation-manifest.json before
any value is read.

Physical pressure, from the receipt's own unit statement (never re-derived):
    p [Pa above freestream] = rho_phys * (U_phys / U_lattice)^2 * (rho_lattice - 1) / 3

What this field can and cannot give a fin ray:
  * it is a sagittal x-z projection extruded infinitely in span, so a pectoral ray (whose axis runs
    in span) is not in it at all;
  * the only in-plane strip with fluid on both faces is the caudal region, columns 52-54 of the
    ROI at row 35, one lattice cell thick. Its record is built from the actual cells and handed to
    the contract, which refuses it (MEMBER_UNRESOLVED). The refusal, not a number, is the result.
"""
from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import numpy as np

from . import SCHEMA_PRESSURE, SCHEMA_TARGET

ROOT = Path(__file__).resolve().parents[2]
RECEIPT_DIR = ROOT / "artifacts" / "windtunnel" / "baseline"
MANIFEST = ROOT / "artifacts" / "windtunnel" / "simulation-manifest.json"
# ROI index of the tail strip (one solid cell at row 35 in each of columns 52, 53, 54), found by
# printing the mask; test_coupled_mechanics_windtunnel re-derives it from the mask.
TAIL_COLUMNS = (52, 53, 54)
TAIL_ROW = 35


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class ReceiptError(RuntimeError):
    pass


def load(receipt_dir: Path = RECEIPT_DIR, manifest: Path = MANIFEST) -> dict:
    res_path, f_path = receipt_dir / "result.json", receipt_dir / "fields.npz"
    res = json.loads(res_path.read_text())
    pins = json.loads(manifest.read_text())
    files = pins["outputs"]
    rel = receipt_dir.name
    got = {"result": sha256_file(res_path), "fields": sha256_file(f_path)}
    if got["fields"] != res.get("fields_sha256"):
        raise ReceiptError(f"fields.npz sha256 {got['fields']} != receipt fields_sha256")
    for k, name in (("result", "result.json"), ("fields", "fields.npz")):
        pin = files.get(f"{rel}/{name}", {}).get("sha256")
        if pin != got[k]:
            raise ReceiptError(f"{rel}/{name} sha256 {got[k]} != manifest pin {pin}")
    if res.get("status") != "SIMULATED_PENDING_REFINEMENT" or res.get("failure") is not None:
        raise ReceiptError(f"receipt status {res.get('status')!r}, failure {res.get('failure')!r}")
    d = np.load(f_path)
    req = res["request_echo"]
    factor = req["density_kg_m3"] * (req["speed_m_s"] / res["lattice_speed"]) ** 2 / 3.0
    conv = d["convective_time"]
    window = conv >= 0.8 * req["convective_time"] - 1e-12
    p_mean = factor * (d["rho"][window].astype(np.float64) - 1.0).mean(axis=0)
    return {"result": res, "sha256": got, "solid": d["solid"], "x_over_L": d["x_over_L"],
            "y_over_L": d["y_over_L"], "t_s": d["t_s"], "window": window,
            "p_mean_Pa": p_mean, "pa_per_lattice_density": factor,
            "dx_m": Fraction(str(req["body_length_m"])) / req["length_cells"],
            "roi_offset": int(round(d["x_over_L"][0] * req["length_cells"] - 0.5)),
            "roi_offset_y": int(round(d["y_over_L"][0] * req["length_cells"] - 0.5)),
            "request": req}


def surface_pressure_force(r: dict) -> dict:
    """Pressure-only force per unit span on the staircase body: F' = -sum p n dx over solid faces.

    Diagnostic for the Pa mapping and the face bookkeeping, compared with the receipt's own
    momentum-exchange force (which also contains viscous traction, so they are not expected to
    agree, and no tolerance is claimed)."""
    s, p, dx = r["solid"], r["p_mean_Pa"], float(r["dx_m"])
    fx = fz = 0.0
    faces = 0
    for (i, j) in zip(*np.nonzero(s)):
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, j + dj
            if 0 <= a < s.shape[0] and 0 <= b < s.shape[1] and not s[a, b]:
                fx -= p[a, b] * di * dx
                fz -= p[a, b] * dj * dx
                faces += 1
    req, res = r["request"], r["result"]
    qref = 0.5 * req["density_kg_m3"] * req["speed_m_s"] ** 2 * req["body_length_m"]
    return {"pressure_drag_N_per_m": fx, "pressure_lift_N_per_m": fz, "faces": faces,
            "receipt_drag_N_per_m": qref * res["mean_Cd_last20pct"],
            "receipt_lift_N_per_m": qref * res["mean_Cl_last20pct"],
            "pressure_over_receipt_lift": fz / (qref * res["mean_Cl_last20pct"]),
            "pressure_over_receipt_drag": fx / (qref * res["mean_Cd_last20pct"]),
            "note": ("pressure-only staircase-face integral of the time-mean field vs the receipt's "
                     "momentum-exchange force; a units/bookkeeping diagnostic, not a validation")}


def tail_strip(r: dict) -> dict:
    """The actual tail strip: columns TAIL_COLUMNS at row TAIL_ROW, with its measured thickness."""
    s = r["solid"]
    cols = []
    for i in TAIL_COLUMNS:
        run = [j for j in range(s.shape[1]) if s[i, j]]
        cols.append({"col": i, "solid_rows": run})
    thickness = min(len(c["solid_rows"]) for c in cols)
    faces_fluid = all(not s[i, TAIL_ROW + 1] and not s[i, TAIL_ROW - 1] and s[i, TAIL_ROW] for i in TAIL_COLUMNS)
    return {"columns": cols, "cells_across": thickness, "fluid_on_both_faces": bool(faces_fluid)}


def _x_m(r, i):
    return (Fraction(2 * (r["roi_offset"] + i) + 1, 2)) * r["dx_m"]


def _z_m(r, j):
    return (Fraction(2 * (r["roi_offset_y"] + j) + 1, 2)) * r["dx_m"]


def tail_record_and_target(r: dict) -> tuple[dict, dict]:
    """Build the member-pressure record and matching 2D-section target from actual cells."""
    strip = tail_strip(r)
    i0, i1 = TAIL_COLUMNS[0], TAIL_COLUMNS[-1]
    frame = f"windtunnel/{r['request']['mesh_id']}/lattice-xz-metres"
    root = [str(_x_m(r, i0)), "0", str(_z_m(r, TAIL_ROW))]
    tip = [str(_x_m(r, i1)), "0", str(_z_m(r, TAIL_ROW))]
    stations = []
    for i in TAIL_COLUMNS:
        stations.append({"s_m": str(_x_m(r, i) - _x_m(r, i0)),
                         "p_pos_Pa": repr(float(r["p_mean_Pa"][i, TAIL_ROW + 1])),
                         "p_neg_Pa": repr(float(r["p_mean_Pa"][i, TAIL_ROW - 1]))})
    t = r["t_s"][r["window"]]
    rec = {"schema": SCHEMA_PRESSURE,
           "source": {"producer": "engineering/windtunnel baseline (actual completed CPU run)",
                      "evidence_kind": "simulated", "receipt_sha256": r["sha256"]["result"],
                      "fields_sha256": r["sha256"]["fields"],
                      "geometry_sha256": r["result"]["geometry"]["sha256"]},
           "dimensionality": "2d-extrusion",
           "frame": {"id": frame, "length_unit": "m"},
           "member": {"id": "windtunnel-tail-strip-cols52-54", "root_m": root, "tip_m": tip,
                      "normal": ["0", "0", "1"]},
           "pressure": {"unit": "Pa", "kind": "dimensional",
                        "reference": "above freestream, receipt mapping rho*(U/U_lat)^2*(rho_lat-1)/3, "
                                     "nearest fluid cell centre above (pos) / below (neg), time mean"},
           "stations": stations,
           "tributary": {"width_m": "1", "status": "declared",
                         "source": "per metre of the infinite 2D extrusion; no finite span exists"},
           "time": {"kind": "time_mean", "window_s": [repr(float(t[0])), repr(float(t[-1]))]},
           "resolution": {"cells_across_member_thickness": strip["cells_across"],
                          "cells_along_member": len(TAIL_COLUMNS)}}
    tgt = {"schema": SCHEMA_TARGET, "member_id": rec["member"]["id"], "frame_id": frame,
           "frame_length_unit": "m", "root_m": root, "tip_m": tip,
           "EI": {"lo_Nm2": "1e-6", "hi_Nm2": "1e-5", "status": "context_only",
                  "source": "Alben et al. 2007 Sec. 3.4 bluegill order of magnitude (context only)"},
           "claim": "member_scenario", "n_elements": 8}
    return rec, tgt
