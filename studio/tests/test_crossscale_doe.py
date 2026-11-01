import hashlib
import json

import pytest

from engineering.experimental_design import crossscale_screen as cs

OUT = cs.OUT


def _j(name):
    return json.loads((OUT / name).read_text())


def test_committed_artifacts_match_manifest_hashes():
    manifest = _j("manifest.json")
    for name, meta in manifest["files"].items():
        assert hashlib.sha256((OUT / name).read_bytes()).hexdigest() == meta["sha256"], name
    assert manifest["measurement_rows"] == 0


def test_protocol_is_the_builder_output_and_run_used_it():
    protocol = json.loads(cs.PROTOCOL.read_text())
    assert protocol == cs.build_protocol()
    assert _j("result.json")["protocol_sha256"] == cs.sha256_json(protocol)
    assert _j("manifest.json")["code_sha256"] == {f: hashlib.sha256((cs.ROOT / f).read_bytes()).hexdigest() for f in cs.CODE_FILES}


def test_analytic_screen_reproduces_recorded_anchor_counts_and_mutant_differs():
    doc = json.loads(cs.SIMS.read_text())
    assert hashlib.sha256(cs.SIMS.read_bytes()).hexdigest() == cs.SIMS_SHA256
    ctrl = cs.controls(doc)
    assert ctrl["C1_analytic_vs_recorded_trials"] == {"trials": 192, "mismatches": 0, "ok": True}
    assert ctrl["C3_mutant_changes_recorded_flags"]["changed_flags"] > 0
    rows = {r["id"]: r for r in _j("candidates.json")["rows"]}
    assert (rows["L0.15-EIx1"]["analytic_pass"], rows["L0.12-EIx1"]["analytic_pass"], rows["L0.15-EIx2"]["analytic_pass"]) == (20, 33, 34)


def test_every_candidate_kept_with_reasons_and_fem_agrees_where_run():
    rows = _j("candidates.json")["rows"]
    assert len(rows) == 30
    for r in rows:
        assert (r["fem"] is None) == bool(r["rejections"])
        if r["fem"]:
            assert r["fem"]["analytic_vs_fem_flag_disagreements"] == 0
            assert r["fem"]["pass"] == r["analytic_pass"]
    assert any("S1-functional-length" in r["rejections"] for r in rows)
    assert any("S3-robustness" in r["rejections"] for r in rows)


def test_baseline_is_rank_deficient_and_selected_plan_is_full_rank():
    m = _j("result.json")["measurement"]
    assert m["baseline_equal_budget"]["likelihood_rank"] == 1
    assert m["best_at_budget"]["likelihood_rank"] == 3
    assert m["best_at_budget"]["target_posterior_variance"] < m["baseline_equal_budget"]["target_posterior_variance"]
    assert m["zero_sensitivity_control"]["variance_reduction"] == 0.0


def test_instrument_contracts_complete_and_sequence_ones_stay_proposed():
    fields = {"id", "kind", "observable", "unit", "sampling_cross_section", "forward_noise_model", "calibration_context",
              "reference_control", "uncertainty", "acceptance", "status", "blocked_on"}
    assert all(set(i) == fields and all(i[k] for k in fields - {"blocked_on"}) for i in cs.INSTRUMENTS)
    status = {i["id"]: i["status"] for i in cs.INSTRUMENTS}
    assert status["P1-reporter-expression"] == status["P2-growth-to-EI"] == "proposed_uncalibrated"
    assert status["V1-saved-deflection-section"] == "simulation_derived"
    assert all(i["blocked_on"] for i in cs.INSTRUMENTS if i["status"] != "simulation_derived")


def test_virtual_validation_accepts_and_unit_mislabel_fails():
    v = _j("result.json")["virtual_validation"]
    assert v["accepted"] and v["response_rows_created"] == 0
    assert v["control_unit_mislabel"]["rejected_by_acceptance"]
    og = v["control_off_grid_refused"]
    assert og["executed"] and og["refused"] and og["error_type"] == "ValueError" and "off the saved grid" in og["message"]
    doc = json.loads(cs.SIMS.read_text())
    bad = json.loads(cs.PROTOCOL.read_text())
    bad["virtual_validation"]["sections_x_over_L"] = [0.2512]
    with pytest.raises(ValueError, match="off the saved grid"):
        cs.virtual_validation(bad, doc)


def test_run_refuses_modified_protocol(tmp_path):
    p = tmp_path / "protocol.json"
    p.write_text("{}")
    with pytest.raises(Exception):
        cs.run(p, tmp_path)


def test_no_empirical_claims():
    r = _j("result.json")
    assert r["empirical_validation"] == "none" and r["biological_success_probability"] is None and r["measurement_rows"] == []
    assert all(row["status"] != "executed" for row in _j("interface-map.json")["rows"])


def test_discounted_cost_case_considers_plans_the_nominal_budget_excluded():
    m = _j("result.json")["measurement"]
    d = m["discounted_cost_case"]
    assert d["newly_feasible_plans_considered"] > 0 and d["best_at_discount_is_newly_feasible"]
    assert d["best_variance_reduction_at_discount"] > d["best_variance_reduction_nominal_budget"]
    assert m["sensitivity"]["plans_in_full_grid"] == 255
    # the omitted plan from the superseded run: R1x3+R2x2 costs 12 nominal, 6 at half price
    assert "R1x3+R2x2" in m["sensitivity"]["plans_ranked_first_at_budget"]


def test_baseline_counts_separate_comparable_and_ineligible_scenarios():
    s = _j("result.json")["measurement"]["sensitivity"]
    assert s["baseline_comparable_scenarios"] + s["baseline_ineligible_scenarios"] == s["scenarios"]
    assert s["baseline_ineligible_scenarios"] > 0
    assert s["baseline_not_beaten_among_comparable"] <= s["baseline_comparable_scenarios"]


def test_decision_exercise_uses_actual_finalist_offset_not_a_centered_sign():
    r = _j("result.json")
    de = r["measurement"]["decision_exercise"]
    assert de["finalist_margin_offset_m0"] > 0
    assert de["sign_misclassification"]["no_measurement"] < 0.2  # superseded centered value was 0.50
    assert de["recorded_pass_fraction_finalist"] == 63 / 64
    old = json.loads((OUT / "superseded/v2-run-11b5c30/result.json").read_text())
    assert old["measurement"]["misclassification_probability_of_sign_of_margin"]["no_measurement"] > 0.45


def test_dependence_assumptions_are_declared_and_sensitivity_reported():
    protocol = json.loads(cs.PROTOCOL.read_text())
    assert "OPTIMISTIC" in protocol["measurement"]["sensitivity_grid"]["dependence"]
    dep = _j("result.json")["measurement"]["dependence_sensitivity"]
    assert dep["best_plan"] and dep["baseline_variance_reduction_under_dependence"] > 0


def test_superseded_outputs_are_preserved_with_hashes():
    sup = json.loads((OUT / "superseded/SUPERSEDED.json").read_text())
    for group in ("v2_run", "v1_runs"):
        files = sup[group]["sha256"] if group == "v2_run" else sup[group]["regenerated_sha256"]
        base = "v2-run-11b5c30" if group == "v2_run" else "v1-regenerated-4bf5481"
        for name, digest in files.items():
            assert hashlib.sha256((OUT / "superseded" / base / name).read_bytes()).hexdigest() == digest
    assert "IRRECOVERABLE" in sup["v1_runs"]["status"]


@pytest.mark.parametrize("mutate,expect", [
    (lambda c: c.pop("replicate unit"), "replicate unit"),
    (lambda c: c.update(evidence_type="measured"), "evidence_type"),
    (lambda c: c.update(blocked_on=None), "name what blocks"),
])
def test_contract_validator_rejects_mutated_physical_proposal(mutate, expect):
    contracts = {c["instrument id and version"]: c for c in _j("instrument-contracts.json")["contracts"]}
    good = contracts["R1-ray-bending@1"]
    assert cs.validate_contract(good) == []
    bad = json.loads(json.dumps(good))
    mutate(bad)
    assert any(expect in p for p in cs.validate_contract(bad))


def test_contract_validator_rejects_calibrated_looking_virtual_and_promoted_sequence_instruments():
    contracts = {c["instrument id and version"]: c for c in _j("instrument-contracts.json")["contracts"]}
    v = json.loads(json.dumps(contracts["V1-saved-deflection-section@1"]))
    assert cs.validate_contract(v) == [] and "NOT calibrated" in v["calibration_context"]
    v["calibration_context"] = "none needed"
    assert any("not calibrated to biology" in p for p in cs.validate_contract(v))
    p1 = json.loads(json.dumps(contracts["P1-reporter-expression@1"]))
    assert cs.validate_contract(p1) == []
    p1["status"] = "simulation_derived"
    assert cs.validate_contract(p1)
    q = json.loads(json.dumps(contracts["P2-growth-to-EI@1"]))
    q["status"], q["evidence_type"] = "proposal_needs_calibration", "proposed"
    assert any("proposed_uncalibrated" in p for p in cs.validate_contract(q))


def test_contract_file_carries_compiler_fields_and_slot_pointers():
    doc = _j("instrument-contracts.json")
    assert doc["compiler_required_fields"] == cs.COMPILER_FIELDS
    assert {c["proposed_compiler_slot"]["interface"] for c in doc["contracts"]} == {"I1", "I2", "I3", "I4"}
    assert all(f in c for c in doc["contracts"] for f in cs.COMPILER_FIELDS)
