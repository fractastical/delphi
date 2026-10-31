"""Require an actual CUDA platform, same-system CPU checks, then short MD.

No automatic CPU fallback. Launch only through the authorized compute owner.
PREFLIGHT=1 verifies the frozen input and imports without preparing or integrating.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

import numpy as np
import openmm as mm
from openmm import unit as u
from .run import controls, context_from, prepare, sha, simulate, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    protocol_path = Path("artifacts/molecular/protocol.json")
    protocol = json.loads(protocol_path.read_text())
    protocol["_sha256"] = sha(protocol_path)
    if sha(protocol["source_path"]) != protocol["source_sha256"]:
        raise ValueError("PDB source mismatch")
    if os.environ.get("PREFLIGHT"):
        print("MD preflight input/import checks passed", mm.__version__, flush=True)
        return
    start = time.perf_counter()
    # A CPU wheel or unloaded CUDA plugin must refuse, never masquerade as GPU MD.
    backend = mm.Platform.getPlatformByName("CUDA")
    prepared = out / "prepared"
    prepare(protocol, prepared)
    controls(protocol, prepared, out / "cpu-controls")
    observations = []
    for name in ("CPU", "CUDA"):
        integrator = mm.VerletIntegrator(0.001 * u.picoseconds)
        _, ctx = context_from(prepared, integrator, name)
        state = ctx.getState(getEnergy=True, getForces=True)
        observations.append(
            (
                state.getPotentialEnergy().value_in_unit(u.kilojoule_per_mole),
                np.asarray(
                    state.getForces(asNumpy=True).value_in_unit(
                        u.kilojoule_per_mole / u.nanometer
                    )
                ),
            )
        )
        del ctx, integrator
    energy_error_per_atom = abs(observations[0][0] - observations[1][0]) / len(
        observations[0][1]
    )
    force_error = float(
        np.linalg.norm(observations[0][1] - observations[1][1])
        / max(np.linalg.norm(observations[0][1]), 1)
    )
    parity = {
        "same_prepared_system_sha256": sha(prepared / "system.xml"),
        "same_prepared_positions_sha256": sha(prepared / "positions.xml"),
        "energy_abs_difference_kJ_mol_per_atom": energy_error_per_atom,
        "force_relative_L2_difference": force_error,
        "frozen_limits": {"energy_per_atom_max": 0.01, "force_relative_L2_max": 0.002},
        "passed": bool(energy_error_per_atom < 0.01 and force_error < 0.002),
    }
    write_json(out / "cpu-cuda-parity.json", parity)
    if not parity["passed"]:
        raise RuntimeError("CPU/CUDA numerical parity failed")
    simulate(protocol, prepared, out / "production", backend.getName())
    # Retain exact prepared inputs for reproduction without inflating plain XML output.
    with tarfile.open(out / "prepared-inputs.tar.gz", "w:gz") as archive:
        for f in sorted(prepared.iterdir()):
            archive.add(f, arcname=f.name)
    hardware = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    versions = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    (out / "environment.txt").write_text(versions)
    write_json(
        out / "job-receipt.json",
        {
            "protocol_sha256": sha(protocol_path),
            "remote_code_sha256": sha(__file__),
            "CUDA_required": True,
            "GPU": hardware,
            "wall_seconds": time.perf_counter() - start,
            "files": {
                str(f.relative_to(out)): sha(f)
                for f in out.rglob("*")
                if f.is_file() and f.name != "job-receipt.json"
            },
        },
    )
    print("MD CUDA production completed", hardware, flush=True)


if __name__ == "__main__":
    main()
