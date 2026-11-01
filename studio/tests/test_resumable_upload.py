import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from urllib.parse import quote

import pytest

from frontier_compute import resumable_upload as m

NOW = datetime(2026, 11, 1, 3, 0, tzinfo=timezone.utc)


def cap():
    return {
        "schema": "frontier.resumable-capability/1",
        "bucket": "private-bucket",
        "object": "r2/state.bin",
        "max_bytes": 100,
        "created_utc": NOW.isoformat(),
        "controller_deadline_utc": (NOW + timedelta(minutes=10)).isoformat(),
        "uri": "https://storage.googleapis.com/upload/storage/v1/b/private-bucket/o?"
        "uploadType=resumable&name="
        + quote("r2/state.bin", safe="")
        + "&ifGenerationMatch=0&upload_id=SECRET_CAP",
    }


class Upload:
    def __init__(self, payload):
        self.payload, self.data, self.calls = payload, b"", []

    def __call__(self, url, method, data=None, headers=None):
        assert "Authorization" not in headers
        self.calls.append((method, len(data)))
        if data:
            self.data += data
        if len(self.data) < len(self.payload):
            return (
                308,
                {"range": "bytes=0-" + str(len(self.data) - 1)} if self.data else {},
                b"",
            )
        return (
            200,
            {},
            json.dumps(
                {
                    "bucket": "private-bucket",
                    "name": "r2/state.bin",
                    "size": str(len(self.data)),
                    "md5Hash": base64.b64encode(
                        hashlib.md5(self.data).digest()
                    ).decode(),
                    "generation": "123",
                }
            ).encode(),
        )


def test_bounded_streaming_checksum_without_auth_or_secret_receipt(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(m, "CHUNK_BYTES", 4)
    path = tmp_path / "state"
    path.write_bytes(b"0123456789")
    remote = Upload(path.read_bytes())
    result = m.upload(cap(), path, transport=remote, now=NOW)
    assert remote.data == path.read_bytes()
    assert max(n for _, n in remote.calls) == 4
    assert result["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert "SECRET_CAP" not in str(result)
    assert result["operator_download_hash_check_required"] is True


@pytest.mark.parametrize(
    "mutation", ["host", "object", "generation", "deadline", "size"]
)
def test_capability_identity_bounds(mutation):
    item = cap()
    if mutation == "host":
        item["uri"] = item["uri"].replace("storage.googleapis.com", "example.com")
    elif mutation == "object":
        item["object"] = "r2/other"
    elif mutation == "generation":
        item["uri"] = item["uri"].replace("ifGenerationMatch=0", "ifGenerationMatch=1")
    elif mutation == "deadline":
        item["controller_deadline_utc"] = NOW.isoformat()
    else:
        item["max_bytes"] = m.MAX_BYTES + 1
    with pytest.raises(ValueError):
        m.validate(item, now=NOW)


def test_cancel_reloads_private_state_and_retains_completed_session_status(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    path = private / "state.json"
    m.private_save(path, {"sessions": [{"capability": cap()}]})
    assert path.stat().st_mode & 0o777 == 0o600
    calls = []

    def cancel(url, method):
        assert method == "DELETE"
        calls.append(method)
        return 499, {}, b"SECRET_CAP"

    assert m.cancel_due(path, now=NOW, transport=cancel)["pending"] == 1
    # A separate invocation loads the persisted ledger after its deadline.
    result = m.cancel_due(path, now=NOW + timedelta(minutes=11), transport=cancel)
    assert (
        result["pending"] == 0 and len(calls) == 1 and "SECRET_CAP" not in str(result)
    )
    assert (
        m.cancel_due(path, now=NOW + timedelta(minutes=12), transport=cancel)["events"]
        == []
    )


def test_symlink_oversize_rejected_without_network(tmp_path):
    path = tmp_path / "state"
    path.write_bytes(b"x" * 101)
    with pytest.raises(ValueError):
        m.upload(cap(), path, now=NOW)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        m.upload(cap(), link, now=NOW)


def test_checksum_or_identity_mismatch_is_not_success(tmp_path):
    path = tmp_path / "state"
    path.write_bytes(b"x")
    remote = Upload(b"wrong")

    def corrupt(url, method, data=None, headers=None):
        status, h, b = remote(url, method, data, headers)
        if data:
            return (
                200,
                {},
                json.dumps(
                    {
                        "bucket": "wrong",
                        "name": "r2/state.bin",
                        "size": "1",
                        "md5Hash": "wrong",
                        "generation": "1",
                    }
                ).encode(),
            )
        return status, h, b

    with pytest.raises(ValueError, match="checksum mismatch"):
        m.upload(cap(), path, transport=corrupt, now=NOW)


def test_ack_jump_is_rejected(tmp_path):
    path = tmp_path / "state"
    path.write_bytes(b"x")
    with pytest.raises(ValueError, match="offset"):
        m.upload(
            cap(),
            path,
            transport=lambda *a: (308, {"range": "bytes=0-10000"}, b""),
            now=NOW,
        )


def test_error_redaction():
    class Broken:
        def __init__(self, *a, **k):
            pass

        def request(self, *a, **k):
            raise ValueError("SECRET_CAP")

        def close(self):
            pass

    with pytest.raises(RuntimeError) as error:
        m.request(m.validate(cap(), now=NOW), "DELETE", connection_factory=Broken)
    assert str(error.value) == "Capability transport failed: ValueError"


def test_public_state_directory_rejected(tmp_path):
    folder = tmp_path / "public"
    folder.mkdir(mode=0o755)
    with pytest.raises(ValueError, match="mode0700"):
        m.private_save(folder / "state", {})
