import json
import os
import subprocess

import pytest

from frontier_adapters import materials_import as mi
from frontier_adapters import run_bundles as rb
from frontier_adapters.tests.test_run_bundles import ROOT, pgstore  # noqa: F401

COMMIT = "f1796ecfd043b6bc89b9571771f8e568ba6ff754"
D = os.path.join(ROOT, "frontier_adapters", "examples", "materials_formlabs")
needs = pytest.mark.skipif(subprocess.run(["git", "-C", ROOT, "cat-file", "-e", COMMIT + "^{commit}"], capture_output=True).returncode != 0, reason="source commit absent")


def bundle():
    return json.load(open(os.path.join(D, "bundle.materials.frontier-bundle-0.1.json")))


@needs
def test_shape_and_honesty():
    b = bundle()
    k = [r["kind"] for r in b["records"]]
    assert (k.count("Claim"), k.count("Action"), k.count("Evidence")) == (4, 0, 4)
    ev = {r["id"]: r["payload"] for r in b["records"] if r["kind"] == "Evidence"}
    assert {p["evidence_kind"] for p in ev.values()} == {"source_assessment"}
    assert ev["run-materials-evidence-tough1500"]["relation"] == "qualifies" and "NO source sha256" in ev["run-materials-evidence-tough1500"]["method"]
    t = json.dumps(b)
    assert "not recompute" in t and "No Frontier measurement" in t and "measured_print_mass_kg\": 0" not in t


@needs
def test_proposed_members_carry_no_bridge_and_resolve_to_bundle_records():
    p = json.load(open(os.path.join(D, "proposed-members.json")))
    have = {(r["id"], r["version"]) for r in bundle()["records"]}
    assert len(p["members"]) == 4 and all(m["causal_bridge"] == "none_declared" and (m["ref"]["id"], m["ref"]["version"]) in have for m in p["members"])
    assert "acceptance" in " ".join(p["not_claimed"])


@needs
def test_a_card_cell_that_disagrees_with_its_conversion_is_refused(tmp_path):
    d = str(tmp_path)
    subprocess.run(f"git -C {ROOT} archive {COMMIT} data/materials | tar -x -C {d}", shell=True, check=True)
    g = lambda *a: subprocess.run(["git", "-C", d, *a], check=True, capture_output=True, text=True, env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e.org", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e.org"}).stdout.strip()  # noqa: E731
    g("init", "-q"); g("add", "-A"); g("commit", "-q", "-m", "b")
    rb.materials_chain(d, g("rev-parse", "HEAD"))                                      # positive control
    path = os.path.join(d, "data/materials/source-cell-check.json")
    j = json.load(open(path)); j["checks"][2]["converted_value"] += 1.0; json.dump(j, open(path, "w"))
    g("add", "-A"); g("commit", "-q", "-m", "m")
    with pytest.raises(Exception):
        rb.materials_chain(d, g("rev-parse", "HEAD"))


@needs
def test_frozen_output_is_reproduced(tmp_path):
    subprocess.run(["python3", "-m", "frontier_adapters.materials_import", "--repo", ROOT, "--source-commit", COMMIT, "--out", str(tmp_path)], check=True, capture_output=True, cwd=ROOT)
    for n in sorted(os.listdir(tmp_path)):
        assert open(os.path.join(D, n), "rb").read() == open(tmp_path / n, "rb").read(), n
    assert sorted(n for n in os.listdir(D) if n != "README.md") == sorted(os.listdir(tmp_path))


@needs
def test_bundle_imports_into_an_ephemeral_store_with_zero_forks(pgstore):  # noqa: F811
    out = pgstore.import_bundle("test-only-local-token-for-alice", "materials-import", bundle())
    assert len(out["inserted"]) == 8 and out["forks"] == []
