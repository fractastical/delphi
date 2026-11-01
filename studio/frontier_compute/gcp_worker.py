"""Build a credential-free, bounded GCE startup script from a frozen task packet.

Admission remains an explicit operator action. The resulting script runs one task,
exports immutable snapshots through the attached identity, then powers off.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path("/work/frontier")


def validate(spec):
    if not re.fullmatch(r"frontier-cpu-\d{8}-\d{2}", spec["vm"]):
        raise ValueError("Invalid owned VM name")
    if not re.fullmatch(r"[a-z0-9-]{1,64}", spec["task_id"]):
        raise ValueError("Invalid task ID")
    if spec["vcpus"] not in (4, 8, 16) or not 1 <= spec["memory_gb"] <= 56:
        raise ValueError("Invalid CPU or memory bound")
    if not 60 <= spec["runtime_s"] <= 79200:
        raise ValueError("Invalid task runtime bound")
    if not 300 <= spec["export_interval_s"] <= 3600:
        raise ValueError("Invalid export interval")
    if not isinstance(spec["argv"], list) or not spec["argv"] or not all(isinstance(x, str) for x in spec["argv"]):
        raise ValueError("Task command must be an argv list")
    if not re.fullmatch(r"[a-f0-9]{64}", spec["source_sha256"]):
        raise ValueError("Source hash required")
    # Only declared, nonsensitive task parameters are permitted in metadata.
    for key in spec.get("env", {}):
        if re.search(r"token|secret|password|credential|api.?key", key, re.I):
            raise ValueError("Credentials are not allowed in VM metadata")
    return spec


def systemd_argv(spec, source, output):
    validate(spec)
    args = ["systemd-run", "--wait", "--pipe", "--collect", "--unit=frontier-science",
            "-p", f"WorkingDirectory={source}", "-p", f"CPUQuota={spec['vcpus'] * 100}%",
            "-p", f"MemoryMax={spec['memory_gb']}G", "-p", "MemorySwapMax=0",
            "-p", "TasksMax=256", "-p", f"RuntimeMaxSec={spec['runtime_s']}",
            "-p", "KillMode=control-group", "-p", "TimeoutStopSec=45",
            "--setenv", f"COPS_OUT={output}", "--setenv", "PYTHONUNBUFFERED=1"]
    for key, value in spec.get("env", {}).items():
        args += ["--setenv", f"{key}={value}"]
    return args + ["--", *spec["argv"]]


def build(spec, packet, exporter, destination):
    validate(spec)
    packet_bytes = Path(packet).read_bytes()
    if hashlib.sha256(packet_bytes).hexdigest() != spec["source_sha256"]:
        raise ValueError("Source packet hash mismatch")
    files = {"packet.tar": packet_bytes, "config.json": json.dumps(spec).encode(),
             "gcp_worker.py": Path(__file__).read_bytes(), "gcp_artifacts.py": Path(exporter).read_bytes()}
    text = "#!/bin/bash\nset -euo pipefail\nmkdir -p /work/frontier\ncd /work/frontier\n"
    # No shell interpolation of task content: all bytes are base64 encoded.
    for name, payload in files.items():
        text += f"base64 -d > {name} <<'FRONTIER_BYTES'\n{base64.b64encode(payload).decode()}\nFRONTIER_BYTES\n"
    text += "/usr/bin/python3 /work/frontier/gcp_worker.py run /work/frontier/config.json\n"
    if len(text.encode()) > 250_000:
        raise ValueError("Startup metadata too large; use a separately hash-bound source transport")
    Path(destination).write_text(text)
    return {"startup_sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode()),
            "source_sha256": spec["source_sha256"], "exporter_sha256": hashlib.sha256(files["gcp_artifacts.py"]).hexdigest()}


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def extract_source(archive, source, output):
    members = archive.getmembers()
    for member in members:
        if not (member.isfile() or member.isdir()) or Path(member.name).is_absolute() or ".." in Path(member.name).parts:
            raise ValueError("Unsafe packet member")
        target = source / member.name
        for part in [target, *target.parents]:
            if part == source.parent:
                break
            if part.is_symlink():
                raise ValueError("Packet target traverses a symlink")
    try:
        archive.extractall(source, filter="data")
    except TypeError as error:
        if "filter" not in str(error) or "unexpected keyword" not in str(error):
            raise
        # Debian's older Python3.11 can lack the extraction-filter backport.
        # All members were checked before extraction; copy regular bytes only,
        # never applying archive modes, ownership, links or special-file types.
        receipt = {"utc": now(), "python": sys.version, "observed_exception": repr(error),
                   "repair": "Validated regular-file copying; traversal/link/special-file refusals retained"}
        (output / "tar-extraction-compatibility.json").write_text(json.dumps(receipt, indent=2))
        print("FRONTIER_TAR_COMPATIBILITY " + json.dumps(receipt), flush=True)
        for member in members:
            target = source / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as incoming, target.open("wb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing)


def export_snapshot(spec, output, rc, started):
    """Copy an immutable tree before hashing; skip a concurrently changing file."""
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    (output / "host-sample.json").write_text(json.dumps({"observed_utc": now(),
        "logical_cpus": os.cpu_count(), "load_1_5_15": os.getloadavg(),
        "cpu_pressure": Path("/proc/pressure/cpu").read_text(),
        "scope": "Instant worker host sample; allocation is not utilization."}, indent=2))
    with tempfile.TemporaryDirectory(prefix="export-", dir=ROOT) as temp:
        snapshot = Path(temp) / "out"
        snapshot.mkdir()
        skipped = []
        for path in sorted(output.rglob("*")):
            if path.is_symlink():
                raise ValueError("Output symlink refused")
            if not path.is_file():
                continue
            before = path.stat()
            target = snapshot / path.relative_to(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                target.unlink()
                skipped.append(str(path.relative_to(output)))
        (snapshot / "snapshot-status.json").write_text(json.dumps({"created_utc": now(), "exit_code": rc,
            "skipped_mutable_files": skipped, "complete_collection_possible": rc is not None and not skipped}, indent=2))
        record = {"job_id": spec["vm"], "task_id": spec["task_id"], "source_commit": spec["source_commit"],
                  "source_sha256": spec["source_sha256"], "input_sha256": spec.get("input_sha256", {}),
                  "parameters": spec.get("parameters", {}), "command": spec["argv"], "exit_code": rc,
                  "started_utc": started, "finished_utc": now() if rc is not None else None}
        record_path = Path(temp) / "record.json"
        record_path.write_text(json.dumps(record))
        command = [sys.executable, str(ROOT / "gcp_artifacts.py"), "upload", "--bucket", spec["bucket"],
                   "--prefix", f"jobs/{spec['vm']}/{spec['task_id']}/{stamp}", "--output-dir", str(snapshot),
                   "--record", str(record_path), "--max-total-bytes", str(spec.get("max_export_bytes", 3_000_000_000))]
        if rc is None or skipped:
            command.append("--partial")
        result = subprocess.run(command, timeout=1200, capture_output=True, text=True)
        print(json.dumps({"event": "export", "utc": now(), "rc": result.returncode,
                          "task_rc": rc, "started_utc": started, "stderr": result.stderr[-1000:]}), flush=True)
        return result.returncode


def run(spec):
    import tarfile

    validate(spec)
    source, output = ROOT / "src", ROOT / "out"
    source.mkdir(exist_ok=True)
    output.mkdir(exist_ok=True)
    packet = ROOT / "packet.tar"
    if hashlib.sha256(packet.read_bytes()).hexdigest() != spec["source_sha256"]:
        raise ValueError("VM packet hash mismatch")
    with tarfile.open(packet) as archive:
        extract_source(archive, source, output)
    started = now()
    (output / "dispatch.json").write_text(json.dumps({"spec": spec, "started_utc": started}, indent=2))
    try:
        with (output / "console.log").open("w") as log:
            process = subprocess.Popen(systemd_argv(spec, source, output), stdout=log, stderr=subprocess.STDOUT)
            # Confirm the attached-identity transport promptly during setup.
            next_export = time.monotonic() + 30
            while process.poll() is None:
                if time.monotonic() >= next_export:
                    try:
                        export_snapshot(spec, output, None, started)
                    except (OSError, ValueError, subprocess.SubprocessError) as error:
                        print(json.dumps({"event": "partial_export_failed", "error": str(error)[:500]}), flush=True)
                    next_export = time.monotonic() + spec["export_interval_s"]
                time.sleep(5)
        rc = process.returncode
        (output / "completion.json").write_text(json.dumps({"exit_code": rc, "finished_utc": now()}, indent=2))
        export_rc = export_snapshot(spec, output, rc, started)
        if export_rc:
            # One transport retry, never a scientific rerun. VM hard-stop remains.
            export_rc = export_snapshot(spec, output, rc, started)
        print(json.dumps({"event": "finished", "task_rc": rc, "export_rc": export_rc}), flush=True)
    finally:
        subprocess.run(["systemctl", "poweroff"], check=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["build", "run"])
    parser.add_argument("config", type=Path)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--exporter", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    spec = json.loads(args.config.read_text())
    if args.mode == "build":
        print(json.dumps(build(spec, args.packet, args.exporter, args.output)))
    else:
        run(spec)


if __name__ == "__main__":
    main()
