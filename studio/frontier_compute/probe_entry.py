"""Execute a frozen build probe while returning only its declared small evidence.

The temporary compiler/source tree stays outside the log-return artifact tree.
Native failures and timeouts stay failures; this adapter never interprets physics.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from frontier_compute.portable_entry import unpack


def collect(work, out, limit):
    sources = []
    for directory in ("logs", "out"):
        for source in sorted((work / directory).rglob("*")):
            if source.is_symlink():
                raise ValueError("Probe evidence contains a symlink")
            if source.is_file() and source.name != "probe-return.tar.gz":
                sources.append(source)
    total = sum(path.stat().st_size for path in sources)
    if total > limit:
        raise ValueError("Native probe evidence exceeds declared return bound")
    rows = []
    for source in sources:
        relative = source.relative_to(work)
        target = out / "native" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        rows.append({"path": str(relative), "bytes": target.stat().st_size,
                     "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    return rows


def run(archive, manifest_path):
    out = Path(os.environ["COPS_OUT"]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text())
    source = out / "packet-source"
    source.mkdir()
    unpack(archive, manifest, source)
    if os.environ.get("PREFLIGHT"):
        subprocess.run(["bash", "-n", str(source / "run_probe.sh")], check=True)
        print("Probe archive/member hashes and shell syntax passed; no GPU work run")
        return 0
    work = Path(tempfile.mkdtemp(prefix="frontier-build-probe-"))
    started = time.monotonic()
    timed_out = False
    with (out / "probe-console.log").open("w") as log:
        process = subprocess.Popen(["bash", str(source / "run_probe.sh"), str(work)],
                                   cwd=source, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            process.wait(timeout=manifest["timeout_seconds"])
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    error = None
    rows = []
    try:
        rows = collect(work, out, manifest["max_evidence_bytes"])
        if not rows or not (out / "native/out/receipt.json").is_file():
            raise ValueError("Native probe receipt is missing; empty return cannot pass")
    except (OSError, ValueError) as exc:
        error = {"type": type(exc).__name__, "message": str(exc)[:300]}
    result = {"schema": "frontier.build-probe-transport/1", "native_exit_code": process.returncode,
              "timed_out": timed_out, "elapsed_s": round(time.monotonic() - started, 3),
              "archive_sha256": manifest["archive_sha256"], "files": rows,
              "collection_failure": error, "source_build_tree_excluded": True,
              "native_scientific_criteria_unchanged": True}
    (out / "probe-transport.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "files"}), flush=True)
    return 1 if timed_out or error else process.returncode


if __name__ == "__main__":
    raise SystemExit(run(*map(Path, sys.argv[1:3])))
