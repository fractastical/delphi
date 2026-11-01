"""Stream an immutable artifact using a short, create-only GCS PUT capability.

The capability JSON is private runtime input, never an output artifact. Receipts
contain object identity and content hashes, never the signed URL or response body.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import stat
from urllib.parse import parse_qs, quote, urlsplit


MAX_BYTES = 3_200_000_000


def validate(capability, *, now=None):
    now = now or datetime.now(timezone.utc)
    if capability.get("method") != "PUT":
        raise ValueError("Only PUT capabilities are accepted")
    bucket, name = capability["bucket"], capability["object"]
    if not bucket or not name or any(x in name.split("/") for x in ("", ".", "..")):
        raise ValueError("Invalid object identity")
    url = urlsplit(capability["url"])
    if url.scheme != "https" or url.username or url.password or url.port or url.fragment:
        raise ValueError("Invalid capability endpoint")
    paths = {
        "storage.googleapis.com": "/" + bucket + "/" + quote(name, safe="/"),
        bucket + ".storage.googleapis.com": "/" + quote(name, safe="/"),
    }
    if url.hostname not in paths or url.path != paths[url.hostname]:
        raise ValueError("Capability object does not match the declared object")
    query = parse_qs(url.query, strict_parsing=True)
    if any(len(values) != 1 for values in query.values()):
        raise ValueError("Duplicate capability query fields")
    fields = {key.lower(): values[0] for key, values in query.items()}
    started = datetime.strptime(fields["x-goog-date"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    seconds = int(fields["x-goog-expires"])
    if not 1 <= seconds <= 43200 or started > now + timedelta(seconds=60):
        raise ValueError("Capability exceeds the bounded validity window")
    expires = started + timedelta(seconds=seconds)
    if now >= expires:
        raise ValueError("Capability expired")
    headers = {key.lower(): str(value) for key, value in capability["headers"].items()}
    if set(headers) != {"content-type", "x-goog-if-generation-match"}:
        raise ValueError("Unexpected upload headers")
    if headers["x-goog-if-generation-match"] != "0":
        raise ValueError("Upload must be create-only")
    signed = set(fields["x-goog-signedheaders"].lower().split(";"))
    if not {"host", *headers} <= signed:
        raise ValueError("Create-only and content-type headers must be signed")
    if fields.get("x-goog-algorithm") != "GOOG4-RSA-SHA256" or not fields.get("x-goog-signature"):
        raise ValueError("Expected a V4 RSA signed capability")
    return url, headers, expires


def upload(capability, path, max_bytes, *, connection_factory=http.client.HTTPSConnection, now=None):
    """Upload once; an ambiguous network result requires operator hash checking."""
    url, headers, expires = validate(capability, now=now)
    if type(max_bytes) is not int or not 0 < max_bytes <= MAX_BYTES:
        raise ValueError("Invalid output byte bound")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Artifact must be a regular file")
        if not 0 < before.st_size <= max_bytes:
            raise ValueError("Artifact is empty or exceeds its byte bound")
        sha, md5 = hashlib.sha256(), hashlib.md5(usedforsecurity=False)
        remaining = before.st_size
        while remaining:
            chunk = source.read(min(1 << 20, remaining))
            if not chunk:
                raise ValueError("Artifact changed while hashing")
            remaining -= len(chunk)
            sha.update(chunk)
            md5.update(chunk)
        source.seek(0)
        headers.update({"content-length": str(before.st_size),
                        "content-md5": base64.b64encode(md5.digest()).decode()})
        connection = connection_factory(url.hostname, timeout=120)
        try:
            connection.request("PUT", url.path + "?" + url.query, body=source, headers=headers)
            response = connection.getresponse()
            response.read(4096)
            status = response.status
            generation = response.getheader("x-goog-generation")
        except Exception as error:
            # Exception messages can include request URLs. Never expose them.
            raise RuntimeError("Upload transport failed: " + type(error).__name__) from None
        finally:
            connection.close()
        after = os.fstat(source.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Artifact changed while uploading")
        if not 200 <= status < 300:
            raise RuntimeError(f"Signed upload rejected with HTTP {status}")
    return {"schema": "frontier.signed-upload-receipt/1", "bucket": capability["bucket"],
            "object": capability["object"], "bytes": before.st_size, "sha256": sha.hexdigest(),
            "content_md5": headers["content-md5"], "generation": generation,
            "http_status": status, "capability_expires_utc": expires.isoformat(),
            "create_only": True, "operator_download_hash_check_required": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capability_file", type=Path)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--max-bytes", required=True, type=int)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    receipt = upload(json.loads(args.capability_file.read_text()), args.artifact, args.max_bytes)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
