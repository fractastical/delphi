"""Diagnose derivative measurement precision on an exact saved molecular state.

This reports discrepancies; it never changes an acceptance threshold or runs a
production trajectory. CPU and Reference evaluate the same serialized Hamiltonian.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import openmm as mm
from openmm import unit as u

from .run import sha, write_json


def diagnose(prepared, state_path, output, component=None):
    system = mm.XmlSerializer.deserialize((prepared / "system.xml").read_text())
    state = mm.XmlSerializer.deserialize(state_path.read_text())
    positions = np.asarray(state.getPositions(asNumpy=True).value_in_unit(u.nanometer))
    solute_atoms = len(json.loads((prepared / "atoms.json").read_text()))
    observations = {}
    force_arrays = {}
    for backend in ("CPU", "Reference"):
        integrator = mm.VerletIntegrator(0.001 * u.picoseconds)
        properties = {"Threads": "1"} if backend == "CPU" else {}
        context = mm.Context(
            system, integrator, mm.Platform.getPlatformByName(backend), properties
        )
        context.setState(state)
        forces = np.asarray(
            context.getState(getForces=True)
            .getForces(asNumpy=True)
            .value_in_unit(u.kilojoule_per_mole / u.nanometer)
        )
        if component is None:
            atom, axis = np.unravel_index(
                np.argmax(abs(forces[:solute_atoms])), forces[:solute_atoms].shape
            )
            component = (int(atom), int(axis))
        atom, axis = component
        analytic = float(forces[atom, axis])
        scan = []
        for h in (1e-6, 1e-5, 1e-4, 1e-3):
            energies = []
            for delta in (-h, h):
                q = positions.copy()
                q[atom, axis] += delta
                context.setPositions(q * u.nanometer)
                energies.append(
                    context.getState(getEnergy=True)
                    .getPotentialEnergy()
                    .value_in_unit(u.kilojoule_per_mole)
                )
            finite = -(energies[1] - energies[0]) / (2 * h)
            scan.append(
                {
                    "h_nm": h,
                    "finite_difference_kJ_mol_nm": finite,
                    "analytic_kJ_mol_nm": analytic,
                    "relative_error": abs(finite - analytic) / max(abs(analytic), 1),
                    "energies_kJ_mol": energies,
                }
            )
        observations[backend] = {"atom": atom, "axis": axis, "gradient_scan": scan}
        force_arrays[backend] = forces
        del context, integrator
    cpu = force_arrays["CPU"]
    reference = force_arrays["Reference"]
    report = {
        "schema": "frontier.molecular.derivative-diagnosis/1",
        "system_sha256": sha(prepared / "system.xml"),
        "state_sha256": sha(state_path),
        "code_sha256": sha(__file__),
        "component": list(component),
        "observations": observations,
        "CPU_Reference_force_relative_L2": float(
            np.linalg.norm(cpu - reference) / np.linalg.norm(reference)
        ),
        "CPU_force_vs_Reference_derivative_at_frozen_h_relative_error": abs(
            float(cpu[component])
            - observations["Reference"]["gradient_scan"][1][
                "finite_difference_kJ_mol_nm"
            ]
        )
        / max(abs(float(cpu[component])), 1),
        "scope": "Measurement precision diagnosis; original failed gate remains failed. No acceptance bounds changed.",
    }
    write_json(output, report)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--prepared", default="artifacts/molecular/prepared")
    p.add_argument(
        "--state", default="artifacts/molecular/cpu-controls/minimized-state.xml"
    )
    p.add_argument("--output", required=True)
    p.add_argument("--atom", type=int)
    p.add_argument("--axis", type=int)
    a = p.parse_args()
    diagnose(
        Path(a.prepared),
        Path(a.state),
        a.output,
        None if a.atom is None else (a.atom, a.axis),
    )
