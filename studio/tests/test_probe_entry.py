import pytest

from frontier_compute.probe_entry import collect


def test_returns_native_failure_evidence_but_not_build_tree_or_nested_archive(tmp_path):
    work, out = tmp_path / "work", tmp_path / "out"
    for name in ("logs", "out", "build"):
        (work / name).mkdir(parents=True)
    (work / "logs/error.txt").write_text("first compiler failure")
    (work / "out/receipt.json").write_text('{"status":"COMPILE_FAIL"}')
    (work / "out/probe-return.tar.gz").write_bytes(b"redundant")
    (work / "build/large-binary").write_bytes(b"not evidence")
    rows = collect(work, out, 100)
    assert {x["path"] for x in rows} == {"logs/error.txt", "out/receipt.json"}
    assert (out / "native/out/receipt.json").read_text() == '{"status":"COMPILE_FAIL"}'


def test_refuses_native_symlink_before_copy(tmp_path):
    (tmp_path / "work/logs").mkdir(parents=True)
    (tmp_path / "private").write_text("not allowed")
    (tmp_path / "work/logs/link").symlink_to(tmp_path / "private")
    with pytest.raises(ValueError, match="symlink"):
        collect(tmp_path / "work", tmp_path / "out", 100)
    assert not (tmp_path / "out").exists()


def test_refuses_oversized_evidence_without_silent_truncation(tmp_path):
    (tmp_path / "work/logs").mkdir(parents=True)
    (tmp_path / "work/logs/error.txt").write_bytes(b"12345")
    with pytest.raises(ValueError, match="return bound"):
        collect(tmp_path / "work", tmp_path / "out", 4)
    assert not (tmp_path / "out").exists()


def test_empty_native_return_is_visible_as_empty_not_invented(tmp_path):
    assert collect(tmp_path / "work", tmp_path / "out", 100) == []


def test_nonzero_probe_exit_and_receipt_are_preserved(tmp_path, monkeypatch):
    import hashlib
    import io
    import json
    import tarfile

    from frontier_compute.probe_entry import run

    raw = b'#!/bin/bash\nmkdir -p "$1/out"\necho \'{"status":"COMPILE_FAIL"}\' > "$1/out/receipt.json"\nexit 7\n'
    archive = tmp_path / "packet.tar.gz"
    with tarfile.open(archive, "w:gz") as target:
        member = tarfile.TarInfo("run_probe.sh")
        member.size = len(raw)
        target.addfile(member, io.BytesIO(raw))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                                    "files": {"run_probe.sh": hashlib.sha256(raw).hexdigest()},
                                    "timeout_seconds": 5, "max_evidence_bytes": 100}))
    monkeypatch.setenv("COPS_OUT", str(tmp_path / "output"))
    assert run(archive, manifest) == 7
    receipt = json.loads((tmp_path / "output/probe-transport.json").read_text())
    assert receipt["native_exit_code"] == 7
    assert receipt["collection_failure"] is None
    assert len(receipt["files"]) == 1
