import hashlib
from io import BytesIO

import pytest

from frontier_compute import secondary_entry as runner


def setup_response(monkeypatch, payload=b"artifact", redirect=False):
    url = runner.PUBLIC_PREFIX + "primary-runtime-inputs.tar.xz"
    spec = {"url": url, "bytes": len(payload), "archive_sha256": hashlib.sha256(payload).hexdigest()}

    class Response(BytesIO):
        status = 200

        def geturl(self):
            return "https://elsewhere.invalid/file" if redirect else url

    monkeypatch.setattr(runner, "urlopen", lambda *args, **kwargs: Response(payload))
    return spec


def test_public_input_receipt_binds_actual_bytes(monkeypatch, tmp_path):
    spec = setup_response(monkeypatch)
    out = tmp_path / "archive"
    runner.fetch_inputs(spec, out)
    assert out.read_bytes() == b"artifact"
    spec["archive_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash"):
        runner.fetch_inputs(spec, tmp_path / "changed")
    assert not (tmp_path / "changed").exists()


def test_input_size_and_redirect_fail_closed(monkeypatch, tmp_path):
    spec = setup_response(monkeypatch)
    spec["bytes"] -= 1
    with pytest.raises(ValueError, match="bytes"):
        runner.fetch_inputs(spec, tmp_path / "archive")
    spec = setup_response(monkeypatch, redirect=True)
    with pytest.raises(ValueError, match="redirect"):
        runner.fetch_inputs(spec, tmp_path / "archive")


def test_other_hosts_and_unbounded_inputs_are_never_fetched(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid request reached network")

    monkeypatch.setattr(runner, "urlopen", forbidden)
    with pytest.raises(ValueError, match="route"):
        runner.fetch_inputs({"url": "https://elsewhere.invalid/weights.tar.xz"}, tmp_path / "archive")
    with pytest.raises(ValueError, match="budget"):
        runner.fetch_inputs({"url": runner.PUBLIC_PREFIX + "input.tar.xz", "bytes": 12_000_001}, tmp_path / "archive")
