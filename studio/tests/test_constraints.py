"""Solver tests: exact rational witnesses, named unsat cores, unknown on missing parameters,
mutated-law sensitivity, tampered-certificate rejection, no rounded algebraic witnesses."""
from fractions import Fraction

import pytest

pytest.importorskip("z3")
from engineering.constraints import (  # noqa: E402
    Constraint, Model, dim, flying_fish_model, lean_conflict_certificate, poly, q_mass_min,
    q_speed_max, q_wl_min, solve, verify_certificate, frac,
)


def fm():
    return flying_fish_model(rho="1.225", CL="1")


def test_missing_design_assumptions_give_unknown_not_feasible():
    r = solve(flying_fish_model())
    assert r.status == "unknown"
    assert r.missing_parameters == ["CL", "rho"]
    assert r.witness is None and r.partial_witness is not None
    assert "NOT a design" in r.reason


def test_feasible_witness_is_exact_rational_and_independently_rechecked():
    M = fm()
    r = solve(M)
    assert r.status == "feasible"
    assert all(isinstance(Fraction(v), Fraction) for v in r.witness.values())
    v = verify_certificate(M, r.to_json())
    assert v["ok"] and v["independent"]
    assert r.checks["exact_recheck_violations"] == []


def test_mass_above_source_envelope_names_the_two_conflicting_constraints():
    M = fm()
    r = solve(M, [q_mass_min(1)])
    assert r.status == "unsat"
    assert set(r.conflict) == {"mass_hi", "q_mass_min"} and r.core_minimal
    assert r.provenance["mass_hi"]["kind"] == "source_envelope"
    # relaxing the envelope gives a witness AND reports exactly which envelopes it leaves
    r2 = solve(M, [q_mass_min(1)], relax_envelopes=True)
    assert r2.status == "feasible" and "mass_hi" in r2.extrapolates_envelope
    assert "universal feasibility" in r2.to_json()["scope"]


def test_wing_loading_ceiling_conflict_core_is_exactly_three_names():
    M = fm()
    r = solve(M, [q_wl_min(150), q_speed_max(10)])
    assert r.status == "unsat"
    assert set(r.conflict) == {"lift_stall", "q_wl_min", "q_speed_max"}


def test_exact_boundary_rho_V2_CL_over_2():
    # rho=1.225, CL=1, V<=10  =>  WL <= 61.25 = 245/4 exactly; boundary allowed, one hair above is not
    M = fm()
    ok = solve(M, [q_wl_min(Fraction(245, 4)), q_speed_max(10)])
    assert ok.status == "feasible"
    assert verify_certificate(M, ok.to_json(), [q_wl_min(Fraction(245, 4)), q_speed_max(10)])["ok"]
    over = solve(M, [q_wl_min(Fraction(245, 4) + Fraction(1, 10**6)), q_speed_max(10)])
    assert over.status == "unsat"


def test_unsat_stays_sound_when_unrelated_parameters_are_missing():
    r = solve(flying_fish_model(), [q_mass_min(1)])  # rho, CL unset; conflict does not need them
    assert r.status == "unsat" and set(r.conflict) == {"mass_hi", "q_mass_min"}
    assert r.missing_parameters == ["CL", "rho"]


def _with_lift_law(terms):
    M = fm()
    for i, c in enumerate(M.constraints):
        if c.name == "lift_stall":
            M.constraints[i] = Constraint("lift_stall", c.kind, poly(*terms), ">=", "MUTANT")
    return M


def test_dimensionally_wrong_law_is_rejected_before_solving():
    """V^1 instead of V^2 in the lift law is caught by the unit check, not by the solver."""
    M = _with_lift_law([(1, {"V": 1, "rho": 1, "S": 1, "CL": 1}), (-2, {"m": 1, "g": 1})])
    with pytest.raises(ValueError, match="different dimensions"):
        solve(M, [q_wl_min(50), q_speed_max(10)])


def test_dimensionally_consistent_wrong_law_changes_the_verdict():
    """Factor 2 -> 8 keeps the units valid but changes the answer: feasible (real law) vs unsat (mutant)."""
    Q = [q_wl_min(50), q_speed_max(10)]
    assert solve(fm(), Q).status == "feasible"
    M = _with_lift_law([(1, {"V": 2, "rho": 1, "S": 1, "CL": 1}), (-8, {"m": 1, "g": 1})])
    assert solve(M, Q).status == "unsat"


def test_tampered_witness_is_rejected_by_exact_recheck():
    M = fm()
    r = solve(M).to_json()
    r["witness"] = dict(r["witness"], m="10")  # leaves the mass envelope
    v = verify_certificate(M, r)
    assert v["ok"] is False and "mass_hi" in v["violations"]


def test_algebraic_witness_is_never_rounded_into_a_certificate():
    """V*V = 2 m^2/s^2 forces V = sqrt 2: no rational point exists, so the answer must not be 'feasible'."""
    M = fm()
    sq = dim(m=2, s=-2)
    eq = [Constraint("q_v2_le", "user_query", poly((1, {"V": 2}), (-2, {}, sq)), "<=", "test"),
          Constraint("q_v2_ge", "user_query", poly((1, {"V": 2}), (-2, {}, sq)), ">=", "test")]
    r = solve(M, eq, relax_envelopes=True)
    assert r.status in ("unknown", "unsat") and r.witness is None


def test_units_and_floats_are_checked():
    M = fm()
    bad = Constraint("bad", "user_query", poly((1, {"m": 1}), (-1, {}, dim(m=1))), ">=", "x")
    with pytest.raises(ValueError, match="different dimensions"):
        solve(M, [bad])
    with pytest.raises(TypeError):
        frac(0.1)
    with pytest.raises(ValueError, match="different dimensions"):  # b*b vs S*AR is fine, b vs S is not
        solve(M, [Constraint("bad2", "user_query", poly((1, {"b": 1}), (-1, {"S": 1})), "<=", "x")])


def test_result_interface_is_stable():
    j = solve(fm()).to_json()
    assert set(j) == {"status", "witness", "conflict", "core_minimal", "missing_parameters", "partial_witness",
                      "reason", "scope", "extrapolates_envelope", "used_constraints", "provenance", "checks",
                      "solver", "z3_version", "lean"}
    assert j["lean"] == "not_run"  # the solver never claims Lean ran


def test_lean_certificate_text_only_for_the_matching_core():
    M, Q = fm(), [q_wl_min(150), q_speed_max(10)]
    txt = lean_conflict_certificate(M, solve(M, Q), Q)
    assert "(150 : ℝ)" in txt and "(10 : ℝ)" in txt and "(49 : ℝ) / 40" in txt
    assert lean_conflict_certificate(M, solve(M, [q_mass_min(1)]), [q_mass_min(1)]) is None
