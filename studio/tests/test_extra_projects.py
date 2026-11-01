"""The two reuse studies: authored text, validated Project drafts and one prepared bundle stay consistent, and nothing is invented."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_extra_projects as B  # noqa: E402

from frontier.models import Draft, Project, Record, digest  # noqa: E402

IDS = ["tissue-microcarrier", "epithelial-repair"]
CATALOG = json.loads((ROOT / "site/data/catalog.json").read_text())
BY_ID = {r["ref"]["id"]: r["ref"] for r in CATALOG["records"]}      # authoritative: the catalog computed these versions
PROJ = json.loads((ROOT / "site/content/projects.json").read_text())["projects"]
EXTRA = {p["id"]: p for p in PROJ if p.get("template") == "reuse-study"}
FISH_ONLY = ["wing loading", "exocoet", "halfbeak", "candidate n1", "fish1990", "glide", "cl_max", "promoter", "enhancer"]


def test_flying_fish_stays_the_sole_featured_first_project():
    assert PROJ[0]["id"] == "flying-fish" and PROJ[0]["featured"] is True and "template" not in PROJ[0]
    assert [p["id"] for p in PROJ if p.get("featured")] == ["flying-fish"]
    assert set(EXTRA) == set(IDS) and all(p["group"] == "Reuse studies" and p["featured"] is False for p in EXTRA.values())


@pytest.mark.parametrize("pid", IDS)
def test_committed_draft_is_what_the_builder_produces(pid):
    assert json.loads((ROOT / "projects" / f"{pid}.draft.json").read_text()) == json.loads(json.dumps(B.build()[pid], sort_keys=True))


@pytest.mark.parametrize("pid", IDS)
def test_draft_validates_and_every_ref_is_the_catalogs(pid):
    d = json.loads((ROOT / "projects" / f"{pid}.draft.json").read_text())
    Draft.model_validate(d["draft"])
    Project.model_validate(d["draft"]["payload"])
    pl = d["draft"]["payload"]
    assert pl["members"] and all(m["ref"] == BY_ID[m["ref"]["id"]] and m["causal_bridge"] == "none_declared" for m in pl["members"])
    assert all(q["problem"] == BY_ID[q["problem"]["id"]] for q in pl["open_questions"] if q.get("problem"))
    assert not any(c["status"] == "implemented_model" for c in pl["scale_coverage"])      # no runner exists for either study
    assert d["grounding"]["members_grounded"] == d["grounding"]["members_in_catalog"] == len(pl["members"])


def test_builder_fails_closed_when_a_wanted_record_is_absent(monkeypatch):
    broken = {"records": [r for r in CATALOG["records"] if r["ref"]["id"] != "doc-model-coupling"]}
    p = ROOT / "projects" / ".nocoupling.json"
    p.write_text(json.dumps(broken))
    try:
        monkeypatch.setattr(B, "CATALOG", p)
        with pytest.raises(SystemExit):
            B.build()
    finally:
        p.unlink()


def test_bundle_is_a_consistent_prepared_bundle_of_exactly_the_two_projects():
    b = json.loads((ROOT / "projects/extra-projects.bundle.json").read_text())
    assert set(b) == {"schema_version", "exporting_node", "records", "review_claims", "policy_version", "trust", "bundle_sha256"}
    assert digest({k: v for k, v in b.items() if k != "bundle_sha256"}) == b["bundle_sha256"]
    recs = [Record.model_validate(r) for r in b["records"]]
    assert {r.id for r in recs} == {"project-" + i for i in IDS} and all(r.kind == "Project" for r in recs)
    for r in recs:
        assert r.payload == json.loads((ROOT / "projects" / f"{r.id[len('project-'):]}.draft.json").read_text())["draft"]["payload"]
    assert b["review_claims"] == []


@pytest.mark.parametrize("pid", IDS)
def test_authored_study_is_bounded_sourced_and_not_fish(pid):
    p = EXTRA[pid]
    assert p["live_project_id"] is None and p["runner"] is None           # no stored Project, no control surface
    assert 3 <= len(p["scales"]) <= 4 and p["endpoints"] and p["missing_couplings"] and p["open_questions"]
    ids = {s["id"] for s in p["sources"]}
    assert all(s["url"].startswith("https://") and s["read_level"] == "abstract" and s["pmid"] and s["doi"] for s in p["sources"])
    assert all(c["source"] in ids and c["quote"] and c["status"].startswith("source-reported") for c in p["claims"])
    assert all(e["falsifier"] for e in p["endpoints"])
    assert p["proposed_instruments"]["virtual"] and all("proposed" in x["status"] for k in ("virtual", "physical") for x in p["proposed_instruments"][k])
    chain0 = p["chain"][0]
    assert {k: chain0[k] for k in ("kind", "id", "version", "namespace")} == BY_ID["doc-model-coupling"]
    text = json.dumps(p).lower()
    assert not [w for w in FISH_ONLY if w in text]
    assert "verified" not in text and text.count("validated") == text.count("frog-validated mechanics")   # only the negated non-goal


def test_tools_named_by_the_studies_are_recorded_simulation_manifests():
    snap = json.loads((ROOT / "site/data/snapshot.json").read_text())
    have = {m["id"] for m in snap["simulation_manifests"]}
    named = {t["id"] for p in EXTRA.values() for t in p["tools"]}
    assert named and named <= have


def test_stored_project_label_requires_bound_record_and_current_authored_source(tmp_path, monkeypatch):
    import shutil
    import build_site as site_builder

    files = ['site/content/projects.json', 'projects/reuse-studies/live-projects.json',
             'projects/tissue-microcarrier.draft.json', 'projects/epithelial-repair.draft.json']
    for name in files:
        dest = tmp_path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    monkeypatch.setattr(site_builder, 'ROOT', tmp_path)
    result = site_builder.project_drafts(site_builder.Inputs())
    assert all(result[pid]['live_ref']['id'] == 'project-' + pid for pid in IDS)
    receipt_path = tmp_path / files[1]
    receipt = json.loads(receipt_path.read_text())
    receipt['projects'][0]['target']['version'] = '0' * 64
    receipt_path.write_text(json.dumps(receipt))
    result = site_builder.project_drafts(site_builder.Inputs())
    assert 'live_ref' not in result[receipt['projects'][0]['project']]
    source = tmp_path / files[0]
    source.write_bytes(source.read_bytes() + b'\n')
    result = site_builder.project_drafts(site_builder.Inputs())
    assert all('live_ref' not in row for row in result.values())
