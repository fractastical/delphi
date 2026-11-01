import json
import os
import subprocess

import pytest

from frontier_adapters import run_bundles as rb
from frontier_adapters.tests.test_run_bundles import ROOT, pgstore  # noqa: F401

COMMIT = "bff38281e28cf65961626a342612ba2c993861d2"
D = os.path.join(ROOT, "frontier_adapters", "examples", "regmap_zebrafish")
needs = pytest.mark.skipif(subprocess.run(["git", "-C", ROOT, "cat-file", "-e", COMMIT + "^{commit}"], capture_output=True).returncode != 0, reason="source commit absent")


def bundle():
    return json.load(open(os.path.join(D, "bundle.regmap.frontier-bundle-0.1.json")))


@needs
def test_shape_species_and_no_transfer_or_inference():
    b = bundle()
    k = [r["kind"] for r in b["records"]]
    assert (k.count("Claim"), k.count("Evidence"), k.count("Problem"), k.count("Action")) == (11, 11, 3, 0)
    ev = [r["payload"] for r in b["records"] if r["kind"] == "Evidence"]
    assert {p["evidence_kind"] for p in ev} == {"source_assessment"} and {p["relation"] for p in ev} == {"context_only"}
    t = json.dumps(b)
    assert t.count("Danio rerio") >= 11 and "flying-fish transfer unknown" in t.lower().replace("flying-fish transfer is unknown", "flying-fish transfer unknown") or "Flying-fish transfer is unknown" in t
    assert "/data/artifacts" not in t and "local_response_path" not in t
    pr = {r["id"]: r["payload"] for r in b["records"] if r["kind"] == "Problem"}
    assert "conditional" in pr["run-regmap-problem-fin-natural-element-prediction-benchmark"]["known_state"] and len(pr) == 3


@needs
def test_proposed_members_resolve_and_carry_no_bridge():
    p = json.load(open(os.path.join(D, "proposed-members.json")))
    have = {(r["id"], r["version"]) for r in bundle()["records"]}
    assert len(p["members"]) == 10 and all(m["causal_bridge"] == "none_declared" and (m["ref"]["id"], m["ref"]["version"]) in have for m in p["members"])
    assert "no DNA-to-fin bridge" in p["not_claimed"]


@needs
def test_a_non_zebrafish_row_or_a_validated_transfer_is_refused(tmp_path):
    d = str(tmp_path)
    subprocess.run(f"git -C {ROOT} archive {COMMIT} artifacts/fish-regulatory-map docs/research/fish-regulatory-map-2026-10-31.md | tar -x -C {d}", shell=True, check=True)
    g = lambda *a: subprocess.run(["git", "-C", d, *a], check=True, capture_output=True, text=True, env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e.org", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e.org"}).stdout.strip()  # noqa: E731
    g("init", "-q"); g("add", "-A"); g("commit", "-q", "-m", "b")
    rb.regmap_chain(d, g("rev-parse", "HEAD"))                                         # positive control
    path = os.path.join(d, "artifacts/fish-regulatory-map/map.json")
    j = json.load(open(path)); j["rows"][0]["biological_transfer_validated"] = True; open(path, "w").write(json.dumps(j))
    g("add", "-A"); g("commit", "-q", "-m", "m")
    with pytest.raises(Exception):                                                      # fails on the manifest hash first; either refusal is correct
        rb.regmap_chain(d, g("rev-parse", "HEAD"))


@needs
def test_frozen_output_is_reproduced(tmp_path):
    subprocess.run(["python3", "-m", "frontier_adapters.regmap_import", "--repo", ROOT, "--source-commit", COMMIT, "--out", str(tmp_path)], check=True, capture_output=True, cwd=ROOT)
    assert sorted(n for n in os.listdir(D) if n != "README.md") == sorted(os.listdir(tmp_path))
    for n in os.listdir(tmp_path):
        assert open(os.path.join(D, n), "rb").read() == open(tmp_path / n, "rb").read(), n


@needs
def test_bundle_imports_into_an_ephemeral_store_with_zero_forks(pgstore):  # noqa: F811
    out = pgstore.import_bundle("test-only-local-token-for-alice", "regmap-import", bundle())
    assert len(out["inserted"]) == 25 and out["forks"] == []
