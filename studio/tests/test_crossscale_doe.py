import hashlib
import json
from pathlib import Path

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
