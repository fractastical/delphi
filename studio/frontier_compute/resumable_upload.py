"""Object-scoped GCS sessions with private state and explicit operator cancellation.

Provider session lifetime is one week. A persisted deadline plus an independent
operator timer cancels unused sessions sooner; it is not a provider-enforced TTL.
Workers receive only exact-object session URIs, never OAuth or service-account keys.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import parse_qs, quote, urlsplit

from frontier_compute.gcp_artifacts import CHUNK_BYTES, GCS, safe_relpath

MAX_BYTES = 3_200_000_000


def instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return result.astimezone(timezone.utc)


def validate(cap, *, now=None, allow_expired=False):
    now = now or datetime.now(timezone.utc)
    if cap.get("schema") != "frontier.resumable-capability/1":
        raise ValueError("Unsupported capability schema")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,220}[a-z0-9]", cap["bucket"]):
        raise ValueError("Invalid bucket")
    safe_relpath(cap["object"])
    if type(cap["max_bytes"]) is not int or not 0 < cap["max_bytes"] <= MAX_BYTES:
        raise ValueError("Invalid byte bound")
    start, deadline = (
        instant(cap["created_utc"]),
        instant(cap["controller_deadline_utc"]),
    )
    if not 0 < (deadline - start).total_seconds() <= 18000 or start > now:
        raise ValueError("Invalid cancellation window")
    if not allow_expired and now >= deadline:
        raise ValueError("Operator deadline reached")
    url = urlsplit(cap["uri"])
    if (
        url.scheme != "https"
        or url.hostname != "storage.googleapis.com"
        or url.port
        or url.username
        or url.password
        or url.fragment
        or url.path != "/upload/storage/v1/b/" + cap["bucket"] + "/o"
    ):
        raise ValueError("Invalid capability endpoint")
    query = parse_qs(url.query, strict_parsing=True)
    if any(len(v) != 1 for v in query.values()):
        raise ValueError("Duplicate query field")
    if (
        query.get("uploadType") != ["resumable"]
        or query.get("name") != [cap["object"]]
        or query.get("ifGenerationMatch") != ["0"]
        or not query.get("upload_id")
    ):
        raise ValueError("Capability object or create-only constraint mismatch")
    return url


def request(
    url,
    method,
    data=None,
    headers=None,
    *,
    connection_factory=http.client.HTTPSConnection,
):
    """No redirects, auth forwarding, response body logging or secret exceptions."""
    connection = connection_factory(url.hostname, timeout=60)
    try:
        connection.request(
            method, url.path + "?" + url.query, body=data, headers=headers or {}
        )
        response = connection.getresponse()
        body = response.read(65537)
        if len(body) > 65536:
            raise ValueError("Response exceeds metadata limit")
        return response.status, {k.lower(): v for k, v in response.getheaders()}, body
    except Exception as error:
        raise RuntimeError(
            "Capability transport failed: " + type(error).__name__
        ) from None
    finally:
        connection.close()


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


def upload(cap, path, *, transport=request, now=None):
    url = validate(cap, now=now)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or not 0 < before.st_size <= cap["max_bytes"]
        ):
            raise ValueError("Artifact must be nonempty regular file within byte bound")
        sha, md5 = hashlib.sha256(), hashlib.md5(usedforsecurity=False)
        while data := stream.read(1 << 20):
            sha.update(data)
            md5.update(data)
        expected_md5 = base64.b64encode(md5.digest()).decode()
        status, headers, body = transport(
            url,
            "PUT",
            b"",
            {"Content-Length": "0", "Content-Range": f"bytes */{before.st_size}"},
        )
        sent, stalls, attempts = 0, 0, 0
        while status == 308:
            validate(cap, now=now)
            accepted = headers.get("range")
            if accepted:
                match = re.fullmatch(r"bytes=0-(\d+)", accepted)
                if not match:
                    raise ValueError("Malformed upload acknowledgment")
                offset = int(match.group(1)) + 1
            else:
                offset = 0
            if not sent <= offset <= before.st_size or (
                attempts and offset > sent + CHUNK_BYTES
            ):
                raise ValueError("Invalid upload offset")
            stalls = stalls + 1 if attempts and offset == sent else 0
            if stalls > 3 or attempts > (before.st_size // CHUNK_BYTES + 1) * 5:
                raise RuntimeError("Upload made insufficient progress")
            sent = offset
            if sent >= before.st_size:
                raise ValueError("Full upload not finalized")
            stream.seek(sent)
            data = stream.read(min(CHUNK_BYTES, before.st_size - sent))
            if not data:
                raise ValueError("Artifact changed during upload")
            status, headers, body = transport(
                url,
                "PUT",
                data,
                {
                    "Content-Length": str(len(data)),
                    "Content-Range": f"bytes {sent}-{sent + len(data) - 1}/{before.st_size}",
                },
            )
            attempts += 1
        if status not in (200, 201):
            raise RuntimeError(f"Capability upload rejected with HTTP {status}")
        metadata = json.loads(body)
        if (
            metadata.get("bucket") != cap["bucket"]
            or metadata.get("name") != cap["object"]
            or int(metadata.get("size", -1)) != before.st_size
            or metadata.get("md5Hash") != expected_md5
            or not metadata.get("generation")
        ):
            raise ValueError("Final object metadata or content checksum mismatch")
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Artifact changed during upload")
    return {
        "schema": "frontier.resumable-upload-receipt/1",
        "bucket": cap["bucket"],
        "object": cap["object"],
        "bytes": before.st_size,
        "sha256": sha.hexdigest(),
        "md5_base64": expected_md5,
        "generation": metadata["generation"],
        "http_status": status,
        "controller_deadline_utc": cap["controller_deadline_utc"],
        "create_only": True,
        "operator_download_hash_check_required": True,
    }


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


if __name__ == "__main__":
    main()
