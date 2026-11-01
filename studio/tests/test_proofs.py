"""Recorded proof sharing never compiles or follows a caller-supplied path."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from frontier.proofs import FAMILY_IDS, MAX_SOURCE_CHARS, ProofCatalog

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lean_gallery  # noqa: E402


class Inputs:
    def __init__(self, root):
        self.root = Path(root)

    def read(self, relative):
        return (self.root / relative).read_bytes()


@pytest.fixture
def tree(tmp_path):
    for name in ["engineering/formal", "engineering/formalize/lean", "site/artifacts/lean-gallery",
                 "artifacts/oxygen-diffusion-rule"]:
        shutil.copytree(ROOT / name, tmp_path / name)
    shutil.copy2(ROOT / "engineering/constraints.py", tmp_path / "engineering/constraints.py")
    (tmp_path / "projects/reuse-studies").mkdir(parents=True)
    shutil.copy2(ROOT / "projects/reuse-studies/live-projects.json", tmp_path / "projects/reuse-studies/live-projects.json")
    out = {}
    lean_gallery.build(Inputs(tmp_path), out, root=tmp_path)
    for key, value in out.items():
        if not key.startswith("@"):
            continue
        target = tmp_path / "site" / key[1:]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
    return tmp_path


def test_summary_and_optional_source_match_actual_published_receipts_without_execution(monkeypatch, tree):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("No compiler or process allowed"))
    catalog = ProofCatalog(tree)
    result = catalog.read()
    assert {f["id"] for f in result["families"]} == set(FAMILY_IDS) and result["withheld"] == []
    assert not result["compile_executed"] and not result["biological_validation"]
    assert all("source" not in f and f["positive_exit"] == 0 and f["negative_exit"] == 1 for f in result["families"])
    assert "cantilever_guard_hypotheses_satisfiable" in result["families"][2]["theorem_names"]
    oxygen = next(f for f in result["families"] if f["id"] == "steady-oxygen-bound")
    assert len(oxygen["check_results"]) == 6 and len(oxygen["negative_control_ids"]) == 4
    assert oxygen["contextual_reuse"]["status"] == "exact project versions matched the live registry"
    assert set(oxygen["contextual_reuse"]["contexts"][0]["parameter_status"].values()) == {"unknown"}
    full = catalog.read("cantilever-guard", True, "frontier.morphoswarm.ai")
    family = full["families"][0]
    source = family["source"]
    assert len(source["text"]) <= MAX_SOURCE_CHARS and not source["truncated"]
    assert sha256(source["text"].encode()).hexdigest() == source["full_file_sha256"]
    for item in family["files"]:
        raw = (tree / "site" / item["href"]).read_bytes()
        assert sha256(raw).hexdigest() == item["sha256"] and len(raw) == item["bytes"]
        assert item["public_url"] == "https://frontier.morphoswarm.ai/" + item["href"]
    assert "/data/" not in json.dumps(full) and "/tmp/" not in json.dumps(full)
    assert all("public_url" not in f for f in catalog.read("unit-algebra", False, "user:secret@example.org/path")["families"][0]["files"])


@pytest.mark.parametrize("path,family", [
    ("engineering/formal/GeometricSimilarity.lean", "geometric-similarity"),
    ("engineering/formal/unit_algebra_checks.py", "unit-algebra"),
    ("site/artifacts/lean-gallery/cantilever-guard/CantileverGuard.lean", "cantilever-guard"),
    ("site/artifacts/lean-gallery/unit-algebra/UNIT_ALGEBRA_RECEIPT.json", "unit-algebra"),
])
def test_changed_original_dependency_or_published_bytes_withholds_family_without_cache(tree, path, family):
    catalog = ProofCatalog(tree)
    assert len(catalog.read()["families"]) == 4
    target = tree / path
    target.write_bytes(target.read_bytes() + b"\n-- mutation")
    result = catalog.read(include_source=True)
    assert family in {f["id"] for f in result["withheld"]}
    assert family not in {f["id"] for f in result["families"]}
    assert len(result["families"]) == 3


def test_receipt_mutation_cannot_introduce_an_arbitrary_file_read(tree, monkeypatch):
    target = tree / "engineering/formal/RECEIPT.json"
    data = json.loads(target.read_text())
    data["lean_checks"]["provenance"]["files"]["../../secret"] = "0" * 64
    target.write_text(json.dumps(data))
    catalog = ProofCatalog(tree)
    original = catalog.source.read
    seen = []
    def read(path):
        seen.append(path)
        return original(path)
    monkeypatch.setattr(catalog.source, "read", read)
    result = catalog.read("geometric-similarity", True)
    assert not result["families"] and len(result["withheld"]) == 1
    assert seen == ["engineering/formal/RECEIPT.json"]


def test_oxygen_receipt_path_cannot_expand_its_fixed_read_allowlist(tree, monkeypatch):
    target = tree / "artifacts/oxygen-diffusion-rule/lean-receipt.json"
    data = json.loads(target.read_text())
    data["source"]["path"] = "../../secret"
    target.write_text(json.dumps(data))
    catalog = ProofCatalog(tree)
    original = catalog.source.read
    seen = []

    def read(path):
        seen.append(path)
        return original(path)

    monkeypatch.setattr(catalog.source, "read", read)
    result = catalog.read("steady-oxygen-bound", include_source=True)
    assert not result["families"] and len(result["withheld"]) == 1
    assert seen == ["artifacts/oxygen-diffusion-rule/lean-receipt.json"]


@pytest.mark.parametrize("path,family", [
    ("site/artifacts/lean-gallery/cantilever-guard/CantileverGuard.lean", "cantilever-guard"),
    ("engineering/formalize/lean/CantileverGuard.lean", "cantilever-guard"),
    ("site/artifacts/lean-gallery/steady-oxygen-bound/geometry-control.png", "steady-oxygen-bound"),
    ("engineering/formalize/lean/OxygenDiffusionBound.lean", "steady-oxygen-bound"),
])
def test_symlink_even_to_identical_bytes_is_withheld(tree, tmp_path, path, family):
    target = tree / path
    other = tmp_path / "identical-outside-proof-source"
    other.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(other)
    result = ProofCatalog(tree).read(family, True)
    assert result["families"] == [] and len(result["withheld"]) == 1


def test_missing_family_and_invalid_request_are_bounded(tree):
    (tree / "engineering/formalize/lean/RECEIPT.json").unlink()
    result = ProofCatalog(tree).read()
    assert len(result["families"]) == 3 and result["withheld"][0]["id"] == "cantilever-guard"
    with pytest.raises(ValueError):
        ProofCatalog(tree).read("../../secret")
    with pytest.raises(ValueError):
        ProofCatalog(tree).read(include_source="true")
