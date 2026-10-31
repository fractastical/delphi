"""Tests for the post-run tools (exact W1, fail-closed audit, strict JSON). Fixtures are CODE-BUILT SOFTWARE FIXTURES, not results of any model or solver."""
import copy, hashlib, json, math, sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engineering" / "rd_diffusion"))
import audit_result as AU
from exact_w1 import exact_w1


def test_exact_w1_hand_worked():
    assert exact_w1([0.0], [1.0, 1.0]) == pytest.approx(1.0) and exact_w1([0, 1], [0, 0, 1, 1]) == pytest.approx(0.0) and exact_w1([2, 4], [2, 4]) == 0
    assert exact_w1([1, 2, 3], [11, 12, 13]) == pytest.approx(10.0)                                                  # a pure shift by 10
    a, b = np.array([0.3, 1.1, 2.0, 5.0]), np.array([0.5, 0.9, 2.5, 4.0]); assert exact_w1(a, b) == pytest.approx(np.abs(np.sort(a) - np.sort(b)).mean())   # equal sizes: mean sorted difference
    assert exact_w1([1] * 32, [0] * 31 + [32]) == pytest.approx(62 / 32)                                              # reviewer counterexample: exactly 1.9375
    with pytest.raises(ValueError): exact_w1([1.0], [float("nan")])


def test_the_frozen_w1_is_an_approximation_that_differs_on_the_review_counterexample():
    import rd_ddpm as R
    n = 64; sign = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
    field = lambda amp: np.stack([amp * sign, np.ones(n)])                                                           # std of u over x equals amp
    sol = np.stack([field(1.0)] * 32); gen = np.stack([field(0.0)] * 31 + [field(32.0)])
    frozen = R.ens_metrics(gen, sol, R.dct_matrix(n))["amp_w1_rel"]
    assert frozen == pytest.approx(1.453125) and exact_w1(gen[:, 0].std(-1), sol[:, 0].std(-1)) == pytest.approx(1.9375) and frozen < 1.9375


def _good(tmp):
    d = tmp; tmp.mkdir(exist_ok=True); (d / "checkpoint.pt").write_bytes(b"ckpt"); (d / "examples.npz").write_bytes(b"x")
    (d / "train_loss.jsonl").write_text("\n".join(json.dumps({"step": i}) for i in range(301)))
    taus = [50, 100, 150, 200]; m = {"mode_tv": 0.1, "amp_w1_rel": 0.1}
    per = [{"setting_id": 1450 + s, "tau": t, **{k: dict(m) for k in AU.METHODS}} for s in range(40) for t in taus]
    seg = lambda n_runs, n_rows, pt: {"n_runs": n_runs, "n_rows": n_rows, "failed_runs": 0, "by_tau": {str(t): {"n": pt} for t in taus}}
    ev = {"smoke": False, "env": {"device": "cuda"}, "dataset": {**AU.FROZEN, "train": {"runs": 4200, "rows": 16800, "failed_runs": 0}},
          "train": {"steps": 30000, "checkpoint_sha256": hashlib.sha256(b"ckpt").hexdigest(), "frozen_before_holdout_generation": True},
          "ensemble_eval": {"n_conditions": 160, "per_condition": per, "ensemble_failed_runs": 0},
          "held_out_marginals": {"test_param": seg(600, 2400, 600), "test_seed": seg(300, 1200, 300)}, "timings": {"batch": 1024, "ddpm_sampling_seconds": [1, 1, 1]}}
    (d / "evaluation.json").write_text(json.dumps(ev)); (d / "control.json").write_text(json.dumps({"ok": True, "env": {"cuda_available": True}})); return d, ev


def test_audit_accepts_a_complete_fixture_and_rejects_each_defect(tmp_path):
    d, ev = _good(tmp_path / "g"); r = AU.audit(d); assert r["complete"], r["problems"]
    def bad(mut, needle, name):
        dd, e = _good(tmp_path / name); mut(e); (dd / "evaluation.json").write_text(json.dumps(e)); r = AU.audit(dd)
        assert not r["complete"] and any(needle in p for p in r["problems"]), (name, r["problems"])
    bad(lambda e: e["ensemble_eval"]["per_condition"].pop(), "conditions", "missing_condition")
    bad(lambda e: e["ensemble_eval"]["per_condition"][0].update(skipped="x"), "skipped", "skipped")
    bad(lambda e: e["ensemble_eval"]["per_condition"][3].pop("nearest5_pooled"), "lack one of the five", "method_missing")
    bad(lambda e: e["ensemble_eval"].update(ensemble_failed_runs=2), "failed", "failed_runs")
    bad(lambda e: e["train"].update(steps=29000), "steps", "steps")
    bad(lambda e: e["train"].update(checkpoint_sha256="0" * 64), "checkpoint sha256", "ckpt_hash")
    bad(lambda e: e["dataset"].update(code_sha256="0" * 64), "code_sha256", "code_hash")
    bad(lambda e: e.update(smoke=True), "full CUDA", "smoke")
    bad(lambda e: e["held_out_marginals"]["test_seed"].update(n_rows=1100), "test_seed", "marginal_rows")
    bad(lambda e: e["timings"].update(batch=64), "timing", "timing")
    (d / "evaluation.json").unlink(); assert any("missing file" in p for p in AU.audit(d)["problems"])


def test_nonfinite_json_is_located_not_silently_accepted(tmp_path):
    d, ev = _good(tmp_path / "n"); txt = (d / "evaluation.json").read_text().replace('"amp_w1_rel": 0.1', '"amp_w1_rel": Infinity', 1); (d / "evaluation.json").write_text(txt)
    r = AU.audit(d); assert r["nonfinite_paths"] and r["nonfinite_paths"][0].endswith("amp_w1_rel") and "Infinity" in json.dumps(AU.load_strict(d / "evaluation.json")[0], default=str)


def test_secondary_json_is_strict(tmp_path):
    import secondary_eval as SE
    out = SE.strict({"a": float("nan"), "b": [float("inf"), 1.0], "c": np.float32(2.0)}); assert out["a"]["status"] == "nonfinite" and out["b"][0]["status"] == "nonfinite" and out["b"][1] == 1.0
    json.dumps(out, allow_nan=False, default=lambda o: o.item())
