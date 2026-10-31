"""HH ion-channel kinetics with capacitive membranes and conservative gap currents.

Time ms, voltage intracellular-minus-extracellular mV, conductance mS/cm²,
capacitance µF/cm², current density µA/cm². A mS*mV equals a µA.
Fixed bath/reversal potentials; no ion depletion, pumps, gene or geometry dynamics.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

HERE = Path(__file__).parent
N_CELLS = 12
SOURCES = json.loads((HERE / "sources.json").read_text())
DEFAULTS = {
    "sodium_scale": 1.0, "potassium_scale": 1.0, "gap_mS_cm2": 0.5,
    "stimulus_uA_cm2": 12.0, "temperature_c": 6.3, "duration_ms": 30.0, "dt_ms": 0.025,
}
BOUNDS = {
    "sodium_scale": (0.0, 1.5), "potassium_scale": (0.25, 2.0), "gap_mS_cm2": (0.0, 2.0),
    "stimulus_uA_cm2": (0.0, 30.0), "temperature_c": (6.3, 18.0),
    "duration_ms": (10.0, 60.0), "dt_ms": (0.005, 0.025),
}
UNITS = {"sodium_scale": "1", "potassium_scale": "1", "gap_mS_cm2": "mS/cm^2",
         "stimulus_uA_cm2": "uA/cm^2", "temperature_c": "degC",
         "duration_ms": "ms", "dt_ms": "ms"}
LIMITATIONS = [
    "SIMULATED: published squid-axon membrane kinetics; not measured fin voltages.",
    "Equal-area 12-cell sealed chain and ohmic gap conductance are assumed design scenarios.",
    "All cells start at -65 mV with gates at their voltage-dependent steady states; perturbed conductances need not initially be at equilibrium.",
    "Fixed extracellular potential and reversal potentials represent infinite buffered ion reservoirs; no ion mass balance, pumps or depletion is modeled.",
    "Current is injected into cell 0 during 5 <= t < 6 ms; positive current is inward and depolarizing.",
    "No cross-scale map to gene expression, tissue pattern, fin anatomy, stiffness or flight has been established.",
]
QUESTIONS = [
    {"id": "bioelectric-cell-tissue", "status": "unknown", "scales": ["cell", "tissue"],
     "question": "Which ion channels, reservoir concentrations and gap conductances determine fin-cell voltage and its causal relation to tissue pattern?",
     "next_evidence": "Species- and developmental-stage-matched voltage/channel/coupling measurements and a held-out perturbation prediction."},
    {"id": "bioelectric-tissue-fin", "status": "unknown", "scales": ["tissue", "organ"],
     "question": "Can a measured tissue voltage perturbation predict fin geometry or material properties through a calibrated causal model?",
     "next_evidence": "An independently tested voltage-to-pattern-to-geometry bridge with uncertainty; no such calibration is in this model."},
]


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def code_hashes() -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(HERE.glob("*.py")) + [HERE / "sources.json"]}


def _vtrap(x, scale):
    """x/(exp(x/scale)-1), with analytic removable-singularity expansion."""
    z = np.asarray(x, dtype=float) / scale
    out = np.empty_like(z)
    small = np.abs(z) < 1e-6
    out[small] = scale * (1 - z[small] / 2 + z[small] ** 2 / 12)
    out[~small] = scale * z[~small] / np.expm1(z[~small])
    return out


def rates(v, temperature_c=6.3):
    """Return alpha/beta in ms^-1 for (m,h,n), modern voltage convention."""
    v = np.asarray(v)
    q10 = 3.0 ** ((temperature_c - 6.3) / 10.0)
    alpha = np.array([0.1 * _vtrap(-(v + 40), 10),
                      0.07 * np.exp(-(v + 65) / 20), 0.01 * _vtrap(-(v + 55), 10)])
    beta = np.array([4 * np.exp(-(v + 65) / 18),
                     1 / (np.exp(-(v + 35) / 10) + 1), 0.125 * np.exp(-(v + 65) / 80)])
    return q10 * alpha, q10 * beta


def gap_current(v, conductance, *, mutant=False):
    """Inward current per equal membrane area; every edge cancels exactly in sum.

    g_gap = absolute junction conductance / common membrane area. End cells
    have only one neighbor: no periodic edge and no external cable current.
    The explicit mutant reverses one current endpoint to violate charge balance.
    """
    edge = conductance * np.diff(v)
    current = np.zeros_like(v)
    current[:-1] += edge
    current[1:] += edge if mutant else -edge
    return current


def currents(state, p):
    v, m, h, n = state
    return np.array([120 * p["sodium_scale"] * m**3 * h * (v - 50),
                     36 * p["potassium_scale"] * n**4 * (v + 77),
                     0.3 * (v + 54.387)])


def rhs(state, p, injected):
    v = state[0]
    alpha, beta = rates(v, p["temperature_c"])
    dv = -currents(state, p).sum(axis=0) + gap_current(v, p["gap_mS_cm2"])
    dv[0] += injected  # C_m = 1 µF/cm², so dv/dt = current / C_m.
    return np.vstack((dv, alpha * (1 - state[1:]) - beta * state[1:]))


def rk4_step(state, dt, derivative):
    k1 = derivative(state)
    k2 = derivative(state + dt * k1 / 2)
    k3 = derivative(state + dt * k2 / 2)
    k4 = derivative(state + dt * k3)
    return state + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6


def validate_request(request):
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    unknown = set(request) - set(DEFAULTS) - {"schema"}
    if unknown:
        raise ValueError("unsupported fields: " + ", ".join(sorted(unknown)))
    if request.get("schema", "frontier.bioelectric.request/1") != "frontier.bioelectric.request/1":
        raise ValueError("unsupported request schema")
    p = DEFAULTS | {k: v for k, v in request.items() if k != "schema"}
    for key, value in p.items():
        lo, hi = BOUNDS[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"{key} must be finite in [{lo}, {hi}] {UNITS[key]}")
        p[key] = float(value)
    return p


def simulate(request=None):
    """Deterministic bounded UI entry point; no file writes or external calls."""
    started = time.perf_counter()
    try:
        p = validate_request({} if request is None else request)
    except ValueError as error:
        return {"schema": "frontier.bioelectric.result/1", "status": "invalid_request", "error": str(error),
                "evidence_kind": "SimulationResult"}
    alpha, beta = rates(np.full(N_CELLS, -65.0), p["temperature_c"])
    state = np.vstack((np.full(N_CELLS, -65.0), alpha / (alpha + beta)))
    states, times = [state.copy()], [0.0]
    # Split exactly at stimulus discontinuities, then use fixed current within
    # every RK4 interval. This prevents a half-weight pulse-endpoint error.
    t = 0.0
    sample_after = 0.1
    for left, right, current in [(0, 5, 0), (5, 6, p["stimulus_uA_cm2"]), (6, p["duration_ms"], 0)]:
        count = math.ceil((right - left) / p["dt_ms"])
        dt = (right - left) / count
        for step in range(count):
            state = rk4_step(state, dt, lambda y: rhs(y, p, current))
            t = left + (step + 1) * dt
            if t >= sample_after - 1e-10 or step == count - 1:
                states.append(state.copy())
                times.append(t)
                sample_after = t + 0.1
    values = np.asarray(states)
    if not np.isfinite(values).all() or np.min(values[:, 1:]) < -1e-6 or np.max(values[:, 1:]) > 1.000001:
        return {"schema": "frontier.bioelectric.result/1", "status": "numerical_failure",
                "evidence_kind": "SimulationResult", "error": "non-finite state or gating bound violation"}
    voltages = values[:, 0, :]
    peaks = voltages.max(axis=0)
    spike_times = [next((float(ti) for ti, vi in zip(times, voltages[:, i]) if vi > 0), None)
                   for i in range(N_CELLS)]
    parameters = {k: {"value": v, "unit": UNITS[k], "bounds": list(BOUNDS[k]),
                      "status": "design-selected", "source": "bounded scenario; source scaling, not measured values"}
                  for k, v in p.items()}
    parameters.update({k: {"value": v, "unit": unit, "status": "published-model-parameter",
                           "source": "10.1113/jphysiol.1952.sp004764 Table 3, p.520; modern sign/offset"}
                       for k, v, unit in [("C_m", 1, "uF/cm^2"), ("g_Na_max", 120, "mS/cm^2"),
                                          ("g_K_max", 36, "mS/cm^2"), ("g_leak", 0.3, "mS/cm^2"),
                                          ("E_Na", 50, "mV"), ("E_K", -77, "mV"), ("E_leak", -54.387, "mV")]})
    return {
        "schema": "frontier.bioelectric.result/1", "model_id": "hh1952_gap_chain",
        "status": "completed", "evidence_kind": "SimulationResult", "request": p,
        "parameters": parameters, "n_cells": N_CELLS, "time_ms": times, "voltage_mV": voltages.tolist(),
        "gates_m_h_n": values[:, 1:].tolist(),
        "ionic_current_uA_cm2": [currents(s, p).tolist() for s in values],
        "metrics": {"peak_mV_by_cell": peaks.tolist(), "first_crossing_0mV_ms_by_cell": spike_times,
                    "cells_crossing_0mV": int(sum(t is not None for t in spike_times)),
                    "final_mV_by_cell": voltages[-1].tolist()},
        "source_envelope": SOURCES, "limitations": LIMITATIONS, "open_questions": QUESTIONS,
        "simulationAction": {"kind": "simulation", "engine": "independent HH + ohmic equal-area cell network",
                             "method": "classical RK4, event-aligned current steps; actual sampled integration states",
                             "input_sha256": digest(p), "code_sha256": code_hashes(),
                             "state_sha256": hashlib.sha256(values.astype("<f8").tobytes()).hexdigest(),
                             "voltage_sha256": hashlib.sha256(voltages.astype("<f8").tobytes()).hexdigest(),
                             "time_sha256": hashlib.sha256(np.asarray(times, dtype="<f8").tobytes()).hexdigest(),
                             "elapsed_s": time.perf_counter() - started, "exit_status": 0,
                             "units": {"time": "ms", "voltage": "mV", "current": "uA/cm^2"},
                             "scope": "numerical scenario; biological validity not established"},
    }
