"""Portable CPU-only frozen uncertainty batch; preserve partial and failed cases."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import gzip
from hashlib import sha256
import json
import multiprocessing
from pathlib import Path
import platform
import time

import mujoco
import numpy as np

from .model import ART, ROOT, dump, protocol, simulate
from .run import controls, paired_comparison


def save_trace(path, result):
    xml = result.pop("model_xml")
    path.with_suffix(".xml").write_text(xml)

    def scalar(value):
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError(type(value).__name__)

    encoded = json.dumps(
        result, separators=(",", ":"), allow_nan=False, default=scalar
    ).encode()
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
            stream.write(encoded)
    return {
        "path": str(path),
        "sha256": sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
        "uncompressed_json_sha256": sha256(encoded).hexdigest(),
        "xml_sha256": sha256(xml.encode()).hexdigest(),
    }


def endpoint(result, when):
    found = [frame for frame in result["frames"] if abs(frame["time_s"] - when) < 1e-7]
    if not found:
        return {
            "available": False,
            "reason": "No actual saved state at declared endpoint; no substitution",
            "response_count": None,
            "positive_work_J": None,
            "mean_lateral_displacement_m": None,
        }
    frame = found[0]
    initial = {x["id"]: x for x in result["frames"][0]["fish"]}
    distances = []
    for other in result["frames"]:
        positions = np.asarray([x["position_m"] for x in other["fish"]])
        pairs = np.linalg.norm(positions[:, None, :] - positions[None, :, :], axis=2)
        pairs[np.diag_indices(len(positions))] = np.inf
        distances.append(float(pairs.min()))
    return {
        "available": True,
        "time_s": frame["time_s"],
        "response_count": sum(x["escape_triggered"] for x in frame["fish"]),
        "positive_work_J": sum(x["positive_actuator_work_J"] for x in frame["fish"]),
        "mean_lateral_displacement_m": float(
            np.mean(
                [
                    x["position_m"][1] - initial[x["id"]]["position_m"][1]
                    for x in frame["fish"]
                ]
            )
        ),
        "min_saved_center_separation_m": min(distances),
        "separation_scope": "Saved whole-episode center distance only, not continuous mesh collision clearance.",
    }


def scenario(job):
    task, root, deadline = job
    if time.monotonic() > deadline:
        return {"id": task["id"], "status": "not-started: soft deadline reached"}
    started = time.monotonic()
    directory = Path(root) / task["id"]
    directory.mkdir(parents=True)
    try:
        p = json.loads((ART / "uncertainty-protocol.json").read_text())
        fixed = json.loads((ART / "protocol-refinement.json").read_text())
        params = deepcopy(fixed["parameters"])
        params.update(task["overrides"])
        case = {
            "id": task["id"],
            "n": 8,
            "feedback": True,
            "neighbors": task["neighbors"],
        }
        main = simulate(case, params, p["dt_s"], task["seed"])
        main_trace = save_trace(directory / "main.json.gz", main)
        dump(
            directory / "main-complete-before-half.json",
            {
                "id": task["id"],
                "status": "main complete; half-step pending at checkpoint",
                "main_summary": main["summary"],
                "trace": main_trace,
            },
        )
        fine = simulate(case, params, p["half_dt_s"], task["seed"])
        discrepancy = paired_comparison(main, fine)
        numeric = (
            discrepancy["max_position_difference_m"]
            <= protocol()["controls"]["dt_half_position_max_error_m"]
            and discrepancy["max_orientation_angle_rad"]
            <= protocol()["controls"]["dt_half_orientation_max_angle_rad"]
        )
        peak = main["summary"]["peaks"]
        actuator = {
            "torque": peak["torque_Nm"] <= params["joint_torque_limit_Nm"] + 1e-12,
            "joint_power": peak["positive_joint_power_W"]
            <= params["joint_positive_power_limit_W"] + 1e-12,
            "rate": peak["joint_rate_rad_s"] <= params["actual_rate_gate_rad_s"],
            "command_rate": peak["command_rate_rad_s"]
            <= params["command_rate_limit_rad_s"] + 1e-12,
            "work": max(main["summary"]["final_positive_work_J"])
            <= params["per_fish_positive_work_budget_J"]
            + params["work_budget_discrete_tolerance_J"],
        }
        metrics = endpoint(main, p["endpoint_time_s"])
        result = {
            "id": task["id"],
            "task": task,
            "status": "computed",
            "wall_seconds": time.monotonic() - started,
            "numeric_gate_passed": numeric,
            "actuator_gates": actuator,
            "discrepancy": discrepancy,
            "main_summary": main["summary"],
            "half_dt_summary": fine["summary"],
            "endpoint": metrics,
            "input_sha256": sha256(
                json.dumps(
                    {"params": params, "case": case, "seed": task["seed"]},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
            "shared_input_groups": [
                "same-v3a-geometry-and-VLM",
                "common-seed-" + str(task["seed"]),
            ],
            "traces": [main_trace, save_trace(directory / "half-dt.json.gz", fine)],
        }
        dump(directory / "result.json", result)
        return result
    except Exception as exc:
        result = {
            "id": task["id"],
            "task": task,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "wall_seconds": time.monotonic() - started,
        }
        dump(directory / "result.json", result)
        return result


def run(out, workers):
    if out.exists():
        raise ValueError("Output exists; refuse duplicate batch")
    if mujoco.__version__ != "3.17.0" or np.__version__ != "2.5.4":
        raise ValueError("Exact solver/NumPy pins required")
    p = json.loads((ART / "uncertainty-protocol.json").read_text())
    fixed = json.loads((ART / "protocol-refinement.json").read_text())
    out = out.resolve()
    out.mkdir(parents=True)
    check = controls(fixed)
    dump(out / "controls.json", check)
    if not check["passed"]:
        raise RuntimeError("Frozen same-job controls failed; batch not started")
    tasks = []
    for setting in p["settings"]:
        for seed in p["seeds"]:
            for neighbors in p["neighbor_modes"]:
                tasks.append(
                    {
                        "id": f"{setting['id']}-s{seed}-{'neighbors' if neighbors else 'ablated'}",
                        "setting": setting["id"],
                        "overrides": setting["overrides"],
                        "seed": seed,
                        "neighbors": neighbors,
                    }
                )
    assert len(tasks) == p["scenario_count"] == 28
    started = time.monotonic()
    deadline = started + p["soft_no_new_work_deadline_s"]
    results = []
    with ProcessPoolExecutor(
        max_workers=min(workers, 4), mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        futures = [pool.submit(scenario, (task, str(out), deadline)) for task in tasks]
        for future in as_completed(futures):
            results.append(future.result())
            dump(
                out / "progress.json",
                {"expected": len(tasks), "returned": len(results), "results": results},
            )
            print(
                json.dumps(
                    {
                        "returned": len(results),
                        "id": results[-1]["id"],
                        "status": results[-1]["status"],
                    }
                ),
                flush=True,
            )
    paired = []
    for setting in p["settings"]:
        for seed in p["seeds"]:
            values = [
                x
                for x in results
                if x.get("task", {}).get("setting") == setting["id"]
                and x.get("task", {}).get("seed") == seed
            ]
            good = [
                x
                for x in values
                if x["status"] == "computed"
                and x["numeric_gate_passed"]
                and all(x["actuator_gates"].values())
                and x["endpoint"]["available"]
            ]
            item = {
                "setting": setting["id"],
                "seed": seed,
                "eligible": len(good) == 2,
                "response_count_difference": None,
                "lateral_displacement_difference_m": None,
                "positive_work_difference_J": None,
            }
            if len(good) == 2:
                neighbor = next(x for x in good if x["task"]["neighbors"])
                ablation = next(x for x in good if not x["task"]["neighbors"])
                for key, source in [
                    ("response_count_difference", "response_count"),
                    (
                        "lateral_displacement_difference_m",
                        "mean_lateral_displacement_m",
                    ),
                    ("positive_work_difference_J", "positive_work_J"),
                ]:
                    item[key] = (
                        neighbor["endpoint"][source] - ablation["endpoint"][source]
                    )
            paired.append(item)
    summary = {
        "schema": "frontier.ecology.uncertainty-results/1",
        "status": "complete"
        if len(results) == len(tasks)
        and all(x["status"] == "computed" for x in results)
        else "partial or failed",
        "scenario_count": len(tasks),
        "returned_count": len(results),
        "computed_count": sum(x["status"] == "computed" for x in results),
        "paired_comparisons": paired,
        "results": results,
        "scope": "Declared engineering scenarios only; no interactions estimated or biological success probability. All raw failures/domain stops remain visible.",
        "biological_success_probability": None,
        "wall_seconds": time.monotonic() - started,
        "environment": {
            "python": platform.python_version(),
            "mujoco": mujoco.__version__,
            "numpy": np.__version__,
            "device": "MuJoCo CPU rigid-body integration; no GPU renderer",
        },
        "protocol_sha256": sha256(
            (ART / "uncertainty-protocol.json").read_bytes()
        ).hexdigest(),
        "dollars": None,
        "source_hashes": {
            str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
            for path in (ROOT / "engineering/ecology").glob("*.py")
        },
    }
    dump(out / "summary.json", summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    run(args.out, args.workers)
