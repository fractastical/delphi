"""Synthetic structural fixtures only; no simulated scientific results."""

import hashlib
import json

import pytest

from frontier_compute.diffusion_audit import CODE_SHA, CONFIG_SHA, METHODS, METRICS, TAUS, audit, finite_json


@pytest.fixture
def output(tmp_path):
    checkpoint = b"fixture, not model weights"
    (tmp_path / "control.json").write_text(json.dumps({"ok": True, "env": {"cuda_available": True}}))
    (tmp_path / "checkpoint.pt").write_bytes(checkpoint)
    (tmp_path / "examples.npz").write_bytes(b"fixture, not field data")
    (tmp_path / "train_loss.jsonl").write_text("\n".join(json.dumps({"step": i}) for i in [1, *range(100, 30001, 100)]))
    report = {
        "smoke": False, "env": {"device": "cuda"},
        "timings": {"batch": 1024, "ddpm_sampling_seconds": [1, 1, 1]},
        "dataset": {"code_sha256": CODE_SHA, "config_sha256": CONFIG_SHA,
                    "train": {"runs": 4200, "failed_runs": 0, "rows": 16800, "n_settings": 1400}},
        "train": {"steps": 30000, "frozen_before_holdout_generation": True,
                  "checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest()},
        "ensemble_eval": {"n_conditions": 160, "ensemble_failed_runs": 0,
                          "per_condition": [{"setting_id": sid, "tau": tau, "n_solver": 32,
                                             **{m: dict.fromkeys(METRICS, 0) for m in METHODS}}
                                            for sid in range(1450, 1490) for tau in TAUS]},
        "held_out_marginals": {name: {"n_runs": n, "n_rows": 4*n, "failed_runs": 0,
                                     "by_tau": {str(t): {"n": n, "gen_nonfinite_frac": 0} for t in TAUS}}
                               for name, n in (("test_param", 600), ("test_seed", 300))},
    }
    keys = ["conditional_mean_of_nearest10" if m == "nearest10_pooled" else m for m in METHODS]
    report["ensemble_eval"]["summary_median_over_conditions"] = {
        key: dict.fromkeys(METRICS - {"mode_agree_argmax"}, 0) for key in keys
    }
    report["ensemble_eval"]["paired_counts_ddpm_vs_baseline"] = {
        key: {metric: {"ddpm_lower": 0, "tie": 160, "ddpm_higher": 0, "n": 160}
              for metric in ("mode_tv", "amp_w1_rel")} for key in keys[1:]
    }
    (tmp_path / "evaluation.json").write_text(json.dumps(report))
    return tmp_path, report


def test_complete_fixture_and_declared_training_exclusion(output):
    path, report = output
    assert audit(path)["complete"]
    report["dataset"]["train"].update(failed_runs=1, rows=16796)
    (path / "evaluation.json").write_text(json.dumps(report))
    assert audit(path)["complete"]


def test_missing_holdout_cannot_be_success(output):
    path, report = output
    report["ensemble_eval"]["per_condition"][0] = {"setting_id": 1450, "tau": 50, "skipped": "failed"}
    (path / "evaluation.json").write_text(json.dumps(report))
    assert not audit(path)["complete"]


def test_changed_checkpoint_is_rejected(output):
    path, _ = output
    (path / "checkpoint.pt").write_bytes(b"changed")
    assert "checkpoint hash mismatch or missing" in audit(path)["failures"]


@pytest.mark.parametrize("text", ['{"x": NaN}', '{"x": Infinity}', '{"x": 1e999}'])
def test_nonfinite_json_is_rejected(text):
    with pytest.raises(ValueError, match="Nonfinite"):
        finite_json(text)


def test_duplicate_condition_rejects_count_only_match(output):
    path, report = output
    rows = report["ensemble_eval"]["per_condition"]
    rows[-1] = rows[0]
    (path / "evaluation.json").write_text(json.dumps(report))
    assert not audit(path)["complete"]


def test_nonfinite_samples_reported_by_finite_fraction_fail(output):
    path, report = output
    report["ensemble_eval"]["per_condition"][0]["ddpm"]["nonfinite_frac"] = 1/32
    (path / "evaluation.json").write_text(json.dumps(report))
    assert not audit(path)["complete"]


def test_summary_cannot_drop_losing_conditions(output):
    path, report = output
    report["ensemble_eval"]["paired_counts_ddpm_vs_baseline"]["nearest1_pooled"]["mode_tv"]["n"] = 159
    (path / "evaluation.json").write_text(json.dumps(report))
    assert not audit(path)["complete"]


@pytest.mark.parametrize("token", ["NaN", "Infinity", "1e999"])
def test_located_nonfinite_can_never_be_complete(output, token):
    from engineering.rd_diffusion.audit_result import audit as publication_audit

    path, _ = output
    original = (path / "evaluation.json").read_text()
    (path / "evaluation.json").write_text(original.replace('"amp_w1_rel": 0', '"amp_w1_rel": ' + token, 1))
    for result in (audit(path), publication_audit(path)):
        assert not result["complete"]
        assert result["nonfinite_paths"][0].endswith("/amp_w1_rel")


def test_publication_adapter_preserves_complete_core_result(output):
    from engineering.rd_diffusion.audit_result import audit as publication_audit

    path, _ = output
    result = publication_audit(path)
    assert result["complete"]
    assert result["problems"] == result["failures"] == []


def test_separate_control_part_is_required_and_supported(output):
    path, _ = output
    control = path / "separate-control.json"
    (path / "control.json").rename(control)
    assert not audit(path)["complete"]
    assert audit(path, control)["complete"]
    control.write_text('{"ok": false, "env": {"cuda_available": true}}')
    assert not audit(path, control)["complete"]


@pytest.mark.parametrize("change", ["batch", "repeats", "duration", "loss_steps"])
def test_timing_and_actual_training_steps_are_checked(output, change):
    path, report = output
    if change == "batch":
        report["timings"]["batch"] = 64
    elif change == "repeats":
        report["timings"]["ddpm_sampling_seconds"].pop()
    elif change == "duration":
        report["timings"]["ddpm_sampling_seconds"][0] = 0
    else:
        (path / "train_loss.jsonl").write_text("\n".join(json.dumps({"step": i}) for i in range(301)))
    (path / "evaluation.json").write_text(json.dumps(report))
    assert not audit(path)["complete"]
