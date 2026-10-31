"""The mapping keeps source assertions, simulation and unknown applicability apart (offline)."""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors.biomodels import frontier_mapping as fm  # noqa: E402
from connectors.biomodels import mapping_v2 as mv2  # noqa: E402

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
    return mv2.build()


def test_committed_mapping_is_not_stale(full):
    committed = json.loads((Path(fm.PACKAGE) / "mapping" / f"{fm.ACCESSION}.mapping.json").read_text())
    assert committed == json.loads(json.dumps(full)), "rebuild with: python -m connectors.biomodels.mapping_v2"


def test_simulated_evidence_pins_the_model_claim_and_is_never_observed(full):
    r = by_id(full)
    ev = r["orx-run-simulated-evidence"]["payload"]
    assert ev["evidence_kind"] == "simulated" and ev["target"]["version"] == r["biomodels-1047-model-behaviour"]["version"]
    assert ev["source"]["content_available"] is False and ev["source"]["license"] is None
    assert ev["provenance"]["exit_code_file"] == 0 and "action_ref" not in ev["provenance"]
    assert all(ev["provenance"]["replay"]["outputs_identical"].values())
    assert any("not independent replication" in s for s in ev["limitations"])
    assert not ABS.search(json.dumps(full))
    assert "observed" not in {x["payload"]["evidence_kind"] for x in full["records"] if x["kind"] == "Evidence"}


def test_typed_links_replace_provenance_pointers(full):
    r = by_id(full)
    ev, act = r["orx-run-simulated-evidence"]["payload"], r["biomodels-1047-replay"]["payload"]
    assert ev["relation"] == "supports" and ev["produced_by"]["id"] == "biomodels-1047-replay"
    assert ev["produced_by"]["version"] == r["biomodels-1047-replay"]["version"]
    assert [i["id"] for i in act["inputs"]] == ["biomodels-1047-source-model-claim"]
    assert act["inputs"][0]["version"] == r["biomodels-1047-source-model-claim"]["version"]
    assert r["biomodels-1047-source-assessment"]["payload"]["relation"] == "context_only"
    edges = {(e["type"], e["from"], e["to"]) for e in full["edges"]}
    assert ("uses", "biomodels-1047-replay", "biomodels-1047-source-model-claim") in edges
    assert ("produced_by", "orx-run-simulated-evidence", "biomodels-1047-replay") in edges


def test_artifacts_are_typed_digest_only_and_the_sbml_is_not_redistributed(full):
    ev = by_id(full)["orx-run-simulated-evidence"]["payload"]
    arts = ev["artifacts"]
    assert {a["role"] for a in arts} >= {"input", "output", "log", "code", "environment"}
    assert all(a["availability"] == "referenced" and a["license"] is None for a in arts)
    sbml_in = [a for a in arts if a["role"] == "input"]
    assert len(sbml_in) == 1 and sbml_in[0]["sha256"] == fm.MODEL_SHA256 and sbml_in[0]["uri"] == "https://www.biomodels.org/BIOMD0000001047"
    manifest = json.loads((Path(fm.PACKAGE) / "orx" / "artifact-manifest.json").read_text())
    assert manifest["bytes_included"] is False and manifest["hosting"]["hosted"] is False
    assert {a["sha256"] for a in manifest["artifacts"]} <= {a["sha256"] for a in arts}, "v2 keeps every artifact of the orx manifest"
    stray = [p for p in Path(fm.PACKAGE).rglob("*") if p.is_file() and p.suffix not in (".py", ".pyc") and "__pycache__" not in p.parts and b"<sbml" in p.read_bytes()[:20000]]
    assert not stray, f"raw SBML must not be committed: {stray}"


def test_negative_control_stray_sbml_would_be_detected(tmp_path):
    f = tmp_path / "x.xml"
    f.write_bytes(b'<?xml version="1.0"?><sbml level="2"/>')
    assert b"<sbml" in f.read_bytes()[:20000]


def preserved(v1, v2):
    """v2 keeps every v1 artifact and every replay hash, and changes nothing else about the Evidence."""
    keep = {(a["sha256"], a["role"]) for a in v1["payload"]["artifacts"]} <= {(a["sha256"], a["role"]) for a in v2["payload"]["artifacts"]}
    same = all(v1["payload"][k] == v2["payload"][k] for k in ("target", "evidence_kind", "relation", "produced_by", "source", "method", "context", "assumptions", "uncertainty"))
    return keep and same and v2["predecessor"] == v1["version"] and (v1["namespace"], v1["kind"], v1["id"]) == (v2["namespace"], v2["kind"], v2["id"])


def test_evidence_v2_chains_to_v1_and_preserves_the_replay_hashes(full):
    v1, v2 = full["superseded_versions"][0], by_id(full)["orx-run-simulated-evidence"]
    assert preserved(v1, v2) and v1["version"] != v2["version"]
    chain = full["chains"][0]
    assert chain["versions"] == [v1["version"], v2["version"]] and chain["head"] == v2["version"]
    receipt = json.loads((Path(fm.PACKAGE) / "receipts" / fm.ACCESSION / "receipt.json").read_text())
    kept = v2["payload"]["provenance"]["replay_hashes_preserved"]
    assert kept["model_sha256"] == fm.MODEL_SHA256 == receipt["model"]["sha256"] and kept["replay_code_sha256"] == receipt["run"]["code_sha256"]
    assert kept["csv"] == {k: v for k, v in receipt["output_sha256"].items() if k.endswith(".csv")}
    assert [r["id"] for r in full["records"]].count("orx-run-simulated-evidence") == 1, "only the head is in records"


def test_v2_links_video_poster_manifest_and_render_code_as_typed_artifacts(full):
    v2 = by_id(full)["orx-run-simulated-evidence"]["payload"]
    video = json.loads((Path(fm.PACKAGE) / "video" / "delta_notch_replay_manifest.json").read_text())
    by_sha = {(a["sha256"], a["role"]): a for a in v2["artifacts"]}
    assert (video["video"]["sha256"], "output") in by_sha and by_sha[(video["video"]["sha256"], "output")]["media_type"] == "video/mp4"
    assert (video["poster"]["sha256"], "output") in by_sha
    render_sha = mv2.hashlib.sha256((Path(fm.PACKAGE) / "render.py").read_bytes()).hexdigest()
    man_sha = mv2.hashlib.sha256((Path(fm.PACKAGE) / "video" / "delta_notch_replay_manifest.json").read_bytes()).hexdigest()
    assert (render_sha, "code") in by_sha and (man_sha, "log") in by_sha
    assert any("not produced by the replay Action" in s for s in v2["limitations"])
    assert all(a["availability"] == "referenced" and a["license"] is None for a in v2["artifacts"])


def test_negative_control_a_successor_that_drops_an_artifact_is_not_preserved(full):
    v1, v2 = full["superseded_versions"][0], by_id(full)["orx-run-simulated-evidence"]
    bad = json.loads(json.dumps(v2))
    bad["payload"]["artifacts"] = bad["payload"]["artifacts"][1:]
    assert not preserved(v1, bad)
    bad2 = json.loads(json.dumps(v2)); bad2["predecessor"] = "0" * 64
    assert not preserved(v1, bad2)
