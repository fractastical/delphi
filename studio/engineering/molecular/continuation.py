"""Exact-state conditional MD branches with new declared thermostat RNG seeds.

A State XML preserves coordinates/velocities, not the stochastic integrator RNG
stream. This is a conditional branch, not a bitwise continuation or an independent
new biological replicate. No minimization, velocity reset or extra thermalization.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
from urllib.request import urlopen

import numpy as np
import openmm as mm
from openmm import unit as u

from .diagnose import diagnose
from .run import CPU_THREADS, context_from, rmsd_nm, sha, write_json

CODE_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def load_warmstart(protocol, output):
    output.mkdir(parents=True, exist_ok=True)
    local = os.environ.get("MD_WARMSTART_PATH")
    if local:
        raw = Path(local).read_bytes()
    else:
        with urlopen(protocol["warmstart_url"], timeout=60) as response:
            raw = response.read(8_000_001)
    if (
        len(raw) > 8_000_000
        or hashlib.sha256(raw).hexdigest() != protocol["warmstart_sha256"]
    ):
        raise ValueError("Public warm-start input hash/size mismatch")
    archive = output / "warmstart-v3.tar.xz"
    archive.write_bytes(raw)
    warm = output / "warmstart"
    warm.mkdir(exist_ok=True)
    with tarfile.open(archive) as tar:
        item = tar.getmember("warmstart-files.json")
        if not item.isfile():
            raise ValueError("Invalid warm-start manifest")
        manifest = json.load(tar.extractfile(item))
        expected = set(manifest["files"]) | {"warmstart-files.json"}
        for member in tar.getmembers():
            if member.name not in expected or not member.isfile():
                raise ValueError("Unexpected warm-start member")
        tar.extractall(warm, filter="data")
    for name, digest in manifest["files"].items():
        if sha(warm / name) != digest:
            raise ValueError("Warm-start file mismatch: " + name)
    if (
        manifest["source_job_id"] != protocol["source_job_id"]
        or manifest["source_protocol_sha256"] != protocol["parent_protocol_sha256"]
    ):
        raise ValueError("Parent simulation identity mismatch")
    return warm, manifest


def nve_pair(prepared, state_path, protocol):
    source = mm.XmlSerializer.deserialize(state_path.read_text())
    system = mm.XmlSerializer.deserialize((prepared / "system.xml").read_text())
    rows = []
    endpoints = []
    for dt in (0.001, 0.0005):
        integrator = mm.VerletIntegrator(dt * u.picoseconds)
        integrator.setConstraintTolerance(1e-6)
        context = mm.Context(
            system,
            integrator,
            mm.Platform.getPlatformByName("CPU"),
            {"Threads": str(CPU_THREADS)},
        )
        context.setState(source)
        context.applyVelocityConstraints(1e-6)
        first = context.getState(getEnergy=True)
        e0 = (first.getKineticEnergy() + first.getPotentialEnergy()).value_in_unit(
            u.kilojoule_per_mole
        )
        kinetic = first.getKineticEnergy().value_in_unit(u.kilojoule_per_mole)
        integrator.step(round(protocol["controls"]["nve_duration_ps"] / dt))
        last = context.getState(getEnergy=True, getPositions=True)
        e1 = (last.getKineticEnergy() + last.getPotentialEnergy()).value_in_unit(
            u.kilojoule_per_mole
        )
        rows.append(
            {
                "dt_ps": dt,
                "duration_ps": protocol["controls"]["nve_duration_ps"],
                "energy_drift_over_initial_kinetic": abs(e1 - e0) / max(kinetic, 1),
                "initial_total_kJ_mol": e0,
                "final_total_kJ_mol": e1,
            }
        )
        endpoints.append(
            np.asarray(last.getPositions(asNumpy=True).value_in_unit(u.nanometer))
        )
        del context, integrator
    return {
        "runs": rows,
        "paired_endpoint_all_atom_rmsd_nm": rmsd_nm(*endpoints),
        "passed": all(
            r["energy_drift_over_initial_kinetic"]
            < protocol["controls"]["nve_drift_over_initial_kinetic_max"]
            for r in rows
        ),
    }


def controls(warm, branch, protocol, output, require_cuda):
    output.mkdir(parents=True, exist_ok=True)
    prepared = warm / "prepared"
    state_path = warm / branch["state_path"]
    if sha(state_path) != branch["state_sha256"]:
        raise ValueError("Parent final-state hash mismatch")
    diagnose(prepared, state_path, output / "gradient-diagnosis.json")
    derivative = json.loads((output / "gradient-diagnosis.json").read_text())
    h = derivative["observations"]["Reference"]["gradient_scan"][1]
    if h["h_nm"] != protocol["controls"]["finite_difference_nm"]:
        raise ValueError("Frozen perturbation mismatch")
    nve = nve_pair(prepared, state_path, protocol)
    cpu_force = derivative["observations"]["CPU"]["gradient_scan"][1]["analytic_kJ_mol_nm"]
    wrong_sign = abs(h["finite_difference_kJ_mol_nm"] + cpu_force) / max(abs(cpu_force), 1)
    checks = {
        "source_state_sha256": sha(state_path),
        "gradient": derivative,
        "nve": nve,
        "CUDA_parity": None,
        "wrong_sign_relative_error": wrong_sign,
    }
    passed = (
        derivative["CPU_force_vs_Reference_derivative_at_frozen_h_relative_error"]
        < protocol["controls"]["gradient_relative_max"]
        and derivative["CPU_Reference_force_relative_L2"]
        < protocol["controls"]["CPU_Reference_force_relative_L2_max"]
        and nve["passed"]
        and wrong_sign > 1
    )
    if require_cuda:
        measured = []
        for backend in ("CPU", "CUDA"):
            integrator = mm.VerletIntegrator(0.001 * u.picoseconds)
            _, context = context_from(prepared, integrator, backend)
            context.setState(mm.XmlSerializer.deserialize(state_path.read_text()))
            state = context.getState(getEnergy=True, getForces=True)
            measured.append(
                (
                    state.getPotentialEnergy().value_in_unit(u.kilojoule_per_mole),
                    np.asarray(
                        state.getForces(asNumpy=True).value_in_unit(
                            u.kilojoule_per_mole / u.nanometer
                        )
                    ),
                )
            )
            del context, integrator
        energy = abs(measured[0][0] - measured[1][0]) / len(measured[0][1])
        force = float(
            np.linalg.norm(measured[0][1] - measured[1][1])
            / np.linalg.norm(measured[0][1])
        )
        parity = {
            "energy_error_per_atom_kJ_mol": energy,
            "force_relative_L2": force,
            "passed": bool(
                energy < protocol["controls"]["CPU_CUDA_energy_error_per_atom_max"]
                and force < protocol["controls"]["CPU_CUDA_force_relative_L2_max"]
            ),
        }
        checks["CUDA_parity"] = parity
        passed = passed and parity["passed"]
    checks["passed"] = bool(passed)
    checks["scope"] = (
        "Numerical same-state checks; no molecular equilibrium or biological validation"
    )
    write_json(output / "controls.json", checks)
    if not passed:
        raise RuntimeError("Unchanged continuation numerical control failed")
    return checks


def small_window_drift(metrics, protocol):
    early, late = protocol["predeclared_analysis"]["window_global_production_ps"]
    windows = []
    for start, end in (early, late):
        items = [m for m in metrics if start <= m["global_production_time_ps"] <= end]
        if not items:
            raise ValueError("Declared diagnostic window has no samples")
        windows.append(
            {
                "window_ps": [start, end],
                "n_samples": len(items),
                "actual_sample_range_ps": [
                    items[0]["global_production_time_ps"],
                    items[-1]["global_production_time_ps"],
                ],
                "mean_original_reference_CA_RMSD_nm": float(
                    np.mean(
                        [m["CA_RMSD_from_original_production_start_nm"] for m in items]
                    )
                ),
                "mean_CA_geometric_Rg_nm": float(
                    np.mean([m["CA_geometric_Rg_nm"] for m in items])
                ),
            }
        )
    rmsd = abs(
        windows[1]["mean_original_reference_CA_RMSD_nm"]
        - windows[0]["mean_original_reference_CA_RMSD_nm"]
    )
    rg = abs(
        windows[1]["mean_CA_geometric_Rg_nm"] - windows[0]["mean_CA_geometric_Rg_nm"]
    )
    threshold = protocol["predeclared_analysis"]["small_window_drift_diagnostic"]
    return {
        "windows": windows,
        "RMSD_window_mean_change_nm": rmsd,
        "CA_Rg_window_mean_change_nm": rg,
        "small_window_drift": bool(
            rmsd < threshold["RMSD_threshold_nm"]
            and rg < threshold["CA_Rg_threshold_nm"]
        ),
        "meaning": "Descriptive finite-window diagnostic; false outcomes retained. Even true does not establish equilibrium or material properties.",
    }


def production(warm, branch, protocol, output):
    output.mkdir(parents=True, exist_ok=True)
    prepared = warm / "prepared"
    atoms = json.loads((prepared / "atoms.json").read_text())
    heavy = [a["index"] for a in atoms if a["element"] != "H"]
    ca = [a["index"] for a in atoms if a["name"] == "CA"]
    baseline = np.load(warm / branch["baseline_reference_path"])["CA_positions_nm"]
    state_path = warm / branch["state_path"]
    seed = branch["new_thermostat_seed"]
    started = time.perf_counter()
    integrator = mm.LangevinMiddleIntegrator(
        protocol["temperature_K"] * u.kelvin,
        protocol["friction_per_ps"] / u.picosecond,
        protocol["timestep_ps"] * u.picoseconds,
    )
    integrator.setRandomNumberSeed(seed)
    integrator.setConstraintTolerance(1e-6)
    system, context = context_from(prepared, integrator, "CUDA")
    context.setState(mm.XmlSerializer.deserialize(state_path.read_text()))
    source = context.getState(getPositions=True, getVelocities=True)
    initial = np.asarray(source.getPositions(asNumpy=True).value_in_unit(u.nanometer))
    context_initial_time = source.getTime().value_in_unit(u.picoseconds)
    steps = protocol["additional_production_steps"]
    stride = steps // protocol["frames_per_branch"]
    if steps % stride:
        raise ValueError("Production steps must match frame stride exactly")
    frames = []
    metrics = []
    for step in range(0, steps + 1, stride):
        state = context.getState(getPositions=True, getEnergy=True)
        x = np.asarray(state.getPositions(asNumpy=True).value_in_unit(u.nanometer))
        potential = state.getPotentialEnergy().value_in_unit(u.kilojoule_per_mole)
        kinetic = state.getKineticEnergy().value_in_unit(u.kilojoule_per_mole)
        if not np.isfinite(x).all() or not np.isfinite([potential, kinetic]).all():
            raise RuntimeError("Nonfinite continuation state")
        chain_lengths = []
        for chain in ("A", "B", "C"):
            ids = [
                a["index"] for a in atoms if a["chain"] == chain and a["name"] == "CA"
            ]
            chain_lengths.append(float(np.linalg.norm(x[ids[-1]] - x[ids[0]])))
        centered = x[ca] - x[ca].mean(0)
        t = step * protocol["timestep_ps"]
        dof = 3 * system.getNumParticles() - system.getNumConstraints() - 3
        metrics.append(
            {
                "time_ps": t,
                "global_production_time_ps": protocol["parent_production_ps"] + t,
                "potential_energy_kJ_mol": potential,
                "kinetic_energy_kJ_mol": kinetic,
                "kinetic_temperature_K": 2
                * kinetic
                / (
                    dof
                    * u.MOLAR_GAS_CONSTANT_R.value_in_unit(
                        u.kilojoule_per_mole / u.kelvin
                    )
                ),
                "CA_RMSD_nm": rmsd_nm(x[ca], initial[ca]),
                "CA_RMSD_from_original_production_start_nm": rmsd_nm(x[ca], baseline),
                "CA_geometric_Rg_nm": float(
                    np.sqrt(np.mean(np.sum(centered**2, axis=1)))
                ),
                "chain_end_to_end_nm": chain_lengths,
            }
        )
        frames.append(x[heavy].copy())
        if step + stride <= steps:
            integrator.step(stride)
    np.savez_compressed(
        output / f"trajectory-{seed}.npz",
        positions_nm=np.array(frames, dtype=np.float32),
        atom_indices=np.array(heavy),
        times_ps=np.array([m["time_ps"] for m in metrics]),
        global_production_times_ps=np.array(
            [m["global_production_time_ps"] for m in metrics]
        ),
    )
    write_json(output / f"metrics-{seed}.json", metrics)
    (output / f"final-state-{seed}.xml").write_text(
        mm.XmlSerializer.serialize(
            context.getState(getPositions=True, getVelocities=True, getEnergy=True)
        )
    )
    summary = {
        "seed": seed,
        "parent_seed": branch["source_seed"],
        "parent_state_sha256": sha(state_path),
        "backend": "CUDA",
        "platform_properties": {
            k: context.getPlatform().getPropertyValue(context, k)
            for k in context.getPlatform().getPropertyNames()
        },
        "production_steps": steps,
        "equilibration_steps": 0,
        "production_ps": steps * protocol["timestep_ps"],
        "equilibration_ps": 0,
        "parent_production_ps": protocol["parent_production_ps"],
        "context_initial_time_ps": context_initial_time,
        "frames": len(frames),
        "wall_seconds": time.perf_counter() - started,
        "final_CA_RMSD_nm": metrics[-1]["CA_RMSD_nm"],
        "predeclared_diagnostic": small_window_drift(metrics, protocol),
        "random_state_scope": protocol["random_state_note"],
    }
    del context, integrator
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--branch", type=int)
    args = parser.parse_args()
    path = Path("artifacts/molecular/continuation-protocol.json")
    protocol = json.loads(path.read_text())
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    warm, manifest = load_warmstart(protocol, out)
    if os.environ.get("PREFLIGHT"):
        print(
            "Continuation preflight verified exact warm-start archive and files; no integration",
            flush=True,
        )
        return
    if args.branch is not None and not args.check_only:
        raise ValueError("Branch selector is only for CPU control checks")
    if not args.check_only:
        mm.Platform.getPlatformByName("CUDA")
    summaries = []
    branches = [
        b
        for b in protocol["branches"]
        if args.branch is None or b["source_seed"] == args.branch
    ]
    if not branches:
        raise ValueError("No declared source branches selected")
    for branch in branches:
        controls(
            warm,
            branch,
            protocol,
            out / f"controls-{branch['source_seed']}",
            not args.check_only,
        )
        if not args.check_only:
            summaries.append(production(warm, branch, protocol, out / "production"))
    if args.check_only:
        write_json(
            out / "CPU-check-only.json",
            {
                "passed": True,
                "branches": [b["source_seed"] for b in branches],
                "protocol_sha256": sha(path),
                "code_sha256": CODE_SHA,
                "scope": "CPU/Reference derivative+NVE controls only; CUDA parity and production not run",
            },
        )
        return
    prod = out / "production"
    write_json(
        prod / "receipt.json",
        {
            "schema": "frontier.molecular.run/1",
            "protocol_sha256": sha(path),
            "parent_job_id": protocol["source_job_id"],
            "code_sha256": CODE_SHA,
            "openmm_version": mm.__version__,
            "python": sys.version,
            "numpy_version": np.__version__,
            "warmstart_sha256": protocol["warmstart_sha256"],
            "runs": summaries,
            "empirical_accuracy": "unknown",
            "scope": "Conditional extensions of3parents,not6independent runs; no equilibrium/modulus claim",
            "files": {
                f.name: sha(f)
                for f in prod.iterdir()
                if f.is_file() and f.name != "receipt.json"
            },
        },
    )
    (out / "environment.txt").write_text(
        subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    write_json(
        out / "job-receipt.json",
        {
            "protocol_sha256": sha(path),
            "code_sha256": CODE_SHA,
            "source_job_id": protocol["source_job_id"],
            "GPU": subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,driver_version",
                    "--format=csv,noheader",
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip(),
            "files": {
                str(f.relative_to(out)): sha(f)
                for f in out.rglob("*")
                if f.is_file() and f.name != "job-receipt.json"
            },
        },
    )
    print(
        "Conditional900ps CUDA branches completed; finite-window diagnostic is not equilibrium",
        flush=True,
    )


if __name__ == "__main__":
    main()
