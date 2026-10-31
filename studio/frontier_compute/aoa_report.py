"""Check the frozen angle/grid packet against returned numerical artifacts."""

import argparse
import hashlib
import json
import math
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report(parts, protocol_path):
    protocol = json.loads(protocol_path.read_text())
    rows, hashes = {}, {str(protocol_path): digest(protocol_path)}
    parity_path = parts / "00-p9-exact-artifact-recovery/out/checks.json"
    parity = json.loads(parity_path.read_text())
    if parity.get("repeat_passed") is not True:
        raise ValueError("Original CPU/CUDA parity gate did not pass")
    hashes[str(parity_path)] = digest(parity_path)
    for path in sorted(parts.glob("*/out/aoa*/result.json")):
        result = json.loads(path.read_text())
        request = result["request_echo"]
        key = (request["aoa_deg"], request["length_cells"])
        if key in rows:
            raise ValueError("Duplicate angle/grid result")
        fields = path.with_name("fields.npz")
        if digest(fields) != result["fields_sha256"]:
            raise ValueError("Returned fields hash mismatch")
        for source in (path, fields):
            hashes[str(source)] = digest(source)
        scalar_keys = ("mean_Cd_last20pct", "mean_Cl_last20pct", "max_mach", "max_density_deviation", "flux_relative_difference")
        if not all(math.isfinite(result[k]) for k in scalar_keys):
            raise ValueError("Nonfinite result")
        rows[key] = {
            "angle_deg": key[0], "grid": key[1],
            **{k: result[k] for k in scalar_keys},
            "declared_checks": result["checks"],
            "frozen_bounds_passed": (
                result["failure"] is None
                and result["completed_steps"] == result["planned_steps"]
                and result["max_mach"] <= 0.3
                and result["max_density_deviation"] <= 0.1
                and result["flux_relative_difference"] <= 0.05
                and result["mean_Cd_last20pct"] > 0
                and result["force_history"][-1]["convective_time"] == 4.0
            ),
        }
    expected = {(a, g) for a in protocol["angles_deg"] for g in protocol["grids"]}
    if set(rows) != expected or len(rows) != 6:
        raise ValueError("Angle/grid coverage mismatch")
    pairs = []
    for angle in protocol["angles_deg"]:
        coarse, fine = (rows[angle, g] for g in protocol["grids"])
        delta = abs(coarse["mean_Cd_last20pct"] - fine["mean_Cd_last20pct"]) / max(abs(fine["mean_Cd_last20pct"]), 1e-12)
        pairs.append({"angle_deg": angle, "relative_drag_difference": delta,
                      "bound": protocol["grid_relative_drag_bound"],
                      "passed": delta <= protocol["grid_relative_drag_bound"]})
    return {
        "schema": "frontier.angle-grid-check/1",
        "evidence_kind": "computational_check",
        "job_id": "aijob-e00saz7cewggkp50d2",
        "scope": "Re=80, static 2D sagittal print-mesh projection; span ignored. Not measured fish aerodynamics or flight validation.",
        "cpu_cuda_parity_passed": True,
        "cases": list(rows.values()), "grid_pairs": pairs,
        "all_frozen_bounds_passed": all(r["frozen_bounds_passed"] for r in rows.values()) and all(p["passed"] for p in pairs),
        "physical_validation": "not established",
        "source_sha256": hashes,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parts", type=Path)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = report(args.parts, args.protocol)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("grid_pairs", "all_frozen_bounds_passed")}, indent=2))
