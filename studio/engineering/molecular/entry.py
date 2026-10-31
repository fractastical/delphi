"""Compute-controller entry: verify/extract frozen packet, install pinned runtime, execute."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile


def main():
    archive = Path("inputs/molecular/portable-md.tar.xz")
    manifest = json.loads(Path("inputs/molecular/portable-md.json").read_text())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
        raise ValueError("MD packet hash mismatch")
    destination = Path(os.environ.get("COPS_OUT", ".")) / "md-work"
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if member.name not in manifest["files"] or not member.isfile():
                raise ValueError("Unexpected packet path")
        tar.extractall(destination, filter="data")
    for name, digest in manifest["files"].items():
        if hashlib.sha256((destination / name).read_bytes()).hexdigest() != digest:
            raise ValueError("MD file hash mismatch: " + name)
    if os.environ.get("PREFLIGHT"):
        sys.path.insert(0, str(destination.resolve()))
        if os.environ.get("MD_DEPS_DIR"):
            sys.path.insert(0, os.environ["MD_DEPS_DIR"])
        os.chdir(destination)
        from engineering.molecular.remote import main as remote_main

        sys.argv = [sys.argv[0], "--output", "preflight-output"]
        remote_main()
        return
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(destination / "engineering/molecular/requirements-cuda.txt"),
        ],
        check=True,
        timeout=300,
    )
    env = dict(
        os.environ,
        OMP_NUM_THREADS="2",
        OPENBLAS_NUM_THREADS="2",
        MKL_NUM_THREADS="2",
        OPENMM_CPU_THREADS="2",
        PYTHONUNBUFFERED="1",
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "engineering.molecular.remote",
            "--output",
            str((Path(os.environ["COPS_OUT"]) / "molecular-output").resolve()),
        ],
        cwd=destination,
        env=env,
        check=True,
        timeout=1050,
    )


if __name__ == "__main__":
    main()
