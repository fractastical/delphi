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
