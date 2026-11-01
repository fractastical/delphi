"""Consume a pinned mathematical Claim before deriving actual beam inputs."""

from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re
import time

import numpy as np

from frontier.models import Record, ref
from engineering.fin_mechanics import beam
from engineering.fin_mechanics.load_bridge import bridge, exact
from engineering.fin_mechanics.sweep import canonical, critical_EI

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/claim-reuse"
CODE_FILES = [
    "engineering/claim_reuse/__init__.py",
    "engineering/claim_reuse/compute.py",
    "engineering/claim_reuse/workflow.py",
    "engineering/fin_mechanics/beam.py",
    "engineering/fin_mechanics/__init__.py",
    "engineering/fin_mechanics/load_bridge.py",
    "engineering/fin_mechanics/sweep.py",
    "frontier/models.py",
]


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def utc():
    return datetime.now(timezone.utc).isoformat()


def parsed_critical(record):
    matches = re.findall(
        r"EI_crit = ([0-9]+/[0-9]+) N m\^2", record["payload"]["statement"]
    )
    if len(matches) != 1 or Fraction(matches[0]) <= 0:
        raise ValueError("Claim does not expose one positive exact critical stiffness")
    return Fraction(matches[0])


def candidate_stiffness(critical, margin):
    return Fraction(critical) * Fraction(margin)


def bind_inputs(record, protocol, case):
    Record.model_validate(record)
    if ref(record) != protocol["claim_ref"]:
        raise ValueError("Exact Claim reference changed")
    if (
        record["payload"]["source"]["content_sha256"]
        != protocol["source_result_sha256"]
    ):
        raise ValueError("Claim source scope changed")
    if (
        sha(ART / "source-result.json") != protocol["source_result_sha256"]
        or sha(ART / "source-request.json") != protocol["source_request_sha256"]
    ):
        raise ValueError("Historical source inputs changed")
    request = json.loads((ART / "source-request.json").read_text())
    if (
        sha256(canonical(request)).hexdigest()
        != protocol["source_request_canonical_sha256"]
    ):
        raise ValueError("Original request context changed")
    origin = json.loads((ART / "source-result.json").read_text())
    if origin["inputs_sha256"] != protocol["source_request_canonical_sha256"]:
        raise ValueError("Source result does not pin this request")
    critical = parsed_critical(record)
    load = bridge(request)
    validity = request["validity"]
    calculated = critical_EI(
        exact(load["exact"]["q_line_N_per_m"], "q"),
        exact(load["exact"]["L_ray_m"], "L"),
        exact(validity["tip_over_L_max"], "tiplimit"),
        exact(validity["slope_max_rad"], "slope"),
    )
    if critical != Fraction(calculated["EI_crit_Nm2_exact"]):
        raise ValueError(
            "Consumed Claim threshold disagrees with its exact declared context"
        )
    return {
        "claim_ref": ref(record),
        "claim_critical_EI_exact": str(critical),
        "margin_exact": case["margin_exact"],
        "solver_EI_Nm2_exact": str(candidate_stiffness(critical, case["margin_exact"])),
        "q_line_N_per_m_exact": load["exact"]["q_line_N_per_m"],
        "L_m_exact": load["exact"]["L_ray_m"],
        "load_derivation": load,
        "tip_over_L_limit_exact": validity["tip_over_L_max"],
        "slope_limit_rad_exact": validity["slope_max_rad"],
        "scope": protocol["scope"],
    }


def compute(record, protocol, case, output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    params = bind_inputs(record, protocol, case)
    params["bound_before_solver_at_utc"] = utc()
    dump(out / "effective-inputs.json", params)
    started = time.perf_counter()
    started_utc = utc()
    EI, q, length = (
        float(Fraction(params[k]))
        for k in ("solver_EI_Nm2_exact", "q_line_N_per_m_exact", "L_m_exact")
    )
    x = np.linspace(0, length, protocol["numerics"]["profile_points"])
    analytic = beam.w_uniform(x, q, length, EI)
    profiles, grids = {}, []
    for n in protocol["numerics"]["elements"]:
        solution, validity = beam.solve_checked(
            length,
            EI,
            q,
            n,
            tip_over_L_max=float(Fraction(params["tip_over_L_limit_exact"])),
            slope_max_rad=float(Fraction(params["slope_limit_rad_exact"])),
        )
        profile, slope = solution.evaluate(x)
        profiles[n] = profile
        grids.append(
            {
                "elements": n,
                "tip_m": solution.tip,
                "max_slope_rad": solution.max_abs_slope,
                "analytic_tip_relative_error": abs(solution.tip - analytic[-1])
                / abs(analytic[-1]),
                "profile_relative_Linf_error": float(
                    abs(profile - analytic).max() / abs(analytic[-1])
                ),
            }
        )
    control = beam.control_residuals()
    mutant = beam.control_residuals(
        uniform_fn=lambda a, L, stiffness: a * L**3 / (8 * stiffness)
    )
    original_error = max(
        max(r["tip_load_rel_residual"], r["uniform_rel_residual"])
        for r in control.values()
    )
    mutant_error = max(r["uniform_rel_residual"] for r in mutant.values())
    zero = beam.solve_cantilever(length, EI, 0.0, 16)
    controls = {
        "quadrature_baseline_max_relative_error": original_error,
        "wrong_uniform_law_mutant_max_relative_error": mutant_error,
        "wrong_law_rejected": mutant_error
        > protocol["numerics"]["analytic_vs_independent_quadrature_relative_max"],
        "zero_load_max_abs_m": float(abs(zero.w).max()),
        "claim_binding_causal_check": candidate_stiffness(
            2 * parsed_critical(record), case["margin_exact"]
        )
        != Fraction(params["solver_EI_Nm2_exact"]),
    }
    numerical_pass = (
        original_error
        <= protocol["numerics"]["analytic_vs_independent_quadrature_relative_max"]
        and controls["wrong_law_rejected"]
        and controls["zero_load_max_abs_m"] == 0
        and controls["claim_binding_causal_check"]
        and max(v["analytic_tip_relative_error"] for v in grids)
        <= protocol["numerics"]["FEM_vs_analytic_tip_relative_max"]
        and grids[-1]["profile_relative_Linf_error"]
        <= protocol["numerics"]["finest_profile_relative_Linf_max"]
    )
    columns = np.column_stack(
        [x, *[profiles[n] for n in protocol["numerics"]["elements"]], slope, analytic]
    )
    np.savetxt(
        out / "profile.csv",
        columns,
        delimiter=",",
        header="x_m,w16_m,w32_m,w64_m,slope64_rad,analytic_w_m",
        comments="",
    )
    result = {
        "schema": "frontier.claim-reuse.result/1",
        "case": case["id"],
        "evidence_kind": "simulated",
        "started_at_utc": started_utc,
        "finished_at_utc": utc(),
        "wall_seconds": time.perf_counter() - started,
        "effective_inputs_sha256": sha(out / "effective-inputs.json"),
        "claim_ref": params["claim_ref"],
        "protocol_sha256": sha(ART / "protocol.json"),
        "grids": grids,
        "controls": controls,
        "numerical_checks_passed": bool(numerical_pass),
        "validity": validity,
        "declared_domain_predicate_matches": bool(validity["valid"])
        == case["expected_model_domain_valid"],
        "model_domain_valid": bool(validity["valid"]),
        "expected_model_domain_valid": case["expected_model_domain_valid"],
        "time_step": "not applicable: static beam boundary-value problem",
        "source_code_sha256": {p: sha(ROOT / p) for p in CODE_FILES},
        "scope": protocol["scope"],
        "limitations": record["payload"]["limitations"],
        "empirical_validation": "unknown",
        "biological_success_probability": None,
        "files": {
            "effective-inputs.json": sha(out / "effective-inputs.json"),
            "profile.csv": sha(out / "profile.csv"),
        },
    }
    dump(out / "result.json", result)
    return result
