import math

import pytest

from engineering.mechanobio.model import Parameters, run_request, simulate


def test_binding_and_velocity_nulls():
    for p in (Parameters(on_rate_s=0), Parameters(unloaded_speed_nm_s=0)):
        result = simulate(p, duration_s=1)
        assert all(frame["traction_pN"] == 0 for frame in result["frames"])


def test_exact_mechanics_matches_independent_elastic_solution():
    p = Parameters(additional_stiffness_pN_nm=0, on_rate_s=0, off_rate_s=0)
    result = simulate(p, duration_s=2, dt_s=0.02, initial_bound=True)
    kc = p.clutches * p.clutch_stiffness_pN_nm
    keff = 1 / (1 / kc + 1 / p.long_term_stiffness_pN_nm)
    stall = p.motors * p.motor_stall_pN
    for f in result["frames"]:
        expected = stall * (1 - math.exp(-p.unloaded_speed_nm_s * keff * f["t_s"] / stall))
        assert f["traction_pN"] == pytest.approx(expected, abs=1e-10)


def test_force_law_mutant_changes_mechanics():
    p = Parameters(long_term_stiffness_pN_nm=1, clutches=5, rupture_force_pN=1)
    base = simulate(p, duration_s=12, seed=19)
    mutant = simulate(p, duration_s=12, seed=19, force_feedback=False)
    assert abs(base["summary"]["mean_traction_pN"] - mutant["summary"]["mean_traction_pN"]) > 1
    assert base["summary"]["max_force_balance_residual_pN"] < 1e-9


def test_replay_and_unsupported_transfer_labels():
    one = run_request({"duration_s": 1, "frame_count": 11})
    two = run_request({"duration_s": 1, "frame_count": 11})
    assert one["frames"] == two["frames"]
    assert one["provenance"]["trajectory_sha256"] == two["provenance"]["trajectory_sha256"]
    assert one["model"]["calibration"] == "none"
    assert one["evidence_kind"] == "simulated"
    assert one["parameter_provenance"]["motors"]["status"] == "assumed_scenario"


@pytest.mark.parametrize("payload", [{"duration_s": float("nan")}, {"seed": True}, {"frame_count": 1000},
                                    {"parameters": {"clutches": 1.2}}, {"parameters": {"motors": 10000}},
                                    {"unknown": 1}, {"parameters": {"viscosity_pN_s_nm": 0}}])
def test_resource_bounds_and_bad_inputs_are_refused(payload):
    with pytest.raises(ValueError):
        run_request(payload)
