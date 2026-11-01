"""Legacy/bypassed inserts exercise exit gates independently of the submit gate."""
from copy import deepcopy

import pytest

from conftest import TOKENS, claim, evidence
from frontier.artifacts import ArtifactIndex
from frontier.models import Draft, POLICY, digest, make_record, ref
from frontier.store import Forbidden, _unlicensed_available_content


def held(store, kind):
    target = store.submit(TOKENS["alice"], "target", claim(store))["record"]
    d = evidence(store, ref(target))
    if kind == "source":
        d["payload"]["source"].update(content_available=True, license=None)
    elif kind == "nested":
        d["payload"]["provenance"] = {"source": {"content_available": True, "license": None}}
    else:
        d["payload"]["artifacts"] = [{"title": "Fixture", "uri": "https://example.org/result.csv",
            "sha256": "a" * 64, "byte_size": 7, "media_type": "text/csv", "role": "output",
            "availability": "downloadable", "license": None}]
    return target, d


@pytest.mark.parametrize("kind", ["source", "nested", "artifact"])
def test_each_entry_and_exit_guard_independently(stores, kind):
    store, other = stores(), stores("node-b")
    target, draft = held(store, kind)
    with pytest.raises(Forbidden, match="unstated licence"):
        store.submit(TOKENS["alice"], "bad", draft)
    record = make_record(Draft.model_validate(draft))
    body = {"schema_version": "frontier-bundle-0.1", "exporting_node": store.namespace,
            "records": [target, record], "review_claims": [], "policy_version": POLICY,
            "trust": "Test fixture; not scientific evidence"}
    with pytest.raises(Forbidden, match="unstated licence"):
        other.import_bundle(TOKENS["alice"], "bad-import", body | {"bundle_sha256": digest(body)})
    # Deliberately bypass submit to model data written before the guard existed.
    # A separate get/export guard must still refuse it, even if entry protection fails.
    with store.connection() as c:
        store._insert(c, record, store._auth(c, TOKENS["alice"]))
    with pytest.raises(Forbidden, match="unstated licence"):
        store.get(ref(record))
    with pytest.raises(Forbidden, match="unstated licence"):
        store.export_bundle([ref(record)])
    if kind == "artifact":
        with pytest.raises(Forbidden, match="unstated licence"):
            ArtifactIndex(store).search()


@pytest.mark.parametrize("license", [None, "", " ", "unknown", "n/a", "all rights reserved"])
def test_unknown_and_denied_declarations_do_not_authorize_bytes(license):
    d = {"kind": "Evidence", "id": "fixture", "payload": {
        "provenance": [{"source": {"content_available": True, "license": license}}]}}
    assert _unlicensed_available_content([d]) == ["Evidence/fixture"]
    control = deepcopy(d)
    control["payload"]["provenance"][0]["source"]["content_available"] = False
    assert _unlicensed_available_content([control]) == []


def test_declared_artifact_permission_and_reference_controls(store):
    _, d = held(store, "artifact")
    d["payload"]["artifacts"][0]["license"] = "CC-BY-4.0"
    result = store.submit(TOKENS["alice"], "declared", d)["record"]
    assert store.get(ref(result))["record"] == result
    assert store.export_bundle([ref(result)])["records"] == [result]
    assert ArtifactIndex(store).search()["items"][0]["artifact_bytes_verified"] is False
    d["id"] = "pointer"
    d["payload"]["artifacts"][0].update(availability="referenced", license=None)
    store.submit(TOKENS["alice"], "pointer", d)
