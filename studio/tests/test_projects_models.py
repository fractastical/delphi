"""Project / Annotation wire contracts. Pure validation; no database."""
import copy
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from frontier.models import (KINDS, PAYLOADS, Annotation, Draft, Project, Ref, canonical, digest, make_record, ref,
                             references)

V = lambda c: c * 64          # a syntactically valid digest
SRC = {"uri": "https://example.org/x", "locator": None, "source_version": None, "content_sha256": None,
       "content_available": False, "access": "public reference", "license": "CC0-1.0"}
OLD_CLAIM_HASH = "bc71cf00a1cbbdabe86306ede942478ee7fa8e29120e3e5cb4fb086ac562676e"   # computed with the code BEFORE this change


def r(kind, c="a", id_=None):
    return {"namespace": "node-a", "kind": kind, "id": id_ or f"{kind.lower()}-{c}", "version": V(c)}


def member(kind="Claim", c="a", **kw):
    m = {"ref": r(kind, c), "role": "subsystem", "subsystem": "wing", "scale": "organism", "relationship": "supports",
         "applicability": "Declared: applies to the stated wing geometry only.", "rationale": "Pinned for the design."}
    m.update(kw)
    return m


def project(**kw):
    p = {"title": "Design studio project", "mission": "A design goal.", "source": SRC, "limitations": ["Not validated."],
         "scale_coverage": [{"scale": "organism", "status": "implemented_model", "note": "glide sim"},
                            {"scale": "tissue", "status": "unimplemented", "note": "no fin tissue model"}],
         "members": [member()], "requirements": [], "open_questions": []}
    p.update(kw)
    return p


def anchor(**kw):
    a = {"record": r("Claim")}
    a.update(kw)
    return a


def annotation(**kw):
    a = {"kind": "comment", "body": "A comment.", "anchor": anchor()}
    a.update(kw)
    return a


def bad(model, payload, match=None):
    with pytest.raises(ValidationError, match=match):
        model.model_validate(payload)


def test_kinds_and_payloads_are_extended_additively():
    assert KINDS[:9] == ("Problem", "Claim", "Evidence", "Assessment", "Action", "Actor", "ResourceOffer", "Interest", "Event")
    assert KINDS[9:] == ("Project", "Annotation") and {"Project", "Annotation"} <= set(PAYLOADS)
    Ref(namespace="node-a", kind="Project", id="p", version=V("a")), Ref(namespace="node-a", kind="Annotation", id="a", version=V("a"))


def test_an_old_record_keeps_its_exact_hash():
    d = Draft(namespace="node-a", kind="Claim", id="claim", issuer="alice", source_uri="https://example.org/test-protocol",
              payload={"title": "Protocol fixture, not scientific data", "statement": "A software fixture asserts a scoped statement.",
                       "context": "Protocol test only", "assumptions": ["Fixture"], "limitations": ["Not measured evidence"],
                       "source": {"uri": "https://example.org/public-dataset.csv", "locator": "row=7",
                                  "source_version": "source-release-v3", "content_sha256": "a" * 64, "content_available": False,
                                  "access": "public reference, unavailable bytes", "license": "CC0-1.0"}})
    assert make_record(d, "2026-10-31T12:00:00+00:00")["version"] == OLD_CLAIM_HASH


def test_the_model_code_hardcodes_no_organism_or_mission():
    text = (Path(__file__).resolve().parents[1] / "frontier" / "models.py").read_text().lower()
    block = text[text.index("class artifactpin"):text.index("payloads = {")]
    assert not re.search(r"fish|flying|exocoet|wing|fin\b|glide", block)


# --------------------------------------------------------------------------------------------- Project
def test_a_minimal_project_validates_and_a_member_may_be_a_gap():
    Project.model_validate(project())
    Project.model_validate(project(members=[member(role="gap", relationship="context_for", scale=None)]))
    Project.model_validate(project(members=[], open_questions=[{"text": "What is unknown?"}]))


@pytest.mark.parametrize("label,mut", [
    ("member kind Assessment", lambda p: p["members"].__setitem__(0, member("Assessment"))),
    ("member kind Project", lambda p: p["members"].__setitem__(0, member("Project"))),
    ("calibrated without calibration", lambda p: p["members"].__setitem__(0, member(causal_bridge="calibrated"))),
    ("calibration without calibrated", lambda p: p["members"].__setitem__(0, member(calibration=r("Evidence", "b")))),
    ("calibration of the wrong kind", lambda p: p["members"].__setitem__(0, member(causal_bridge="calibrated", calibration=r("Action", "b")))),
    ("artifact on a non-evidence member", lambda p: p["members"].__setitem__(0, member(artifact={"evidence": r("Evidence", "b"), "sha256": V("d")}))),
    ("artifact for a different evidence", lambda p: p["members"].__setitem__(0, member("Evidence", "a", artifact={"evidence": r("Evidence", "b"), "sha256": V("d")}))),
    ("member scale outside coverage", lambda p: p["members"].__setitem__(0, member(scale="molecular"))),
    ("repeated scale", lambda p: p["scale_coverage"].append({"scale": "organism", "status": "unknown", "note": "x"})),
    ("repeated member version", lambda p: p["members"].append(member(role="context"))),
    ("no scale coverage", lambda p: p.update(scale_coverage=[])),
    ("no limitations", lambda p: p.update(limitations=[])),
    ("repeated requirement id", lambda p: p.update(requirements=[{"id": "r1", "kind": "function", "text": "t"}] * 2)),
    ("requirement source_member out of range", lambda p: p.update(requirements=[{"id": "r1", "kind": "function", "text": "t", "source_member": 5}])),
    ("open question blocks out of range", lambda p: p.update(open_questions=[{"text": "q", "blocks": [3]}])),
    ("open question links a Claim", lambda p: p.update(open_questions=[{"text": "q", "problem": r("Claim")}])),
    ("unknown field", lambda p: p.update(status="accepted")),
    ("self-declared acceptance in a member", lambda p: p["members"][0].update(validated=True)),
])
def test_project_rejections(label, mut):
    p = copy.deepcopy(project())
    mut(p)
    bad(Project, p)


def test_a_calibrated_bridge_and_an_evidence_artifact_pin_validate():
    Project.model_validate(project(members=[
        member("Evidence", "a", artifact={"evidence": r("Evidence", "a"), "sha256": V("d")}),
        member("Claim", "c", causal_bridge="calibrated", calibration=r("Evidence", "e"), role="design")]))


def test_requirement_quantities_are_exact_decimal_strings():
    q = lambda v: {"id": "r1", "kind": "constraint", "text": "t", "quantity": {"name": "mass", "unit": "kg", "comparator": "<=", "value": v}}
    for ok in ("0.53", "-1", "1e-3", "208.9"):
        Project.model_validate(project(requirements=[q(ok)]))
    for nope in ("1/3", "NaN", "inf", "0.5kg", "", ".5", "1e", 0.53):
        bad(Project, project(requirements=[q(nope)]))


# --------------------------------------------------------------------------------------------- Annotation
@pytest.mark.parametrize("region", [
    {"type": "named_subsystem", "name": "left pectoral fin"},
    {"type": "mesh_part", "part_id": "ray_3"},
    {"type": "image_rect", "x": "0.25", "y": "0", "w": "0.5", "h": "1"},
    {"type": "equation_symbol", "symbol": "C_L", "equation_id": "lift"},
    {"type": "parameter_path", "path": "fin.tributary_width_m"},
    {"type": "parameter_path", "path": "members[3].scale"}])
def test_every_region_selector_validates(region):
    Annotation.model_validate(annotation(anchor=anchor(region=region)))


@pytest.mark.parametrize("region", [
    {"type": "image_rect", "x": "0.6", "y": "0", "w": "0.5", "h": "1"},          # x + w > 1
    {"type": "image_rect", "x": "0", "y": "0", "w": "0", "h": "1"},              # zero width
    {"type": "image_rect", "x": "-0.1", "y": "0", "w": "0.5", "h": "0.5"},
    {"type": "image_rect", "x": "1/3", "y": "0", "w": "0.5", "h": "0.5"},
    {"type": "image_rect", "x": 0.25, "y": "0", "w": "0.5", "h": "0.5"},          # a float is refused
    {"type": "image_rect", "x": "NaN", "y": "0", "w": "0.5", "h": "0.5"},
    {"type": "parameter_path", "path": "a b"}, {"type": "parameter_path", "path": "1a"},
    {"type": "parameter_path", "path": "a..b"}, {"type": "parameter_path", "path": "a." + "b." * 20 + "c"},
    {"type": "named_subsystem", "name": ""}, {"type": "unknown_kind", "name": "x"},
    {"type": "named_subsystem", "name": "x", "latitude": "1"}])
def test_region_rejections(region):
    bad(Annotation, annotation(anchor=anchor(region=region)))


def test_annotation_coherence_rules():
    edit = {"target_path": "limitations[0]", "proposed": "A better limitation.", "rationale": "Clearer."}
    Annotation.model_validate(annotation(kind="proposed_edit", proposed_edit=edit))
    bad(Annotation, annotation(kind="proposed_edit"))                              # edit kind without an edit
    bad(Annotation, annotation(kind="comment", proposed_edit=edit))                # an edit on a comment
    bad(Annotation, annotation(kind="proposed_edit", proposed_edit={**edit, "proposed": "x" * 9000}))
    bad(Annotation, annotation(kind="proposed_edit", proposed_edit={**edit, "target_path": "a b"}))
    bad(Annotation, annotation(reply_to=r("Claim")))                               # a reply pins an Annotation
    Annotation.model_validate(annotation(reply_to=r("Annotation", "b")))
    bad(Annotation, annotation(anchor=anchor(record=r("Event"))))                  # transaction receipts are not annotated
    bad(Annotation, annotation(status="resolved"))                                 # no self-declared lifecycle/acceptance
    bad(Annotation, annotation(speaker="some-agent"))                              # no pretend authorship field
    bad(Annotation, annotation(anchor=anchor(author="x")))


def test_artifact_and_frame_rules():
    ev = r("Evidence", "e")
    art = {"evidence": ev, "sha256": V("d")}
    Annotation.model_validate(annotation(anchor={"record": ev, "artifact": art,
                                                 "region": {"type": "mesh_part", "part_id": "p", "artifact_sha256": V("d")}}))
    bad(Annotation, annotation(anchor={"record": r("Claim"), "artifact": art}))              # anchored record is not that evidence
    bad(Annotation, annotation(anchor={"record": ev, "artifact": {"evidence": r("Evidence", "f"), "sha256": V("d")}}))
    bad(Annotation, annotation(anchor={"record": ev, "artifact": art, "region": {"type": "mesh_part", "part_id": "p", "artifact_sha256": V("9")}}))
    bad(Annotation, annotation(anchor={"record": ev, "artifact": {"evidence": r("Claim"), "sha256": V("d")}}))
    bad(Annotation, annotation(anchor=anchor(frame="declared_biological", region={"type": "named_subsystem", "name": "x"})))
    bad(Annotation, annotation(anchor=anchor(frame_declaration="x")))
    bad(Annotation, annotation(anchor=anchor(frame="declared_biological", frame_declaration="Coordinates are mm from the snout.")))
    Annotation.model_validate(annotation(anchor=anchor(frame="declared_biological", frame_declaration="mm from the snout",
                                                       region={"type": "named_subsystem", "name": "x"})))


def test_typed_edges_are_exact_and_explicit():
    proj = make_record(Draft(namespace="node-a", kind="Project", id="p", issuer="alice", source_uri="urn:x", payload=project(
        members=[member("Evidence", "a", artifact={"evidence": r("Evidence", "a"), "sha256": V("d")}),
                 member("Claim", "c", causal_bridge="calibrated", calibration=r("Evidence", "e"), role="design")],
        open_questions=[{"text": "q", "problem": r("Problem", "f")}])))
    rels = [(a, t["version"]) for a, t in references(proj)]
    assert rels == [("project_member", V("a")), ("project_member_artifact", V("a")), ("project_member", V("c")),
                    ("project_calibration", V("e")), ("project_open_question", V("f"))]
    ann = make_record(Draft(namespace="node-a", kind="Annotation", id="a", issuer="alice", source_uri="urn:x", payload=annotation(
        anchor={"record": r("Evidence", "e"), "artifact": {"evidence": r("Evidence", "e"), "sha256": V("d")}},
        reply_to=r("Annotation", "b"))))
    assert [(a, t["version"]) for a, t in references(ann)] == [("annotates", V("e")), ("annotates_artifact", V("e")),
                                                              ("replies_to", V("b"))]


def test_drafts_validate_through_the_shared_draft_model_and_the_digest_binds_the_payload():
    d = Draft(namespace="node-a", kind="Project", id="p", issuer="alice", source_uri="urn:x", payload=project())
    rec = make_record(d, "2026-10-31T12:00:00+00:00")
    assert rec["version"] == digest({k: v for k, v in rec.items() if k != "version"})
    with pytest.raises(ValidationError):
        Draft(namespace="node-a", kind="Project", id="p", issuer="alice", source_uri="urn:x", payload={"title": "x"})
    other = make_record(Draft(namespace="node-a", kind="Project", id="p", issuer="alice", source_uri="urn:x",
                              payload=project(title="Changed")), "2026-10-31T12:00:00+00:00")
    assert other["version"] != rec["version"]
