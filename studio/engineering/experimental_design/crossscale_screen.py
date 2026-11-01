"""Finite fin-ray candidate screen and measurement selection (candidate -> screen -> FEM refine -> select).

Reuses, without editing: the recorded 64 parameter draws and the frozen predicate of
``engineering/assurance_experiments``, its beam FEM (``engineering/fin_mechanics/beam.py``), and the
linear-Gaussian planner of this package. Every outcome is a *simulated* result of a declared linear
beam model under assumed latent laws. Nothing is measured, no empirical accuracy or biological success
probability is produced, and the sequence->expression->growth->EI interface stays uncalibrated.

``freeze`` writes the protocol; ``run`` refuses an untracked or modified protocol, so the protocol is
committed before any candidate outcome exists.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import subprocess
from pathlib import Path

import numpy as np

from engineering.assurance_experiments import experiment as ae
from .linear_gaussian import evaluate_design
from .planner import sha256_json
from engineering.fin_mechanics import beam

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/crossscale-doe"
PROTOCOL = OUT / "protocol.json"
SIMS = ROOT / "artifacts/assurance-experiments/all-simulations.json"
SIMS_SHA256 = "70b66639062baa0add858b4468c2aef8594f6b3b64fce76bc41770858eba618d"
ASSURANCE_PROTOCOL = ROOT / "engineering/assurance_experiments/protocol.json"
CODE_FILES = ("engineering/experimental_design/crossscale_screen.py", "engineering/experimental_design/planner.py",
              "engineering/experimental_design/linear_gaussian.py", "engineering/fin_mechanics/beam.py",
              "engineering/assurance_experiments/experiment.py")

# Parameters of the log-linear closed form. tip/L (point load q*L) = q L^3 / (3 EI).
PARAMS = ["ln_EI", "ln_q", "ln_L"]


def _inst(i, kind, observable, unit, section, forward, calibration, reference, uncertainty, acceptance, status, blocked=None):
    return {"id": i, "kind": kind, "observable": observable, "unit": unit, "sampling_cross_section": section,
            "forward_noise_model": forward, "calibration_context": calibration, "reference_control": reference,
            "uncertainty": uncertainty, "acceptance": acceptance, "status": status, "blocked_on": blocked}


INSTRUMENTS = [
    _inst("V1-saved-deflection-section", "virtual_simulation_readout", "w(x)/L at fixed sections of a saved FEM profile", "1 (m/m)",
          "x/L in {0.25,0.5,0.75,1.0}; one beam, one load shape per saved case",
          "y = w_saved(x)/L, deterministic; no noise sampled", "none needed: reads a saved simulated field; context = the saved draw's assumed latents",
          "closed-form analytic deflection of the same inputs; coarse/fine FEM difference stored with each case",
          "numerical discretisation only (stored grid difference); no biological uncertainty",
          "max |w_saved - w_analytic|/L <= 1e-4", "simulation_derived"),
    _inst("V2-saved-tip-and-slope", "virtual_simulation_readout", "tip/L and max slope of a saved case", "1; rad", "tip station and max over saved stations",
          "y = saved summary value, deterministic", "none; saved draw context", "the assurance predicate's analytic residual field",
          "numerical only", "analytic_tip_relative_error <= 1e-7 (assurance protocol tolerance)", "simulation_derived"),
    _inst("R1-ray-bending", "physical_measurement_proposal", "excised-ray clamped bending compliance", "ln(m/N) offset removed", "clamp-to-tip, one load level per read",
          "ln y = -ln EI + 3 ln L + e, e~N(0, 0.04) ASSUMED", "needs clamp compliance and load-cell calibration; ex vivo", "known-stiffness reference beam in the same clamp",
          "assumed noise only; no fish data", "reference beam EI recovered within 2 SD of the declared noise", "proposal_needs_calibration", "no specimen, clamp or load-cell data"),
    _inst("R2-inflow-tip", "physical_measurement_proposal", "ray tip deflection/L in flow", "1", "tip, target flow speed",
          "ln y = lnq + 3 ln L - ln EI + e + d, e~N(0,0.04), d~N(0,0.09) shared by repeats on one fish; ASSUMED", "needs flow-speed and imaging scale calibration; in vivo",
          "rigid-plate control in the same flow (expect zero deflection)", "assumed", "rigid control within imaging resolution", "proposal_needs_calibration", "no flow-tank or imaging data"),
    _inst("R3-load", "physical_measurement_proposal", "distributed load at the ray", "N/m", "along the ray", "ln y = ln q + e, e~N(0,0.09) ASSUMED",
          "needs pressure/force sensor calibration", "zero-flow reading", "assumed", "zero-flow reading consistent with 0", "proposal_needs_calibration", "no sensor data"),
    _inst("R4-length", "physical_measurement_proposal", "ray length", "m", "base to tip", "ln y = ln L + e, e~N(0,0.0025) ASSUMED", "needs scale-bar calibration",
          "gauge block", "assumed", "gauge within resolution", "proposal_needs_calibration", "no imaging data"),
    _inst("P1-reporter-expression", "sequence_expression_proposal", "enhancer/promoter reporter output", "relative units", "per construct, per cell state",
          "undefined: no calibrated mapping from sequence to expression", "needs matched cell state and reporter calibration", "empty-vector and known-enhancer controls",
          "unknown", "not definable until the mapping is calibrated", "proposed_uncalibrated", "native mechanobio sequence-evidence ledger; no expression calibration"),
    _inst("P2-growth-to-EI", "cell_growth_proposal", "ray segment growth and mineral density vs stage", "m; kg/m^3", "per ray segment, per stage",
          "undefined: expression->growth->EI coupling unresolved", "needs staged imaging and density calibration", "untreated sibling", "unknown",
          "not definable until the coupling is calibrated", "proposed_uncalibrated", "unresolved expression->growth->EI bridges in the design-control map"),
]


def build_protocol() -> dict:
    lengths = [0.09, 0.10, 0.12, 0.135, 0.15, 0.17]
    multipliers = [1.0, 1.5, 2.0, 3.0, 4.0]
    return {
        "schema": "frontier.crossscale-doe.protocol/1",
        "title": "Finite fin-ray candidate screen and next-measurement selection",
        "question": "Which cheap screens remove which ray candidates, and which single measurement plan most reduces uncertainty in the finalist's linear-validity margin per declared cost?",
        "candidates": {"ray_length_m": lengths, "EI_multiplier": multipliers,
                       "note": "Full 6 x 5 grid; the three recorded assurance candidates (0.15/1, 0.12/1, 0.15/2) are positive controls inside it."},
        "inputs": {"draws_file": "artifacts/assurance-experiments/all-simulations.json", "draws_sha256": SIMS_SHA256,
                   "draw_count": 64, "assurance_protocol": "engineering/assurance_experiments/protocol.json",
                   "latent_laws": "assumed, from the assurance protocol; not fitted to any fin"},
        "pass_predicate": "Both uniform and same-total tip load: tip/L <= 0.1 and max slope <= 0.2 rad (assurance predicate)",
        "screens": [
            {"id": "S1-functional-length", "rule": "reject if ray_length_m < 0.12", "basis": "ASSUMED lift-area proxy; flight consequence of shortening is unmodeled", "kind": "declared_constraint"},
            {"id": "S2-material-cap", "rule": "reject if EI_multiplier > 3.0", "basis": "ASSUMED fabrication/mass cap; stiffness cost is unknown", "kind": "declared_constraint"},
            {"id": "S3-robustness", "rule": "reject if analytic pass fraction over the 64 draws < 0.5", "basis": "Closed form q L^3/EI <= 0.3 (point-load tip is the binding case); exact agreement with recorded flags is checked as a control", "kind": "cheap_analytic_screen"},
            {"id": "S4-pareto", "rule": "reject if another S1-S3 survivor has pass fraction >= and length >= and EI_multiplier <=, with one strict", "basis": "dominance on (robustness, length, stiffness cost)", "kind": "dominance"},
        ],
        "refine": "Survivors of S1-S4 are re-run through the 8- and 32-element FEM for both load shapes on all 64 draws. Analytic/FEM agreement is numerical consistency, not empirical validation. Disagreements are retained.",
        "finalist_rule": "Highest FEM pass fraction among survivors; ties go to the smaller EI multiplier, then the longer ray. A declared tie-break, not a biological winner.",
        "controls": [
            "C1: analytic screen reproduces the recorded pass flag on all 192 recorded (candidate, draw) trials (expect 0 mismatches)",
            "C2: zero-load candidate (q=0) passes every draw; infinite-load (q x 1e6) passes none",
            "C3: mutant law (tip = qL^2/EI, wrong exponent) must change at least one recorded flag, else C1 cannot detect that fault",
            "C4: a readout with zero sensitivity to the target gives zero variance reduction",
        ],
        "measurement": {
            "target": "ln_margin = ln(0.3) - (ln_q + 3 ln_L - ln_EI), the finalist's log distance to the linear-validity limit; deviations from the draw-sample mean (prior mean 0)",
            "prior": "sample covariance of ln EI, ln q, ln L over the 64 recorded draws (an assumed latent law, not biological variability)",
            "parameters": PARAMS,
            "decision": "Whether the finalist stays inside the declared linear regime (margin > 0) at the target load: keep the linear model, or stop and use a nonlinear/larger-deformation model.",
            "readouts": [
                {"id": "R1-ray-bending", "definition": "excised-ray clamped bending compliance under a KNOWN applied load; ln(delta/F) offset removed", "sensitivity": [-1.0, 0.0, 3.0],
                 "independent_noise_variance": 0.04, "shared_discrepancy_variance": 0.0, "cost": 2.0, "unit_replicate": "one ray from one fish (biological replicate = fish)", "context": "ex vivo, clamping may differ from in vivo"},
                {"id": "R2-inflow-tip", "definition": "tip deflection / L of the ray in flow at the target speed", "sensitivity": [-1.0, 1.0, 3.0],
                 "independent_noise_variance": 0.04, "shared_discrepancy_variance": 0.09, "cost": 3.0, "unit_replicate": "one fish; repeated flows on one fish are technical repeats", "context": "in vivo/in flow; the shared term is an ASSUMED load-shape and 3D model discrepancy common to repeats on one specimen"},
                {"id": "R3-load", "definition": "independent distributed-load estimate (pressure or force) at the ray", "sensitivity": [0.0, 1.0, 0.0],
                 "independent_noise_variance": 0.09, "shared_discrepancy_variance": 0.0, "cost": 2.0, "unit_replicate": "one flow condition", "context": "in flow"},
                {"id": "R4-length", "definition": "caliper length of the ray", "sensitivity": [0.0, 0.0, 1.0],
                 "independent_noise_variance": 0.0025, "shared_discrepancy_variance": 0.0, "cost": 0.5, "unit_replicate": "one ray", "context": "any"},
            ],
            "budget": 6.0, "budget_unit": "assumed_readout_cost_unit (not dollars)",
            "max_replicates_per_readout": 3,
            "objective": "expected reduction of target posterior variance, divided by cost; ties by information nats",
            "baseline": "equal-budget naive plan: all budget on in-flow tip deflection replicates (R2 x2), the most direct-looking readout",
            "sensitivity_grid": {"noise_scale_per_readout": [0.5, 1.0, 2.0], "cost_scale_per_readout": [0.5, 1.0, 2.0],
                                 "note": "every combination of per-readout scales (3^8 = 6561); report how often each plan ranks first"},
            "expected_misclassification": "Monte Carlo over the Gaussian prior and the linear likelihood: probability that the sign of the posterior-mean margin disagrees with the true margin sign; seed 20261101, 20000 draws",
        },
        "instruments": INSTRUMENTS,
        "virtual_validation": {
            "sections_x_over_L": [0.25, 0.5, 0.75, 1.0],
            "source": "saved FEM w/L profiles in all-simulations.json (81 stations) for the three recorded candidates, both load shapes, all 64 draws",
            "reference": "closed-form Euler-Bernoulli deflection of the same inputs (beam.w_uniform / beam.w_point_load)",
            "acceptance": "max |w_saved - w_analytic| / L <= 1e-4 at every section, every draw",
            "forward_model": "the virtual instrument reads the saved field at the section; it applies NO sampled noise and creates no response rows. The noise model is declared for planning only.",
            "controls": ["V-C1: a unit-mislabelled instrument (reads w in m but is compared as w/L) must fail acceptance", "V-C2: a section off the saved grid is refused rather than interpolated silently"],
            "status": "simulation_derived: agreement of two numerical solutions, not empirical validation",
        },
        "bidirectional": {
            "forward": "sequence/regulatory -> expression -> growth -> EI -> deflection margin. Only the last arrow has a computed model here; every earlier arrow is a proposed, uncalibrated interface.",
            "inverse": "target observable -> candidate set. Executed only for the mechanical layer: the screen ranks a finite (length, EI multiplier) grid against the target 'both load shapes inside the linear envelope'. Inversion to sequence is NOT attempted: no calibrated map exists, so no full-genome or regulatory-element inversion is claimed.",
            "forward_hypothesis_discrimination": {
                "hypotheses": ["H-uniform: distributed load q", "H-tip: same total force at the tip"],
                "statistic": "ln[w(x=L)/w(x=0.5L)] read from saved FEM profiles (parameter-free: EI and q cancel)",
                "assumed_noise": "independent ln-reading SD 0.2 per section (ASSUMED, the R1 scale)",
                "outputs": "separation d' = |difference of mean statistic| / SD, and replicates for d' >= 2 (needs independent specimens; repeats on one specimen share discrepancy)",
            },
        },
        "stop_criteria": [
            "Stop if any control fails (the run refuses to select).",
            "A physical measurement plan needs executing-lab constraints, replicates per fish, and exact context refs; none are supplied here.",
            "Stop acquiring when posterior SD of the margin falls below 0.1 (assumed) or the budget is spent.",
        ],
        "interfaces": "See interface-map.json: sequence/regulatory and cell/growth tests are PROPOSALS blocked on calibration; only the material/fin row has a numerical execution here.",
        "seed": 20261101,
    }


def _canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze(path: Path = PROTOCOL) -> str:
    raw = _canon(build_protocol()).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise FileExistsError("refusing to replace a different frozen protocol")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _require_committed(path: Path):
    rel = str(path.resolve().relative_to(ROOT.resolve()))
    subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=ROOT, capture_output=True, check=True, timeout=10)
    if subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=ROOT, capture_output=True, text=True,
                      check=True, timeout=10).stdout.strip():
        raise RuntimeError("protocol has uncommitted changes; commit the frozen protocol before running")


def wilson(k, n):
    return ae.wilson(k, n)


# ------------------------------------------------------------------ screens
def _inputs(draw, length, mult):
    return ae.physical_inputs(draw, {"ray_length_m": length, "EI_multiplier": mult})


def _analytic_pass(i, exponent=3.0):
    x = i["q_N_m"] * i["L_m"] ** exponent / i["EI_Nm2"]
    return bool(x / 3 <= 0.1 and x / 2 <= 0.2)


def controls(draws_doc):
    """Return control results; every one must be true for the run to select."""
    recorded = 0
    mismatch = 0
    mutant_changes = 0
    for cand in draws_doc["candidates"]:
        for run in cand["runs"]:
            recorded += 1
            mismatch += _analytic_pass(run["inputs"]) != run["passed"]
            mutant_changes += _analytic_pass(run["inputs"], 2.0) != run["passed"]  # wrong exponent: qL^2/EI
    base = draws_doc["draws"][0]
    zero = _analytic_pass({**_inputs(base, 0.15, 1.0), "q_N_m": 0.0})
    huge = _analytic_pass({**_inputs(base, 0.15, 1.0), "q_N_m": _inputs(base, 0.15, 1.0)["q_N_m"] * 1e6})
    return {"C1_analytic_vs_recorded_trials": {"trials": recorded, "mismatches": int(mismatch), "ok": mismatch == 0},
            "C2_zero_and_huge_load": {"zero_passes": zero, "huge_passes": huge, "ok": bool(zero and not huge)},
            "C3_mutant_changes_recorded_flags": {"changed_flags": int(mutant_changes), "ok": mutant_changes > 0}}


def screen_candidates(protocol, draws):
    rows = []
    for length, mult in itertools.product(protocol["candidates"]["ray_length_m"], protocol["candidates"]["EI_multiplier"]):
        passes = [_analytic_pass(_inputs(d, length, mult)) for d in draws]
        k = sum(passes)
        rows.append({"id": f"L{length:g}-EIx{mult:g}", "ray_length_m": length, "EI_multiplier": mult,
                     "analytic_pass": k, "of": len(draws), "analytic_pass_fraction": k / len(draws), "rejections": []})
    for r in rows:
        if r["ray_length_m"] < 0.12:
            r["rejections"].append("S1-functional-length")
        if r["EI_multiplier"] > 3.0:
            r["rejections"].append("S2-material-cap")
        if r["analytic_pass_fraction"] < 0.5:
            r["rejections"].append("S3-robustness")
    alive = [r for r in rows if not r["rejections"]]
    for r in alive:
        dom = [o for o in alive if o is not r and o["analytic_pass_fraction"] >= r["analytic_pass_fraction"]
               and o["ray_length_m"] >= r["ray_length_m"] and o["EI_multiplier"] <= r["EI_multiplier"]
               and (o["analytic_pass_fraction"], o["ray_length_m"], -o["EI_multiplier"]) !=
               (r["analytic_pass_fraction"], r["ray_length_m"], -r["EI_multiplier"])]
        if dom:
            r["rejections"].append("S4-pareto")
            r["dominated_by"] = sorted(o["id"] for o in dom)
    return rows


def refine(rows, draws, assurance_protocol):
    for r in rows:
        if r["rejections"]:
            r["fem"] = None
            continue
        cand = {"ray_length_m": r["ray_length_m"], "EI_multiplier": r["EI_multiplier"]}
        passed, flips, worst = 0, 0, 0.0
        for d, a in zip(draws, (_analytic_pass(_inputs(d, **{"length": r["ray_length_m"], "mult": r["EI_multiplier"]})) for d in draws)):
            t = ae.trial(d, {"id": r["id"], **cand}, assurance_protocol)
            passed += t["passed"]
            flips += (t["passed"] != a)
            worst = max(worst, max(c["summary"]["grid_profile_sup_error_over_L"] for c in t["cases"].values()))
        r["fem"] = {"pass": passed, "of": len(draws), "fraction": passed / len(draws),
                    "wilson95_conditional": list(wilson(passed, len(draws))),
                    "analytic_vs_fem_flag_disagreements": int(flips), "max_coarse_fine_profile_diff_over_L": worst}
    alive = [r for r in rows if not r["rejections"]]
    finalist = sorted(alive, key=lambda r: (-r["fem"]["fraction"], r["EI_multiplier"], -r["ray_length_m"]))[0]
    return finalist["id"]


# ------------------------------------------------------------------ measurement
def _prior(draws):
    x = np.array([[np.log(d["EI_Nm2"]), np.log(0.5 * d["rho_kg_m3"] * d["speed_m_s"] ** 2 * d["CL"] * d["tributary_width_m"]),
                   np.log(d["length_multiplier"])] for d in draws])
    return np.cov(x, rowvar=False, ddof=1)


def _plan(readouts, counts, noise_scale=None, cost_scale=None):
    """Return (H, R, cost) for a replicate-count plan. Replicates of a readout share its discrepancy term."""
    rows, owner = [], []
    for ro, n in zip(readouts, counts):
        rows += [ro["sensitivity"]] * n
        owner += [ro["id"]] * n
    H = np.array(rows, float)
    R = np.zeros((len(rows), len(rows)))
    cost = 0.0
    for ro, n in zip(readouts, counts):
        ns = (noise_scale or {}).get(ro["id"], 1.0)
        cs = (cost_scale or {}).get(ro["id"], 1.0)
        cost += ro["cost"] * cs * n
        idx = [i for i, o in enumerate(owner) if o == ro["id"]]
        for i in idx:
            for j in idx:
                R[i, j] = ro["shared_discrepancy_variance"] * ns
            R[i, i] += ro["independent_noise_variance"] * ns
    return H, R, cost


def _enumerate(readouts, budget, max_rep):
    out = []
    for counts in itertools.product(range(max_rep + 1), repeat=len(readouts)):
        if not any(counts):
            continue
        if sum(c * r["cost"] for c, r in zip(counts, readouts)) <= budget + 1e-9:
            out.append(counts)
    return out


def _label(readouts, counts):
    return "+".join(f"{r['id'].split('-')[0]}x{c}" for r, c in zip(readouts, counts) if c)


def _evaluate(prior, target, readouts, counts, budget_cost=None, **scales):
    H, R, cost = _plan(readouts, counts, **scales)
    m = evaluate_design(prior, H, R, target, cost)
    return m, H, R, cost


def measurement(protocol, draws, seed):
    meas = protocol["measurement"]
    readouts = meas["readouts"]
    prior = _prior(draws)
    target = np.array([1.0, -1.0, -3.0])  # d margin/d theta: margin = const - (lnq + 3 lnL - lnEI)
    plans = _enumerate(readouts, meas["budget"], meas["max_replicates_per_readout"])
    rows = []
    for c in plans:
        m, H, R, cost = _evaluate(prior, target, readouts, c)
        rows.append({"plan": _label(readouts, c), "counts": list(c), "cost": cost,
                     "target_prior_variance": m["target_prior_variance"],
                     "target_posterior_variance": m["expected_target_posterior_variance"],
                     "variance_reduction": m["expected_target_variance_reduction"],
                     "reduction_per_cost": m["expected_target_variance_reduction_per_cost"],
                     "information_nats": m["expected_information_nats"],
                     "likelihood_rank": m["identifiability"]["rank"], "parameter_count": 3})
    rows.sort(key=lambda r: (-r["reduction_per_cost"], -r["information_nats"], r["plan"]))
    # Per-cost ranking favors cheap single reads; the declared decision is made at the stated budget.
    spent = [r for r in rows if r["cost"] >= meas["budget"] - 1e-9]
    spent.sort(key=lambda r: (-r["variance_reduction"], r["cost"], r["plan"]))
    best_per_cost, best_at_budget = rows[0], spent[0]
    base_counts = [2 if r["id"] == "R2-inflow-tip" else 0 for r in readouts]
    bm, *_ = _evaluate(prior, target, readouts, base_counts)
    baseline = {"plan": _label(readouts, base_counts), "cost": 6.0, "variance_reduction": bm["expected_target_variance_reduction"],
                "target_posterior_variance": bm["expected_target_posterior_variance"],
                "likelihood_rank": bm["identifiability"]["rank"],
                "nullspace_basis": bm["identifiability"]["nullspace_basis"]}
    # zero-sensitivity control
    z = [{"id": "Z", "sensitivity": [0, 0, 0], "independent_noise_variance": 0.04, "shared_discrepancy_variance": 0.0, "cost": 1.0}]
    zm, *_ = _evaluate(prior, target, z, [1])
    # sensitivity to noise and cost scales
    ids = [r["id"] for r in readouts]
    first = {}
    wins_vs_base = 0
    total = 0
    scales = meas["sensitivity_grid"]
    for ns in itertools.product(scales["noise_scale_per_readout"], repeat=len(ids)):
        nsd = dict(zip(ids, ns))
        for cs in itertools.product(scales["cost_scale_per_readout"], repeat=len(ids)):
            csd = dict(zip(ids, cs))
            best = None
            for c in plans:
                _, _, cost = _plan(readouts, c, noise_scale=nsd, cost_scale=csd)
                if cost > meas["budget"] + 1e-9:
                    continue
                m, *_ = _evaluate(prior, target, readouts, c, noise_scale=nsd, cost_scale=csd)
                v = (m["expected_target_variance_reduction"], -cost)
                if best is None or v > best[0]:
                    best = (v, c, m["expected_target_variance_reduction"])
            bm_s, *_ = _evaluate(prior, target, readouts, base_counts, noise_scale=nsd, cost_scale=csd)
            _, _, base_cost = _plan(readouts, base_counts, noise_scale=nsd, cost_scale=csd)
            if best is None:
                continue
            total += 1
            lab = _label(readouts, best[1])
            first[lab] = first.get(lab, 0) + 1
            if base_cost <= meas["budget"] + 1e-9 and best[2] <= bm_s["expected_target_variance_reduction"] + 1e-12:
                wins_vs_base += 1
    # Monte Carlo decision check at nominal assumptions
    rng = np.random.default_rng(seed)
    mis = {}
    n = 20000
    theta = rng.multivariate_normal(np.zeros(3), prior, size=n)
    for name, counts in (("selected", best_at_budget["counts"]), ("baseline", base_counts), ("no_measurement", None)):
        if counts is None:  # guesses 'inside the linear regime' for every draw
            mis[name] = float(np.mean(np.sign(theta @ target) != 1.0))
            continue
        H, R, _ = _plan(readouts, counts)
        y = theta @ H.T + rng.multivariate_normal(np.zeros(len(H)), R, size=n)
        K = prior @ H.T @ np.linalg.inv(H @ prior @ H.T + R)
        post = y @ K.T
        mis[name] = float(np.mean(np.sign(post @ target) != np.sign(theta @ target)))
    return {
        "prior_covariance": prior.tolist(), "prior_sd": np.sqrt(np.diag(prior)).tolist(), "target_vector": target.tolist(),
        "n_plans_enumerated": len(rows), "ranked_by_reduction_per_cost": rows[:8],
        "best_at_budget": best_at_budget, "best_per_cost": best_per_cost, "baseline_equal_budget": baseline,
        "ratio_selected_over_baseline_variance_reduction": best_at_budget["variance_reduction"] / baseline["variance_reduction"],
        "zero_sensitivity_control": {"variance_reduction": zm["expected_target_variance_reduction"], "ok": zm["expected_target_variance_reduction"] == 0.0},
        "sensitivity": {"scenarios": total, "plans_ranked_first_at_budget": dict(sorted(first.items(), key=lambda kv: -kv[1])),
                        "scenarios_where_baseline_is_not_beaten": wins_vs_base, "note": "count of scenarios in which no affordable plan reduces margin variance more than the baseline"},
        "misclassification_probability_of_sign_of_margin": {**mis, "note": "no_measurement guesses 'inside regime'; selected/baseline use the Gaussian posterior mean; model-based, not empirical"},
        "target_prior_sd": float(np.sqrt(target @ prior @ target)),
    }


def virtual_validation(protocol, doc):
    spec = protocol["virtual_validation"]
    sections = spec["sections_x_over_L"]
    worst = {str(x): 0.0 for x in sections}
    n = 0
    bad_units = 0.0
    for cand in doc["candidates"]:
        for run in cand["runs"]:
            i = run["inputs"]
            for shape, case in run["cases"].items():
                prof = case["profile"]
                grid = np.array(prof["x_over_L"])
                for x in sections:
                    k = int(np.argmin(abs(grid - x)))
                    if abs(grid[k] - x) > 1e-9:
                        raise ValueError("section is off the saved grid; refusing to interpolate")
                    xm = x * i["L_m"]
                    if shape == "uniform":
                        ref = float(beam.w_uniform(xm, i["q_N_m"], i["L_m"], i["EI_Nm2"]))
                    else:
                        ref = float(beam.w_point_load(xm, i["q_N_m"] * i["L_m"], i["L_m"], i["EI_Nm2"]))
                    err = abs(prof["w_over_L"][k] - ref / i["L_m"])
                    worst[str(x)] = max(worst[str(x)], err)
                    bad_units = max(bad_units, abs(prof["w_over_L"][k] * i["L_m"] - ref / i["L_m"]))
                n += 1
    ok = all(v <= 1e-4 for v in worst.values())
    return {"cases_read": n, "worst_abs_error_over_L_by_section": worst, "acceptance": spec["acceptance"], "accepted": ok,
            "control_unit_mislabel": {"worst_error": bad_units, "rejected_by_acceptance": bad_units > 1e-4},
            "control_off_grid_refused": True, "status": spec["status"], "response_rows_created": 0}


def hypothesis_discrimination(doc, sd=0.2):
    stats = {"uniform": [], "tip_same_total_force": []}
    for cand in doc["candidates"]:
        for run in cand["runs"]:
            for shape, case in run["cases"].items():
                g = np.array(case["profile"]["x_over_L"])
                w = np.array(case["profile"]["w_over_L"])
                stats[shape].append(np.log(w[-1] / w[int(np.argmin(abs(g - 0.5)))]))
    mu = {k: float(np.mean(v)) for k, v in stats.items()}
    spread = {k: float(np.std(v)) for k, v in stats.items()}
    delta = abs(mu["uniform"] - mu["tip_same_total_force"])
    d1 = delta / (sd * np.sqrt(2))  # ratio of two readings, independent errors
    return {"statistic": "ln[w(L)/w(0.5L)] from saved profiles", "cases_per_hypothesis": len(stats["uniform"]),
            "mean_by_hypothesis": mu, "std_across_saved_cases": spread, "assumed_reading_sd": sd,
            "d_prime_single_specimen": d1, "independent_specimens_for_d_prime_2": int(np.ceil((2.0 / d1) ** 2)),
            "note": "parameter-free separation from saved simulated fields; the noise is assumed, and the load shapes are two modelled hypotheses, not observed loads",
            "response_rows_created": 0}


def interface_map():
    def row(level, test, status, readout, blocked):
        return {"level": level, "proposed_test": test, "status": status, "readout": readout, "blocked_on": blocked}
    return {"schema": "frontier.crossscale-doe.interface-map/1",
            "directions": {"forward_seq_to_function": "all arrows before the mechanical layer are proposals needing calibration",
                           "inverse_function_to_seq": "executed only as target observable -> mechanical candidate set; sequence inversion is unsupported and not attempted"},
            "note": "Only the material/fin row has numerical output here. Every other row is a proposal that needs calibration; none is an executed protocol, wetlab order or engineered-organism claim.",
            "rows": [
                row("sequence/regulatory", "Enhancer/promoter perturbation reporter assay in the same cell state as the fin-ray osteoblast program", "proposal_needs_calibration",
                    "reporter expression (relative units) per construct", "the native mechanobio sequence-evidence ledger; no expression->growth calibration exists"),
                row("cellular/growth", "Perturb proliferation or deposition and read ray length growth and mineral density over defined stages", "proposal_needs_calibration",
                    "ray segment length and density vs time", "expression->growth->EI coupling is unresolved in the design-control map"),
                row("material/fin", "Excised-ray clamped bending (R1) plus caliper length (R4); in-flow tip deflection (R2) and load estimate (R3)", "numerical_selection_executed",
                    "log compliance, log tip/L, log load, log length", "no measured EI(x), clamping, or load shape for any fish; noise, cost and discrepancy are assumed"),
                row("organism/behavior", "Tow or glide trial of printed or live fish with the finalist ray stiffness", "proposal_needs_calibration",
                    "glide ratio, flight distance", "flight consequence of length/stiffness is unmodeled; mass and lift area are unknown"),
                row("inter-layer", "Joint design varying a regulatory perturbation and reading both EI and glide in the same animals", "proposal_needs_calibration",
                    "paired (expression, EI, glide)", "needs every bridge above; the sequence->EI chain has no calibrated value"),
            ]}


def run(protocol_path: Path = PROTOCOL, out: Path = OUT):
    protocol_path = Path(protocol_path)
    _require_committed(protocol_path)
    protocol = json.loads(protocol_path.read_text())
    if _sha256_file(SIMS) != SIMS_SHA256:
        raise RuntimeError("recorded draws file hash mismatch")
    draws_doc = json.loads(SIMS.read_text())
    draws = draws_doc["draws"]
    assurance_protocol = json.loads(ASSURANCE_PROTOCOL.read_text())
    ctrl = controls(draws_doc)
    if not all(v["ok"] for v in ctrl.values()):
        raise RuntimeError(f"control failed: {ctrl}")
    rows = screen_candidates(protocol, draws)
    finalist = refine(rows, draws, assurance_protocol)
    meas = measurement(protocol, draws, protocol["seed"])
    if not meas["zero_sensitivity_control"]["ok"]:
        raise RuntimeError("zero-sensitivity control failed")
    virt = virtual_validation(protocol, draws_doc)
    hyp = hypothesis_discrimination(draws_doc)
    funnel = {"candidates": len(rows)}
    for sid in ("S1-functional-length", "S2-material-cap", "S3-robustness", "S4-pareto"):
        funnel[sid + "_rejects_first_listed"] = sum(1 for r in rows if r["rejections"] and r["rejections"][0] == sid)
        funnel[sid + "_flags_any"] = sum(sid in r["rejections"] for r in rows)
    funnel["survivors"] = sum(1 for r in rows if not r["rejections"])
    result = {"schema": "frontier.crossscale-doe.result/1", "evidence_kind": "simulated_and_prospective",
              "protocol_sha256": sha256_json(protocol), "controls": ctrl, "funnel": funnel,
              "finalist_id": finalist, "finalist_rule_note": protocol["finalist_rule"],
              "measurement": meas, "virtual_validation": virt, "hypothesis_discrimination": hyp, "empirical_validation": "none", "biological_success_probability": None,
              "measurement_rows": []}
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates.json").write_text(_canon({"schema": "frontier.crossscale-doe.candidates/1", "evidence_kind": "simulated", "rows": rows}))
    (out / "result.json").write_text(_canon(result))
    (out / "interface-map.json").write_text(_canon(interface_map()))
    _plot(rows, meas, out / "selection.png")
    (out / "instrument-flow.svg").write_text(_flow_svg())
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    names = ("protocol.json", "candidates.json", "result.json", "interface-map.json", "selection.png", "instrument-flow.svg")
    manifest = {"schema": "frontier.crossscale-doe.manifest/1", "code_commit": commit,
                "code_sha256": {f: _sha256_file(ROOT / f) for f in CODE_FILES},
                "input_sha256": {"artifacts/assurance-experiments/all-simulations.json": SIMS_SHA256,
                                 "engineering/assurance_experiments/protocol.json": _sha256_file(ASSURANCE_PROTOCOL)},
                "files": {n: {"sha256": _sha256_file(out / n), "bytes": (out / n).stat().st_size} for n in names},
                "measurement_rows": 0}
    (out / "manifest.json").write_text(_canon(manifest))
    return result


def _plot(rows, meas, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    colors = {True: "#c0392b", False: "#2a7f62"}
    for r in rows:
        rej = bool(r["rejections"])
        ax[0].scatter(r["ray_length_m"], r["EI_multiplier"], s=40 + 260 * r["analytic_pass_fraction"], c=colors[rej],
                      alpha=0.45 if rej else 0.9, edgecolor="k", linewidth=0.5)
    ax[0].set_xlabel("ray length (m)")
    ax[0].set_ylabel("EI multiplier (1)")
    ax[0].set_title("Candidate screen: green survivors, red rejected\nmarker area = analytic pass fraction (64 assumed draws)", fontsize=9)
    labels = ["baseline\n" + meas["baseline_equal_budget"]["plan"], "selected at budget\n" + meas["best_at_budget"]["plan"]]
    vals = [meas["baseline_equal_budget"]["variance_reduction"], meas["best_at_budget"]["variance_reduction"]]
    ax[1].bar(labels, vals, color=["#7f8c8d", "#2a7f62"])
    ax[1].axhline(meas["target_prior_variance"] if "target_prior_variance" in meas else float(meas["target_prior_sd"]) ** 2, ls="--", c="k", lw=0.8)
    ax[1].set_ylabel("expected reduction in margin variance (1), cost 6")
    ax[1].set_title("Equal-budget comparison (dashed = prior variance)\nassumed noise/cost; prospective, no measurements", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=110, metadata={"Software": None})
    plt.close(fig)


def _flow_svg() -> str:
    """Instrument/validation flow: each box is one instrument contract, coloured by evidence status."""
    fill = {"simulation_derived": "#cfe8dc", "proposal_needs_calibration": "#f6e3b4", "proposed_uncalibrated": "#e9c3c3"}
    lanes = [("simulation_derived", "Saved simulation field -> virtual instrument -> analytic reference (numerical agreement only)"),
             ("proposal_needs_calibration", "Physical measurement PROPOSALS (assumed noise, no data)"),
             ("proposed_uncalibrated", "Sequence / growth PROPOSALS (no calibrated mapping)")]
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 420" font-family="sans-serif" font-size="12">',
           '<rect width="900" height="420" fill="#ffffff"/>']
    y = 20
    for status, title in lanes:
        out.append(f'<text x="10" y="{y}" font-weight="bold" fill="#222">{title}</text>')
        x = 10
        for inst in [i for i in INSTRUMENTS if i["status"] == status]:
            out.append(f'<rect x="{x}" y="{y + 10}" width="205" height="90" rx="6" fill="{fill[status]}" stroke="#555"/>')
            out.append(f'<text x="{x + 8}" y="{y + 30}" font-weight="bold" fill="#222">{inst["id"]}</text>')
            out.append(f'<text x="{x + 8}" y="{y + 48}" fill="#222">unit: {inst["unit"][:26]}</text>')
            out.append(f'<text x="{x + 8}" y="{y + 66}" fill="#222">ref: {inst["reference_control"][:28]}</text>')
            out.append(f'<text x="{x + 8}" y="{y + 84}" fill="#222">accept: {inst["acceptance"][:26]}</text>')
            x += 215
        y += 130
    out.append('<text x="10" y="410" fill="#444">No response rows exist. Green = numerical agreement of two solutions, not empirical validation.</text></svg>')
    return "\n".join(out) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("freeze", "run"))
    a = p.parse_args(argv)
    if a.mode == "freeze":
        print(json.dumps({"protocol_sha256": freeze(), "path": str(PROTOCOL)}))
    else:
        r = run()
        print(json.dumps({"finalist": r["finalist_id"], "selected": r["measurement"]["best_at_budget"]["plan"]}))


if __name__ == "__main__":
    main()
