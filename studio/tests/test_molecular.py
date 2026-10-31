"""Numerical geometry controls and exact frozen molecular-input provenance."""

import hashlib
import json
from pathlib import Path

import numpy as np

from engineering.molecular.run import rmsd_nm

ROOT = Path(__file__).parents[1]


def test_rmsd_removes_translation_and_proper_rotation():
    x = np.array([[0.0, 0, 0], [1, 0, 0], [0, 2, 0], [0, 0, 3]])
    rotation = np.array([[0.0, -1, 0], [1, 0, 0], [0, 0, 1]])
    assert rmsd_nm(x @ rotation + np.array([8, 7, 6]), x) < 1e-12


def test_rmsd_does_not_fit_reflection_or_hide_deformation():
    x = np.array([[0.0, 0, 0], [1, 0, 0], [0, 2, 0], [0, 0, 3]])
    y = x.copy()
    y[:, 0] *= -1
    assert rmsd_nm(x, y) > 0.5
    y = x.copy()
    y[0, 2] += 1
    assert rmsd_nm(x, y) > 0.2


def test_protocol_pins_actual_standard_collagen_mimetic():
    protocol = json.loads((ROOT / "artifacts/molecular/protocol.json").read_text())
    data = (ROOT / protocol["source_path"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == protocol["source_sha256"]
    assert len(protocol["seeds"]) == len(set(protocol["seeds"])) == 3
    assert protocol["timestep_ps"] == 0.001
    assert protocol["production_steps"] % protocol["frames"] == 0
    assert protocol["controls"]["gradient_relative_max"] == 0.005
    residues = {
        line[17:20] for line in data.decode().splitlines() if line.startswith("ATOM")
    }
    assert residues == {"PRO", "GLY"}


def test_preparation_files_match_pins_and_standard_templates():
    prepared = ROOT / "artifacts/molecular/prepared"
    receipt = json.loads((prepared / "preparation.json").read_text())
    assert receipt["chain_residues"] == [29, 29, 29]
    assert receipt["total_atoms"] > receipt["solute_atoms"] > 0
    assert receipt["terminal_missing_residues_not_rebuilt"] == [30, 30, 30]
    for name, digest in receipt["files"].items():
        assert hashlib.sha256((prepared / name).read_bytes()).hexdigest() == digest


def test_completed_cpu_checks_are_finite_and_kill_wrong_sign():
    checks = json.loads(
        (ROOT / "artifacts/molecular/cpu-controls/controls.json").read_text()
    )
    assert checks["passed"]
    assert checks["minimization"]["decreased"]
    assert checks["force_gradient"]["relative_error"] < 0.005
    assert checks["force_gradient"]["wrong_sign_relative_error"] > 1
    assert len(checks["nve"]) == 2
    assert all(row["energy_drift_over_initial_kinetic"] < 0.02 for row in checks["nve"])


def test_native_interface_refuses_length_to_fin_material_transfer():
    from engineering.coupling import (
        Coupling,
        default_registry,
        model_from_json,
        validate_coupling,
    )

    model = model_from_json(
        json.loads((ROOT / "artifacts/molecular/model-interface.json").read_text())
    )
    reg = default_registry()
    reg.add_model(model)
    verdict = validate_coupling(
        reg,
        Coupling(
            "test",
            "collagen_mimetic_md.terminal_CA_distance",
            "finbeam_euler_bernoulli.flexural_rigidity",
            mapping_kind="none",
        ),
    )
    assert verdict.status == "refused"
    assert model.timescale.kind == "unknown"
    assert model.port("terminal_CA_distance").unit == "nm"


def test_delivered_trajectory_and_render_are_actual_pinned_states():
    folder = ROOT / "artifacts/molecular/cpu-trajectory-final"
    receipt = json.loads((folder / "receipt.json").read_text())
    assert (
        hashlib.sha256((folder / "producer-run.py").read_bytes()).hexdigest()
        == receipt["code_sha256"]
    )
    data = np.load(folder / "trajectory-1731.npz")
    metrics = json.loads((folder / "metrics-1731.json").read_text())
    assert len(data["positions_nm"]) == len(metrics) == 101
    assert np.isfinite(data["positions_nm"]).all()
    assert np.max(abs(data["positions_nm"][-1] - data["positions_nm"][0])) > 0
    assert data["times_ps"][-1] == 0.2
    assert all(np.isfinite(m["kinetic_temperature_K"]) for m in metrics)
    render = json.loads(
        (ROOT / "artifacts/molecular/cpu-render/render.json").read_text()
    )
    assert (
        render["trajectory_sha256"]
        == hashlib.sha256((folder / "trajectory-1731.npz").read_bytes()).hexdigest()
    )
    assert render["simulation_duration_ps"] == 0.2 and render["frames"] == 101


def test_model_inventory_keeps_proposed_and_executed_distinct():
    inventory = json.loads((ROOT / "artifacts/molecular/model-index.json").read_text())
    models = inventory["models"]
    assert len(models) >= 12 and len({row["id"] for row in models}) == len(models)
    actual = next(row for row in models if row["id"] == "collagen_mimetic_md")
    assert actual["biological_success_probability"] is None
    assert actual["empirical_accuracy"] == "unknown"
    for row in models:
        assert row["source"] and row["missing_transfer"] and row["coupling_ports"]
        if row["status"].startswith("source_only"):
            assert "artifacts" not in row
