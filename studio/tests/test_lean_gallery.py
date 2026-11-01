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

PIECES = ["engineering/formal", "engineering/formalize/lean", "engineering/constraints.py",
          "artifacts/oxygen-diffusion-rule", "projects/reuse-studies/live-projects.json",
          "artifacts/epithelial/interval-certificate", "artifacts/audits/epithelial-sweep/review.json"]


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


def test_five_recorded_families_are_current_and_only_pinned_files_are_published(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("the helper must not run any process")))
    g, out = run(ROOT)
    fams = {f["id"]: f for f in g["families"]}
    assert set(fams) == {"geometric-similarity", "unit-algebra", "cantilever-guard", "steady-oxygen-bound", "scaled-threshold-intervals"} and g["refused"] == []
    assert all(f["status"] == "current" and not f["reasons"] for f in fams.values())
    # the assembled sources that were compiled are rebuilt from the current files and equal the receipt's hashes
    assert fams["geometric-similarity"]["assembled_sources_match"] is True and fams["unit-algebra"]["assembled_sources_match"] is True
    names = {f["id"]: sorted(x["name"] for x in f["files"]) for f in fams.values()}
    assert names["geometric-similarity"] == ["GeometricSimilarity.lean", "MutantRefutations.lean", "NegativeControls.lean", "RECEIPT.json"]
    assert names["cantilever-guard"] == ["CantileverGuard.lean", "CantileverGuard_negative_corrupt_law.lean", "RECEIPT.json"]
    assert names["steady-oxygen-bound"] == ["OxygenDiffusionBound.lean", "OxygenDiffusionBound_negative_corrupt_law.lean", "lean-receipt.json"]
    published = [x["path"] for f in fams.values() for x in f["files"]]
    published += [x["path"] for f in fams.values() for x in f.get("display_artifacts", []) if x["status"] == "verified"]
    assert sorted(out) == sorted("@" + x for x in published) and all(k.startswith("@artifacts/lean-gallery/") for k in out)
    for f in fams.values():
        for x in f["files"]:
            assert hashlib.sha256(out["@" + x["path"]]).hexdigest() == x["sha256"]
    # theorems and mutants come from the real sources
    assert {"scaling_laws", "conflict_of_certificate", "wingLoading_ceiling"} <= {t["name"] for t in fams["geometric-similarity"]["theorems"]}
    assert {"convert_comp", "interval_map", "dim_compose"} <= {t["name"] for t in fams["unit-algebra"]["theorems"]}
    assert [t["name"] for t in fams["cantilever-guard"]["theorems"]] == ["cantilever_guard", "cantilever_guard_hypotheses_satisfiable", "cantilever_guard_needs_stiffness"]
    assert [b["id"] for b in fams["geometric-similarity"]["negative_blocks"]] == ["wl_k2", "mass_exponent", "stall_k2", "corrupted_certificate"]
    assert len(fams["unit-algebra"]["negative_blocks"]) == 4 and len(fams["cantilever-guard"]["negative_blocks"]) == 1
    oxygen = fams["steady-oxygen-bound"]
    assert {t["name"] for t in oxygen["theorems"] if t["kind"] == "theorem"} == set(next(s for s in L.FAMILIES if s["id"] == "steady-oxygen-bound")["positive_check_names"])
    assert len(oxygen["check_results"]) == 6 and all(x["status"] == "recorded compile passed" for x in oxygen["check_results"])
    assert [b["id"] for b in oxygen["negative_blocks"]] == ["sphere_parametric", "slab_parametric", "sphere_witness", "slab_witness"]
    assert all(b["rejected"] for b in oxygen["negative_blocks"])
    assert oxygen["contextual_reuse"]["status"] == "exact project versions matched the live registry"
    assert {x["project_id"] for x in oxygen["contextual_reuse"]["contexts"]} == {"project-epithelial-repair", "project-tissue-microcarrier"}
    assert all(set(x["parameter_status"].values()) == {"unknown"} for x in oxygen["contextual_reuse"]["contexts"])
    assert "viability threshold" in " ".join(oxygen["does_not_prove"])
    assert all(b["rejected"] for f in fams.values() for b in f["negative_blocks"])
    assert "conflict_instance" in fams["geometric-similarity"]["certificate"]["lean"] and "neg_corrupted" in fams["geometric-similarity"]["certificate"]["corrupted_lean"]
    # a statement is copied verbatim from the source, up to ':='
    t = next(t for t in fams["cantilever-guard"]["theorems"] if t["name"] == "cantilever_guard")
    assert "10 * P * L ^ 2 ≤ 3 * E * I" in t["statement"] and ":=" not in t["statement"]


@pytest.mark.parametrize("family, name", [("geometric-similarity", "engineering/formal/GeometricSimilarity.lean"), ("unit-algebra", "engineering/formal/UnitAlgebra.lean"),
                                          ("cantilever-guard", "engineering/formalize/lean/CantileverGuard.lean"),
                                          ("steady-oxygen-bound", "engineering/formalize/lean/OxygenDiffusionBound.lean"),
                                          ("scaled-threshold-intervals", "engineering/formalize/lean/ScaledThresholdIntervals.lean")])
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


def test_oxygen_receipt_is_hash_pinned_and_does_not_publish_mutated_evidence(tree):
    path = tree / "artifacts/oxygen-diffusion-rule/lean-receipt.json"
    receipt = json.loads(path.read_text())
    receipt["positive"]["only_standard_axioms"] = False
    path.write_text(json.dumps(receipt))
    gallery, out = run(tree)
    oxygen = next(x for x in gallery["families"] if x["id"] == "steady-oxygen-bound")
    assert oxygen["status"] == "stale" and oxygen["files"] == [] and "source" not in oxygen
    assert not any("steady-oxygen-bound" in key for key in out)


def test_oxygen_display_artifact_and_live_context_fail_separately_from_proof(tree):
    figure = tree / "artifacts/oxygen-diffusion-rule/geometry-control.png"
    figure.write_bytes(figure.read_bytes() + b"tamper")
    gallery, out = run(tree)
    oxygen = next(x for x in gallery["families"] if x["id"] == "steady-oxygen-bound")
    assert oxygen["status"] == "current" and len(oxygen["check_results"]) == 6
    assert next(x for x in oxygen["display_artifacts"] if x["name"] == "geometry-control.png")["status"] == "withheld"
    assert not any(key.endswith("geometry-control.png") for key in out)

    projects = tree / "projects/reuse-studies/live-projects.json"
    data = json.loads(projects.read_text())
    data["projects"][0]["target"]["version"] = "0" * 64
    projects.write_text(json.dumps(data))
    gallery, _ = run(tree)
    oxygen = next(x for x in gallery["families"] if x["id"] == "steady-oxygen-bound")
    assert oxygen["status"] == "current" and oxygen["contextual_reuse"]["contexts"] == []
    assert oxygen["contextual_reuse"]["status"] == "pinned project references could not be matched"


def test_a_changed_checker_dependency_is_stale(tree):
    p = tree / "engineering/constraints.py"
    p.write_text(p.read_text() + "\n# changed\n")
    g, _ = run(tree)
    f = next(f for f in g["families"] if f["id"] == "geometric-similarity")
    assert f["status"] == "stale" and any("constraints.py changed" in r for r in f["reasons"])


@pytest.mark.parametrize("mutation", ["empty_controls", "missing_control", "nonstandard_axiom", "contradictory_exit"])
def test_receipt_summary_cannot_hide_incomplete_or_contradictory_checks(tree, mutation):
    name = "engineering/formalize/lean/RECEIPT.json" if mutation == "contradictory_exit" else "engineering/formal/RECEIPT.json"
    path = tree / name
    data = json.loads(path.read_text())
    record = data.get("lean_checks", data)
    if mutation == "empty_controls":
        record["negative"]["each_block_rejected"] = {}
    elif mutation == "missing_control":
        record["negative"]["each_block_rejected"].pop("wl_k2")
    elif mutation == "nonstandard_axiom":
        record["positive"]["axioms_used"].append("sorryAx")
    else:
        record["negative_corrupt_law"]["exit"] = 0
    path.write_text(json.dumps(data))
    gallery, out = run(tree)
    family = "cantilever-guard" if mutation == "contradictory_exit" else "geometric-similarity"
    result = next(f for f in gallery["families"] if f["id"] == family)
    assert result["status"] == "receipt_failed" and not result["receipt"]["all_ok"]
    assert not any(f"/{family}/" in key for key in out)


def test_interval_roles_and_exact_published_dependencies():
    gallery, out = run(ROOT)
    family = next(f for f in gallery["families"] if f["id"] == "scaled-threshold-intervals")
    assert family["status"] == "current" and family["receipt"]["all_ok"]
    assert [len(group) for group in family["check_roles"].values()] == [2, 2, 2, 4]
    assert len(family["check_results"]) == 10
    assert len(family["negative_blocks"]) == 4 and all(x["rejected"] for x in family["negative_blocks"])
    assert "not ten biological laws" in family["summary"]
    assert family["source_binding"]["cells"] == 4 and family["source_binding"]["logger_witnesses"] == 8
    assert len(family["source"]) < 6000
    assert {a["name"] for a in family["display_artifacts"]} == {"source-witnesses.json", "validate.py", "reviewed-sweep-audit.json", "review.json"}
    assert all(a["status"] == "verified" and "@" + a["path"] in out for a in family["display_artifacts"])


@pytest.mark.parametrize("path", [
    "artifacts/epithelial/interval-certificate/source-witnesses.json",
    "artifacts/epithelial/interval-certificate/validate.py",
    "artifacts/epithelial/interval-certificate/reviewed-sweep-audit.json",
    "artifacts/audits/epithelial-sweep/review.json",
    "artifacts/epithelial/interval-certificate/lean-receipt.json",
])
def test_changed_interval_binding_refuses_entire_family(tree, path):
    target = tree / path
    target.write_bytes(target.read_bytes() + b" mutation")
    gallery, out = run(tree)
    family = next(f for f in gallery["families"] if f["id"] == "scaled-threshold-intervals")
    assert family["status"] != "current" and family["files"] == [] and "source" not in family
    assert not any("/scaled-threshold-intervals/" in key for key in out)
