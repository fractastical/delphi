"""Analytic metric cases and explicit failed-metric markers, not model outcomes."""

import numpy as np

from frontier_compute.diffusion_secondary_audit import nonfinite_paths, rank_pair_w1


def test_explicit_nonfinite_markers_and_numeric_overflow_are_both_failures():
    assert nonfinite_paths({"x": [{"status": "nonfinite", "token": "inf"}, float("inf")]}) == ["/x/0", "/x/1"]
    assert nonfinite_paths({"x": 0.0}) == []


def test_rank_formula_recovers_known_amplitude_shift_without_quantile_interpolation():
    solver = np.zeros((2, 2, 4), np.float32)
    solver[:, 0] = [-1, 1, -1, 1]
    generated = solver * 3
    result = rank_pair_w1(generated, solver)
    assert result["absolute_w1"] == 2 and result["relative_w1"] == 2
    zero = rank_pair_w1(generated, np.zeros_like(solver))
    assert zero["denominator"] == 0 and zero["relative_w1"] is None
    assert zero["absolute_w1"] == 3
