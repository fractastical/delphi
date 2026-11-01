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
                 "artifacts/oxygen-diffusion-rule", "artifacts/epithelial/interval-certificate"]:
        shutil.copytree(ROOT / name, tmp_path / name)
    shutil.copy2(ROOT / "engineering/constraints.py", tmp_path / "engineering/constraints.py")
    (tmp_path / "projects/reuse-studies").mkdir(parents=True)
    shutil.copy2(ROOT / "projects/reuse-studies/live-projects.json", tmp_path / "projects/reuse-studies/live-projects.json")
    (tmp_path / "artifacts/audits/epithelial-sweep").mkdir(parents=True)
    shutil.copy2(ROOT / "artifacts/audits/epithelial-sweep/review.json", tmp_path / "artifacts/audits/epithelial-sweep/review.json")
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
    assert len(catalog.read()["families"]) == 5
    target = tree / path
    target.write_bytes(target.read_bytes() + b"\n-- mutation")
    result = catalog.read(include_source=True)
    assert family in {f["id"] for f in result["withheld"]}
    assert family not in {f["id"] for f in result["families"]}
    assert len(result["families"]) == 4


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
    assert len(result["families"]) == 4 and result["withheld"][0]["id"] == "cantilever-guard"
    with pytest.raises(ValueError):
        ProofCatalog(tree).read("../../secret")
    with pytest.raises(ValueError):
        ProofCatalog(tree).read(include_source="true")


def test_interval_catalog_publishes_bounded_full_source_and_roles(tree):
    result = ProofCatalog(tree).read("scaled-threshold-intervals", True, "frontier.morphoswarm.ai")
    assert result["withheld"] == [] and len(result["families"]) == 1
    family = result["families"][0]
    assert [len(names) for names in family["check_roles"].values()] == [2, 2, 2, 4]
    assert len(family["theorem_names"]) == 10 and len(family["negative_control_ids"]) == 4
    assert not family["source"]["truncated"] and len(family["source"]["text"]) == 4272
    assert {item["name"] for item in family["files"]} >= {"source-witnesses.json", "validate.py", "lean-receipt.json", "reviewed-sweep-audit.json"}
    assert "/data/" not in json.dumps(result) and "/tmp/" not in json.dumps(result)


@pytest.mark.parametrize("path", [
    "artifacts/epithelial/interval-certificate/source-witnesses.json",
    "artifacts/epithelial/interval-certificate/validate.py",
    "artifacts/epithelial/interval-certificate/reviewed-sweep-audit.json",
    "site/artifacts/lean-gallery/scaled-threshold-intervals/source-witnesses.json",
    "site/artifacts/lean-gallery/scaled-threshold-intervals/lean-receipt.json",
])
def test_interval_catalog_changed_source_or_published_dependency_is_withheld(tree, path):
    catalog = ProofCatalog(tree)
    assert catalog.read("scaled-threshold-intervals")["withheld"] == []
    target = tree / path
    target.write_bytes(target.read_bytes() + b"changed")
    result = catalog.read("scaled-threshold-intervals", True)
    assert result["families"] == [] and len(result["withheld"]) == 1


def test_interval_changed_receipt_cannot_expand_allowlist(tree, monkeypatch):
    target = tree / "artifacts/epithelial/interval-certificate/lean-receipt.json"
    receipt = json.loads(target.read_text())
    receipt["source_pins"].append({"path": "../../secret", "sha256": "0" * 64})
    target.write_text(json.dumps(receipt))
    catalog = ProofCatalog(tree)
    read = catalog.source.read
    seen = []
    def observe(path):
        seen.append(path)
        return read(path)
    monkeypatch.setattr(catalog.source, "read", observe)
    assert catalog.read("scaled-threshold-intervals")["families"] == []
    assert seen == ["artifacts/epithelial/interval-certificate/lean-receipt.json"]


@pytest.mark.parametrize('remote', [False, True])
def test_fifth_family_official_sdk_schema_and_anonymous_read(tree, monkeypatch, remote):
    import asyncio
    from types import SimpleNamespace
    from mcp.shared.memory import create_connected_server_and_client_session
    from frontier import proofs
    from frontier.mcp import make_mcp

    monkeypatch.setattr(proofs, 'ProofCatalog', lambda: ProofCatalog(tree))
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: pytest.fail('No process allowed in a proof read'))
    # No store method is exercised: this fixed public tool reads only published artifacts.
    server = make_mcp(SimpleNamespace(namespace='proof-fixture'), remote=remote, public_read=remote)

    async def exercise():
        async with create_connected_server_and_client_session(server) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            schema = tools['frontier_proofs'].inputSchema['properties']['family']
            values = next(x['enum'] for x in schema['anyOf'] if 'enum' in x)
            assert set(values) == set(FAMILY_IDS)
            assert tools['frontier_proofs'].annotations.readOnlyHint
            assert tools['frontier_get'].annotations.readOnlyHint
            result = await client.call_tool('frontier_proofs', {'family': 'scaled-threshold-intervals', 'include_source': True})
            assert not result.isError
            data = json.loads(result.content[0].text)
            assert len(data['families']) == 1 and data['withheld'] == []
            assert not data['compile_executed'] and not data['biological_validation']
            assert len(data['families'][0]['check_results']) == 10
            assert not data['families'][0]['source']['truncated']
            assert '/data/' not in json.dumps(data) and '/tmp/' not in json.dumps(data)
            target = tree / 'artifacts/epithelial/interval-certificate/source-witnesses.json'
            target.write_bytes(target.read_bytes() + b'changed')
            after = await client.call_tool('frontier_proofs', {'family': 'scaled-threshold-intervals'})
            assert not after.isError
            refused = json.loads(after.content[0].text)
            assert refused['families'] == [] and len(refused['withheld']) == 1
            assert (await client.call_tool('frontier_proofs', {'family': '../../secret'})).isError
    asyncio.run(exercise())
