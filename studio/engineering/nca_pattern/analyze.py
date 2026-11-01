"""Audit and display returned NCA states without selecting a successful model."""

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .model import ART, ROOT, dump


def load(path):
    def reject(value):
        raise ValueError(f"nonfinite JSON {value}")

    return json.loads(path.read_bytes(), parse_constant=reject)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def artifact_path(root, original):
    """Map only frozen job-relative result paths; never fetch arbitrary paths."""
    parts = Path(original).parts
    for marker in ("evaluation", "training"):
        if marker in parts:
            candidate = root.joinpath(*parts[parts.index(marker) :])
            if candidate.resolve().is_relative_to(root.resolve()):
                return candidate
    raise ValueError("Unrecognized returned artifact path")


def image_rgba(values, size):
    rgba = np.moveaxis(values, 0, -1)
    if not np.isfinite(rgba).all():
        raise ValueError("Cannot display nonfinite raw state")
    # Clipping is only for display, never for reported loss/IoU or saved state.
    layer = Image.fromarray(np.uint8(np.clip(rgba, 0, 1) * 255), "RGBA")
    background = Image.new("RGBA", (64, 64), "#173044")
    background.alpha_composite(layer)
    return background.convert("RGB").resize((size, size), Image.Resampling.NEAREST)


def visible_metrics(visible, goal, ray):
    predicted = visible[3] > 0.1
    foreground = goal[3] > 0.1
    union = np.count_nonzero(predicted | foreground)
    metrics = {
        "rgba_MSE": float(np.mean((visible - goal) ** 2)),
        "silhouette_IoU": float(np.count_nonzero(predicted & foreground) / union)
        if union
        else 0.0,
        "living_pixels": int(predicted.sum()),
        "ray_RGB_MSE": float(np.mean((visible[:3, ray] - goal[:3, ray]) ** 2)),
    }
    return metrics


def audit(root, out, inputs=ART):
    cfg = load(inputs / "protocol.json")
    if digest(inputs / "target.npz") != cfg["target"]["sha256"]:
        raise ValueError("Analysis target bytes do not match protocol")
    receipt = load(root / "job-receipt.json")
    for item in receipt["files"]:
        path = root / item["path"]
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Receipt path escapes output")
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise ValueError("Returned file digest/size mismatch")
    if receipt["protocol_sha256"] != digest(inputs / "protocol.json"):
        raise ValueError("Frozen protocol changed")
    for relative, expected in receipt["sources"].items():
        if digest(ROOT / relative) != expected:
            raise ValueError("Frozen source changed")
    result = {
        "schema": "frontier.nca.return-audit/1",
        "job_receipt_sha256": digest(root / "job-receipt.json"),
        "job_status": receipt["status"],
        "files_checked": len(receipt["files"]),
        "bytes_checked": sum(x["bytes"] for x in receipt["files"]),
        "environment": receipt["environment"],
        "device": receipt["device"],
        "checks": [],
        "input_artifacts": str(inputs),
        "target_sha256": digest(inputs / "target.npz"),
        "seed_xy": np.load(inputs / "target.npz")["seed_xy"].tolist(),
        "evaluation_reused_from_parent": "seed_placement_follow_up" in cfg,
        "scope": "Returned-byte integrity and independent saved-visible-state metric recomputation; not biological validation or independent training replication.",
    }
    if not (root / "summary.json").exists():
        result["failure"] = load(root / "failure.json")
        dump(out / "audit.json", result)
        return result
    summary = load(root / "summary.json")
    barrier_path = root / "checkpoint-before-holdout.json"
    barrier = load(barrier_path)
    if digest(barrier_path) != summary["checkpoint_barrier_sha256"]:
        raise ValueError("Checkpoint barrier pin changed")
    checkpoints = {x["sha256"] for x in barrier["completed_checkpoints"]}
    for model in barrier["models"]:
        if model["status"] == "complete" and (
            model["training_steps"] != 2000
            or datetime.fromisoformat(model["finished_utc"])
            > datetime.fromisoformat(barrier["created_utc"])
        ):
            raise ValueError("Final checkpoint count/time barrier mismatch")
    for checkpoint in barrier["completed_checkpoints"]:
        if digest(artifact_path(root, checkpoint["path"])) != checkpoint["sha256"]:
            raise ValueError("Checkpoint bytes changed")
    target = np.load(inputs / "target.npz")
    goal = np.moveaxis(target["rgba"], -1, 0).astype(np.float64)
    ray = target["ray_mask"]
    identities = set()
    counts = {
        "design_executed": 0,
        "design_passed": 0,
        "negative_executed": 0,
        "negative_passed": 0,
    }
    traces = {}
    zero_visible_design_finals = 0
    for item in summary["evaluations"]:
        identity = (item["model_id"], item["kind"], item["update_seed"])
        if identity in identities:
            raise ValueError("Duplicate evaluation identity")
        identities.add(identity)
        if item["status"].startswith("not-started"):
            continue
        if item["checkpoint_sha256"] not in checkpoints or item[
            "checkpoint_barrier_sha256"
        ] != digest(barrier_path):
            raise ValueError("Evaluation checkpoint/barrier mismatch")
        path = artifact_path(root, item["trajectory"]["path"])
        if digest(path) != item["trajectory"]["sha256"]:
            raise ValueError("Evaluation trajectory changed")
        with np.load(path, allow_pickle=False) as data:
            visible = data["final_rgba"].astype(np.float64)
            metrics = visible_metrics(visible, goal, ray)
            for key, actual in metrics.items():
                stored = item["final"][key]
                result["checks"].append(
                    {
                        "identity": list(identity),
                        "metric": key,
                        "actual": actual,
                        "stored": stored,
                        "exact": actual == stored,
                        "fixed_roundoff_match": bool(
                            np.isclose(actual, stored, rtol=1e-10, atol=1e-12)
                        ),
                        "absolute_difference": abs(actual - stored),
                    }
                )
            match = metrics["silhouette_IoU"] >= 0.75 and metrics["rgba_MSE"] <= 0.02
            if match != item["final"]["design_match"]:
                raise ValueError("Design predicate mismatch")
            if item["kind"] == "persistence":
                considered = [x for x in item["metrics"] if x["update_step"] >= 256]
                passed = (
                    item["status"] == "complete"
                    and bool(considered)
                    and all(
                        x["silhouette_IoU"] >= 0.75 and x["rgba_MSE"] <= 0.02
                        for x in considered
                    )
                )
            elif item["kind"] == "all-erased-negative":
                passed = (
                    item["final"]["max_abs_state"] == 0
                    and np.count_nonzero(visible) == 0
                )
            else:
                before = item["predamage"]
                passed = (
                    item["status"] == "complete"
                    and before is not None
                    and before["silhouette_IoU"] >= 0.75
                    and before["rgba_MSE"] <= 0.02
                    and match
                )
            if bool(passed) != item["criterion_passed"]:
                raise ValueError("Saved-metric predicate disagrees")
            name = "negative" if item["kind"] == "all-erased-negative" else "design"
            if name == "design" and np.count_nonzero(visible) == 0:
                zero_visible_design_finals += 1
            counts[name + "_executed"] += 1
            counts[name + "_passed"] += int(passed)
            if bool(data["recorded_trace"]):
                traces[identity] = {k: data[k].copy() for k in data.files}
    result.update(
        counts=counts,
        zero_visible_final_design_count=zero_visible_design_finals,
        evaluation_identities=len(identities),
        checkpoint_count=len(checkpoints),
        paired_training_checks=load(root / "paired-training-checks.json"),
        exact_visible_metric_reproduction=all(x["exact"] for x in result["checks"]),
        fixed_roundoff_visible_metric_reproduction=all(
            x["fixed_roundoff_match"] for x in result["checks"]
        ),
        analysis_code_sha256=digest(Path(__file__)),
    )
    result["nonexact_visible_metric_count"] = sum(
        not x["exact"] for x in result["checks"]
    )
    result["max_visible_metric_absolute_difference"] = max(
        (x["absolute_difference"] for x in result["checks"]), default=0.0
    )
    result["selected_full_state_diagnostics"] = [
        {
            "model_id": key[0],
            "kind": key[1],
            "update_seed": key[2],
            "saved_update_step": int(step),
            "phase": str(phase),
            "nonzero_full_state_values": int(np.count_nonzero(state)),
        }
        for key, trace in traces.items()
        for step, phase, state in zip(
            trace["full_state_update_step"],
            trace["full_state_phase"],
            trace["full_state"],
            strict=True,
        )
    ]
    result["native_design_counts_match_recomputed"] = (
        summary["design_target_tests"]["executed"] == counts["design_executed"]
        and summary["design_target_tests"]["passed"] == counts["design_passed"]
    )
    result["native_negative_counts_match_recomputed"] = (
        summary["all_erased_negative_controls"]["executed"]
        == counts["negative_executed"]
        and summary["all_erased_negative_controls"]["absorbing_state_checks_passed"]
        == counts["negative_passed"]
    )
    dump(out / "audit.json", result)
    plot(root, out, summary, inputs)
    render(root, out, summary, traces, goal, cfg)
    report(root, out, summary, result, receipt, inputs)
    return result


def report(root, out, summary, result, receipt, inputs):
    target = np.load(inputs / "target.npz")
    xy = target["seed_xy"].tolist()
    inside = bool(target["silhouette"][xy[1], xy[0]])
    rows = []
    for model in summary["models"]:
        runs = [
            x
            for x in summary["evaluations"]
            if x["model_id"] == model["id"]
            and x["kind"] != "all-erased-negative"
            and not x["status"].startswith("not-started")
        ]
        rows.append(
            f"| {model['id']} | {model['training_steps']} | {model['status']} | {sum(x['criterion_passed'] for x in runs)}/{len(runs)} executed |"
        )
    cpu = load(root / "cpu-controls.json")
    cuda = load(root / "cuda-controls.json")
    text = (
        f"""# Actual inverse-pattern NCA experiment

**Execution: {summary["status"]}. Design tests: {result["counts"]["design_passed"]}/{48} declared passed, {result["counts"]["design_executed"]} executed.** Completing training is separate from achieving the target. Empty-state negative controls: {result["counts"]["negative_passed"]}/{4} declared passed.

| Frozen candidate | Actual training steps | Status | Design predicates |
| --- | --- | --- | --- |
"""
        + "\n".join(rows)
        + f"""

Of the executed design tests, {result["zero_visible_final_design_count"]} end with exactly zero raw RGBA. An empty field fails the target predicate. Under this rule, the activity mask makes the empty full state absorbing. Current seed_xy is {xy}; membership in target silhouette: {inside}. The original projected root[8,42] lies outside the silhouette, one pixel from foreground. The additive experiment tests seed placement as a possible mechanism without replacing that original failure or presuming a repair.

The goal is a fixed 64×64 design raster of the existing biological-v3a pectoral fin/rays (653 foreground pixels), with synthetic colors. It is **not an observed tissue or cellular image**. The computational seed_xy is {xy}. Computational updates/pixels have no biological time/cell-size calibration.

## Implemented rule and inverse objective

The shared 16-channel rule computes identity and two Sobel perceptions, a 48→128 ReLU→16 residual, then stochastic per-cell updates (fire probability0.5). Pre/post alpha-neighborhood masks restrict activity. Learned perception is3×3; composing the activity masks makes total one-step dependency5×5. The 12 hidden channels have no measured biochemical identity. There are8336 learned parameters.

Adam minimizes raw RGBA mean-square error to the design goal. Both regimes use the same pool128, batch8, unroll64–95, final2000-step budget and paired initialization/update schedules. Damage training additionally erases random circles. Final checkpoints are pinned before held-out masks load; no best-model or held-out selection occurs. This adapts [Distill2020, Model and Experiments2/3](https://distill.pub/2020/growing-ca/) and its [official notebook](https://github.com/google-research/self-organising-systems/blob/master/notebooks/growing_ca.ipynb); pool/budget/target/framework differ, so this is not an exact benchmark reproduction.

Evaluation uses three update seeds (reused from the parent: {result["evaluation_reused_from_parent"]}; reused cases are not fresh untouched heldouts), persistence to1024 updates, and three fixed erasure masks after256 growth updates plus512 recovery updates. Match requires silhouette IoU≥0.75 and raw RGBA MSE≤0.02. Persistence requires every saved checkpoint256–1024; recovery requires a valid pre-damage pattern AND final recovery. All-erased controls test an absorbing zero state and are excluded from the48 design tests. Repeated probes share learned weights and source assumptions; counts are descriptive, not biological probabilities or independent biological replicates.

## Numerical and provenance checks

Same-job CPU controls passed: {cpu["passed"]}; CPU/CUDA controls passed: {cuda["passed"]}. The numerical tolerances were frozen before training and remain unchanged. {result["nonexact_visible_metric_count"]} final metric comparisons differ bit-for-bit; maximum absolute difference {result["max_visible_metric_absolute_difference"]:.17g}. Exact reproduction remains false where recorded; the separately frozen roundoff comparison is not substituted for it. Returned-byte audit checked {result["files_checked"]} files/{result["bytes_checked"]}bytes; final visible-state metrics exact reproduction: {result["exact_visible_metric_reproduction"]}; separately named fixed-roundoff diagnostic: {result["fixed_roundoff_visible_metric_reproduction"]}. Predicate counts are recomputed from raw final RGBA plus saved per-checkpoint metrics. Hidden-state all-zero assertions rely on saved whole-state summary metrics except where full-state snapshots were preselected; this audit does not independently rerun training or every hidden-state trajectory.

Actual device: {receipt["device"]}. Environment: {json.dumps(receipt["environment"], sort_keys=True)}. Native science wall time: {receipt["wall_seconds"]:.3f}s. Dollar cost unknown/null. Final checkpoint barrier SHA256: {summary["checkpoint_barrier_sha256"]}. Protocol SHA256: {receipt["protocol_sha256"]}. Source hashes, final/periodic checkpoints, optimizer/RNG state, all52 evaluation records where executed, raw final RGBA, and eight preselected histories are retained. The training pool is not serialized: checkpoints do not promise exact training resume.

The video uses only actual selected central-square/update-seed7001 states; saved update256 before/after erasure are distinct phases. It does not interpolate physics or invent intermediate patterns. RGBA is clipped only for display; every loss/IoU uses raw state values. Simulation/training and render provenance remain separate.

## Applicability and next question

Pattern growth/recovery, if achieved, would establish only this computational local-rule design objective. It would not implement DNA, measured cell signaling, tissue material, fish neural control or organism feasibility. All failed target predicates, empty/collapsed patterns, incomplete arms and numerical failures stay visible. A further optimization repair would require a separately frozen experiment; this report does not alter the target, initial seed, loss, evaluation masks, thresholds or original results.
"""
    )
    (out / "RESULTS.md").write_text(text)


def plot(root, out, summary, inputs):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(12.8, 4.8), layout="constrained")
    for index, model in enumerate(summary["models"]):
        if "history_path" in model:
            history = load(artifact_path(root, model["history_path"]))
            axes[0].plot(
                [x["training_step"] for x in history],
                [x["batch_output_loss_before_parameter_update"] for x in history],
                label=model["id"],
                linewidth=1.4,
            )
        runs = [
            x
            for x in summary["evaluations"]
            if x["model_id"] == model["id"]
            and x["kind"] != "all-erased-negative"
            and "final" in x
        ]
        for axis, key in [(axes[1], "silhouette_IoU"), (axes[2], "rgba_MSE")]:
            values = [x["final"][key] for x in runs if key in x["final"]]
            axis.scatter([index] * len(values), values, alpha=0.65, label=model["id"])
    baseline = float(
        np.mean(np.load(inputs / "target.npz")["rgba"].astype(np.float64) ** 2)
    )
    axes[0].axhline(
        baseline, color="black", linestyle="--", label="Empty-field baseline"
    )
    axes[0].set(
        xlabel="Actual training step",
        ylabel="Raw batch RGBA MSE",
        title="All frozen training arms",
    )
    axes[0].legend(fontsize=6)
    for axis in axes[1:]:
        axis.set_xticks(
            range(4),
            ["seed1\nundamaged", "seed1\ndamage", "seed2\nundamaged", "seed2\ndamage"],
            fontsize=8,
        )
        axis.set_xlabel("Returned model (repeated probes share weights)")
    axes[1].axhline(0.75, color="black", linestyle="--")
    axes[1].set(ylabel="Final silhouette IoU", title="Frozen IoU criterion >=0.75")
    axes[2].axhline(0.02, color="black", linestyle="--")
    axes[2].set(ylabel="Final raw RGBA MSE", title="Frozen MSE criterion <=0.02")
    fig.suptitle(
        "Computational fin design goal; no measured tissue or biological probability",
        fontsize=12,
    )
    fig.savefig(out / "training-and-holdout.png", dpi=120)
    plt.close(fig)


def render(root, out, summary, traces, goal, cfg):
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    models = [
        f"{regime}-s{seed}"
        for seed in cfg["training"]["model_seeds"]
        for regime in cfg["training"]["regimes"]
    ]
    selected = [traces.get((model, "central-square", 7001)) for model in models]
    count = max((len(x["rgba"]) for x in selected if x is not None), default=0)
    if not count:
        return
    provenance = {
        "schema": "frontier.nca.render/1",
        "summary_sha256": digest(root / "summary.json"),
        "analysis_code_sha256": digest(Path(__file__)),
        "source_trajectories": [
            x["trajectory"]
            for x in summary["evaluations"]
            if x.get("trajectory", {}).get("full_history_selected_before_training")
        ],
        "frames": [],
        "scope": "Actual preselected central-square/update-seed7001 RGBA states; no physical/biological time. Clip [0,1] only for display; no interpolation. Missing histories explicitly labeled.",
    }
    argv = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        "1280x720",
        "-r",
        "5",
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(out / "damage-trajectories.mp4"),
    ]
    process = subprocess.Popen(argv, stdin=subprocess.PIPE)
    try:
        for frame in range(count):
            canvas = Image.new("RGB", (1280, 720), "#081c2c")
            draw = ImageDraw.Draw(canvas)
            draw.text(
                (24, 12),
                "Learned local rule | frozen fin design goal | all four models retained",
                font=font,
                fill="white",
            )
            draw.text(
                (24, 41),
                "Computational patterns: hidden channels are not measured biochemical signals",
                font=small,
                fill="#b9c7d3",
            )
            canvas.paste(image_rgba(goal, 256), (32, 100))
            draw.text(
                (32, 73),
                "DESIGN GOAL (not observed tissue)",
                font=small,
                fill="#8ed0e0",
            )
            mapping = []
            for i, (model, trace) in enumerate(zip(models, selected, strict=True)):
                x, y = 336 + (i % 2) * 458, 89 + (i // 2) * 291
                draw.text((x, y - 20), model, font=small, fill="white")
                if trace is None:
                    draw.text(
                        (x, y + 30),
                        "No returned selected trajectory",
                        font=small,
                        fill="#ffb199",
                    )
                    continue
                index = min(frame, len(trace["rgba"]) - 1)
                step = int(trace["frame_update_step"][index])
                phase = str(trace["frame_phase"][index])
                canvas.paste(image_rgba(trace["rgba"][index], 236), (x, y))
                draw.text(
                    (x + 244, y + 20),
                    f"Update {step}\n{phase}"
                    + ("\nterminal hold" if frame >= len(trace["rgba"]) else ""),
                    font=small,
                    fill="#b9c7d3",
                )
                mapping.append(
                    {
                        "model_id": model,
                        "saved_frame_index": index,
                        "update_step": step,
                        "phase": phase,
                    }
                )
            draw.text(
                (24, 674),
                f"Design tests passed {summary['design_target_tests']['passed']}/{summary['design_target_tests']['declared_expected']} declared | biological validity unknown",
                font=font,
                fill="white",
            )
            provenance["frames"].append(
                {"movie_frame": frame, "actual_states": mapping}
            )
            process.stdin.write(canvas.tobytes())
            if frame == count - 1:
                canvas.save(out / "poster.png")
    finally:
        process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    provenance["outputs"] = [
        {
            "path": name,
            "sha256": digest(out / name),
            "bytes": (out / name).stat().st_size,
        }
        for name in (
            "poster.png",
            "damage-trajectories.mp4",
            "training-and-holdout.png",
        )
    ]
    dump(out / "render-provenance.json", provenance)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--input-artifacts", type=Path, default=ART)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    print(
        {
            k: v
            for k, v in audit(args.root, args.out, args.input_artifacts).items()
            if k != "checks"
        }
    )
