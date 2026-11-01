"""Paired deterministic stress-envelope analysis on the existing coupled solver."""

import argparse
from hashlib import sha256
import json
import platform
from pathlib import Path
import time

import numpy as np
import scipy

from .controls import run as run_controls
from .model import ART, ROOT, check_inputs, dump
from .run import solve_arm


HERE = ART / "joint-uncertainty-v1"
PROTOCOL_PATH = HERE / "protocol.json"
SCENARIO_ROWS = json.loads(PROTOCOL_PATH.read_text())["shared_scenarios"]
PRESSURE_POLICIES = [
    "frozen-rigid-distribution",
    "updated-deformed-distribution",
]
ARMS = ["rigid", "one-way-frozen-load", "two-way-static-feedback"]
COMPARISONS = [
    ("one-way-minus-rigid", "one-way-frozen-load", "rigid"),
    ("feedback-minus-rigid", "two-way-static-feedback", "rigid"),
    ("feedback-minus-one-way", "two-way-static-feedback", "one-way-frozen-load"),
]


def _lookup(index, scenario, policy, mesh, arm):
    return index.get((scenario, policy, mesh, arm))


def _effect(target, reference):
    if target is None or reference is None:
        return {"available": False, "reason": "missing declared arm"}
    if not target.get("valid_for_declared_transfer") or not reference.get(
        "valid_for_declared_transfer"
    ):
        return {
            "available": False,
            "reason": "paired arm invalid or incomplete",
            "target_status": target.get("status"),
            "reference_status": reference.get("status"),
        }
    target_CL = target["iterations"][-1]["CL_on_fixed_source_area"]
    reference_CL = reference["iterations"][-1]["CL_on_fixed_source_area"]
    target_flight = target["flight"]
    reference_flight = reference["flight"]
    if target_flight is None or reference_flight is None:
        return {"available": False, "reason": "paired flight result missing"}
    return {
        "available": True,
        "delta_CL": target_CL - reference_CL,
        "delta_range_m": target_flight["main"]["range_m"]
        - reference_flight["main"]["range_m"],
        "delta_half_dt_range_m": target_flight["half"]["range_m"]
        - reference_flight["half"]["range_m"],
        "target_status": target["status"],
        "reference_status": reference["status"],
    }


def derive(arms):
    """Build signed paired effects without dropping unavailable arms."""
    index = {
        (
            row["scenario_id"],
            row["pressure_policy"],
            row["mesh"],
            row["arm"],
        ): row
        for row in arms
    }
    paired = []
    for scenario in SCENARIO_ROWS:
        for policy in PRESSURE_POLICIES:
            for mesh in ["main", "fine"]:
                for comparison, target_arm, reference_arm in COMPARISONS:
                    paired.append(
                        {
                            "scenario_id": scenario["id"],
                            "pressure_policy": policy,
                            "mesh": mesh,
                            "comparison": comparison,
                            **_effect(
                                _lookup(
                                    index,
                                    scenario["id"],
                                    policy,
                                    mesh,
                                    target_arm,
                                ),
                                _lookup(
                                    index,
                                    scenario["id"],
                                    policy,
                                    mesh,
                                    reference_arm,
                                ),
                            ),
                        }
                    )
    mesh_resolution = []
    for scenario in SCENARIO_ROWS:
        for policy in PRESSURE_POLICIES:
            for comparison, _, _ in COMPARISONS:
                pair = {
                    row["mesh"]: row
                    for row in paired
                    if row["scenario_id"] == scenario["id"]
                    and row["pressure_policy"] == policy
                    and row["comparison"] == comparison
                }
                main, fine = pair["main"], pair["fine"]
                row = {
                    "scenario_id": scenario["id"],
                    "pressure_policy": policy,
                    "comparison": comparison,
                    "available": main["available"] and fine["available"],
                    "interpretation": "descriptive paired main-minus-fine discrepancy; not a validated error bound",
                }
                if row["available"]:
                    for metric in ["delta_CL", "delta_range_m"]:
                        row[f"main_minus_fine_{metric}"] = main[metric] - fine[metric]
                else:
                    row["main_status"] = main.get("reason")
                    row["fine_status"] = fine.get("reason")
                mesh_resolution.append(row)
    pressure_effects = []
    for scenario in SCENARIO_ROWS:
        for mesh in ["main", "fine"]:
            for arm in ARMS:
                updated = _lookup(
                    index,
                    scenario["id"],
                    "updated-deformed-distribution",
                    mesh,
                    arm,
                )
                frozen = _lookup(
                    index,
                    scenario["id"],
                    "frozen-rigid-distribution",
                    mesh,
                    arm,
                )
                effect = _effect(updated, frozen)
                pressure_effects.append(
                    {
                        "scenario_id": scenario["id"],
                        "mesh": mesh,
                        "arm": arm,
                        "comparison": "updated-deformed-minus-frozen-rigid-pressure",
                        **effect,
                    }
                )
    integration_resolution = []
    for row in arms:
        flight = row.get("flight")
        history = row.get("iterations", [])
        integration_resolution.append(
            {
                "scenario_id": row["scenario_id"],
                "pressure_policy": row["pressure_policy"],
                "mesh": row["mesh"],
                "arm": row["arm"],
                "status": row.get("status"),
                "available": bool(row.get("valid_for_declared_transfer") and flight),
                "fixed_point_iteration_count": len(history),
                "final_shape_residual_over_span": history[-1].get(
                    "shape_residual_over_span"
                )
                if history
                else None,
                "final_iteration_CL_change": history[-1].get("CL_change")
                if history
                else None,
                "main_half_dt_range_relative_difference": flight.get(
                    "range_relative_difference"
                )
                if flight
                else None,
                "dt_gate_passed_under_existing_assumption": flight.get("dt_gate_passed")
                if flight
                else None,
                "interpretation": "solver and time-resolution diagnostics; not independent biological or transfer validation",
            }
        )
    return {
        "paired_effects": paired,
        "pressure_policy_effects": pressure_effects,
        "mesh_effect_resolution": mesh_resolution,
        "integration_effect_resolution": integration_resolution,
    }


def _pinned_inputs():
    frozen = json.loads(PROTOCOL_PATH.read_text())
    checked = []
    for item in frozen["inputs"]:
        path = ROOT / item["path"]
        raw = path.read_bytes()
        actual = {"path": item["path"], "sha256": sha256(raw).hexdigest(), "bytes": len(raw)}
        if path.name in {"protocol.json", "panels.json"} and (
            actual["sha256"] != item["sha256"] or actual["bytes"] != item["bytes"]
        ):
            raise ValueError(f"Frozen scientific input changed: {item['path']}")
        checked.append({**actual, "frozen_sha256": item["sha256"]})
    return checked


def run(out, pilot=False):
    out = Path(out)
    if out.exists():
        raise ValueError("Fresh output directory required")
    out.mkdir(parents=True)
    started = time.monotonic()
    limit_s = 1200
    deadline = started + limit_s
    failure = None
    arms = []
    declared = 0
    controls_path = out / "controls.json"
    try:
        if np.__version__ != "2.5.4" or scipy.__version__ != "1.17.1":
            raise ValueError("Exact frozen NumPy/SciPy pins required")
        check_inputs()
        input_pins = _pinned_inputs()
        controls = run_controls(controls_path)
        if not controls.get("passed"):
            raise RuntimeError("Existing aeroelastic controls failed")
        selected_scenarios = ["nominal"] if pilot else [x["id"] for x in SCENARIO_ROWS]
        selected_meshes = ["main"] if pilot else ["main", "fine"]
        declared = len(selected_scenarios) * len(selected_meshes) * len(PRESSURE_POLICIES) * len(ARMS)
        for scenario in SCENARIO_ROWS:
            if scenario["id"] not in selected_scenarios:
                continue
            scale_values = {key: value for key, value in scenario.items() if key != "id"}
            for policy in PRESSURE_POLICIES:
                for mesh in selected_meshes:
                    for arm in ARMS:
                        identifier = f"{scenario['id']}-{policy}-{mesh}-{arm}"
                        result_dir = out / "arms" / identifier
                        try:
                            if time.monotonic() > deadline:
                                result = {
                                    "status": "not-started: deadline",
                                    "valid_for_declared_transfer": False,
                                }
                            else:
                                result = solve_arm(
                                    0.2,
                                    20.0,
                                    mesh,
                                    arm,
                                    result_dir,
                                    deadline,
                                    scenario=scale_values,
                                    pressure_policy=policy,
                                )
                        except Exception as exc:
                            result = {
                                "status": "failed",
                                "error": f"{type(exc).__name__}: {exc}",
                                "valid_for_declared_transfer": False,
                            }
                            dump(result_dir / "failure.json", result)
                        result.update(
                            {
                                "id": identifier,
                                "scenario_id": scenario["id"],
                                "scenario_scales": scale_values,
                                "pressure_policy": policy,
                                "mesh": mesh,
                                "arm": arm,
                            }
                        )
                        arms.append(result)
                        dump(out / "progress.json", {"arms": arms, "pilot": pilot})
        summary = {
            "schema": "frontier.aeroelastic.joint-uncertainty-results/1",
            "run_kind": "timing-and-control-pilot" if pilot else "frozen-scenario-assay",
            "execution_status": "all declared rows returned" if len(arms) == declared else "partial",
            "declared_arm_rows": declared,
            "returned_arm_rows": len(arms),
            "valid_arm_rows": sum(x.get("valid_for_declared_transfer", False) for x in arms),
            "failed_rows": sum(str(x.get("status", "")).startswith("failed") for x in arms),
            "domain_exit_rows": sum(str(x.get("status", "")).startswith("model-domain") for x in arms),
            "unconverged_rows": sum(str(x.get("status", "")).startswith("unconverged") for x in arms),
            "not_started_or_partial_rows": sum(
                str(x.get("status", "")).startswith(("not-started", "partial")) for x in arms
            ),
            "controls": controls,
            "arms": arms,
            "derived": derive(arms),
            "input_pins": input_pins,
            "scope": "Assumed deterministic envelope only; not probability, measured biology, or calibrated cross-scale transfer.",
        }
        dump(out / "results.json", summary)
        _write_ports(out, summary)
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        dump(out / "failure.json", {"error": failure, "arms": arms})
    paths = [path for path in out.rglob("*") if path.is_file() and path.name != "receipt.json"]
    sources = [
        "engineering/aeroelastic/uncertainty.py",
        "engineering/aeroelastic/run.py",
        "engineering/aeroelastic/flight.py",
        "engineering/aeroelastic/model.py",
        "engineering/aeroelastic/controls.py",
        "artifacts/aeroelastic/joint-uncertainty-v1/protocol.json",
        "artifacts/aeroelastic/protocol.json",
    ]
    receipt = {
        "schema": "frontier.aeroelastic.joint-uncertainty-receipt/1",
        "run_kind": "timing-and-control-pilot" if pilot else "frozen-scenario-assay",
        "protocol_sha256": sha256(PROTOCOL_PATH.read_bytes()).hexdigest(),
        "sources": {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in sources},
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "device": "CPU"},
        "wall_seconds": time.monotonic() - started,
        "failure": failure,
        "gpu": 0,
        "cloud_calls": 0,
        "dollars": None,
        "files": [
            {"path": str(path.relative_to(out)), "sha256": sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
            for path in paths
        ],
    }
    receipt["output_bytes"] = sum(row["bytes"] for row in receipt["files"])
    receipt["output_cap_exceeded"] = receipt["output_bytes"] > 50_000_000
    dump(out / "receipt.json", receipt)
    print({"failure": failure, "arm_rows": len(arms), "wall_seconds": receipt["wall_seconds"], "output_bytes": receipt["output_bytes"]}, flush=True)
    return 1 if failure or receipt["output_cap_exceeded"] or len(arms) != declared else 0


def _write_ports(out, summary):
    result_path = out / "results.json"
    digest = sha256(result_path.read_bytes()).hexdigest()
    ports = []
    for port_name, key, value_key, units, scope in [
        ("aeroelastic_joint_uncertainty.delta_CL", "paired_effects", "delta_CL", "1", "Signed arm-minus-rigid CL effects, indexed by scenario, pressure policy, mesh, and comparison."),
        ("aeroelastic_joint_uncertainty.delta_range_m", "paired_effects", "delta_range_m", "m", "Signed rigidized-glide range effects, indexed by scenario, pressure policy, mesh, and comparison."),
        ("aeroelastic_joint_uncertainty.mesh_effect_resolution", "mesh_effect_resolution", None, "mixed", "Paired main-minus-fine effect discrepancy; descriptive, not a validated error bound."),
        ("aeroelastic_joint_uncertainty.integration_effect_resolution", "integration_effect_resolution", None, "mixed", "Feedback residual/iteration and main-half-dt diagnostics; descriptive only."),
    ]:
        ports.append(
            {
                "id": port_name,
                "units": units,
                "evidence_kind": "computed-scenario-output",
                "scope": scope,
                "data_path": "results.json#/derived/" + key,
                "value_key": value_key,
                "data_sha256": digest,
                "assurance_status": "not-observed; not-biologically-calibrated",
            }
        )
    dump(
        out / "output-ports.json",
        {
            "schema": "frontier.aeroelastic.output-ports/1",
            "evidence_kind": "computed scenario contrasts; no measured biology",
            "source_result": {"path": "results.json", "sha256": digest},
            "ports": ports,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true", help="Run nominal/main-mesh feasibility subset only")
    args = parser.parse_args()
    raise SystemExit(run(args.out, pilot=args.pilot))
