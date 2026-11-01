"""Build a self-contained, source-hashed CPU packet; never provision compute."""

import gzip
from hashlib import sha256
import io
import subprocess
import tarfile

from .model import ART, ROOT, dump, protocol


def run():
    source = [
        ROOT / "engineering/aeroelastic" / name
        for name in [
            "__init__.py",
            "model.py",
            "flight.py",
            "controls.py",
            "run.py",
            "requirements.txt",
        ]
    ]
    source += [
        ROOT / name
        for name in [
            "engineering/fin_mechanics/__init__.py",
            "engineering/fin_mechanics/beam.py",
            "engineering/cfd3d/vlm.py",
            "engineering/cfd3d/gates_vlm.json",
            "engineering/simulation/__init__.py",
            "engineering/simulation/glide.py",
            "engineering/simulation/schema.py",
        ]
    ]
    source += [ROOT / item["path"] for item in protocol()["inputs"]]
    source += [ART / "protocol.json", ART / "controls-local.json"]
    payload = io.BytesIO()
    files = []
    with gzip.GzipFile(fileobj=payload, mode="wb", filename="", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w") as archive:
            for path in sorted(source):
                raw = path.read_bytes()
                name = str(path.relative_to(ROOT))
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(raw))
                files.append(
                    {"path": name, "sha256": sha256(raw).hexdigest(), "bytes": len(raw)}
                )
    out = ART / "aeroelastic-cpu-packet.tar.gz"
    out.write_bytes(payload.getvalue())
    manifest = {
        "schema": "frontier.aeroelastic.cpu-packet/1",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "archive_path": str(out.relative_to(ROOT)),
        "archive_sha256": sha256(out.read_bytes()).hexdigest(),
        "archive_bytes": out.stat().st_size,
        "entry_argv": [
            "python",
            "-m",
            "engineering.aeroelastic.run",
            "--out",
            "output",
        ],
        "requirements": "engineering/aeroelastic/requirements.txt",
        "environment": {
            "OMP_NUM_THREADS": "2",
            "OPENBLAS_NUM_THREADS": "2",
            "MKL_NUM_THREADS": "2",
        },
        "resources": protocol()["resources"],
        "files": files,
        "scope": "Static equivalent-scaffold aeroelastic comparison, paired ablation/refinement and explicitly rigidized-shape glide; not tissue calibration or continuousFSI",
        "outputs": [
            "output/controls.json",
            "output/<36declaredarms>/{result.json,static-states.npz,glide-main.npz,glide-half.npz} as applicable",
            "output/summary.json",
            "output/receipt.json",
            "failure/partial artifacts retained",
        ],
        "input_network_required": False,
        "no_credentials_or_model_inference": True,
    }
    dump(ART / "packet.json", manifest)
    print(
        {k: manifest[k] for k in ["source_commit", "archive_sha256", "archive_bytes"]}
    )


if __name__ == "__main__":
    run()
