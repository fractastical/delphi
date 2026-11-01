import numpy as np
import pytest

from engineering.fin_ray.model import Parameters, analytic, compute, controls, dump, unloaded_stiffness


def test_printed_parameters_cancel_hyperbolic_term_not_make_S_curve():
    p = Parameters()
    s = np.linspace(0, 1, 11)
    phi, derivative = analytic(s, p)
    assert np.array_equal(phi, .01 * (1 - s))
    assert np.all(derivative == -.01)
    assert controls()["passed"]


def test_unloaded_base_stiffness_is_energy_hessian_not_fin_EI():
    record, _ = compute(Parameters(G=20, p=0, phi0=.005))
    assert record["stiffness_relative_error"] < 1e-7
    assert unloaded_stiffness(Parameters(p=200)) is None
    assert unloaded_stiffness(Parameters(G=0, p=0)) == 20000


def test_invalid_coefficients_and_unbounded_localization_refused():
    with pytest.raises(ValueError):
        Parameters(G=-1)
    with pytest.raises(ValueError):
        Parameters(B=0)
    with pytest.raises(ValueError):
        Parameters(G=1e12)


def test_control_receipt_serializes_native_boolean_values(tmp_path):
    import json

    path = tmp_path / "controls.json"
    dump(path, controls())
    assert json.loads(path.read_text())["passed"] is True
