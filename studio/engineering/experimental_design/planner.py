"""Validate experiment contracts and compare prospective linear-Gaussian designs."""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

import numpy as np

from frontier.models import ActionProposal, Ref

from .linear_gaussian import evaluate_design


SCHEMA = "frontier.experimental-design.request/1"
ARTIFACT_SCHEMA = "frontier.experimental-design.plan/1"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _exact_ref(value, label, kind=None):
    ref = Ref.model_validate(value)
    if kind and ref.kind != kind:
        raise ValueError(f"{label} must pin a {kind} record")
    return ref.model_dump(mode="json")


def _validate_contract(contract: dict) -> dict:
    required = {
        "schema", "title", "question", "context", "source_claims", "equation",
        "design_version", "parameters", "target", "readouts", "designs", "controls",
        "randomization", "blocking", "replicate_unit", "batch_effects", "held_out_validation",
        "input_datasets", "fit_method", "model_discrepancy", "sensitivity_plan", "resources",
        "stop_rules", "iteration", "links", "action_proposal",
    }
    if not isinstance(contract, dict) or set(contract) != required:
        raise ValueError(f"contract fields must be exactly {sorted(required)}")
    if contract["schema"] != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    _nonempty(contract["title"], "title")
    _nonempty(contract["question"], "question")
    context = contract["context"]
    context_fields = {"species", "genotype", "cell_state", "developmental_time", "environment",
                      "measurement_method", "eligibility", "open_gaps"}
    if not isinstance(context, dict) or set(context) != context_fields:
        raise ValueError(f"context fields must be exactly {sorted(context_fields)}")
    for key in context_fields - {"open_gaps"}:
        _nonempty(context[key], f"context.{key}")
    if not isinstance(context["open_gaps"], list) or any(not isinstance(x, str) or not x for x in context["open_gaps"]):
        raise ValueError("context.open_gaps must be an explicit string list")

    claims = contract["source_claims"]
    if not isinstance(claims, list):
        raise ValueError("source_claims must be a list of exact pinned Claim refs")
    source_claims = [_exact_ref(item, "source_claims", "Claim") for item in claims]
    if len({r["version"] for r in source_claims}) != len(source_claims):
        raise ValueError("duplicate source Claim version")
    equation = contract["equation"]
    eq_fields = {"expression", "model_version", "source_uri", "source_sha256", "units", "applicability"}
    if not isinstance(equation, dict) or set(equation) != eq_fields:
        raise ValueError(f"equation fields must be exactly {sorted(eq_fields)}")
    for key in ("expression", "model_version", "source_uri", "applicability"):
        _nonempty(equation[key], f"equation.{key}")
    if not SHA_RE.fullmatch(str(equation["source_sha256"])):
        raise ValueError("equation.source_sha256 must be a lowercase SHA-256")
    if not isinstance(equation["units"], dict) or not equation["units"]:
        raise ValueError("equation.units must declare unit conventions")

    _nonempty(contract["design_version"], "design_version")
    parameters = contract["parameters"]
    p_fields = {"names", "units", "prior_mean", "prior_covariance", "hypotheses", "likelihood"}
    if not isinstance(parameters, dict) or set(parameters) != p_fields:
        raise ValueError(f"parameters fields must be exactly {sorted(p_fields)}")
    names, units = parameters["names"], parameters["units"]
    if not isinstance(names, list) or not names or len(set(names)) != len(names) or any(not isinstance(x, str) or not x for x in names):
        raise ValueError("parameters.names must be unique nonempty strings")
    if not isinstance(units, list) or len(units) != len(names) or any(not isinstance(x, str) or not x for x in units):
        raise ValueError("every parameter needs an explicit unit")
    if any(unit != "1" for unit in units):
        raise ValueError("SPEC-013 linear-Gaussian v1 requires dimensionless parameters")
    _nonempty(parameters["likelihood"], "parameters.likelihood")
    if not isinstance(parameters["hypotheses"], list) or not parameters["hypotheses"]:
        raise ValueError("parameters.hypotheses must be stated")
    prior_mean = np.asarray(parameters["prior_mean"], dtype=float)
    if prior_mean.shape != (len(names),) or not np.all(np.isfinite(prior_mean)):
        raise ValueError("prior_mean must match the dimensionless parameter vector")
    prior_cov = np.asarray(parameters["prior_covariance"], dtype=float)
    if prior_cov.shape != (len(names), len(names)):
        raise ValueError("prior_covariance shape must match parameters")
    # The numerical evaluator performs the symmetry and PSD check.
    target = contract["target"]
    if not isinstance(target, dict) or set(target) != {"name", "unit", "vector"}:
        raise ValueError("target must name a declared scalar estimand and unit")
    _nonempty(target["name"], "target.name")
    _nonempty(target["unit"], "target.unit")
    if target["unit"] != "1":
        raise ValueError("target coefficients must produce a dimensionless estimand")
    target_vector = np.asarray(target["vector"], dtype=float)
    if target_vector.shape != (len(names),) or not np.all(np.isfinite(target_vector)):
        raise ValueError("target.vector must match parameter dimensions")

    readouts = contract["readouts"]
    if not isinstance(readouts, list) or not readouts:
        raise ValueError("at least one readout definition is required")
    readout_by_id = {}
    r_fields = {"id", "definition", "unit", "sensitivity", "noise_variance", "sampling_times",
                "detection_limit", "censoring", "missingness"}
    for readout in readouts:
        if not isinstance(readout, dict) or set(readout) != r_fields:
            raise ValueError(f"readout fields must be exactly {sorted(r_fields)}")
        identifier = _nonempty(readout["id"], "readout.id")
        if identifier in readout_by_id:
            raise ValueError("readout ids must be unique")
        _nonempty(readout["definition"], f"readout {identifier} definition")
        _nonempty(readout["unit"], f"readout {identifier} unit")
        sensitivity = np.asarray(readout["sensitivity"], dtype=float)
        if sensitivity.shape != (len(names),) or not np.all(np.isfinite(sensitivity)):
            raise ValueError(f"readout {identifier} sensitivity does not match parameters")
        variance = readout["noise_variance"]
        if isinstance(variance, bool) or not isinstance(variance, (int, float)) or not math.isfinite(variance) or variance <= 0:
            raise ValueError(f"readout {identifier} needs a positive assumed noise variance")
        sampling_times = readout["sampling_times"]
        if not ((isinstance(sampling_times, list) and all(isinstance(t, (int, float, str)) for t in sampling_times))
                or (isinstance(sampling_times, str) and sampling_times.strip())):
            raise ValueError("sampling_times must be an explicit list or not-applicable/unknown string")
        for key in ("detection_limit", "censoring", "missingness"):
            _nonempty(readout[key], f"readout {identifier}.{key}")
        readout_by_id[identifier] = readout

    designs = contract["designs"]
    if not isinstance(designs, list) or not designs:
        raise ValueError("at least one candidate design is required")
    design_ids = set()
    shared_cost_unit = None
    comparison_rows = []
    for design in designs:
        d_fields = {"id", "title", "intervention", "observations", "noise_covariance", "cost", "batch_count"}
        if not isinstance(design, dict) or set(design) != d_fields:
            raise ValueError(f"design fields must be exactly {sorted(d_fields)}")
        design_id = _nonempty(design["id"], "design.id")
        if design_id in design_ids:
            raise ValueError("design ids must be unique")
        design_ids.add(design_id)
        _nonempty(design["title"], f"design {design_id} title")
        _nonempty(design["intervention"], f"design {design_id} intervention")
        observations = design["observations"]
        if not isinstance(observations, list) or not observations:
            raise ValueError(f"design {design_id} must declare observations/readouts")
        obs_fields = {"readout_id", "condition", "biological_replicate", "technical_repeat", "batch"}
        matrix = []
        for observation in observations:
            if not isinstance(observation, dict) or set(observation) != obs_fields:
                raise ValueError(f"observations must carry explicit context/replicate/batch fields: {sorted(obs_fields)}")
            readout = readout_by_id.get(observation["readout_id"])
            if readout is None:
                raise ValueError(f"unknown readout {observation['readout_id']}")
            for key in ("condition", "biological_replicate", "batch"):
                _nonempty(observation[key], f"observation.{key}")
            if isinstance(observation["technical_repeat"], bool) or not isinstance(observation["technical_repeat"], int) or observation["technical_repeat"] < 1:
                raise ValueError("technical_repeat must be a positive integer")
            matrix.append(readout["sensitivity"])
        h = np.asarray(matrix, dtype=float)
        noise = np.asarray(design["noise_covariance"], dtype=float)
        if noise.shape != (len(observations), len(observations)):
            raise ValueError(f"{design_id} noise covariance must match its observation rows")
        expected_diag = np.asarray([readout_by_id[o["readout_id"]]["noise_variance"] for o in observations], dtype=float)
        if not np.allclose(np.diag(noise), expected_diag, rtol=1e-10, atol=1e-12):
            raise ValueError(f"{design_id} noise diagonal must match readout variances; shared errors belong off-diagonal")
        cost = design["cost"]
        if not isinstance(cost, dict) or set(cost) != {"value", "unit", "basis"}:
            raise ValueError("cost must state value, unit, and basis")
        _nonempty(cost["unit"], "cost.unit")
        _nonempty(cost["basis"], "cost.basis")
        if shared_cost_unit is None:
            shared_cost_unit = cost["unit"]
        elif cost["unit"] != shared_cost_unit:
            raise ValueError("candidate designs must use the same declared cost unit")
        amount = cost["value"]
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0:
            raise ValueError("cost.value must be positive and finite")
        if isinstance(design["batch_count"], bool) or not isinstance(design["batch_count"], int) or design["batch_count"] < 1:
            raise ValueError("batch_count must be a positive integer")
        metrics = evaluate_design(parameters["prior_covariance"], h, noise, target_vector, amount)
        comparison_rows.append({"id": design_id, "title": design["title"], "intervention": design["intervention"],
                                "observations": observations, "cost": cost, "batch_count": design["batch_count"],
                                **metrics})

    for key in ("controls", "held_out_validation"):
        if not isinstance(contract[key], list) or not contract[key] or any(not isinstance(x, str) or not x for x in contract[key]):
            raise ValueError(f"{key} must explicitly state applicable controls/held-out plans or why not applicable")
    for key in ("randomization", "blocking", "replicate_unit", "batch_effects", "fit_method", "model_discrepancy", "sensitivity_plan"):
        _nonempty(contract[key], key)
    datasets = contract["input_datasets"]
    if not isinstance(datasets, list):
        raise ValueError("input_datasets must be a list")
    for dataset in datasets:
        required_dataset = {"assembly", "locus", "sample", "sha256", "source_uri", "use"}
        if not isinstance(dataset, dict) or set(dataset) != required_dataset:
            raise ValueError(f"input dataset fields must be exactly {sorted(required_dataset)}")
        for key in required_dataset:
            _nonempty(dataset[key], f"dataset.{key}")
        if not SHA_RE.fullmatch(dataset["sha256"]):
            raise ValueError("input dataset sha256 must be lowercase SHA-256")
    resources = contract["resources"]
    resource_fields = {"capability", "duration", "duration_unit", "cost_unit", "concurrency", "stop_limit", "operator"}
    if not isinstance(resources, dict) or set(resources) != resource_fields:
        raise ValueError(f"resources fields must be exactly {sorted(resource_fields)}")
    for key in resource_fields:
        _nonempty(resources[key], f"resources.{key}")
    if not isinstance(contract["stop_rules"], list) or not contract["stop_rules"] or any(not isinstance(x, str) or not x for x in contract["stop_rules"]):
        raise ValueError("stop_rules must be explicit")
    iteration = contract["iteration"]
    if not isinstance(iteration, dict) or set(iteration) != {"parent_versions", "iteration_number", "rationale"}:
        raise ValueError("iteration must carry parent version pins, number, and rationale")
    if not isinstance(iteration["parent_versions"], list) or any(not SHA_RE.fullmatch(x) for x in iteration["parent_versions"]):
        raise ValueError("iteration.parent_versions must be exact SHA-256 version pins")
    if isinstance(iteration["iteration_number"], bool) or not isinstance(iteration["iteration_number"], int) or iteration["iteration_number"] < 1:
        raise ValueError("iteration_number must be a positive integer")
    _nonempty(iteration["rationale"], "iteration.rationale")
    links = contract["links"]
    link_fields = {"project_ref", "problem_ref", "action_ref"}
    if not isinstance(links, dict) or set(links) != link_fields:
        raise ValueError(f"links fields must be exactly {sorted(link_fields)}")
    for key, kind in (("project_ref", "Project"), ("problem_ref", "Problem"), ("action_ref", "Action")):
        if links[key] is not None:
            links[key] = _exact_ref(links[key], f"links.{key}", kind)
    if not isinstance(contract["action_proposal"], dict):
        raise ValueError("action_proposal must match the existing ActionProposal contract")
    proposal = ActionProposal.model_validate(contract["action_proposal"]).model_dump(mode="json")
    contract["source_claims"] = source_claims
    contract["action_proposal"] = proposal
    return contract


def plan_experiments(contract: dict) -> dict:
    """Compare candidate designs and return prospective covariance plus an ActionProposal.

    No response values are accepted, no measurement rows are generated, and no store
    or lab write occurs. The optional exact links are passed through; absent context
    refs remain an explicit blocker to a versioned Action submission.
    """
    request_sha256 = sha256_json(contract)
    normalized = _validate_contract(json.loads(canonical_json(contract)))
    design_rows = []
    for design in normalized["designs"]:
        h = np.asarray([next(r["sensitivity"] for r in normalized["readouts"] if r["id"] == o["readout_id"])
                        for o in design["observations"]], dtype=float)
        metrics = evaluate_design(normalized["parameters"]["prior_covariance"], h,
                                  design["noise_covariance"], normalized["target"]["vector"], design["cost"]["value"])
        design_rows.append({"id": design["id"], "title": design["title"], "intervention": design["intervention"],
                            "observations": design["observations"], "cost": metrics["cost"],
                            "cost_unit": design["cost"]["unit"], "cost_basis": design["cost"]["basis"],
                            "batch_count": design["batch_count"], **{k: v for k, v in metrics.items() if k != "cost"}})
    design_rows.sort(key=lambda row: (-row["expected_target_variance_reduction_per_cost"], row["id"]))
    chosen = design_rows[0]
    links = normalized["links"]
    linked = any(links.values())
    artifact = {
        "schema": ARTIFACT_SCHEMA,
        "artifact_kind": "prospective_experiment_design",
        "state": "proposal_unsubmitted" if linked else "proposal_unlinked",
        "links": links,
        "link_blockers": [] if linked else ["Pin an exact Problem, Project, or Action Ref before submitting a versioned Action."],
        "protocol_sha256": request_sha256,
        "normalized_contract_sha256": sha256_json(normalized),
        "equation": normalized["equation"],
        "context": normalized["context"],
        "source_claims": normalized["source_claims"],
        "input_datasets": normalized["input_datasets"],
        "action_proposal": normalized["action_proposal"],
        "measurement_rows": [],
        "observed_result": None,
    }
    return {
        "schema": ARTIFACT_SCHEMA,
        "status": "prospective_assumption_based",
        "protocol_sha256": artifact["protocol_sha256"],
        "normalized_contract_sha256": artifact["normalized_contract_sha256"],
        "design_version": normalized["design_version"],
        "context": normalized["context"],
        "source_claims": normalized["source_claims"],
        "equation": normalized["equation"],
        "parameters": normalized["parameters"],
        "target": normalized["target"],
        "model_discrepancy": normalized["model_discrepancy"],
        "fit_method": normalized["fit_method"],
        "controls": normalized["controls"],
        "randomization": normalized["randomization"],
        "blocking": normalized["blocking"],
        "replicate_unit": normalized["replicate_unit"],
        "batch_effects": normalized["batch_effects"],
        "held_out_validation": normalized["held_out_validation"],
        "input_datasets": normalized["input_datasets"],
        "resources": normalized["resources"],
        "stop_rules": normalized["stop_rules"],
        "iteration": normalized["iteration"],
        "selection_objective": {
            "name": "expected_target_variance_reduction_per_cost",
            "target": normalized["target"]["name"],
            "target_unit": normalized["target"]["unit"],
                "cost_unit": design_rows[0]["cost_unit"],
            "basis": "analytic linear-Gaussian prospective covariance; no observed response values",
        },
        "designs": design_rows,
        "selected_design_id": chosen["id"],
        "measurement_rows": [],
        "action_artifact": artifact,
    }
