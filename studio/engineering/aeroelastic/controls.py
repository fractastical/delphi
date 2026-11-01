"""Analytic, transfer, geometry, mutation and reused-fluid controls before assay."""

import numpy as np

from engineering.cfd3d import vlm
from engineering.fin_mechanics import beam
from engineering.simulation.schema import G
from .flight import trajectory
from .model import (
    Response,
    check_inputs,
    deform,
    dump,
    protocol,
    setup,
    transfer,
    validate_lattice,
)


def run(out):
    check_inputs()
    p = protocol()
    g = p["gates"]
    checks = {}
    details = {}
    residuals = beam.control_residuals()
    checks["analytic_cantilever_quadrature"] = (
        max(
            x
            for v in residuals.values()
            for k, x in v.items()
            if k.endswith("residual")
        )
        <= g["analytic_tip_relative_max"]
    )
    x = np.linspace(0, 0.15, 401)
    a = np.array([0.037, 0.093, 0.15])
    forces = np.array([0.11, 0.02, 0.1])
    responses = []
    for elements in [1, 2, 4]:
        w, theta = Response(0.15, a, elements).evaluate(x, forces, 2.5e-4)
        responses.append(w)
    err = max(
        float(np.max(abs(w - responses[0])) / np.max(abs(responses[0])))
        for w in responses
    )
    details["FE1_2_4_relative_difference"] = err
    checks["FE_kernel_exactness_roundoff_not_rate"] = (
        err <= g["beam_kernel_FE1_2_4_relative_max"]
    )
    one = Response(0.15, np.array([0.15]))
    w, _ = one.evaluate(np.array([0.15]), np.array([0.37]), 2.5e-4)
    analytic = beam.tip_deflection_point_load(0.37, 0.15, 2.5e-4)
    checks["point_load_analytic"] = (
        abs(float(w[0]) / analytic - 1) <= g["analytic_tip_relative_max"]
    )
    try:
        one.evaluate(x, np.array([1.0]), -1.0)
        checks["negative_EI_rejected"] = False
    except ValueError:
        checks["negative_EI_rejected"] = True
    fins = setup(8, 2)
    lats = {name: fin["lattice"] for name, fin in fins.items()}
    _, F, _, _ = vlm.solve(vlm.combine(lats), 4)
    offset = 0
    zeros = {}
    stiff = {}
    transfer_ok = True
    mutant = False
    invalid = False
    for name, fin in fins.items():
        size = len(fin["lattice"]["area"])
        force = F[offset : offset + size] * p["parameters"]["rho_kg_m3"] * 20**2
        offset += size
        normal, ledger = transfer(fin, fin["lattice"], force)
        transfer_ok &= ledger["passed"]
        dropped = normal.copy()
        dropped[int(abs(dropped).argmax())] = 0
        mutant |= not transfer(fin, fin["lattice"], force, dropped)[1]["passed"]
        zeros[name] = deform(fin, np.zeros_like(normal), 1.0)
        EI = p["parameters"]["EI_inputs"][name]["EI_Nm2_by_compliance"]["0.8"]
        stiff[name] = deform(fin, normal, EI * g["stiff_limit_EI_multiplier"])
        probe = np.linspace(0, fin["length"], 501)
        tiny_w, tiny_s = fin["response"].evaluate(
            probe, normal, EI * g["stiff_limit_EI_multiplier"]
        )
        checks["stiff_limit_tip_" + name] = (
            max(abs(tiny_w)) / fin["length"] <= g["stiff_limit_tip_over_span_max"]
        )
        soft_w, soft_s = fin["response"].evaluate(probe, normal, EI * 0.8 / 20)
        invalid |= not beam.check_small_deformation(
            float(soft_w[-1]),
            float(max(abs(soft_s))),
            fin["length"],
            g["small_deflection_tip_over_span_max"],
            g["small_slope_max_rad"],
        )["valid"]
    checks["full_vector_force_moment_virtualwork_transfer"] = bool(transfer_ok)
    checks["omitted_load_mutation_rejected"] = bool(mutant)
    checks["excessive_compliance_model_exit"] = bool(invalid)

    def CL(lattice):
        _, force, _, _ = vlm.solve(vlm.combine(lattice), 4)
        S = sum(f["lattice"]["area"].sum() for f in fins.values())
        angle = np.deg2rad(4)
        return float(
            force.sum(axis=0) @ np.array([-np.sin(angle), 0, np.cos(angle)]) / (0.5 * S)
        )

    baseline = CL(lats)
    zero = CL(zeros)
    hard = CL(stiff)
    details.update(rigid_CL=baseline, zero_load_CL=zero, stiff_limit_CL=hard)
    checks["zero_load_geometry_exact"] = all(
        np.array_equal(lats[name][key], zeros[name][key])
        for name in fins
        for key in ["A", "B", "C"]
    )
    checks["zero_load_aero_reproduction"] = (
        abs(zero - baseline) <= g["zero_load_CL_absolute_difference_max"]
    )
    checks["stiff_limit_aero_reproduction"] = (
        abs(hard - baseline) <= g["stiff_limit_CL_absolute_difference_max"]
    )
    broken = {
        k: v.copy() if isinstance(v, np.ndarray) else v
        for k, v in lats[next(iter(fins))].items()
    }
    broken["area"][0] = 0
    try:
        validate_lattice(broken)
        checks["degenerate_cell_rejected"] = False
    except ValueError:
        checks["degenerate_cell_rejected"] = True
    raw, ballistic = trajectory(0.3, 0.004, 4, 20, 0.001, drag=False, lift=False)
    expected = 20 * np.sqrt(2 * p["glide"]["height_m"] / G)
    checks["ballistic_analytic"] = (
        abs(ballistic["range_m"] - expected) / expected
        <= g["ballistic_range_relative_error_max"]
    )
    checks["gravity_energy"] = (
        float(np.ptp(raw["mechanical_energy_J"])) / float(raw["mechanical_energy_J"][0])
        <= g["gravity_energy_relative_variation_max"]
    )
    drag, _ = trajectory(0.3, 0.004, 4, 20, 0.002, drag=True, lift=False)
    checks["drag_energy_nonincreasing"] = bool(
        np.max(np.diff(drag["mechanical_energy_J"]))
        <= g["drag_energy_max_step_increase_J"]
    )
    from engineering.simulation.glide import _rhs

    state = np.array([[0.0], [4.0], [20.0], [-0.2]])
    derivative = _rhs(state, 0.05, 0.004, 1.204, 0.3, 0.0, 0.0)
    v = state[2, 0] * np.array([np.cos(state[3, 0]), np.sin(state[3, 0])])
    acceleration = np.array(
        [
            derivative[2, 0] * np.cos(state[3, 0])
            - state[2, 0] * np.sin(state[3, 0]) * derivative[3, 0],
            derivative[2, 0] * np.sin(state[3, 0])
            + state[2, 0] * np.cos(state[3, 0]) * derivative[3, 0],
        ]
    )
    checks["lift_orthogonal_velocity"] = (
        np.linalg.norm(acceleration) > 0
        and abs(float(acceleration @ v))
        / (np.linalg.norm(acceleration) * np.linalg.norm(v))
        <= g["lift_power_relative_error_max"]
    )
    details["upstream_VLM_controls"] = vlm.controls()
    checks["upstream_VLM_frozen_controls"] = details["upstream_VLM_controls"][
        "all_pass"
    ]
    result = {
        "schema": "frontier.aeroelastic.controls/1",
        "checks": checks,
        "details": details,
        "passed": all(checks.values()),
        "scope": "Numerical/analytic/model-consistency controls only; not measured biological validity",
    }
    dump(out, result)
    return result
