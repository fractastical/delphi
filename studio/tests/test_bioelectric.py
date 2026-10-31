"""Physics and bounded API checks; numerical challenge receipts live with artifacts."""
import json

import numpy as np
import pytest

from engineering.bioelectric import simulate
from engineering.bioelectric.controls import gap_balance, passive_membrane, voltage_clamp
from engineering.bioelectric.model import rates


def test_gap_charge_balance_and_sign_mutant():
    assert gap_balance()["passed"]
    assert not gap_balance(mutant=True)["passed"]


def test_membrane_and_gates_match_closed_forms():
    assert passive_membrane()["passed"]
    assert voltage_clamp()["passed"]


def test_removable_singularities_and_temperature_scaling():
    a, b = rates(np.array([-40., -55.]))
    assert np.isfinite(a).all() and np.isfinite(b).all()
    assert a[0, 0] == pytest.approx(1)
    assert a[2, 1] == pytest.approx(0.1)
    hotter_a, hotter_b = rates(np.array([-40., -55.]), 16.3)
    assert hotter_a == pytest.approx(a * 3)
    assert hotter_b == pytest.approx(b * 3)


@pytest.mark.parametrize("payload", [{"dt_ms": 0}, {"sodium_scale": float("nan")}, {"gap_mS_cm2": -1},
                                    {"duration_ms": 1e6}, {"schema": "x"}, {"fake": 1}, {"temperature_c": True}, []])
def test_request_limits(payload):
    assert simulate(payload)["status"] == "invalid_request"


def test_actual_network_propagates_and_disconnects():
    baseline = simulate({"duration_ms": 20})
    disconnected = simulate({"gap_mS_cm2": 0, "duration_ms": 20})
    blocked = simulate({"sodium_scale": 0, "duration_ms": 20})
    assert baseline["status"] == "completed"
    assert baseline["metrics"]["cells_crossing_0mV"] == 12
    assert disconnected["metrics"]["cells_crossing_0mV"] == 1
    assert blocked["metrics"]["cells_crossing_0mV"] == 0
    assert np.max(np.abs(np.array(disconnected["voltage_mV"])[:, 1:] + 65)) < 0.01
    assert baseline["simulationAction"]["input_sha256"] != disconnected["simulationAction"]["input_sha256"]
    assert baseline["open_questions"][0]["status"] == "unknown"
    json.dumps(baseline, allow_nan=False)
