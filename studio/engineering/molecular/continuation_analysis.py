"""Audit and plot actual conditional extensions without claiming independent samples."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .continuation import small_window_drift
from .run import sha, write_json


def analyze(extension, parent, protocol_path, output):
    extension = Path(extension)
    parent = Path(parent)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    protocol = json.loads(Path(protocol_path).read_text())
    receipt = json.loads((extension / "receipt.json").read_text())
    if receipt["protocol_sha256"] != sha(protocol_path):
        raise ValueError("Extension protocol identity mismatch")
    for name, digest in receipt["files"].items():
        if sha(extension / name) != digest:
            raise ValueError("Extension file hash mismatch: " + name)
    if len(receipt["runs"]) != len(protocol["branches"]):
        raise ValueError("Missing declared conditional branches")
    parent_receipt = json.loads((parent / "receipt.json").read_text())
    for name, digest in parent_receipt["files"].items():
        if sha(parent / name) != digest:
            raise ValueError("Parent file hash mismatch: " + name)
    atoms = json.loads((parent.parent / "prepared/atoms.json").read_text())
    ca_indices = [a["index"] for a in atoms if a["name"] == "CA"]
    summaries = []
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 7.5), dpi=120)
    for run in receipt["runs"]:
        seed = run["seed"]
        origin = run["parent_seed"]
        source = next(b for b in protocol["branches"] if b["source_seed"] == origin)
        if run["parent_state_sha256"] != source["state_sha256"]:
            raise ValueError("Conditional parent-state mismatch")
        m = json.loads((extension / f"metrics-{seed}.json").read_text())
        previous = json.loads((parent / f"metrics-{origin}.json").read_text())
        data = np.load(extension / f"trajectory-{seed}.npz")
        old = np.load(parent / f"trajectory-{origin}.npz")
        if not np.array_equal(data["atom_indices"], old["atom_indices"]):
            raise ValueError("Atom identity ordering changed")
        continuity = float(
            np.max(
                abs(
                    data["positions_nm"][0].astype(float)
                    - old["positions_nm"][-1].astype(float)
                )
            )
        )
        lookup = {int(v): i for i, v in enumerate(old["atom_indices"])}
        coords = old["positions_nm"][:, [lookup[i] for i in ca_indices]].astype(float)
        center = coords - coords.mean(1, keepdims=True)
        old_rg = np.sqrt(np.mean(np.sum(center**2, axis=2), axis=1))
        diagnostic = small_window_drift(m, protocol)
        if diagnostic != run["predeclared_diagnostic"]:
            raise ValueError(
                "Saved finite-window diagnostic differs from recomputation"
            )
        global_t = np.array(
            [v["time_ps"] for v in previous]
            + [v["global_production_time_ps"] for v in m[1:]]
        )
        rmsd = [v["CA_RMSD_nm"] for v in previous] + [
            v["CA_RMSD_from_original_production_start_nm"] for v in m[1:]
        ]
        rg = np.r_[old_rg, [v["CA_geometric_Rg_nm"] for v in m[1:]]]
        temp = [v["kinetic_temperature_K"] for v in previous] + [
            v["kinetic_temperature_K"] for v in m[1:]
        ]
        energy = [v["potential_energy_kJ_mol"] for v in previous] + [
            v["potential_energy_kJ_mol"] for v in m[1:]
        ]
        label = f"{origin} → {seed}"
        for axis, values in zip(axes.flat, (rmsd, rg, temp, energy)):
            axis.plot(global_t, values, label=label)
        summaries.append(
            {
                "parent_seed": origin,
                "new_thermostat_seed": seed,
                "parent_state_sha256": run["parent_state_sha256"],
                "frame0_vs_parent_final_saved_float32_max_abs_nm": continuity,
                "global_production_end_ps": float(global_t[-1]),
                "final_original_reference_CA_RMSD_nm": m[-1][
                    "CA_RMSD_from_original_production_start_nm"
                ],
                "final_CA_geometric_Rg_nm": m[-1]["CA_geometric_Rg_nm"],
                "predeclared_diagnostic": diagnostic,
                "shared_parent_and_Hamiltonian": True,
            }
        )
    for axis, title, ylabel in zip(
        axes.flat,
        (
            "Cα RMSD from original production start",
            "Geometric Cα radius of gyration",
            "Actual kinetic temperature",
            "Parameterized potential energy",
        ),
        ("nm", "nm", "K", "kJ/mol"),
    ):
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.set_xlabel("Global production time (ps)")
        axis.axvline(100, color="black", ls="--", lw=0.8)
        axis.axvspan(600, 800, color="#abc5e5", alpha=0.16)
        axis.axvspan(800, 1000, color="#e6c99e", alpha=0.16)
        axis.legend(fontsize=8)
        axis.grid(alpha=0.18)
    axes[1, 0].axhline(300, color="gray", lw=0.8)
    fig.suptitle(
        "Three conditional molecular branches · recorded-state restart at100ps",
        fontsize=14,
    )
    fig.text(
        0.025,
        0.015,
        "New thermostat streams; parents + extensions are3branches, not6independent samples. Small finite-window drift does not prove equilibrium.",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(out / "conditional-branches.png")
    plt.close(fig)
    report = {
        "schema": "frontier.molecular.conditional-analysis/1",
        "protocol_sha256": sha(protocol_path),
        "extension_receipt_sha256": sha(extension / "receipt.json"),
        "parent_receipt_sha256": sha(parent / "receipt.json"),
        "analysis_code_sha256": sha(__file__),
        "n_parent_branches": len(summaries),
        "n_new_independent_biological_samples": 0,
        "branches": summaries,
        "small_window_drift_diagnostic_count": sum(
            s["predeclared_diagnostic"]["small_window_drift"] for s in summaries
        ),
        "diagnostic_denominator": len(summaries),
        "scope": "Descriptive predeclared window diagnostic only; no equilibrium, folding stability, material modulus or biological-success probability. Original reference uses savedfloat32 parent-start coordinates.",
        "empirical_accuracy": "unknown",
        "biological_success_probability": None,
    }
    write_json(out / "summary.json", report)
    write_json(
        out / "provenance.json",
        {
            "analysis_code_sha256": sha(__file__),
            "inputs": {
                "protocol": sha(protocol_path),
                "parent_receipt": sha(parent / "receipt.json"),
                "extension_receipt": sha(extension / "receipt.json"),
            },
            "outputs": {
                f.name: sha(f) for f in out.iterdir() if f.name != "provenance.json"
            },
        },
    )
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("extension")
    p.add_argument("--parent", default="artifacts/molecular/cuda-v2/production")
    p.add_argument(
        "--protocol", default="artifacts/molecular/continuation-protocol.json"
    )
    p.add_argument("--output", required=True)
    a = p.parse_args()
    analyze(a.extension, a.parent, a.protocol, a.output)
