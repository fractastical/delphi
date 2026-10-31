"""Analytic, conservative, step and continuum-grid controls; deliberate law mutant."""
from __future__ import annotations

import argparse
import json

import numpy as np

from .model import DEFAULTS, gap_current, rates, rhs, rk4_step, simulate


def gap_balance(mutant=False):
    voltages = np.array([-70.0, -40.0, 5.0, -20.0])
    value = float(gap_current(voltages, 0.5, mutant=mutant).sum())
    return {"name": "sealed_equal_area_gap_charge_balance", "sum_current_uA_cm2": value,
            "tolerance": 1e-12, "passed": abs(value) < 1e-12}


def passive_membrane():
    alpha, beta = rates(np.array([-65.0]))
    gates = alpha / (alpha + beta)
    state = np.vstack((np.array([-30.0]), gates))
    p = DEFAULTS | {"gap_mS_cm2": 0}
    m, h, n = gates[:, 0]
    conductances = np.array([120 * m**3 * h, 36 * n**4, 0.3])
    g = conductances.sum()
    equilibrium = float(conductances @ np.array([50, -77, -54.387]) / g)
    for _ in range(400):
        def frozen(y):
            derivative = rhs(y, p, 0)
            derivative[1:] = 0
            return derivative
        state = rk4_step(state, 0.025, frozen)
    exact = equilibrium + (-30 - equilibrium) * np.exp(-g * 10)
    error = float(abs(float(state[0, 0]) - exact))
    return {"name": "frozen_gate_capacitive_relaxation_closed_form", "final_mV": float(state[0, 0]),
            "analytic_mV": float(exact), "equilibrium_mV": equilibrium,
            "error_mV": error, "tolerance_mV": 1e-7, "passed": error < 1e-7,
            "formula": "V(t)=Eeff+(V0-Eeff)exp(-sum(g)*t/Cm), actual membrane-current implementation, gates held fixed"}


def voltage_clamp():
    a0, b0 = rates(np.array([-65.0]))
    initial = a0 / (a0 + b0)
    a, b = rates(np.array([-20.0]))
    gates = initial.copy()
    for _ in range(1000):
        gates = rk4_step(gates, 0.001, lambda q: a * (1 - q) - b * q)
    exact = a / (a + b) + (initial - a / (a + b)) * np.exp(-(a + b))
    error = float(np.max(np.abs(gates - exact)))
    return {"name": "voltage_clamp_gate_closed_form", "error": error,
            "tolerance": 1e-9, "passed": error < 1e-9,
            "formula": "q(t)=q_inf+(q0-q_inf)exp[-(alpha+beta)t], V=-20mV, t=1ms"}


def grid_convergence():
    """Independent smooth passive cable control of the same sealed-edge operator.

    This is a continuum control, not a claim that subdividing a biological cell
    leaves the network unchanged. The demo network has 12 fixed physical cells.
    """
    rows = []
    for count in (16, 32, 64):
        dx = 1.0 / count  # cm; chosen cable length L=1cm.
        x = (np.arange(count) + 0.5) * dx
        v = np.cos(np.pi * x)
        for _ in range(1000):
            v = rk4_step(v, 0.001, lambda y: gap_current(y, 0.01 / dx**2))
        exact = np.cos(np.pi * x) * np.exp(-0.01 * np.pi**2)
        rows.append({"n": count, "dx_cm": dx, "max_error_mV": float(np.max(np.abs(v - exact)))})
    ratios = [rows[i]["max_error_mV"] / rows[i+1]["max_error_mV"] for i in range(2)]
    return {"name": "sealed_passive_cable_grid_convergence", "rows": rows, "error_ratios": ratios,
            "passed": all(3.8 < r < 4.2 for r in ratios),
            "scope": "same conservative gap operator, D=.01cm^2/ms, L=1cm, cos(pi*x/L), Neumann boundary, t=1ms; not a calibration of the fixed 12-cell network"}


def time_convergence():
    runs = [simulate({"dt_ms": dt}) for dt in (0.025, 0.0125, 0.00625)]
    if any(r["status"] != "completed" for r in runs):
        return {"name": "HH_time_step_convergence", "passed": False, "error": "a run failed"}
    errors = []
    for first, second in zip(runs, runs[1:]):
        assert np.allclose(first["time_ms"], second["time_ms"], atol=1e-10)
        difference = np.array(first["voltage_mV"]) - second["voltage_mV"]
        errors.append(float(np.max(np.abs(difference))))
    return {"name": "HH_time_step_convergence", "dt_ms": [0.025, 0.0125, 0.00625],
            "successive_max_voltage_difference_mV": errors, "ratio": errors[0] / errors[1],
            "fine_tolerance_mV": 0.05, "passed": errors[1] < 0.05 and errors[0] / errors[1] > 8,
            "scope": "default pulse and network only; event-aligned RK4, all cells at common saved times"}


def run_controls(mutant=False):
    controls = [gap_balance(mutant), passive_membrane(), voltage_clamp(), grid_convergence(), time_convergence()]
    return {"schema": "frontier.bioelectric.controls/1", "passed": all(x["passed"] for x in controls),
            "mutation": "one gap endpoint sign reversed" if mutant else None, "checks": controls}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mutation", choices=["gap-sign"])
    args = parser.parse_args()
    result = run_controls(bool(args.mutation))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
