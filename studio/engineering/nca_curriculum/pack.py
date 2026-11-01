"""Bind independently committed evaluation to an isolated execution packet."""

import argparse
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import tarfile

import numpy as np

from engineering.nca_pattern.model import ROOT

ART = ROOT / "artifacts/nca-curriculum"
BASE = ROOT / "artifacts/nca-seed-placement"


def inputs():
    plan = json.loads((ART / "protocol.json").read_text())
    evaluation = json.loads((ART / "evaluation-manifest.json").read_text())
    runtime = json.loads((ART / "runtime-protocol-template.json").read_text())
    if (
        evaluation["protocol_sha256"]
        != sha256((ART / "protocol.json").read_bytes()).hexdigest()
        or evaluation["target_sha256"]
        != sha256((BASE / "target.npz").read_bytes()).hexdigest()
    ):
        raise ValueError("Independent plan/target pin changed")
    if (
        evaluation["mask_file_sha256"]
        != sha256((ART / "evaluation-masks.npz").read_bytes()).hexdigest()
    ):
        raise ValueError("Independent masks changed")
    if [x["id"] for x in evaluation["masks"]] != [
        x["id"] for x in plan["evaluation"]["mask_cases"]
    ]:
        raise ValueError("Case identities changed")
    if len(set(evaluation["update_seeds"])) != 3:
        raise ValueError("Distinct fresh update seeds required")
    forbidden = {7001, 7002, 7003} | {
        seed + offset
        for seed in plan["training"]["model_seeds"]
        for offset in [0, 11, 17, 113, 211]
    }
    if set(evaluation["update_seeds"]) & forbidden:
        raise ValueError("Evaluation seeds overlap previous/training seeds")
    masks = np.load(ART / "evaluation-masks.npz", allow_pickle=False)
    target = np.load(BASE / "target.npz", allow_pickle=False)["silhouette"]
    if set(masks.files) != {x["id"] for x in evaluation["masks"]} | {
        "all-erased-negative"
    }:
        raise ValueError("Mask count changed")
    for item in evaluation["masks"]:
        value = masks[item["id"]]
        if (
            value.shape != (64, 64)
            or value.dtype != np.bool_
            or sha256(value.tobytes()).hexdigest() != item["mask_array_sha256"]
        ):
            raise ValueError("Mask array identity changed")
        fraction = np.count_nonzero(value & target) / np.count_nonzero(target)
        if not 0.1 <= fraction <= 0.85 or fraction != item["target_erased_fraction"]:
            raise ValueError("Nonvacuity/fraction mismatch")
    if not masks["all-erased-negative"].all():
        raise ValueError("Absorbing-state mask changed")
    runtime["question"] = plan["question"]
    runtime["evaluation"]["update_seeds"] = evaluation["update_seeds"]
    runtime["evaluation"]["negative_all_erased"]["update_seed"] = evaluation[
        "update_seeds"
    ][0]
    runtime["evaluation"]["trace_update_seed"] = evaluation["update_seeds"][0]
    runtime["target"]["heldout_masks_sha256"] = evaluation["mask_file_sha256"]
    runtime["independent_evaluation_manifest_sha256"] = sha256(
        (ART / "evaluation-manifest.json").read_bytes()
    ).hexdigest()
    rp = ART / "runtime-protocol.json"
    rp.write_text(json.dumps(runtime, indent=2) + "\n")
    descriptor = json.loads((BASE / "target-manifest.json").read_text())
    descriptor["heldout_masks_sha256"] = evaluation["mask_file_sha256"]
    descriptor["curriculum_plan_sha256"] = runtime["curriculum_plan_sha256"]
    descriptor["independent_evaluation_manifest_sha256"] = runtime[
        "independent_evaluation_manifest_sha256"
    ]
    descriptor_path = ART / "runtime-target-manifest.json"
    descriptor_path.write_text(json.dumps(descriptor, indent=2) + "\n")
    sources = json.loads((ART / "execution-source-manifest.json").read_text())
    result = {}
    for item in sources["files"]:
        path = ART / "execution-source" / item["path"]
        if sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Adapted source changed")
        result[item["path"]] = path
    result.update(
        {
            "artifacts/nca-pattern/protocol.json": rp,
            "artifacts/nca-pattern/target.npz": BASE / "target.npz",
            "artifacts/nca-pattern/target-manifest.json": descriptor_path,
            "artifacts/nca-pattern/heldout-masks.npz": ART / "evaluation-masks.npz",
            "artifacts/nca-pattern/evaluation-manifest.json": ART
            / "evaluation-manifest.json",
            "artifacts/nca-pattern/curriculum-plan.json": ART / "protocol.json",
        }
    )
    return result


def run(directory=None):
    files = inputs()
    if directory:
        if directory.exists():
            raise ValueError("Fresh staging required")
        for name, source in files.items():
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        print("staged", len(files))
        return
    buf = io.BytesIO()
    refs = []
    with gzip.GzipFile(fileobj=buf, mode="wb", filename="", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w") as archive:
            for name, path in sorted(files.items()):
                raw = path.read_bytes()
                item = tarfile.TarInfo(name)
                item.size = len(raw)
                item.mode = 0o644
                archive.addfile(item, io.BytesIO(raw))
                refs.append(
                    {"path": name, "sha256": sha256(raw).hexdigest(), "bytes": len(raw)}
                )
    path = ART / "nca-curriculum-h100.tar.gz"
    path.write_bytes(buf.getvalue())
    plan = json.loads((ART / "protocol.json").read_text())
    manifest = {
        "schema": "frontier.nca.curriculum.packet/1",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "archive_path": str(path.relative_to(ROOT)),
        "archive_sha256": sha256(path.read_bytes()).hexdigest(),
        "archive_bytes": path.stat().st_size,
        "entry_argv": [
            "python",
            "-m",
            "engineering.nca_pattern.job",
            "--out",
            "output-curriculum",
        ],
        "environment": {
            "OMP_NUM_THREADS": "2",
            "OPENBLAS_NUM_THREADS": "2",
            "MKL_NUM_THREADS": "2",
            "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
        },
        "resources": plan["resources"],
        "files": refs,
        "evaluation_commit": "f5db91a",
        "cpu_preflight_sha256": sha256(
            (ART / "cpu-preflight.json").read_bytes()
        ).hexdigest(),
        "evaluation_manifest_sha256": sha256(
            (ART / "evaluation-manifest.json").read_bytes()
        ).hexdigest(),
        "scope": "Independent committed evaluation plus actual checkpoint-barrier readguard, not cryptographic secrecy.8models/4pairedreplicateunits;192dependentdesignprobes+8negatives; computationalpattern only.",
    }
    (ART / "packet.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        {k: manifest[k] for k in ["archive_sha256", "archive_bytes", "source_commit"]}
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path)
    args = parser.parse_args()
    run(args.stage)
