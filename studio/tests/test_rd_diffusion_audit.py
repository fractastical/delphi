"""Tests for the post-run tools (exact W1, fail-closed audit, strict JSON). Fixtures are CODE-BUILT SOFTWARE FIXTURES, not results of any model or solver."""
import json, sys
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



def test_publication_adapter_missing_files_fail_closed(tmp_path):
    result = AU.audit(tmp_path)
    assert not result["complete"]
    assert result["problems"] == result["failures"]
    assert any("missing file" in problem for problem in result["problems"])


def test_nonfinite_json_is_located_not_silently_accepted(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"nested": [Infinity, NaN, 1e999]}')
    marked, paths = AU.load_strict(path)
    assert paths == ["/nested[0]", "/nested[1]", "/nested[2]"]
    assert all(value["status"] == "nonfinite" for value in marked["nested"])
    json.dumps(marked, allow_nan=False)


def test_secondary_json_is_strict(tmp_path):
    import secondary_eval as SE
    out = SE.strict({"a": float("nan"), "b": [float("inf"), 1.0], "c": np.float32(2.0)}); assert out["a"]["status"] == "nonfinite" and out["b"][0]["status"] == "nonfinite" and out["b"][1] == 1.0
    json.dumps(out, allow_nan=False, default=lambda o: o.item())
