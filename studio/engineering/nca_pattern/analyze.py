"""Audit and display returned NCA states without selecting a successful model."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .model import ART, ROOT, dump, protocol


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


def audit(root, out):
    receipt = load(root / "job-receipt.json")
    for item in receipt["files"]:
        path = root / item["path"]
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Receipt path escapes output")
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise ValueError("Returned file digest/size mismatch")
    if receipt["protocol_sha256"] != digest(ART / "protocol.json"):
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
    for checkpoint in barrier["completed_checkpoints"]:
        if digest(artifact_path(root, checkpoint["path"])) != checkpoint["sha256"]:
            raise ValueError("Checkpoint bytes changed")
    target = np.load(ART / "target.npz")
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
            counts[name + "_executed"] += 1
            counts[name + "_passed"] += int(passed)
            if bool(data["recorded_trace"]):
                traces[identity] = {k: data[k].copy() for k in data.files}
    result.update(
        counts=counts,
        evaluation_identities=len(identities),
        checkpoint_count=len(checkpoints),
        paired_training_checks=load(root / "paired-training-checks.json"),
        exact_visible_metric_reproduction=all(x["exact"] for x in result["checks"]),
        fixed_roundoff_visible_metric_reproduction=all(
            x["fixed_roundoff_match"] for x in result["checks"]
        ),
        analysis_code_sha256=digest(Path(__file__)),
    )
    dump(out / "audit.json", result)
    render(root, out, summary, traces, goal)
    return result


def render(root, out, summary, traces, goal):
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    models = [
        f"{regime}-s{seed}"
        for seed in protocol()["training"]["model_seeds"]
        for regime in protocol()["training"]["regimes"]
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
        for name in ("poster.png", "damage-trajectories.mp4")
    ]
    dump(out / "render-provenance.json", provenance)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    print({k: v for k, v in audit(args.root, args.out).items() if k != "checks"})
