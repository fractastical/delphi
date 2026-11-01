"""Tests for the post-run tools (exact W1, fail-closed audit, strict JSON). Fixtures are CODE-BUILT SOFTWARE FIXTURES, not results of any model or solver."""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from engineering.rd_diffusion import audit_result as AU
from engineering.rd_diffusion.exact_w1 import exact_w1

ROOT = Path(__file__).resolve().parents[1]


def test_exact_w1_hand_worked():
    assert (
        exact_w1([0.0], [1.0, 1.0]) == pytest.approx(1.0)
        and exact_w1([0, 1], [0, 0, 1, 1]) == pytest.approx(0.0)
        and exact_w1([2, 4], [2, 4]) == 0
    )
    assert exact_w1([1, 2, 3], [11, 12, 13]) == pytest.approx(
        10.0
    )  # a pure shift by 10
    a, b = np.array([0.3, 1.1, 2.0, 5.0]), np.array([0.5, 0.9, 2.5, 4.0])
    assert exact_w1(a, b) == pytest.approx(
        np.abs(np.sort(a) - np.sort(b)).mean()
    )  # equal sizes: mean sorted difference
    assert exact_w1([1] * 32, [0] * 31 + [32]) == pytest.approx(
        62 / 32
    )  # reviewer counterexample: exactly 1.9375
    with pytest.raises(ValueError):
        exact_w1([1.0], [float("nan")])


def test_the_frozen_w1_is_an_approximation_that_differs_on_the_review_counterexample():
    from engineering.rd_diffusion import rd_ddpm as R

    n = 64
    sign = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)

    def field(amp):
        return np.stack([amp * sign, np.ones(n)])  # std of u over x equals amp

    sol = np.stack([field(1.0)] * 32)
    gen = np.stack([field(0.0)] * 31 + [field(32.0)])
    frozen = R.ens_metrics(gen, sol, R.dct_matrix(n))["amp_w1_rel"]
    assert (
        frozen == pytest.approx(1.453125)
        and exact_w1(gen[:, 0].std(-1), sol[:, 0].std(-1)) == pytest.approx(1.9375)
        and frozen < 1.9375
    )


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
    from engineering.rd_diffusion import secondary_eval as SE

    out = SE.strict({"a": float("nan"), "b": [float("inf"), 1.0], "c": np.float32(2.0)})
    assert (
        out["a"]["status"] == "nonfinite"
        and out["b"][0]["status"] == "nonfinite"
        and out["b"][1] == 1.0
    )
    json.dumps(out, allow_nan=False, default=lambda o: o.item())


def test_secondary_stratification_uses_the_registered_amplitude_gate():
    from engineering.rd_diffusion import secondary_eval as SE

    def row(m):
        return {
            k: {"mode_tv": m, "amp_w1_rel": m, "amp_w1_exact_rel": m}
            for k in SE.METHODS
        }

    n = 16
    u_hi = np.cos(np.pi * (np.arange(n) + 0.5) / n)  # std ~0.707
    fields = np.zeros((3, 2, 1, 2, n))  # 3 conditions, 2 solver runs, 1 tau
    fields[0, :, 0, 0] = u_hi
    fields[1, :, 0, 0] = 1e-6 * u_hi  # below the 1e-3 gate
    fields[2, :, 0, 0] = u_hi  # failed: excluded
    failed = np.array([[False, False], [False, False], [True, True]])
    out = SE.stratify([row(0.1), row(0.9), row(0.5)], fields, failed, 1)
    assert (
        out["gate_std_u"] == 1e-3
        and out["patterned"]["n_conditions"] == 1
        and out["near_uniform"]["n_conditions"] == 1
    )
    assert out["patterned"]["ddpm"]["mode_tv"] == pytest.approx(0.1) and out[
        "near_uniform"
    ]["ddpm"]["mode_tv"] == pytest.approx(0.9)
    empty = SE.stratify([row(0.1)], fields[:1] * 0 + 1, np.array([[True, True]]), 1)
    assert (
        empty["patterned"]["n_conditions"] == 0
        and empty["patterned"]["ddpm"]["mode_tv"] is None
    )


def test_secondary_policy_matches_infras_recorded_explicit_fp32_policy_and_refuses_default(
    tmp_path,
):
    from engineering.rd_diffusion import secondary_eval as SE

    assert SE.POLICY == {
        "NVIDIA_TF32_OVERRIDE": "0",
        "TORCH_ALLOW_TF32_CUBLAS_OVERRIDE": "0",
        "torch.backends.cuda.matmul.allow_tf32": False,
        "torch.backends.cudnn.allow_tf32": False,
        "torch.set_float32_matmul_precision": "highest",
    }
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "engineering/rd_diffusion/secondary_eval.py"),
            "--ckpt",
            "x",
            "--out",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "NVIDIA_TF32_OVERRIDE": "1"},
    )
    assert r.returncode != 0 and "numerical policy mismatch" in (
        r.stderr + r.stdout
    )  # default/other policy: refused, not merely recorded


def test_launcher_sets_the_policy_before_torch_and_refuses_if_torch_is_already_loaded():
    code = (
        "import sys; sys.argv=['x']; sys.path.insert(0, %r); import launch_secondary as L; import torch; L.main(['x','control'])"
        % str(ROOT / "engineering/rd_diffusion")
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode != 0 and "imported before" in (r.stderr + r.stdout)
    probe = (
        "import os, sys; sys.path.insert(0, %r); import launch_secondary as L; os.environ.update(L.ENV); import torch; torch.backends.cudnn.allow_tf32=False; print(os.environ['NVIDIA_TF32_OVERRIDE'], L.ENV)"
        % str(ROOT / "engineering/rd_diffusion")
    )
    assert (
        "0"
        in subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, text=True
        ).stdout
    )


def test_recovery_normalization_gate_is_exact_and_difference_is_diagnostic_only():
    from engineering.rd_diffusion import recovery_eval as RE

    m, s = (
        np.array([[[1.0], [2.0]]], np.float32),
        np.array([[[3.0], [4.0]]], np.float32),
    )
    ok = RE.normalization_gate(m.copy(), s.copy(), m, s)
    assert ok["ok"] and ok["exactly_equal"] and ok["max_abs_difference_mean"] == 0.0
    off = RE.normalization_gate(
        m + np.float32(1e-7), s, m, s
    )  # a difference far below the old 1e-6 draft tolerance
    assert (
        not off["ok"]
        and not off["exactly_equal"]
        and off["max_relative_difference_DIAGNOSTIC_ONLY"] < 1e-6
    )
    assert not RE.normalization_gate(m, s[:, :1], m, s)[
        "ok"
    ]  # shape mismatch fails, no exception


def test_recovery_requires_the_exact_301_step_log_and_production_has_no_overrides(
    tmp_path,
):
    from engineering.rd_diffusion import recovery_eval as RE

    good = tmp_path / "g.jsonl"
    good.write_text("\n".join(json.dumps({"step": k}) for k in RE.PRODUCTION_STEPS))
    assert (
        RE.check_log_steps(good) == RE.PRODUCTION_STEPS
        and len(RE.PRODUCTION_STEPS) == 301
    )
    for name, steps in (
        ("short", RE.PRODUCTION_STEPS[:-1]),
        ("dup", RE.PRODUCTION_STEPS + [30000]),
        ("gap", [s for s in RE.PRODUCTION_STEPS if s != 15000]),
        ("order", RE.PRODUCTION_STEPS[::-1]),
    ):
        p = tmp_path / f"{name}.jsonl"
        p.write_text("\n".join(json.dumps({"step": k}) for k in steps))
        with pytest.raises(SystemExit):
            RE.check_log_steps(p)
    base = [
        sys.executable,
        str(ROOT / "engineering/rd_diffusion/recovery_eval.py"),
        "--ckpt",
        "x",
        "--train-log",
        "y",
        "--out",
        str(tmp_path / "o"),
    ]
    for flag in (["--expect-sha", "0" * 64], ["--allow-policy-mismatch"]):
        r = subprocess.run(base + flag, capture_output=True, text=True)
        assert r.returncode != 0 and "smoke-only" in (r.stderr + r.stdout)
    assert (
        RE.CHECKPOINT_SHA256
        == "1a0a185cdacd49e8a65aa77ece1cd8f51033533c996025b3f4da907cd2b2ae76"
        and RE.TRAIN_LOG_SHA256
        == "2ecdd2ceb6eec513a634ec7edcaf5e37cc15cba3d3717c90c5ad7ab41dc05862"
    )
    assert RE.POLICY == {
        "NVIDIA_TF32_OVERRIDE": "0",
        "TORCH_ALLOW_TF32_CUBLAS_OVERRIDE": "0",
        "torch.backends.cuda.matmul.allow_tf32": False,
        "torch.backends.cudnn.allow_tf32": False,
        "torch.set_float32_matmul_precision": "highest",
    }


def test_recovery_stage_logger_writes_begin_end_and_fail_durably(tmp_path):
    from engineering.rd_diffusion import recovery_eval as RE

    st = RE.Stages(str(tmp_path))
    assert st.run("a", lambda: 5) == 5
    with pytest.raises(ZeroDivisionError):
        st.run("b", lambda: 1 / 0)
    ev = [
        (r["stage"], r["event"])
        for r in map(
            json.loads, (tmp_path / "stage_log.jsonl").read_text().splitlines()
        )
    ]
    assert ev == [("a", "BEGIN"), ("a", "END"), ("b", "BEGIN"), ("b", "FAIL")]
