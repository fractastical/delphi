"""Tests for frontier.beliefs. No database needed. Hand-worked controls use exact Fractions.

All scenarios are 'declared illustration' fixtures; none is measured data.
"""
import copy
import itertools
import json
from fractions import Fraction as F

import pytest

from frontier import beliefs as B


def var(i, states=("t", "f")):
    return {"id": i, "event": f"event {i}", "context": "declared illustration", "states": list(states)}


def prior(v, t="1/2"):
    return {"variable": v, "method": "uniform-ignorance"} if t is None else {
        "variable": v, "method": "declared", "table": {"t": t, "f": str(1 - F(t))}, "source": "declared:test"}


def fac(i, scope, rows, source=None, group=None):
    return {"id": i, "scope": scope, "table": rows, "source": source or "src-" + i, "group": group or "grp-" + i}


def decision(outcome="A"):
    return {"id": "d", "question": "act?", "outcome": outcome, "actions": {"go": {}, "stop": {}},
            "utility": {"go": {"t": "10", "f": "-10"}, "stop": {"t": "0", "f": "0"}}, "cost": {"go": "0", "stop": "0"}}


def scenario(variables, priors, factors, dec=None, **extra):
    return {"schema": B.SCHEMA, "label": "declared illustration", "variables": variables, "priors": priors,
            "factors": factors, "decision": dec or decision(variables[0]["id"]), **extra}


def post(res, v, s="t"):
    return F(res["variables"][v]["posterior"][s])


# ---- hand-worked controls ---------------------------------------------------------------

def test_hand_worked_two_independent_evidence_factors():
    # prior 1/2; LRs 3:1 and 2:1. t: 1/2*3*2 = 3 ; f: 1/2*1*1 = 1/2 ; Z = 7/2 ; P(t) = 6/7.
    sc = scenario([var("A")], [prior("A")], [fac("e1", ["A"], [["t", "3"], ["f", "1"]]),
                                              fac("e2", ["A"], [["t", "2"], ["f", "1"]])])
    r = B.solve(sc)
    assert r["status"] == "ok" and r["duplicate_paths"] == []
    assert post(r, "A") == F(6, 7)
    assert r["variables"]["A"]["prior_method"] == "declared"


def test_hand_worked_chain_tree():
    # A -- psi -- B, psi = 4 on agreement, 1 otherwise; evidence on B: t=3, f=1; uniform A prior.
    # A=t: 1/2*(4*3 + 1*1) = 13/2 ; A=f: 1/2*(1*3 + 4*1) = 7/2 ; Z = 10 ; P(A=t) = 13/20.
    # B=t: (1/2*4 + 1/2*1)*3 = 15/2 ; B=f: (1/2*1 + 1/2*4)*1 = 5/2 ; P(B=t) = 3/4.
    sc = scenario([var("A"), var("B")], [prior("A"), prior("B", None)],
                  [fac("psi", ["A", "B"], [["t", "t", "4"], ["t", "f", "1"], ["f", "t", "1"], ["f", "f", "4"]]),
                   fac("eb", ["B"], [["t", "3"], ["f", "1"]])])
    # B has a uniform-ignorance prior (1/2,1/2): same arithmetic as the uniform-1/2 above.
    r = B.solve(sc)
    assert r["status"] == "ok" and not r["structure"]["cyclic"]
    assert post(r, "A") == F(13, 20) and post(r, "B") == F(3, 4)
    assert r["variables"]["B"]["prior_method"] == "uniform-ignorance"


def triangle(agree="2", disagree="1"):
    def pair(i, a, b):
        return fac(i, [a, b], [[x, y, agree if x == y else disagree] for x in "tf" for y in "tf"])
    return scenario([var("A"), var("B"), var("C")], [prior("A", None), prior("B", None), prior("C", None)],
                    [pair("ab", "A", "B"), pair("ac", "A", "C"), pair("bc", "B", "C"),
                     fac("ea", ["A"], [["t", "3"], ["f", "1"]])])


def test_hand_worked_cyclic_triangle_is_solved_exactly():
    # Hand count over (A,B,C), weights: agree-pair=2 else 1, evidence A=t x3.
    # A=t: ttt 8*3=24, ttf 2*3=6, tft 6, tff 6 -> 42 ; A=f: fff 8, ftt 2, fft 2, ftf 2 -> 14 ; Z=56.
    # P(A=t)=42/56=3/4 ; B=t: ttt 24 + ttf 6 + ftt 2 + ftf 2 = 34 -> P(B=t)=17/28.
    r = B.solve(triangle())
    assert r["status"] == "ok"
    assert r["structure"]["cyclic"] is True and r["structure"]["solver"] == "exact-variable-elimination"
    assert post(r, "A") == F(3, 4) and post(r, "B") == F(17, 28)
    # independent cross-check by brute-force joint enumeration written separately from the solver
    w = {}
    for a, b, c in itertools.product("tf", repeat=3):
        w[a, b, c] = F(2 if a == b else 1) * (2 if a == c else 1) * (2 if b == c else 1) * (3 if a == "t" else 1)
    assert sum(v for k, v in w.items() if k[0] == "t") / sum(w.values()) == post(r, "A")


# ---- decision-conditioned output ----------------------------------------------------------

def test_decision_values_breakeven_and_flips_are_hand_computed():
    # H prior 1/5, LRs 3 and 2 -> P=3/5. advance EV = 6 - 8/5 - 1 = 17/5. Breakeven 14p = 5 -> p = 5/14.
    # drop e1: odds 1/5*2 : 4/5 -> p = 1/3 < 5/14 -> hold. drop e2: 3/7 > 5/14 -> still advance.
    # prior->uniform: 3 : 1/2 -> 6/7 -> still advance.
    r = B.solve(B.EXAMPLE_SCENARIO)
    d = r["decision"]
    assert r["status"] == "ok"
    assert post(r, "H", "yes") == F(3, 5)
    assert F(d["actions"]["advance"]["expected_value"]) == F(17, 5) and d["preferred"] == "advance"
    assert d["ev_margin_over_runner_up"] == "17/5"
    be = d["preferred_changes_when"]["breakeven"]
    assert F(be[0]["p_threshold"]) == F(5, 14) and be[0]["versus"] == "hold"
    assert d["preferred_changes_when"]["flipping_assumptions"] == ["drop factor e1"]
    flips = {v["assumption_changed"]: v["preferred"] for v in d["preferred_changes_when"]["variations"]}
    assert flips["drop factor e1"] == ["hold"] and flips["drop factor e2"] == ["advance"]


def test_mutated_factor_table_changes_the_decision():
    base = B.solve(B.EXAMPLE_SCENARIO)
    assert base["decision"]["preferred"] == "advance"
    mut = copy.deepcopy(B.EXAMPLE_SCENARIO)
    mut["factors"][0]["table"] = [["yes", "1"], ["no", "3"]]      # evidence now points the other way
    r = B.solve(mut)
    # P(yes) = (1/5*1*2) : (4/5*3*1) = 2 : 12 -> 1/7 < 5/14 -> hold
    assert post(r, "H", "yes") == F(1, 7) and r["decision"]["preferred"] == "hold"
    assert r["input_hash"] != base["input_hash"] and r["output_hash"] != base["output_hash"]


def test_exact_tie_is_reported_not_broken():
    sc = copy.deepcopy(B.EXAMPLE_SCENARIO)
    sc["decision"]["utility"]["advance"] = {"yes": "0", "no": "0"}
    sc["decision"]["cost"]["advance"] = "0"
    d = B.solve(sc)["decision"]
    assert d["preferred"] is None and d["tied"] == ["advance", "hold"]


def test_action_assumption_is_conditioning_and_impossible_one_is_explicit():
    sc = scenario([var("A"), var("B")], [prior("A"), prior("B")],
                  [fac("psi", ["A", "B"], [["t", "t", "1"], ["t", "f", "0"], ["f", "t", "0"], ["f", "f", "1"]])])
    sc["decision"]["actions"] = {"go": {"assumes": {"B": "t"}}, "stop": {}}
    sc["factors"].append(fac("nob", ["B"], [["t", "0"], ["f", "1"]]))
    r = B.solve(sc)
    assert r["status"] == "ok"
    assert r["decision"]["actions"]["go"] == {"status": "impossible-under-its-assumptions"}
    assert r["decision"]["preferred"] == "stop"


# ---- replay ------------------------------------------------------------------------------------

def test_replay_is_identical_and_input_hash_matches_models_canonical_form():
    sc = json.loads(json.dumps(B.EXAMPLE_SCENARIO))           # round-trip through JSON
    a, b = B.solve(sc), B.replay(json.loads(json.dumps(sc)))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["input_hash"] == b["input_hash"] and a["output_hash"] == b["output_hash"]
    assert a["input_hash"] == "8a7f83729dfb2d8b36098cdcba1cda1f123961f834b72b10148e954693c95aaa"
    from frontier.models import digest
    assert a["input_hash"] == digest(sc)
    m = a["metadata"]
    assert m["calibration"].startswith("UNKNOWN") and "not a truth score" in m["interpretation"]
    assert "declared illustration" in a["label"]
    assert not any("truth" in k for k in a)


# ---- negative controls (each MUST refuse / flag) -------------------------------------------------

def dup_scenario(**extra):
    # the SAME evidence reaches A twice, via two factors in one group
    row = [["t", "3"], ["f", "1"]]
    return scenario([var("A")], [prior("A")], [fac("e1", ["A"], row, "paper-X", "paper-X-group"),
                                                fac("e2", ["A"], row, "paper-X-copy", "paper-X-group")], **extra)


def test_duplicate_group_is_detected_and_refused_not_multiplied():
    r = B.solve(dup_scenario())
    assert r["status"] == "refused-duplicate-evidence" and "variables" not in r
    assert r["duplicate_paths"] == [{"kind": "group", "name": "paper-X-group", "members": ["e1", "e2"]}]
    assert "collapse" in r["reasons"][0]


def test_duplicate_source_through_two_routes_is_detected():
    row = [["t", "3"], ["f", "1"]]
    sc = scenario([var("A")], [prior("A")], [fac("e1", ["A"], row, "paper-X", "g1"),
                                              fac("e2", ["A"], row, "paper-X", "g2")])
    r = B.solve(sc)
    assert r["status"] == "refused-duplicate-evidence"
    assert r["duplicate_paths"][0]["kind"] == "source"


def test_prior_and_evidence_from_one_source_are_flagged():
    sc = scenario([var("A")], [prior("A", "1/2")], [fac("e1", ["A"], [["t", "3"], ["f", "1"]], "declared:test")])
    assert B.solve(sc)["status"] == "refused-duplicate-evidence"


def test_declared_collapse_counts_once_and_double_counting_would_differ():
    r = B.solve(dup_scenario(collapse={"group:paper-X-group": "e1"}))
    assert r["status"] == "ok"
    assert r["collapsed"] == [{"rule": "keep-one", "key": "group:paper-X-group", "kept": "e1", "dropped": ["e2"]}]
    assert post(r, "A") == F(3, 4)                  # 1/2*3 : 1/2*1
    assert F(3, 4) != F(9, 10)                      # what multiplying both copies would have given
    assert r["duplicate_paths"], "detections stay reported after collapse"
    with pytest.raises(B.BeliefError):
        B.solve(dup_scenario(collapse={"group:paper-X-group": "nope"}))


def test_cap_exceeded_is_refused_not_approximated():
    big = scenario([var("A")], [prior("A")], [fac("e1", ["A"], [["t", "1"], ["f", "1"]])])
    big["variables"][0]["states"] = [f"s{i}" for i in range(B.MAX_STATES + 1)]
    r = B.solve(big)
    assert r["status"] == "refused-cap-exceeded" and "variables" not in r
    many = scenario([var(f"V{i}") for i in range(B.MAX_VARIABLES + 1)], [], [])
    assert B.solve(many)["status"] == "refused-cap-exceeded"
    wide = scenario([var(f"V{i}") for i in range(B.MAX_FACTOR_SCOPE + 1)], [],
                    [fac("w", [f"V{i}" for i in range(B.MAX_FACTOR_SCOPE + 1)], [])])
    assert B.solve(wide)["status"] == "refused-cap-exceeded"


def test_cyclic_graph_beyond_exact_cap_is_unsupported_with_no_posterior():
    r = B.solve(triangle(), B.Caps(max_elim_cells=4))      # a triangle needs an 8-cell table
    assert r["status"] == "unsupported-cyclic-beyond-exact-cap"
    assert "variables" not in r and "decision" not in r and "no approximate posterior" in r["reasons"][0]
    assert B.solve(triangle(), B.Caps(max_elim_cells=8))["status"] == "ok"      # boundary is exact


def test_default_caps_refuse_a_dense_graph_without_approximating():
    n = 12                                                  # complete graph, 6 states each: width 11
    names = [f"V{i}" for i in range(n)]
    st = tuple(f"s{i}" for i in range(6))
    facs = [fac(f"f{i}_{j}", [names[i], names[j]], [[a, b, "1"] for a in st for b in st])
            for i, j in itertools.combinations(range(n), 2)]
    sc = scenario([var(v, st) for v in names], [prior_u(v) for v in names], facs,
                  dec={**decision("V0"), "utility": {"go": {s: "1" for s in st}, "stop": {s: "0" for s in st}}})
    r = B.solve(sc)
    assert r["status"] == "unsupported-cyclic-beyond-exact-cap" and "variables" not in r


def prior_u(v):
    return {"variable": v, "method": "uniform-ignorance"}


def test_contradiction_is_explicit_not_normalised_away():
    sc = scenario([var("A")], [prior("A")], [fac("no_t", ["A"], [["t", "0"], ["f", "1"]]),
                                              fac("no_f", ["A"], [["t", "1"], ["f", "0"]])])
    r = B.solve(sc)
    assert r["status"] == "contradiction" and "variables" not in r and "decision" not in r
    assert r["contradiction"]["factors_with_hard_zeros"] == ["no_f", "no_t"]
    assert r["contradiction"]["support_restored_if_dropped"] == ["no_f", "no_t"]


def test_ruled_out_state_is_listed_and_prior_only_variable_flagged():
    sc = scenario([var("A"), var("B")], [prior("A"), prior("B")], [fac("no_f", ["A"], [["t", "1"], ["f", "0"]])])
    r = B.solve(sc)
    assert r["variables"]["A"]["ruled_out_states"] == ["f"] and post(r, "A") == 1
    assert r["variables"]["B"]["prior_only"] is True and r["variables"]["A"]["prior_only"] is False


def test_missing_prior_is_unresolved_not_defaulted():
    sc = scenario([var("A")], [], [fac("e1", ["A"], [["t", "3"], ["f", "1"]])])
    r = B.solve(sc)
    assert r["status"] == "unresolved-no-prior" and "variables" not in r


@pytest.mark.parametrize("mutate", [
    lambda s: s["priors"][0].pop("method"),                                       # unlabelled prior
    lambda s: s["priors"][0].update(method="vibes"),                              # unknown method
    lambda s: s["priors"][0].update(method="uniform-ignorance"),                  # numbers + ignorance
    lambda s: s["priors"][0].update(table={"yes": 0.2, "no": 0.8}),               # floats
    lambda s: s["priors"][0].update(table={"yes": "1/5", "no": "1/2"}),           # not normalised
    lambda s: s["factors"][0].pop("source"),                                      # no lineage
    lambda s: s["factors"][0].pop("group"),
    lambda s: s["factors"][0]["table"].pop(),                                     # incomplete table
    lambda s: s["factors"][0]["table"][0].__setitem__(1, "-1"),                   # negative weight
    lambda s: s["variables"][0].pop("context"),                                   # no declared context
    lambda s: s["decision"]["actions"]["advance"].update(do={"H": "yes"}),        # do-queries refused
    lambda s: s["decision"]["cost"].pop("hold"),                                  # silent zero cost
])
def test_malformed_scenarios_raise(mutate):
    sc = copy.deepcopy(B.EXAMPLE_SCENARIO)
    mutate(sc)
    with pytest.raises(B.BeliefError):
        B.solve(sc)
