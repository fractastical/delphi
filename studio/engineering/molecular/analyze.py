"""Descriptive actual-state MD seed variation, not biological confidence."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def analyze(production, output):
    production = Path(production)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    receipt_path = production / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    for name, digest in receipt["files"].items():
        if sha(production / name) != digest:
            raise ValueError("Simulation artifact hash mismatch: " + name)
    summaries = []
    curves = []
    for run in receipt["runs"]:
        seed = run["seed"]
        path = production / f"metrics-{seed}.json"
        metrics = json.loads(path.read_text())
        trajectory = np.load(production / f"trajectory-{seed}.npz")
        times = np.array([m["time_ps"] for m in metrics])
        temp = np.array([m["kinetic_temperature_K"] for m in metrics])
        rmsd = np.array([m["CA_RMSD_nm"] for m in metrics])
        lengths = np.array([m["chain_end_to_end_nm"] for m in metrics])
        if not np.isfinite(trajectory["positions_nm"]).all() or not np.allclose(
            times, trajectory["times_ps"], rtol=0, atol=1e-12
        ):
            raise ValueError("Invalid actual trajectory states/times")
        if not np.isfinite(np.column_stack([times, temp, rmsd, lengths])).all():
            raise ValueError("Nonfinite actual metrics")
        tail = temp[int(len(temp) * 0.8) :]
        summaries.append(
            {
                "seed": seed,
                "backend": run["backend"],
                "production_ps": run["production_ps"],
                "preliminary_thermalization_ps": run["equilibration_ps"],
                "frames": len(times),
                "metrics_sha256": sha(path),
                "trajectory_sha256": sha(production / f"trajectory-{seed}.npz"),
                "final_CA_RMSD_from_production_start_nm": float(rmsd[-1]),
                "final_chain_terminal_distances_nm": lengths[-1].tolist(),
                "kinetic_temperature_range_K": [float(temp.min()), float(temp.max())],
                "last_20_percent_sampled_temperature_mean_K": float(tail.mean()),
                "last_20_percent_sampled_temperature_SD_K": float(tail.std(ddof=1))
                if len(tail) > 1
                else None,
            }
        )
        curves.append((run, metrics))
    endpoint = np.array(
        [s["final_CA_RMSD_from_production_start_nm"] for s in summaries]
    )
    report = {
        "schema": "frontier.molecular.ensemble-analysis/1",
        "simulation_receipt_sha256": sha(receipt_path),
        "analysis_code_sha256": sha(__file__),
        "runs": summaries,
        "descriptive_endpoint_CA_RMSD_nm": {
            "mean": float(endpoint.mean()),
            "sample_SD": float(endpoint.std(ddof=1)) if len(endpoint) > 1 else None,
            "minimum": float(endpoint.min()),
            "maximum": float(endpoint.max()),
            "n_runs": len(endpoint),
        },
        "shared_input_groups": [
            "one_1K6F_structure",
            "one_prepared_solvent_system",
            "one_ff14SB_TIP3P_Hamiltonian",
            "one_assumed_300K_0.1M_condition",
        ],
        "scope": "Descriptive variation over declared velocity/thermostat seeds; not a confidence interval for biological function, equilibrium or force-field accuracy. RMSD is from each run production start, not held-out experiment.",
        "biological_success_probability": None,
        "empirical_accuracy": "unknown",
        "equilibrated_ensemble": "not established",
        "tissue_material_modulus": None,
    }
    (out / "ensemble.json").write_text(json.dumps(report, indent=2) + "\n")
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), dpi=120)
    for run, metrics in curves:
        t = [m["time_ps"] for m in metrics]
        label = "seed " + str(run["seed"])
        axes[0, 0].plot(t, [m["CA_RMSD_nm"] for m in metrics], label=label)
        axes[0, 1].plot(t, [m["kinetic_temperature_K"] for m in metrics], label=label)
        axes[1, 0].plot(
            t, [np.mean(m["chain_end_to_end_nm"]) for m in metrics], label=label
        )
        axes[1, 1].plot(t, [m["potential_energy_kJ_mol"] for m in metrics], label=label)
    for axis, title, ylabel in zip(
        axes.flat,
        [
            "Aligned Cα change from own production start",
            "Actual kinetic temperature",
            "Mean of three chain terminal separations",
            "Parameterized potential energy",
        ],
        ["RMSD (nm)", "K", "nm", "kJ/mol"],
    ):
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.set_xlabel("Production time (ps)")
        axis.legend(fontsize=8)
        axis.grid(alpha=0.2)
    axes[0, 1].axhline(300, ls="--", color="black", lw=0.8)
    fig.suptitle(
        "Actual collagen-mimetic MD seeds · shared structure and force field",
        fontsize=14,
    )
    fig.text(
        0.03,
        0.015,
        "Computed states; seed spread does not measure biological success, force-field accuracy, or tissue mechanics.",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(out / "ensemble.png")
    plt.close(fig)
    (out / "analysis-provenance.json").write_text(
        json.dumps(
            {
                "analysis_code_sha256": sha(__file__),
                "simulation_receipt_sha256": sha(receipt_path),
                "outputs": {
                    f.name: sha(f)
                    for f in out.iterdir()
                    if f.name != "analysis-provenance.json"
                },
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("production")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    analyze(a.production, a.output)
