from datetime import datetime, timezone
import hashlib
from io import BytesIO

import pytest

from frontier_compute.signed_upload import upload, validate


NOW = datetime(2026, 11, 1, 2, 0, tzinfo=timezone.utc)


def capability():
    return {"method": "PUT", "bucket": "example-private", "object": "checkpoints/r2-1.bin",
            "headers": {"content-type": "application/octet-stream", "x-goog-if-generation-match": "0"},
            "url": "https://storage.googleapis.com/example-private/checkpoints/r2-1.bin?"
                   "X-Goog-Date=20261101T020000Z&X-Goog-Expires=600&"
                   "X-Goog-SignedHeaders=host%3Bcontent-type%3Bx-goog-if-generation-match&"
                   "X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Signature=PRIVATE_SIGNATURE"}


class Response(BytesIO):
    status = 200

    def getheader(self, name):
        return "1234" if name == "x-goog-generation" else None


class Connection:
    def __init__(self, host, timeout):
        self.host, self.timeout = host, timeout

    def request(self, method, path, body, headers):
        assert method == "PUT"
        assert not isinstance(body, bytes)
        assert headers["x-goog-if-generation-match"] == "0"
        self.received = body.read()
        assert int(headers["content-length"]) == len(self.received)

    def getresponse(self):
        return Response(b"not retained")

    def close(self):
        pass


def test_streaming_hash_receipt_has_no_capability(tmp_path):
    path = tmp_path / "state"
    path.write_bytes(b"immutable scientific snapshot")
    result = upload(capability(), path, 100, connection_factory=Connection, now=NOW)
    assert result["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["generation"] == "1234"
    assert "PRIVATE_SIGNATURE" not in str(result)
    assert "url" not in result


@pytest.mark.parametrize("mutation", ["host", "object", "expired", "long", "overwrite", "unsigned"])
def test_bad_capability_refused(mutation):
    item = capability()
    if mutation == "host":
        item["url"] = item["url"].replace("storage.googleapis.com", "example.com")
    elif mutation == "object":
        item["object"] = "checkpoints/other.bin"
    elif mutation == "expired":
        item["url"] = item["url"].replace("020000Z", "010000Z")
    elif mutation == "long":
        item["url"] = item["url"].replace("Expires=600", "Expires=43201")
    elif mutation == "overwrite":
        item["headers"]["x-goog-if-generation-match"] = "1"
    else:
        item["url"] = item["url"].replace("%3Bx-goog-if-generation-match", "")
    with pytest.raises(ValueError):
        validate(item, now=NOW)


def test_oversize_and_symlink_refused_before_network(tmp_path):
    path = tmp_path / "state"
    path.write_bytes(b"12345")
    with pytest.raises(ValueError, match="byte bound"):
        upload(capability(), path, 4, now=NOW)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        upload(capability(), link, 10, now=NOW)


def test_remote_and_transport_errors_never_reveal_signature(tmp_path):
    path = tmp_path / "state"
    path.write_bytes(b"state")

    class Broken(Connection):
        def request(self, method, target, body, headers):
            raise ValueError(target)

    with pytest.raises(RuntimeError) as result:
        upload(capability(), path, 100, connection_factory=Broken, now=NOW)
    assert "PRIVATE_SIGNATURE" not in str(result.value)
    assert str(result.value) == "Upload transport failed: ValueError"

    class Refused(Connection):
        def getresponse(self):
            response = Response(b"PRIVATE_SIGNATURE")
            response.status = 412
            return response

    with pytest.raises(RuntimeError, match="HTTP 412"):
        upload(capability(), path, 100, connection_factory=Refused, now=NOW)
