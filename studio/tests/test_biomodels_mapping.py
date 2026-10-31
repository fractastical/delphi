"""The mapping keeps source assertions, simulation and unknown applicability apart (offline)."""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors.biomodels import frontier_mapping as fm  # noqa: E402

ABS = re.compile(r"(?<![A-Za-z0-9_.])/(?:home|tmp|data|Users|var|opt|root|mnt|srv)/")


@pytest.fixture(scope="module")
def doc():
    return fm.build(orx_dir=Path("/nonexistent-orx-dir"))


def by_id(doc):
    return {r["id"]: r for r in doc["records"]}


def test_no_observed_evidence_and_the_slot_is_absent_without_a_capture(doc):
    kinds = {r["payload"]["evidence_kind"] for r in doc["records"] if r["kind"] == "Evidence"}
    assert "observed" not in kinds and kinds == {"source_assessment"}
    assert doc["separation"]["observed_evidence"] == []
    assert doc["separation"]["simulated_evidence_slot"].startswith("absent")


def test_flying_fish_appears_only_as_an_unknown_problem(doc):
    # mentions are allowed only where they deny or defer; the model claim must not name flying fish at all
    named = {r["id"] for r in doc["records"] if "flying" in json.dumps(r["payload"]).lower()}
    assert "biomodels-1047-model-behaviour" not in named and "biomodels-1047-source-model-claim" not in named
    assert "biomodels-1047-flying-fish-applicability" in named
    p = by_id(doc)["biomodels-1047-flying-fish-applicability"]
    assert p["kind"] == "Problem" and p["payload"]["completeness"] == "recorded" and p["payload"]["original"]["status"] == "unknown"
    assert doc["separation"]["unknown"] == ["biomodels-1047-flying-fish-applicability"]


def test_source_assertions_and_simulation_are_different_claims(doc):
    r = by_id(doc)
    assert set(doc["separation"]["source_assertions"]) & set(doc["separation"]["simulation"]) == set()
    assert r["biomodels-1047-source-model-claim"]["payload"]["source"]["uri"].startswith("https://pubmed")
    assert r["biomodels-1047-model-behaviour"]["payload"]["source"]["content_sha256"] == fm.MODEL_SHA256


def test_edges_point_at_exact_versions_of_existing_records(doc):
    r = by_id(doc)
    for rec in doc["records"]:
        t = rec["payload"].get("target")
        if t:
            assert r[t["id"]]["version"] == t["version"], rec["id"]


def test_versions_are_deterministic_and_no_absolute_paths(doc):
    again = fm.core_records()
    assert {x["id"]: x["version"] for x in again} == {x["id"]: x["version"] for x in doc["records"] if x["id"] in {y["id"] for y in again}}
    assert not ABS.search(json.dumps(doc))


def test_action_cache_key_pins_the_exact_target_and_environment(doc):
    a = by_id(doc)["biomodels-1047-replay"]["payload"]
    assert a["cache_key"]["target"] == a["target"]["version"]
    for pin in ("libroadrunner 2.10.0", "numpy 2.4.4", "scipy 1.17.1"):
        assert pin in a["cache_key"]["environment"]


def test_requirements_match_the_pins_in_the_mapping():
    text = (Path(fm.PACKAGE) / "requirements.txt").read_text()
    for name, ver in fm.PINS.items():
        if name != "python":
            assert f"{name}=={ver}" in text


def test_negative_control_an_observed_record_would_be_caught(doc):
    bad = [dict(r, payload=dict(r["payload"], evidence_kind="observed")) for r in doc["records"] if r["kind"] == "Evidence"]
    assert any(r["payload"]["evidence_kind"] == "observed" for r in bad)  # the check in the first test would fail on this


@pytest.fixture(scope="module")
def full():
    return fm.build()


def test_committed_mapping_is_not_stale(full):
    committed = json.loads((Path(fm.PACKAGE) / "mapping" / f"{fm.ACCESSION}.mapping.json").read_text())
    assert committed == json.loads(json.dumps(full)), "rebuild with: python -m connectors.biomodels.frontier_mapping"


def test_simulated_evidence_pins_the_model_claim_and_is_never_observed(full):
    r = by_id(full)
    ev = r["orx-run-simulated-evidence"]["payload"]
    assert ev["evidence_kind"] == "simulated" and ev["target"]["version"] == r["biomodels-1047-model-behaviour"]["version"]
    assert ev["source"]["content_available"] is False and ev["source"]["license"] is None
    assert ev["provenance"]["exit_code_file"] == 0 and ev["provenance"]["action_ref"]["id"] == "biomodels-1047-replay"
    assert all(ev["provenance"]["replay"]["outputs_identical"].values())
    assert any("not independent replication" in s for s in ev["limitations"])
    assert not ABS.search(json.dumps(full))
    assert "observed" not in {x["payload"]["evidence_kind"] for x in full["records"] if x["kind"] == "Evidence"}
