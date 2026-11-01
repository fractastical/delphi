"""Run only the two originally unstarted arms, preserving the original partial."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import json
import multiprocessing
from pathlib import Path
import time

import mujoco
import numpy as np

from .batch import scenario
from .model import ART, ROOT, dump
from .remote import source_inputs
from .run import controls


def validate_missing_tasks(cfg, summary, original):
    missing = {
        x["id"]
        for x in summary["results"]
        if x["status"] == "not-started: soft deadline reached"
    }
    done = {x["id"] for x in summary["results"] if x["status"] == "computed"}
    selected = {x["id"] for x in cfg["tasks"]}
    if (
        selected != missing
        or len(selected) != 2
        or selected & done
        or done != set(cfg["prohibited_already_computed_ids"])
    ):
        raise ValueError("Continuation would repeat/change original scientific arms")
    expected = {
        f"{setting['id']}-s{seed}-{'neighbors' if neighbors else 'ablated'}": {
            "id": f"{setting['id']}-s{seed}-{'neighbors' if neighbors else 'ablated'}",
            "setting": setting["id"],
            "overrides": setting["overrides"],
            "seed": seed,
            "neighbors": neighbors,
        }
        for setting in original["settings"]
        for seed in original["seeds"]
        for neighbors in original["neighbor_modes"]
    }
    if any(task != expected[task["id"]] for task in cfg["tasks"]):
        raise ValueError("Missing task parameter/seed recipe changed")
    return cfg["tasks"]


def selected_tasks():
    cfg = json.loads((ART / "continuation-protocol.json").read_text())
    source = ROOT / cfg["original_summary_path"]
    if sha256(source.read_bytes()).hexdigest() != cfg["original_summary_sha256"]:
        raise ValueError("Original partial summary changed")
    summary = json.loads(source.read_text())
    original_path = ART / "uncertainty-protocol.json"
    if sha256(original_path.read_bytes()).hexdigest() != summary["protocol_sha256"]:
        raise ValueError("Original scientific protocol changed")
    validate_missing_tasks(cfg, summary, json.loads(original_path.read_text()))
    for path, digest in summary["source_hashes"].items():
        if sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise ValueError("Original core solver/source changed")
    return cfg


def run(out):
    if out.exists():
        raise ValueError("Fresh output required; original results not overwritten")
    if mujoco.__version__ != "3.17.0" or np.__version__ != "2.5.4":
        raise ValueError("Exact original dependency pins required")
    cfg = selected_tasks()
    inputs = source_inputs()
    out = out.resolve()
    out.mkdir(parents=True)
    check = controls(json.loads((ART / "protocol-refinement.json").read_text()))
    dump(out / "controls.json", check)
    if not check["passed"]:
        raise RuntimeError("Unchanged same-job controls failed")
    started = time.monotonic()
    results = []
    with ProcessPoolExecutor(
        max_workers=2, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        futures = [
            pool.submit(scenario, (task, str(out), started + 450))
            for task in cfg["tasks"]
        ]
        for future in as_completed(futures):
            results.append(future.result())
            dump(out / "progress.json", {"expected": 2, "results": results})
    result = {
        "schema": "frontier.ecology.continuation-results/1",
        "status": "computed requested missing arms"
        if len(results) == 2 and all(x["status"] == "computed" for x in results)
        else "partial or failed",
        "original_summary_sha256": cfg["original_summary_sha256"],
        "continuation_protocol_sha256": sha256(
            (ART / "continuation-protocol.json").read_bytes()
        ).hexdigest(),
        "original_partial_unchanged": True,
        "results": results,
        "wall_seconds": time.monotonic() - started,
        "dollars": None,
        "environment": {
            "mujoco": mujoco.__version__,
            "numpy": np.__version__,
            "device": "CPU",
        },
        "scope": "Separate bounded missing-only execution; original partial status and all26 results preserved.",
    }
    dump(out / "summary.json", result)
    dump(out / "source-download-receipt.json", inputs)
    print({"status": result["status"], "scenarios": len(results)}, flush=True)
    return 0 if result["status"] == "computed requested missing arms" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.out))
