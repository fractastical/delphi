"""Receipt for one candidate: schema validation -> glide integration (dt and dt/2) -> uncertainty Monte Carlo -> verdict."""
from __future__ import annotations

import math

import numpy as np

from . import MODEL_VERSION, glide
from .schema import G, SCHEMA_RECEIPT, Refused, digest, parse_candidate

PRIORS = {"CL_max": (0.8, 1.6), "CD0": (0.03, 0.12), "e": (0.6, 0.95)}   # DECLARED design-assumption ranges, not measurements
MC_N, MC_SEED = 200, 20261031
DT, TOL_REL = 0.002, 1e-4
NOT_ESTABLISHED = ["biological feasibility of any fin or body", "fin-tissue coupling or any genetic mechanism", "calibrated lift/drag for any fish",
                   "Reynolds-number or scale validity of the drag polar", "unsteady, flapping, taxiing or take-off phases", "wind, waves, ground effect"]


def _vs(p):
    return float(glide.stall_speed(p["m"], p["S"], p["rho"], p["CL_max"]))


def run_one(p, dt=DT, V0=None, CL_max=None, CD0=None, e=None):
    CLm, c0, ee = (p["CL_max"] if CL_max is None else CL_max), (p["CD0"] if CD0 is None else CD0), (p["e"] if e is None else e)
    CL = glide.cl_command(CLm, c0, ee, p["AR"])
    Vs = glide.stall_speed(p["m"], p["S"], p["rho"], CLm)
    V0 = (1.5 * Vs) if V0 is None else V0
    return glide.integrate(p["m"], p["S"], p["AR"], p["rho"], CL, c0, ee, p["release_height_m"], V0, dt=dt), CL, Vs


def evaluate(candidate: dict, mc_n=MC_N, mc_seed=MC_SEED, with_series=True) -> dict:
    try:
        p = parse_candidate(candidate)
    except Refused as r:
        return {"schema": SCHEMA_RECEIPT, "model_version": MODEL_VERSION, "verdict": "refused", "code": r.code, "detail": r.detail, "evidence_kind": "none"}
    rec = {"schema": SCHEMA_RECEIPT, "model_version": MODEL_VERSION, "evidence_kind": "simulated", "not_established": NOT_ESTABLISHED,
           "inputs": {"candidate_sha256": p["candidate_sha256"], "assumption_sha256": p["assumption_sha256"], "assumption_sources": p["assumption_sources"],
                      "AR": p["AR"], "wing_loading_N_m2": p["m"] * G / p["S"]}}
    V_wit = p["V"]
    base, CL, Vs = run_one(p, V0=V_wit if p["release_speed_from_witness"] else None)
    half, _, _ = run_one(p, dt=DT / 2, V0=V_wit if p["release_speed_from_witness"] else None)
    rng, rng_h = float(base["range_m"][0]), float(half["range_m"][0])
    rel = abs(rng - rng_h) / max(abs(rng_h), 1e-12)
    eq = glide.equilibrium(p["m"], p["S"], p["AR"], p["rho"], float(CL), p["CD0"], p["e"])
    rec["results"] = {"stall_speed_ms": float(Vs), "CL_commanded": float(CL), "equilibrium_glide_ratio_L_over_D": float(eq["L_over_D"]),
                      "equilibrium_sink_rate_ms": float(eq["sink_ms"]), "equilibrium_speed_ms": float(eq["V_ms"]),
                      "glide_range_m": rng, "glide_time_s": float(base["time_s"][0]), "end_reason": int(base["end_reason"][0]),
                      "end_reason_key": {"0": "water contact", "1": "time limit", "2": "stalled", "3": "non-finite"},
                      "release_speed_ms": V_wit if p["release_speed_from_witness"] else float(1.5 * Vs)}
    rec["numerics"] = {"integrator": "RK4", "dt_s": DT, "dt_half_range_rel_diff": rel, "tolerance": TOL_REL, "converged": bool(rel <= TOL_REL)}
    # uncertainty: paired Monte Carlo over declared prior ranges
    rngs = np.random.default_rng(mc_seed)
    d = {k: rngs.uniform(lo, hi, mc_n) for k, (lo, hi) in PRIORS.items()}
    CLd = glide.cl_command(d["CL_max"], d["CD0"], d["e"], p["AR"])
    Vsd = glide.stall_speed(p["m"], p["S"], p["rho"], d["CL_max"])
    V0d = np.full(mc_n, V_wit) if p["release_speed_from_witness"] else 1.5 * Vsd
    mc = glide.integrate(p["m"], p["S"], p["AR"], p["rho"], CLd, d["CD0"], d["e"], p["release_height_m"], V0d, dt=DT)
    ok = mc["end_reason"] != 3
    q = np.quantile(mc["range_m"][ok], [0.1, 0.5, 0.9]) if ok.any() else [float("nan")] * 3
    rec["uncertainty"] = {"method": "Monte Carlo over DECLARED prior ranges (design assumptions, not measurements), paired seed", "priors": PRIORS, "n": mc_n,
                          "seed": mc_seed, "quantiles_glide_range_m": {"q10": float(q[0]), "q50": float(q[1]), "q90": float(q[2])},
                          "fraction_stalled": float(np.mean(mc["end_reason"] == 2)), "fraction_nonfinite": float(np.mean(~ok))}
    # verdict and counterexamples against the solver's level-flight proxy
    ce = None
    if p["release_speed_from_witness"] and V_wit < Vs:
        ce = {"code": "BELOW_STALL", "witness": {"V_ms": V_wit, "stall_speed_ms": float(Vs)}}
    elif int(base["end_reason"][0]) == 2:
        ce = {"code": "STALLS_BEFORE_WATER_CONTACT", "witness": {"range_m_at_stall": rng, "stall_speed_ms": float(Vs)}}
    elif p["required_glide_range_m"] is not None and rng < p["required_glide_range_m"]:
        ce = {"code": "RANGE_SHORTFALL", "witness": {"required_m": p["required_glide_range_m"], "simulated_range_m": rng,
                                                    "q10_range_m": float(q[0])}}
    rec["counterexample"] = ce
    rec["verdict"] = "counterexample" if ce else ("consistent" if rec["numerics"]["converged"] else "unconverged")
    rec["receipt_sha256"] = digest({k: v for k, v in rec.items() if k != "receipt_sha256"})
    return rec
