"""One bounded CUDA training/evaluation workload with a checkpoint-before-holdout barrier."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import platform
import time

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import numpy as np
import torch

from .evaluate import evaluate
from .model import (
    ART,
    ROOT,
    configure,
    cpu_controls,
    cuda_controls,
    dump,
    protocol,
    target,
)
from .train import train_one
from .curriculum_policy import install_read_guard, validate_manifest


def run(out):
    if out.exists():
        raise ValueError("Output exists; refuse duplicate job")
    out = out.resolve()
    out.mkdir(parents=True)
    start = time.monotonic()
    cfg = protocol()
    read_guard = install_read_guard(ART / "heldout-masks.npz")
    try:
        with open(ART / "heldout-masks.npz", "rb"):
            pass
    except RuntimeError:
        pass
    else:
        raise RuntimeError("Evaluation read guard failed its negative control")
    status = "starting"
    training = []
    evaluation = []
    failure = None
    receipt = {
        "schema": "frontier.nca.job-receipt/1",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": sha256((ART / "protocol.json").read_bytes()).hexdigest(),
        "target_sha256": cfg["target"]["sha256"],
        "sources": {
            str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
            for path in (ROOT / "engineering/nca_pattern").glob("*.py")
        },
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "numpy": np.__version__,
            "cuda_runtime": torch.version.cuda,
        },
        "device": None,
        "dollars": None,
        "model_generation_or_DNA_calls": 0,
        "empirical_validation": "unknown",
    }
    dump(out / "protocol.json", cfg)
    try:
        configure()
        target("cpu")
        status = "CPU controls"
        cpu = cpu_controls()
        dump(out / "cpu-controls.json", cpu)
        if not cpu["passed"]:
            raise RuntimeError("Frozen CPU controls failed")
        status = "CUDA controls"
        cuda = cuda_controls()
        dump(out / "cuda-controls.json", cuda)
        if not cuda["passed"]:
            raise RuntimeError("Frozen CPU/CUDA controls failed")
        receipt["device"] = cuda["actual_device"]
        torch.cuda.reset_peak_memory_stats()
        deadline = start + cfg["resources"]["training_soft_deadline_s"]
        status = "training"
        for model_seed in cfg["training"]["model_seeds"]:
            for regime in cfg["training"]["regimes"]:
                if time.monotonic() > deadline:
                    result = {
                        "id": f"{regime}-s{model_seed}",
                        "regime": regime,
                        "initialization_seed": model_seed,
                        "status": "not-started: training deadline",
                        "training_steps": 0,
                    }
                else:
                    result = train_one(regime, model_seed, out / "training", deadline)
                training.append(result)
                dump(
                    out / "training-progress.json", {"expected": 8, "models": training}
                )
        pair_checks = []
        for model_seed in cfg["training"]["model_seeds"]:
            pair = [
                x
                for x in training
                if x["initialization_seed"] == model_seed and x["status"] == "complete"
            ]
            if len(pair) == 2:
                matched = (
                    pair[0]["initial_model_tensor_sha256"]
                    == pair[1]["initial_model_tensor_sha256"]
                    and pair[0]["CA_updates_total"] == pair[1]["CA_updates_total"]
                )
                pair_checks.append(
                    {
                        "seed": model_seed,
                        "matched_initial_weights_and_update_budget": matched,
                    }
                )
                if not matched:
                    raise RuntimeError("Paired initialization/update budget mismatch")
        dump(out / "paired-training-checks.json", pair_checks)
        barrier = {
            "schema": "frontier.nca.checkpoint-barrier/1",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "training_phase_finished": True,
            "heldout_masks_loaded_yet": False,
            "protocol_sha256": receipt["protocol_sha256"],
            "models": training,
            "completed_checkpoints": [
                x["final_checkpoint"] for x in training if x["status"] == "complete"
            ],
            "selection": "Only frozen final2000-step checkpoints; no holdout evaluation or model selection has occurred.",
        }
        barrier_path = out / "checkpoint-before-holdout.json"
        dump(barrier_path, barrier)
        read_guard["released_after_checkpoint_barrier"] = True
        read_guard["checkpoint_barrier_sha256"] = sha256(barrier_path.read_bytes()).hexdigest()
        dump(out / "evaluation-read-guard.json", read_guard)
        print(
            {
                "stage": "checkpoint_barrier",
                "sha256": sha256(barrier_path.read_bytes()).hexdigest(),
                "completed_models": len(barrier["completed_checkpoints"]),
            },
            flush=True,
        )
        validate_manifest(ART / "evaluation-manifest.json", cfg)
        status = "holdout evaluation"
        evaluation = evaluate(
            training,
            out / "evaluation",
            barrier_path,
            start + cfg["resources"]["total_soft_deadline_s"],
        )
        positive = [x for x in evaluation if x["kind"] != "all-erased-negative" and not x["status"].startswith("not-started")]
        negatives = [x for x in evaluation if x["kind"] == "all-erased-negative" and not x["status"].startswith("not-started")]
        actual = [
            x for x in evaluation if x["status"] != "not-started: evaluation deadline"
        ]
        expected = cfg["evaluation"]["total_expected_evaluation_runs"]
        complete_training = len(training) == 8 and all(
            x["status"] == "complete" for x in training
        )
        status = (
            "complete"
            if complete_training
            and len(actual) == expected
            and all(x["status"] == "complete" for x in actual)
            else "partial or failed; see all model/evaluation statuses"
        )
        summary = {
            "schema": "frontier.nca.inverse-pattern-results/1",
            "status": status,
            "training_models_expected": 8,
            "training_models_completed": sum(
                x["status"] == "complete" for x in training
            ),
            "evaluation_runs_expected": expected,
            "evaluation_runs_executed": len(actual),
            "design_target_tests": {
                "declared_expected": 192,
                "executed": len(positive),
                "passed": sum(x["criterion_passed"] for x in positive),
                "scope": "Fraction over declared computational update/damage scenarios only; not biological success probability",
            },
            "all_erased_negative_controls": {
                "declared_expected": 8,
                "executed": len(negatives),
                "absorbing_state_checks_passed": sum(
                    x["criterion_passed"] for x in negatives
                ),
            },
            "models": training,
            "evaluations": evaluation,
            "biological_success_probability": None,
            "limitations": [
                "Hidden channels have no measured biochemical meaning.",
                "One design target, not a new-target generalization benchmark.",
                "No genomic/neuronal implementation or tissue regeneration established.",
                "Incomplete training, model failures and failed predicates retained.",
            ],
            "checkpoint_barrier_sha256": sha256(barrier_path.read_bytes()).hexdigest(),
        }
        dump(out / "summary.json", summary)
        dump(out / "evaluation-read-guard.json", read_guard)
    except Exception as exc:
        failure = {"stage": status, "error": f"{type(exc).__name__}: {exc}"}
        status = "failed"
        dump(out / "failure.json", failure)
    finally:
        receipt.update(
            evaluation_read_guard=read_guard,
            status=status,
            failure=failure,
            finished_utc=datetime.now(timezone.utc).isoformat(),
            wall_seconds=time.monotonic() - start,
        )
        if torch.cuda.is_available():
            receipt["max_cuda_memory_allocated_bytes"] = (
                torch.cuda.max_memory_allocated()
            )
        files = [
            path
            for path in out.rglob("*")
            if path.is_file() and path.name != "job-receipt.json"
        ]
        receipt["files"] = [
            {
                "path": str(path.relative_to(out)),
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
            for path in files
        ]
        receipt["output_bytes"] = sum(x["bytes"] for x in receipt["files"])
        receipt["output_cap_exceeded"] = (
            receipt["output_bytes"] > cfg["resources"]["output_raw_cap_bytes"]
        )
        dump(out / "job-receipt.json", receipt)
        print(
            {
                "stage": "final",
                "status": status,
                "output_bytes": receipt["output_bytes"],
                "output_cap_exceeded": receipt["output_cap_exceeded"],
            },
            flush=True,
        )
    return 0 if status == "complete" and not receipt["output_cap_exceeded"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.out))
