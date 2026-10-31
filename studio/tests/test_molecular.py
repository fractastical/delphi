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
