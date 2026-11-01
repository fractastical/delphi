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


def test_numbered_print_revisions_keep_older_downloads_and_refuse_bad_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, "ROOT", tmp_path)
    artifact = b"synthetic software fixture, not a printable mesh"
    digest = build_site.digest_bytes(artifact)
    for version in (3, 4, 10):
        directory = tmp_path / "artifacts" / f"print-v{version}"
        directory.mkdir(parents=True)
        (directory / "study.stl").write_bytes(artifact)
        form = {"id": f"fixture-v{version}", "display_scale": 0.55,
                "files": [{"kind": "stl_prop", "path": "study.stl", "sha256": digest, "bytes": len(artifact), "units": "mm"}]}
        (directory / "downloads.json").write_text(json.dumps({"schema": "frontier.print.downloads/1",
            "forms": [form], "limitations": ["Software fixture"], "printer_resin": "unknown"}))
        (directory / "manifest.json").write_text(json.dumps({"files": {"study.stl": digest}}))
    (tmp_path / "artifacts/print-v4-scratch").mkdir()
    assert [p.name for p in build_site.print_families(3)] == ["print-v10", "print-v4", "print-v3"]
    out = {}
    result = build_site.print_v3_block(build_site.Inputs(), out)
    assert [f["id"] for f in result["forms"]] == ["fixture-v10", "fixture-v4", "fixture-v3"]
    assert result["refused"] == [] and len(out) == 3
    downloads = build_site.model_downloads(build_site.Inputs(), {})
    assert len(downloads["groups"]) == 3 and not downloads["refused"]
    (tmp_path / "artifacts/print-v4/study.stl").write_bytes(b"changed")
    out = {}
    result = build_site.print_v3_block(build_site.Inputs(), out)
    assert result["refused"] == ["artifacts/print-v4/study.stl"]
    assert "@artifacts/print-v4/study.stl" not in out
