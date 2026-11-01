"""The Lean gallery helper: real pinned sources and receipts in, nothing run, stale or failed inputs refused."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lean_gallery as L  # noqa: E402

PIECES = ["engineering/formal", "engineering/formalize/lean", "engineering/constraints.py"]


class Ins:
    def __init__(self, root):
        self.root, self.seen = Path(root), {}

    def read(self, rel):
        b = (self.root / rel).read_bytes()
        self.seen[rel] = hashlib.sha256(b).hexdigest()
        return b


@pytest.fixture()
def tree(tmp_path):
    for p in PIECES:
        src, dst = ROOT / p, tmp_path / p
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst) if src.is_dir() else shutil.copy2(src, dst)
    return tmp_path


def run(root):
    out = {}
    return L.build(Ins(root), out, root=root), out


def test_three_recorded_families_are_current_and_only_pinned_files_are_published(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("the helper must not run any process")))
    g, out = run(ROOT)
    fams = {f["id"]: f for f in g["families"]}
    assert set(fams) == {"geometric-similarity", "unit-algebra", "cantilever-guard"} and g["refused"] == []
    assert all(f["status"] == "current" and not f["reasons"] for f in fams.values())
    # the assembled sources that were compiled are rebuilt from the current files and equal the receipt's hashes
    assert fams["geometric-similarity"]["assembled_sources_match"] is True and fams["unit-algebra"]["assembled_sources_match"] is True
    names = {f["id"]: sorted(x["name"] for x in f["files"]) for f in fams.values()}
    assert names["geometric-similarity"] == ["GeometricSimilarity.lean", "MutantRefutations.lean", "NegativeControls.lean", "RECEIPT.json"]
    assert names["cantilever-guard"] == ["CantileverGuard.lean", "CantileverGuard_negative_corrupt_law.lean", "RECEIPT.json"]
    assert sorted(out) == sorted("@" + x["path"] for f in fams.values() for x in f["files"]) and all(k.startswith("@artifacts/lean-gallery/") for k in out)
    for f in fams.values():
        for x in f["files"]:
            assert hashlib.sha256(out["@" + x["path"]]).hexdigest() == x["sha256"]
    # theorems and mutants come from the real sources
    assert {"scaling_laws", "conflict_of_certificate", "wingLoading_ceiling"} <= {t["name"] for t in fams["geometric-similarity"]["theorems"]}
    assert {"convert_comp", "interval_map", "dim_compose"} <= {t["name"] for t in fams["unit-algebra"]["theorems"]}
    assert [t["name"] for t in fams["cantilever-guard"]["theorems"]] == ["cantilever_guard", "cantilever_guard_hypotheses_satisfiable", "cantilever_guard_needs_stiffness"]
    assert [b["id"] for b in fams["geometric-similarity"]["negative_blocks"]] == ["wl_k2", "mass_exponent", "stall_k2", "corrupted_certificate"]
    assert len(fams["unit-algebra"]["negative_blocks"]) == 4 and len(fams["cantilever-guard"]["negative_blocks"]) == 1
    assert all(b["rejected"] for f in fams.values() for b in f["negative_blocks"])
    assert "conflict_instance" in fams["geometric-similarity"]["certificate"]["lean"] and "neg_corrupted" in fams["geometric-similarity"]["certificate"]["corrupted_lean"]
    # a statement is copied verbatim from the source, up to ':='
    t = next(t for t in fams["cantilever-guard"]["theorems"] if t["name"] == "cantilever_guard")
    assert "10 * P * L ^ 2 ≤ 3 * E * I" in t["statement"] and ":=" not in t["statement"]


@pytest.mark.parametrize("family, name", [("geometric-similarity", "engineering/formal/GeometricSimilarity.lean"), ("unit-algebra", "engineering/formal/UnitAlgebra.lean"),
                                          ("cantilever-guard", "engineering/formalize/lean/CantileverGuard.lean")])
def test_a_positive_receipt_with_changed_source_is_stale_and_its_files_are_not_published(tree, family, name):
    p = tree / name
    p.write_text(p.read_text() + "\n-- edited after the receipt\n")
    g, out = run(tree)
    f = next(f for f in g["families"] if f["id"] == family)
    assert f["status"] == "stale" and any("changed since the receipt" in r for r in f["reasons"])
    assert f["files"] == [] and f["theorems"] == [] and f["negative_blocks"] == [] and "source" not in f
    assert not [k for k in out if f"/{family}/" in k], "a stale family publishes nothing"
    assert family in g["refused"]


def test_a_changed_negative_fixture_makes_the_compiled_sources_unreproducible(tree):
    p = tree / "engineering/formal/NegativeControls.lean"
    p.write_text(p.read_text().replace("k ^ 2 * wingLoading", "k ^ 5 * wingLoading", 1))
    g, _ = run(tree)
    f = next(f for f in g["families"] if f["id"] == "geometric-similarity")
    assert f["status"] == "stale" and any("NegativeControls.lean changed" in r for r in f["reasons"])
    assert next(f for f in g["families"] if f["id"] == "cantilever-guard")["status"] == "current", "an unrelated family is unaffected"


def test_a_receipt_that_records_a_failed_run_or_missing_file_is_refused(tree):
    rp = tree / "engineering/formalize/lean/RECEIPT.json"
    R = json.loads(rp.read_text()); R["positive"]["exit"] = 1; rp.write_text(json.dumps(R))
    g, out = run(tree)
    f = next(f for f in g["families"] if f["id"] == "cantilever-guard")
    assert f["status"] == "receipt_failed" and f["files"] == []
    (tree / "engineering/formal/UNIT_ALGEBRA_RECEIPT.json").unlink()
    g, _ = run(tree)
    assert next(f for f in g["families"] if f["id"] == "unit-algebra")["status"] == "missing"


def test_a_changed_checker_dependency_is_stale(tree):
    p = tree / "engineering/constraints.py"
    p.write_text(p.read_text() + "\n# changed\n")
    g, _ = run(tree)
    f = next(f for f in g["families"] if f["id"] == "geometric-similarity")
    assert f["status"] == "stale" and any("constraints.py changed" in r for r in f["reasons"])
