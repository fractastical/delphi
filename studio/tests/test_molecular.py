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


def test_failed_attempt_and_reference_oracle_repair_keep_original_limits():
    original = json.loads((ROOT / "artifacts/molecular/protocol.json").read_text())
    revised = json.loads(
        (ROOT / "artifacts/molecular/protocol-reference-oracle.json").read_text()
    )
    failure = json.loads(
        (ROOT / "artifacts/molecular/gpu-attempt-1/controls.json").read_text()
    )
    repaired = ROOT / "artifacts/molecular/gpu-attempt-1/repaired-controls"
    result = json.loads((repaired / "controls.json").read_text())
    assert failure["passed"] is False
    assert (
        failure["force_gradient"]["relative_error"]
        > original["controls"]["gradient_relative_max"]
    )
    for field in (
        "finite_difference_nm",
        "gradient_relative_max",
        "nve_duration_ps",
        "nve_drift_over_kinetic_max",
    ):
        assert revised["controls"][field] == original["controls"][field]
    assert (
        result["passed"] and result["force_gradient"]["energy_platform"] == "Reference"
    )
    assert (
        result["force_gradient"]["relative_error"]
        < original["controls"]["gradient_relative_max"]
    )
    assert result["force_gradient"]["CPU_Reference_force_relative_L2"] < 0.005
    assert (
        hashlib.sha256((repaired / "producer-run.py").read_bytes()).hexdigest()
        == result["code_sha256"]
    )


def test_exact_failed_state_diagnosis_preserves_h_and_demonstrates_precision():
    report = json.loads(
        (
            ROOT / "artifacts/molecular/gpu-attempt-1/derivative-diagnosis.json"
        ).read_text()
    )
    assert report["component"] == [345, 2]
    assert (
        report["state_sha256"]
        == "fb6ac7d070f975b6547324cbbb4027937968041e1b89e6c4f380ce9d7c470e73"
    )
    cpu = report["observations"]["CPU"]["gradient_scan"][1]
    reference = report["observations"]["Reference"]["gradient_scan"][1]
    assert cpu["h_nm"] == reference["h_nm"] == 0.00001
    assert cpu["relative_error"] > 0.005
    assert reference["relative_error"] < 1e-6
    assert (
        report["CPU_force_vs_Reference_derivative_at_frozen_h_relative_error"] < 0.005
    )


def test_descriptive_seed_analysis_and_render_retain_actual_backend_and_pins():
    production = ROOT / "artifacts/molecular/cpu-trajectory-final"
    analysis = json.loads(
        (ROOT / "artifacts/molecular/cpu-analysis/ensemble.json").read_text()
    )
    assert analysis["descriptive_endpoint_CA_RMSD_nm"]["n_runs"] == 1
    assert analysis["descriptive_endpoint_CA_RMSD_nm"]["sample_SD"] is None
    assert analysis["biological_success_probability"] is None
    assert analysis["empirical_accuracy"] == "unknown"
    assert (
        analysis["simulation_receipt_sha256"]
        == hashlib.sha256((production / "receipt.json").read_bytes()).hexdigest()
    )
    render = ROOT / "artifacts/molecular/cpu-render"
    receipt = json.loads((render / "render.json").read_text())
    assert receipt["backend"] == "CPU"
    assert receipt["preliminary_thermalization_ps"] == 0.1
    assert receipt["coordinate_storage_dtype"] == "float32"
    assert (
        receipt["render_code_sha256"]
        == hashlib.sha256((render / "producer-render.py").read_bytes()).hexdigest()
    )
    for name, digest in receipt["outputs"].items():
        assert hashlib.sha256((render / name).read_bytes()).hexdigest() == digest


def test_actual_cuda_result_three_nonempty_pinned_runs_and_backend_parity():
    folder = ROOT / "artifacts/molecular/cuda-v2"
    receipt = json.loads((folder / "production/receipt.json").read_text())
    assert len(receipt["runs"]) == 3
    assert {run["seed"] for run in receipt["runs"]} == {1731, 1732, 1733}
    assert all(
        run["backend"] == "CUDA"
        and run["production_ps"] == 100
        and run["frames"] == 101
        for run in receipt["runs"]
    )
    assert all(
        "H100" in run["platform_properties"]["DeviceName"] for run in receipt["runs"]
    )
    for name, digest in receipt["files"].items():
        assert (
            hashlib.sha256((folder / "production" / name).read_bytes()).hexdigest()
            == digest
        )
    parity = json.loads((folder / "cpu-cuda-parity.json").read_text())
    assert parity["passed"]
    assert parity["energy_abs_difference_kJ_mol_per_atom"] < 0.01
    assert parity["force_relative_L2_difference"] < 0.002
    summary = json.loads(
        (ROOT / "artifacts/molecular/cuda-analysis/ensemble.json").read_text()
    )
    assert summary["descriptive_endpoint_CA_RMSD_nm"]["n_runs"] == 3
    assert summary["descriptive_endpoint_CA_RMSD_nm"]["sample_SD"] > 0
    assert summary["biological_success_probability"] is None


def test_molecular_assurance_keeps_empirical_and_functional_robustness_unknown():
    assurance = json.loads(
        (ROOT / "artifacts/molecular/design-assurance.json").read_text()
    )
    assert assurance["vector"]["numerical_fidelity"]["status"] == "checked_in_scope"
    for name in ("empirical_validation", "cross_scale_transfer", "ensemble_robustness"):
        assert assurance["vector"][name]["status"] == "unknown"
    assert assurance["biological_success_probability"] is None
    for axis in assurance["vector"].values():
        for item in axis["evidence"]:
            assert (
                hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
                == item["sha256"]
            )


def test_continuation_protocol_preserves_parent_states_and_declares_new_rng():
    import tarfile

    protocol = json.loads(
        (ROOT / "artifacts/molecular/continuation-protocol.json").read_text()
    )
    archive = ROOT / "artifacts/molecular/warmstart-v3.tar.xz"
    assert (
        hashlib.sha256(archive.read_bytes()).hexdigest() == protocol["warmstart_sha256"]
    )
    assert protocol["additional_production_steps"] == 900000
    assert protocol["minimize"] is False and protocol["reset_velocities"] is False
    assert protocol["extra_thermalization_steps"] == 0
    assert len(protocol["branches"]) == 3
    with tarfile.open(archive) as tar:
        manifest = json.load(tar.extractfile("warmstart-files.json"))
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(tar.extractfile(name).read()).hexdigest() == digest
        for branch in protocol["branches"]:
            assert branch["new_thermostat_seed"] != branch["source_seed"]
            assert (
                hashlib.sha256(tar.extractfile(branch["state_path"]).read()).hexdigest()
                == branch["state_sha256"]
            )


def test_continuation_window_drift_diagnostic_keeps_negative_outcome():
    from engineering.molecular.continuation import small_window_drift

    protocol = json.loads(
        (ROOT / "artifacts/molecular/continuation-protocol.json").read_text()
    )
    # Synthetic software fixture for the reporting rule, never a measured series.
    metrics = [
        {
            "global_production_time_ps": t,
            "CA_RMSD_from_original_production_start_nm": 0.1,
            "CA_geometric_Rg_nm": 2.3,
        }
        for t in (600, 650, 700, 750, 800, 850, 900, 950, 1000)
    ]
    assert small_window_drift(metrics, protocol)["small_window_drift"]
    changed = [
        {
            **m,
            "CA_RMSD_from_original_production_start_nm": 0.3
            if m["global_production_time_ps"] >= 850
            else 0.1,
        }
        for m in metrics
    ]
    assert not small_window_drift(changed, protocol)["small_window_drift"]
    assert (
        "does not establish equilibrium"
        in small_window_drift(metrics, protocol)["meaning"]
    )


def test_actual_conditional_extensions_keep_parent_identity_and_negative_diagnostics():
    from engineering.molecular.continuation import small_window_drift

    folder = ROOT / "artifacts/molecular/cuda-v3"
    receipt = json.loads((folder / "production/receipt.json").read_text())
    protocol = json.loads(
        (ROOT / "artifacts/molecular/continuation-protocol.json").read_text()
    )
    assert (
        receipt["protocol_sha256"]
        == hashlib.sha256(
            (ROOT / "artifacts/molecular/continuation-protocol.json").read_bytes()
        ).hexdigest()
    )
    assert len(receipt["runs"]) == 3
    assert {r["parent_seed"] for r in receipt["runs"]} == {1731, 1732, 1733}
    assert {r["seed"] for r in receipt["runs"]} == {11731, 11732, 11733}
    outcomes = []
    for run in receipt["runs"]:
        assert run["backend"] == "CUDA" and run["production_ps"] == 900
        assert run["equilibration_steps"] == 0 and run["frames"] == 101
        seed = run["seed"]
        metrics = json.loads((folder / f"production/metrics-{seed}.json").read_text())
        data = np.load(folder / f"production/trajectory-{seed}.npz")
        assert data["global_production_times_ps"][[0, -1]].tolist() == [100, 1000]
        assert np.isfinite(data["positions_nm"]).all()
        diagnostic = small_window_drift(metrics, protocol)
        assert diagnostic == run["predeclared_diagnostic"]
        outcomes.append(diagnostic["small_window_drift"])
        control = json.loads(
            (folder / f"controls-{run['parent_seed']}/controls.json").read_text()
        )
        assert (
            control["passed"]
            and control["CUDA_parity"]["passed"]
            and control["nve"]["passed"]
        )
    assert outcomes == [False, False, True]
    for name, digest in receipt["files"].items():
        assert (
            hashlib.sha256((folder / "production" / name).read_bytes()).hexdigest()
            == digest
        )
    summary = json.loads(
        (ROOT / "artifacts/molecular/continuation-analysis/summary.json").read_text()
    )
    assert summary["n_new_independent_biological_samples"] == 0
    assert summary["biological_success_probability"] is None
    assert summary["empirical_accuracy"] == "unknown"
    assert summary["small_window_drift_diagnostic_count"] == 1
    assert all(
        r["frame0_vs_parent_final_saved_float32_max_abs_nm"] == 0
        for r in summary["branches"]
    )
    render = ROOT / "artifacts/molecular/continuation-render"
    render_receipt = json.loads((render / "render.json").read_text())
    assert render_receipt["global_production_time_ps"] == [100, 1000]
    for name, digest in render_receipt["outputs"].items():
        assert hashlib.sha256((render / name).read_bytes()).hexdigest() == digest
