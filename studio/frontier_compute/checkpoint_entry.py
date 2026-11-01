"""Run an unchanged CFD packet and export only its coherent declared checkpoints.

Small scientific outputs use the established log archive. Large immutable
checkpoints use exact-object capabilities and remain represented by size/hash
receipts. No capability file or URI enters the scientific output tree.
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
from frontier_compute.resumable_upload import upload, validate


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def export_checkpoints(science, out, sessions, ledger, *, uploader=upload):
    manifest = science / "checkpoints/manifest.json"
    if not manifest.exists():
        return
    declaration = json.loads(manifest.read_text())
    if declaration.get("coherent_only_if_listed") is not True:
        raise ValueError("Checkpoint manifest does not assert coherent snapshots")
    rows = declaration["snapshots"]
    if len(rows) > len(sessions):
        raise ValueError("Declared checkpoint count exceeds prepared object slots")
    if sum(row["bytes"] for row in rows) > 3_200_000_000:
        raise ValueError("Declared checkpoint total exceeds frozen byte bound")
    for index, row in enumerate(rows):
        name = row["file"]
        if Path(name).name != name or not name.endswith(".ckpt"):
            raise ValueError("Unsafe checkpoint filename")
        if name in ledger:
            if ledger[name]["sha256"] != row["sha256"]:
                raise ValueError("Immutable checkpoint identity changed")
            continue
        path = science / "checkpoints" / name
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != row["bytes"]
        ):
            raise ValueError("Declared checkpoint size/type mismatch")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while data := stream.read(1 << 20):
                digest.update(data)
        if digest.hexdigest() != row["sha256"]:
            raise ValueError("Declared checkpoint digest mismatch")
        receipt = uploader(sessions[index]["capability"], path)
        if receipt["sha256"] != row["sha256"] or receipt["bytes"] != row["bytes"]:
            raise ValueError("Upload did not preserve declared checkpoint")
        ledger[name] = dict(receipt, source_snapshot=row)
        save(
            out / "external-checkpoints.json",
            {
                "schema": "frontier.external-checkpoints/1",
                "checkpoints": ledger,
                "scope": "Coherent native checkpoint bytes are external; independent operator download/hash required.",
            },
        )


def sync_small(science, out):
    for source in science.rglob("*"):
        if (
            not source.is_file()
            or source.is_symlink()
            or source.name.endswith((".tmp", ".partial", ".ckpt"))
        ):
            continue
        relative = source.relative_to(science)
        target = out / "science" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".copying")
        shutil.copyfile(source, temporary)
        temporary.replace(target)


def run(archive, manifest_path, capability_path):
    out = Path(os.environ["COPS_OUT"]).resolve()
    manifest = json.loads(manifest_path.read_text())
    source = out / "packet-source"
    source.mkdir(parents=True, exist_ok=True)
    unpack(archive, manifest, source)
    if os.environ.get("PREFLIGHT"):
        print(
            json.dumps(
                {
                    "archive_and_member_hashes_checked": True,
                    "science_not_executed": True,
                }
            )
        )
        return 0
    sessions = json.loads(capability_path.read_text())["sessions"]
    if not 1 <= len(sessions) <= 4:
        raise ValueError("Checkpoint session count is outside declared bounds")
    for session in sessions:
        validate(session["capability"])
    science = Path(tempfile.mkdtemp(prefix="frontier-cfd-output-", dir="/work"))
    environment = dict(os.environ, COPS_OUT=str(science))
    argv = [sys.executable, *manifest["entry"][1:]]
    process = subprocess.Popen(
        argv, cwd=source, env=environment, start_new_session=True
    )
    started = time.monotonic()
    ledger = {}
    failures = []
    timed_out = False
    export_failures = 0
    try:
        while True:
            rc = process.poll()
            sync_small(science, out)
            try:
                if export_failures < 3:
                    export_checkpoints(science, out, sessions, ledger)
            except (OSError, ValueError, RuntimeError) as error:
                export_failures += 1
                # Error messages may contain transport details: retain only the class.
                failures.append(
                    {
                        "at_s": round(time.monotonic() - started, 1),
                        "type": type(error).__name__,
                        "stage": "checkpoint_export",
                        "pending_operator_check": True,
                    }
                )
                save(out / "checkpoint-transport-failures.json", failures)
            if rc is not None:
                break
            if time.monotonic() - started > manifest["timeout_seconds"]:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                break
            time.sleep(20)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=20)
    sync_small(science, out)
    expected = (
        json.loads((science / "checkpoints/manifest.json").read_text())["snapshots"]
        if (science / "checkpoints/manifest.json").exists()
        else []
    )
    complete = len(expected) == len(ledger)
    receipt = {
        "schema": "frontier.checkpoint-runner/1",
        "native_rc": process.returncode,
        "timed_out": timed_out,
        "elapsed_s": round(time.monotonic() - started, 1),
        "declared_checkpoint_count": len(expected),
        "uploaded_checkpoint_count": len(ledger),
        "checkpoint_export_complete": complete,
        "transport_failures_retained": len(failures),
        "independent_operator_hash_checks_required": True,
        "native_acceptance_unchanged": True,
    }
    save(out / "checkpoint-runner-receipt.json", receipt)
    print(json.dumps(receipt), flush=True)
    return process.returncode if complete and not timed_out else 1


if __name__ == "__main__":
    raise SystemExit(run(*map(Path, sys.argv[1:4])))
