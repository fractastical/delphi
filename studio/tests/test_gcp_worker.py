import hashlib
import json
from pathlib import Path

import pytest

from frontier_compute import gcp_worker


def spec():
    return {"vm": "frontier-cpu-20261031-01", "task_id": "controlled-cfd", "vcpus": 16,
            "memory_gb": 48, "runtime_s": 79200, "export_interval_s": 1800,
            "argv": ["python3", "entry.py"], "source_sha256": "0" * 64}


def test_whole_task_has_memory_process_cpu_and_runtime_caps():
    args = gcp_worker.systemd_argv(spec(), Path("/src"), Path("/out"))
    for bound in ("MemoryMax=48G", "MemorySwapMax=0", "TasksMax=256", "RuntimeMaxSec=79200",
                  "KillMode=control-group", "CPUQuota=1600%"):
        assert bound in args
    assert args[-3:] == ["--", "python3", "entry.py"]


def test_metadata_refuses_credentials_and_unbounded_task():
    request = spec()
    request["env"] = {"GCP_TOKEN": "must-not-embed"}
    with pytest.raises(ValueError, match="Credentials"):
        gcp_worker.validate(request)
    request = spec()
    request["runtime_s"] = 999999
    with pytest.raises(ValueError, match="runtime"):
        gcp_worker.validate(request)


def test_packet_changed_after_freeze_never_becomes_bootable_metadata(tmp_path):
    packet, exporter, dest = (tmp_path / name for name in ("packet", "exporter", "startup"))
    packet.write_bytes(b"frozen packet")
    exporter.write_bytes(b"uploader")
    request = spec()
    with pytest.raises(ValueError, match="hash mismatch"):
        gcp_worker.build(request, packet, exporter, dest)
    assert not dest.exists()
    request["source_sha256"] = hashlib.sha256(packet.read_bytes()).hexdigest()
    receipt = gcp_worker.build(request, packet, exporter, dest)
    assert receipt["startup_sha256"] == hashlib.sha256(dest.read_bytes()).hexdigest()
    assert receipt["bytes"] < 250000
    assert b"frozen packet" not in dest.read_bytes()


def test_export_snapshot_labels_running_outputs_partial(monkeypatch, tmp_path):
    monkeypatch.setattr(gcp_worker, "ROOT", tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "actual.json").write_text('{"measured": 3}')
    request = {**spec(), "source_commit": "frozen-source", "bucket": "private-bucket"}
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        record = json.loads(Path(argv[argv.index("--record") + 1]).read_text())
        assert record["exit_code"] is None and record["finished_utc"] is None
        snapshot = Path(argv[argv.index("--output-dir") + 1])
        assert (snapshot / "actual.json").read_bytes() == (out / "actual.json").read_bytes()
        return type("Result", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(gcp_worker.subprocess, "run", fake_run)
    assert gcp_worker.export_snapshot(request, out, None, "2026-11-01T00:00:00Z") == 0
    assert "--partial" in calls[0]
