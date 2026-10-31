"""Run a source-hashed portable scientific packet without remote credentials."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile


def unpack(archive, manifest, destination):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
        raise ValueError("Portable packet hash mismatch")
    with tarfile.open(archive) as packet:
        members = packet.getmembers()
        if len(members) != len(manifest["files"]):
            raise ValueError("Portable packet member count mismatch")
        for member in members:
            if not member.isfile() or member.name not in manifest["files"]:
                raise ValueError("Unexpected portable packet member")
        packet.extractall(destination, filter="data")
    for name, expected in manifest["files"].items():
        if hashlib.sha256((destination / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Portable file hash mismatch: " + name)


def main():
    archive, manifest_path = map(Path, sys.argv[1:3])
    manifest = json.loads(manifest_path.read_text())
    out = Path(os.environ["COPS_OUT"]).resolve()
    work = out / "packet-source"
    work.mkdir(parents=True, exist_ok=True)
    unpack(archive, manifest, work)
    mode = "preflight" if os.environ.get("PREFLIGHT") else "entry"
    argv = [sys.executable, *manifest[mode][1:]]
    argv = [str(out / "output") if argument == "OUT" else argument for argument in argv]
    subprocess.run(argv, cwd=work, check=True, timeout=60 if mode == "preflight" else manifest["timeout_seconds"])


if __name__ == "__main__":
    main()
