"""Independent completeness audit of the frozen RD pilot; never edit raw outputs.

This checks the preregistered run's evidence, not surrogate quality or biology.
Training failures may be excluded with recorded counts. Missing holdouts fail.
Checkpoint bytes are hashed without loading pickle content.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics


CONFIG_SHA = "bc77ebc55010b9c8ac910c2b31868ec0dbf2d1e3785a06ec3ef1aa028ea2b210"
CODE_SHA = "25455430ef138b49e6bac151a144e338269a81ce5c2f576387f8805bbb1a400a"
TAUS = (50, 100, 150, 200)
METHODS = ("ddpm", "ddpm_shuffled_condition", "nearest1_pooled", "nearest5_pooled", "nearest10_pooled")
METRICS = {"mode_tv", "mode_agree_argmax", "amp_w1_rel", "amp_mean_rel_err", "nonfinite_frac", "negative_frac"}


class NonFinite(dict):
    """Display-only marker; its presence always fails the collection audit."""


def marked_json(text):
    value = json.loads(text, parse_constant=lambda token: NonFinite(status="nonfinite", token=token))
    paths = []

    def walk(item, path):
        if isinstance(item, NonFinite):
            paths.append(path)
            return item
        if isinstance(item, float) and not math.isfinite(item):
            paths.append(path)
            return NonFinite(status="nonfinite", token=str(item))
        if isinstance(item, dict):
            return {key: walk(child, f"{path}/{key}") for key, child in item.items()}
        if isinstance(item, list):
            return [walk(child, f"{path}[{index}]") for index, child in enumerate(item)]
        return item

    return walk(value, ""), paths


def load_strict(path):
    """Locate invalid constants and overflowing numeric literals without dropping them."""
    return marked_json(Path(path).read_text())


def finite_json(text):
    value, paths = marked_json(text)
    if paths:
        raise ValueError("Nonfinite JSON number at " + ", ".join(paths))
    return value


def audit(output, control_path=None):
    """Fail closed, including malformed files; optionally use the separate control part."""
    output = Path(output)
    failures = []
    nonfinite_paths = []
    control = Path(control_path) if control_path is not None else output / "control.json"
    required = [control, *(output / name for name in (
        "evaluation.json", "checkpoint.pt", "examples.npz", "train_loss.jsonl"))]
    for path in required:
        if not path.is_file():
            failures.append("missing file " + str(path))
    if not failures:
        try:
            report, paths = load_strict(output / "evaluation.json")
            ctl, control_paths = load_strict(control)
            nonfinite_paths = ["evaluation.json" + p for p in paths] + ["control.json" + p for p in control_paths]
            if nonfinite_paths:
                failures.append("Nonfinite JSON values: " + ", ".join(nonfinite_paths))
            else:
                return _audit_finite(output, report, ctl)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            failures.append(str(error))
    return {"schema": "frontier.rd-ddpm.collection-audit/1", "complete": False,
            "failures": failures, "nonfinite_paths": nonfinite_paths}


def _audit_finite(output, report, control):
    output = Path(output)
    failures = []

    def check(condition, label):
        if not condition:
            failures.append(label)

    check(report.get("smoke") is False, "smoke run is not a trained result")
    check(report.get("env", {}).get("device") == "cuda", "CUDA training receipt missing")
    check(control.get("ok") is True and control.get("env", {}).get("cuda_available") is True,
          "control gate not ok on CUDA")
    data = report.get("dataset", {})
    check(data.get("config_sha256") == CONFIG_SHA, "config hash differs from frozen protocol")
    check(data.get("code_sha256") == CODE_SHA, "code hash differs from frozen protocol")
    train_data = data.get("train", {})
    failed = train_data.get("failed_runs", -1)
    check(train_data.get("runs") == 4200 and isinstance(failed, int) and 0 <= failed < 4200,
          "training run/exclusion count invalid")
    check(train_data.get("rows") == 4 * (4200 - failed), "training row count disagrees with exclusions")
    check(0 < train_data.get("n_settings", 0) <= 1400, "training setting count invalid")
    training = report.get("train", {})
    check(training.get("steps") == 30000, "training did not complete 30000 steps")
    check(training.get("frozen_before_holdout_generation") is True, "checkpoint ordering receipt missing")
    checkpoint = output / "checkpoint.pt"
    check(checkpoint.is_file() and hashlib.sha256(checkpoint.read_bytes()).hexdigest() == training.get("checkpoint_sha256"),
          "checkpoint hash mismatch or missing")
    logs = [finite_json(line) for line in (output / "train_loss.jsonl").read_text().splitlines() if line.strip()]
    check([r.get("step") for r in logs] == [1, *range(100, 30001, 100)], "training log steps incomplete or duplicated")
    ensemble = report.get("ensemble_eval", {})
    rows = ensemble.get("per_condition", [])
    expected = {(sid, tau) for sid in range(1450, 1490) for tau in TAUS}
    check(len(rows) == 160 and {(r.get("setting_id"), r.get("tau")) for r in rows} == expected,
          "ensemble condition coverage incomplete or duplicated")
    check(ensemble.get("n_conditions") == 160 and ensemble.get("ensemble_failed_runs") == 0,
          "ensemble holdouts missing or failed")
    for row in rows:
        label = f"condition {row.get('setting_id')}/{row.get('tau')}"
        check("skipped" not in row and row.get("n_solver") == 32, label + " has missing solver samples")
        check(all(isinstance(row.get(method), dict) for method in METHODS), label + " lacks a baseline or null")
        check(all(METRICS <= set(row.get(method, {})) for method in METHODS), label + " lacks required metrics")
        check(all(row.get(method, {}).get("nonfinite_frac") == 0 for method in METHODS),
              label + " includes nonfinite generated samples")
    if len(rows) == 160 and all(all(METRICS <= set(row.get(method, {})) for method in METHODS) for row in rows):
        summaries = ensemble.get("summary_median_over_conditions", {})
        paired = ensemble.get("paired_counts_ddpm_vs_baseline", {})
        for method in METHODS:
            key = "conditional_mean_of_nearest10" if method == "nearest10_pooled" else method
            summary = summaries.get(key, {})
            for metric in METRICS - {"mode_agree_argmax"}:
                expected_median = statistics.median(row[method][metric] for row in rows)
                check(summary.get(metric) == expected_median, key + "/" + metric + " summary disagrees with rows")
            for metric in ("mode_tv", "amp_w1_rel") if method != "ddpm" else ():
                counts = paired.get(key, {}).get(metric, {})
                check(counts == {
                    "ddpm_lower": sum(row["ddpm"][metric] < row[method][metric] for row in rows),
                    "tie": sum(row["ddpm"][metric] == row[method][metric] for row in rows),
                    "ddpm_higher": sum(row["ddpm"][metric] > row[method][metric] for row in rows), "n": 160,
                }, key + "/" + metric + " paired counts disagree with rows")
    for name, runs in (("test_param", 600), ("test_seed", 300)):
        marginal = report.get("held_out_marginals", {}).get(name, {})
        check(marginal.get("n_runs") == runs and marginal.get("n_rows") == 4 * runs and marginal.get("failed_runs") == 0,
              name + " has missing holdout runs/rows")
        by_tau = marginal.get("by_tau", {})
        check(set(by_tau) == {str(tau) for tau in TAUS} and all(r.get("n") == runs for r in by_tau.values()),
              name + " time coverage incomplete")
        check(all(r.get("gen_nonfinite_frac") == 0 for r in by_tau.values()),
              name + " includes nonfinite generated samples")
    check((output / "examples.npz").is_file(), "actual generated/solver example archive missing")
    timing = report.get("timings", {})
    durations = timing.get("ddpm_sampling_seconds", [])
    check(timing.get("batch") == 1024 and len(durations) == 3
          and all(isinstance(value, (int, float)) and value > 0 for value in durations),
          "timing protocol requires three positive durations at batch 1024")
    return {
        "schema": "frontier.rd-ddpm.collection-audit/1", "complete": not failures, "failures": failures,
        "nonfinite_paths": [],
        "evaluation_sha256": hashlib.sha256((output / "evaluation.json").read_bytes()).hexdigest(),
        "scope": "Frozen run completeness and artifact identity only; no performance or biological validity claim. Quantile W1 is an approximation.",
        "training_failed_runs": failed,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--control", type=Path, help="Control JSON from the separately returned control part")
    args = parser.parse_args()
    try:
        result = audit(args.output, args.control)
    except (OSError, ValueError, TypeError, KeyError) as error:
        result = {"complete": False, "failures": [str(error)]}
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(0 if result["complete"] else 1)
