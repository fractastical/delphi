"""Operator-only issuance and persisted cancellation; never shipped to workers."""

from __future__ import annotations

import argparse
import hashlib
import re
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import tempfile
from urllib.parse import quote, urlsplit

from frontier_compute.resumable_upload import instant, request, safe_relpath, validate


def private_save(path, value):
    """Persist cancellation state atomically without permissive intermediate files."""
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = path.parent.stat()
    if stat.S_IMODE(st.st_mode) != 0o700 or st.st_uid != os.getuid():
        raise ValueError("Capability directory must be owned and mode0700")
    fd, name = tempfile.mkstemp(prefix=".cap-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def issue(gcs, bucket, object_name, deadline, max_bytes, *, now=None):
    """Operator only. The returned URI is a bearer capability: persist privately."""
    now = now or datetime.now(timezone.utc)
    safe_relpath(object_name)
    uri = (
        "https://storage.googleapis.com/upload/storage/v1/b/"
        + quote(bucket, safe="")
        + "/o?uploadType=resumable&ifGenerationMatch=0&name="
        + quote(object_name, safe="")
    )
    cap = {
        "schema": "frontier.resumable-capability/1",
        "bucket": bucket,
        "object": object_name,
        "uri": uri + "&upload_id=preinit-validation-only",
        "max_bytes": max_bytes,
        "created_utc": now.isoformat(),
        "controller_deadline_utc": deadline,
        "provider_lifetime": "One week; explicit controller cancellation is separate",
    }
    validate(cap, now=now)
    status, headers, _ = request(
        urlsplit(uri),
        "POST",
        json.dumps({"name": object_name}).encode(),
        {
            "Authorization": "Bearer " + gcs.token_provider(),
            "Content-Type": "application/json",
            "X-Upload-Content-Type": "application/octet-stream",
        },
    )
    if status not in (200, 201) or "location" not in headers:
        raise RuntimeError(f"Capability initiation failed with HTTP {status}")
    cap["uri"] = headers["location"]
    validate(cap, now=now)
    return cap


def cancel_due(path, *, now=None, force=False, transport=request):
    """Reload persisted state on each call; an independent timer survives restarts."""
    now = now or datetime.now(timezone.utc)
    path = Path(path)
    state = json.loads(path.read_text())
    events = []
    for row in state["sessions"]:
        if row.get("cancelled_utc"):
            continue
        cap = row["capability"]
        if not force and now < instant(cap["controller_deadline_utc"]):
            continue
        url = validate(cap, now=now, allow_expired=True)
        status, _, _ = transport(url, "DELETE")
        # A completed/absent session can no longer write. This does not delete objects.
        if status not in (200, 204, 404, 410, 499):
            raise RuntimeError(f"Capability cancellation failed with HTTP {status}")
        row.update(cancelled_utc=now.isoformat(), cancellation_status=status)
        private_save(path, state)
        events.append(
            {
                "object": cap["object"],
                "http_status": status,
                "cancelled_utc": now.isoformat(),
            }
        )
    return {
        "events": events,
        "pending": sum(not r.get("cancelled_utc") for r in state["sessions"]),
    }


def collect_checkpoints(gcs, state_path, native_path, external_path, destination):
    """Bind exact native hashes to our issued objects, then stream them off-project."""
    state = json.loads(Path(state_path).read_text())
    native = json.loads(Path(native_path).read_text())
    external = json.loads(Path(external_path).read_text())
    if native.get("coherent_only_if_listed") is not True:
        raise ValueError("Native checkpoint manifest is not coherent")
    if external.get("schema") != "frontier.external-checkpoints/1":
        raise ValueError("Unsupported external checkpoint receipt")
    slots = {}
    for row in state["sessions"]:
        cap = row["capability"]
        validate(cap, allow_expired=True)
        key = (cap["bucket"], cap["object"])
        if key in slots:
            raise ValueError("Duplicate issued checkpoint object")
        slots[key] = cap
    snapshots, receipts = native["snapshots"], external["checkpoints"]
    if not snapshots or len(snapshots) > len(slots):
        raise ValueError("Invalid checkpoint cardinality")
    names = [row["file"] for row in snapshots]
    if len(set(names)) != len(names) or set(names) != set(receipts):
        raise ValueError("Native and uploaded checkpoint identities differ")
    total = 0
    validated = []
    used = set()
    for row in snapshots:
        name, size, digest = row["file"], row["bytes"], row["sha256"]
        if (Path(name).name != name or not name.endswith(".ckpt")
                or type(size) is not int or size <= 0
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("Invalid native checkpoint identity")
        receipt = receipts[name]
        key = (receipt["bucket"], receipt["object"])
        cap = slots.get(key)
        if (cap is None or key in used or size > cap["max_bytes"]
                or receipt.get("source_snapshot") != row
                or receipt.get("sha256") != digest or receipt.get("bytes") != size
                or receipt.get("create_only") is not True
                or not re.fullmatch(r"[0-9]+", str(receipt.get("generation", "")))):
            raise ValueError("Checkpoint receipt does not match issued object and native bytes")
        total += size
        used.add(key)
        validated.append((row, receipt))
    if total > 3_200_000_000:
        raise ValueError("Checkpoint collection exceeds aggregate byte bound")
    destination = Path(destination)
    collected = []
    for row, receipt in validated:
        path = destination / row["file"]
        digest, size = gcs.download_to_path(receipt["bucket"], receipt["object"], path,
                                          row["bytes"], row["sha256"])
        if digest != row["sha256"] or size != row["bytes"]:
            raise ValueError("Independent downloaded bytes differ from native checkpoint")
        collected.append({"file": row["file"], "bytes": size, "sha256": digest,
                          "bucket": receipt["bucket"], "object": receipt["object"],
                          "upload_generation": receipt["generation"],
                          "local_path": str(path.resolve())})
    result = {"schema": "frontier.independent-checkpoint-collection/1",
              "observed_utc": datetime.now(timezone.utc).isoformat(),
              "native_manifest_sha256": hashlib.sha256(Path(native_path).read_bytes()).hexdigest(),
              "external_receipt_sha256": hashlib.sha256(Path(external_path).read_bytes()).hexdigest(),
              "checkpoints": collected, "bytes": total,
              "all_expected_checkpoints_collected": True,
              "scope": "Transport and native byte identity checked; no numerical or biological acceptance inferred."}
    path = destination / "collection-receipt.json"
    if path.is_symlink():
        raise ValueError("Refusing linked collection receipt")
    fd, temp = tempfile.mkstemp(prefix=".checkpoint-receipt-", dir=destination)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("issue")
    create.add_argument("--bucket", required=True)
    create.add_argument("--prefix", required=True)
    create.add_argument("--deadline", required=True)
    create.add_argument("--slots", type=int, default=4)
    create.add_argument("--max-bytes", type=int, default=1_100_000_000)
    create.add_argument("--state", type=Path, required=True)
    cancel = commands.add_parser("cancel-due")
    cancel.add_argument("state", type=Path)
    cancel.add_argument("--force", action="store_true")
    collection = commands.add_parser("collect")
    collection.add_argument("--state", type=Path, required=True)
    collection.add_argument("--native", type=Path, required=True)
    collection.add_argument("--external", type=Path, required=True)
    collection.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "collect":
        from frontier_compute.gcp_artifacts import GCS
        print(json.dumps(collect_checkpoints(GCS.local(), args.state, args.native,
                                             args.external, args.destination)))
        return
    if args.command == "cancel-due":
        print(json.dumps(cancel_due(args.state, force=args.force)))
        return
    if args.state.exists() or not 1 <= args.slots <= 8:
        raise ValueError("State must be fresh and slot count bounded")
    # Persist every issued URI before issuing the next. Partial initiation remains cancellable.
    state = {"schema": "frontier.resumable-session-ledger/1", "sessions": []}
    private_save(args.state, state)
    from frontier_compute.gcp_artifacts import GCS

    for index in range(args.slots):
        cap = issue(
            GCS.local(),
            args.bucket,
            safe_relpath(args.prefix) + f"/checkpoint-{index:02d}.bin",
            args.deadline,
            args.max_bytes,
        )
        state["sessions"].append({"capability": cap})
        private_save(args.state, state)
    print(
        json.dumps(
            {
                "issued": len(state["sessions"]),
                "controller_deadline_utc": args.deadline,
                "scope": "Object-scoped URIs persisted privately; no IAM changes",
            }
        )
    )

