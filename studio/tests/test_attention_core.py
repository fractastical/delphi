"""Vocabulary, annotation and value-of-information tests. Hand-worked expectations are explained beside each assertion.
Fixtures here are test-only inventions that exercise the code; they are not data about any real problem."""
import copy

import pytest
from pydantic import ValidationError

from attention import annotation as A, vocab, voi

H = "a" * 64
PRIOR = {"H": 0.6, "notH": 0.4}
U = {"reuse": {"H": 10, "notH": -20}, "skip": {"H": 0, "notH": 0}}


# ------------------------------------------------------------------ vocabularies
def test_store_vocabulary_is_read_from_the_store_models():
    assert vocab.STORE["problem_kind"] == ("project_gap", "computational_open_question", "sourced_field_open_problem", "resolved_scope_correction", "curated_question")
    assert vocab.STORE["completeness"] == ("recorded", "actionable")
    assert vocab.STORE["signal"] == ("following", "can_contribute", "resource_offer", "blocked_by_this")
    assert vocab.STORE["verification_status"] == ("unverified", "declared", "checked")


def test_tag_remembers_its_vocabulary_and_rejects_foreign_values():
    t = vocab.tag("frontier-store", "problem_kind", "sourced_field_open_problem")
    assert t == {"vocabulary": "frontier-store", "field": "problem_kind", "value": "sourced_field_open_problem"}
    with pytest.raises(vocab.VocabularyError):
        vocab.tag("frontier-store", "problem_kind", "field_open_problem")          # the old frontier_attention spelling is NOT a store value
    with pytest.raises(vocab.VocabularyError):
        vocab.tag("morphoswarm-register", "importance", "critical")


def test_no_silent_translation_between_vocabularies():
    assert vocab.MAPPINGS == {}
    for src in (vocab.tag("frontier-store", "problem_kind", "project_gap"), vocab.tag("morphoswarm-register", "importance", "significant")):
        with pytest.raises(vocab.NoTranslation):
            vocab.translate(src, "attention", "utility_status")


# ------------------------------------------------------------------ annotation
def target(v=H):
    return {"namespace": "node-a", "kind": "Problem", "id": "p1", "version": v}


def body(**kw):
    b = {"target": target(), "annotator_operator": "op-m", "created_at": "2026-10-31T18:00:00+00:00",
         "decisions": {"D1": {"utility_status": "declared", "description": "reuse the node under the scope", "unit": "eu", "prior": PRIOR, "utilities": U,
                              "prior_source": "declared by annotator", "utility_source": "declared by annotator"},
                       "D2": {"utility_status": "unknown", "description": "second decision"}},
         "unlocks": [{"kind": "logical_necessity", "decision_id": "D1", "independent_group": "g1", "provenance": "curator"}],
         "next_action": {"action_type": "proof", "summary": "freeze the target", "input_hashes": [H], "resource_estimate": {"unit": "compiler_calls", "amount": 40, "basis": "estimate"},
                         "stop_rule": "stop at 40 compiler calls", "acceptance_criterion": "compiled, standard axioms", "reviewer_operator": "op-r"},
         "limitations": ["illustrative fixture"]}
    b.update(kw)
    return b


def test_valid_annotation_has_a_verifiable_digest_and_tamper_is_detected():
    doc = A.make_annotation(body())
    assert A.verify(doc)["target"]["id"] == "p1"
    bad = copy.deepcopy(doc); bad["next_action"]["resource_estimate"]["amount"] = 1
    with pytest.raises(ValueError):
        A.verify(bad)


def test_unknown_utility_must_carry_no_numbers_and_declared_must_carry_all():
    b = body(); b["decisions"]["D2"]["prior"] = {"H": 1.0}
    with pytest.raises(ValidationError, match="unknown-utility decision must carry no"):
        A.make_annotation(b)
    b = body(); del b["decisions"]["D1"]["utility_source"]
    with pytest.raises(ValidationError):
        A.make_annotation(b)
    b = body(); b["decisions"]["D1"]["prior"] = {"H": 0.5, "notH": 0.4}
    with pytest.raises(ValidationError, match="prior sums"):
        A.make_annotation(b)


def test_unlock_edge_rules():
    e = {"kind": "logical_necessity", "independent_group": "g", "provenance": "p"}
    for bad in ({**e}, {**e, "decision_id": "D1", "target": target()}):
        with pytest.raises(ValidationError):
            A.make_annotation(body(unlocks=[bad]))
    with pytest.raises(ValidationError, match="no entry in decisions"):
        A.make_annotation(body(unlocks=[{**e, "decision_id": "NOPE"}]))
    with pytest.raises(ValidationError):
        A.make_annotation(body(unlocks=[{**e, "kind": "similar_to", "decision_id": "D1"}]))
    with pytest.raises(ValidationError, match="Problem or Claim"):
        A.make_annotation(body(unlocks=[{**e, "target": dict(target(), kind="Action")}]))
    assert A.make_annotation(body(unlocks=[{**e, "target": dict(target("b" * 64), id="p2")}]))["unlocks"][0]["target"]["id"] == "p2"


def test_bounded_action_needs_pinned_inputs_estimate_stop_rule_and_reviewer():
    for key, val in (("input_hashes", []), ("input_hashes", ["nothash"]), ("stop_rule", ""), ("reviewer_operator", ""), ("resource_estimate", {"unit": "x", "amount": 5, "basis": "measured"})):
        b = body(); b["next_action"][key] = val
        with pytest.raises(ValidationError):
            A.make_annotation(b)
    with pytest.raises(ValidationError, match="Problem version"):
        A.make_annotation(body(target=dict(target(), kind="Claim")))


# ------------------------------------------------------------------ value of information (hand-worked)
def test_evpi_and_evsi_hand_examples():
    # EU(reuse)=0.6*10+0.4*(-20)=-2, EU(skip)=0 -> best skip. Perfect info: 0.6*10+0.4*0 = 6 -> EVPI 6
    assert voi.best_action(PRIOR, U) == ("skip", 0.0) and voi.evpi(PRIOR, U) == pytest.approx(6.0)
    # p=0.9: EU(reuse)=9-2=7 (best); perfect info 9 -> EVPI 2 = 0.1*20, all of it in finding the bad state
    assert voi.evpi({"H": 0.9, "notH": 0.1}, U) == pytest.approx(2.0)
    # sens .8 / spec .9: after '+' joint(H)=.48, joint(notH)=.04 -> reuse 4.0 ; after '-' reuse -6 -> skip 0 ; EVSI = 4.0
    L = {"pos": {"H": .8, "notH": .1}, "neg": {"H": .2, "notH": .9}}
    assert voi.evsi(PRIOR, U, L) == pytest.approx(4.0)
    assert voi.evsi(PRIOR, U, {"x": {"H": 1.0, "notH": 1.0}}) == pytest.approx(0.0)
    with pytest.raises(voi.DecisionModelError):
        voi.evsi(PRIOR, U, {"pos": {"H": .8, "notH": .1}, "neg": {"H": .1, "notH": .9}})


def model(p, unit="eu"):
    return {"utility_status": "declared", "unit": unit, "prior": {"H": p, "notH": 1 - p}, "utilities": U, "prior_source": "s", "utility_source": "s"}


def edge(kind, d, g):
    return {"kind": kind, "decision_id": d, "independent_group": g}


def test_unlock_value_dedupes_and_never_values_unknown_utility():
    decisions = {"D1": model(0.6), "D2": model(0.9), "D3": model(0.9), "DU": {"utility_status": "unknown"}}      # EVPI 6, 2, 2, unknown
    edges = [edge("logical_necessity", "D1", "g1"), edge("empirical_relevance", "D1", "g1"), edge("logical_necessity", "D2", "g1"),
             edge("empirical_relevance", "D3", "g2"), edge("logical_necessity", "DU", "g3"), edge("proposed_connection", "D4", "g4")]
    r = voi.unlock_value(edges, decisions)
    # g1 -> max(6,2)=6 ; g2 -> 2 ; DU unknown (not valued) ; D4 proposed only. Total 8 (naive per-edge sum: 6+6+2+2=16)
    assert r["value"] == pytest.approx(8.0) and r["decisions_unknown_utility"] == ["DU"] and r["proposed_only_decisions"] == ["D4"]
    assert any("lower bound" in c for c in r["caveats"])
    assert voi.unlock_value([edge("logical_necessity", "DU", "g")], decisions)["value"] is None
    assert voi.unlock_value([edge("logical_necessity", "A", "g"), edge("logical_necessity", "B", "h")], {"A": model(0.6, "eu"), "B": model(0.9, "hours")})["value"] is None
