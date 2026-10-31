"""Source-form CPG phase/amplitude dynamics plus designed dimensioned joint servo.

Eight coarse segments; not biological somites. Signed local joint angle rad,
time s, torque N*m. Independent plant joints, no hydrodynamics or translation.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path
import time

import numpy as np

HERE = Path(__file__).parent
N = 8
DEFAULTS = {"frequency_Hz": 35.0, "amplitude_rad": .1, "coupling_s": 80.0,
            "amplitude_rate_s": 80.0, "phase_lag_rad": 2 * math.pi / 7,
            "dt_s": .0002, "duration_s": 2.0, "feedback": True, "feedback_sign": 1,
            "inertia_scale": 1.0}
J = 1e-8  # kg*m^2: assumed nominal actuator inertia, not measured fish inertia.
B = 2e-7  # N*m*s/rad: assumed damping.
K = 1e-5  # N*m/rad: assumed stiffness.
KP = .003  # N*m/rad; engineering feedback gain.
KD = 1e-5  # N*m*s/rad; engineering feedback gain.
TORQUE_MAX = 1e-4  # N*m: declared actuation bound.
ANGLE_INTERFACE_MAX = .262  # rad: proposed static wind-tunnel interface envelope only.


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(data):
    return sha256(canonical(data)).hexdigest()


def code_hashes():
    return {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob("*.py")) + [HERE / "sources.json", HERE / "protocol.json"]}


def validate(request):
    if not isinstance(request, dict) or set(request) - set(DEFAULTS):
        raise ValueError("unknown behavior request fields")
    p = DEFAULTS | request
    limits = {"frequency_Hz": (15, 45), "amplitude_rad": (.02, .15), "coupling_s": (0, 120),
              "amplitude_rate_s": (40, 120), "phase_lag_rad": (.1, 1.2), "inertia_scale": (.5, 2)}
    for key, (lower, upper) in limits.items():
        if isinstance(p[key], bool) or not isinstance(p[key], (int, float)) or not math.isfinite(p[key]) or not lower <= p[key] <= upper:
            raise ValueError(f"{key} outside declared finite scenario bounds")
    if p["dt_s"] not in (.0001, .0002, .0004) or isinstance(p["dt_s"], bool):
        raise ValueError("dt_s must be .0001,.0002 or.0004 seconds")
    if p["duration_s"] != 2 or type(p["feedback"]) is not bool or type(p["feedback_sign"]) is not int or p["feedback_sign"] not in (-1, 1):
        raise ValueError("duration fixed2s; feedback boolean and sign±1 required")
    return p


def cpg(state, p):
    phase, amplitude, rate = state[:3]
    velocity = np.full(N, 2 * math.pi * p["frequency_Hz"])
    bias = phase[:-1] - phase[1:] - p["phase_lag_rad"]
    velocity[1:] += amplitude[:-1] * p["coupling_s"] * np.sin(bias)
    acceleration = p["amplitude_rate_s"] * (p["amplitude_rate_s"] / 4 * (1 - amplitude) - rate)
    phase_acceleration = np.zeros(N)
    phase_acceleration[1:] = p["coupling_s"] * (rate[:-1] * np.sin(bias) + amplitude[:-1] * np.cos(bias) * (velocity[:-1] - velocity[1:]))
    reference = p["amplitude_rad"] * amplitude * np.cos(phase)
    reference_rate = p["amplitude_rad"] * (rate * np.cos(phase) - amplitude * np.sin(phase) * velocity)
    reference_acceleration = p["amplitude_rad"] * (acceleration * np.cos(phase) - 2 * rate * np.sin(phase) * velocity
                                                  - amplitude * np.cos(phase) * velocity**2 - amplitude * np.sin(phase) * phase_acceleration)
    return velocity, acceleration, reference, reference_rate, reference_acceleration


def torque(state, p, kinematics=None):
    _, _, reference, reference_rate, reference_acceleration = cpg(state, p) if kinematics is None else kinematics
    feedforward = J * reference_acceleration + B * reference_rate + K * reference
    feedback = p["feedback_sign"] * (KP * (reference - state[3]) + KD * (reference_rate - state[4])) if p["feedback"] else 0
    raw = feedforward + feedback
    return np.clip(raw, -TORQUE_MAX, TORQUE_MAX), raw


def rhs(state, p, disturbance):
    kinematics = cpg(state, p)
    phase_rate, amplitude_acceleration, _, _, _ = kinematics
    applied, _ = torque(state, p, kinematics)
    joint_acceleration = (applied + disturbance - B * state[4] - K * state[3]) / (J * p["inertia_scale"])
    return np.array([phase_rate, state[2], amplitude_acceleration, state[4], joint_acceleration])


def rk4(state, dt, derivative):
    k1 = derivative(state)
    k2 = derivative(state + dt * k1 / 2)
    k3 = derivative(state + dt * k2 / 2)
    k4 = derivative(state + dt * k3)
    return state + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6


def wrap(angle):
    return np.arctan2(np.sin(angle), np.cos(angle))


def simulate(request=None):
    p = validate({} if request is None else request)
    started = time.perf_counter()
    state = np.zeros((5, N))
    state[0] = -np.arange(N) * p["phase_lag_rad"] + .3 * np.sin(np.arange(N))
    count = round(p["duration_s"] / p["dt_s"])
    dt = p["duration_s"] / count
    stride = round(.002 / dt)
    saved, times = [], []
    kick_step = round(.8 / dt)
    for step in range(count + 1):
        t = step * dt
        if step == kick_step:
            state[0, 4] += 1.0
        if step % stride == 0 or step == count:
            saved.append(state.copy())
            times.append(t)
        if step == count:
            break
        disturbance = 2e-5 if 1.1 <= (step + .5) * dt < 1.3 else 0.0
        state = rk4(state, dt, lambda y: rhs(y, p, disturbance))
    states = np.asarray(saved)
    if not np.isfinite(states).all():
        raise RuntimeError("nonfinite actuator/CPG state")
    references = np.array([cpg(y, p)[2] for y in states])
    torques = np.array([torque(y, p)[0] for y in states])
    saturated = np.array([np.abs(torque(y, p)[1]) > TORQUE_MAX for y in states])
    time_values = np.asarray(times)
    tracking = states[:, 3] - references
    phase_error = wrap(states[:, 0, :-1] - states[:, 0, 1:] - p["phase_lag_rad"])
    settled, final = time_values >= .5, time_values >= 1.7
    actual_frequency = float((states[-1, 0, 0] - states[0, 0, 0]) / (2 * math.pi * p["duration_s"]))
    metrics = {"tracking_relative_rms_after_0_5s": float(np.sqrt(np.mean(tracking[settled]**2)) / p["amplitude_rad"]),
               "phase_error_rms_final_0_3s_rad": float(np.sqrt(np.mean(phase_error[final]**2))),
               "leader_frequency_Hz": actual_frequency, "peak_abs_angle_rad": float(np.max(np.abs(states[:, 3]))),
               "outside_proposed_static_angle_envelope": bool(np.max(np.abs(states[:, 3])) > ANGLE_INTERFACE_MAX),
               "sampled_torque_saturation_fraction": float(saturated.mean())}
    return {"schema": "frontier.behavior.result/1", "evidence_kind": "SimulationResult", "status": "simulated", "model_id": "phase_cpg_joint_servo",
            "request": p, "metrics": metrics, "time_s": times, "phase_rad": states[:, 0].tolist(),
            "normalized_amplitude": states[:, 1].tolist(), "reference_angle_rad": references.tolist(),
            "actual_angle_rad": states[:, 3].tolist(), "angular_velocity_rad_s": states[:, 4].tolist(), "actuator_torque_Nm": torques.tolist(),
            "phase_error_rad": phase_error.tolist(), "left_activation": (states[:, 1] * (1 + np.cos(states[:, 0]))).tolist(),
            "right_activation": (states[:, 1] * (1 - np.cos(states[:, 0]))).tolist(),
            "source_envelope": json.loads((HERE / "sources.json").read_text()),
            "limitations": ["Reduced designed CPG controller and independent joint servo; not a zebrafish neural circuit reproduction or measured behavior.",
                            "Bilateral anti-phase output is imposed analytically, not discovered from inhibitory neurons.",
                            "Joint inertia/damping/stiffness/gains/torque and phase coupling are assumed; no muscle or fish calibration.",
                            "No hydrodynamics, thrust, swimming speed, genotype map or sensory circuit is modeled.",
                            "Static wind-tunnel angle envelope is only a proposed interface; dynamic force transfer remains unsupported."],
            "simulationAction": {"kind": "simulation", "input_sha256": digest(p), "code_sha256": code_hashes(),
                                 "state_sha256": sha256(states.astype("<f8").tobytes()).hexdigest(),
                                 "voluntary_motion_status": "not_a_brain_or_behavioral_inference", "elapsed_s": time.perf_counter() - started,
                                 "method": "event-aligned RK4", "units": {"time": "s", "phase_angle": "rad", "frequency": "Hz", "torque": "N*m"}}}
