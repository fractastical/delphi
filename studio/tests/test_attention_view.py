"""View, rankings and action ledger on hand-built records (built with the store's own make_record so shapes are real).
Everything here is a test-only fixture, not data about any real problem."""
import copy

import pytest

from attention import annotation as A, rank, view
from attention.ledger import action_ledger
from frontier.models import Draft, POLICY, make_record, ref

NS = "node-a"
SRC = {"uri": None, "locator": None, "source_version": None, "content_sha256": None, "content_available": False, "access": "test fixture", "license": None}
T = "2026-10-31T17:00:00+00:00"
NOW = "2026-10-31T18:00:00+00:00"


def rec(kind, id, payload, created=T, issuer="alice", predecessor=None):
    d = Draft(namespace=NS, kind=kind, id=id, issuer=issuer, source_uri="urn:test", predecessor=predecessor, payload=payload)
    return make_record(d, created_at=created)


def problem(id, *, actionable=False, labels=None, **kw):
    p = {"title": id, "known_state": "k", "question": f"question {id}", "problem_kind": "sourced_field_open_problem", "novelty_status": "unchecked",
         "data_access": "none", "completeness": "actionable" if actionable else "recorded", "required_capabilities": [], "downstream_uses": ["prose use"],
         "source": SRC}
    if actionable:
        p.update(acceptance_criteria=["a"], falsifiers=["f"], next_action="do it", cost_stop_bounds="stop at 10")
    if labels:
        p["original"] = {"register_record": {"importance": {"value": labels[0]}, "tractability": {"value": labels[1]}}}
    p.update(kw)
    return rec("Problem", id, p)


def action(pr, id="act1"):
    return rec("Action", id, {"target": ref(pr), "title": "t", "acceptance_criteria": ["x"], "required_capabilities": [], "cost_stop_bounds": "free text bound",
                              "cache_key": {"target": pr["version"], "input": "i", "code": "c", "model": "m", "environment": "e", "parameters": "p", "scope": "s", "acceptance_policy": POLICY}})


_n = [0]


def event(etype, target, actor="w1", operator="op-w", at="2026-10-31T17:30:00+00:00", details=None, id=None):
    _n[0] += 1
    return rec("Event", id or f"ev-{_n[0]}", {"event_type": etype, "target": ref(target), "actor": actor, "operator": operator, "witnessed_at": at, "details": details or {}}, created=at)


def assessment(pr, decision):
    from frontier.models import DIMENSIONS
    dims = {d: {"status": "passed", "reviewer": "bob", "rationale": "fixture", "evidence_links": []} for d in DIMENSIONS}
    return rec("Assessment", f"asm-{pr['id']}", {"target": ref(pr), "decision": decision, "dimensions": dims, "independence_rationale": "fixture", "limitations": ["fixture"]}, issuer="bob")


def annot(pr, **kw):
    b = {"target": ref(pr), "annotator_operator": "op-m", "created_at": T,
         "decisions": {"D1": {"utility_status": "declared", "description": "d", "unit": "eu", "prior": {"H": .6, "notH": .4},
                              "utilities": {"reuse": {"H": 10, "notH": -20}, "skip": {"H": 0, "notH": 0}}, "prior_source": "declared", "utility_source": "declared"},
                       "DU": {"utility_status": "unknown", "description": "no model"}},
         "unlocks": [{"kind": "logical_necessity", "decision_id": "D1", "independent_group": "g1", "provenance": "curator"},
                     {"kind": "empirical_relevance", "decision_id": "DU", "independent_group": "g2", "provenance": "curator"}],
         "limitations": ["fixture"]}
    b.update(kw)
    return A.make_annotation(b)


@pytest.fixture
def world():
    pa = problem("PA", actionable=True)
    pb = problem("PB", labels=("foundational", "near-term"))
    pc = problem("PC", labels=("specialist", "long-term"))
    pd = problem("PD", labels=("significant", "medium-term"))
    act = action(pa)
    evs = [event("action_ready", act, actor="coord", operator="op-c", at="2026-10-31T17:10:00+00:00"),
           event("action_leased", act, at="2026-10-31T17:20:00+00:00", details={"lease_id": "L1", "lease_until": "2026-10-31T19:00:00+00:00"}),
           event("action_running", act, at="2026-10-31T17:25:00+00:00")]
    return {"pa": pa, "pb": pb, "pc": pc, "pd": pd, "act": act, "events": evs, "records": [pa, pb, pc, pd, act]}


def V(w, annotations=(), extra=()):
    return view.build_view(w["records"] + list(extra), w["events"], list(annotations), NOW)


def row(v, id):
    return next(r for r in v["rows"] if r["ref"]["id"] == id)


def test_view_without_annotations_reports_unknown_not_a_guess(world):
    v = V(world)
    r = row(v, "PB")
    assert r["store"]["completeness"] == {"vocabulary": "frontier-store", "field": "completeness", "value": "recorded"}
    assert r["store"]["downstream_uses_untyped"] == ["prose use"] and r["typed_unlocks"] == [] and r["typed_next_action"] is None
    assert r["utility"]["status"] == "unknown" and r["annotation"]["status"] == "none"
    assert r["register_labels"]["importance"]["vocabulary"] == "morphoswarm-register"
    assert any(w["field"] == "frontier-store.completeness" and "refuses an Action" in w["effect"] for w in r["why_priority"])


def test_applied_annotation_gives_typed_edges_bounded_cost_and_declared_evpi(world):
    v = V(world, [annot(world["pa"], next_action=None) | {}])
    r = row(v, "PA")
    # D1: EVPI 6 (hand-worked in test_attention_core); DU unknown and listed, so the value is a LOWER BOUND
    assert r["annotation"]["status"] == "applied" and r["utility"]["status"] == "partial" and r["utility"]["evpi"] == pytest.approx(6.0)
    assert r["utility"]["decisions_unknown_utility"] == ["DU"] and len(r["typed_unlocks"]) == 2
    assert any("UNKNOWN" in w["effect"] or "declared EVPI" in w["effect"] for w in r["why_priority"] if w["field"] == "annotation.decisions")


def test_bounded_cost_is_shown_as_an_estimate_and_flows_to_the_ledger(world):
    na = {"action_type": "proof", "summary": "s", "input_hashes": ["b" * 64], "resource_estimate": {"unit": "calls", "amount": 12, "basis": "estimate"},
          "stop_rule": "stop at 12", "acceptance_criterion": "ok", "reviewer_operator": "op-r"}
    v = V(world, [annot(world["pa"], next_action=na)])
    assert row(v, "PA")["bounded_cost"] == {"unit": "calls", "amount": 12.0, "basis": "estimate"}
    L = v["action_ledger"][0]
    assert L["estimate"]["amount"] == 12.0 and L["consumed"].startswith("not recorded") and L["cost_stop_bounds_text"] == "free text bound"


def test_annotation_pinned_to_an_older_version_is_stale_and_not_applied(world):
    old = problem("PA", actionable=True, title="older title")           # different content -> different version
    v = V(world, [annot(old)])
    r = row(v, "PA")
    assert r["annotation"]["status"] == "stale" and r["typed_unlocks"] == [] and r["utility"]["status"] == "unknown"


def test_a_tampered_annotation_is_rejected_and_reported_not_applied(world):
    doc = annot(world["pa"]); doc["unlocks"][0]["independent_group"] = "other"
    v = V(world, [doc])
    assert len(v["annotations_rejected"]) == 1 and row(v, "PA")["annotation"]["status"] == "none"


# ------------------------------------------------------------------ rankings (hand-worked)
def test_baseline_rankings_and_how_much_each_actually_orders(world):
    v = V(world, [annot(world["pa"])])
    R = rank.all_baselines(v["rows"])
    ids = lambda name: [t["ids"] for t in R[name]["tiers"]]
    assert ids("id_order") == [["PA"], ["PB"], ["PC"], ["PD"]] and R["id_order"]["pairs_ordered_fraction"] == 1.0
    assert ids("actionable_first") == [["PA"], ["PB", "PC", "PD"]]
    assert R["actionable_first"]["pairs_ordered_fraction"] == pytest.approx(3 / 6)           # PA vs 3 others ordered; 3 pairs inside the recorded tier tied
    # labels: PB (3,3) dominates PD (2,2) dominates PC (1,1) -> three layers ; PA has no labels -> unplaced
    assert ids("register_label_layers") == [["PB"], ["PD"], ["PC"]] and R["register_label_layers"]["unplaced"][0][0] == "PA"
    assert R["register_label_layers"]["pairs_ordered_fraction"] == pytest.approx(3 / 6)      # 3 placed items, all 3 pairs ordered, of 6 pairs overall
    assert ids("typed_unlock_groups") == [["PA"]] and len(R["typed_unlock_groups"]["unplaced"]) == 3     # PA: groups {g1,g2} = 2 ; others have no applied annotation
    assert ids("declared_evpi") == [["PA"]] and R["declared_evpi"]["tiers"][0]["rank"] == 1
    assert R["declared_evpi"]["pairs_ordered_fraction"] == 0.0                              # one placed item orders nothing


def test_register_layers_leave_equal_labels_tied(world):
    w = dict(world); w["records"] = world["records"] + [problem("PE", labels=("foundational", "near-term"))]
    R = rank.register_label_layers(V(w)["rows"])
    assert R["tiers"][0]["ids"] == ["PB", "PE"]                                              # equal labels share a tier; no tie-break by id meaning


def test_truth_and_priority_are_independent(world):
    base = V(world, [annot(world["pa"])])
    r0 = rank.all_baselines(base["rows"])
    with_truth = V(world, [annot(world["pa"])], extra=[assessment(world["pc"], "accepted"), assessment(world["pa"], "rejected")])
    r1 = rank.all_baselines(with_truth["rows"])
    assert r0 == r1                                                                          # accepting or rejecting claims moves no ranking
    assert row(with_truth, "PC")["truth"]["assessment_decision"]["value"] == "accepted" and row(base, "PC")["truth"]["assessment_decision"] is None
    # and an annotation cannot change a truth column
    assert row(base, "PA")["truth"] == row(V(world), "PA")["truth"]
    # an assessment on an older version is counted, not applied
    older = assessment(problem("PB", labels=("specialist", "long-term")), "accepted")
    assert row(V(world, extra=[older]), "PB")["truth"]["assessment_decision"] is None


def test_interest_counts_issuers_on_the_current_version_only(world):
    i1 = rec("Interest", "i1", {"target": ref(world["pa"]), "signal": "following", "explanation": "e"}, issuer="u1")
    i2 = rec("Interest", "i2", {"target": ref(world["pa"]), "signal": "following", "explanation": "e"}, issuer="u1")
    i3 = rec("Interest", "i3", {"target": ref(world["pa"]), "signal": "blocked_by_this", "explanation": "e", "downstream_reference": "P9"}, issuer="u2")
    r = row(V(world, extra=[i1, i2, i3]), "PA")
    assert r["interest_issuers"] == {"blocked_by_this": ["u2"], "following": ["u1"]}


# ------------------------------------------------------------------ action ledger
def test_ledger_replays_state_and_lease(world):
    L = V(world)["action_ledger"][0]
    assert L["state"] == "running" and L["lease"]["operator"] == "op-w" and L["lease_live_at_now"] is True and L["flags"] == []
    later = view.build_view(world["records"], world["events"], [], "2026-10-31T20:00:00+00:00")["action_ledger"][0]
    assert later["lease_live_at_now"] is False                                               # lease_until 19:00 has passed


def test_ledger_flags_unexpected_transitions_and_self_review(world):
    act = world["act"]
    evs = world["events"] + [event("action_accepted", act, at="2026-10-31T17:40:00+00:00")]
    L = action_ledger(world["records"], evs, NOW)[0]
    assert any("running -> accepted" in f for f in L["flags"]) and L["state"] == "accepted"          # accepted without submitted
    evs2 = world["events"] + [event("action_submitted", act, at="2026-10-31T17:35:00+00:00"),
                              event("action_reviewed", act, actor="w1b", operator="op-w", at="2026-10-31T17:36:00+00:00")]
    assert "reviewed by the operator that held the lease" in action_ledger(world["records"], evs2, NOW)[0]["flags"]


def test_action_against_an_older_problem_version_is_marked(world):
    old = problem("PA", actionable=True, title="older")
    w = dict(world); w["records"] = [r for r in world["records"] if r["id"] != "act1"] + [world["pa"], action(old, "act1")]
    r = row(view.build_view(w["records"], [], [], NOW), "PA")
    assert r["actions"][0]["targets_current_problem_version"] is False


# ------------------------------------------------------------------ gaps found by mutation checks, and the interface additions
def test_interest_on_an_older_problem_version_is_counted_apart_not_applied(world):
    old = problem("PA", actionable=True, title="older")
    i_old = rec("Interest", "i-old", {"target": ref(old), "signal": "following", "explanation": "e"}, issuer="u9")
    i_cur = rec("Interest", "i-cur", {"target": ref(world["pa"]), "signal": "following", "explanation": "e"}, issuer="u1")
    r = row(V(world, extra=[i_old, i_cur]), "PA")
    assert r["interest_issuers"] == {"following": ["u1"]} and r["interests_on_older_versions"] == 1


def test_proposed_connection_edges_do_not_count_toward_unlock_groups(world):
    extra = {"kind": "proposed_connection", "decision_id": "DU", "independent_group": "g3", "provenance": "analogy only"}
    base = annot(world["pa"])
    pa_doc = annot(world["pa"], unlocks=base["unlocks"] + [extra])          # PA: groups g1, g2 counted + g3 proposed only
    pb_doc = annot(world["pb"])                                             # PB: groups g1, g2
    R = rank.typed_unlock_groups(V(world, [pa_doc, pb_doc])["rows"])
    assert [t["ids"] for t in R["tiers"]] == [["PA", "PB"]]                  # equal at 2 groups each; counting the analogy would split them


def test_derived_dependents_invert_the_stores_typed_dependencies(world):
    pe = problem("PE", dependencies=[ref(world["pa"])])
    pf = problem("PF", dependencies=[ref(world["pa"]), ref(world["pb"])])
    v = V(world, extra=[pe, pf])
    assert row(v, "PA")["dependents"] == ["PE", "PF"] and row(v, "PB")["dependents"] == ["PF"] and row(v, "PC")["dependents"] == []
    R = rank.derived_dependents(v["rows"])
    assert [t["ids"] for t in R["tiers"]] == [["PA"], ["PB"], ["PC", "PD", "PE", "PF"]]
    stale = problem("PE", dependencies=[ref(problem("PA", actionable=True, title="older"))])
    assert row(V(world, extra=[stale]), "PA")["dependents_pinned_to_older_version"] == 1


def test_every_ranking_and_view_states_it_does_not_imply_viability(world):
    v = V(world)
    assert "viable or true" in v["does_not_imply"]
    assert all("viable or true" in r["does_not_imply"] for r in rank.all_baselines(v["rows"]).values())


def test_ledger_passes_through_action_inputs_when_the_store_provides_them(world):
    assert V(world)["action_ledger"][0]["inputs"] is None                    # absent today: reported as absent, not invented
    act = action(world["pa"], "act2")
    payload = dict(act["payload"], inputs=[ref(world["pb"])])                # root is adding Action.inputs; read tolerantly
    act2 = {**act, "payload": payload}
    L = action_ledger([world["pa"], act2], [], NOW)[0]
    assert L["inputs"] == [ref(world["pb"])]


# ------------------------------------------------------------------ whiteboard: design requirement vs theory challenge
THEORY = {"namespace": NS, "kind": "Claim", "id": "theory-t", "version": "c" * 64}


def wb_annot(pr, **kw):
    edges = [{"kind": "logical_necessity", "decision_id": "D1", "independent_group": "g1", "provenance": "curator", "relation": "design_requirement",
              "reason": "the minimum feature spacing for the design goal depends on this measurement"},
             {"kind": "empirical_relevance", "target": THEORY, "independent_group": "g2", "provenance": "curator", "relation": "theory_challenge",
              "reason": "tests the theory's prediction that spacing scales with domain length"}]
    return annot(pr, unlocks=edges, **kw)


def test_edge_with_a_relation_must_explain_and_a_challenge_must_name_the_theory():
    base = {"kind": "logical_necessity", "decision_id": "D1", "independent_group": "g", "provenance": "p"}
    with pytest.raises(Exception, match="must say why"):
        annot(problem("PX"), unlocks=[{**base, "relation": "design_requirement"}])
    with pytest.raises(Exception, match="exact Claim version"):
        annot(problem("PX"), unlocks=[{**base, "relation": "theory_challenge", "reason": "r"}])
    with pytest.raises(Exception):
        annot(problem("PX"), unlocks=[{**base, "relation": "makes_money", "reason": "r"}])


def test_view_exposes_why_each_question_unlocks_a_requirement_or_challenges_a_theory(world):
    v = V(world, [wb_annot(world["pa"]), annot(world["pb"])])
    r = row(v, "PA")
    rel = {u["relation"]: u for u in r["unlock_reasons"]}
    assert set(rel) == {"design_requirement", "theory_challenge"}
    assert rel["design_requirement"]["counted_in_value"] is True and rel["theory_challenge"]["counted_in_value"] is False      # no decision, so no value
    effects = [w["effect"] for w in r["why_priority"] if w["field"] == "annotation.unlocks.relation"]
    assert any("minimum feature spacing" in e and "[counts toward declared value]" in e for e in effects)
    assert any("prediction that spacing scales" in e and "not part of any value" in e for e in effects)
    assert v["whiteboard_facets"] == {"design_requirement": [], "theory_challenge": [], "both": ["PA"], "neither_stated": ["PB", "PC", "PD"]}
    assert "annotator-declared belief about the state of a DECISION" in r["utility"]["prior_meaning"]


def test_challenging_a_theory_does_not_move_its_truth_and_its_truth_does_not_move_the_ranking(world):
    theory = rec("Claim", "theory-t", {"title": "t", "statement": "s", "context": "c", "assumptions": ["a"], "limitations": ["l"], "source": SRC})
    global THEORY
    saved, THEORY = THEORY, ref(theory)
    try:
        doc = wb_annot(world["pa"])
        r0 = rank.all_baselines(V(world, [doc], extra=[theory])["rows"])
        asm = rec("Assessment", "asm-theory", {"target": ref(theory), "decision": "rejected", "dimensions": assessment(world["pa"], "rejected")["payload"]["dimensions"],
                                               "independence_rationale": "fixture", "limitations": ["fixture"]}, issuer="bob")
        v1 = V(world, [doc], extra=[theory, asm])
        assert rank.all_baselines(v1["rows"]) == r0                              # rejecting the theory changes no priority
        assert row(v1, "PA")["truth"]["assessment_decision"] is None             # and the challenge edge does not assess anything
    finally:
        THEORY = saved


def test_store_whiteboard_fields_pass_through_verbatim_and_partition_is_not_a_ranking(world):
    # payloads are edited after make_record on purpose: these fields are not in the store's models yet, and the view never re-verifies digests
    pt = problem("PT"); pt["payload"].update(approach="top_down", scales=["tissue"], context_tags=["limb"])      # fields root is adding; read tolerantly
    pu = problem("PU"); pu["payload"].update(approach="bottom_up")
    v = view.build_view(world["records"] + [pt, pu], [], [], NOW)
    r = row(v, "PT")["store"]
    assert (r["approach"], r["scales"], r["context_tags"]) == ("top_down", ["tissue"], ["limb"]) and row(v, "PA")["store"]["approach"] is None
    parts = rank.partition_by_approach(v["rows"])
    assert sorted(parts) == ["bottom_up", "top_down", "unspecified"] and len(parts["unspecified"]) == 4


def test_cli_view_reads_a_bundle_file_and_prints_rows_rankings_and_the_disclaimer(world, tmp_path, capsys):
    import json
    from attention.__main__ import main
    f = tmp_path / "bundle.json"
    f.write_text(json.dumps({"records": world["records"]}))
    assert main(["view", "--records", str(f), "--now", NOW, "--out", str(tmp_path / "out.json")]) == 0
    out = json.loads((tmp_path / "out.json").read_text())
    assert out["n_problems"] == 4 and set(out["rankings"]) >= {"id_order", "derived_dependents", "declared_evpi"} and "viable or true" in out["does_not_imply"]
    assert "does_not_imply" in capsys.readouterr().out
