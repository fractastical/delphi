"""Gong et al. (2018), PNAS 115:E2686, Model Description, Eqs. 1–6.

Discrete clutches and exact linear mechanical steps, with first-order stochastic
splitting. This is a scoped implementation, not the authors' original code or a
reproduction of their figures. Internal units: pN, nm, s. Source/assumption
distinctions and missing biological bridges are part of every public result.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import numpy as np
import scipy
from scipy.linalg import expm

SCHEMA = "frontier.mechanobio.request/1"
SOURCE = "https://www.pnas.org/doi/10.1073/pnas.1716620115"
LIMITS = {
    "long_term_stiffness_pN_nm": (0.01, 10),
    "additional_stiffness_pN_nm": (0, 10),
    "viscosity_pN_s_nm": (0.01, 100),
    "motors": (1, 100), "clutches": (1, 100),
    "on_rate_s": (0, 10), "off_rate_s": (0, 10),
    "rupture_force_pN": (0.5, 10), "motor_stall_pN": (1, 10),
    "unloaded_speed_nm_s": (0, 200), "clutch_stiffness_pN_nm": (0.1, 10),
}
NOT_ESTABLISHED = [
    "No calibration to any fish cell, fin, tissue, developmental pathway or organism.",
    "No conversion of contact stiffness (pN/nm) to ECM modulus (kPa) without geometry.",
    "No reproduction of the paper's figures, experimental data or full reinforcement model.",
    "Spreading proxy is v_unloaded - v_retrograde, assuming polymerization equals unloaded flow; not cell area or migration.",
    "No membrane resistance, ligand recruitment, catch bonds, tissue remodeling or whole-cell shape.",
]


@dataclass(frozen=True)
class Parameters:
    long_term_stiffness_pN_nm: float = 0.1
    additional_stiffness_pN_nm: float = 1.0
    viscosity_pN_s_nm: float = 1.0
    motors: int = 20
    clutches: int = 40
    on_rate_s: float = 1.0
    off_rate_s: float = 0.1
    rupture_force_pN: float = 2.0
    motor_stall_pN: float = 2.0
    unloaded_speed_nm_s: float = 100.0
    clutch_stiffness_pN_nm: float = 0.8

    def __post_init__(self):
        for f in fields(self):
            value = getattr(self, f.name)
            lo, hi = LIMITS[f.name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError(f"{f.name} must be finite in [{lo}, {hi}]")
            if f.name in ("motors", "clutches") and not isinstance(value, int):
                raise ValueError(f"{f.name} must be an integer")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def code_hashes():
    return {str(p.relative_to(Path(__file__).parents[2])): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py"))}


def environment():
    return {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
            "platform": platform.platform(), "machine": platform.machine(),
            "mechanics": "scipy.linalg.expm; exact fixed-topology linear step",
            "kinetics": "Bernoulli tau-leaping, exact frozen-rate transition probability, first-order split"}


def _propagators(p, dt):
    """State [actin position a, Maxwell internal displacement z, b, 1].

    Bound clutch position x_i=a-reference_i. b=-kc sum(reference_i).
    Equilibrium xs=(Nc_bound*kc*a+b+ka*z)/(Nc_bound*kc+kl+ka).
    Maxwell z'=ka(xs-z)/eta. F=kl*xs+ka*(xs-z).
    a'=vu*(1-F/(Nm*Fm)). This is exactly paper Eqs.2–4
    while topology stays fixed, including its elastic ka=0 limit.
    """
    kl, ka, eta = p.long_term_stiffness_pN_nm, p.additional_stiffness_pN_nm, p.viscosity_pN_s_nm
    stall = p.motors * p.motor_stall_pN
    cache = []
    for n in range(p.clutches + 1):
        k = n * p.clutch_stiffness_pN_nm
        d = k + kl + ka
        xs = np.array([k, ka, 1, 0]) / d
        force = (kl + ka) * xs - np.array([0, ka, 0, 0])
        mat = np.zeros((4, 4))
        mat[0] = -p.unloaded_speed_nm_s / stall * force
        mat[0, 3] += p.unloaded_speed_nm_s
        mat[1] = ka / eta * (xs - np.array([0, 1, 0, 0]))
        cache.append(expm(dt * mat))
    return cache


def simulate(p: Parameters, *, duration_s=20.0, dt_s=0.01, seed=7,
             frame_count=201, initial_bound=False, force_feedback=True):
    """Return actual trajectory states. Extra flags are controls, not public API inputs."""
    steps = round(duration_s / dt_s)
    dt = duration_s / steps
    if steps < 1 or steps > 60000:
        raise ValueError("simulation requires 1..60000 timesteps")
    propagators = _propagators(p, dt)
    rng = np.random.default_rng(seed)
    bound = np.full(p.clutches, initial_bound, dtype=bool)
    refs = np.zeros(p.clutches)
    a = z = 0.0
    samples = set(np.rint(np.linspace(0, steps, min(frame_count, steps + 1))).astype(int))
    frames, sum_force, sum_flow, sum_bound = [], 0.0, 0.0, 0.0
    off_count = on_count = 0
    max_balance = 0.0
    max_probability = 0.0
    kc, kl, ka = p.clutch_stiffness_pN_nm, p.long_term_stiffness_pN_nm, p.additional_stiffness_pN_nm
    stall = p.motors * p.motor_stall_pN

    def state():
        xs = (kc * np.sum(a - refs[bound]) + ka * z) / (int(bound.sum()) * kc + kl + ka)
        forces = np.where(bound, kc * (a - refs - xs), 0.0)
        force = float(forces.sum())
        return float(xs), forces, force, p.unloaded_speed_nm_s * (1 - force / stall)

    for step in range(steps + 1):
        xs, forces, force, flow = state()
        max_balance = max(max_balance, abs(force - (kl * xs + ka * (xs - z))))
        if step in samples:
            frames.append({"t_s": float(step * dt), "traction_pN": force,
                           "substrate_nm": xs, "actin_nm": float(a),
                           "maxwell_internal_nm": float(z), "bound_clutches": int(bound.sum()),
                           "retrograde_nm_s": flow,
                           "spreading_proxy_nm_s": p.unloaded_speed_nm_s - flow,
                           "clutches": [{"bound": bool(b), "extension_nm": float(f / kc), "force_pN": float(f)}
                                        for b, f in zip(bound, forces, strict=True)]})
        if step == steps:
            break
        sum_force += force
        sum_flow += flow
        sum_bound += int(bound.sum())
        # Tension enhances rupture per Bell law; compression uses unloaded off rate.
        # Cap exponential at 60 only to avoid overflow; p_off already rounds to 1.
        exponent = np.maximum(forces, 0) / p.rupture_force_pN if force_feedback else np.zeros(p.clutches)
        off_probability = -np.expm1(-p.off_rate_s * np.exp(np.minimum(exponent, 60)) * dt)
        on_probability = -math.expm1(-p.on_rate_s * dt)
        off = bound & (rng.random(p.clutches) < off_probability)
        on = ~bound & (rng.random(p.clutches) < on_probability)
        max_probability = max(max_probability, float(np.max(off_probability[bound], initial=0)), on_probability)
        refs[on] = a - xs  # Newly engaged clutch starts at zero force.
        bound[off] = False
        bound[on] = True
        off_count += int(off.sum())
        on_count += int(on.sum())
        b = -kc * np.sum(refs[bound])
        a, z = (propagators[int(bound.sum())] @ np.array([a, z, b, 1.0]))[:2]
    summary = {"mean_traction_pN": sum_force / steps, "mean_retrograde_nm_s": sum_flow / steps,
               "mean_spreading_proxy_nm_s": p.unloaded_speed_nm_s - sum_flow / steps,
               "mean_bound_clutches": sum_bound / steps, "binding_events": on_count,
               "rupture_events": off_count, "max_force_balance_residual_pN": float(max_balance),
               "max_frozen_rate_event_probability": max_probability,
               "steps": steps, "actual_dt_s": dt}
    return {"frames": frames, "summary": summary}


def parameter_provenance(p):
    main_text = {"long_term_stiffness_pN_nm": 0.1, "additional_stiffness_pN_nm": 1.0,
                 "viscosity_pN_s_nm": 1.0}
    return {name: {"value": value, "status": "source_model_example" if main_text.get(name) == value else "assumed_scenario",
                   "source": SOURCE + "#fig01" if main_text.get(name) == value else None,
                   "note": "Fig.1C/D model setting, not a measured fish parameter" if main_text.get(name) == value else
                           "Operator-selected illustration; supplementary Table S1 not retrieved; not calibrated"}
            for name, value in asdict(p).items()}


def run_request(request: dict):
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    allowed = {"schema", "parameters", "duration_s", "dt_s", "seed", "frame_count"}
    if set(request) - allowed:
        raise ValueError("unknown request fields: " + ", ".join(sorted(set(request) - allowed)))
    if request.get("schema", SCHEMA) != SCHEMA:
        raise ValueError("unsupported request schema")
    try:
        p = Parameters(**request.get("parameters", {}))
    except TypeError as exc:
        raise ValueError(str(exc)) from exc
    duration, dt = request.get("duration_s", 20.0), request.get("dt_s", 0.01)
    for name, value, lo, hi in (("duration_s", duration, 1, 60), ("dt_s", dt, 0.001, 0.02)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"{name} must be in [{lo}, {hi}]")
    seed, count = request.get("seed", 7), request.get("frame_count", 201)
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be integer in [0,2**32)")
    if type(count) is not int or not 2 <= count <= 301:
        raise ValueError("frame_count must be integer in [2,301]")
    echo = {"schema": SCHEMA, "parameters": asdict(p), "duration_s": duration,
            "dt_s": dt, "seed": seed, "frame_count": count}
    started = time.perf_counter()
    numerical = simulate(p, duration_s=duration, dt_s=dt, seed=seed, frame_count=count)
    env = environment()
    return {"schema": "frontier.mechanobio.result/1", "status": "simulated", "evidence_kind": "simulated",
            "title": "Force-feedback motor clutches on a relaxing ECM contact",
            "request_echo": echo, "parameter_provenance": parameter_provenance(p),
            "units": {"force": "pN", "position": "nm", "time": "s", "velocity": "nm/s",
                      "stiffness": "pN/nm", "viscosity": "pN s/nm"},
            "model": {"source": SOURCE, "equations": "Model Description Eqs.1–6; slip bonds, no reinforcement",
                      "status": "scoped_implementation_not_paper_reproduction", "scale": ["molecular", "cell"],
                      "calibration": "none", "substrate_relaxation_s": p.viscosity_pN_s_nm / p.additional_stiffness_pN_nm
                      if p.additional_stiffness_pN_nm else None},
            "assumptions": ["All clutches share actin translation; linear springs, quasi-static force balance.",
                            "No rupture enhancement for compressive force; positive tensile force follows Bell law.",
                            "Polymerization speed equals unloaded flow only to define a displayed spreading proxy.",
                            "Initially all clutches disengaged; substrate and actin positions zero."],
            "not_established": NOT_ESTABLISHED,
            "open_questions": ["Measure target cell clutch kinetics, myosin stall load and ECM contact relaxation.",
                               "Does a validated cell-to-tissue constitutive bridge connect this to fin development?"],
            **numerical,
            "provenance": {"input_sha256": digest(echo), "code_files": code_hashes(),
                           "environment": env, "environment_sha256": digest(env),
                           "trajectory_sha256": digest(numerical), "elapsed_s": time.perf_counter() - started}}
