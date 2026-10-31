"""Solver tests: exact rational witnesses, named unsat cores, unknown on missing parameters,
mutated-law sensitivity, tampered-certificate rejection, no rounded algebraic witnesses."""
from fractions import Fraction

import pytest

pytest.importorskip("z3")
from engineering.constraints import (  # noqa: E402
    SCOPE, SOURCES, UI_MUST_NOT_SAY, Constraint, Model, Parameter, Quantity, dim, flying_fish_model,
    frac, lean_conflict_certificate, poly, q_mass_min, q_speed_max, q_wl_min, solve, ui_manifest,
    verify_certificate,
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
    assert set(r.conflict) == {"level_lift_proxy", "q_wl_min", "q_speed_max"}


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
        if c.name == "level_lift_proxy":
            M.constraints[i] = Constraint("level_lift_proxy", c.kind, poly(*terms), ">=", "MUTANT")
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


# ======================= adversarial tests (root review: certificate trust, scope, correspondence) ==============

def fresh():
    M = fm()
    return M, solve(M).to_json()


def test_deleting_a_failed_constraint_from_the_claimed_list_cannot_make_a_bad_witness_pass():
    M, r = fresh()
    r["witness"] = dict(r["witness"], m="10")                   # violates mass_hi
    r["used_constraints"] = [n for n in r["used_constraints"] if n != "mass_hi"]  # attacker deletes it
    v = verify_certificate(M, r)
    assert v["ok"] is False and any("differs" in p for p in v["problems"])
    assert "mass_hi" in v["violations"]  # and the exact check still catches it


def test_extra_or_reordered_constraint_claims_are_rejected():
    M, r = fresh()
    assert verify_certificate(M, dict(r, used_constraints=r["used_constraints"] + ["bogus"]))["ok"] is False
    assert verify_certificate(M, dict(r, used_constraints=list(reversed(r["used_constraints"]))))["ok"] is False
    assert verify_certificate(M, r)["ok"] is True


def test_feasible_claim_with_unset_design_assumptions_is_rejected():
    M = flying_fish_model()                      # rho, CL unset
    forged = solve(M).to_json()
    assert forged["status"] == "unknown"
    forged.update(status="feasible", witness=forged["partial_witness"])
    v = verify_certificate(M, forged)
    assert v["ok"] is False and any("unset parameters" in p for p in v["problems"])


@pytest.mark.parametrize("bad", ["0", "-1", "-1/2"])
def test_nonpositive_rho_or_CL_is_rejected_at_solve_and_at_verify(bad):
    for kw in ({"rho": bad, "CL": "1"}, {"rho": "1.225", "CL": bad}):
        with pytest.raises(ValueError, match="strictly positive"):
            solve(flying_fish_model(**kw))
    M, r = fresh()                                # mutate AFTER solving: verify must re-validate
    M.parameters["rho"] = Parameter("rho", "kg/m^3", dim(kg=1, m=-3), Fraction(bad), "design_assumption", "x")
    v = verify_certificate(M, r)
    assert v["ok"] is False and any("strictly positive" in p for p in v["problems"])


def test_relax_policy_is_a_trusted_argument_not_result_directed():
    M, Q = fm(), [q_mass_min(1)]
    relaxed = solve(M, Q, relax_envelopes=True).to_json()
    assert verify_certificate(M, relaxed, Q, relax_envelopes=True)["ok"] is True
    # verifier trusts ITS argument: the same result is rejected under the strict policy
    strict = verify_certificate(M, relaxed, Q, relax_envelopes=False)
    assert strict["ok"] is False and strict["violations"]
    # an attacker relabels a relaxed result as strict, or edits its own policy flag: still rejected
    for forged in (dict(relaxed, checks=dict(relaxed["checks"], relax_envelopes=False)),
                   dict(relaxed, checks={})):
        assert verify_certificate(M, forged, Q, relax_envelopes=False)["ok"] is False
    # and a result that merely drops envelope names while claiming strict is rejected
    bad = dict(relaxed, checks=dict(relaxed["checks"], relax_envelopes=False))
    assert verify_certificate(M, bad, Q, relax_envelopes=True)["ok"] is False


def test_witness_shape_and_positivity_are_enforced():
    M, r = fresh()
    w = r["witness"]
    for forged in ({k: v for k, v in w.items() if k != "b"}, dict(w, extra="1"), dict(w, m="-1/2"),
                   dict(w, m="not-a-number"), dict(w, m="0")):
        assert verify_certificate(M, dict(r, witness=forged))["ok"] is False
    assert verify_certificate(M, dict(r, scope="anything"))["ok"] is False


def test_forged_unsat_on_a_satisfiable_core_is_rejected():
    M, r = fresh()
    forged = dict(r, status="unsat", conflict=["mass_lo", "mass_hi"], witness=None)
    v = verify_certificate(M, forged)
    assert v["ok"] is False and v["z3"] == "sat"
    assert verify_certificate(M, dict(forged, conflict=["no_such_constraint"]))["ok"] is False
    assert verify_certificate(M, dict(forged, conflict=[]))["ok"] is False


def test_reserved_names_duplicates_and_noop_terms_are_rejected():
    M = fm()
    with pytest.raises(ValueError, match="may not start with"):
        solve(M, [Constraint("domain:m:hi", "user_query", poly((1, {"m": 1}), (-1, {}, dim(kg=1))), "<=", "x")])
    with pytest.raises(ValueError, match="duplicate symbol"):
        Model().add(Quantity("m", "kg", dim(kg=1), Fraction(0), Fraction(1), "x"),
                    Quantity("m", "kg", dim(kg=1), Fraction(0), Fraction(1), "x"))
    with pytest.raises(ValueError, match="duplicate symbol"):
        Model().add(Quantity("m", "kg", dim(kg=1), Fraction(0), Fraction(1), "x"),
                    Parameter("m", "kg", dim(kg=1), Fraction(1), "design_assumption", "x"))
    M.parameters["V"] = Parameter("V", "m/s", dim(m=1, s=-1), Fraction(1), "design_assumption", "x")  # post-hoc overlap
    with pytest.raises(ValueError, match="both quantity and parameter"):
        solve(M)
    noops = {
        "zero coefficient": poly((1, {"m": 1}), (0, {"m": 1}), (-1, {}, dim(kg=1))),
        "zero exponent": poly((1, {"m": 1}), (-1, {"S": 0}, dim(kg=1))),
        "constant only": poly((1, {}, dim(kg=1)), (-1, {}, dim(kg=1))),
    }
    for label, t in noops.items():
        with pytest.raises(ValueError, match="no-op"):
            solve(fm(), [Constraint("q_noop", "user_query", t, ">=", "x")])
    with pytest.raises(ValueError, match="no terms"):
        solve(fm(), [Constraint("q_empty", "user_query", (), ">=", "x")])


def test_default_model_has_no_ar_or_taxi_speed_envelope_and_they_are_opt_in_assumptions():
    D = fm()
    assert not [c for c in D.constraints if c.name.startswith(("ar_", "speed_"))] and D.opt_ins == []
    # without the opt-in, a 25 m/s design is not excluded by any source envelope
    fast = Constraint("q_speed_min", "user_query", poly((1, {"V": 1}), (-25, {}, dim(m=1, s=-1))), ">=", "q")
    assert solve(D, [fast]).status == "feasible"
    A = flying_fish_model(rho="1.225", CL="1", assume_pectoral_ar_applies_to_wing=True, assume_taxi_speed_applies_to_flight=True)
    assert A.opt_ins == ["pectoral_ar_applies_to_wing", "taxi_speed_range"]
    names = {c.name: c for c in A.constraints}
    for n in ("ar_lo_assumed", "ar_hi_assumed", "speed_lo_assumed", "speed_hi_assumed"):
        assert names[n].kind == "design_assumption" and names[n].correspondence
    r = solve(A, [fast])
    assert r.status == "unsat" and "speed_hi_assumed" in r.conflict
    # relaxing SOURCE envelopes must not silently drop a design assumption
    r2 = solve(A, [fast], relax_envelopes=True)
    assert r2.status == "unsat" and "speed_hi_assumed" in r2.conflict


def test_level_proxy_wording_and_full_source_digest_are_present():
    assert "level-flight proxy" in SCOPE and "cos(gamma)" in SCOPE
    assert solve(fm()).provenance["level_lift_proxy"]["correspondence"].startswith("level-flight proxy")
    f = SOURCES["fish1990"]
    assert len(f["sha256"]) == 64 and f["url"].startswith("https://")
    prov = solve(fm()).provenance["mass_hi"]["source"]
    assert f["sha256"] in prov and f["url"] in prov and "..." not in prov


def test_ui_manifest_is_scoped_and_never_upgrades_a_failed_verification():
    M = fm()
    for Q, relax in (([], False), ([q_mass_min(1)], False), ([q_mass_min(1)], True), ([q_wl_min(150), q_speed_max(10)], False)):
        r = solve(M, Q, relax_envelopes=relax)
        ui = ui_manifest(M, r, Q, relax_envelopes=relax)
        assert SCOPE in ui["must_display"] and ui["schema"] == "frontier.constraints.ui/1"
        text = (ui["headline"] + ui["badge"]).lower()
        assert not any(bad.lower() in text for bad in UI_MUST_NOT_SAY)
        assert ui["lean"]["run_by_this_solver"] is False and ui["verification"]["ok"] is True
        if r.status == "unsat":
            assert any("Lean did not verify" in m for m in ui["must_display"])
            assert {row["name"] for row in ui["rows"] if row["in_conflict"]} == set(r.conflict)
        if relax:
            assert any("DROPPED" in m for m in ui["must_display"])
    # tampered result: manifest downgrades to unknown and withholds the witness
    r = solve(M).to_json()
    r["witness"] = dict(r["witness"], m="10")
    ui = ui_manifest(M, r)
    assert ui["status"] == "unknown" and ui["witness"] is None and ui["verification"]["ok"] is False
    # opt-ins are announced
    A = flying_fish_model(rho="1.225", CL="1", assume_taxi_speed_applies_to_flight=True)
    ui = ui_manifest(A, solve(A))
    assert any("taxi_speed_range" in m for m in ui["must_display"])
    assert any(row["opt_in_assumption"] for row in ui["rows"])


# ======================= Lean certificate emitter: structural derivation, metadata is not trusted ===================

def _cert_case(wl=150, vmax=10):
    M, Q = fm(), [q_wl_min(wl), q_speed_max(vmax)]
    return M, Q, solve(M, Q)


def _swap(c, **kw):
    d = dict(name=c.name, kind=c.kind, terms=c.terms, op=c.op, provenance=c.provenance,
             correspondence=c.correspondence, meta=dict(c.meta))
    d.update(kw)
    return Constraint(**d)


def test_certificate_numbers_come_from_the_polynomial_not_the_metadata():
    M, Q, r = _cert_case()
    assert r.status == "unsat"
    good = lean_conflict_certificate(M, r, Q)
    assert "(150 : ℝ)" in good and "(10 : ℝ)" in good
    # metadata scrubbed: still emits, identical text (meta is not an input)
    scrubbed = [_swap(c, meta={}) for c in Q]
    assert lean_conflict_certificate(M, r, scrubbed) == good
    # MUTANT: metadata still says 150 but the actual polynomial now says 200 -> text must say 200, never 150
    lying = [_swap(Q[0], terms=poly((1, {"m": 1, "g": 1}), (-200, {"S": 1}, dim(kg=1, m=-1, s=-2)))), Q[1]]
    assert lying[0].meta["wlmin"] == "150"
    t = lean_conflict_certificate(M, r, lying)
    assert "(200 : ℝ)" in t and "(150 : ℝ)" not in t
    # same for the speed cap
    lying_v = [Q[0], _swap(Q[1], terms=poly((1, {"V": 1}), (-8, {}, dim(m=1, s=-1))))]
    t = lean_conflict_certificate(M, r, lying_v)
    assert "(8 : ℝ)" in t and "(10 : ℝ)" not in t


@pytest.mark.parametrize("label,mutate", [
    ("extra term", lambda c: _swap(c, terms=c.terms + poly((1, {"b": 1}, ))[:0] + poly((1, {"S": 1}, dim(kg=1, m=-1, s=-2))))),
    ("wrong power on S", lambda c: _swap(c, terms=poly((1, {"m": 1, "g": 1}), (-150, {"S": 2}, dim(kg=1, m=-3, s=-2))))),
    ("wrong operator", lambda c: _swap(c, op="<=")),
    ("positive coefficient", lambda c: _swap(c, terms=poly((1, {"m": 1, "g": 1}), (150, {"S": 1}, dim(kg=1, m=-1, s=-2))))),
    ("different variable", lambda c: _swap(c, terms=poly((1, {"m": 1, "g": 1}), (-150, {"b": 1}, dim(kg=1, m=-1, s=-2))))),
    ("wrong coefficient on m*g", lambda c: _swap(c, terms=poly((2, {"m": 1, "g": 1}), (-150, {"S": 1}, dim(kg=1, m=-1, s=-2))))),
])
def test_structurally_different_wl_query_gets_no_certificate_even_with_matching_metadata(label, mutate):
    M, Q, r = _cert_case()
    bad = [mutate(Q[0]), Q[1]]
    assert bad[0].meta == Q[0].meta                      # metadata and names still look right
    assert lean_conflict_certificate(M, r, bad) is None, label


def test_structurally_different_speed_query_or_lift_law_gets_no_certificate():
    M, Q, r = _cert_case()
    for bad_v in (_swap(Q[1], op=">="), _swap(Q[1], terms=poly((1, {"V": 2}), (-100, {}, dim(m=2, s=-2)))),
                  _swap(Q[1], terms=poly((1, {"V": 1}), (10, {}, dim(m=1, s=-1)))),
                  _swap(Q[1], terms=poly((1, {"V": 1}), (-10, {}, dim(kg=1))))):          # wrong coefficient unit
        assert lean_conflict_certificate(M, r, [Q[0], bad_v]) is None
    # model's own lift law mutated (2 -> 8): no certificate, because the Lean lemma is about the real law
    M2 = fm()
    for i, c in enumerate(M2.constraints):
        if c.name == "level_lift_proxy":
            M2.constraints[i] = _swap(c, terms=poly((1, {"V": 2, "rho": 1, "S": 1, "CL": 1}), (-8, {"m": 1, "g": 1})))
    assert lean_conflict_certificate(M2, r, Q) is None


def test_forged_unsat_result_or_false_side_condition_gets_no_certificate():
    M, Q, r = _cert_case(wl=50, vmax=10)          # actually feasible: rho*vmax^2*CL = 122.5 >= 100
    assert r.status == "feasible"
    forged = dict(r.to_json(), status="unsat", conflict=["q_wl_min", "q_speed_max", "level_lift_proxy"])
    assert lean_conflict_certificate(M, forged, Q) is None
    # boundary: rho*vmax^2*CL == 2*wlmin exactly is NOT strictly less -> no certificate
    M2, Q2, r2 = _cert_case(wl=Fraction(245, 4), vmax=10)
    assert lean_conflict_certificate(M2, dict(r2.to_json(), status="unsat",
                                              conflict=["q_wl_min", "q_speed_max", "level_lift_proxy"]), Q2) is None
    # unset rho, duplicate names
    assert lean_conflict_certificate(flying_fish_model(CL="1"), dict(r.to_json(), status="unsat",
                                     conflict=["q_wl_min", "q_speed_max", "level_lift_proxy"]), Q) is None
    M3, Q3, r3 = _cert_case()
    assert lean_conflict_certificate(M3, r3, Q3 + [Q3[0]]) is None


def test_certificate_accepts_a_generator_query_and_materialises_it_once():
    M, Q, r = _cert_case()
    good = lean_conflict_certificate(M, r, Q)
    assert good is not None
    assert lean_conflict_certificate(M, r, (c for c in Q)) == good          # one-shot iterator
    assert lean_conflict_certificate(M, r, iter(Q)) == good
    # the iterator must not be silently half-consumed into a false 'duplicate'/'missing' verdict
    assert lean_conflict_certificate(M, r, (c for c in Q + Q)) is None       # real duplicates still rejected


def test_certificate_returns_none_for_a_dimension_invalid_model_or_query():
    M, Q, r = _cert_case()
    bad_q = Constraint("q_extra", "user_query", poly((1, {"m": 1}), (-1, {}, dim(m=1))), ">=", "x")  # kg vs m
    assert lean_conflict_certificate(M, r, Q + [bad_q]) is None
    M2 = fm()                                    # break the model AFTER building it: wrong unit on g
    M2.parameters["g"] = Parameter("g", "m/s^2", dim(m=1), Fraction(980665, 100000), "physical_law", "x")
    assert lean_conflict_certificate(M2, r, Q) is None
    M3 = fm()
    M3.parameters["rho"] = Parameter("rho", "kg/m^3", dim(kg=1, m=-3), Fraction(-1), "design_assumption", "x")
    assert lean_conflict_certificate(M3, r, Q) is None


@pytest.mark.parametrize("bad", ["x\ny", "a b", "a.b", "x:=0", "1abc", "", "foo;sorry", "theorem", "sorry", "by",
                                 "x -- c", "α\u0307", "x)"])
def test_unsafe_lean_identifier_is_refused_not_emitted(bad):
    M, Q, r = _cert_case()
    with pytest.raises(ValueError, match="unsafe Lean identifier"):
        lean_conflict_certificate(M, r, Q, name=bad)


def test_safe_names_and_unsupported_forms_still_behave():
    M, Q, r = _cert_case()
    t = lean_conflict_certificate(M, r, Q, name="my_conflict_1'")
    assert t.startswith("theorem my_conflict_1' ")
    assert lean_conflict_certificate(M, solve(M, [q_mass_min(1)]), [q_mass_min(1)]) is None   # other core
    assert lean_conflict_certificate(M, r.to_json(), Q) == lean_conflict_certificate(M, r, Q)
