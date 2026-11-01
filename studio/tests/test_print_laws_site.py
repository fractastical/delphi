"""The website must not attach grounding to altered or unindexed print bytes."""
import json

from scripts import build_site


def setup_index(tmp_path, monkeypatch, rows):
    monkeypatch.setattr(build_site, "ROOT", tmp_path)
    path = tmp_path / "artifacts/print-law-index.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"schema": "frontier.print-law-index/1", "files": rows}))
    return {"groups": [{"files": [{"href": "artifacts/part.stl", "sha256": "a" * 64, "format": "STL"}]}]}


def test_grounding_binds_to_published_file_hash(tmp_path, monkeypatch):
    downloads = setup_index(tmp_path, monkeypatch, [{"path": "artifacts/part.stl", "sha256": "b" * 64}])
    out = {}
    result = build_site.print_laws(build_site.Inputs(), out, downloads)
    assert result["data"] is None
    assert result["refused"] == ["artifacts/part.stl"]
    assert out == {}


def test_missing_and_duplicate_print_grounding_are_refused(tmp_path, monkeypatch):
    rows = [{"path": "artifacts/part.stl", "sha256": "a" * 64}] * 2
    downloads = setup_index(tmp_path, monkeypatch, rows)
    downloads["groups"][0]["files"].append({"href": "artifacts/unmapped.stl", "sha256": "c" * 64, "format": "STL"})
    result = build_site.print_laws(build_site.Inputs(), {}, downloads)
    assert result["data"] is None
    assert "artifacts/unmapped.stl" in result["refused"]
    assert "index schema or cardinality" in result["refused"]


def test_valid_index_is_published_and_fingerprinted(tmp_path, monkeypatch):
    rows = [{"path": "artifacts/part.stl", "sha256": "a" * 64}]
    downloads = setup_index(tmp_path, monkeypatch, rows)
    inputs, out = build_site.Inputs(), {}
    result = build_site.print_laws(inputs, out, downloads)
    assert result["data"]["files"] == rows
    assert result["refused"] == []
    assert "artifacts/print-law-index.json" in inputs.seen
    assert build_site.digest_bytes(out["@" + result["href"]]) == result["sha256"]
