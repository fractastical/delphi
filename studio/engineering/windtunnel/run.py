"""Frozen CPU case/control suite; prepares portable masks for optional CUDA refinement."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .geometry import file_sha
from .model import PROTOCOL, canonical, no_body_control, run_request

CASES = {
    "baseline": {},
    "grid48": {"length_cells": 48},
    "time24-coarse": {"convective_time": 2.0},
    "time24-half": {"convective_time": 2.0, "lattice_speed": 0.02},
}


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def run_suite(output_directory, analytic_path):
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    analytic = json.loads(Path(analytic_path).read_text())
    if not analytic.get("all_pass"):
        raise ValueError("original analytic prerequisites failed")
    write(output / "analytic-controls.json", analytic)
    no_body = no_body_control()
    write(output / "no-body.json", no_body)
    if not no_body["passed"]:
        raise ValueError("no-body control failed")
    for name, request in CASES.items():
        print(json.dumps({"case": name, "state": "running"}), flush=True)
        result = run_request(request, output / name, analytic_receipt=analytic)
        print(
            json.dumps(
                {
                    "case": name,
                    "state": result["status"],
                    "Cd": result["mean_Cd_last20pct"],
                    "seconds": result["wall_seconds"],
                }
            ),
            flush=True,
        )
        # A resource-limited grid case must not suppress an independent time pair.
    return finalize_suite(output)


def finalize_suite(output_directory):
    output = Path(output_directory)
    analytic = json.loads((output / "analytic-controls.json").read_text())
    no_body = json.loads((output / "no-body.json").read_text())
    results = {
        name: json.loads((output / name / "result.json").read_text())
        for name in CASES
        if (output / name / "result.json").exists()
    }
    checks = {"analytic": analytic["all_pass"], "no_body": no_body["passed"]}
    complete = {
        name: r["status"] != "FAIL" and r["completed_steps"] == r["planned_steps"]
        for name, r in results.items()
    }
    grid = time_error = None
    if all(complete.get(name, False) for name in ("baseline", "grid48")):
        grid = abs(
            results["baseline"]["mean_Cd_last20pct"]
            - results["grid48"]["mean_Cd_last20pct"]
        ) / max(abs(results["grid48"]["mean_Cd_last20pct"]), 1e-12)
    if all(complete.get(name, False) for name in ("time24-coarse", "time24-half")):
        time_error = abs(
            results["time24-coarse"]["mean_Cd_last20pct"]
            - results["time24-half"]["mean_Cd_last20pct"]
        ) / max(abs(results["time24-half"]["mean_Cd_last20pct"]), 1e-12)
    checks.update(
        {
            "grid_relative_drag_difference_le_20pct": None
            if grid is None
            else grid <= 0.2,
            "time_relative_drag_difference_le_10pct": None
            if time_error is None
            else time_error <= 0.1,
            "drag_sign": results.get("baseline", {}).get("mean_Cd_last20pct", 0) > 0,
            "opposite_force_sign_mutant_rejected": not (
                -results.get("baseline", {}).get("mean_Cd_last20pct", 0) > 0
            ),
        }
    )
    stable = all(
        r["checks"]["stable"] and r["checks"]["positive_drag"] for r in results.values()
    )
    checks["all_case_stability_and_sign"] = stable
    checks["all_case_flux"] = all(r["checks"]["flux_le_5pct"] for r in results.values())
    checks["stationarity"] = all(
        r["checks"]["stationary_drag_le_5pct"] for r in results.values()
    )
    label = (
        "FAIL"
        if not stable or len(results) < len(CASES)
        else ("PASS" if all(checks.values()) else "PARTIAL")
    )
    summary = {
        "schema": "frontier.windtunnel.suite/1",
        "evidence_kind": "simulated",
        "label": label,
        "checks": checks,
        "grid_relative_drag_difference": grid,
        "time_relative_drag_difference": time_error,
        "cases": {
            name: {
                k: r[k]
                for k in (
                    "status",
                    "request_echo",
                    "geometry",
                    "Re",
                    "mean_Cd_last20pct",
                    "mean_Cl_last20pct",
                    "checks",
                    "wall_seconds",
                    "max_mach",
                    "failure",
                    "completed_steps",
                    "planned_steps",
                )
            }
            for name, r in results.items()
        },
        "scope": "2D low-Re mesh-silhouette proxy; not a calibrated fish or flight polar",
        "biological_success_probability": None,
        "protocol_sha256": file_sha(PROTOCOL),
    }
    write(output / "summary.json", summary)
    write(
        output / "simulation-manifest.json",
        {
            "schema": "frontier.windtunnel.manifest/1",
            "evidence_kind": "simulated",
            "protocol_sha256": file_sha(PROTOCOL),
            "analytic_receipt_sha256": hashlib.sha256(canonical(analytic)).hexdigest(),
            "physics_code_files": {
                str(p): file_sha(Path(__file__).parent / p)
                for p in ("lbm.py", "model.py", "geometry.py")
            },
            "outputs": {
                str(p.relative_to(output)): {
                    "sha256": file_sha(p),
                    "byte_size": p.stat().st_size,
                }
                for p in [
                    output / "analytic-controls.json",
                    output / "no-body.json",
                    output / "summary.json",
                    *[
                        f
                        for name in results
                        for f in (
                            output / name / "result.json",
                            output / name / "fields.npz",
                        )
                        if f.exists()
                    ],
                ]
            },
        },
    )
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--output", default="artifacts/windtunnel")
    p.add_argument("--analytic-controls", required=True)
    p.add_argument("--finalize-only", action="store_true")
    args = p.parse_args()
    print(
        json.dumps(
            finalize_suite(args.output)
            if args.finalize_only
            else run_suite(args.output, args.analytic_controls)
        )
    )
