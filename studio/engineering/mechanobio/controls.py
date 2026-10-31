"""Analytic, null, force-law mutation and timestep controls; no biological claims."""
from dataclasses import replace

import numpy as np
from scipy.integrate import solve_ivp

from .model import Parameters, simulate


def run_controls(replicates=12):
    p = Parameters(additional_stiffness_pN_nm=0, off_rate_s=0, on_rate_s=0)
    run = simulate(p, duration_s=4, dt_s=0.02, initial_bound=True)
    frames = run["frames"]
    k = p.clutches * p.clutch_stiffness_pN_nm
    effective = k * p.long_term_stiffness_pN_nm / (k + p.long_term_stiffness_pN_nm)
    stall = p.motors * p.motor_stall_pN
    t = np.array([f["t_s"] for f in frames])
    expected = stall * (-np.expm1(-p.unloaded_speed_nm_s * effective * t / stall))
    error = float(np.max(np.abs(expected - [f["traction_pN"] for f in frames])))
    visco = replace(p, additional_stiffness_pN_nm=1.0)
    visco_run = simulate(visco, duration_s=4, dt_s=0.02, initial_bound=True)
    ka, kl, eta = visco.additional_stiffness_pN_nm, visco.long_term_stiffness_pN_nm, visco.viscosity_pN_s_nm

    def direct_paper_equation(_t, y):
        # Independent coordinates [a,xs], obtained directly from paper Eq2
        # and dF/dt=K*(da/dt-dxs/dt), with fixed all-bound topology.
        a, xs = y
        force = k * (a - xs)
        velocity = visco.unloaded_speed_nm_s * (1 - force / stall)
        dxs = (ka * force + eta * k * velocity - ka * kl * xs) / (eta * (ka + kl + k))
        return [velocity, dxs]

    independent = solve_ivp(direct_paper_equation, [0, 4], [0, 0], t_eval=t, rtol=1e-11, atol=1e-12)
    expected_force = k * (independent.y[0] - independent.y[1])
    visco_error = float(np.max(np.abs(expected_force - [f["traction_pN"] for f in visco_run["frames"]])))
    null = simulate(Parameters(on_rate_s=0), duration_s=4, dt_s=0.01)
    null_max = max(abs(f["traction_pN"]) for f in null["frames"])
    stationary = simulate(Parameters(unloaded_speed_nm_s=0), duration_s=4, dt_s=0.01)
    stationary_max = max(abs(f["traction_pN"]) for f in stationary["frames"])
    # Same seeded stochastic draws; replacing force-dependent rupture by constant
    # rupture must change traction and off-events. This is a behavioral mutation
    # control, not independent biological validation or a whole-suite mutation kill.
    base_p = replace(Parameters(), long_term_stiffness_pN_nm=1.0, clutches=5, rupture_force_pN=1.0)
    base = simulate(base_p, duration_s=12, seed=19)
    mutant = simulate(base_p, duration_s=12, seed=19, force_feedback=False)
    mutation_delta = abs(base["summary"]["mean_traction_pN"] - mutant["summary"]["mean_traction_pN"])
    means = {}
    for dt in (0.02, 0.01, 0.005):
        values = [simulate(Parameters(), duration_s=10, dt_s=dt, seed=seed, frame_count=2)["summary"]["mean_traction_pN"]
                  for seed in range(replicates)]
        means[str(dt)] = {"mean_pN": float(np.mean(values)), "sd_pN": float(np.std(values, ddof=1)),
                          "se_pN": float(np.std(values, ddof=1) / np.sqrt(replicates)), "n": replicates}
    fine, coarse = means["0.005"], means["0.01"]
    difference = abs(fine["mean_pN"] - coarse["mean_pN"])
    # Declared screening tolerance: 10% of finest mean plus independent-SE envelope.
    # Seeds are common, so this is deliberately not described as a confidence test.
    tolerance = float(0.1 * abs(fine["mean_pN"]) + 3 * np.hypot(fine["se_pN"], coarse["se_pN"]))
    out = {"evidence_kind": "computational_check", "replicates": replicates,
           "analytic_elastic_no_rupture": {"max_error_pN": error, "tolerance_pN": 1e-9,
                                           "equation": "F=Nm*Fm*(1-exp(-vu*k_series*t/(Nm*Fm)))",
                                           "passed": error < 1e-9},
           "independent_viscoelastic_integration": {"max_error_pN": visco_error, "tolerance_pN": 1e-7,
                                                    "reference": "solve_ivp direct paper Eq2 in [actin,substrate] coordinates",
                                                    "passed": visco_error < 1e-7},
           "zero_binding": {"max_force_pN": null_max, "passed": null_max == 0},
           "zero_motor_velocity": {"max_force_pN": stationary_max, "passed": stationary_max == 0},
           "force_balance": {"max_residual_pN": base["summary"]["max_force_balance_residual_pN"],
                             "passed": base["summary"]["max_force_balance_residual_pN"] < 1e-9},
           "bell_law_mutant": {"mutation": "replace exp(force/Fb) with 1", "same_seed": 19,
                               "parameters": {"long_term_stiffness_pN_nm": 1.0, "clutches": 5,
                                              "rupture_force_pN": 1.0, "others": "Parameters defaults"},
                               "baseline_mean_pN": base["summary"]["mean_traction_pN"],
                               "mutant_mean_pN": mutant["summary"]["mean_traction_pN"],
                               "absolute_change_pN": mutation_delta,
                               "detection_threshold_pN": 1.0, "detected": mutation_delta > 1.0},
           "timestep_screen": {"statistics": means, "coarse_fine_difference_pN": difference,
                               "declared_tolerance_pN": float(tolerance), "passed": difference < tolerance,
                               "scope": "ensemble mean traction for default parameters over 10 s; not uniform convergence of all settings"}}
    out["passed"] = all(v.get("passed", v.get("detected", True)) for v in out.values() if isinstance(v, dict))
    return out
