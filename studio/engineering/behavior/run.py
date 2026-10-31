"""Execute the frozen comparisons, analytic/numerical controls and state render."""
from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

from .model import HERE, code_hashes, simulate


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def controls(results, refined, protocol):
    limits = protocol["acceptance"]
    baseline = results["baseline"]
    metrics = baseline["metrics"]
    base_error = metrics["tracking_relative_rms_after_0_5s"]
    phase = metrics["phase_error_rms_final_0_3s_rad"]
    diff = float(np.max(np.abs(np.array(baseline["actual_angle_rad"]) - refined["actual_angle_rad"])))
    t = np.asarray(baseline["time_s"])
    rate = baseline["request"]["amplitude_rate_s"] / 2
    exact = 1 - (1 + rate * t) * np.exp(-rate * t)
    amplitude_error = float(np.max(np.abs(np.asarray(baseline["normalized_amplitude"]) - exact[:, None])))
    no_feedback_ratio = results["feedback_removed"]["metrics"]["tracking_relative_rms_after_0_5s"] / base_error
    no_coupling_ratio = results["coupling_removed"]["metrics"]["phase_error_rms_final_0_3s_rad"] / max(phase, 1e-15)
    frequency_error = abs(results["changed_frequency"]["metrics"]["leader_frequency_Hz"] - protocol["scenarios"]["changed_frequency"]["frequency_Hz"])
    mutant_error = results["feedback_sign_mutant"]["metrics"]["tracking_relative_rms_after_0_5s"]
    rows = [
        {"name": "baseline_tracking", "value": base_error, "threshold": limits["baseline_tracking_relative_rms_after_0_5s_max"], "passed": base_error < limits["baseline_tracking_relative_rms_after_0_5s_max"]},
        {"name": "phase_wave_recovery_after_kick", "value_rad": phase, "threshold_rad": limits["phase_error_rms_final_0_3s_max_rad"], "passed": phase < limits["phase_error_rms_final_0_3s_max_rad"]},
        {"name": "feedback_removed_discriminates", "ratio": no_feedback_ratio, "minimum_ratio": limits["no_feedback_tracking_over_baseline_min_ratio"], "passed": no_feedback_ratio > limits["no_feedback_tracking_over_baseline_min_ratio"]},
        {"name": "coupling_removed_discriminates", "ratio": no_coupling_ratio, "minimum_ratio": limits["uncoupled_phase_error_over_baseline_min_ratio"], "passed": no_coupling_ratio > limits["uncoupled_phase_error_over_baseline_min_ratio"]},
        {"name": "changed_command_frequency", "error_Hz": frequency_error, "tolerance_Hz": limits["changed_frequency_endpoint_Hz_tolerance"], "passed": frequency_error < limits["changed_frequency_endpoint_Hz_tolerance"]},
        {"name": "time_step_halving", "max_angle_difference_rad": diff, "tolerance_rad": limits["step_halving_max_angle_difference_rad"], "passed": diff < limits["step_halving_max_angle_difference_rad"]},
        {"name": "amplitude_closed_form", "max_error": amplitude_error, "tolerance": limits["amplitude_closed_form_max_error"], "formula": "r(t)=1-(1+a*t/2)exp(-a*t/2), r(0)=r_dot(0)=0", "passed": amplitude_error < limits["amplitude_closed_form_max_error"]},
        {"name": "feedback_sign_mutant_rejected", "mutant_relative_tracking_rms": mutant_error, "baseline_predicate_threshold": limits["baseline_tracking_relative_rms_after_0_5s_max"], "mutant_baseline_predicate_passed": mutant_error < limits["baseline_tracking_relative_rms_after_0_5s_max"], "passed": mutant_error >= limits["baseline_tracking_relative_rms_after_0_5s_max"]},
    ]
    return {"schema": "frontier.behavior.controls/1", "evidence_kind": "computational_check", "passed": all(row["passed"] for row in rows),
            "checks": rows, "scope": "Frozen numerical/controller predicates; no biological or fluid-force success is tested"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/behavior"))
    parser.add_argument("--skip-render", action="store_true")
    args = parser.parse_args()
    if os.environ.get("FRONTIER_BEHAVIOR_ACTIVE"):
        raise SystemExit("nested behavior run refused")
    os.environ["FRONTIER_BEHAVIOR_ACTIVE"] = "1"
    started = time.perf_counter()
    args.output.mkdir(parents=True, exist_ok=True)
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen_commit = subprocess.check_output(["git", "log", "--diff-filter=A", "--format=%H", "--", str(HERE / "protocol.json")], text=True).strip().splitlines()[-1]
    frozen_bytes = subprocess.check_output(["git", "show", frozen_commit + ":engineering/behavior/protocol.json"])
    if frozen_bytes != (HERE / "protocol.json").read_bytes():
        raise SystemExit("frozen protocol changed; original acceptance cannot be silently replaced")
    results = {}
    for name, request in protocol["scenarios"].items():
        results[name] = simulate(request)
        write(args.output / (name + ".json"), results[name])
    refined = simulate({"dt_s": protocol["numerics"]["refined_dt_s"]})
    write(args.output / "refined_baseline.json", refined)
    checks = controls(results, refined, protocol)
    write(args.output / "controls.json", checks)
    if not checks["passed"]:
        print(json.dumps(checks))
        raise SystemExit("frozen acceptance failed; blocker recorded, no render success asserted")
    for name in ("sources.json", "interface.json", "problems.json", "protocol.json"):
        (args.output / name).write_bytes((HERE / name).read_bytes())
    if not args.skip_render:
        from .render import render
        write(args.output / "render_receipt.json", render(args.output))
    manifest = {"schema": "frontier.behavior.manifest/1", "evidence_kind": "SimulationResult", "status": "completed", "exit_status": 0,
                "protocol_commit": frozen_commit, "protocol_sha256": sha256(frozen_bytes).hexdigest(), "source_parent_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "source_identity": "Exact source files pinned below; parent commit is provenance context, not an assertion of clean tracked state at run time",
                "code_sha256": code_hashes(), "command": [sys.executable, "-m", "engineering.behavior.run", *sys.argv[1:]],
                "environment": {"python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(), "threads": {k: os.environ.get(k) for k in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"]}},
                "timestamp_seattle": datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z"), "elapsed_s": time.perf_counter() - started,
                "simulationActions": [name + ".json#/simulationAction" for name in results], "renderAction": "render_receipt.json",
                "biological_accuracy": "unknown; no measured trajectory/circuit or force calibration", "control_scope": checks["scope"],
                "files": {p.name: {"sha256": sha256(p.read_bytes()).hexdigest(), "byte_size": p.stat().st_size}
                          for p in sorted(args.output.iterdir()) if p.is_file() and p.name != "manifest.json"}}
    write(args.output / "manifest.json", manifest)
    print(json.dumps({"status": "completed", "controls_passed": checks["passed"], "elapsed_s": manifest["elapsed_s"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
