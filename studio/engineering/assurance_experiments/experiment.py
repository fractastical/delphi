"""Paired uncertainty assay using existing fin FEM; no new beam solver."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
from pathlib import Path

import numpy as np
import scipy

from engineering.fin_mechanics import beam
from engineering.fin_mechanics.sweep import convergence_study

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = "engineering/assurance_experiments/protocol.json"
REGIONS = ["pectoral-left", "pectoral-right"]
SCOPE = "fraction over declared simulated scenarios; not probability biological success"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def output_reference(path):
    return str(Path(path).resolve().relative_to(ROOT))


def protocol_receipt(path):
    path = Path(path).resolve()
    if path != ROOT / PROTOCOL_PATH:
        raise ValueError("this bounded assay executes only its committed protocol")
    commit = git("log", "-1", "--format=%H", "--", PROTOCOL_PATH)
    original = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:{PROTOCOL_PATH}"])
    if original != path.read_bytes():
        raise ValueError("protocol differs from frozen commit")
    subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", commit, "HEAD"], check=True)
    p = json.loads(original)
    if p["schema"] != "frontier.fin-assurance.protocol/1" or not 2 <= p["parameter_draws"] <= 128:
        raise ValueError("invalid or unbounded protocol")
    return p, {"path": PROTOCOL_PATH, "sha256": sha(path), "protocol_commit": commit}


def sample_parameters(protocol):
    """Named transforms are the frozen protocol, not an executable string parser."""
    rng = np.random.default_rng(protocol["seed"])
    latents = rng.random((protocol["parameter_draws"], 5))
    output = []
    for index, (weather, geometry, material, aero, context) in enumerate(latents):
        output.append({"id": f"draw-{index:03d}", "rho_kg_m3": float(1.15 + 0.15 * weather),
                       "speed_m_s": float(6 - 2 * weather), "length_multiplier": float(0.85 + 0.3 * geometry),
                       "tributary_width_m": float(0.008 + 0.004 * geometry),
                       "EI_Nm2": float(0.0003 * 10**material), "CL": float(0.7 + 0.4 * aero),
                       "context_E_Pa": float(1e8 * 10**context),
                       "latent_values": {k: float(v) for k, v in zip(protocol["latents"], latents[index], strict=True)}})
    return output


def physical_inputs(draw, candidate):
    length = candidate["ray_length_m"] * draw["length_multiplier"]
    q = 0.5 * draw["rho_kg_m3"] * draw["speed_m_s"]**2 * draw["CL"] * draw["tributary_width_m"]
    return {"L_m": length, "EI_Nm2": draw["EI_Nm2"] * candidate["EI_multiplier"], "q_N_m": q}


def predicate(summary, protocol):
    return (summary["tip_over_L"] <= protocol["predicate"]["tip_over_length_limit"] and
            summary["max_slope_rad"] <= protocol["predicate"]["slope_limit_rad"])


def simulate_case(inputs, load_shape, protocol):
    length, ei, q = inputs["L_m"], inputs["EI_Nm2"], inputs["q_N_m"]
    xs = np.linspace(0, length, protocol["numerics"]["profile_positions"])
    if load_shape == "uniform":
        line, point = q, 0.0
        analytic = beam.w_uniform(xs, q, length, ei)
        exact_tip = beam.tip_deflection_uniform(q, length, ei)
    elif load_shape == "tip_same_total_force":
        line, point = 0.0, q * length
        analytic = beam.w_point_load(xs, point, length, ei)
        exact_tip = beam.tip_deflection_point_load(point, length, ei)
    else:
        raise ValueError("unknown load shape")
    solutions = [beam.solve_cantilever(length, ei, line, n, tip_force=point)
                 for n in (protocol["numerics"]["coarse_elements"], protocol["numerics"]["fine_elements"])]
    coarse, _ = solutions[0].evaluate(xs)
    fine, slope = solutions[1].evaluate(xs)
    summary = {"tip_over_L": float(abs(solutions[1].tip) / length),
               "max_slope_rad": float(np.max(np.abs(slope))),
               "analytic_tip_relative_error": float(abs(solutions[1].tip - exact_tip) / abs(exact_tip)) if exact_tip else 0.0,
               "grid_profile_sup_error_over_L": float(np.max(np.abs(fine - coarse)) / length),
               "analytic_profile_sup_error_over_L": float(np.max(np.abs(fine - analytic)) / length)}
    return {"summary": summary, "within_linear_envelope": predicate(summary, protocol),
            "profile": {"x_over_L": (xs / length).tolist(), "w_over_L": (fine / length).tolist(),
                        "coarse_fine_abs_difference_over_L": (np.abs(fine - coarse) / length).tolist()},
            "load_shape": load_shape,
            "interpretation": "linear-model extrapolation, outside declared validity" if not predicate(summary, protocol) else "inside declared linear envelope; biological accuracy unknown"}


def trial(draw, candidate, protocol):
    inputs = physical_inputs(draw, candidate)
    cases = {shape: simulate_case(inputs, shape, protocol) for shape in ("uniform", "tip_same_total_force")}
    passed = all(case["within_linear_envelope"] for case in cases.values())
    return {"id": draw["id"], "candidate_id": candidate["id"], "inputs": inputs, "cases": cases,
            "passed": passed, "model_shape_discrepancy_tip_over_L": abs(cases["uniform"]["summary"]["tip_over_L"] - cases["tip_same_total_force"]["summary"]["tip_over_L"])}


def wilson(numerator, denominator):
    if denominator < 1 or not 0 <= numerator <= denominator:
        raise ValueError("nonempty bounded ensemble required")
    z = 1.959963984540054
    p = numerator / denominator
    div = 1 + z*z / denominator
    center = (p + z*z / (2 * denominator)) / div
    width = z * math.sqrt(p * (1-p) / denominator + z*z / (4 * denominator**2)) / div
    return [max(0.0, center-width), min(1.0, center+width)]


def controls(protocol):
    numerical = convergence_study(0.12, 0.15, 0.001, ns=protocol["numerics"]["control_grids"])
    residuals = beam.control_residuals()
    zero = simulate_case({"L_m": .15, "EI_Nm2": .001, "q_N_m": 0}, "uniform", protocol)
    sample = sample_parameters(protocol)[0]
    candidate = protocol["candidates"][0]
    epsilon = protocol["numerics"]["sensitivity_fraction"]
    elasticities = {}
    for name, expected in [("rho_kg_m3", 1), ("speed_m_s", 2), ("tributary_width_m", 1),
                           ("length_multiplier", 3), ("EI_Nm2", -1), ("CL", 1)]:
        values = []
        for sign in (-1, 1):
            changed = dict(sample)
            changed[name] *= 1 + sign * epsilon
            inp = physical_inputs(changed, candidate)
            values.append(simulate_case(inp, "uniform", protocol)["summary"]["tip_over_L"])
        measured = math.log(values[1]/values[0]) / math.log((1+epsilon)/(1-epsilon))
        elasticities[name] = {"elasticity": measured, "expected_from_dimensions": expected,
                              "absolute_residual": abs(measured-expected),
                              "scope": "paired local perturbation, holding other inputs fixed; not biological causality"}
    # Actual alternative simulations: change load scaling to V^1 while keeping
    # the same baseline q. The predeclared V^2 elasticity check must detect it.
    baseline = physical_inputs(sample, candidate)
    mutant_values = [simulate_case({**baseline, "q_N_m": baseline["q_N_m"] * (1+sign*epsilon)}, "uniform", protocol)["summary"]["tip_over_L"]
                     for sign in (-1, 1)]
    mutant_elasticity = math.log(mutant_values[1]/mutant_values[0]) / math.log((1+epsilon)/(1-epsilon))
    max_residual = max(v for case in residuals.values() for key, v in case.items() if key.endswith("residual"))
    passed = (max_residual < protocol["numerics"]["analytic_relative_tolerance"] and
              max(v["absolute_residual"] for v in elasticities.values()) < protocol["numerics"]["sensitivity_elasticity_tolerance"] and
              zero["summary"]["tip_over_L"] == 0 and abs(mutant_elasticity-2) > 0.5)
    return {"passed": passed, "evidence_kind": "computational_check", "analytic_controls": residuals,
            "grid_convergence": numerical, "paired_sensitivity": elasticities,
            "zero_load_tip_over_L": zero["summary"]["tip_over_L"],
            "speed_law_mutant": {"change": "q proportional to V instead of V squared", "measured_elasticity": mutant_elasticity,
                                  "expected_baseline_elasticity": 2, "detected": abs(mutant_elasticity-2) > .5},
            "empirical_accuracy": "unknown; no held-out measured specimen/model pair"}


def run_protocol(protocol_path, output_directory):
    protocol, frozen = protocol_receipt(protocol_path)
    output = Path(output_directory).resolve()
    output_reference(output)  # Published references must remain inside this checkout.
    output.mkdir(parents=True, exist_ok=True)
    if git("status", "--porcelain", "--", "engineering/assurance_experiments", "engineering/fin_mechanics"):
        raise ValueError("commit model/assay code before producing published result artifacts")
    numerical_controls = controls(protocol)
    if not numerical_controls["passed"]:
        raise ValueError("predeclared numerical controls failed")
    write_json(output / "controls.json", numerical_controls)
    draws = sample_parameters(protocol)
    results = [{"candidate": candidate, "runs": [trial(draw, candidate, protocol) for draw in draws]}
               for candidate in protocol["candidates"]]
    context_settings = protocol["context_only"]
    context = [simulate_case({"L_m": context_settings["source_values"]["typical_ray_length_m"],
                             "EI_Nm2": draw["context_E_Pa"] * context_settings["source_values"]["I_average_m4"],
                             "q_N_m": context_settings["declared_test_load_N_m"]}, "uniform", protocol)
               for draw in draws]
    all_results = {"schema": "frontier.fin-assurance.simulations/1", "evidence_kind": "simulated",
                   "protocol": frozen, "run_code_revision": git("rev-parse", "HEAD"), "draws": draws,
                   "candidates": results, "source_context_cases": context,
                   "context_scope": protocol["context_only"], "biological_success_probability": None}
    write_json(output / "all-simulations.json", all_results)
    result_path = output_reference(output / "all-simulations.json")
    result_sha = sha(output / "all-simulations.json")
    ensembles = []
    for ci, candidate_result in enumerate(results):
        runs = []
        for index, record in enumerate(candidate_result["runs"]):
            runs.append({"id": record["id"], "input_sha256": hashlib.sha256(canonical({"draw": draws[index], "candidate": candidate_result["candidate"]})).hexdigest(),
                         "protocol_sha256": frozen["sha256"], "result_artifact": {"path": result_path, "sha256": result_sha,
                         "selector": f"$.candidates[{ci}].runs[{index}]"}, "passed": record["passed"],
                         "summary": {shape: case["summary"] for shape, case in record["cases"].items()},
                         "region_ids": REGIONS, "shared_input_groups": [f"{group}:{record['id']}" for group in
                         ("weather", "geometry", "design_material", "aerodynamics")], "model_group": "single-beam-linear-static"})
        numerator = sum(r["passed"] for r in runs)
        entry = {"schema": "frontier.assurance.ensemble/1", "candidate": candidate_result["candidate"],
                 "protocol": {"path": PROTOCOL_PATH, "sha256": frozen["sha256"]}, "protocol_commit": frozen["protocol_commit"],
                 "run_code_revision": all_results["run_code_revision"], "predicate": protocol["predicate"], "runs": runs,
                 "numerator": numerator, "denominator": len(runs), "fraction": numerator/len(runs),
                 "conditional_wilson95_interval": wilson(numerator, len(runs)), "scope": SCOPE,
                 "interval_scope": protocol["analysis"]["interval"], "biological_success_probability": None,
                 "uniform_only_numerator": sum(r["cases"]["uniform"]["within_linear_envelope"] for r in candidate_result["runs"])}
        write_json(output / f"ensemble-{candidate_result['candidate']['id']}.json", entry)
        ensembles.append(entry)
    write_json(output / "summary.json", {"schema": "frontier.fin-assurance.summary/1", "protocol": frozen,
               "candidates": [{k: e[k] for k in ("candidate", "numerator", "denominator", "fraction", "conditional_wilson95_interval", "uniform_only_numerator")} for e in ensembles],
               "all_candidates_retained": True, "empirical_accuracy": "unknown", "biological_success_probability": None,
               "next_measurements": ["Measure EI(x) under the target clamping/actuation condition.", "Measure spatial pressure/load shape; uniform-versus-tip discrepancy is not a calibrated error bound.", "Measure mass/lifting-area costs before choosing stiffer or shorter candidates."]})
    env = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "platform": platform.platform()}
    code_paths = [*Path(__file__).parent.glob("*.py"), ROOT / "engineering/fin_mechanics/beam.py", ROOT / "engineering/fin_mechanics/sweep.py"]
    write_json(output / "simulation-manifest.json", {"schema": "frontier.fin-assurance.simulation-manifest/1",
               "protocol": frozen, "code_revision": all_results["run_code_revision"], "code_files": {str(p.relative_to(ROOT)): sha(p) for p in sorted(code_paths)},
               "environment": env, "environment_sha256": hashlib.sha256(canonical(env)).hexdigest(),
               "outputs": {p.name: {"sha256": sha(p), "byte_size": p.stat().st_size} for p in sorted(output.glob("*.json")) if p.name != "simulation-manifest.json"}})
    return {"candidates": len(ensembles), "parameter_draws_per_candidate": len(draws), "protocol": frozen}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--protocol", default=PROTOCOL_PATH)
    parser.add_argument("--output", default="artifacts/assurance-experiments")
    args = parser.parse_args()
    print(json.dumps(run_protocol(args.protocol, args.output)))
