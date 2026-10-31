"""Small software checks; no training, held-out evaluation, or audit endpoints."""

import numpy as np

from engineering.rd_numerics.audit import common_grid, controls, solve


def test_analytic_cosine_projection_preserves_shared_continuous_modes():
    projected = []
    for n in (64, 128, 256):
        x = (np.arange(n) + 0.5) / n
        wave = 1.2 + 0.3 * np.cos(7 * np.pi * x) - 0.2 * np.cos(19 * np.pi * x)
        result, high = common_grid(wave)
        projected.append(result)
        assert high < 1e-24
    assert np.max(abs(projected[0] - projected[-1])) < 1e-12


def test_short_CPU_controls_and_diffusion_sign_mutation_execute():
    result = controls("cpu")
    assert result["passed"]
    assert result["wrong_sign_max_abs"] > 1
    assert result["CPU_CUDA_max_abs"] is None


def test_explicit_timestep_controls_actual_wrapper_dynamics():
    params = np.array([[0.1, 0.9, 20.0, 40.0]])
    a = solve(params, np.array([0]), 64, 0.02, [0.2], "cpu")
    b = solve(params, np.array([0]), 64, 0.01, [0.2], "cpu")
    assert a.shape == b.shape == (1, 1, 2, 64)
    # A nonzero difference confirms dt is used; magnitude is not an audit result.
    assert 0 < np.max(abs(a - b)) < 1e-3


def test_partial_result_remains_incomplete_and_contradictory_claim_is_rejected(
    tmp_path,
    monkeypatch,
):
    """Synthetic flat software fixture only; never published as solver evidence."""
    import json

    import pytest

    from engineering.rd_numerics.analyze import analyze
    from engineering.rd_numerics.audit import ROOT, dump, rd, sha

    folder = tmp_path / "partial"
    folder.mkdir()
    ids = np.repeat(np.arange(16), 3)
    seedidx = np.tile(np.arange(3), 16)
    np.savez_compressed(
        folder / "declared-inputs.npz",
        setting_ids=ids,
        seed_indices=seedidx,
        ic_seeds=ids * 1000 + seedidx,
        params=rd.settings_table()[ids],
        save_tau=[50, 100, 150, 200],
    )
    fields = np.ones((48, 4, 2, 64), dtype=np.float64)
    np.savez_compressed(
        folder / "config-0.npz",
        fields=fields,
        finite=np.ones((48, 4), bool),
        exceeded=np.zeros((48, 4), bool),
        negative=np.zeros((48, 4), bool),
    )
    dump(folder / "paired-discrepancies.json", [])
    receipt = {
        "complete": False,
        "completed_configs": [0],
        "paired_rows": 0,
        "source_pins": json.loads(
            (
                ROOT / "artifacts/rd-numerics/cpu-controls/input-code-pins.json"
            ).read_text()
        ),
        "files": {f.name: sha(f) for f in folder.iterdir()},
    }
    dump(folder / "receipt.json", receipt)
    analyze(folder, tmp_path / "analysis")
    report = json.loads((tmp_path / "analysis/summary.json").read_text())
    assert report["complete"] is False and report["convergence_pass"] is None
    receipt["complete"] = True
    dump(folder / "receipt.json", receipt)
    with pytest.raises(ValueError, match="Completeness claim"):
        analyze(folder, tmp_path / "bad-analysis")
    receipt["complete"] = False
    dump(folder / "receipt.json", receipt)

    def failed_recalculation(*args):
        raise ValueError("Synthetic derived-metric reproduction failure")

    monkeypatch.setattr(
        "engineering.rd_numerics.analyze.compare_saved_metrics", failed_recalculation
    )
    assert analyze(folder, tmp_path / "retained-failure", True) is False
    report = json.loads((tmp_path / "retained-failure/summary.json").read_text())
    assert report["independent_metric_reproduction_status"] == "FAILED"
    assert report["convergence_pass"] is None


def test_recalculation_tolerance_preserves_exact_modes_and_rejects_material_change():
    import pytest

    from engineering.rd_numerics.analyze import compare_saved_metrics

    actual = {"metric": 1.0, "mode": 3, "changed": False}
    check = compare_saved_metrics(actual, {**actual, "metric": 1.0 + 1e-13})
    assert 0 < check["max_absolute_recalculation_difference"] < 1e-12
    with pytest.raises(ValueError, match="beyond roundoff"):
        compare_saved_metrics(actual, {**actual, "metric": 1.01})
    with pytest.raises(ValueError, match="categorical"):
        compare_saved_metrics(actual, {**actual, "mode": 4})
