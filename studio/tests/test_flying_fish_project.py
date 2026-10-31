"""The flying-fish mission as ONE Project on the generic schema: grounded refs, explicit gaps, re-pin to a live node."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_flying_fish_project as B  # noqa: E402

from frontier.models import Draft, Project  # noqa: E402

DRAFT = ROOT / "projects" / "flying-fish.draft.json"
WANT = {"doc-SPEC-005": "Evidence", "src-fish1990": "Evidence", "src-parkchoi2010": "Evidence", "src-davenport1992": "Evidence",
        "src-davenport2003": "Evidence", "src-daane2021": "Evidence", "src-darwin1859": "Evidence", "src-lovejoy2004": "Evidence",
        "doc-model-coupling": "Evidence", "doc-2026-10-31-kcne1-binding-ddg-STOPPED": "Evidence", "F002": "Problem",
        "F003": "Problem", "turing-wavelength": "Claim"}


def test_the_committed_draft_is_exactly_what_the_builder_produces():
    assert json.loads(DRAFT.read_text()) == json.loads(json.dumps(B.build(), sort_keys=True, ensure_ascii=False))


def test_the_draft_validates_against_the_real_contract():
    d = json.loads(DRAFT.read_text())["draft"]
    Draft.model_validate(d)
    Project.model_validate(d["payload"])
    assert d["kind"] == "Project" and d["visibility"] == "public"


def test_project_draft_does_not_depend_on_the_snapshot_that_embeds_it(monkeypatch, tmp_path):
    baseline = B.build()
    catalog = json.loads(B.CATALOG.read_text())
    catalog["snapshot"] = "a new enclosing snapshot fingerprint"
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog))
    monkeypatch.setattr(B, "CATALOG", path)
    assert B.build() == baseline


def test_every_member_ref_is_copied_verbatim_from_the_catalog_and_none_is_invented():
    cat = json.loads((ROOT / "site/data/catalog.json").read_text())
    by_id = {r["ref"]["id"]: r["ref"] for r in cat["records"]}
    d = json.loads(DRAFT.read_text())
    members = d["draft"]["payload"]["members"]
    assert {m["ref"]["id"]: m["ref"]["kind"] for m in members} == WANT
    for m in members:
        assert m["ref"] == by_id[m["ref"]["id"]]
    for q in d["draft"]["payload"]["open_questions"]:
        if q.get("problem"):
            assert q["problem"] == by_id[q["problem"]["id"]]
    assert d["grounding"]["members_grounded"] == d["grounding"]["members_in_catalog"] == len(WANT)


def test_the_builder_fails_closed_when_a_wanted_record_is_absent(monkeypatch):
    real = B.load
    def without_fish(*a):
        cat, snap, refs = real()
        refs = {k: v for k, v in refs.items() if k != "src-fish1990"}
        return cat, snap, refs
    monkeypatch.setattr(B, "load", without_fish)
    with pytest.raises(SystemExit, match="refusing to invent"):
        B.build()


def test_all_twelve_scales_are_stated_and_the_unimplemented_ones_are_explicit_gaps():
    p = json.loads(DRAFT.read_text())["draft"]["payload"]
    cov = {c["scale"]: c for c in p["scale_coverage"]}
    assert len(cov) == len(p["scale_coverage"]) == 12
    assert {s for s, c in cov.items() if c["status"] in ("unimplemented", "unknown")} == {
        "macromolecular", "subcellular", "tissue", "neural", "collective", "evolutionary"}
    assert {s for s, c in cov.items() if c["status"] == "implemented_model"} == {"organ", "organism"}
    assert "ASSUMED" in cov["organ"]["note"] and "no calibrated" in cov["organ"]["note"]
    assert "no fin-tissue model" in cov["tissue"]["note"]
    assert d_grounding()["unimplemented_or_unknown_scales"] == sorted(
        [s for s, c in cov.items() if c["status"] in ("unimplemented", "unknown")], key=[c["scale"] for c in p["scale_coverage"]].index)


def d_grounding():
    return json.loads(DRAFT.read_text())["grounding"]


def test_membership_declares_applicability_and_never_a_causal_bridge_or_pinned_artifact():
    p = json.loads(DRAFT.read_text())["draft"]["payload"]
    for m in p["members"]:
        assert m["causal_bridge"] == "none_declared" and "calibration" not in m and "artifact" not in m
        assert m["applicability"].startswith("Declared:")
    assert "artifact_pins" in d_grounding() and d_grounding()["artifact_pins"].startswith("none")
    assert any("snapshot-catalog ref" in x for x in p["limitations"])


def test_the_text_makes_no_feasibility_or_validation_claim():
    d = json.loads(DRAFT.read_text())
    text = json.dumps(d["draft"]["payload"], ensure_ascii=False)
    assert not re.search(r"\bvalidated\b|\bproves?\b|\bviable\b|\bproven\b", text, re.I)
    for sentence in re.split(r"(?<=[.;])\s+", text):
        if re.search(r"feasib", sentence, re.I):
            assert re.search(r"\b(not|no|nor|never)\b", sentence, re.I), sentence
    assert "not_established" in d["grounding"]


def test_numeric_requirements_are_exact_decimals_traced_to_the_fish_source_member():
    p = json.loads(DRAFT.read_text())["draft"]["payload"]
    fish = next(i for i, m in enumerate(p["members"]) if m["ref"]["id"] == "src-fish1990")
    nums = {r["id"]: (r["quantity"]["comparator"], r["quantity"]["value"], r["source_member"]) for r in p["requirements"] if r.get("quantity")}
    assert nums == {"req-mass-min": (">=", "0.003", fish), "req-mass-max": ("<=", "0.53", fish),
                    "req-wl-min": (">=", "11.7", fish), "req-wl-max": ("<=", "208.9", fish)}
    assert [r["kind"] for r in p["requirements"] if r["kind"] == "non_goal"] == ["non_goal"]


def test_the_schema_is_generic_a_second_project_reuses_the_same_pinned_records():
    d = json.loads(DRAFT.read_text())["draft"]
    shared = [m for m in d["payload"]["members"] if m["ref"]["id"] in ("src-fish1990", "F002")]
    other = {**d, "id": "project-another-mission", "payload": {
        "title": "A different design problem", "mission": "Unrelated goal on the same schema.", "source": d["payload"]["source"],
        "limitations": ["Illustration of reuse only."],
        "scale_coverage": [{"scale": "tissue", "status": "unknown", "note": "n/a"}, {"scale": "organism", "status": "unknown", "note": "n/a"}],
        "members": shared, "requirements": [], "open_questions": []}}
    Draft.model_validate(other)
    assert [m["ref"] for m in other["payload"]["members"]] == [m["ref"] for m in shared]


# ------------------------------------------------------------------------------------------------- live re-pin
from conftest import TOKENS, claim, evidence  # noqa: E402
from frontier.store import Missing  # noqa: E402
from frontier.models import ref  # noqa: E402


def _problem(store, id):
    from conftest import source
    return {"namespace": store.namespace, "kind": "Problem", "id": id, "issuer": "alice", "source_uri": "https://example.org/p",
            "payload": {"title": "Problem " + id, "known_state": "Fixture.", "question": "Fixture question?",
                        "problem_kind": "project_gap", "novelty_status": "fixture", "data_access": "fixture",
                        "completeness": "recorded", "required_capabilities": [], "downstream_uses": [], "source": source()}}


def _seed_live(store, skip=()):
    base = store.submit(TOKENS["alice"], "base", claim(store, id="base-claim"))["record"]
    for rid, kind in WANT.items():
        if rid in skip:
            continue
        if kind == "Claim":
            d = claim(store, id=rid)
        elif kind == "Problem":
            d = _problem(store, rid)
        else:
            d = evidence(store, ref(base))
            d["id"] = rid
        store.submit(TOKENS["alice"], "seed-" + rid, d)


def test_repin_moves_the_draft_onto_a_live_node_and_the_project_is_accepted_as_a_proposal(store):
    _seed_live(store)
    draft = json.loads(DRAFT.read_text())["draft"]
    pinned = B.repin(draft, store, TOKENS["alice"])
    assert pinned["namespace"] == store.namespace and draft["namespace"] == "snapshot"        # input is not mutated
    pinned["issuer"] = "alice"
    assert all(m["ref"]["namespace"] == store.namespace for m in pinned["payload"]["members"])
    assert not any("snapshot-catalog ref" in x for x in pinned["payload"]["limitations"])
    rec = store.submit(TOKENS["alice"], "ff", pinned)["record"]
    assert store.get(ref(rec))["local_review"]["status"] == "proposed"
    status = store.project_members(ref(rec))["members"]
    assert len(status) == len(WANT) and all(m["available"] and m["is_current"] for m in status)
    assert {x["ref"]["id"] for x in store.projects_for(status[1]["pin"])["projects"]} == {"project-flying-fish-mission"}


def test_repin_fails_closed_when_a_record_is_missing_on_the_node(store):
    _seed_live(store, skip=("F003",))
    with pytest.raises(Missing):
        B.repin(json.loads(DRAFT.read_text())["draft"], store, TOKENS["alice"])
    with pytest.raises(Missing):
        store.head_ref("Claim", "never-existed")
