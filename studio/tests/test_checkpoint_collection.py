import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import pytest

from frontier_compute.resumable_operator import collect_checkpoints


def fixture(tmp_path):
    payload = b"a coherent scientific checkpoint"
    digest = hashlib.sha256(payload).hexdigest()
    now = datetime.now(timezone.utc)
    cap = {
        "schema": "frontier.resumable-capability/1", "bucket": "private-bucket",
        "object": "owned/checkpoint-00.bin", "max_bytes": 100,
        "created_utc": now.isoformat(),
        "controller_deadline_utc": (now + timedelta(minutes=10)).isoformat(),
        "uri": "https://storage.googleapis.com/upload/storage/v1/b/private-bucket/o?"
        "uploadType=resumable&ifGenerationMatch=0&name="
        + quote("owned/checkpoint-00.bin", safe="") + "&upload_id=SECRET_CAP",
    }
    row = {"file": "R1-1.ckpt", "bytes": len(payload), "sha256": digest}
    state = {"sessions": [{"capability": cap}]}
    native = {"coherent_only_if_listed": True, "snapshots": [row]}
    receipt = dict(bucket=cap["bucket"], object=cap["object"], bytes=len(payload),
                   sha256=digest, generation="12345", create_only=True, source_snapshot=dict(row))
    external = {"schema": "frontier.external-checkpoints/1", "checkpoints": {row["file"]: receipt}}
    paths = [tmp_path / x for x in ("state.json", "native.json", "external.json")]
    return payload, paths, [state, native, external]


def write(paths, documents):
    for path, document in zip(paths, documents, strict=True):
        path.write_text(json.dumps(document))


class Downloader:
    def __init__(self, payload, corrupt=False):
        self.payload, self.calls, self.corrupt = payload, [], corrupt

    def download_to_path(self, bucket, name, path, size, digest):
        self.calls.append((bucket, name, size, digest))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.payload)
        return ("0" * 64 if self.corrupt else hashlib.sha256(self.payload).hexdigest(), len(self.payload))


def test_native_issued_object_and_downloaded_hash_all_match(tmp_path):
    payload, paths, documents = fixture(tmp_path)
    write(paths, documents)
    client = Downloader(payload)
    result = collect_checkpoints(client, *paths, tmp_path / "collected")
    assert result["all_expected_checkpoints_collected"] is True
    assert len(client.calls) == len(result["checkpoints"]) == 1
    assert result["bytes"] == len(payload)
    assert "SECRET_CAP" not in json.dumps(result)
    assert Path(result["checkpoints"][0]["local_path"]).read_bytes() == payload
    assert json.loads((tmp_path / "collected/collection-receipt.json").read_text()) == result


@pytest.mark.parametrize("mutation", ["foreign_object", "native_hash", "partial", "traversal", "unbounded", "not_coherent"])
def test_invalid_collection_refused_before_network(tmp_path, mutation):
    payload, paths, documents = fixture(tmp_path)
    state, native, external = documents
    row = native["snapshots"][0]
    receipt = external["checkpoints"]["R1-1.ckpt"]
    if mutation == "foreign_object":
        receipt["object"] = "other/checkpoint-00.bin"
    elif mutation == "native_hash":
        row["sha256"] = "0" * 64
    elif mutation == "partial":
        external["checkpoints"] = {}
    elif mutation == "traversal":
        row["file"] = "../R1-1.ckpt"
    elif mutation == "unbounded":
        state["sessions"][0]["capability"]["max_bytes"] = 1
    else:
        native["coherent_only_if_listed"] = False
    write(paths, documents)
    client = Downloader(payload)
    with pytest.raises(ValueError):
        collect_checkpoints(client, *paths, tmp_path / "collected")
    assert client.calls == []


def test_independent_rehash_failure_never_writes_success_receipt(tmp_path):
    payload, paths, documents = fixture(tmp_path)
    write(paths, documents)
    with pytest.raises(ValueError, match="downloaded bytes"):
        collect_checkpoints(Downloader(payload, corrupt=True), *paths, tmp_path / "collected")
    assert not (tmp_path / "collected/collection-receipt.json").exists()
