"""Synthetic structural fixtures only; no simulated scientific results."""

import hashlib
import json

import pytest

from frontier_compute.diffusion_audit import CODE_SHA, CONFIG_SHA, METHODS, METRICS, TAUS, audit, finite_json


@pytest.fixture
def output(tmp_path):
    checkpoint = b"fixture, not model weights"
    (tmp_path / "checkpoint.pt").write_bytes(checkpoint)
    (tmp_path / "examples.npz").write_bytes(b"fixture, not field data")
    (tmp_path / "train_loss.jsonl").write_text("\n".join(json.dumps({"step": i}) for i in [1, *range(100, 30001, 100)]))
    report = {
        "smoke": False, "env": {"device": "cuda"},
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
