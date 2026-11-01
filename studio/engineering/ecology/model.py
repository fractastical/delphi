"""MuJoCo dynamics with actual v3a panel-derived quasisteady force interfaces."""

from hashlib import sha256
import json
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/ecology"
GEOM = ROOT / "artifacts/fish3d/fish3d-v3a-fan"
FINS = ["pectoral_L", "pectoral_R", "pelvic_L", "pelvic_R"]
FLIP = np.diag([-1.0, -1.0, 1.0])


def dump(path, value):
    def scalar(item):
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(f"Unsupported JSON value: {type(item).__name__}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False, default=scalar) + "\n")


def protocol():
    return json.loads((ART / "protocol.json").read_text())


def geometry(params):
    candidate = json.loads((GEOM / "candidate.json").read_text())
    panels = json.loads((GEOM / "panels.json").read_text())["fins"]
    components = json.loads((GEOM / "components.json").read_text())
    polar_path = ROOT / "artifacts/cfd3d/vlm/fish3d-v3a-fan/vlm.json"
    polar = json.loads(polar_path.read_text())
    for item in protocol()["geometry"]["paths"]:
        if sha256((ROOT / item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("geometry/polar input hash changed")
    if (
        polar["candidate_sha256"]
        != sha256((GEOM / "candidate.json").read_bytes()).hexdigest()
    ):
        raise ValueError("VLM candidate identity mismatch")
    if (
        polar["panels_sha256"]
        != sha256((GEOM / "panels.json").read_bytes()).hexdigest()
    ):
        raise ValueError("VLM panel identity mismatch")
    length = candidate["biology"]["standard_length_m"]["value"]
    cg = params["cg_from_nose_over_standard_length"] * length
    center = np.array([cg, 0, 0])
    bbox = np.asarray(components["components"]["body"]["check"]["bbox_mm"]) * 0.001
    out = {
        "cg_from_nose_m": cg,
        "length_m": length,
        "body_half_size_m": (bbox[1] - bbox[0]) / 2,
        "fins": {},
    }
    for name in FINS:
        fin = panels[name]
        q = np.asarray(fin["quads_m"])
        area = (
            np.linalg.norm(np.cross(q[:, 1] - q[:, 0], q[:, 2] - q[:, 0]), axis=1)
            + np.linalg.norm(np.cross(q[:, 2] - q[:, 0], q[:, 3] - q[:, 0]), axis=1)
        ) / 2
        centroid = np.sum(q.mean(axis=1) * area[:, None], axis=0) / area.sum()
        root = FLIP @ (np.asarray(fin["fin_plane"]["origin_m"]) - center)
        centroid = FLIP @ (centroid - center)
        outline = (np.asarray(fin["outline_m"]) - center) @ FLIP
        normal = FLIP @ np.cross(fin["fin_plane"]["e_u"], fin["fin_plane"]["e_w"])
        normal *= 1 if normal[2] >= 0 else -1
        normal /= np.linalg.norm(normal)
        span = np.ptp(outline[:, 1])
        out["fins"][name] = {
            "root_m": root,
            "centroid_relative_root_m": centroid - root,
            "normal": normal,
            "area_m2": fin["area_flat_m2"],
            "AR": max(span * span / fin["area_flat_m2"], 0.1),
            "extent_m": np.maximum(np.ptp(outline, axis=0), 0.0002),
            "alpha_deg": np.array([0.0, 4.0, 8.0]),
            "CL": np.array(
                [
                    polar["cases"][str(a)]["fins"][name]["CL_fin_on_own_lattice_area"]
                    for a in [0, 4, 8]
                ]
            ),
        }
    return out


def aero(velocity, normal, area, cl, cd, rho):
    speed = np.linalg.norm(velocity)
    if speed < 1e-10:
        return np.zeros(3), np.zeros(3)
    direction = velocity / speed
    lift_dir = normal - direction * np.dot(normal, direction)
    norm = np.linalg.norm(lift_dir)
    if norm > 1e-12:
        lift_dir /= norm
    else:
        lift_dir[:] = 0
    q = 0.5 * rho * speed * speed * area
    return q * cl * lift_dir, -q * cd * direction


def angles(rotation):
    return np.arctan2(rotation[2, 0], np.linalg.norm(rotation[:2, 0])), np.arctan2(
        rotation[2, 1], rotation[2, 2]
    )


def build(n, params, dt):
    geo = geometry(params)
    mass = params["mass_kg"]
    finmass = mass * params["fin_mass_fraction_each"]
    bodymass = mass - 4 * finmass
    half = geo["body_half_size_m"]
    inertia = (
        bodymass
        * np.array(
            [
                half[1] ** 2 + half[2] ** 2,
                half[0] ** 2 + half[2] ** 2,
                half[0] ** 2 + half[1] ** 2,
            ]
        )
        / 5
    )
    neutral = -np.deg2rad(params["initial_fin_incidence_deg"])
    parts = [
        f'<mujoco model="v3a-airborne"><compiler angle="radian"/><option timestep="{dt}" integrator="implicitfast" gravity="0 0 -9.81" density="0" viscosity="0"/><worldbody>'
    ]
    motors = []
    for i in range(n):
        pos = (
            [0, 0, params["initial_height_m"]]
            if n == 1
            else [
                (i // 2) * params["school_layout_m"]["x_spacing"],
                (i % 2) * params["school_layout_m"]["y_spacing"],
                params["initial_height_m"],
            ]
        )
        parts.append(
            f'<body name="fish{i}" pos="{pos[0]} {pos[1]} {pos[2]}"><freejoint name="free{i}"/><inertial pos="0 0 0" mass="{bodymass}" diaginertia="{inertia[0]} {inertia[1]} {inertia[2]}"/>'
        )
        for name, fin in geo["fins"].items():
            root, center = fin["root_m"], fin["centroid_relative_root_m"]
            ext = fin["extent_m"] / 2
            iner = (
                finmass
                * np.array(
                    [
                        ext[1] ** 2 + ext[2] ** 2,
                        ext[0] ** 2 + ext[2] ** 2,
                        ext[0] ** 2 + ext[1] ** 2,
                    ]
                )
                / 3
            )
            parts.append(
                f'<body name="fish{i}_{name}" pos="{root[0]} {root[1]} {root[2]}"><joint name="joint{i}_{name}" type="hinge" axis="0 1 0" range="{-params["joint_angle_limit_rad"]} {params["joint_angle_limit_rad"]}" stiffness="{params["fin_stiffness_Nm_rad"]}" springref="{neutral}" damping="{params["fin_damping_Nm_s_rad"]}"/><inertial pos="{center[0]} {center[1]} {center[2]}" mass="{finmass}" diaginertia="{iner[0]} {iner[1]} {iner[2]}"/></body>'
            )
            motors.append(
                f'<motor name="motor{i}_{name}" joint="joint{i}_{name}" gear="1" ctrllimited="true" ctrlrange="{-params["joint_torque_limit_Nm"]} {params["joint_torque_limit_Nm"]}"/>'
            )
        parts.append("</body>")
    parts.append("</worldbody><actuator>" + "".join(motors) + "</actuator></mujoco>")
    xml = "".join(parts)
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    ids = []
    for i in range(n):
        body = model.body(f"fish{i}").id
        free = model.joint(f"free{i}").id
        qadr, vadr = model.jnt_qposadr[free], model.jnt_dofadr[free]
        data.qvel[vadr] = params["initial_speed_m_s"]
        joints = []
        for name in FINS:
            j = model.joint(f"joint{i}_{name}").id
            data.qpos[model.jnt_qposadr[j]] = neutral
            joints.append(
                {
                    "name": name,
                    "body": model.body(f"fish{i}_{name}").id,
                    "q": int(model.jnt_qposadr[j]),
                    "v": int(model.jnt_dofadr[j]),
                    "motor": model.actuator(f"motor{i}_{name}").id,
                }
            )
        ids.append({"body": body, "q": int(qadr), "v": int(vadr), "joints": joints})
    mujoco.mj_forward(model, data)
    return model, data, geo, ids, xml


def dynamics_forces(model, data, geo, ids, params):
    data.qfrc_applied[:] = 0
    forces = np.zeros((len(ids), 3))
    torques = forces.copy()
    alphas = []
    power = 0.0
    lift_dot = 0.0
    for i, fish in enumerate(ids):
        for joint in fish["joints"]:
            fin = geo["fins"][joint["name"]]
            bid = joint["body"]
            velocity = np.zeros(6)
            mujoco.mj_objectVelocity(
                model, data, mujoco.mjtObj.mjOBJ_BODY, bid, velocity, 0
            )
            normal = data.xmat[bid].reshape(3, 3) @ fin["normal"]
            speed = np.linalg.norm(velocity[3:])
            alpha = -np.arcsin(
                np.clip(np.dot(velocity[3:], normal) / max(speed, 1e-12), -1, 1)
            )
            alphas.append(float(alpha))
            if abs(np.rad2deg(alpha)) > params["alpha_domain_deg"][1]:
                # The caller retains this actual terminal state and stops before
                # integration. Never evaluate a clipped/extrapolated polar there.
                continue
            cl = np.interp(
                abs(np.rad2deg(alpha)), fin["alpha_deg"], fin["CL"]
            ) * np.sign(alpha)
            cd = params["fin_CD0"] + cl * cl / (
                np.pi * params["oswald_efficiency"] * fin["AR"]
            )
            lift, drag = aero(
                velocity[3:],
                normal,
                fin["area_m2"],
                cl,
                cd,
                params["air_density_kg_m3"],
            )
            total = lift + drag
            mujoco.mj_applyFT(
                model, data, total, np.zeros(3), data.xipos[bid], bid, data.qfrc_applied
            )
            forces[i] += total
            torques[i] += np.cross(data.xipos[bid] - data.xpos[fish["body"]], total)
            power += np.dot(drag, velocity[3:])
            lift_dot = max(
                lift_dot,
                abs(np.dot(lift, velocity[3:]))
                / max(np.linalg.norm(lift) * speed, 1e-12),
            )
        v = np.zeros(6)
        mujoco.mj_objectVelocity(
            model, data, mujoco.mjtObj.mjOBJ_BODY, fish["body"], v, 0
        )
        area = np.pi * geo["body_half_size_m"][1] * geo["body_half_size_m"][2]
        _, drag = aero(
            v[3:],
            np.array([0, 0, 1.0]),
            area,
            0,
            params["body_CD"],
            params["air_density_kg_m3"],
        )
        mujoco.mj_applyFT(
            model,
            data,
            drag,
            np.zeros(3),
            data.xipos[fish["body"]],
            fish["body"],
            data.qfrc_applied,
        )
        forces[i] += drag
        power += np.dot(drag, v[3:])
    return (
        forces,
        torques,
        np.array(alphas).reshape(len(ids), 4),
        float(power),
        float(lift_dot),
    )


def energies(model, data, ids, params):
    values = []
    neutral = -np.deg2rad(params["initial_fin_incidence_deg"])
    for fish in ids:
        value = 0.0
        for bid in [fish["body"]] + [x["body"] for x in fish["joints"]]:
            v = np.zeros(6)
            mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, bid, v, 0)
            omega = data.ximat[bid].reshape(3, 3).T @ v[:3]
            value += (
                0.5 * model.body_mass[bid] * np.dot(v[3:], v[3:])
                + 0.5 * np.dot(model.body_inertia[bid] * omega, omega)
                + model.body_mass[bid] * 9.81 * data.xipos[bid, 2]
            )
        value += sum(
            0.5 * params["fin_stiffness_Nm_rad"] * (data.qpos[x["q"]] - neutral) ** 2
            for x in fish["joints"]
        )
        values.append(float(value))
    return values


def simulate(case, params, dt=None, seed=None):
    dt = dt or protocol()["solver"]["dt_s"]
    duration = protocol()["solver"]["duration_s"]
    model, data, geo, ids, xml = build(case["n"], params, dt)
    rng = np.random.default_rng(seed if seed is not None else params["initial_seed"])
    delays = rng.uniform(*params["reaction_delay_s_range"], len(ids))
    scheduled = np.full(len(ids), np.inf)
    triggered = np.zeros(len(ids), bool)
    commands = np.full((len(ids), 4), -np.deg2rad(params["initial_fin_incidence_deg"]))
    work = np.zeros(len(ids))
    signedwork = work.copy()
    fluid_work = 0.0
    damping_loss = 0.0
    initial_energy = float(sum(energies(model, data, ids, params)))
    frames = []
    reason = "duration reached"
    peaks = {
        "torque_Nm": 0.0,
        "positive_joint_power_W": 0.0,
        "joint_rate_rad_s": 0.0,
        "command_rate_rad_s": 0.0,
        "lift_dot_relative": 0.0,
        "drag_power_W_max": -1e300,
    }
    stride = round(protocol()["solver"]["saved_state_period_s"] / dt)
    force = np.zeros((len(ids), 3))
    torque = force.copy()
    alpha = np.zeros((len(ids), 4))
    for step in range(round(duration / dt) + 1):
        mujoco.mj_forward(model, data)
        force, torque, alpha, drag_power, lift_dot = dynamics_forces(
            model, data, geo, ids, params
        )
        rotation = [data.xmat[x["body"]].reshape(3, 3).copy() for x in ids]
        attitude = np.asarray([angles(x) for x in rotation])
        positions = np.asarray([data.xpos[x["body"]] for x in ids])
        t = float(data.time)
        for i in range(len(ids)):
            threat = (
                params["threat_window_s"][0] <= t <= params["threat_window_s"][1]
                and np.linalg.norm(positions[i] - params["threat_center_world_m"])
                <= params["threat_radius_m"]
            )
            near = (
                np.linalg.norm(positions - positions[i], axis=1)
                < params["neighbor_radius_m"]
            )
            near[i] = False
            social = bool(
                case["neighbors"]
                and np.any(
                    near
                    & (
                        np.abs(attitude[:, 1])
                        > np.deg2rad(params["social_observation_bank_threshold_deg"])
                    )
                )
            )
            if threat or social:
                scheduled[i] = min(scheduled[i], t + delays[i])
            triggered[i] |= t + 1e-12 >= scheduled[i]
        previous_velocity = np.asarray(
            [[data.qvel[j["v"]] for j in x["joints"]] for x in ids]
        )
        applied = np.zeros_like(previous_velocity)
        oldcommands = commands.copy()
        for i, fish in enumerate(ids):
            pitch, roll = attitude[i]
            omega = data.qvel[fish["v"] + 3 : fish["v"] + 6]
            bank_target = (
                np.deg2rad(params["escape_bank_target_deg"])
                if triggered[i] and case["n"] > 1
                else 0.0
            )
            pitchmix = np.clip(
                params["attitude_KP"] * (-pitch) + params["attitude_KD_s"] * omega[1],
                -params["control_incidence_delta_limit_rad"],
                params["control_incidence_delta_limit_rad"],
            )
            rollmix = np.clip(
                params["attitude_KP"] * (bank_target - roll)
                - params["attitude_KD_s"] * omega[0],
                -params["control_incidence_delta_limit_rad"],
                params["control_incidence_delta_limit_rad"],
            )
            for k, j in enumerate(fish["joints"]):
                neutral = -np.deg2rad(params["initial_fin_incidence_deg"])
                desired = neutral
                if case["feedback"]:
                    fin = geo["fins"][j["name"]]
                    desired -= pitchmix * (
                        1 if j["name"].startswith("pectoral") else -1
                    ) + rollmix * np.sign(fin["root_m"][1])
                    desired = np.clip(
                        desired,
                        -params["joint_angle_limit_rad"],
                        params["joint_angle_limit_rad"],
                    )
                    commands[i, k] += np.clip(
                        desired - commands[i, k],
                        -params["command_rate_limit_rad_s"] * dt,
                        params["command_rate_limit_rad_s"] * dt,
                    )
                    velocity = data.qvel[j["v"]]
                    raw = (
                        params["servo_KP_Nm_rad"] * (commands[i, k] - data.qpos[j["q"]])
                        - params["servo_KD_Nm_s_rad"] * velocity
                    )
                    limit = min(
                        params["joint_torque_limit_Nm"],
                        params["joint_positive_power_limit_W"]
                        / max(abs(velocity), 1e-12),
                    )
                    raw = float(np.clip(raw, -limit, limit))
                    if (
                        abs(velocity) >= params["actual_rate_gate_rad_s"]
                        and raw * velocity > 0
                    ):
                        raw = 0.0
                    if (
                        work[i] >= params["per_fish_positive_work_budget_J"]
                        and raw * velocity > 0
                    ):
                        raw = 0.0
                    applied[i, k] = raw
                data.ctrl[j["motor"]] = applied[i, k]
        peakpower = np.maximum(applied * previous_velocity, 0)
        peaks["torque_Nm"] = max(peaks["torque_Nm"], float(np.max(abs(applied))))
        peaks["positive_joint_power_W"] = max(
            peaks["positive_joint_power_W"], float(np.max(peakpower))
        )
        peaks["joint_rate_rad_s"] = max(
            peaks["joint_rate_rad_s"], float(np.max(abs(previous_velocity)))
        )
        peaks["command_rate_rad_s"] = max(
            peaks["command_rate_rad_s"], float(np.max(abs(commands - oldcommands))) / dt
        )
        peaks["lift_dot_relative"] = max(peaks["lift_dot_relative"], lift_dot)
        peaks["drag_power_W_max"] = max(peaks["drag_power_W_max"], drag_power)
        if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
            reason = "nonfinite state"
        elif np.max(abs(alpha)) > np.deg2rad(params["alpha_domain_deg"][1]):
            reason = "effective fin alpha outside reused VLM domain"
        elif any(
            abs(data.qpos[j["q"]]) > params["joint_angle_limit_rad"] + 0.005
            for x in ids
            for j in x["joints"]
        ):
            reason = "joint angle outside declared domain"
        elif np.min(positions[:, 2]) <= params["water_stop_height_m"]:
            reason = "water interface reached; no water physics modeled"
        ending = reason != "duration reached"
        if step % stride == 0 or ending or step == round(duration / dt):
            energy = energies(model, data, ids, params)
            fishframes = []
            for i, x in enumerate(ids):
                fishframes.append(
                    {
                        "id": f"fish-{i:02d}",
                        "position_m": positions[i].tolist(),
                        "center_of_mass_world_m": data.subtree_com[x["body"]].tolist(),
                        "orientation_wxyz": data.qpos[x["q"] + 3 : x["q"] + 7].tolist(),
                        "linear_velocity_m_s": data.qvel[x["v"] : x["v"] + 3].tolist(),
                        "angular_velocity_body_rad_s": data.qvel[
                            x["v"] + 3 : x["v"] + 6
                        ].tolist(),
                        "fin_angle_rad": {
                            j["name"]: float(data.qpos[j["q"]]) for j in x["joints"]
                        },
                        "fin_command_rad": commands[i].tolist(),
                        "fin_actuator_torque_Nm": applied[i].tolist(),
                        "fin_angular_velocity_rad_s": previous_velocity[i].tolist(),
                        "fin_effective_alpha_rad": alpha[i].tolist(),
                        "force_model_valid": bool(
                            np.max(abs(alpha[i]))
                            <= np.deg2rad(params["alpha_domain_deg"][1])
                        ),
                        "fluid_force_world_N": force[i].tolist()
                        if np.max(abs(alpha[i]))
                        <= np.deg2rad(params["alpha_domain_deg"][1])
                        else None,
                        "force_world_N": (
                            force[i] + np.array([0, 0, -params["mass_kg"] * 9.81])
                        ).tolist()
                        if np.max(abs(alpha[i]))
                        <= np.deg2rad(params["alpha_domain_deg"][1])
                        else None,
                        "fluid_torque_about_body_origin_world_Nm": torque[i].tolist()
                        if np.max(abs(alpha[i]))
                        <= np.deg2rad(params["alpha_domain_deg"][1])
                        else None,
                        "torque_world_Nm": (
                            torque[i]
                            + sum(
                                (
                                    np.cross(
                                        data.xipos[bid] - positions[i],
                                        np.array([0, 0, -model.body_mass[bid] * 9.81]),
                                    )
                                    for bid in [x["body"]]
                                    + [j["body"] for j in x["joints"]]
                                ),
                                np.zeros(3),
                            )
                        ).tolist()
                        if np.max(abs(alpha[i]))
                        <= np.deg2rad(params["alpha_domain_deg"][1])
                        else None,
                        "actuator_positive_power_W": float(peakpower[i].sum()),
                        "positive_actuator_work_J": float(work[i]),
                        "signed_actuator_work_J": float(signedwork[i]),
                        "mechanical_energy_J": energy[i],
                        "escape_triggered": bool(triggered[i]),
                        "escape_scheduled_time_s": float(scheduled[i])
                        if np.isfinite(scheduled[i])
                        else None,
                        "active": not ending,
                        "termination_reason": reason if ending else None,
                    }
                )
            frames.append({"time_s": t, "fish": fishframes})
        if ending or step == round(duration / dt):
            break
        mujoco.mj_step(model, data)
        if abs(data.time - (t + dt)) > 1e-10:
            reason = "MuJoCo time reset/divergence"
            break
        after = np.asarray([[data.qvel[j["v"]] for j in x["joints"]] for x in ids])
        interval = applied * (previous_velocity + after) / 2 * dt
        signedwork += interval.sum(axis=1)
        work += np.maximum(interval, 0).sum(axis=1)
        fluid_work += drag_power * dt
        damping_loss += (
            params["fin_damping_Nm_s_rad"] * float(np.sum(previous_velocity**2)) * dt
        )
    quat_error = max(
        abs(np.linalg.norm(x["orientation_wxyz"]) - 1)
        for f in frames
        for x in f["fish"]
    )
    return {
        "schema": "frontier.ecology.trajectory/1",
        "case": case,
        "parameters": params,
        "dt_s": dt,
        "seed": seed if seed is not None else params["initial_seed"],
        "world_axes": "right-handed +X initial flight,+Y left,+Z up",
        "body_axes": "+X nose,+Y left,+Z dorsal",
        "orientation_order": "wxyz;body-to-world",
        "angular_velocity_frame": "body",
        "geometry": {
            "path": "artifacts/fish3d/fish3d-v3a-fan",
            "candidate_sha256": sha256(
                (GEOM / "candidate.json").read_bytes()
            ).hexdigest(),
            "panels_sha256": sha256((GEOM / "panels.json").read_bytes()).hexdigest(),
            "mesh_source_units": "m; biological component STLs, not print STLs",
            "mesh_m_to_body_m": "Rz(pi)*(component_STL_m-[cg_from_nose_m,0,0])",
            "cg_from_nose_m": geo["cg_from_nose_m"],
        },
        "assumptions": "Reduced quasisteady VLM-derived forces; no CFD, underwater propulsion, neural calibration, body/fin collision or wake coupling; assumed mass/CG/inertia/drag/control",
        "frames": frames,
        "summary": {
            "termination_reason": reason,
            "completed_duration": reason == "duration reached",
            "last_time_s": frames[-1]["time_s"],
            "max_quaternion_norm_error": quat_error,
            "peaks": peaks,
            "final_positive_work_J": work.tolist(),
            "fluid_work_J_total": fluid_work,
            "joint_damping_loss_J_total": damping_loss,
            "initial_mechanical_energy_J_total": initial_energy,
            "final_mechanical_energy_J_total": float(
                sum(energies(model, data, ids, params))
            ),
            "mechanical_energy_balance_residual_J": float(
                sum(energies(model, data, ids, params))
            )
            - initial_energy
            - float(signedwork.sum())
            - fluid_work
            + damping_loss,
            "triggered_count": int(triggered.sum()),
            "delays_s": delays.tolist(),
        },
        "model_xml": xml,
    }
