"""Append-only GCS export and hash-checked local collection for bounded VM jobs.

The VM identity needs only ``storage.objects.create`` on one private bucket. Every
object name is unique, manifests are snapshots, and the final manifest is written
last. The local collector uses the operator's gcloud identity to list and read the
exact task prefix, verifies every digest, then atomically retains files locally.

No credentials are accepted in job metadata or command arguments. On a GCE VM the
worker gets a short-lived token from the metadata server; no key file is used.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid


SCHEMA = "delphi.gcp-artifacts/1"
DEFAULT_BUCKET = "delphi-frontier-cpu-artifacts-20261031"
DEFAULT_PREFIX = "jobs/frontier-cpu-20261031-01"
CHUNK_BYTES = 8 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
SECRET_KEY = re.compile(r"(token|secret|password|credential|private.?key|api.?key|authorization)", re.I)
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def safe_relpath(value: str) -> str:
    """Return a canonical relative POSIX path or reject traversal/platform paths."""
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("invalid artifact path")
    p = PurePosixPath(value)
    if p.is_absolute() or any(part in ("", ".", "..") for part in p.parts) or ":" in p.parts[0]:
        raise ValueError("artifact path must be relative and traversal-free")
    return p.as_posix()


def safe_component(value: str, name: str) -> str:
    if not isinstance(value, str) or not SAFE_COMPONENT.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"invalid {name}")
    return value


def validate_record(record: dict) -> dict:
    """Validate the intentionally small, non-secret run record contract."""
    required = {"job_id", "task_id", "source_commit", "source_sha256", "input_sha256", "parameters", "command", "exit_code"}
    optional = {"started_utc", "finished_utc"}
    if not isinstance(record, dict) or not required.issubset(record) or set(record) - required - optional:
        raise ValueError(f"run record must contain {sorted(required)} and optional timestamps")
    record = {"started_utc": None, "finished_utc": None, **record}
    safe_component(record["job_id"], "job_id")
    safe_component(record["task_id"], "task_id")
    if not isinstance(record["source_commit"], str) or not record["source_commit"]:
        raise ValueError("source_commit is required")
    if not re.fullmatch(r"[0-9a-f]{64}", str(record["source_sha256"])):
        raise ValueError("source_sha256 must be a lowercase SHA-256")
    inputs = record["input_sha256"]
    if not isinstance(inputs, dict) or any(not isinstance(k, str) or SECRET_KEY.search(k) or not re.fullmatch(r"[0-9a-f]{64}", str(v)) for k, v in inputs.items()):
        raise ValueError("input_sha256 must map input names to lowercase SHA-256 values")
    if not isinstance(record["parameters"], dict) or any(not isinstance(k, str) or SECRET_KEY.search(k) for k in record["parameters"]):
        raise ValueError("parameters must be a non-secret mapping")
    command = record["command"]
    if not isinstance(command, list) or not command or any(not isinstance(x, str) or SECRET_KEY.search(x) for x in command):
        raise ValueError("command must be a non-secret argv list")
    rc = record["exit_code"]
    if rc is not None and (not isinstance(rc, int) or isinstance(rc, bool)):
        raise ValueError("exit_code must be an integer or null")
    for key in ("started_utc", "finished_utc"):
        if record[key] is not None and (not isinstance(record[key], str) or not record[key].endswith("Z")):
            raise ValueError(f"{key} must be an ISO UTC timestamp ending in Z, or null")
    if record["finished_utc"] is None and record["exit_code"] is not None and record["started_utc"] is not None:
        raise ValueError("a running snapshot must have null exit_code and finished_utc")
    return record


def _response_bytes(opener, request, timeout=60) -> tuple[int, dict, bytes]:
    try:
        response = opener(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        if error.code == 308:
            return 308, dict(error.headers.items()), error.read()
        body = error.read(2048)
        raise RuntimeError(f"GCS request failed with HTTP {error.code}: {body[:500].decode('utf-8', 'replace')}") from None
    with response:
        body = response.read()
        return getattr(response, "status", 200), dict(response.headers.items()), body


def _bounded_response_bytes(opener, request, max_bytes: int, timeout=300):
    """Read no more than max_bytes+1 from the remote body before rejecting it."""
    try:
        response = opener(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        body = error.read(2048)
        raise RuntimeError(f"GCS request failed with HTTP {error.code}: {body[:500].decode('utf-8', 'replace')}") from None
    with response:
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError("remote object exceeds configured collection limit")
        return getattr(response, "status", 200), dict(response.headers.items()), body


class GCS:
    """Small JSON API client; token and opener injection keep tests credential-free."""

    def __init__(self, token_provider, opener=urllib.request.urlopen):
        self.token_provider = token_provider
        self.opener = opener

    @classmethod
    def on_vm(cls, opener=urllib.request.urlopen):
        def token_provider():
            req = urllib.request.Request(
                "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
                headers={"Metadata-Flavor": "Google"},
            )
            _, _, body = _response_bytes(opener, req, timeout=5)
            token = json.loads(body)["access_token"]
            if not isinstance(token, str) or not token:
                raise RuntimeError("metadata server returned no access token")
            return token
        return cls(token_provider, opener)

    @classmethod
    def local(cls, opener=urllib.request.urlopen, gcloud="gcloud"):
        def token_provider():
            result = subprocess.run([gcloud, "auth", "print-access-token"], capture_output=True,
                                    text=True, timeout=30, check=False)
            if result.returncode != 0 or not result.stdout.strip():
                raise RuntimeError("gcloud could not obtain an access token")
            return result.stdout.strip()
        return cls(token_provider, opener)

    def _auth_headers(self, extra=None):
        headers = {"Authorization": "Bearer " + self.token_provider()}
        if extra:
            headers.update(extra)
        return headers

    def upload_file(self, bucket: str, object_name: str, path: Path, digest: str, size: int):
        """Resumable upload with object metadata; all names are create-only."""
        if size > MAX_FILE_BYTES:
            raise ValueError(f"artifact exceeds {MAX_FILE_BYTES} byte limit: {object_name}")
        metadata = {"name": object_name, "metadata": {"sha256": digest, "bytes": str(size)}}
        url = ("https://storage.googleapis.com/upload/storage/v1/b/" + urllib.parse.quote(bucket, safe="")
               + "/o?uploadType=resumable&ifGenerationMatch=0&name=" + urllib.parse.quote(object_name, safe=""))
        req = urllib.request.Request(url, data=json.dumps(metadata, separators=(",", ":")).encode(), method="POST",
                                    headers=self._auth_headers({"Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "application/octet-stream", "X-Upload-Content-Length": str(size)}))
        _, headers, _ = _response_bytes(self.opener, req)
        session = headers.get("Location")
        if not session or not session.startswith("https://"):
            raise RuntimeError("GCS resumable initiation returned no HTTPS session URL")
        with path.open("rb") as stream:
            sent = 0
            no_progress = 0
            if size == 0:
                chunk = b""
                req = urllib.request.Request(session, data=chunk, method="PUT", headers=self._auth_headers({"Content-Length": "0", "Content-Range": "bytes */0"}))
                _response_bytes(self.opener, req)
            while sent < size:
                stream.seek(sent)
                chunk = stream.read(min(CHUNK_BYTES, size - sent))
                if not chunk:
                    raise RuntimeError("artifact shrank during upload")
                end = sent + len(chunk) - 1
                req = urllib.request.Request(session, data=chunk, method="PUT", headers=self._auth_headers({"Content-Length": str(len(chunk)), "Content-Range": f"bytes {sent}-{end}/{size}"}))
                status, response_headers, _ = _response_bytes(self.opener, req)
                if status in (200, 201):
                    sent = size
                elif status == 308:
                    accepted = response_headers.get("Range") or response_headers.get("range")
                    next_sent = int(accepted.rsplit("-", 1)[1]) + 1 if accepted else sent
                    no_progress = no_progress + 1 if next_sent <= sent else 0
                    if no_progress > 3:
                        raise RuntimeError("GCS resumable upload made no progress")
                    sent = next_sent
                else:
                    raise RuntimeError(f"unexpected GCS resumable status {status}")
        return {"object_name": object_name, "sha256": digest, "bytes": size}

    def upload_bytes(self, bucket: str, object_name: str, data: bytes):
        with tempfile.NamedTemporaryFile(prefix="gcs-manifest-", delete=False) as stream:
            temp = Path(stream.name)
            stream.write(data)
        try:
            return self.upload_file(bucket, object_name, temp, sha256_bytes(data), len(data))
        finally:
            temp.unlink(missing_ok=True)

    def list_objects(self, bucket: str, prefix: str):
        token = None
        items = []
        while True:
            query = {"prefix": prefix, "maxResults": "1000"}
            if token:
                query["pageToken"] = token
            url = "https://storage.googleapis.com/storage/v1/b/" + urllib.parse.quote(bucket, safe="") + "/o?" + urllib.parse.urlencode(query)
            req = urllib.request.Request(url, headers=self._auth_headers())
            _, _, body = _response_bytes(self.opener, req)
            page = json.loads(body)
            items.extend(page.get("items", []))
            token = page.get("nextPageToken")
            if not token:
                return items

    def download(self, bucket: str, object_name: str, max_bytes: int) -> bytes:
        url = ("https://storage.googleapis.com/download/storage/v1/b/" + urllib.parse.quote(bucket, safe="")
               + "/o/" + urllib.parse.quote(object_name, safe="") + "?alt=media")
        if not isinstance(max_bytes, int) or max_bytes < 0:
            raise ValueError("max_bytes must be a nonnegative integer")
        req = urllib.request.Request(url, headers=self._auth_headers())
        _, _, body = _bounded_response_bytes(self.opener, req, max_bytes)
        return body

    def download_to_path(self, bucket: str, object_name: str, destination: Path,
                         max_bytes: int, expected_sha256: str):
        """Stream a bounded object to disk, hash it, and atomically publish on success."""
        if not isinstance(max_bytes, int) or max_bytes < 0:
            raise ValueError("max_bytes must be a nonnegative integer")
        destination = Path(destination)
        _mkdir_without_symlinks(destination.parent)
        if destination.is_symlink():
            raise ValueError("refusing linked artifact destination")
        if destination.exists():
            if not destination.is_file() or destination.stat().st_size != max_bytes:
                raise ValueError("existing artifact size or type mismatch")
            actual_sha = _sha256_path(destination)
            if actual_sha != expected_sha256:
                raise ValueError("existing artifact SHA-256 mismatch")
            return actual_sha, max_bytes
        url = ("https://storage.googleapis.com/download/storage/v1/b/" + urllib.parse.quote(bucket, safe="")
               + "/o/" + urllib.parse.quote(object_name, safe="") + "?alt=media")
        req = urllib.request.Request(url, headers=self._auth_headers())
        try:
            response = self.opener(req, timeout=300)
        except urllib.error.HTTPError as error:
            body = error.read(2048)
            raise RuntimeError(f"GCS request failed with HTTP {error.code}: {body[:500].decode('utf-8', 'replace')}") from None
        temp_fd, temp_name = tempfile.mkstemp(prefix=".gcs-download-", dir=destination.parent)
        digest = hashlib.sha256()
        total = 0
        try:
            with response, os.fdopen(temp_fd, "wb") as target:
                while True:
                    chunk = response.read(min(1024 * 1024, max_bytes + 1 - total))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("remote object exceeds configured collection limit")
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            actual_sha = digest.hexdigest()
            if actual_sha != expected_sha256:
                raise ValueError("artifact SHA-256 mismatch")
            if destination.exists():
                if destination.is_symlink() or _sha256_path(destination) != actual_sha:
                    raise ValueError(f"refusing to overwrite different or linked artifact: {destination}")
                return actual_sha, total
            os.replace(temp_name, destination)
            return actual_sha, total
        finally:
            Path(temp_name).unlink(missing_ok=True)


def upload_run(gcs: GCS, bucket: str, prefix: str, output_dir: Path, record: dict,
               max_total_bytes: int = 512 * 1024 * 1024, complete: bool = True) -> dict:
    """Upload regular files and append-only progress snapshots, then final snapshot.

    ``record`` is frozen run metadata and must not contain environment values or secrets.
    A nonzero task exit code is still a completely collected run; those are distinct fields.
    """
    record = validate_record(record)
    prefix = prefix.strip("/")
    if not prefix or ".." in PurePosixPath(prefix).parts:
        raise ValueError("invalid GCS task prefix")
    output_dir = Path(output_dir).resolve(strict=True)
    found = []
    total = 0
    for path in sorted(output_dir.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlinks are not exportable: {path.relative_to(output_dir)}")
        if path.is_file():
            rel = safe_relpath(path.relative_to(output_dir).as_posix())
            digest, size = sha256_file(path)
            total += size
            if total > max_total_bytes:
                raise ValueError("artifact set exceeds configured upload limit")
            found.append((rel, path, digest, size))

    uploaded = []
    first_doc = _manifest(record, bucket, prefix, uploaded, complete=False)
    first_bytes = json.dumps(first_doc, sort_keys=True, separators=(",", ":")).encode()
    gcs.upload_bytes(bucket, f"{prefix}/manifests/progress-000000-{uuid.uuid4().hex}.json", first_bytes)
    for rel, path, digest, size in found:
        object_name = f"{prefix}/objects/{uuid.uuid4().hex}/{rel}"
        gcs.upload_file(bucket, object_name, path, digest, size)
        uploaded.append({"path": rel, "object_name": object_name, "sha256": digest, "bytes": size})
        doc = _manifest(record, bucket, prefix, uploaded, complete=False)
        manifest_data = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
        gcs.upload_bytes(bucket, f"{prefix}/manifests/progress-{len(uploaded):06d}-{uuid.uuid4().hex}.json", manifest_data)

    doc = _manifest(record, bucket, prefix, uploaded, complete=complete)
    manifest_data = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    kind = "final" if complete else "progress"
    result = gcs.upload_bytes(bucket, f"{prefix}/manifests/{kind}-{uuid.uuid4().hex}.json", manifest_data)
    return {**doc, "manifest_object": result["object_name"], "manifest_sha256": result["sha256"]}


def _manifest(record, bucket, prefix, artifacts, complete):
    return {"schema": SCHEMA, "manifest_kind": "final" if complete else "progress", "complete": complete,
            "created_utc": utc_now(), "bucket": bucket,
            "prefix": prefix, "job": record, "artifacts": list(artifacts)}


def _verify_remote_metadata(item: dict, data: bytes):
    metadata = item.get("metadata") or {}
    digest = metadata.get("sha256")
    size = metadata.get("bytes")
    if digest and digest != sha256_bytes(data):
        raise ValueError(f"GCS metadata SHA mismatch for {item.get('name')}")
    if size is not None and int(size) != len(data):
        raise ValueError(f"GCS metadata size mismatch for {item.get('name')}")


def _write_verified(destination: Path, data: bytes, digest: str):
    if sha256_bytes(data) != digest:
        raise ValueError("artifact SHA-256 mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    current = destination.parent
    while current != current.parent:
        if current.is_symlink():
            raise ValueError("destination path traverses a symlink")
        current = current.parent
    if destination.exists():
        if destination.is_symlink() or sha256_file(destination)[0] != digest:
            raise ValueError(f"refusing to overwrite different or linked artifact: {destination}")
        return
    fd, tempname = tempfile.mkstemp(prefix=".gcs-download-", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tempname, destination)
    finally:
        Path(tempname).unlink(missing_ok=True)


def _sha256_path(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _mkdir_without_symlinks(directory: Path):
    directory = Path(directory)
    missing = []
    current = directory
    while not current.exists():
        if current.is_symlink():
            raise ValueError("destination path traverses a symlink")
        missing.append(current)
        current = current.parent
    if current.is_symlink():
        raise ValueError("destination path traverses a symlink")
    for path in reversed(missing):
        path.mkdir()
    current = directory
    while current != current.parent:
        if current.is_symlink():
            raise ValueError("destination path traverses a symlink")
        current = current.parent


def collect(gcs: GCS, bucket: str, prefix: str, destination: Path,
            max_total_bytes: int = 2 * 1024 * 1024 * 1024, require_complete: bool = False) -> dict:
    prefix = prefix.strip("/")
    if not prefix or ".." in PurePosixPath(prefix).parts:
        raise ValueError("invalid GCS task prefix")
    destination = Path(destination).resolve()
    objects = gcs.list_objects(bucket, prefix + "/")
    by_name = {obj["name"]: obj for obj in objects}
    manifest_objects = [x for x in objects if "/manifests/" in x.get("name", "") and x["name"].endswith(".json")]
    snapshots = []
    for item in manifest_objects:
        raw = gcs.download(bucket, item["name"], max_bytes=1024 * 1024)
        _verify_remote_metadata(item, raw)
        doc = json.loads(raw)
        doc_prefix = doc.get("prefix")
        if doc.get("schema") != SCHEMA or not isinstance(doc_prefix, str) or not (doc_prefix == prefix or doc_prefix.startswith(prefix + "/")):
            raise ValueError(f"unexpected manifest contract at {item['name']}")
        if doc.get("manifest_kind") not in {"progress", "final"} or not isinstance(doc.get("artifacts"), list):
            raise ValueError(f"malformed manifest at {item['name']}")
        snapshots.append((doc.get("created_utc", ""), item["name"], item, doc))
    if not snapshots:
        raise ValueError("no progress or final manifests found under task prefix")
    snapshots.sort(key=lambda row: (int(row[2].get("generation", 0)), row[0], row[1]))
    _, manifest_name, manifest_item, manifest = snapshots[-1]
    if require_complete and not manifest.get("complete"):
        raise ValueError("latest task manifest is partial; final marker is absent")
    job = validate_record(manifest["job"])
    snapshot_id = PurePosixPath(manifest_name).name.removesuffix(".json")
    task_dir = destination / safe_component(job["task_id"], "task_id") / safe_component(job["job_id"], "job_id") / safe_component(snapshot_id, "snapshot_id")
    _mkdir_without_symlinks(task_dir)
    expected_total = sum(int(a["bytes"]) for a in manifest["artifacts"])
    if expected_total > max_total_bytes:
        raise ValueError("manifest artifact total exceeds collection limit")
    rows = []
    seen_paths = set()
    for artifact in manifest["artifacts"]:
        rel = safe_relpath(artifact["path"])
        if rel in seen_paths:
            raise ValueError("duplicate artifact path in manifest")
        seen_paths.add(rel)
        obj_name = artifact["object_name"]
        manifest_prefix = manifest["prefix"]
        if not isinstance(obj_name, str) or not obj_name.startswith(manifest_prefix + "/objects/"):
            raise ValueError("manifest object escapes task prefix")
        remote = by_name.get(obj_name)
        if remote is None:
            raise ValueError(f"manifest references missing GCS object: {obj_name}")
        expected_size = artifact.get("bytes")
        if not isinstance(expected_size, int) or expected_size < 0 or expected_size > max_total_bytes:
            raise ValueError("invalid artifact size in manifest")
        target = task_dir / Path(*PurePosixPath(rel).parts)
        digest, actual_size = gcs.download_to_path(bucket, obj_name, target, max_bytes=expected_size,
                                                   expected_sha256=artifact["sha256"])
        if actual_size != expected_size:
            raise ValueError(f"artifact size mismatch: {rel}")
        remote_metadata = remote.get("metadata") or {}
        if remote_metadata.get("sha256") and remote_metadata["sha256"] != digest:
            raise ValueError(f"GCS metadata SHA mismatch for {obj_name}")
        if remote_metadata.get("bytes") is not None and int(remote_metadata["bytes"]) != actual_size:
            raise ValueError(f"GCS metadata size mismatch for {obj_name}")
        rows.append({"path": rel, "local_path": str(target), "object_name": obj_name,
                     "sha256": digest, "bytes": actual_size})

    receipt = {"schema": SCHEMA, "collected_utc": utc_now(), "bucket": bucket, "requested_prefix": prefix,
               "prefix": manifest["prefix"],
               "manifest_object": manifest_name, "manifest_sha256": (manifest_item.get("metadata") or {}).get("sha256"),
               "complete": manifest["complete"], "job": job, "artifacts": rows}
    receipt_path = task_dir / "collection_receipt.json"
    receipt_raw = json.dumps(receipt, sort_keys=True, indent=2).encode() + b"\n"
    if receipt_path.is_symlink():
        raise ValueError("refusing to replace linked collection receipt")
    fd, tempname = tempfile.mkstemp(prefix=".collection-receipt-", dir=task_dir)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(receipt_raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tempname, receipt_path)
    finally:
        Path(tempname).unlink(missing_ok=True)
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def _load_record(path: Path):
    return validate_record(json.loads(path.read_text()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    upload = sub.add_parser("upload", help="run on the VM after the scientific command")
    upload.add_argument("--bucket", default=DEFAULT_BUCKET)
    upload.add_argument("--prefix", required=True)
    upload.add_argument("--output-dir", type=Path, required=True)
    upload.add_argument("--record", type=Path, required=True, help="non-secret JSON run record")
    upload.add_argument("--max-total-bytes", type=int, default=512 * 1024 * 1024)
    upload.add_argument("--partial", action="store_true", help="publish progress only; no completion marker")
    grab = sub.add_parser("collect", help="run locally to retain verified output outside GCP")
    grab.add_argument("--bucket", default=DEFAULT_BUCKET)
    grab.add_argument("--prefix", required=True)
    grab.add_argument("--destination", type=Path, required=True)
    grab.add_argument("--max-total-bytes", type=int, default=2 * 1024 * 1024 * 1024)
    grab.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    if args.mode == "upload":
        result = upload_run(GCS.on_vm(), args.bucket, args.prefix, args.output_dir,
                            _load_record(args.record), args.max_total_bytes, complete=not args.partial)
        print(json.dumps({"complete": result["complete"], "manifest_object": result["manifest_object"],
                          "manifest_sha256": result["manifest_sha256"], "artifacts": len(result["artifacts"])}))
    else:
        result = collect(GCS.local(), args.bucket, args.prefix, args.destination,
                         args.max_total_bytes, args.require_complete)
        print(json.dumps({"complete": result["complete"], "artifacts": len(result["artifacts"]),
                          "receipt": result["receipt_path"]}))


if __name__ == "__main__":
    main()
