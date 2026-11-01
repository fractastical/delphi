import pytest

from engineering.aeroelastic.flight import trajectory
from engineering.aeroelastic.uncertainty import _effect, derive


def _valid_arm(cl, main_range, half_range, status):
    return {
        "valid_for_declared_transfer": True,
        "status": status,
        "iterations": [{"CL_on_fixed_source_area": cl}],
        "flight": {
            "main": {"range_m": main_range},
            "half": {"range_m": half_range},
            "range_relative_difference": 0.002,
            "dt_gate_passed": False,
        },
    }


def test_paired_effect_keeps_sign_and_main_half_dt_ranges_separate():
    reference = _valid_arm(0.25, 13.0, 13.2, "computed rigid")
    target = _valid_arm(0.24, 12.0, 12.1, "converged static feedback")
    result = _effect(target, reference)
    assert result["available"]
    assert result["delta_CL"] == pytest.approx(-0.01)
    assert result["delta_range_m"] == -1.0
    assert result["delta_half_dt_range_m"] == pytest.approx(-1.1)


def test_derive_preserves_missing_rows_and_reports_mesh_discrepancy_descriptively():
    arms = []
    for mesh, rigid_cl, one_cl, rigid_range, one_range in [
        ("main", 0.25, 0.24, 13.0, 12.0),
        ("fine", 0.26, 0.245, 14.0, 12.5),
    ]:
        for name, arm, cl, distance in [
            ("rigid", "rigid", rigid_cl, rigid_range),
            ("one-way-frozen-load", "one-way-frozen-load", one_cl, one_range),
        ]:
            arms.append(
                {
                    **_valid_arm(cl, distance, distance + 0.1, arm),
                    "scenario_id": "nominal",
                    "pressure_policy": "updated-deformed-distribution",
                    "mesh": mesh,
                    "arm": name,
                }
            )
    result = derive(arms)
    pair = next(
        row
        for row in result["paired_effects"]
        if row["scenario_id"] == "nominal"
        and row["pressure_policy"] == "updated-deformed-distribution"
        and row["mesh"] == "main"
        and row["comparison"] == "one-way-minus-rigid"
    )
    assert pair["available"] and pair["delta_CL"] == pytest.approx(-0.01)
    mesh = next(
        row
        for row in result["mesh_effect_resolution"]
        if row["scenario_id"] == "nominal"
        and row["pressure_policy"] == "updated-deformed-distribution"
        and row["comparison"] == "one-way-minus-rigid"
    )
    assert mesh["available"]
    assert mesh["main_minus_fine_delta_CL"] == pytest.approx(0.005)
    assert "not a validated error bound" in mesh["interpretation"]
    missing = next(
        row
        for row in result["paired_effects"]
        if row["scenario_id"] == "high-demand"
        and row["pressure_policy"] == "updated-deformed-distribution"
        and row["mesh"] == "main"
        and row["comparison"] == "one-way-minus-rigid"
    )
    assert not missing["available"]
    assert missing["reason"] == "missing declared arm"


def test_invalid_arm_is_not_promoted_to_paired_estimate():
    invalid = {"valid_for_declared_transfer": False, "status": "model-domain exit"}
    valid = _valid_arm(0.2, 5.0, 5.1, "computed rigid")
    result = _effect(invalid, valid)
    assert not result["available"]
    assert result["target_status"] == "model-domain exit"


def test_flight_adapter_reports_declared_mass_and_drag_scenario_scales():
    _, base = trajectory(0.3, 0.004, 4.0, 20.0, 0.004)
    _, scaled = trajectory(
        0.3, 0.004, 4.0, 20.0, 0.004, mass_scale=1.1, CD0_scale=1.15
    )
    assert base["mass_kg"] == 0.05
    assert scaled["mass_kg"] == pytest.approx(0.055)
    assert scaled["range_m"] != base["range_m"]
