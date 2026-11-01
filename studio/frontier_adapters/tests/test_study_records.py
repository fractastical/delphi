import copy
import hashlib
import json
from pathlib import Path

import pytest

from frontier.models import Project
from frontier_adapters import study_records as sr

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "projects/reuse-studies/study-records"
RECORDS = json.loads((OUT / "records.json").read_text())
BINDINGS = json.loads((OUT / "source-bindings.json").read_text())
ATTACH = json.loads((OUT / "project-attachments.json").read_text())


def by_id(i):
    return next(r for r in RECORDS if r["id"] == i)


def test_committed_bundle_is_valid_and_rebuild_is_byte_identical():
    assert sr.validate(ROOT, RECORDS, BINDINGS) == []
    created = RECORDS[0]["created_at"]
    records, att, bindings = sr.build(ROOT, created_at=created)
    assert records == RECORDS and att == ATTACH and bindings == BINDINGS


def test_source_bytes_match_pinned_commits():
    for b in BINDINGS:
        assert b["manifest_sha256"] == b["computed_sha256"]
    for r in RECORDS:
        for art in r["payload"].get("artifacts", []):
            assert art["uri"] == "urn:sha256:" + art["sha256"] and art["availability"] == "referenced"
    # every record's source digest equals the blob at the commit and path its own uri names
    for r in RECORDS:
        src = r["payload"]["source"]
        rest = src["uri"].removeprefix(sr.REPO_URL)
        commit, path = rest.split("/", 1)
        assert commit == src["source_version"]
        assert src["content_sha256"] == hashlib.sha256(sr.Pinned(ROOT, commit).read(path)).hexdigest(), r["id"]


def test_claim_and_evidence_stay_separate_with_unknown_parameters():
    for g in ("sphere", "slab"):
        claim, lean = by_id(f"claim:oxygen-{g}-center-bound"), by_id(f"evidence:oxygen-{g}-lean")
        assert claim["kind"] == "Claim" and lean["payload"]["evidence_kind"] == "formal"
        assert lean["payload"]["target"]["id"] == claim["id"] and lean["payload"]["target"]["version"] == claim["version"]
        text = json.dumps(claim["payload"])
        assert "unknown" in text and "survival" in text  # named only as not established
    assert by_id("claim:oxygen-slab-center-bound")["payload"]["origin"] == "derived"
    assert "No slab expression is attributed" in json.dumps(by_id("claim:oxygen-slab-center-bound")["payload"])


def test_oxygen_claims_are_restricted_to_positive_consumption():
    for g in ("sphere", "slab"):
        p = by_id(f"claim:oxygen-{g}-center-bound")["payload"]
        assert "a > 0" in p["statement"] and "non-negative consumption" not in p["statement"] and "a >= 0" not in p["statement"]
        assert "zero-consumption extension is not claimed" in " ".join(p["limitations"])
        assert "for a > 0" in by_id(f"evidence:oxygen-{g}-lean")["payload"]["context"]


def test_epithelial_problem_cites_final_source_and_context_specific_22_percent():
    p = by_id("problem:epithelial-gap-closure-to-physical-time")["payload"]
    assert p["source"]["source_version"] == "66f2b95" and "6298621" in p["source"]["access"]
    ks = p["known_state"]
    assert "22.04%" in ks and "not a universal subtraction" in ks and "no mechanism contribution isolated" in ks
    assert "7 pass, 3 fail, G6 descriptive, G1b incomplete, G8 unevaluable" in ks
    assert "arithmetic floor" not in ks and "review was not final" not in ks and p["completeness"] == "recorded"
    assert "46eb7ff" not in json.dumps(RECORDS)


def test_superseded_outputs_preserved():
    old = json.loads((OUT / "superseded-adec3fe/records.json").read_text())
    assert any("a >= 0" not in json.dumps(r) and "non-negative consumption" in json.dumps(r) for r in old if r["id"].startswith("claim:oxygen"))
    assert any("46eb7ff" in json.dumps(r) for r in old)


def test_validator_rejects_stale_epithelial_and_a_ge_0():
    recs = copy.deepcopy(RECORDS)
    next(r for r in recs if r["id"] == "problem:epithelial-gap-closure-to-physical-time")["payload"]["known_state"] += " arithmetic floor"
    assert any("stale epithelial" in q for q in sr.validate(ROOT, recs, BINDINGS))
    recs = copy.deepcopy(RECORDS)
    c = next(r for r in recs if r["id"] == "claim:oxygen-sphere-center-bound")["payload"]
    c["statement"] = c["statement"].replace("positive consumption a > 0", "non-negative consumption a")
    assert any("restricted to a > 0" in q for q in sr.validate(ROOT, recs, BINDINGS))


def test_voxel_evidence_is_simulated_toy_scale_with_miss_and_nonconvergence():
    ev = by_id("evidence:voxelyze-summary")["payload"]
    assert ev["evidence_kind"] == "simulated" and ev["relation"] == "qualifies"
    assert ev["provenance"]["control_E"]["met"] is False
    assert ev["provenance"]["arm_G"]["G-coarse"]["body_lengths"] > ev["provenance"]["arm_G"]["G-fine"]["body_lengths"]
    assert by_id("evidence:voxelyze-replay")["payload"]["provenance"]["E_still_fails_frozen_bound"] is True


def test_problems_are_recorded_and_open_with_no_invented_fields():
    for i in ("problem:tissue-contractility-to-actuation", "problem:epithelial-gap-closure-to-physical-time"):
        p = by_id(i)["payload"]
        assert p["completeness"] == "recorded" and not p.get("acceptance_criteria") and not p.get("falsifiers") and p.get("next_action") is None
        assert "priority" not in p and "probability" not in p
    assert "review" in by_id("problem:epithelial-gap-closure-to-physical-time")["payload"]["known_state"]


def test_attachments_use_exact_live_project_refs_and_validate():
    live = sr.live_project_refs(ROOT)
    ids = {r["id"]: r for r in RECORDS}
    for row in ATTACH:
        name = row["project"]["id"].removeprefix("project-")
        assert row["project"] == live[name][0] and row["payload_validates_if_appended"]
        for m in row["proposed_members"]:
            assert any(r["kind"] == m["ref"]["kind"] and r["version"] == m["ref"]["version"] and r["id"] in ids for r in RECORDS)
        Project.model_validate({**live[name][1], "members": live[name][1]["members"] + row["proposed_members"]})
    tissue = next(r for r in ATTACH if r["project"]["id"] == "project-tissue-microcarrier")
    assert tissue["proposed_open_question_link"]["problem"]["id"] == "problem:tissue-contractility-to-actuation"


@pytest.mark.parametrize("mutate,expect", [
    (lambda recs, b: b[0].update(computed_sha256="0" * 64), "binding mismatch"),
    (lambda recs, b: [r for r in recs if r["id"] == "problem:tissue-contractility-to-actuation"][0]["payload"].update(falsifiers=["invented"]), "must not carry invented"),
    (lambda recs, b: [r for r in recs if r["id"] == "claim:voxelyze-toy-numerical-mechanics"][0]["payload"].update(statement="it works"), "E miss"),
    (lambda recs, b: [r for r in recs if r["id"] == "evidence:voxelyze-summary"][0]["payload"].update(evidence_kind="observed"), "simulated"),
])
def test_validator_rejects_mutations(mutate, expect):
    recs, bind = copy.deepcopy(RECORDS), copy.deepcopy(BINDINGS)
    mutate(recs, bind)
    try:
        probs = sr.validate(ROOT, recs, bind)
    except Exception as exc:  # a payload that no longer validates is also a rejection, but say which
        probs = [str(exc)]
    assert any(expect in p for p in probs), probs
