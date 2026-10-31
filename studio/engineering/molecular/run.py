"""Bounded OpenMM simulation of the experimental 1K6F collagen-mimetic trimer.

All saved trajectory coordinates are actual states. No effective tissue modulus
or biological success probability is inferred from short molecular trajectories.
"""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import sys
import time

import numpy as np
import openmm as mm
from openmm import app, unit as u

CODE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def rmsd_nm(x, reference):
    """Proper-rotation least-squares RMSD, with translation removed."""
    x = np.asarray(x) - np.mean(x, axis=0)
    y = np.asarray(reference) - np.mean(reference, axis=0)
    left, _, right = np.linalg.svd(x.T @ y)
    correction = np.diag([1, 1, np.linalg.det(left @ right)])
    return float(
        np.sqrt(np.mean(np.sum((x @ left @ correction @ right - y) ** 2, axis=1)))
    )


def prepare(protocol, output):
    from pdbfixer import PDBFixer

    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    seed = protocol["preparation_seed"]
    random.seed(seed)
    np.random.seed(seed)
    source = Path(protocol["source_path"])
    if sha(source) != protocol["source_sha256"]:
        raise ValueError("Input PDB hash mismatch")
    fixer = PDBFixer(filename=str(source))
    fixer.removeHeterogens(False)
    # The deposited terminal Gly30 is absent in all three chains. Do not invent
    # unobserved residues: simulate the modeled29-residue chains with free termini.
    fixer.findMissingResidues()
    fixer.missingResidues = {}
    fixer.findMissingAtoms()
    added = {
        str((r.chain.id, r.id)): [a.name for a in atoms]
        for r, atoms in fixer.missingAtoms.items()
    }
    terminal = {
        str((r.chain.id, r.id)): names for r, names in fixer.missingTerminals.items()
    }
    fixer.addMissingAtoms(seed=seed)
    ff = app.ForceField(*protocol["forcefield_files"])
    model = app.Modeller(fixer.topology, fixer.positions)
    model.addHydrogens(
        ff, pH=protocol["pH"], platform=mm.Platform.getPlatformByName("CPU")
    )
    solute_atoms = list(model.topology.atoms())
    if len(list(model.topology.chains())) != 3 or set(
        a.residue.name for a in solute_atoms
    ) != {"PRO", "GLY"}:
        raise ValueError(
            "Expected exactly three standard-residue collagen-mimetic chains"
        )
    positions = np.asarray(model.positions.value_in_unit(u.nanometer))
    box = np.ptp(positions, axis=0) + 2 * protocol["padding_nm"]
    model.addSolvent(
        ff,
        model="tip3p",
        boxSize=mm.Vec3(*box) * u.nanometer,
        ionicStrength=protocol["salt_molar"] * u.molar,
        neutralize=True,
    )
    system = ff.createSystem(
        model.topology,
        nonbondedMethod=app.PME,
        nonbondedCutoff=protocol["cutoff_nm"] * u.nanometer,
        constraints=app.HBonds,
        rigidWater=True,
        ewaldErrorTolerance=protocol["ewald_error_tolerance"],
    )
    with (out / "prepared.pdb").open("w") as f:
        app.PDBFile.writeFile(model.topology, model.positions, f, keepIds=True)
    (out / "system.xml").write_text(mm.XmlSerializer.serialize(system))
    # XML State preserves full coordinate precision; PDB is human-readable only.
    integrator = mm.VerletIntegrator(0.001 * u.picoseconds)
    context = mm.Context(
        system, integrator, mm.Platform.getPlatformByName("CPU"), {"Threads": "2"}
    )
    context.setPositions(model.positions)
    (out / "positions.xml").write_text(
        mm.XmlSerializer.serialize(context.getState(getPositions=True))
    )
    atom_data = [
        {
            "index": a.index,
            "name": a.name,
            "element": a.element.symbol,
            "chain": a.residue.chain.id,
            "residue_id": a.residue.id,
            "residue": a.residue.name,
        }
        for a in solute_atoms
    ]
    write_json(out / "atoms.json", atom_data)
    ff_root = Path(app.__file__).parent / "data"
    write_json(
        out / "preparation.json",
        {
            "protocol_sha256": protocol["_sha256"],
            "source_sha256": sha(source),
            "modeled_residues": 87,
            "chain_residues": [29, 29, 29],
            "terminal_missing_residues_not_rebuilt": [30, 30, 30],
            "missing_atoms_added": added,
            "terminal_atoms_added": terminal,
            "hydrogens": "OpenMM Modeller pH7 standard termini",
            "crystal_waters": "removed; fresh explicit TIP3P solvent",
            "solute_atoms": len(solute_atoms),
            "total_atoms": system.getNumParticles(),
            "box_nm": box.tolist(),
            "forcefield_hashes": {
                name: sha(ff_root / name) for name in protocol["forcefield_files"]
            },
            "files": {
                name: sha(out / name)
                for name in (
                    "prepared.pdb",
                    "system.xml",
                    "positions.xml",
                    "atoms.json",
                )
            },
        },
    )
    print("Prepared", system.getNumParticles(), "atoms", flush=True)


def context_from(prepared, integrator, backend):
    system = mm.XmlSerializer.deserialize((prepared / "system.xml").read_text())
    props = (
        {"Threads": "2"}
        if backend == "CPU"
        else {"Precision": "mixed", "DeterministicForces": "true"}
        if backend == "CUDA"
        else {}
    )
    context = mm.Context(
        system, integrator, mm.Platform.getPlatformByName(backend), props
    )
    context.setState(
        mm.XmlSerializer.deserialize((prepared / "positions.xml").read_text())
    )
    return system, context


def controls(protocol, prepared, output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    integ = mm.VerletIntegrator(0.001 * u.picoseconds)
    system, ctx = context_from(prepared, integ, "CPU")
    initial = (
        ctx.getState(getEnergy=True)
        .getPotentialEnergy()
        .value_in_unit(u.kilojoule_per_mole)
    )
    mm.LocalEnergyMinimizer.minimize(
        ctx,
        10 * u.kilojoule_per_mole / u.nanometer,
        protocol["minimization_max_iterations"],
    )
    state = ctx.getState(getPositions=True, getEnergy=True, getForces=True)
    minimized = state.getPotentialEnergy().value_in_unit(u.kilojoule_per_mole)
    pos = np.array(state.getPositions(asNumpy=True).value_in_unit(u.nanometer))
    forces = np.array(
        state.getForces(asNumpy=True).value_in_unit(u.kilojoule_per_mole / u.nanometer)
    )
    # Select a nonzero force component from actual solute atoms for a meaningful
    # finite-difference gradient and a deliberately wrong-sign negative control.
    atom_count = len(json.loads((prepared / "atoms.json").read_text()))
    atom, axis = np.unravel_index(
        np.argmax(abs(forces[:atom_count])), forces[:atom_count].shape
    )
    eps = protocol["controls"]["finite_difference_nm"]
    energies = []
    for delta in (-eps, eps):
        q = pos.copy()
        q[atom, axis] += delta
        ctx.setPositions(q * u.nanometer)
        energies.append(
            ctx.getState(getEnergy=True)
            .getPotentialEnergy()
            .value_in_unit(u.kilojoule_per_mole)
        )
    numerical = -(energies[1] - energies[0]) / (2 * eps)
    analytic = float(forces[atom, axis])
    relative = abs(numerical - analytic) / max(abs(analytic), 1)
    wrong_sign = abs(numerical + analytic) / max(abs(analytic), 1)
    ctx.setPositions(pos * u.nanometer)
    ctx.setVelocitiesToTemperature(
        protocol["temperature_K"] * u.kelvin, protocol["seeds"][0]
    )
    velocities = ctx.getState(getVelocities=True).getVelocities()
    drifts = []
    endpoints = []
    del ctx, integ
    for dt in (0.001, 0.0005):
        integrator = mm.VerletIntegrator(dt * u.picoseconds)
        c = mm.Context(
            system, integrator, mm.Platform.getPlatformByName("CPU"), {"Threads": "2"}
        )
        c.setPositions(pos * u.nanometer)
        c.setVelocities(velocities)
        c.applyVelocityConstraints(1e-6)
        start = c.getState(getEnergy=True)
        e0 = (start.getPotentialEnergy() + start.getKineticEnergy()).value_in_unit(
            u.kilojoule_per_mole
        )
        kinetic = start.getKineticEnergy().value_in_unit(u.kilojoule_per_mole)
        integrator.step(round(protocol["controls"]["nve_duration_ps"] / dt))
        end = c.getState(getEnergy=True, getPositions=True)
        e1 = (end.getPotentialEnergy() + end.getKineticEnergy()).value_in_unit(
            u.kilojoule_per_mole
        )
        drift = abs(e1 - e0) / max(kinetic, 1)
        drifts.append(
            {
                "dt_ps": dt,
                "energy_drift_over_initial_kinetic": drift,
                "initial_total_kJ_mol": e0,
                "final_total_kJ_mol": e1,
            }
        )
        endpoints.append(
            np.asarray(end.getPositions(asNumpy=True).value_in_unit(u.nanometer))[
                :atom_count
            ]
        )
        del c, integrator
    passed = (
        all(np.isfinite([initial, minimized, relative, wrong_sign]))
        and minimized <= initial
        and relative < protocol["controls"]["gradient_relative_max"]
        and wrong_sign > 1
        and all(
            d["energy_drift_over_initial_kinetic"]
            < protocol["controls"]["nve_drift_over_kinetic_max"]
            for d in drifts
        )
    )
    report = {
        "schema": "frontier.molecular.controls/1",
        "protocol_sha256": protocol["_sha256"],
        "code_sha256": CODE_SHA256,
        "passed": bool(passed),
        "minimization": {
            "initial_kJ_mol": initial,
            "final_kJ_mol": minimized,
            "decreased": bool(minimized <= initial),
        },
        "force_gradient": {
            "atom": int(atom),
            "axis": int(axis),
            "analytic_kJ_mol_nm": analytic,
            "central_difference_kJ_mol_nm": numerical,
            "relative_error": relative,
            "wrong_sign_relative_error": wrong_sign,
        },
        "nve": drifts,
        "paired_timestep_solute_endpoint_rmsd_nm": rmsd_nm(*endpoints),
        "scope": "Numerical checks of this parameterized system; not experimental or fish-biological validation",
    }
    (out / "minimized-state.xml").write_text(mm.XmlSerializer.serialize(state))
    write_json(out / "controls.json", report)
    print(json.dumps(report), flush=True)
    if not passed:
        raise RuntimeError("Frozen numerical controls failed")


def simulate(protocol, prepared, output, backend, steps=None):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    atoms = json.loads((prepared / "atoms.json").read_text())
    heavy = [a["index"] for a in atoms if a["element"] != "H"]
    ca = [a["index"] for a in atoms if a["name"] == "CA"]
    dt = protocol["timestep_ps"]
    production_steps = steps or protocol["production_steps"]
    equil_steps = protocol["equilibration_steps"] if steps is None else min(100, steps)
    receipts = []
    for seed in protocol["seeds"] if steps is None else protocol["seeds"][:1]:
        started = time.perf_counter()
        integ = mm.LangevinMiddleIntegrator(
            protocol["temperature_K"] * u.kelvin,
            protocol["friction_per_ps"] / u.picosecond,
            dt * u.picoseconds,
        )
        integ.setRandomNumberSeed(seed)
        integ.setConstraintTolerance(1e-6)
        system, ctx = context_from(prepared, integ, backend)
        mm.LocalEnergyMinimizer.minimize(
            ctx,
            10 * u.kilojoule_per_mole / u.nanometer,
            protocol["minimization_max_iterations"],
        )
        ctx.setVelocitiesToTemperature(protocol["temperature_K"] * u.kelvin, seed)
        integ.step(equil_steps)
        initial = (
            ctx.getState(getPositions=True)
            .getPositions(asNumpy=True)
            .value_in_unit(u.nanometer)
        )
        frames = []
        metrics = []
        stride = max(1, production_steps // protocol["frames"])
        for step in range(0, production_steps + 1, stride):
            state = ctx.getState(getPositions=True, getEnergy=True)
            x = np.asarray(state.getPositions(asNumpy=True).value_in_unit(u.nanometer))
            energy = state.getPotentialEnergy().value_in_unit(u.kilojoule_per_mole)
            if not np.isfinite(x).all() or not np.isfinite(energy):
                raise RuntimeError("Nonfinite molecular state")
            ends = []
            for chain in ("A", "B", "C"):
                ids = [
                    a["index"]
                    for a in atoms
                    if a["chain"] == chain and a["name"] == "CA"
                ]
                ends.append(float(np.linalg.norm(x[ids[-1]] - x[ids[0]])))
            kinetic = state.getKineticEnergy().value_in_unit(u.kilojoule_per_mole)
            dof = 3 * system.getNumParticles() - system.getNumConstraints() - 3
            temperature = (
                2
                * kinetic
                / (
                    dof
                    * u.MOLAR_GAS_CONSTANT_R.value_in_unit(
                        u.kilojoule_per_mole / u.kelvin
                    )
                )
            )
            frames.append(x[heavy].copy())
            metrics.append(
                {
                    "time_ps": step * dt,
                    "potential_energy_kJ_mol": energy,
                    "kinetic_energy_kJ_mol": kinetic,
                    "kinetic_temperature_K": temperature,
                    "CA_RMSD_nm": rmsd_nm(x[ca], initial[ca]),
                    "chain_end_to_end_nm": ends,
                }
            )
            if step + stride <= production_steps:
                integ.step(stride)
        np.savez_compressed(
            out / f"trajectory-{seed}.npz",
            positions_nm=np.asarray(frames, dtype=np.float32),
            atom_indices=np.array(heavy),
            times_ps=np.array([m["time_ps"] for m in metrics]),
        )
        write_json(out / f"metrics-{seed}.json", metrics)
        (out / f"final-state-{seed}.xml").write_text(
            mm.XmlSerializer.serialize(
                ctx.getState(getPositions=True, getVelocities=True, getEnergy=True)
            )
        )
        receipts.append(
            {
                "seed": seed,
                "backend": ctx.getPlatform().getName(),
                "platform_properties": {
                    name: ctx.getPlatform().getPropertyValue(ctx, name)
                    for name in ctx.getPlatform().getPropertyNames()
                },
                "production_steps": production_steps,
                "equilibration_steps": equil_steps,
                "production_ps": production_steps * dt,
                "equilibration_ps": equil_steps * dt,
                "wall_seconds": time.perf_counter() - started,
                "final_CA_RMSD_nm": metrics[-1]["CA_RMSD_nm"],
                "frames": len(frames),
            }
        )
        del ctx, integ
    write_json(
        out / "receipt.json",
        {
            "schema": "frontier.molecular.run/1",
            "protocol_sha256": protocol["_sha256"],
            "openmm_version": mm.__version__,
            "numpy_version": np.__version__,
            "python": sys.version,
            "platform": platform.platform(),
            "code_sha256": CODE_SHA256,
            "preparation_sha256": sha(prepared / "preparation.json"),
            "runs": receipts,
            "simulation_kind": "computed atomistic classical molecular dynamics",
            "empirical_accuracy": "unknown",
            "cross_scale_transfer": "unknown: no conversion to tissue modulus or fin function",
            "files": {
                f.name: sha(f)
                for f in sorted(out.iterdir())
                if f.is_file() and f.name != "receipt.json"
            },
        },
    )
    print(json.dumps(receipts), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["prepare", "controls", "run", "preflight"])
    p.add_argument("--protocol", default="artifacts/molecular/protocol.json")
    p.add_argument("--prepared", default="artifacts/molecular/prepared")
    p.add_argument("--output", required=True)
    p.add_argument("--backend", choices=["CPU", "CUDA", "Reference"], default="CPU")
    p.add_argument("--steps", type=int)
    a = p.parse_args()
    protocol = json.loads(Path(a.protocol).read_text())
    protocol["_sha256"] = sha(a.protocol)
    if a.command == "prepare":
        prepare(protocol, a.output)
    elif a.command == "controls":
        controls(protocol, Path(a.prepared), a.output)
    elif a.command == "run":
        simulate(protocol, Path(a.prepared), a.output, a.backend, a.steps)
    else:
        prepared = Path(a.prepared)
        prep = json.loads((prepared / "preparation.json").read_text())
        for name, digest in prep["files"].items():
            if sha(prepared / name) != digest:
                raise ValueError("Prepared input hash mismatch: " + name)
        print(
            "preflight inputs verified",
            mm.__version__,
            [
                mm.Platform.getPlatform(i).getName()
                for i in range(mm.Platform.getNumPlatforms())
            ],
        )


if __name__ == "__main__":
    main()
