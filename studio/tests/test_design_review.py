"""Structured Project design challenges remain authored, pinned Annotations."""
import pytest
from pydantic import ValidationError

from conftest import TOKENS, claim, evidence, source
from frontier.design_review import project_design_context
from frontier.http import Application
from frontier.models import Draft, make_record, ref, references
from frontier.store import Conflict, Missing, Unauthorized


def member(pin):
    return {"ref": pin, "role": "subsystem", "subsystem": "fin ray model", "scale": "organism",
            "relationship": "informs", "applicability": "Declared model scope only.", "rationale": "Exact test pin."}


def project(store, pin, id="design-project"):
    return {"namespace": store.namespace, "kind": "Project", "id": id, "issuer": "alice",
            "source_uri": "urn:frontier:design-review-test", "payload": {
                "title": "Design review fixture", "mission": "Exercise adversarial discussion records.", "source": source(),
                "limitations": ["Protocol fixture; no biological conclusion."],
                "scale_coverage": [{"scale": "organism", "status": "unknown", "note": "Test-only."}],
                "members": [member(pin)], "requirements": [], "open_questions": []}}


def challenge(store, project_ref, evidence_refs=None, member_index=0, id="challenge"):
    return {"namespace": store.namespace, "kind": "Annotation", "id": id, "issuer": "alice",
            "source_uri": "urn:frontier:design-review-test", "payload": {
                "kind": "challenge", "body": "The transfer from a static measurement to the modeled glide regime is not established.",
                "anchor": {"record": project_ref}, "design_review": {
                    "dimension": "biology", "member_index": member_index, "evidence_basis": "assumption",
                    "scope": "The exact pinned fin-ray model member and its declared organism-scale use.",
                    "evidence_refs": evidence_refs or [],
                    "alternative": "Stiffness may vary with activation, geometry, and loading rate.",
                    "falsifiable_next_test": "Measure static and cyclic deflection under declared loads and test held-out predictions."}}}


def test_annotation_extension_preserves_legacy_hash_and_requires_structured_project_challenges():
    digest = "a" * 64
    old = {"namespace": "node-a", "kind": "Annotation", "id": "ann", "issuer": "alice", "source_uri": "urn:test",
           "payload": {"kind": "challenge", "body": "Test challenge.",
                       "anchor": {"record": {"namespace": "node-a", "kind": "Project", "id": "p", "version": digest}}}}
    assert make_record(Draft.model_validate(old), "2026-10-31T12:00:00+00:00")["version"] == \
        "249f89eecfdf824e7aac99cee0d62256e87fd2b2473b5ccf46dbfe4801bbf686"
    assert "design_review" not in Draft.model_validate(old).payload
    assert Draft.model_validate(challenge_payload(old)).kind == "Annotation"


def challenge_payload(draft):
    payload = dict(draft["payload"])
    payload["design_review"] = {"dimension": "aerodynamics", "member_index": 0, "evidence_basis": "simulation",
        "scope": "A bounded model scope.", "evidence_refs": [], "alternative": "A different regime applies.",
        "falsifiable_next_test": "Measure the relevant glide regime."}
    return {**draft, "payload": payload}


@pytest.mark.parametrize("changes", [
    {"payload": {"kind": "comment", "body": "x", "anchor": {"record": {"namespace": "node-a", "kind": "Project", "id": "p", "version": "a" * 64}},
                  "design_review": {"dimension": "biology", "evidence_basis": "unknown", "scope": "x", "alternative": "y", "falsifiable_next_test": "z"}}},
    {"payload": {"kind": "challenge", "body": "x", "anchor": {"record": {"namespace": "node-a", "kind": "Claim", "id": "c", "version": "a" * 64}},
                  "design_review": {"dimension": "biology", "evidence_basis": "unknown", "scope": "x", "alternative": "y", "falsifiable_next_test": "z"}}},
    {"payload": {"kind": "challenge", "body": "x", "anchor": {"record": {"namespace": "node-a", "kind": "Project", "id": "p", "version": "a" * 64}},
                  "design_review": {"dimension": "other", "member_index": 60, "evidence_basis": "unknown", "scope": "x", "alternative": "y", "falsifiable_next_test": "z"}}},
])
def test_structured_review_shape_rejects_wrong_kind_anchor_and_unbounded_member_index(changes):
    draft = {"namespace": "node-a", "kind": "Annotation", "id": "ann", "issuer": "alice", "source_uri": "urn:test", **changes}
    with pytest.raises(ValidationError):
        Draft.model_validate(draft)


def test_review_refs_are_typed_edges_and_store_enforces_exact_project_member_and_visibility(store):
    target = store.submit(TOKENS["alice"], "claim", claim(store, id="review-target"))["record"]
    target_ref = ref(target)
    project_record = store.submit(TOKENS["alice"], "project", project(store, target_ref))["record"]
    project_ref = ref(project_record)
    cited = store.submit(TOKENS["alice"], "citation", evidence(store, target_ref))["record"]
    valid = challenge(store, project_ref, [ref(cited)])
    assert ("design_review_evidence", ref(cited)) in references({**valid, "kind": "Annotation"})
    review = store.submit(TOKENS["alice"], "valid-review", valid)["record"]
    assert review["payload"]["design_review"]["evidence_refs"] == [ref(cited)]

    revised = project(store, target_ref)
    revised["predecessor"] = project_record["version"]
    revised["payload"]["title"] = "Revised test project"
    revised_record = store.submit(TOKENS["alice"], "revise-project", revised)["record"]
    cross_version_reply = {"namespace": store.namespace, "kind": "Annotation", "id": "cross-version-reply", "issuer": "carol",
        "source_uri": "urn:frontier:design-review-test", "payload": {"kind": "comment", "body": "This answer is pinned elsewhere.",
            "anchor": {"record": ref(revised_record)}, "reply_to": ref(review)}}
    with pytest.raises(Conflict, match="same exact Project version"):
        store.submit(TOKENS["carol"], "cross-version-reply", cross_version_reply)

    out_of_range = challenge(store, project_ref, member_index=1, id="bad-index")
    with pytest.raises(Conflict, match="outside the pinned Project"):
        store.submit(TOKENS["alice"], "bad-index", out_of_range)
    missing = challenge(store, project_ref, [{"namespace": store.namespace, "kind": "Evidence", "id": "missing", "version": "f" * 64}], id="dangling")
    with pytest.raises(Missing):
        store.submit(TOKENS["alice"], "dangling", missing)

    private = evidence(store, target_ref)
    private.update(id="private-citation", visibility="private")
    private_record = store.submit(TOKENS["alice"], "private-citation", private)["record"]
    public_review = challenge(store, project_ref, [ref(private_record)], id="private-citation-review")
    with pytest.raises(Conflict, match="public Annotation may reference only public"):
        store.submit(TOKENS["alice"], "private-citation-review", public_review)


def test_context_paginates_exact_project_and_member_threads_and_http_reuses_store_auth(store):
    target = store.submit(TOKENS["alice"], "claim", claim(store, id="context-target"))["record"]
    project_record = store.submit(TOKENS["alice"], "project", project(store, ref(target)))["record"]
    project_ref = ref(project_record)
    initial = challenge(store, project_ref, id="context-challenge")
    challenge_record = store.submit(TOKENS["alice"], "context-challenge", initial)["record"]
    reply = {"namespace": store.namespace, "kind": "Annotation", "id": "context-reply", "issuer": "carol",
             "source_uri": "urn:frontier:design-review-test", "payload": {"kind": "comment", "body": "I disagree; test a second loading regime.",
                 "anchor": {"record": project_ref}, "reply_to": ref(challenge_record)}}
    store.submit(TOKENS["carol"], "context-reply", reply)
    member_note = {"namespace": store.namespace, "kind": "Annotation", "id": "member-note", "issuer": "carol",
                   "source_uri": "urn:frontier:design-review-test", "payload": {"kind": "comment", "body": "Member-specific note.",
                       "anchor": {"record": ref(target)}}}
    store.submit(TOKENS["carol"], "member-note", member_note)

    first = project_design_context(store, project_ref, limit=1)
    assert first["project"]["record"]["version"] == project_record["version"]
    assert first["pagination"]["truncated"] and first["pagination"]["next_cursor"]
    rows = first["annotations"]
    cursor = first["pagination"]["next_cursor"]
    while cursor:
        page = project_design_context(store, project_ref, limit=1, cursor=cursor)
        rows.extend(page["annotations"])
        cursor = page["pagination"]["next_cursor"]
    assert {x["record"]["id"] for x in rows} == {"context-challenge", "context-reply", "member-note"}
    reply_row = next(x for x in rows if x["record"]["id"] == "context-reply")
    assert reply_row["thread_root_ref"] == ref(challenge_record) and reply_row["member_index"] is None
    note_row = next(x for x in rows if x["record"]["id"] == "member-note")
    assert note_row["member_index"] == 0 and note_row["anchor_ref"] == ref(target)

    app = Application(store)
    with pytest.raises(Unauthorized):
        app.dispatch("/v1/design/reviews", {"draft": challenge(store, project_ref, id="unauthorized")}, None, "unauth")
    proposed = app.dispatch("/v1/design/reviews", {"draft": challenge(store, project_ref, id="http-review")}, TOKENS["alice"], "http-review")
    assert proposed["local_status"] == "proposed"
    context = app.dispatch("/v1/read/design-context", {"target": project_ref, "limit": 20}, token=None)
    assert context["project"]["record"]["version"] == project_record["version"]
    assert any(x["record"]["id"] == "http-review" for x in context["annotations"])
