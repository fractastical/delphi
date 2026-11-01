"""Portable same-code CUDA repeat/refinement. GPUops owns dispatch."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import zlib
from pathlib import Path

import numpy as np

from .geometry import mask_from_mesh
from .model import run_request


def build_input(output):
    output = Path(output)
    reference = json.loads((output / "baseline/result.json").read_text())
    fields = np.load(output / "baseline/fields.npz")
    masks = {}
    for cells in (24, 48, 96):
        mask, geometry = mask_from_mesh("N1-cypselurus-baseline", cells, 8.0, 1.0)
        masks[str(cells)] = {
            "shape": list(mask.shape),
            "mask_packed_zlib_base64": base64.b64encode(
                zlib.compress(np.packbits(mask).tobytes())
            ).decode(),
            "geometry": geometry,
        }
    subset = {
        k: fields[k][-1, ::8, ::8].astype(float).tolist() for k in ("rho", "ux", "uy")
    }
    payload = {
        "schema": "frontier.windtunnel.cuda-protocol/1",
        "frozen_before_gpu": True,
        "cpu_controls": json.loads((output / "analytic-controls.json").read_text()),
        "masks": masks,
        "cpu_reference": {
            "request": reference["request_echo"],
            "Cd": reference["mean_Cd_last20pct"],
            "Cl": reference["mean_Cl_last20pct"],
            "last_field_subset": subset,
        },
        "cases": [
            {"id": "cuda-repeat24", "request": {"frames": 21}},
            {"id": "cuda-complete48", "request": {"length_cells": 48, "frames": 21}},
            {
                "id": "cuda-refine96",
                "request": {"length_cells": 96, "convective_time": 8.0, "frames": 21},
            },
        ],
        "criteria": {
            "cpu_cuda_max_scaled_field_error": 1e-6,
            "field_scaling": "density divided by rho0=1; velocity divided by U_lattice=.04",
            "cpu_cuda_abs_coefficient_error": 1e-6,
            "grid": "CPU48 hit its immutable runtime cap. CUDA48 completes the frozen24/48 comparison, with20percent bound unchanged. Compare96 midpoint at SAME tU/L=4; difference must shrink relative to24/48 before calling further refinement consistent",
            "extension": "tU/L4..8 retained to inspect stationarity, not a new physical-validation claim",
            "stability": "same immutable Mach/density/finite bounds",
        },
        "output_cap_hint": "Return result JSON, sampled fields NPZ and checks;21 frames per case keep output small",
    }
    (output / "cuda-protocol.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def run_remote(input_path, output_directory):
    if os.environ.get("FRONTIER_WINDTUNNEL_REMOTE_ACTIVE"):
        raise ValueError("nested wind-tunnel remote runner refused")
    os.environ["FRONTIER_WINDTUNNEL_REMOTE_ACTIVE"] = "1"
    payload = json.loads(Path(input_path).read_text())
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for case in payload["cases"]:
        cells = case["request"].get("length_cells", 24)
        packed = payload["masks"][str(cells)]
        count = int(np.prod(packed["shape"]))
        raw = zlib.decompress(base64.b64decode(packed["mask_packed_zlib_base64"]))
        mask = (
            np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[:count]
            .reshape(packed["shape"])
            .astype(bool)
        )
        if (
            hashlib.sha256(mask.tobytes()).hexdigest()
            != packed["geometry"]["mask_sha256"]
        ):
            raise ValueError("mask hash mismatch")
        result = run_request(
            case["request"],
            output / case["id"],
            device="cuda",
            analytic_receipt=payload["cpu_controls"],
            mask_override=(mask, packed["geometry"]),
        )
        results[case["id"]] = result
        if result["status"] == "FAIL":
            break
    check = {
        "schema": "frontier.windtunnel.cuda-checks/1",
        "evidence_kind": "computational_check",
        "cases_completed": list(results),
    }
    if "cuda-repeat24" in results:
        repeat = results["cuda-repeat24"]
        fields = np.load(output / "cuda-repeat24/fields.npz")
        reference = payload["cpu_reference"]
        error = max(
            float(
                np.max(
                    np.abs(
                        fields[k][-1, ::8, ::8]
                        - np.asarray(reference["last_field_subset"][k])
                    )
                )
            )
            / (1.0 if k == "rho" else 0.04)
            for k in ("rho", "ux", "uy")
        )
        coefficient_error = max(
            abs(repeat["mean_Cd_last20pct"] - reference["Cd"]),
            abs(repeat["mean_Cl_last20pct"] - reference["Cl"]),
        )
        check.update(
            {
                "cpu_cuda_max_scaled_field_error": error,
                "cpu_cuda_abs_coefficient_error": coefficient_error,
                "repeat_passed": error <= 1e-6 and coefficient_error <= 1e-6,
            }
        )
    if "cuda-refine96" in results:
        history = results["cuda-refine96"]["force_history"]
        window = [
            r["Cd"]
            for r in history
            if 3.2 + 1e-10 < r["convective_time"] <= 4.0 + 1e-10
        ]
        check["Cd96_last20pct_before_t4"] = float(np.mean(window))
        if "cuda-complete48" in results:
            cd48 = results["cuda-complete48"]["mean_Cd_last20pct"]
            d24_48 = abs(payload["cpu_reference"]["Cd"] - cd48) / max(abs(cd48), 1e-12)
            d48_96 = abs(cd48 - check["Cd96_last20pct_before_t4"]) / max(
                abs(check["Cd96_last20pct_before_t4"]), 1e-12
            )
            check.update(
                {
                    "grid24_48_relative_drag_difference": d24_48,
                    "frozen_grid_bound_passed": d24_48 <= 0.2,
                    "grid48_96_relative_drag_difference": d48_96,
                    "successive_grid_difference_shrank": d48_96 < d24_48,
                }
            )
    (output / "checks.json").write_text(json.dumps(check, indent=2) + "\n")
    return check


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("command", choices=["build-input", "run"])
    parser.add_argument("path")
    parser.add_argument("--output", default="windtunnel-remote")
    args = parser.parse_args()
    print(
        json.dumps(
            build_input(args.path)
            if args.command == "build-input"
            else run_remote(args.path, args.output)
        )
    )
