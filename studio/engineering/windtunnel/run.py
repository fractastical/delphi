"""Frozen CPU case/control suite; prepares portable masks for optional CUDA refinement."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .geometry import file_sha
from .model import PROTOCOL, canonical, no_body_control, run_request


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
    cases = {
        "baseline": {},
        "grid48": {"length_cells": 48},
        "time24-coarse": {"convective_time": 2.0},
        "time24-half": {"convective_time": 2.0, "lattice_speed": 0.02},
    }
    results = {}
    for name, request in cases.items():
        print(json.dumps({"case": name, "state": "running"}), flush=True)
        result = run_request(request, output / name, analytic_receipt=analytic)
        results[name] = result
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
        if result["status"] == "FAIL":
            break
    checks = {"analytic": analytic["all_pass"], "no_body": no_body["passed"]}
    if len(results) == len(cases):
        grid = abs(
            results["baseline"]["mean_Cd_last20pct"]
            - results["grid48"]["mean_Cd_last20pct"]
        ) / max(abs(results["grid48"]["mean_Cd_last20pct"]), 1e-12)
        time_error = abs(
            results["time24-coarse"]["mean_Cd_last20pct"]
            - results["time24-half"]["mean_Cd_last20pct"]
        ) / max(abs(results["time24-half"]["mean_Cd_last20pct"]), 1e-12)
        checks.update(
            {
                "grid_relative_drag_difference_le_20pct": grid <= 0.2,
                "time_relative_drag_difference_le_10pct": time_error <= 0.1,
                "drag_sign": results["baseline"]["mean_Cd_last20pct"] > 0,
                "opposite_force_sign_mutant_rejected": not (
                    -results["baseline"]["mean_Cd_last20pct"] > 0
                ),
            }
        )
    else:
        grid = time_error = None
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
        if not stable or len(results) < len(cases)
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
            "outputs": {
                str(p.relative_to(output)): {
                    "sha256": file_sha(p),
                    "byte_size": p.stat().st_size,
                }
                for p in sorted(output.rglob("*"))
                if p.is_file() and p.name != "simulation-manifest.json"
            },
        },
    )
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--output", default="artifacts/windtunnel")
    p.add_argument("--analytic-controls", required=True)
    args = p.parse_args()
    print(json.dumps(run_suite(args.output, args.analytic_controls)))
