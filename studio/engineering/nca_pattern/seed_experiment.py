"""Build a separate seed-only experiment with byte-identical original solvers."""

import argparse
import copy
import gzip
from hashlib import sha256
import io
import json
import subprocess
from pathlib import Path
import tarfile

import numpy as np

from .model import ART, ROOT, dump

VARIANT = ROOT / "artifacts/nca-seed-placement"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def nearest_foreground(silhouette, xy):
    points = np.argwhere(silhouette)
    if not len(points):
        raise ValueError("Empty target cannot define a seed")
    distance = ((points - np.asarray(xy)[::-1]) ** 2).sum(axis=1)
    # np.argwhere is row-major: deterministic y,x tie order.
    return points[int(np.argmin(distance))][::-1].tolist()


def array_ref(array):
    return {
        "sha256": sha256(array.tobytes()).hexdigest(),
        "shape": list(array.shape),
        "dtype": str(array.dtype),
    }


def prepare():
    old = dict(np.load(ART / "target.npz", allow_pickle=False))
    if old["seed_xy"].tolist() != [8, 42]:
        raise ValueError("Unexpected original seed")
    new = {key: value.copy() for key, value in old.items()}
    new["seed_xy"] = np.asarray(
        nearest_foreground(old["silhouette"], old["seed_xy"]),
        dtype=old["seed_xy"].dtype,
    )
    if new["seed_xy"].tolist() != [7, 41]:
        raise ValueError("Proposed exact nearest-target identity unresolved")
    VARIANT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(VARIANT / "target.npz", **new)
    cfg = json.loads((ART / "protocol.json").read_text())
    followup = copy.deepcopy(cfg)
    followup["target"]["sha256"] = digest(VARIANT / "target.npz")
    followup["training"]["seed"] = (
        "one computational pixel at nearest foregroundxy[7,41] to original projected root[8,42]; RGB0,alpha+hidden1; sole scientific input change"
    )
    followup["seed_placement_follow_up"] = {
        "parent_receipt_sha256": digest(ART / "run-original/job-receipt.json"),
        "parent_design_result": "0of48 design predicates;4of4 empty-state negatives passed",
        "question": "Does changing only seed placement prevent the observed absorbing-empty optimization failure? No guaranteed success or causal conclusion from the parent alone.",
        "original_seed_xy": [8, 42],
        "new_seed_xy": [7, 41],
        "evaluation_status": "Same previously evaluated cases reused for controlled comparison; not a fresh untouched holdout or new-target test.",
    }
    dump(VARIANT / "protocol.json", followup)
    meta = json.loads((ART / "target-manifest.json").read_text())
    meta["projection"]["seed_xy"] = [7, 41]
    meta["target_sha256"] = digest(VARIANT / "target.npz")
    meta["seed_placement_builder_sha256"] = digest(Path(__file__))
    meta["parent_target_sha256"] = digest(ART / "target.npz")
    dump(VARIANT / "target-manifest.json", meta)
    original = json.loads((ART / "packet.json").read_text())
    for item in original["files"]:
        if digest(ROOT / item["path"]) != item["sha256"]:
            raise ValueError("Original frozen packet member changed")
    declaration = {
        "schema": "frontier.nca.one-factor-seed-protocol/1",
        "status": "Frozen before any follow-up training or evaluation",
        "parent_source_commit": subprocess.check_output(
            ["git", "rev-parse", "9b20492"], cwd=ROOT, text=True
        ).strip(),
        "parent_receipt": {
            "path": str((ART / "run-original/job-receipt.json").relative_to(ROOT)),
            "sha256": digest(ART / "run-original/job-receipt.json"),
        },
        "parent_protocol_sha256": digest(ART / "protocol.json"),
        "follow_up_runtime_protocol_sha256": digest(VARIANT / "protocol.json"),
        "sole_scientific_change": {
            "input": "seed_xy in target NPZ",
            "from": [8, 42],
            "to": [7, 41],
            "selection": "minimum squared Euclidean pixel distance to target silhouette, row-major y,x ties",
        },
        "invariants": {
            "source_files_byte_identical": [
                x for x in original["files"] if x["path"].startswith("engineering/")
            ],
            "target_arrays": {
                k: array_ref(v) for k, v in old.items() if k != "seed_xy"
            },
            "heldout_mask_sha256": digest(ART / "heldout-masks.npz"),
            "training_and_evaluation": "All4original models, same initialization/pool/fire/damage seeds,2000steps,52evaluations,48design+4negatives,original thresholds and deadlines. No loss,rule,optimizer,damage,checkpoint selection or budget change.",
        },
        "target_npz_sha256": digest(VARIANT / "target.npz"),
        "evaluation_scope": "Previously seen evaluation scenarios reused for a one-factor comparison, not fresh heldouts or biological validation.",
        "partial_policy": "Keep all failure/incomplete cases; no retry, threshold relaxation or replacement of parent results.",
        "resources": original["resources"],
        "builder_sha256": digest(Path(__file__)),
    }
    dump(VARIANT / "one-factor-protocol.json", declaration)
    validate()


def validate():
    parent = dict(np.load(ART / "target.npz", allow_pickle=False))
    variant = dict(np.load(VARIANT / "target.npz", allow_pickle=False))
    if set(parent) != set(variant):
        raise ValueError("Target fields changed")
    if any(not np.array_equal(parent[k], variant[k]) for k in parent if k != "seed_xy"):
        raise ValueError("A scientific target array changed beyond seed placement")
    if variant["seed_xy"].tolist() != [7, 41]:
        raise ValueError("Seed changed from frozen proposal")
    cfg = json.loads((ART / "protocol.json").read_text())
    vcfg = json.loads((VARIANT / "protocol.json").read_text())
    restored = copy.deepcopy(vcfg)
    restored["target"]["sha256"] = cfg["target"]["sha256"]
    restored["training"]["seed"] = cfg["training"]["seed"]
    restored.pop("seed_placement_follow_up")
    if restored != cfg:
        raise ValueError("Protocol changed beyond seed identity/provenance")
    if digest(VARIANT / "target.npz") != vcfg["target"]["sha256"]:
        raise ValueError("Follow-up target pin changed")
    return True


def members():
    validate()
    original = json.loads((ART / "packet.json").read_text())
    result = {}
    for item in original["files"]:
        name = item["path"]
        if name.startswith("engineering/") and digest(ROOT / name) != item["sha256"]:
            raise ValueError("Original source changed")
        replacement = VARIANT / Path(name).name
        result[name] = replacement if replacement.exists() else ROOT / name
    result["artifacts/nca-pattern/one-factor-protocol.json"] = (
        VARIANT / "one-factor-protocol.json"
    )
    return result


def stage(directory):
    if directory.exists():
        raise ValueError("Fresh staging tree required")
    for name, source in members().items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source.read_bytes())


def pack():
    data = io.BytesIO()
    files = []
    with gzip.GzipFile(fileobj=data, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for name, source in sorted(members().items()):
                raw = source.read_bytes()
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(raw))
                files.append(
                    {"path": name, "sha256": sha256(raw).hexdigest(), "bytes": len(raw)}
                )
    path = VARIANT / "nca-seed-placement-h100.tar.gz"
    path.write_bytes(data.getvalue())
    parent = json.loads((ART / "packet.json").read_text())
    manifest = {
        k: copy.deepcopy(parent[k])
        for k in [
            "image",
            "environment",
            "dependency_policy",
            "resources",
            "same_job_gates",
            "outputs",
            "partial_policy",
            "scientific_scope",
        ]
    }
    manifest.update(
        schema="frontier.nca.seed-placement-packet/1",
        archive_path=str(path.relative_to(ROOT)),
        archive_sha256=digest(path),
        archive_bytes=path.stat().st_size,
        entry_argv=[
            "python",
            "-m",
            "engineering.nca_pattern.job",
            "--out",
            "output-seed-placement",
        ],
        files=files,
        staging_note="Variant input files map into an isolated original-layout tree; original repository artifacts/source are not overwritten",
        one_factor_protocol_sha256=digest(VARIANT / "one-factor-protocol.json"),
    )
    dump(VARIANT / "packet.json", manifest)
    print(
        {
            "archive": str(path),
            "sha256": digest(path),
            "bytes": path.stat().st_size,
            "members": len(files),
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["prepare", "pack", "stage", "validate"])
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    if args.operation == "stage":
        if args.directory is None:
            parser.error("stage requires --directory")
        stage(args.directory)
    else:
        globals()[args.operation]()
