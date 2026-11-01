from copy import deepcopy

import numpy as np
import pytest

from frontier.models import ActionProposal
from engineering.experimental_design.linear_gaussian import evaluate_design, posterior_covariance
from engineering.experimental_design.planner import plan_experiments


def action_proposal():
    return {
        "intent": "experiment",
        "method": "Compare prospective Gaussian covariance under two equal assumed-cost readout plans; no response values are used.",
        "assumptions": ["Dimensionless log-ratio prior and noise values are assumed, not fitted.",
                        "This abstract cantilever calculation has no species calibration."],
        "alternatives": [
            {"label": "deflection-only", "description": "Two normalized deflection reads at different nominal force settings.",
             "tradeoff": "Same sensitivity row; cannot separate stiffness from load calibration."},
            {"label": "mixed", "description": "One normalized deflection read and one independent load-scale read.",
             "tradeoff": "Assumes the load-scale read is available at equal declared cost."},
        ],
        "expected_information": "Expected reduction in variance of dimensionless log stiffness per assumed cost unit.",
        "decision_context": "Choose an illustrative readout design that makes stiffness identifiable under the stated linear model.",
        "expected_outputs": ["Prospective covariance, rank/nullspace diagnostics, and a frozen design comparison."],
        "controls": ["Repeated-force sensitivity remains rank one.", "Independent load sensitivity raises rank to two.",
                     "Zero-sensitivity readout has zero expected target-variance reduction."],
        "analysis_plan": "Use exact linear-Gaussian covariance conditioning and compare the predeclared target variance reduction per equal assumed cost.",
        "outcomes": [
            {"label": "mixed-rank-two", "criterion": "Mixed plan has full likelihood rank and greater target variance reduction per equal cost.",
             "decision_consequence": "Retain as the selected prospective design under this assumed model only."},
            {"label": "not-discriminating", "criterion": "Rank or expected target-variance comparison does not meet the predeclared relation.",
             "decision_consequence": "Keep the design comparison unresolved and inspect assumptions."},
        ],
        "selection_basis": "declared_utility",
        "selection_rationale": "Rank candidate plans by declared expected target-variance reduction per shared assumed cost unit.",
        "limitations": ["No measurements, biological parameters, empirical posterior, or physical success probability are generated.",
                        "The design is not linked or submitted until exact Problem/Project refs are supplied."],
    }


def contract():
    def observation(readout, condition):
        return {"readout_id": readout, "condition": condition, "biological_replicate": "not_applicable_mathematical_example",
                "technical_repeat": 1, "batch": "one_assumed_batch"}

    return {
        "schema": "frontier.experimental-design.request/1",
        "title": "Prospective cantilever stiffness identifiability comparison",
        "question": "At equal assumed measurement cost, does an independent load-scale readout resolve the stiffness/load degeneracy?",
        "context": {"species": "not_applicable_mathematical_cantilever", "genotype": "not_applicable",
                    "cell_state": "not_applicable", "developmental_time": "not_applicable",
                    "environment": "not_applicable; static mathematical beam", "measurement_method": "prospective dimensionless readout model",
                    "eligibility": "abstract model only; no specimen or organism eligibility", "open_gaps": ["No biological calibration or source Claim pin is supplied."]},
        "source_claims": [],
        "equation": {"expression": "delta = F * L^3 / (3 * EI)", "model_version": "engineering.fin_mechanics.beam/1",
                     "source_uri": "repo:engineering/fin_mechanics/beam.py#tip_deflection_point_load",
                     "source_sha256": "a" * 64,
                     "units": {"delta": "m", "F": "N", "L": "m", "EI": "N m^2",
                               "parameters": "dimensionless log-ratios", "normalized_log_readout": "1"},
                     "applicability": "Euler-Bernoulli static small-deflection cantilever point-load model; mathematical demonstration only."},
        "design_version": "cantilever-identifiability-v1",
        "parameters": {"names": ["log_EI_ratio", "log_load_scale"], "units": ["1", "1"],
                       "prior_mean": [0.0, 0.0], "prior_covariance": [[0.36, 0.18], [0.18, 0.25]],
                       "hypotheses": ["Assumed joint Gaussian prior with correlated log-stiffness and log-load calibration."],
                       "likelihood": "Linear Gaussian normalized log-readouts; measurement noise variance 0.01 is assumed, not calibrated."},
        "target": {"name": "log_EI_ratio", "unit": "1", "vector": [1.0, 0.0]},
        "readouts": [
            {"id": "normalized_log_deflection", "definition": "log(delta) minus known nominal geometry/load offset", "unit": "1",
             "sensitivity": [-1.0, 1.0], "noise_variance": 0.01, "sampling_times": "not_applicable_static_scalar",
             "detection_limit": "not_applicable_in_abstract_model", "censoring": "none_assumed",
             "missingness": "none_assumed; no observations exist"},
            {"id": "direct_log_load_scale", "definition": "Independent log load-calibration readout", "unit": "1",
             "sensitivity": [0.0, 1.0], "noise_variance": 0.01, "sampling_times": "not_applicable_static_scalar",
             "detection_limit": "not_applicable_in_abstract_model", "censoring": "none_assumed",
             "missingness": "none_assumed; no observations exist"},
        ],
        "designs": [
            {"id": "deflection_only", "title": "Two deflection reads at different nominal force settings",
             "intervention": "Set nominal force ratios 1 and 2; normalize out their known offsets.",
             "observations": [observation("normalized_log_deflection", "nominal_force_ratio=1"),
                             observation("normalized_log_deflection", "nominal_force_ratio=2")],
             "noise_covariance": [[0.01, 0.0], [0.0, 0.01]],
             "cost": {"value": 2.0, "unit": "assumed_readout_cost_unit", "basis": "two reads at one assumed unit each; not a dollar cost"},
             "batch_count": 1},
            {"id": "mixed_load_deflection", "title": "One direct load-scale and one deflection read",
             "intervention": "Acquire independent load-scale read plus one normalized deflection read.",
             "observations": [observation("direct_log_load_scale", "load_scale_sensor"),
                             observation("normalized_log_deflection", "nominal_force_ratio=1")],
             "noise_covariance": [[0.01, 0.0], [0.0, 0.01]],
             "cost": {"value": 2.0, "unit": "assumed_readout_cost_unit", "basis": "two reads at one assumed unit each; not a dollar cost"},
             "batch_count": 1},
        ],
        "controls": ["Two nominal-force deflections have identical normalized sensitivity [-1,+1].",
                     "Independent load-scale sensitivity is [0,+1].",
                     "No synthetic response or result table is provided."],
        "randomization": "Not applicable to deterministic mathematical design calculation; no observations assigned.",
        "blocking": "Not applicable to the abstract calculation; a physical study would need randomized/blocking protocol from an executing lab.",
        "replicate_unit": "No biological replicate unit; two explicitly modeled readouts are not biological replicates.",
        "batch_effects": "Noise covariance is diagonal by assumption; shared-batch error is not modeled or measured.",
        "held_out_validation": ["No observations or validation split exist; empirical fit/validation is blocked."],
        "input_datasets": [],
        "fit_method": "Analytic prospective Gaussian covariance update; no data fitting and no posterior mean update.",
        "model_discrepancy": "Unknown and unestimated; no simulator-to-beam or beam-to-biology discrepancy model is fitted.",
        "sensitivity_plan": "Report the exact likelihood rank/nullspace and vary prior/noise assumptions only in a separately versioned protocol.",
        "resources": {"capability": "local CPU; deterministic 2x2 linear algebra", "duration": "under 1", "duration_unit": "second assumed",
                      "cost_unit": "assumed_readout_cost_unit", "concurrency": "1 local process", "stop_limit": "one deterministic calculation",
                      "operator": "unassigned local proposal; no lab or cloud job"},
        "stop_rules": ["Stop if covariance is nonfinite, asymmetric, or non-positive-semidefinite.",
                       "Do not submit or execute the physical plan without exact context refs and lab constraints."],
        "iteration": {"parent_versions": [], "iteration_number": 1, "rationale": "Initial prospective identifiability demo, not a biological design iteration."},
        "links": {"project_ref": None, "problem_ref": None, "action_ref": None},
        "action_proposal": action_proposal(),
    }


def test_correlated_noise_update_exact_small_case():
    prior = [[1.0, 0.5], [0.5, 1.0]]
    h = [[0.0, 1.0]]
    posterior = posterior_covariance(prior, h, [[1.0]])
    assert np.allclose(posterior, [[0.875, 0.25], [0.25, 0.5]])


def test_protocol_compares_equal_cost_designs_and_preserves_rank_one_control():
    result = plan_experiments(contract())
    designs = {row["id"]: row for row in result["designs"]}
    repeated = designs["deflection_only"]
    mixed = designs["mixed_load_deflection"]
    assert repeated["cost"] == mixed["cost"] == 2.0
    assert repeated["identifiability"]["rank"] == 1
    assert repeated["identifiability"]["full_rank"] is False
    assert mixed["identifiability"]["rank"] == 2
    assert mixed["expected_target_variance_reduction_per_cost"] > repeated["expected_target_variance_reduction_per_cost"]
    assert result["selected_design_id"] == "mixed_load_deflection"
    assert result["measurement_rows"] == []
    assert result["action_artifact"]["measurement_rows"] == []
    assert result["action_artifact"]["observed_result"] is None
    assert result["action_artifact"]["state"] == "proposal_unlinked"
    ActionProposal.model_validate(result["action_artifact"]["action_proposal"])


def test_zero_sensitivity_has_no_gain_and_positive_cost_is_required():
    result = evaluate_design([[1.0, 0.2], [0.2, 1.0]], [[0.0, 0.0]], [[0.1]], [1.0, 0.0], cost=4)
    assert result["expected_target_variance_reduction"] == pytest.approx(0.0, abs=1e-12)
    assert result["expected_information_nats"] == pytest.approx(0.0, abs=1e-12)
    with pytest.raises(ValueError, match="cost must be positive"):
        evaluate_design([[1.0]], [[1.0]], [[1.0]], [1.0], cost=0)


@pytest.mark.parametrize("bad", [[[-0.1, 0.0], [0.0, 1.0]], [[1.0, 0.2], [0.1, 1.0]]])
def test_invalid_prior_covariance_rejected(bad):
    with pytest.raises(ValueError):
        posterior_covariance(bad, [[1.0, 0.0]], [[1.0]])


def test_positive_semidefinite_prior_is_accepted():
    prior = [[1.0, 1.0], [1.0, 1.0]]
    result = posterior_covariance(prior, [[1.0, -1.0]], [[0.1]])
    assert np.allclose(result, prior, atol=1e-10)


def test_invalid_noise_covariance_and_missing_protocol_field_rejected():
    with pytest.raises(ValueError, match="positive definite"):
        posterior_covariance([[1.0]], [[1.0], [1.0]], [[1.0, 2.0], [2.0, 1.0]])
    bad = deepcopy(contract())
    del bad["replicate_unit"]
    with pytest.raises(ValueError, match="contract fields"):
        plan_experiments(bad)


def test_protocol_has_stable_hash_and_unlinked_plan_is_not_claimed_submitted():
    first = plan_experiments(contract())
    second = plan_experiments(contract())
    assert first["protocol_sha256"] == second["protocol_sha256"]
    assert first["action_artifact"]["link_blockers"]
    assert first["action_artifact"]["state"] == "proposal_unlinked"

