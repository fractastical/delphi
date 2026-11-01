"""Operator-only issuance and persisted cancellation; never shipped to workers."""

from __future__ import annotations

import argparse
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
    args = parser.parse_args()
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

