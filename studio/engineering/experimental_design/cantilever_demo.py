"""Frozen abstract cantilever experiment-design example.

This is a mathematical identifiability demonstration, not a species model or
measurement. ``freeze_protocol`` creates the protocol artifact; ``run_demo`` only
reads that frozen file and writes prospective covariance/plot data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from .planner import canonical_json, plan_experiments, sha256_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTOCOL = ROOT / "artifacts/experimental-design/protocol.json"
DEFAULT_OUTPUT = ROOT / "artifacts/experimental-design"
BEAM_SOURCE = ROOT / "engineering/fin_mechanics/beam.py"
BEAM_SOURCE_SHA256 = "4dfceb004a2eddef9cad27f09b744710de2a8b9b7f9f9e232b756e3cb4683b5d"
BEAM_SOURCE_COMMIT = "72df07cb22ec6458625fd01092ceccda8ea96271"


def _action_proposal():
    return {
        "intent": "experiment",
        "method": "Compare prospective Gaussian covariance under two equal assumed-cost readout plans; no response values are used.",
        "assumptions": [
            "Dimensionless log-ratio prior and readout-noise values are assumed, not fitted.",
            "This abstract cantilever calculation has no species calibration.",
        ],
        "alternatives": [
            {"label": "deflection-only", "description": "Two normalized deflection reads at different nominal force settings.",
             "tradeoff": "Same sensitivity row; cannot separate stiffness from load calibration."},
            {"label": "mixed", "description": "One normalized deflection read and one independent load-scale read.",
             "tradeoff": "Assumes the load-scale read is available at equal declared cost."},
        ],
        "expected_information": "Expected reduction in variance of dimensionless log stiffness per assumed cost unit.",
        "decision_context": "Choose an illustrative readout design that makes stiffness identifiable under the stated linear model.",
        "expected_outputs": ["Prospective covariance, rank/nullspace diagnostics, and a frozen design comparison."],
        "controls": [
            "Repeated-force deflections have the same sensitivity row and remain rank one.",
            "An independent load-scale readout supplies the second direction.",
            "A zero-sensitivity readout has zero expected target-variance reduction.",
        ],
        "analysis_plan": "Use exact linear-Gaussian covariance conditioning and compare the predeclared target variance reduction per equal assumed cost.",
        "outcomes": [
            {"label": "mixed-rank-two", "criterion": "Mixed plan has full likelihood rank and greater target variance reduction per equal cost.",
             "decision_consequence": "Retain as the selected prospective design under this assumed model only."},
            {"label": "not-discriminating", "criterion": "Rank or expected target-variance comparison does not meet the predeclared relation.",
             "decision_consequence": "Keep the design comparison unresolved and inspect assumptions."},
        ],
        "selection_basis": "declared_utility",
        "selection_rationale": "Rank candidate plans by declared expected target-variance reduction per shared assumed cost unit.",
        "limitations": [
            "No measurements, biological parameters, empirical posterior, or physical success probability are generated.",
            "The local proposal is not linked/submitted until exact Problem/Project refs are supplied.",
        ],
    }


def build_cantilever_protocol() -> dict:
    """Return the preregistered contract; call once to freeze protocol.json."""
    def observation(readout, condition):
        return {"readout_id": readout, "condition": condition,
                "biological_replicate": "not_applicable_mathematical_example",
                "technical_repeat": 1, "batch": "one_assumed_batch"}

    return {
        "schema": "frontier.experimental-design.request/1",
        "title": "Prospective cantilever stiffness identifiability comparison",
        "question": "At equal assumed measurement cost, does an independent load-scale readout resolve the stiffness/load degeneracy?",
        "context": {
            "species": "not_applicable_mathematical_cantilever",
            "genotype": "not_applicable",
            "cell_state": "not_applicable",
            "developmental_time": "not_applicable",
            "environment": "not_applicable; static mathematical beam",
            "measurement_method": "prospective dimensionless readout model",
            "eligibility": "abstract model only; no specimen or organism eligibility",
            "open_gaps": ["No biological calibration, species bridge, or source Claim pin is supplied."],
        },
        "source_claims": [],
        "equation": {
            "expression": "delta = F * L^3 / (3 * EI)",
            "model_version": "engineering.fin_mechanics.beam/point-load/1",
            "source_uri": f"https://github.com/kganjam/delphi-frontier/blob/{BEAM_SOURCE_COMMIT}/engineering/fin_mechanics/beam.py",
            "source_sha256": BEAM_SOURCE_SHA256,
            "units": {
                "delta": "m", "F": "N", "L": "m", "EI": "N m^2",
                "parameters": "dimensionless log-ratios", "normalized_log_readout": "1",
            },
            "applicability": "Euler-Bernoulli static small-deflection cantilever point-load model; mathematical demonstration only.",
        },
        "design_version": "cantilever-identifiability-v1",
        "parameters": {
            "names": ["log_EI_ratio", "log_load_scale"],
            "units": ["1", "1"],
            "prior_mean": [0.0, 0.0],
            "prior_covariance": [[0.36, 0.18], [0.18, 0.25]],
            "hypotheses": [
                "Assumed Gaussian prior: SD(log_EI_ratio)=0.6, SD(log_load_scale)=0.5, correlation=0.6; covariance entry 0.18 is the declared product 0.6*0.5*0.6.",
            ],
            "likelihood": "Linear Gaussian normalized log-readouts; each assumed noise variance is 0.01 (SD 0.1), not calibrated.",
        },
        "target": {"name": "log_EI_ratio", "unit": "1", "vector": [1.0, 0.0]},
        "readouts": [
            {
                "id": "normalized_log_deflection",
                "definition": "log(delta) minus known nominal geometry/load offset",
                "unit": "1", "sensitivity": [-1.0, 1.0], "noise_variance": 0.01,
                "sampling_times": "not_applicable_static_scalar",
                "detection_limit": "not_applicable_in_abstract_model",
                "censoring": "none_assumed", "missingness": "none_assumed; no observations exist",
            },
            {
                "id": "direct_log_load_scale",
                "definition": "Independent log load-calibration readout",
                "unit": "1", "sensitivity": [0.0, 1.0], "noise_variance": 0.01,
                "sampling_times": "not_applicable_static_scalar",
                "detection_limit": "not_applicable_in_abstract_model",
                "censoring": "none_assumed", "missingness": "none_assumed; no observations exist",
            },
        ],
        "designs": [
            {
                "id": "deflection_only",
                "title": "Two deflection reads at different nominal force settings",
                "intervention": "Set nominal force ratios 1 and 2; normalize out their known offsets.",
                "observations": [
                    observation("normalized_log_deflection", "nominal_force_ratio=1"),
                    observation("normalized_log_deflection", "nominal_force_ratio=2"),
                ],
                "noise_covariance": [[0.01, 0.0], [0.0, 0.01]],
                "cost": {"value": 2.0, "unit": "assumed_readout_cost_unit",
                         "basis": "two reads at one assumed unit each; not a dollar cost"},
                "batch_count": 1,
            },
            {
                "id": "mixed_load_deflection",
                "title": "One direct load-scale and one deflection read",
                "intervention": "Acquire an independent load-scale read plus one normalized deflection read.",
                "observations": [
                    observation("direct_log_load_scale", "load_scale_sensor"),
                    observation("normalized_log_deflection", "nominal_force_ratio=1"),
                ],
                "noise_covariance": [[0.01, 0.0], [0.0, 0.01]],
                "cost": {"value": 2.0, "unit": "assumed_readout_cost_unit",
                         "basis": "two reads at one assumed unit each; not a dollar cost"},
                "batch_count": 1,
            },
        ],
        "controls": [
            "Two nominal-force deflections have identical normalized sensitivity [-1,+1].",
            "Independent load-scale sensitivity is [0,+1].",
            "No synthetic response or measurement table is included.",
        ],
        "randomization": "Not applicable to deterministic mathematical design calculation; no observations assigned.",
        "blocking": "Not applicable to the abstract calculation; a physical study needs its executing lab's constraints and review.",
        "replicate_unit": "No biological replicate unit; two modeled readouts are not biological replicates.",
        "batch_effects": "The diagonal noise covariance assumes independent readout errors; shared-batch error is not modeled or measured.",
        "held_out_validation": ["No observations or validation split exist; empirical fit/validation is blocked."],
        "input_datasets": [],
        "fit_method": "Analytic prospective Gaussian covariance update; no data fitting and no posterior mean update.",
        "model_discrepancy": "Unknown and unestimated; no simulator-to-beam or beam-to-biology discrepancy model is fitted.",
        "sensitivity_plan": "Report exact likelihood rank/nullspace and vary prior/noise assumptions only in a separately versioned protocol.",
        "resources": {
            "capability": "local CPU; deterministic 2x2 linear algebra",
            "duration": "under 1", "duration_unit": "second assumed",
            "cost_unit": "assumed_readout_cost_unit",
            "concurrency": "1 local process", "stop_limit": "one deterministic calculation",
            "operator": "unassigned local proposal; no lab or cloud job",
        },
        "stop_rules": [
            "Stop if covariance is nonfinite, asymmetric, or not positive semidefinite.",
            "Do not submit or execute a physical plan without exact context refs and executing-lab constraints.",
        ],
        "iteration": {"parent_versions": [], "iteration_number": 1,
                      "rationale": "Initial prospective identifiability demo, not a biological design iteration."},
        "links": {"project_ref": None, "problem_ref": None, "action_ref": None},
        "action_proposal": _action_proposal(),
    }


def freeze_protocol(path: Path = DEFAULT_PROTOCOL) -> str:
    """Write the immutable prospective protocol artifact and return its canonical hash."""
    protocol = build_cantilever_protocol()
    raw = (json.dumps(protocol, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise FileExistsError("refusing to replace a different frozen protocol")
    if not path.exists():
        path.write_bytes(raw)
    return sha256_json(protocol)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _require_committed_protocol(protocol_path: Path) -> None:
    """Require a tracked, clean protocol so execution follows preregistration."""
    try:
        relative = protocol_path.resolve().relative_to(ROOT.resolve())
        subprocess.run(["git", "ls-files", "--error-unmatch", str(relative)], cwd=ROOT,
                       capture_output=True, text=True, timeout=10, check=True)
        status = subprocess.run(["git", "status", "--porcelain", "--", str(relative)], cwd=ROOT,
                               capture_output=True, text=True, timeout=10, check=True).stdout
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("protocol must be a committed file within this repository") from exc
    if status.strip():
        raise RuntimeError("protocol has uncommitted changes; commit the frozen protocol before running")


def run_demo(protocol_path: Path = DEFAULT_PROTOCOL, output_dir: Path = DEFAULT_OUTPUT) -> dict:
    """Read a committed protocol and write prospective result/plot data plus hash manifest."""
    protocol_path = Path(protocol_path)
    if not protocol_path.is_file():
        raise FileNotFoundError("freeze and commit protocol.json before running the demo")
    _require_committed_protocol(protocol_path)
    protocol = json.loads(protocol_path.read_text())
    result = plan_experiments(protocol)
    try:
        code_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                     text=True, timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("could not identify the exact code commit") from exc
    code_files = [Path(__file__), Path(__file__).with_name("planner.py"), Path(__file__).with_name("linear_gaussian.py")]
    code_hashes = {str(path.relative_to(ROOT)): _sha256_file(path) for path in code_files}
    result["reproducibility"] = {"code_commit": code_commit, "code_sha256": code_hashes,
                                 "protocol_file_sha256": _sha256_file(protocol_path)}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "result.json"
    plot_data_path = output_dir / "plot-data.json"
    result_path.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    plot_data = {
        "schema": "frontier.experimental-design.plot-data/1",
        "label": "prospective covariance under stated assumptions; no measurements",
        "objective": result["selection_objective"],
        "selected_design_id": result["selected_design_id"],
        "designs": [{
            "id": row["id"], "label": row["title"], "cost": row["cost"], "cost_unit": row["cost_unit"],
            "target_prior_variance": row["target_prior_variance"],
            "expected_target_posterior_variance": row["expected_target_posterior_variance"],
            "expected_target_variance_reduction": row["expected_target_variance_reduction"],
            "expected_target_variance_reduction_per_cost": row["expected_target_variance_reduction_per_cost"],
            "likelihood_rank": row["identifiability"]["rank"],
            "parameter_count": row["identifiability"]["parameter_count"],
            "nullspace_basis": row["identifiability"]["nullspace_basis"],
            "prospective_covariance": row["expected_posterior_covariance"],
        } for row in result["designs"]],
        "measurement_rows": [],
    }
    plot_data_path.write_text(json.dumps(plot_data, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    manifest = {
        "schema": "frontier.experimental-design.manifest/1",
        "status": result["status"],
        "protocol_sha256": result["protocol_sha256"],
        "code_commit": code_commit,
        "code_sha256": code_hashes,
        "files": {p.name: {"sha256": _sha256_file(p), "bytes": p.stat().st_size}
                  for p in (protocol_path, result_path, plot_data_path)},
        "measurement_rows": 0,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    return {"result": result, "plot_data": plot_data, "manifest": manifest,
            "paths": {"result": str(result_path), "plot_data": str(plot_data_path), "manifest": str(manifest_path)}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "run"))
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.mode == "freeze":
        print(json.dumps({"protocol_sha256": freeze_protocol(args.protocol), "path": str(args.protocol)}))
    else:
        done = run_demo(args.protocol, args.output)
        print(json.dumps({"protocol_sha256": done["result"]["protocol_sha256"],
                          "selected_design_id": done["result"]["selected_design_id"], "paths": done["paths"]}))


if __name__ == "__main__":
    main()
