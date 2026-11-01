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
          "y = w_saved(x)/L, deterministic; no noise sampled", "no empirical calibration was performed (none is applicable to a saved simulated field); the instrument model is NOT calibrated to any biological system; context = the saved draw's assumed latents",
          "closed-form analytic deflection of the same inputs; coarse/fine FEM difference stored with each case",
          "numerical discretisation only (stored grid difference); no biological uncertainty",
          "max |w_saved - w_analytic|/L <= 1e-4", "simulation_derived"),
    _inst("V2-saved-tip-and-slope", "virtual_simulation_readout", "tip/L and max slope of a saved case", "1; rad", "tip station and max over saved stations",
          "y = saved summary value, deterministic", "no empirical calibration performed; instrument model not calibrated to biology; saved draw context", "the assurance predicate's analytic residual field",
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


# Fields compiler02's genotype layer requires of an instrument contract (genotype.py INSTRUMENT_FIELDS, branch
# work/genotype-compiler @ 2dfc9b7). Slot interfaces below are claude-14 PROPOSALS for compiler02 to confirm.
COMPILER_FIELDS = ["instrument id and version", "input schema with units", "observation schema with units",
                   "noise or uncertainty model", "replicate unit", "cost and duration units"]
CONTRACT_EXTRAS = {
    "V1-saved-deflection-section": dict(slot=("I4", "virtual"), inp="saved case: L_m (m), EI_Nm2 (N m^2), q_N_m (N/m), load_shape", obs="w(x)/L at x/L sections (1)", rep="one saved simulated case (a draw x candidate x load shape); not a biological replicate", cost="CPU-seconds (reads saved fields; the whole run is ~95 s)", dur="seconds, deterministic"),
    "V2-saved-tip-and-slope": dict(slot=("I4", "virtual"), inp="saved case: L_m (m), EI_Nm2 (N m^2), q_N_m (N/m), load_shape", obs="tip/L (1); max slope (rad)", rep="one saved simulated case; not a biological replicate", cost="CPU-seconds", dur="seconds, deterministic"),
    "R1-ray-bending": dict(slot=("I3", "physical"), inp="excised ray; applied load F (N, known); clamped length L (m)", obs="ln(delta/F) offset removed (1)", rep="one ray from one fish (biological replicate = fish); repeats on one ray share clamp/setup error", cost="assumed_readout_cost_unit = 2 (not dollars)", dur="not defined (prospective)"),
    "R2-inflow-tip": dict(slot=("I4", "physical"), inp="ray in flow at target speed (m/s)", obs="tip deflection / L (1)", rep="one fish; repeated flows on one fish are technical repeats sharing the model discrepancy", cost="assumed_readout_cost_unit = 3 (not dollars)", dur="not defined (prospective)"),
    "R3-load": dict(slot=("I4", "physical"), inp="flow condition (m/s)", obs="distributed load (N/m)", rep="one flow condition", cost="assumed_readout_cost_unit = 2 (not dollars)", dur="not defined (prospective)"),
    "R4-length": dict(slot=("I3", "physical"), inp="ray image or specimen", obs="length (m)", rep="one ray", cost="assumed_readout_cost_unit = 0.5 (not dollars)", dur="not defined (prospective)"),
    "P1-reporter-expression": dict(slot=("I1", "physical"), inp="pinned construct sequence artifact in a stated cell state/stage (units undefined)", obs="reporter output (relative units; mapping to expression undefined)", rep="undefined until the design states it", cost="undefined", dur="undefined"),
    "P2-growth-to-EI": dict(slot=("I2", "physical"), inp="expression perturbation in a stated cell state (units undefined)", obs="segment growth (m) and density (kg/m^3) vs stage", rep="undefined until the design states it", cost="undefined", dur="undefined"),
}


def instrument_contracts(protocol_sha256: str) -> dict:
    out = []
    for inst in INSTRUMENTS:
        x = CONTRACT_EXTRAS[inst["id"]]
        out.append({
            "instrument id and version": f"{inst['id']}@1",
            "input schema with units": x["inp"], "observation schema with units": x["obs"],
            "noise or uncertainty model": f"{inst['forward_noise_model']}; uncertainty: {inst['uncertainty']}",
            "replicate unit": x["rep"], "cost and duration units": f"{x['cost']}; duration: {x['dur']}",
            "evidence_type": "computed" if inst["status"] == "simulation_derived" else "proposed",
            "status": inst["status"], "kind": inst["kind"], "calibration_context": inst["calibration_context"],
            "reference_control": inst["reference_control"], "acceptance": inst["acceptance"], "blocked_on": inst["blocked_on"],
            "proposed_compiler_slot": {"interface": x["slot"][0], "kind": x["slot"][1],
                                       "state": "claude-14 proposal; compiler02 confirms the interface mapping"}})
    return {"schema": "frontier.crossscale-doe.instrument-contracts/1", "protocol_sha256": protocol_sha256,
            "compiler_required_fields": COMPILER_FIELDS, "contracts": out,
            "rule": "contract_ref for a compiler slot = {path: artifacts/crossscale-doe/instrument-contracts.json, sha256: manifest files entry, pointer: /contracts/<index>}. A contract does not calibrate anything; no contract carries response data."}


def validate_contract(c: dict) -> list:
    """Return a list of problems; an empty list means the contract is internally consistent, nothing more."""
    probs = [f"missing or empty: {f}" for f in COMPILER_FIELDS if not str(c.get(f, "")).strip()]
    if c.get("status") == "simulation_derived":
        if c.get("kind") != "virtual_simulation_readout" or c.get("evidence_type") != "computed":
            probs.append("simulation_derived must be a computed virtual_simulation_readout")
        if "deterministic" not in c.get("noise or uncertainty model", ""):
            probs.append("a saved-field readout must declare its deterministic forward model")
        if "NOT calibrated" not in c.get("calibration_context", "") and "not calibrated" not in c.get("calibration_context", ""):
            probs.append("a virtual readout must say its instrument model is not calibrated to biology")
    else:
        if c.get("evidence_type") != "proposed":
            probs.append("a non-simulated instrument must be evidence_type proposed")
        if not c.get("blocked_on"):
            probs.append("a proposed instrument must name what blocks it")
    if c.get("kind") in ("sequence_expression_proposal", "cell_growth_proposal") and c.get("status") != "proposed_uncalibrated":
        probs.append("a sequence/growth instrument without a calibrated mapping must stay proposed_uncalibrated")
    return probs


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
                                 "note": "every combination of per-readout scales (3^8 = 6561). The FULL replicate-count grid (max_replicates_per_readout) is enumerated once, so plans that a price cut makes affordable are considered; a discounted-cost case (all prices x0.5) must show at least one newly feasible plan considered. Noise scale multiplies independent and shared variance. Baseline-not-beaten is counted only over scenarios in which the baseline is affordable; baseline-ineligible scenarios are reported separately.",
                                 "dependence": "Nominal model: repeats of R1, R3 and R4 are treated as independent (OPTIMISTIC for repeats on one ray or setup); only R2 carries a shared discrepancy. A dependence sensitivity gives every readout a shared term equal to its independent variance and reports the best plan again."},
            "decision_exercise": "Model-based exercise, not an observed error rate. True margin = m0 + theta.target where m0 is the FINALIST's actual log margin ln(0.3) - (ln q + 3 ln L - ln EI) at the sample mean of the recorded draws, and theta ~ N(0, prior). Each plan decides by the sign of the posterior-mean margin; no-measurement decides by sign(m0). Reports sign-misclassification probability; seed 20261101, 20000 draws. The earlier centered (m0 = 0) version is superseded.",
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


def measurement(protocol, draws, seed, finalist):
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
    # Sensitivity: the full replicate-count grid is enumerated ONCE (no nominal-budget filter), because a price
    # cut makes plans affordable that the nominal budget excluded. Variance reduction depends on the noise scale
    # only; cost scales only decide which plans are affordable.
    ids = [r["id"] for r in readouts]
    all_plans = _enumerate(readouts, float("inf"), meas["max_replicates_per_readout"])
    counts_arr = np.array(all_plans, float)
    nominal_cost = counts_arr @ np.array([r["cost"] for r in readouts])
    base_idx = all_plans.index(tuple(base_counts))
    scales = meas["sensitivity_grid"]
    budget = meas["budget"]
    first, comparable, base_ineligible, base_not_beaten, scenarios = {}, 0, 0, 0, 0
    newly_feasible_seen = 0
    for ns in itertools.product(scales["noise_scale_per_readout"], repeat=len(ids)):
        nsd = dict(zip(ids, ns))
        red = np.array([_evaluate(prior, target, readouts, c, noise_scale=nsd)[0]["expected_target_variance_reduction"]
                        for c in all_plans])
        for cs in itertools.product(scales["cost_scale_per_readout"], repeat=len(ids)):
            cost = counts_arr @ (np.array([r["cost"] for r in readouts]) * np.array(cs))
            ok = cost <= budget + 1e-9
            scenarios += 1
            if not ok.any():
                continue
            best = max(np.flatnonzero(ok), key=lambda i: (red[i], -cost[i]))
            lab = _label(readouts, all_plans[best])
            first[lab] = first.get(lab, 0) + 1
            newly_feasible_seen += int(np.any(ok & (nominal_cost > budget + 1e-9)))
            if ok[base_idx]:
                comparable += 1
                base_not_beaten += int(red[best] <= red[base_idx] + 1e-12)
            else:
                base_ineligible += 1
    # discounted-cost case: every price halved; plans costing up to 2x the budget at nominal prices are affordable
    half = {i: 0.5 for i in ids}
    cost_half = counts_arr @ (np.array([r["cost"] for r in readouts]) * 0.5)
    red_nom = np.array([_evaluate(prior, target, readouts, c)[0]["expected_target_variance_reduction"] for c in all_plans])
    ok_half = cost_half <= budget + 1e-9
    new_idx = [i for i in np.flatnonzero(ok_half) if nominal_cost[i] > budget + 1e-9]
    best_half = max(np.flatnonzero(ok_half), key=lambda i: (red_nom[i], -cost_half[i]))
    discount_case = {"cost_scale": half, "plans_in_grid": len(all_plans), "affordable_at_discount": int(ok_half.sum()),
                     "newly_feasible_plans_considered": len(new_idx),
                     "example_newly_feasible": [_label(readouts, all_plans[i]) for i in new_idx[:3]],
                     "best_plan_at_discount": _label(readouts, all_plans[best_half]),
                     "best_variance_reduction_at_discount": float(red_nom[best_half]),
                     "best_variance_reduction_nominal_budget": best_at_budget["variance_reduction"],
                     "best_at_discount_is_newly_feasible": bool(best_half in new_idx)}
    # Dependence sensitivity: R1, R3, R4 repeats are independent in the nominal model (optimistic for repeats on
    # one ray/setup). Here each also carries a shared term equal to its independent variance.
    dep = [{**r, "shared_discrepancy_variance": r["independent_noise_variance"] if r["shared_discrepancy_variance"] == 0 else r["shared_discrepancy_variance"]}
           for r in readouts]
    dep_red = np.array([_evaluate(prior, target, dep, c)[0]["expected_target_variance_reduction"] for c in all_plans])
    ok_nom = nominal_cost <= budget + 1e-9
    dbest = max(np.flatnonzero(ok_nom), key=lambda i: (dep_red[i], -nominal_cost[i]))
    dependence = {"assumption": "every readout shares a discrepancy equal to its independent variance across repeats",
                  "best_plan": _label(readouts, all_plans[dbest]), "best_variance_reduction": float(dep_red[dbest]),
                  "nominal_selected_plan_variance_reduction_under_dependence": float(dep_red[all_plans.index(tuple(best_at_budget["counts"]))]),
                  "baseline_variance_reduction_under_dependence": float(dep_red[base_idx])}
    # Decision exercise: the TRUE margin is m0 + theta.target, with m0 the finalist's actual log margin at the sample
    # mean of the recorded draws (not a centered perturbation).
    ln = np.log
    means = np.array([np.mean([ln(d["EI_Nm2"]) for d in draws]),
                      np.mean([ln(0.5 * d["rho_kg_m3"] * d["speed_m_s"] ** 2 * d["CL"] * d["tributary_width_m"]) for d in draws]),
                      np.mean([ln(d["length_multiplier"]) for d in draws])])
    m0 = float(ln(0.3) - (means[1] + 3 * (ln(finalist["ray_length_m"]) + means[2]) - (means[0] + ln(finalist["EI_multiplier"]))))
    sd_t = float(np.sqrt(target @ prior @ target))
    from math import erf, sqrt
    gaussian_p_inside = 0.5 * (1 + erf(m0 / (sd_t * sqrt(2))))
    rng = np.random.default_rng(seed)
    mis = {}
    n = 20000
    theta = rng.multivariate_normal(np.zeros(3), prior, size=n)
    true_margin = m0 + theta @ target
    for name, counts in (("selected", best_at_budget["counts"]), ("baseline", base_counts), ("no_measurement", None)):
        if counts is None:  # decide from the prior mean margin m0
            mis[name] = float(np.mean(np.sign(true_margin) != np.sign(m0)))
            continue
        H, R, _ = _plan(readouts, counts)
        y = theta @ H.T + rng.multivariate_normal(np.zeros(len(H)), R, size=n)
        K = prior @ H.T @ np.linalg.inv(H @ prior @ H.T + R)
        mis[name] = float(np.mean(np.sign(m0 + (y @ K.T) @ target) != np.sign(true_margin)))
    return {
        "prior_covariance": prior.tolist(), "prior_sd": np.sqrt(np.diag(prior)).tolist(), "target_vector": target.tolist(),
        "n_plans_enumerated": len(rows), "ranked_by_reduction_per_cost": rows[:8],
        "best_at_budget": best_at_budget, "best_per_cost": best_per_cost, "baseline_equal_budget": baseline,
        "ratio_selected_over_baseline_variance_reduction": best_at_budget["variance_reduction"] / baseline["variance_reduction"],
        "zero_sensitivity_control": {"variance_reduction": zm["expected_target_variance_reduction"], "ok": zm["expected_target_variance_reduction"] == 0.0},
        "sensitivity": {"scenarios": scenarios, "plans_in_full_grid": len(all_plans),
                        "plans_ranked_first_at_budget": dict(sorted(first.items(), key=lambda kv: -kv[1])),
                        "scenarios_with_newly_feasible_plan_affordable": newly_feasible_seen,
                        "baseline_comparable_scenarios": comparable, "baseline_ineligible_scenarios": base_ineligible,
                        "baseline_not_beaten_among_comparable": base_not_beaten,
                        "note": "comparable = baseline affordable under that scenario's prices; not-beaten = no affordable plan reduces margin variance more"},
        "discounted_cost_case": discount_case, "dependence_sensitivity": dependence,
        "decision_exercise": {"finalist_margin_offset_m0": m0, "gaussian_p_inside_regime": gaussian_p_inside,
                              "recorded_pass_fraction_finalist": finalist["fem"]["fraction"],
                              "sign_misclassification": mis,
                              "note": "model-based exercise under the assumed Gaussian latent law: true margin = m0 + theta.target; the no-measurement arm decides from sign(m0). Gaussian P(inside) differs from the recorded pass fraction because the recorded draws are uniform, not Gaussian. Not an observed fish error rate."},
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
            "control_off_grid_refused": off_grid_control(protocol, doc), "status": spec["status"], "response_rows_created": 0}


def off_grid_control(protocol, doc):
    """Execute the negative arm: a section absent from the saved grid must raise the specific refusal."""
    bad = json.loads(json.dumps(protocol))
    bad["virtual_validation"]["sections_x_over_L"] = [0.2512]
    try:
        virtual_validation(bad, doc)
    except ValueError as exc:
        return {"executed": True, "refused": "off the saved grid" in str(exc), "error_type": "ValueError", "message": str(exc)}
    return {"executed": True, "refused": False, "error_type": None, "message": "no error raised"}


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
    meas = measurement(protocol, draws, protocol["seed"], next(r for r in rows if r["id"] == finalist))
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
    contracts = instrument_contracts(result["protocol_sha256"])
    problems = {c["instrument id and version"]: validate_contract(c) for c in contracts["contracts"]}
    if any(problems.values()):
        raise RuntimeError(f"instrument contract problems: {problems}")
    (out / "instrument-contracts.json").write_text(_canon(contracts))
    _plot(rows, meas, out / "selection.png")
    (out / "instrument-flow.svg").write_text(_flow_svg())
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    names = ("protocol.json", "candidates.json", "result.json", "interface-map.json", "instrument-contracts.json", "selection.png", "instrument-flow.svg")
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
