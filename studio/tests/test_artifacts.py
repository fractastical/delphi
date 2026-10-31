from copy import deepcopy

import pytest
from pydantic import ValidationError

from conftest import TOKENS, claim, evidence
from frontier.artifacts import ArtifactIndex
from frontier.models import Draft, ref
from frontier.store import FrontierError, Unauthorized


def seed(store):
    target = store.submit(TOKENS["alice"], "c", claim(store))["record"]
    for i in range(4):
        d = evidence(store, ref(target))
        d["id"] = f"e-{i}"
        d["visibility"] = "private" if i == 3 else "public"
        d["payload"]["context"] = "geometry roundtrip fixture, not a fish experiment"
        d["payload"]["artifacts"] = [{"title": f"Mesh {i}", "uri": "urn:sha256:" + str(i) * 64,
            "sha256": str(i) * 64, "byte_size": 256, "media_type": "model/stl", "role": "geometry",
            "availability": "unavailable"}]
        store.submit(TOKENS["alice"], f"e-{i}", d)


def test_artifact_context_privacy_and_cursor(store):
    seed(store)
    index = ArtifactIndex(store)
    first = index.search("geometry", role="geometry", limit=2)
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = index.search("geometry", role="geometry", limit=2, cursor=first["next_cursor"])
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    assert {r["artifact"]["sha256"] for r in first["items"] + rest["items"]} == {str(i) * 64 for i in range(3)}
    assert len(index.search("geometry", token=TOKENS["alice"])["items"]) == 4
    item = first["items"][0]
    assert item["artifact_bytes_verified"] is False
    assert item["evidence_kind"] == "source_assessment" and item["relation"] == "unspecified"
    assert item["local_status"] == "proposed"
    with pytest.raises(FrontierError, match="changed filters"):
        index.search("different", cursor=first["next_cursor"])
    with pytest.raises(Unauthorized):
        index.search(token="invalid-token")
    assert index.search(role="code")["items"] == []
    assert index.search(evidence_kind="observed")["items"] == []


@pytest.mark.parametrize("params", [{"limit": True}, {"limit": 51}, {"query": "x" * 201},
                                       {"query": "\x00"}, {"role": "executable"}, {"cursor": "%%%%"}])
def test_artifact_query_bounds(params, store):
    with pytest.raises(FrontierError):
        ArtifactIndex(store).search(**params)


def test_question_directions_preserve_existing_contract(store):
    d = {"namespace": store.namespace, "issuer": "alice", "id": "q", "kind": "Problem", "source_uri": "urn:fixture",
         "payload": {"title": "Interface mismatch", "known_state": "A fixture only", "question": "Which input is missing?",
                     "problem_kind": "project_gap", "novelty_status": "no claim", "data_access": "fixture",
                     "completeness": "recorded", "required_capabilities": [], "downstream_uses": [],
                     "source": claim(store)["payload"]["source"], "approach": "design_goal",
                     "scales": ["organ", "organism"], "context_tags": ["glide"]}}
    saved = store.submit(TOKENS["alice"], "q", d)["record"]
    assert saved["payload"]["approach"] == "design_goal"
    assert saved["payload"]["completeness"] == "recorded"
    bad = deepcopy(d)
    bad["payload"]["scales"] = ["organ", "organ"]
    with pytest.raises(ValidationError):
        Draft.model_validate(bad)


def test_artifact_http_application_preserves_access_boundary(store):
    from frontier.http import Application
    seed(store)
    app = Application(store)
    assert len(app.dispatch("/v1/read/artifacts", {})["items"]) == 3
    assert len(app.dispatch("/v1/read/artifacts", {}, token=TOKENS["alice"])["items"]) == 4
    with pytest.raises(FrontierError):
        app.dispatch("/v1/read/artifacts", {"token": TOKENS["alice"]})
