"""Run frozen controls and paired bounded airborne experiments."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import resource
import subprocess
import time

import mujoco
import numpy as np

from .model import ART, FLIP, ROOT, aero, build, dump, protocol, simulate


def controls():
    p = protocol()
    params = p["parameters"]
    dt = p["solver"]["dt_s"]
    m, d, _, ids, _ = build(1, params, dt)
    q, v = ids[0]["q"], ids[0]["v"]
    start = d.qpos[q : q + 3].copy()
    velocity = d.qvel[v : v + 3].copy()
    for _ in range(round(1 / dt)):
        mujoco.mj_step(m, d)
    exact = start + velocity * d.time + np.array([0, 0, -4.905 * d.time * d.time])
    position_error = float(np.max(abs(d.qpos[q : q + 3] - exact)))
    velocity_error = float(
        np.max(abs(d.qvel[v : v + 3] - (velocity + np.array([0, 0, -9.81 * d.time]))))
    )
    m.opt.gravity[:] = 0
    mujoco.mj_forward(m, d)
    mujoco.mj_energyVel(m, d)
    before = float(d.energy[1])
    drag_work = 0.0
    for _ in range(100):
        vel = d.qvel[v : v + 3].copy()
        force = -0.02 * vel * np.linalg.norm(vel)
        d.qfrc_applied[:] = 0
        mujoco.mj_applyFT(
            m,
            d,
            force,
            np.zeros(3),
            d.xipos[ids[0]["body"]],
            ids[0]["body"],
            d.qfrc_applied,
        )
        drag_work += float(np.dot(force, vel)) * dt
        mujoco.mj_step(m, d)
    mujoco.mj_forward(m, d)
    mujoco.mj_energyVel(m, d)
    after = float(d.energy[1])
    rng = np.random.default_rng(1101)
    dots = []
    dragpowers = []
    for _ in range(30):
        vv = rng.normal(size=3) * 10
        normal = rng.normal(size=3)
        normal /= np.linalg.norm(normal)
        lift, drag = aero(vv, normal, 0.005, 0.5, 0.08, 1.204)
        dots.append(
            abs(float(np.dot(lift, vv)))
            / max(np.linalg.norm(lift) * np.linalg.norm(vv), 1e-12)
        )
        dragpowers.append(float(np.dot(drag, vv)))
    m2, d2, _, ids2, _ = build(1, params, dt)
    ii = ids2[0]
    d2.qpos[ii["q"] + 3 : ii["q"] + 7] = [np.sqrt(0.5), 0, 0, np.sqrt(0.5)]
    mujoco.mj_forward(m2, d2)
    f = np.array([1.0, 2.0, 3.0])
    tau = np.array([0.1, 0.2, 0.3])
    general = np.zeros(m2.nv)
    mujoco.mj_applyFT(m2, d2, f, tau, d2.xpos[ii["body"]], ii["body"], general)
    rot = d2.xmat[ii["body"]].reshape(3, 3)
    # Force point equals free body origin; no lever-arm torque in this oracle.
    frame_error = float(
        max(
            np.max(abs(general[ii["v"] : ii["v"] + 3] - f)),
            np.max(abs(general[ii["v"] + 3 : ii["v"] + 6] - rot.T @ tau)),
        )
    )
    checks = {
        "ballistic_position": position_error
        <= p["controls"]["ballistic_position_max_error_m"],
        "ballistic_velocity": velocity_error
        <= p["controls"]["ballistic_velocity_max_error_m_s"],
        "drag_energy_loss": after < before and drag_work < 0,
        "lift_orthogonal": max(dots)
        <= p["controls"]["lift_velocity_dot_relative_tolerance"],
        "drag_work_nonpositive": max(dragpowers) <= 1e-12,
        "wrong_sign_drag_mutation_rejected": min([-x for x in dragpowers]) > 0,
        "right_handed_mesh_transform": bool(
            np.allclose(np.cross(FLIP[:, 0], FLIP[:, 1]), FLIP[:, 2])
            and np.linalg.det(FLIP) > 0
        ),
        "world_force_body_torque_frame": frame_error < 1e-12,
    }
    return {
        "schema": "frontier.ecology.controls/1",
        "checks": checks,
        "passed": all(checks.values()),
        "ballistic_position_error_m": position_error,
        "ballistic_velocity_error_m_s": velocity_error,
        "drag_kinetic_energy_before_J": before,
        "drag_kinetic_energy_after_J": after,
        "drag_work_J": drag_work,
        "max_lift_velocity_dot_relative": max(dots),
        "max_drag_power_W": max(dragpowers),
        "frame_generalized_force_error": frame_error,
        "scope": "Analytic/numerical controls only, no empirical fish validation",
    }


def save_case(out, result):
    out.mkdir(parents=True)
    xml = result.pop("model_xml")
    (out / "model.xml").write_text(xml)
    result["model_xml_sha256"] = sha256(xml.encode()).hexdigest()
    dump(out / "trajectory.json", result)
    frames = result["frames"]
    np.savez_compressed(
        out / "states.npz",
        time_s=np.array([f["time_s"] for f in frames]),
        position_m=np.array([[x["position_m"] for x in f["fish"]] for f in frames]),
        orientation_wxyz=np.array(
            [[x["orientation_wxyz"] for x in f["fish"]] for f in frames]
        ),
        velocity_m_s=np.array(
            [[x["linear_velocity_m_s"] for x in f["fish"]] for f in frames]
        ),
        fin_angle_rad=np.array(
            [[list(x["fin_angle_rad"].values()) for x in f["fish"]] for f in frames]
        ),
    )


def paired_comparison(a, b):
    matches = []
    index = {round(f["time_s"], 8): f for f in b["frames"]}
    for frame in a["frames"]:
        other = index.get(round(frame["time_s"], 8))
        if other:
            for x, y in zip(frame["fish"], other["fish"], strict=True):
                position = np.linalg.norm(np.array(x["position_m"]) - y["position_m"])
                dot = min(
                    1.0,
                    abs(float(np.dot(x["orientation_wxyz"], y["orientation_wxyz"]))),
                )
                matches.append((position, 2 * np.arccos(dot)))
    return {
        "paired_fish_states": len(matches),
        "max_position_difference_m": float(max(x[0] for x in matches)),
        "max_orientation_angle_rad": float(max(x[1] for x in matches)),
        "same_termination_reason": a["summary"]["termination_reason"]
        == b["summary"]["termination_reason"],
        "scope": "Comparison only at actual common saved times; incomplete cases remain incomplete.",
    }


def run(out):
    if out.exists():
        raise ValueError("output exists; refuse overwrite")
    p = protocol()
    out.mkdir(parents=True)
    started = time.monotonic()
    cpu = time.process_time()
    result = controls()
    dump(out / "controls.json", result)
    if not result["passed"]:
        raise RuntimeError("Frozen controls failed; no production run")
    summary = {}
    for case in p["cases"]:
        main = simulate(case, deepcopy(p["parameters"]))
        fine = simulate(case, deepcopy(p["parameters"]), p["solver"]["refined_dt_s"])
        comparison = paired_comparison(main, fine)
        comparison["passes_frozen_discrepancy_bounds"] = (
            comparison["max_position_difference_m"]
            <= p["controls"]["dt_half_position_max_error_m"]
            and comparison["max_orientation_angle_rad"]
            <= p["controls"]["dt_half_orientation_max_angle_rad"]
        )
        summary[case["id"]] = {
            "main": main["summary"],
            "half_dt": fine["summary"],
            "discrepancy": comparison,
        }
        peaks = main["summary"]["peaks"]
        summary[case["id"]]["actuator_checks"] = {
            "torque": peaks["torque_Nm"]
            <= p["parameters"]["joint_torque_limit_Nm"] + 1e-12,
            "positive_joint_power": peaks["positive_joint_power_W"]
            <= p["parameters"]["joint_positive_power_limit_W"] + 1e-12,
            "actual_rate": peaks["joint_rate_rad_s"]
            <= p["parameters"]["actual_rate_gate_rad_s"],
            "command_rate": peaks["command_rate_rad_s"]
            <= p["parameters"]["command_rate_limit_rad_s"] + 1e-12,
            "positive_work": max(main["summary"]["final_positive_work_J"])
            <= p["parameters"]["per_fish_positive_work_budget_J"]
            + p["parameters"]["work_budget_discrete_tolerance_J"],
        }
        if case["id"] == "glide-feedback":
            replay = simulate(case, deepcopy(p["parameters"]))
            check = paired_comparison(main, replay)
            summary[case["id"]]["deterministic_replay"] = check
        save_case(out / case["id"], main)
        save_case(out / (case["id"] + "-dt-half"), fine)
        dump(out / "summary.json", summary)
        print(case["id"], json.dumps(summary[case["id"]]), flush=True)
    files = [x for x in out.rglob("*") if x.is_file()]
    receipt = {
        "schema": "frontier.ecology.simulation-receipt/1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": sha256((ART / "protocol.json").read_bytes()).hexdigest(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_hashes": {
            str(x.relative_to(ROOT)): sha256(x.read_bytes()).hexdigest()
            for x in (ROOT / "engineering/ecology").glob("*.py")
        },
        "environment": {
            "python": platform.python_version(),
            **{
                x: importlib.metadata.version(x)
                for x in ["mujoco", "numpy", "trimesh", "matplotlib"]
            },
        },
        "wall_seconds": time.monotonic() - started,
        "process_cpu_seconds": time.process_time() - cpu,
        "max_rss_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "dollars": None,
        "files": [
            {
                "path": str(x.relative_to(ROOT)),
                "sha256": sha256(x.read_bytes()).hexdigest(),
                "bytes": x.stat().st_size,
            }
            for x in files
        ],
    }
    dump(out / "receipt.json", receipt)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ART / "run")
    args = parser.parse_args()
    run(args.out)
