"""A download must match its pinned bytes and the revision it describes."""
import hashlib
import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("download_builder", Path(__file__).parents[1] / "scripts/build_site.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_bundle_rejects_changed_bytes_and_changed_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    directory = tmp_path / "artifacts/glider/test-revision"
    directory.mkdir(parents=True)
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps({"revision": "test-revision", "files": {}}))
    archive = directory / "print-set.zip"
    archive.write_bytes(b"pinned bundle fixture")
    (directory / "download.json").write_text(json.dumps({
        "path": "artifacts/glider/test-revision/print-set.zip",
        "bytes": archive.stat().st_size,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
    }))
    outputs = {}
    result = builder.model_downloads(builder.Inputs(), outputs)
    assert result["refused"] == []
    assert result["groups"][0]["files"][0]["format"] == "ZIP"
    assert "@artifacts/glider/test-revision/print-set.zip" in outputs
    archive.write_bytes(b"changed bundle bytes")
    outputs = {}
    assert builder.model_downloads(builder.Inputs(), outputs)["refused"]
    assert "@artifacts/glider/test-revision/print-set.zip" not in outputs
    archive.write_bytes(b"pinned bundle fixture")
    manifest.write_text(json.dumps({"revision": "different-revision", "files": {}}))
    assert builder.model_downloads(builder.Inputs(), {})["refused"]


def test_archived_right_fins_are_marked_withdrawn(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    directory = tmp_path / "artifacts/glider/old-revision"
    (directory / "stl").mkdir(parents=True)
    body = b"mesh fixture"
    (directory / "stl/pectoral_R.stl").write_bytes(body)
    (directory / "manifest.json").write_text(json.dumps({
        "revision": "old-revision",
        "files": {"stl/pectoral_R.stl": hashlib.sha256(body).hexdigest()},
    }))
    (directory.parent / "KNOWN_DEFECTS.json").write_text(json.dumps({
        "right_hand_print_files_are_left_parts": {"revisions": ["old-revision"]},
    }))
    result = builder.model_downloads(builder.Inputs(), {})
    assert not result["refused"]
    assert result["groups"][0]["files"][0]["withdrawn"]
    assert result["groups"][0]["warning"]
