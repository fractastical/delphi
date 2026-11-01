"""Frozen curated import set: MD continuation, genomics (verbatim) and Project v2 (additive)."""
import json
import os
import subprocess

import pytest

from frontier_adapters import engineering_manifest as em
from frontier_adapters import run_bundles as rb
from frontier_adapters.tests.test_run_bundles import ROOT, pgstore  # noqa: F401

D = os.path.join(ROOT, "frontier_adapters", "examples", "curated_import")
COMMIT, GCOMMIT = "4f4ea254ca13501ad3b0747669b6a5b03152b40e", "8cf7008933fc71897b5a397a69bddd8220f128af"
ok = lambda c: subprocess.run(["git", "-C", ROOT, "cat-file", "-e", c + "^{commit}"], capture_output=True).returncode == 0  # noqa: E731
needs = pytest.mark.skipif(not (ok(COMMIT) and ok(GCOMMIT)), reason="source commits not in this checkout")


def load(n):
    return json.load(open(os.path.join(D, n)))


def bundles():
    return {n: load(n) for n in sorted(os.listdir(D)) if n.startswith("bundle.")}


@needs
def test_md_continuation_keeps_the_three_branch_scope_and_the_false_false_true_flags():
    b = load("bundle.md_continuation.frontier-bundle-0.1.json")
    t = json.dumps(b)
    assert "NOT six independent samples" in t and "False, False, True" in t and "not a stability probability" in t
    ev = {r["id"]: r["payload"] for r in b["records"] if r["kind"] == "Evidence"}
    assert ev["run-mdc-evidence-render"]["relation"] == "context_only" and all(p["relation"] != "supports" for p in ev.values())
    assert "aijob-e00h8rra7x8ams6jyn" in t and "aijob-e00qxektzctnk69zwg" in t        # the two job ids, kept as found


@needs
def test_genomics_records_are_verbatim_with_the_authors_versions():
    src = json.loads(subprocess.check_output(["git", "-C", ROOT, "show", f"{GCOMMIT}:data/genomics/daane2021_supplement_records.json"]))["records"]
    got = load("bundle.genomics-daane2021.frontier-bundle-0.1.json")["records"]
    assert got == src and [r["kind"] for r in got].count("Evidence") == 2


@needs
def test_project_v2_is_additive_and_old_members_annotations_and_version_are_preserved():
    rec, rep = load("project-v2.record.json"), load("project-v2.report.json")
    live = json.loads(subprocess.check_output(["git", "-C", ROOT, "show", f"{COMMIT}:projects/flying-fish.live-repin.json"]))["draft"]["payload"]
    assert rec["predecessor"] == rep["predecessor_version"] == "a4953d50afab24261de62163cb5ea2d32a7dd683c509263c398bcb89d7f54038" != rec["version"]
    p = rec["payload"]
    assert p["members"][:13] == live["members"] and len(p["members"]) == 22
    assert all(p[k] == live[k] for k in ("requirements", "open_questions", "scale_coverage", "mission", "title"))
    assert p["limitations"][:len(live["limitations"])] == live["limitations"] and len(p["limitations"]) == len(live["limitations"]) + 1
    assert all(m["causal_bridge"] == "none_declared" for m in p["members"][13:]) and rep["annotations_anchored_to_old_version"] == 4
    anns = subprocess.check_output(["git", "-C", ROOT, "show", f"{COMMIT}:projects/flying-fish.design-challenges.jsonl"]).decode().splitlines()
    assert len(anns) == 4 and all(json.loads(a)["payload"]["anchor"]["record"]["version"] == rep["predecessor_version"] for a in anns)
    assert "calibrat" not in " ".join(m["rationale"].lower() for m in p["members"][13:]).replace("no fin calibration", "").replace("not calibrat", "")


@needs
def test_every_new_member_pin_resolves_to_a_record_in_the_set_or_the_imported_betse_bundle():
    imported = json.loads(subprocess.check_output(["git", "-C", ROOT, "show", f"origin/main:{rb_betse()}"])) if ok("origin/main") else None
    have = {(r["namespace"], r["kind"], r["id"], r["version"]) for b in bundles().values() for r in b["records"]}
    if imported:
        have |= {(r["namespace"], r["kind"], r["id"], r["version"]) for r in imported["records"]}
    for m in load("project-v2.record.json")["payload"]["members"][13:]:
        r = m["ref"]
        assert (r["namespace"], r["kind"], r["id"], r["version"]) in have, r


def rb_betse():
    from frontier_adapters import curated_import as ci
    return ci.IMPORTED_BETSE


@needs
def test_frozen_files_reproduce_and_hold_no_secret_text(tmp_path):
    subprocess.run(["python3", "-m", "frontier_adapters.curated_import", "--repo", ROOT, "--source-commit", COMMIT, "--genomics-commit", GCOMMIT, "--out", str(tmp_path)], check=True, capture_output=True, cwd=ROOT)
    frozen = sorted(n for n in os.listdir(D) if n != "README.md")
    assert frozen == sorted(os.listdir(tmp_path))
    for n in frozen:
        assert open(os.path.join(D, n), "rb").read() == open(tmp_path / n, "rb").read(), n
        assert rb.find_secretish(open(os.path.join(D, n)).read()) == []


@needs
def test_bundles_import_into_an_ephemeral_store_with_zero_forks(pgstore):  # noqa: F811
    for n, b in bundles().items():
        out = pgstore.import_bundle("test-only-local-token-for-alice", "ci-" + n[:40], b)
        assert len(out["inserted"]) == len(b["records"]) and out["forks"] == []
