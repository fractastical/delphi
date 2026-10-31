"""Native typed molecular ports and an explicit refused molecular-to-fin bridge."""

import json
from pathlib import Path

from engineering.coupling import (
    Coupling,
    ModelSpec,
    Port,
    Provenance,
    Timescale,
    build_manifest,
    default_registry,
    dim,
    model_to_json,
    tree_sha256,
)
from .run import sha

ROOT = Path(__file__).resolve().parents[2]


def molecular_model():
    paths = [
        "artifacts/molecular/protocol.json",
        "artifacts/molecular/cpu-trajectory-final/producer-run.py",
    ]
    files = {name: sha(ROOT / name) for name in paths}
    scope = "Synthetic 1K6F modeled collagen-mimetic trimer;87residues;ff14SB/TIP3P;CPU setup trajectory only"
    provenance = Provenance(
        "Actual saved OpenMM CPU trajectory metrics and exact source snapshot",
        "simulated",
        "file",
    )
    ports = tuple(
        Port(
            name,
            "out",
            quantity,
            "dimensional",
            "nm",
            dim(m=1),
            "molecular",
            "300K target;0.1ps preliminary thermalization +0.2ps production;no equilibrium claim",
            scope,
            provenance,
            None,
            caveat,
        )
        for name, quantity, caveat in [
            (
                "terminal_CA_distance",
                "molecular chain terminal separation",
                "Three actual chain lengths, not a contour length or material modulus",
            ),
            (
                "CA_RMSD",
                "C-alpha least-squares RMSD from production start",
                "Rigid aligned; not an experimental accuracy measure",
            ),
        ]
    )
    return ModelSpec(
        "collagen_mimetic_md",
        "Collagen-mimetic atomistic MD (computed)",
        "OpenMM8.4 CPU",
        "implemented",
        {
            "repo": "kganjam/delphi-frontier",
            "branch": "work/multiscale-md",
            "commit": "5a4b6fa",
            "path": ",".join(paths),
            "files": files,
            "source_sha256": tree_sha256(files),
        },
        ports,
        Timescale(
            "unknown",
            None,
            "0.2ps trajectory duration is not a physical relaxation-time estimate",
        ),
        scope,
        (
            "native fish collagen sequence",
            "equilibrated conformational ensemble",
            "force-field empirical accuracy",
            "molecular stiffness",
            "fibril assembly/crosslinking",
            "tissue Young modulus",
            "fin bending stiffness",
            "fish function",
        ),
        {
            "receipt": "artifacts/molecular/cpu-trajectory-final/receipt.json",
            "protocol": "artifacts/molecular/protocol.json",
            "controls": "artifacts/molecular/cpu-controls/controls.json",
            "measured_biological_data": None,
        },
    )


def main():
    model = molecular_model()
    registry = default_registry()
    registry.add_model(model)
    bridge = Coupling(
        "molecular_length_to_fin_EI",
        "collagen_mimetic_md.terminal_CA_distance",
        "finbeam_euler_bernoulli.flexural_rigidity",
        mapping_kind="none",
        time_relation="unknown",
        uncertainty_kind="unknown",
        note="Missing molecular-to-fibril-to-tissue constitutive law, morphology, volume fraction and crosslink calibration. A short molecular length trajectory cannot set fin EI.",
    )
    out = ROOT / "artifacts/molecular"
    (out / "model-interface.json").write_text(
        json.dumps(model_to_json(model), indent=2) + "\n"
    )
    (out / "cross-scale-gate.json").write_text(
        json.dumps(build_manifest(registry, [bridge]), indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
