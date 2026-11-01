import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from frontier_compute.gcp_artifacts import GCS, collect, safe_relpath, upload_run


def run_record(exit_code=0):
    return {
        "job_id": "frontier-cpu-20261031-01",
        "task_id": "mechanobio-sweep",
        "source_commit": "abc123",
        "source_sha256": "a" * 64,
        "input_sha256": {"source.tar.gz": "b" * 64},
        "parameters": {"replicates": 32, "grid": 7},
        "command": ["python", "-m", "engineering.mechanobio.sweep", "--grid", "7"],
        "exit_code": exit_code,
        "started_utc": "2026-10-31T10:00:00Z",
        "finished_utc": "2026-10-31T10:05:00Z" if exit_code is not None else None,
    }


class Response:
    def __init__(self, body=b"", headers=None, status=200):
        self.body = body
        self.headers = headers or {}
        self.status = status
        self.read_sizes = []
        self.position = 0

    def read(self, size=-1):
        self.read_sizes.append(size)
        end = len(self.body) if size < 0 else min(len(self.body), self.position + size)
        data = self.body[self.position:end]
        self.position = end
        return data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FakeGCS:
    def __init__(self):
        self.objects = {}
        self.generation = 0
        self.sessions = {}

    def __call__(self, req, timeout=60):
        parsed = urlparse(req.full_url)
        if parsed.path.endswith("/o") and parsed.path.startswith("/upload/"):
            name = parse_qs(parsed.query)["name"][0]
            doc = json.loads(req.data)
            session = "https://upload.test/" + str(len(self.sessions))
            self.sessions[session] = {"name": name, "metadata": doc.get("metadata", {}), "data": bytearray()}
            return Response(headers={"Location": session})
        if parsed.netloc == "upload.test":
            session = self.sessions[req.full_url]
            session["data"].extend(req.data or b"")
            self.generation += 1
            self.objects[session["name"]] = {
                "name": session["name"], "metadata": session["metadata"],
                "generation": str(self.generation), "data": bytes(session["data"]),
            }
            return Response(status=200, body=b"{}")
        if parsed.path.endswith("/o") and req.get_method() == "GET":
            prefix = parse_qs(parsed.query).get("prefix", [""])[0]
            items = [{k: v for k, v in obj.items() if k != "data"} for name, obj in self.objects.items() if name.startswith(prefix)]
            return Response(body=json.dumps({"items": items}).encode())
        if "/o/" in parsed.path and req.get_method() == "GET":
            name = parsed.path.split("/o/", 1)[1]
            from urllib.parse import unquote
            name = unquote(name)
            return Response(body=self.objects[name]["data"])
        raise AssertionError(f"unexpected request {req.get_method()} {req.full_url}")


def test_upload_then_collect_retains_hash_checked_artifacts(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    (output / "sweep.json").write_text('{"runs": 2}\n')
    (output / "stdout.log").write_text("finished\n")
    fake = FakeGCS()
    client = GCS(lambda: "test-token", fake)

    result = upload_run(client, "bucket", "jobs/job/task", output, run_record())
    assert result["complete"] is True
    assert result["job"]["exit_code"] == 0
    receipt = collect(client, "bucket", "jobs/job/task", tmp_path / "durable", require_complete=True)

    assert receipt["complete"] is True
    assert {row["path"] for row in receipt["artifacts"]} == {"sweep.json", "stdout.log"}
    assert list((tmp_path / "durable/mechanobio-sweep/frontier-cpu-20261031-01").glob("*/sweep.json"))[0].read_text() == '{"runs": 2}\n'
    assert Path(receipt["receipt_path"]).is_file()


def test_partial_snapshot_is_collectable_and_not_reported_complete(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    (output / "segment-01.csv").write_text("x,y\n0,1\n")
    fake = FakeGCS()
    client = GCS(lambda: "test-token", fake)
    partial = run_record(exit_code=None)
    partial["finished_utc"] = None
    result = upload_run(client, "bucket", "jobs/job/segment-01", output, partial, complete=False)
    assert result["complete"] is False
    with pytest.raises(ValueError, match="partial"):
        collect(client, "bucket", "jobs/job/segment-01", tmp_path / "durable", require_complete=True)
    receipt = collect(client, "bucket", "jobs/job/segment-01", tmp_path / "durable")
    assert receipt["complete"] is False
    assert receipt["job"]["exit_code"] is None


def test_empty_progress_snapshot_writes_receipt(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    fake = FakeGCS()
    client = GCS(lambda: "test-token", fake)
    record = run_record(exit_code=None)
    record["finished_utc"] = None
    upload_run(client, "bucket", "jobs/job/empty", output, record, complete=False)

    receipt = collect(client, "bucket", "jobs/job/empty", tmp_path / "durable")
    assert receipt["complete"] is False
    assert receipt["artifacts"] == []
    assert Path(receipt["receipt_path"]).is_file()


def test_parent_prefix_collects_latest_immutable_snapshot(tmp_path):
    fake = FakeGCS()
    client = GCS(lambda: "test-token", fake)
    first = tmp_path / "first"
    first.mkdir()
    (first / "segment.json").write_text('{"segment": 1}')
    upload_run(client, "bucket", "jobs/job/task/segment-01", first, run_record())
    second = tmp_path / "second"
    second.mkdir()
    (second / "segment.json").write_text('{"segment": 2}')
    upload_run(client, "bucket", "jobs/job/task/segment-02", second, run_record())

    receipt = collect(client, "bucket", "jobs/job/task", tmp_path / "durable", require_complete=True)
    assert receipt["prefix"] == "jobs/job/task/segment-02"
    saved = list((tmp_path / "durable/mechanobio-sweep/frontier-cpu-20261031-01").glob("*/segment.json"))
    assert [p.read_text() for p in saved] == ['{"segment": 2}']


def test_collector_detects_corrupted_object(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    (output / "result.json").write_text("original")
    fake = FakeGCS()
    client = GCS(lambda: "test-token", fake)
    upload_run(client, "bucket", "jobs/job/task", output, run_record())
    object_name = next(name for name in fake.objects if "/objects/" in name)
    fake.objects[object_name]["data"] = b"tampered"
    with pytest.raises(ValueError, match="SHA mismatch|size mismatch|SHA-256 mismatch"):
        collect(client, "bucket", "jobs/job/task", tmp_path / "durable")


def test_paths_and_records_reject_traversal_and_secret_material(tmp_path):
    with pytest.raises(ValueError):
        safe_relpath("../credentials.json")
    with pytest.raises(ValueError):
        safe_relpath("C:/private.txt")
    output = tmp_path / "output"
    output.mkdir()
    fake = FakeGCS()
    client = GCS(lambda: "test-token", fake)
    record = run_record()
    record["parameters"]["api_key"] = "must-not-be-exported"
    with pytest.raises(ValueError, match="non-secret"):
        upload_run(client, "bucket", "jobs/job/task", output, record)
    assert fake.objects == {}


def test_export_refuses_symlinked_output(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("private")
    (output / "linked.txt").symlink_to(outside)
    with pytest.raises(ValueError, match="symlinks"):
        upload_run(GCS(lambda: "token", FakeGCS()), "bucket", "jobs/job/task", output, run_record())


def test_download_reads_at_most_cap_plus_one_bytes():
    response = Response(body=b"oversized")
    client = GCS(lambda: "test-token", lambda req, timeout=60: response)
    with pytest.raises(ValueError, match="collection limit"):
        client.download("bucket", "prefix/object", max_bytes=3)
    assert response.read_sizes == [4]


def test_large_artifact_download_streams_in_bounded_chunks(tmp_path):
    payload = b"abc123\n" * 400_000
    response = Response(body=payload)
    client = GCS(lambda: "test-token", lambda req, timeout=60: response)
    destination = tmp_path / "nested/output.bin"
    digest, size = client.download_to_path("bucket", "prefix/object", destination, len(payload),
                                           hashlib.sha256(payload).hexdigest())
    assert size == len(payload)
    assert digest == hashlib.sha256(payload).hexdigest()
    assert destination.read_bytes() == payload
    assert all(0 < n <= 1024 * 1024 for n in response.read_sizes)


def test_streaming_download_removes_oversized_partial_file(tmp_path):
    response = Response(body=b"oversized")
    client = GCS(lambda: "test-token", lambda req, timeout=60: response)
    destination = tmp_path / "nested/output.bin"
    with pytest.raises(ValueError, match="collection limit"):
        client.download_to_path("bucket", "prefix/object", destination, 3, "0" * 64)
    assert not destination.exists()
    assert list(destination.parent.glob(".gcs-download-*")) == []
