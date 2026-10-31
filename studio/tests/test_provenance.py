"""Artifact declarations and executable reuse must survive the actual store boundary."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from conftest import TOKENS, action, claim, evidence
from frontier.models import ArtifactRef, Draft, Record, make_record, ref
from frontier.store import Conflict, Missing


def artifact(**changes):
    return dict(title="Software control output", uri="urn:sha256:" + "a" * 64,
                sha256="a" * 64, byte_size=17, media_type="application/json",
                role="output", availability="unavailable", **changes)


def test_artifact_identity_and_credentials():
    base = artifact()
    ArtifactRef.model_validate(base)
    for fields in ({"uri": "urn:sha256:" + "b" * 64},
                   {"uri": "file:///home/worker/output.json"},
                   {"uri": "https://user:secret@example.org/output"},
                   {"uri": "https://example.org/output?token=secret"},
                   {"availability": "downloadable"}, {"byte_size": True},
                   {"byte_size": -1}, {"sha256": "not-a-digest"}):
        with pytest.raises(ValidationError):
            ArtifactRef.model_validate(base | fields)
    ArtifactRef.model_validate(base | {"uri": "https://example.org/artifacts/output.json", "availability": "downloadable"})


def test_old_record_bytes_and_digest_are_preserved(store):
    old = make_record(Draft.model_validate(claim(store)), "2026-10-31T18:00:00Z")
    assert "origin" not in old["payload"]
    assert Record.model_validate(old).model_dump() == old
    assert make_record(Draft.model_validate(claim(store)), old["created_at"]) == old


def test_shared_claim_two_action_evidence_chains_and_export(stores):
    store, other = stores("node-a"), stores("node-b")
    shared = store.submit(TOKENS["alice"], "shared", claim(store, "shared"))["record"]
    actions = []
    for i in range(2):
        draft = action(store, ref(shared))
        draft["id"] = f"action-{i}"
        draft["payload"]["inputs"] = [ref(shared)]
        saved = store.submit(TOKENS["alice"], f"action-{i}", draft)["record"]
        actions.append(saved)
        ev = evidence(store, ref(shared))
        ev["id"] = f"result-{i}"
        ev["payload"].update(produced_by=ref(saved), relation="reproduces", artifacts=[artifact()])
        result = store.submit(TOKENS["alice"], f"result-{i}", ev)
        assert result["artifact_bytes_verified"] is False
        assert result["local_status"] == "proposed"
    with store.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM typed_edges WHERE relation='uses' AND target_version=%s",
                         (shared["version"],)).fetchone()["n"] == 2
        assert c.execute("SELECT count(*) AS n FROM typed_edges WHERE relation='produced_by'").fetchone()["n"] == 2
    # A reference is workflow provenance, not evidence that either action ran.
    assert all(store.get(ref(a))["action"]["state"] == "proposed" for a in actions)
    result_ref = ref(result["record"])
    bundle = store.export_bundle([ref(shared), ref(actions[1]), result_ref])
    other.import_bundle(TOKENS["alice"], "transfer", bundle)
    imported = other.get(result_ref)
    assert imported["record"] == result["record"]
    assert imported["local_review"]["status"] == "imported_unreviewed"


def test_false_producer_and_missing_inputs_are_refused(store):
    c1 = store.submit(TOKENS["alice"], "c1", claim(store, "c1"))["record"]
    c2 = store.submit(TOKENS["alice"], "c2", claim(store, "c2"))["record"]
    a = action(store, ref(c1))
    a["payload"]["inputs"] = [ref(c2) | {"version": "0" * 64}]
    with pytest.raises(Missing):
        store.submit(TOKENS["alice"], "missing", a)
    a["payload"]["inputs"] = [ref(c2)]
    saved = store.submit(TOKENS["alice"], "action", a)["record"]
    ev = evidence(store, ref(c2))
    ev["payload"]["produced_by"] = ref(saved)
    with pytest.raises(Conflict, match="same target"):
        store.submit(TOKENS["alice"], "wrong-producer", ev)
    bad = deepcopy(a)
    bad["payload"]["inputs"] *= 2
    with pytest.raises(ValidationError):
        Draft.model_validate(bad)
