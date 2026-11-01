"""Actual frozen-bundle receipts plus direct CPG/plant law and bound checks."""
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pytest

from engineering.behavior import model

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/behavior"


def test_cpg_target_wave_is_an_exact_phase_solution():
    p = model.validate({})
    state = np.zeros((5, model.N))
    state[0] = -np.arange(model.N) * p["phase_lag_rad"]
    state[1] = 1
    phase_velocity, amplitude_acceleration, *_ = model.cpg(state, p)
    assert phase_velocity == pytest.approx(np.full(model.N, 2 * np.pi * p["frequency_Hz"]))
    assert amplitude_acceleration == pytest.approx(np.zeros(model.N))
    state[0, 4] += .5
    disturbed = model.cpg(state, p)[0]
    assert disturbed[4] < phase_velocity[4]
    uncoupled = model.cpg(state, p | {"coupling_s": 0})[0]
    assert uncoupled == pytest.approx(phase_velocity)


def test_passive_plant_energy_law_uses_actual_rhs():
    # Internal analytic control: disable all angle drive, not a public request.
    p = model.DEFAULTS | {"amplitude_rad": 0, "feedback": False}
    state = np.zeros((5, model.N))
    state[3] = .02
    state[4] = .3
    derivative = model.rhs(state, p, 0)
    energy_rate = model.J * state[4] * derivative[4] + model.K * state[3] * state[4]
    assert energy_rate == pytest.approx(-model.B * state[4] ** 2)


def test_wrong_feedback_sign_reverses_restoring_torque():
    p = model.validate({})
    state = np.zeros((5, model.N))
    state[0] = np.pi / 2
    state[1] = 1
    state[3] = .01
    normal, _ = model.torque(state, p)
    mutant, _ = model.torque(state, p | {"feedback_sign": -1})
    assert np.all(normal < 0) and np.all(mutant > 0)
    assert np.max(np.abs(normal)) <= model.TORQUE_MAX


@pytest.mark.parametrize("payload", [{"frequency_Hz": 100}, {"amplitude_rad": 1}, {"coupling_s": -1},
                                     {"inertia_scale": float("nan")}, {"dt_s": .01}, {"duration_s": 500},
                                     {"feedback": 1}, {"feedback_sign": True}, {"code": "pass"}, []])
def test_public_request_cannot_exceed_declared_bounded_proxy(payload):
    with pytest.raises(ValueError):
        model.validate(payload)


def test_actual_bundle_keeps_all_controls_counterexamples_and_frozen_acceptance():
    controls = json.loads((OUTPUT / "controls.json").read_text())
    assert controls["passed"] and len(controls["checks"]) == 8
    checks = {row["name"]: row for row in controls["checks"]}
    assert not checks["feedback_sign_mutant_rejected"]["mutant_baseline_predicate_passed"]
    assert checks["feedback_removed_discriminates"]["ratio"] > 2
    assert checks["coupling_removed_discriminates"]["ratio"] > 5
    baseline = json.loads((OUTPUT / "baseline.json").read_text())
    changed = json.loads((OUTPUT / "changed_frequency.json").read_text())
    bad = json.loads((OUTPUT / "feedback_removed.json").read_text())
    assert baseline["metrics"]["leader_frequency_Hz"] == pytest.approx(35)
    assert changed["metrics"]["leader_frequency_Hz"] == pytest.approx(25)
    assert not baseline["metrics"]["outside_proposed_static_angle_envelope"]
    assert bad["metrics"]["outside_proposed_static_angle_envelope"]
    assert baseline["evidence_kind"] == "SimulationResult"
    assert len(baseline["actual_angle_rad"]) == len(baseline["time_s"])
    assert baseline["limitations"] and baseline["source_envelope"]["transfer"]


def test_manifest_inputs_source_hashes_and_actual_render_frame_pins():
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    assert manifest["code_sha256"] == model.code_hashes()
    for name, pointer in manifest["files"].items():
        data = (OUTPUT / name).read_bytes()
        assert sha256(data).hexdigest() == pointer["sha256"]
        assert len(data) == pointer["byte_size"]
    assert manifest["protocol_sha256"] == sha256((model.HERE / "protocol.json").read_bytes()).hexdigest()
    render = json.loads((OUTPUT / "render_receipt.json").read_text())
    assert render["kind"] == "render" and render["time_interpolation"] == "none"
    assert render["frames"] == len(render["actual_state_frame_indices"])
    baseline = json.loads((OUTPUT / "baseline.json").read_text())
    assert all(0 <= index < len(baseline["time_s"]) for index in render["actual_state_frame_indices"])


def test_equation_parameter_ports_and_missing_bridges_remain_explicit():
    interface = json.loads((model.HERE / "interface.json").read_text())
    assert len(interface["equations"]) == 5
    assert all(row["variables"] and row["implementation"] and row["source"] for row in interface["equations"])
    assert all(row["basis"] for row in interface["parameter_registry"])
    coupling = interface["proposed_coupling"]
    assert coupling["status"] == "unsupported_dynamic_transfer" and "unknown" in coupling["frequency_transfer"]
    assert json.loads((model.HERE / "problems.json").read_text())["status"] == "proposed_not_persisted"
