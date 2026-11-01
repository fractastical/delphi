"""Explicit one-way transfer: rigidize solved shape, then use existing glide RK4."""

import numpy as np

from engineering.simulation import glide
from engineering.simulation.schema import G
from .model import protocol


def trajectory(CL, area, AR, speed, dt, drag=True, lift=True):
    p = protocol()
    f = p["glide"]
    rho = p["parameters"]["rho_kg_m3"]
    native = glide.integrate(
        f["mass_kg"],
        area,
        AR,
        rho,
        CL,
        f["CD0"],
        f["oswald_e"],
        f["height_m"],
        speed,
        dt=dt,
        record_stride=1,
        drag=drag,
        lift=lift,
    )
    rows = [[0.0, 0.0, f["height_m"], speed, 0.0]]
    for old_time, state, active in native["series"]:
        if bool(active[0]):
            rows.append([old_time + dt, *state[:, 0].tolist()])
    values = np.asarray(rows)
    cd = float(glide.drag_coeff(CL, f["CD0"], f["oswald_e"], AR)) if drag else 0.0
    mass = f["mass_kg"]
    energy = 0.5 * mass * values[:, 3] ** 2 + mass * G * values[:, 2]
    power = -0.5 * rho * values[:, 3] ** 3 * area * cd
    work = np.trapezoid(power, values[:, 0])
    return {
        "time_s": values[:, 0],
        "state_x_h_V_gamma": values[:, 1:],
        "mechanical_energy_J": energy,
        "drag_power_W": power,
    }, {
        "range_m": float(native["range_m"][0]),
        "time_s": float(native["time_s"][0]),
        "end_reason": int(native["end_reason"][0]),
        "actual_integrated_saved_states": len(rows),
        "dt_s": dt,
        "CL_fixed": CL,
        "reference_area_m2": area,
        "AR": AR,
        "mass_kg": mass,
        "initial_energy_J": float(energy[0]),
        "last_saved_energy_J": float(energy[-1]),
        "drag_work_J": float(work),
        "saved_state_energy_balance_residual_J": float(energy[-1] - energy[0] - work),
        "time_adapter": "Actual active post-step states relabeled from upstream k*dt to(k+1)*dt; initialstate explicit; interpolated event endpoint remains scalar result, not a trajectory frame",
        "scope": f["scope"],
    }
