import copy
import json
from pathlib import Path

import pytest

from engineering.assurance_experiments.experiment import (
    controls, physical_inputs, predicate, protocol_receipt, sample_parameters, simulate_case, trial, wilson,
)

PROTOCOL = Path(__file__).resolve().parents[1] / "engineering/assurance_experiments/protocol.json"


def protocol():
    return json.loads(PROTOCOL.read_text())


def test_protocol_is_frozen_and_nonvacuous():
    p, receipt = protocol_receipt(PROTOCOL)
    assert len(receipt["protocol_commit"]) == 40
    assert len(receipt["sha256"]) == 64
    assert p["parameter_draws"] >= 2
    assert len(p["candidates"]) >= 3
    assert p["predicate"]["declared_before_runs"]


def test_shared_correlations_and_candidate_inputs_are_actual_parameters():
    p = protocol()
    draws = sample_parameters(p)
    assert draws == sample_parameters(p)
    for draw in draws:
        assert draw["rho_kg_m3"] == pytest.approx(1.6 - .075 * draw["speed_m_s"])
        assert draw["tributary_width_m"] == pytest.approx(.008 + .004/.3 * (draw["length_multiplier"]-.85))
        base, short, stiff = [physical_inputs(draw, candidate) for candidate in p["candidates"]]
        assert short["L_m"] / base["L_m"] == pytest.approx(.8)
        assert stiff["EI_Nm2"] / base["EI_Nm2"] == pytest.approx(2)
        assert stiff["q_N_m"] == base["q_N_m"]
        assert 1e-6 <= draw["context_E_Pa"] * 1e-14 <= 1e-5
        assert draw["EI_Nm2"] >= .0003  # no context-EI transfer


def test_paired_load_shapes_retain_the_actual_discrepancy():
    p = protocol()
    row = trial(sample_parameters(p)[0], p["candidates"][0], p)
    a, b = row["cases"]["uniform"], row["cases"]["tip_same_total_force"]
    assert b["summary"]["tip_over_L"] / a["summary"]["tip_over_L"] == pytest.approx(8/3, rel=1e-8)
    assert row["passed"] == all(predicate(case["summary"], p) for case in row["cases"].values())
    assert a["summary"]["analytic_tip_relative_error"] < p["numerics"]["analytic_relative_tolerance"]


def test_bad_load_shape_is_refused_and_threshold_failure_is_preserved():
    p = protocol()
    inp = {"L_m": .15, "EI_Nm2": 1e-6, "q_N_m": .1}
    with pytest.raises(ValueError):
        simulate_case(inp, "invented", p)
    failed = simulate_case(inp, "uniform", p)
    assert not failed["within_linear_envelope"]
    assert "extrapolation" in failed["interpretation"]
    assert failed["summary"]["tip_over_L"] > .1


def test_independent_controls_and_velocity_law_mutant_execute():
    result = controls(protocol())
    assert result["passed"]
    assert result["speed_law_mutant"]["detected"]
    assert result["paired_sensitivity"]["speed_m_s"]["elasticity"] == pytest.approx(2, abs=.001)
    assert result["speed_law_mutant"]["measured_elasticity"] == pytest.approx(1, abs=.001)
    altered = copy.deepcopy(protocol())
    altered["predicate"]["tip_over_length_limit"] = 0
    assert not predicate({"tip_over_L": .001, "max_slope_rad": .01}, altered)


def test_conditional_interval_refuses_empty_ensemble():
    with pytest.raises(ValueError):
        wilson(0, 0)
    low, high = wilson(32, 64)
    assert 0 < low < .5 < high < 1
    assert wilson(0, 64)[0] == pytest.approx(0)
