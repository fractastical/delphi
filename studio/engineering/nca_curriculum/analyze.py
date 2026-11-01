"""Audit frozen curriculum returns and describe four dependent-probe seed pairs.

This postprocessor never trains a model or changes the preregistered criteria.
Only preselected saved states are rendered. Historical results stay separate.
"""

import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

from engineering.nca_pattern.analyze import (
    artifact_path,
    digest,
    load,
    visible_metrics,
)
from engineering.nca_pattern.model import ROOT, dump

ART = ROOT / "artifacts/nca-curriculum"


def expected_identities(cfg):
    """All declared probes, including negatives and cases not started in time."""
    return {
        (f"{regime}-s{seed}", kind, update_seed)
        for seed in cfg["training"]["model_seeds"]
        for regime in cfg["training"]["regimes"]
        for update_seed in cfg["evaluation"]["update_seeds"]
        for kind in [
            "persistence",
            *cfg["evaluation"]["damage"]["masks"],
            *(
                ["all-erased-negative"]
                if update_seed == cfg["evaluation"]["negative_all_erased"]["update_seed"]
                else []
            ),
        ]
    }


def match(metrics):
    return metrics["silhouette_IoU"] >= 0.75 and metrics["rgba_MSE"] <= 0.02


def predicate(item, final, final_rgba):
    """Recompute fixed predicates; intermediate checkpoints use saved metrics."""
    if final is None:
        return False
    if item["kind"] == "all-erased-negative":
        return bool(
            item["final"]["max_abs_state"] == 0
            and np.count_nonzero(final_rgba) == 0
        )
    if item["status"] != "complete":
        return False
    if item["kind"] == "persistence":
        points = [x for x in item["metrics"] if x["update_step"] >= 256]
        # The full, regular checkpoint schedule is checked independently below.
        return bool(points) and all(match(x) for x in points)
    return bool(item["predamage"] is not None and match(item["predamage"]) and match(final))


def paired_effects(cfg, records):
    """Count fixed-denominator effects per training pair, never pool as iid."""
    result = []
    groups = {
        "all_design": ["persistence", *cfg["evaluation"]["damage"]["masks"]],
        "persistence": ["persistence"],
        "damage": cfg["evaluation"]["damage"]["masks"],
        **{name: [name] for name in cfg["evaluation"]["damage"]["masks"]},
    }
    for seed in cfg["training"]["model_seeds"]:
        for group, kinds in groups.items():
            counts = {}
            for regime in cfg["training"]["regimes"]:
                subset = [
                    x for x in records
                    if x["model_id"] == f"{regime}-s{seed}" and x["kind"] in kinds
                ]
                counts[regime] = {
                    "passed": sum(x["recomputed_passed"] for x in subset),
                    "executed": len(subset),
                    "declared": len(kinds) * len(cfg["evaluation"]["update_seeds"]),
                }
            a, b = (counts[x] for x in ["damage-pool", "curriculum-pool"])
            complete = all(x["executed"] == x["declared"] for x in [a, b])
            result.append({
                "initialization_seed": seed,
                "group": group,
                "regimes": counts,
                "both_evaluation_sets_executed": complete,
                "curriculum_minus_baseline_fraction": (
                    (b["passed"] - a["passed"]) / a["declared"] if complete else None
                ),
            })
    return result


def safe_file(root, name):
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Returned path escapes output root")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing/nonregular returned artifact")
    return path


def verify_receipt(root):
    receipt = load(root / "job-receipt.json")
    seen = set()
    for item in receipt["files"]:
        if item["path"] in seen:
            raise ValueError("Duplicate receipt file")
        seen.add(item["path"])
        path = safe_file(root, item["path"])
        if digest(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError(f"Returned digest/size mismatch: {item['path']}")
    actual = {
        str(x.relative_to(root)) for x in root.rglob("*")
        if x.is_file() and x.name != "job-receipt.json"
    }
    if actual != seen:
        raise ValueError("Receipt file set differs from actual returned tree")
    return receipt


def compare_metrics(actual, stored, identity, checks, selector):
    for name, value in actual.items():
        if name not in stored:
            raise ValueError(f"Missing metric {name}")
        checks.append({
            "identity": list(identity), "selector": selector, "metric": name,
            "actual": value, "stored": stored[name], "exact": value == stored[name],
            "absolute_difference": abs(value - stored[name]),
            "fixed_roundoff_match": bool(np.isclose(
                value, stored[name], rtol=1e-10, atol=1e-12
            )),
        })


def validate_summary_counts(summary, counts, checkpoints):
    if (
        summary["training_models_expected"] != 8
        or summary["training_models_completed"] != checkpoints
        or summary["evaluation_runs_expected"] != 200
        or summary["evaluation_runs_executed"]
        != counts["design_executed"] + counts["negative_executed"]
        or summary["design_target_tests"]["declared_expected"] != 192
        or summary["all_erased_negative_controls"]["declared_expected"] != 8
    ):
        raise ValueError("Native summary expected/completed/executed counts disagree")


def audit(root, out, inputs=ART):
    cfg = load(inputs / "runtime-protocol.json")
    receipt = verify_receipt(root)
    sources = load(inputs / "execution-source-manifest.json")
    expected_sources = {x["path"]: x["sha256"] for x in sources["files"]}
    if receipt["sources"] != expected_sources:
        raise ValueError("Executed source manifest mismatch")
    for item in sources["files"]:
        path = inputs / "execution-source" / item["path"]
        if digest(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError("Pinned execution snapshot changed")
    if (
        receipt["protocol_sha256"] != digest(inputs / "runtime-protocol.json")
        or digest(root / "protocol.json") != receipt["protocol_sha256"]
        or cfg["curriculum_plan_sha256"] != digest(inputs / "protocol.json")
        or cfg["independent_evaluation_manifest_sha256"]
        != digest(inputs / "evaluation-manifest.json")
    ):
        raise ValueError("Frozen plan/runtime/evaluation protocol identity changed")
    packet = load(inputs / "packet.json")
    if digest(inputs / "nca-curriculum-h100.tar.gz") != packet["archive_sha256"]:
        raise ValueError("Frozen submitted archive changed")
    target_path = ROOT / "artifacts/nca-seed-placement/target.npz"
    if digest(target_path) != cfg["target"]["sha256"]:
        raise ValueError("Target input changed")
    target = np.load(target_path, allow_pickle=False)
    goal = np.moveaxis(target["rgba"], -1, 0).astype(np.float64)
    ray = target["ray_mask"]
    result = {
        "schema": "frontier.nca.curriculum.return-audit/1",
        "analysis_code_sha256": digest(Path(__file__)),
        "protocol_sha256": receipt["protocol_sha256"],
        "job_receipt_sha256": digest(root / "job-receipt.json"),
        "files_checked": len(receipt["files"]),
        "bytes_checked": sum(x["bytes"] for x in receipt["files"]),
        "receipt_status": receipt["status"],
        "checks": [],
        "scope": "Returned bytes and saved metrics/state audit; no independent training rerun or biological validation. Four paired initialization units; probes share weights.",
    }
    if not (root / "summary.json").exists():
        result["failure"] = load(root / "failure.json")
        dump(out / "audit.json", result)
        return result
    summary = load(root / "summary.json")
    barrier_path = root / "checkpoint-before-holdout.json"
    barrier = load(barrier_path)
    if digest(barrier_path) != summary["checkpoint_barrier_sha256"]:
        raise ValueError("Checkpoint barrier changed")
    guard = receipt["evaluation_read_guard"]
    if (
        guard != load(root / "evaluation-read-guard.json")
        or guard["blocked_early_attempts"] != 1
        or not guard["released_after_checkpoint_barrier"]
        or guard["checkpoint_barrier_sha256"] != digest(barrier_path)
        or guard["mask_reads_after_release"] < 1
        or not barrier["training_phase_finished"]
        or barrier["heldout_masks_loaded_yet"]
    ):
        raise ValueError("Evaluation read-guard/barrier event inconsistency")
    model_ids = {
        f"{regime}-s{seed}" for seed in cfg["training"]["model_seeds"]
        for regime in cfg["training"]["regimes"]
    }
    models = {x["id"]: x for x in summary["models"]}
    if set(models) != model_ids or len(summary["models"]) != 8:
        raise ValueError("Training model identities differ from frozen plan")
    if barrier["models"] != summary["models"]:
        raise ValueError("Summary models differ from checkpoint barrier")
    checkpoints = []
    for model in models.values():
        if model["id"] != f"{model['regime']}-s{model['initialization_seed']}":
            raise ValueError("Model ID disagrees with regime/seed")
        if model["status"] == "complete":
            if (
                model["training_steps"] != 2000 or model["heldout_data_read"]
                or datetime.fromisoformat(model["finished_utc"])
                > datetime.fromisoformat(barrier["created_utc"])
            ):
                raise ValueError("Final-model training count/order mismatch")
            checkpoint = model["final_checkpoint"]
            if digest(artifact_path(root, checkpoint["path"])) != checkpoint["sha256"]:
                raise ValueError("Final checkpoint changed")
            checkpoints.append(checkpoint)
    if checkpoints != barrier["completed_checkpoints"]:
        raise ValueError("Completed checkpoint list differs from barrier")
    pairs = []
    for seed in cfg["training"]["model_seeds"]:
        a, b = (models[f"{regime}-s{seed}"] for regime in cfg["training"]["regimes"])
        if a["status"] == b["status"] == "complete":
            matched = (
                a["initial_model_tensor_sha256"] == b["initial_model_tensor_sha256"]
                and a["CA_updates_total"] == b["CA_updates_total"]
            )
            pairs.append({"seed": seed, "matched_initial_weights_and_update_budget": matched})
            if not matched:
                raise ValueError("Training pair initial weights/update budget differs")
    if pairs != load(root / "paired-training-checks.json"):
        raise ValueError("Native paired checks differ from recomputation")
    identities, records, traces = set(), [], {}
    expected = expected_identities(cfg)
    for item in summary["evaluations"]:
        identity = (item["model_id"], item["kind"], item["update_seed"])
        if identity not in expected or identity in identities:
            raise ValueError("Unexpected/duplicate evaluation identity")
        identities.add(identity)
        if item["status"].startswith("not-started"):
            continue
        checkpoint = models[item["model_id"]]["final_checkpoint"]
        if (
            checkpoint["sha256"] != item["checkpoint_sha256"]
            or item["checkpoint_barrier_sha256"] != digest(barrier_path)
        ):
            raise ValueError("Evaluation model/checkpoint identity mismatch")
        path = artifact_path(root, item["trajectory"]["path"])
        if digest(path) != item["trajectory"]["sha256"]:
            raise ValueError("Evaluation trajectory changed")
        with np.load(path, allow_pickle=False) as data:
            visible = data["final_rgba"].astype(np.float64)
            if visible.shape != (4, 64, 64):
                raise ValueError("Raw visible state has wrong shape")
            final = visible_metrics(visible, goal, ray) if np.isfinite(visible).all() else None
            if final is not None:
                compare_metrics(final, item["final"], identity, result["checks"], "final_rgba")
                if match(final) != item["final"]["design_match"]:
                    raise ValueError("Raw final-state design predicate differs")
            if item["status"] == "complete":
                horizon = 2048 if item["kind"] == "persistence" else 768
                if item["updates_completed"] != horizon:
                    raise ValueError("Complete evaluation stopped at wrong update")
                actual_steps = {x["update_step"] for x in item["metrics"]}
                if not set(range(0, horizon + 1, 16)).issubset(actual_steps):
                    raise ValueError("Complete evaluation missing metric checkpoints")
            passed = predicate(item, final, visible)
            if passed != item["criterion_passed"]:
                raise ValueError("Recomputed criterion differs from native result")
            records.append({
                "model_id": identity[0], "kind": identity[1], "update_seed": identity[2],
                "status": item["status"], "recomputed_passed": passed,
                "final": final, "zero_visible_final": bool(np.count_nonzero(visible) == 0),
            })
            selected = (
                identity[1] == cfg["evaluation"]["trace_damage_kind"]
                and identity[2] == cfg["evaluation"]["trace_update_seed"]
            )
            if bool(data["recorded_trace"]) != selected:
                raise ValueError("Preselected trace membership changed")
            if selected:
                traces[identity[0]] = {k: data[k].copy() for k in data.files}
                history = {(x["update_step"], x["phase"]): x for x in item["metrics"]}
                for state, step, phase in zip(
                    data["rgba"], data["frame_update_step"], data["frame_phase"], strict=True
                ):
                    values = visible_metrics(state.astype(np.float64), goal, ray)
                    compare_metrics(values, history[(int(step), str(phase))], identity,
                                    result["checks"], f"rgba[{step},{phase}]")
                if item["status"] == "complete":
                    full = {
                        (int(s), str(p)): x for s, p, x in zip(
                            data["full_state_update_step"], data["full_state_phase"],
                            data["full_state"], strict=True
                        )
                    }
                    if (
                        set(full) != {(0, "seed"), (256, "before-damage"),
                                      (256, "after-damage"), (257, "recovery"),
                                      (768, "recovery")}
                        or len(data["full_state"]) != 5
                    ):
                        raise ValueError("Complete selected whole-state schedule changed")
                    for (step, phase), state in full.items():
                        if state.shape != (16, 64, 64) or not np.isfinite(state).all():
                            raise ValueError("Complete selected whole state invalid")
                        values = visible_metrics(state[:4].astype(np.float64), goal, ray)
                        values["max_abs_state"] = float(np.max(abs(state)))
                        compare_metrics(values, history[(step, phase)], identity,
                                        result["checks"], f"full_state[{step},{phase}]")
                    masks = np.load(inputs / "evaluation-masks.npz", allow_pickle=False)
                    before, after = (full[(256, p)] for p in ["before-damage", "after-damage"])
                    if not np.array_equal(after, before * ~masks[identity[1]][None]):
                        raise ValueError("Saved whole-state damage operator differs")
    design = [x for x in records if x["kind"] != "all-erased-negative"]
    negatives = [x for x in records if x["kind"] == "all-erased-negative"]
    counts = {
        "design_declared": 192, "design_executed": len(design),
        "design_passed": sum(x["recomputed_passed"] for x in design),
        "negative_declared": 8, "negative_executed": len(negatives),
        "negative_passed": sum(x["recomputed_passed"] for x in negatives),
    }
    validate_summary_counts(summary, counts, len(checkpoints))
    if (
        summary["design_target_tests"]["executed"] != counts["design_executed"]
        or summary["design_target_tests"]["passed"] != counts["design_passed"]
        or summary["all_erased_negative_controls"]["executed"] != counts["negative_executed"]
        or summary["all_erased_negative_controls"]["absorbing_state_checks_passed"]
        != counts["negative_passed"]
    ):
        raise ValueError("Native count differs from recomputed predicates")
    checks = result["checks"]
    result.update(
        counts=counts, evaluated_identities=len(identities), expected_identities=len(expected),
        missing_identities=[list(x) for x in sorted(expected - identities)],
        complete_checkpoint_count=len(checkpoints), paired_training_checks=pairs,
        exact_metric_reproduction=all(x["exact"] for x in checks),
        fixed_roundoff_metric_reproduction=all(x["fixed_roundoff_match"] for x in checks),
        nonexact_metric_count=sum(not x["exact"] for x in checks),
        max_metric_absolute_difference=max((x["absolute_difference"] for x in checks), default=0),
        records=records, per_pair_effects=paired_effects(cfg, records),
        status_counts=dict(Counter(x["status"] for x in summary["evaluations"])),
        selected_traces=len(traces), environment=receipt["environment"], device=receipt["device"],
        wall_seconds=receipt["wall_seconds"], read_guard=guard,
    )
    dump(out / "audit.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, default=ART)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    result = audit(args.root, args.out, args.inputs)
    print({k: v for k, v in result.items() if k not in ["checks", "records", "per_pair_effects"]})


if __name__ == "__main__":
    main()
