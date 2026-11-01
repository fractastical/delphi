"""Independently inspect immutable returned bytes and saved-state metric reproduction."""

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path

import mujoco
import numpy as np

from .batch import endpoint
from .model import ART, ROOT, build, dump, dynamics_forces, energies
from .run import paired_comparison


def strict(data):
    def reject(value):
        raise ValueError(f"nonfinite JSON constant {value}")

    return json.loads(data, parse_constant=reject)


def audit(collection, out, continuation=False):
    protocol = strict((ART / "return-audit-protocol.json").read_bytes())
    rtol = protocol["roundoff_tolerance_before_recomputation"]["relative"]
    atol = protocol["roundoff_tolerance_before_recomputation"]["absolute"]
    receipt = strict(collection.read_bytes())
    base = collection.parent
    science = base / "science"
    for item in receipt["artifacts"]:
        path = Path(item["local_path"])
        data = path.read_bytes()
        if len(data) != item["bytes"] or sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("collection file hash/size mismatch")
    summary = strict((science / "summary.json").read_bytes())
    cfg = strict((ART / "uncertainty-protocol.json").read_bytes())
    fixed = strict((ART / "protocol-refinement.json").read_bytes())
    context = summary
    continuation_cfg = None
    if continuation:
        from .continuation import selected_tasks

        continuation_cfg = selected_tasks()
        context = strict((ART / "uncertainty-initial/summary.json").read_bytes())
        if (
            summary["original_summary_sha256"]
            != continuation_cfg["original_summary_sha256"]
            or summary["continuation_protocol_sha256"]
            != sha256((ART / "continuation-protocol.json").read_bytes()).hexdigest()
        ):
            raise ValueError("Continuation parent/protocol pin mismatch")
    if (
        sha256((ART / "uncertainty-protocol.json").read_bytes()).hexdigest()
        != context["protocol_sha256"]
    ):
        raise ValueError("protocol pin mismatch")
    for path, digest in context["source_hashes"].items():
        if sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise ValueError("frozen core source changed")
    expected = {
        f"{setting['id']}-s{seed}-{'neighbors' if neighbors else 'ablated'}": {
            "id": f"{setting['id']}-s{seed}-{'neighbors' if neighbors else 'ablated'}",
            "setting": setting["id"],
            "overrides": setting["overrides"],
            "seed": seed,
            "neighbors": neighbors,
        }
        for setting in cfg["settings"]
        for seed in cfg["seeds"]
        for neighbors in cfg["neighbor_modes"]
    }
    if continuation:
        expected = {x["id"]: x for x in continuation_cfg["tasks"]}
    ids = [x["id"] for x in summary["results"]]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError("scenario identity/count mismatch")
    details = []
    missing = []
    recomputations = []
    force_checks = []
    total_frames = 0

    def compare(label, actual, stored):
        if isinstance(actual, (bool, str)) or actual is None:
            exact = actual == stored
            near = exact
            delta = 0 if exact else None
        else:
            exact = actual == stored
            near = bool(np.isclose(actual, stored, rtol=rtol, atol=atol))
            delta = float(abs(actual - stored))
        recomputations.append(
            {
                "field": label,
                "exact": bool(exact),
                "fixed_roundoff_match": bool(near),
                "absolute_difference": delta,
                "actual": actual,
                "stored": stored,
            }
        )

    for item in summary["results"]:
        if item["status"] != "computed":
            if item["status"] != "not-started: soft deadline reached":
                raise ValueError("unexpected noncomputed scenario")
            missing.append(expected[item["id"]])
            continue
        task = expected[item["id"]]
        if item["task"] != task:
            raise ValueError("task drift")
        params = dict(fixed["parameters"])
        params.update(task["overrides"])
        case = {
            "id": task["id"],
            "n": 8,
            "feedback": True,
            "neighbors": task["neighbors"],
        }
        digest = sha256(
            json.dumps(
                {"params": params, "case": case, "seed": task["seed"]},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        if digest != item["input_sha256"]:
            raise ValueError("input hash mismatch")
        traces = []
        for index, name in enumerate(["main.json.gz", "half-dt.json.gz"]):
            path = science / task["id"] / name
            data = path.read_bytes()
            raw = gzip.decompress(data)
            trace = item["traces"][index]
            if (
                sha256(data).hexdigest() != trace["sha256"]
                or len(data) != trace["bytes"]
                or sha256(raw).hexdigest() != trace["uncompressed_json_sha256"]
            ):
                raise ValueError("trace identity mismatch")
            xml = path.with_suffix(".xml").read_bytes()
            if sha256(xml).hexdigest() != trace["xml_sha256"]:
                raise ValueError("model XML changed")
            result = strict(raw)
            traces.append(result)
            if (
                result["case"] != case
                or result["parameters"] != params
                or result["seed"] != task["seed"]
                or result["dt_s"] != ([cfg["dt_s"], cfg["half_dt_s"]][index])
            ):
                raise ValueError("trajectory context mismatch")
            times = np.asarray([f["time_s"] for f in result["frames"]])
            positions = np.asarray(
                [[f["position_m"] for f in frame["fish"]] for frame in result["frames"]]
            )
            quats = np.asarray(
                [
                    [f["orientation_wxyz"] for f in frame["fish"]]
                    for frame in result["frames"]
                ]
            )
            if (
                not np.isfinite(positions).all()
                or not np.isfinite(quats).all()
                or np.max(abs(np.linalg.norm(quats, axis=-1) - 1)) > 1e-10
                or times[0] != 0
                or not np.all(np.diff(times) > 0)
            ):
                raise ValueError("state time/frame/finite gate")
            total_frames += len(times)
            m, d, g, fishids, _ = build(8, params, result["dt_s"])
            selected = sorted(
                set(range(0, len(times), 10))
                | {len(times) - 1}
                | {i for i, t in enumerate(times) if abs(t - 0.6) < 1e-7}
            )
            max_force = max_torque = max_energy = 0.0
            ok = True
            for frameid in selected:
                frame = result["frames"][frameid]
                for fish, ref in zip(frame["fish"], fishids, strict=True):
                    q, v = ref["q"], ref["v"]
                    d.qpos[q : q + 3] = fish["position_m"]
                    d.qpos[q + 3 : q + 7] = fish["orientation_wxyz"]
                    d.qvel[v : v + 3] = fish["linear_velocity_m_s"]
                    d.qvel[v + 3 : v + 6] = fish["angular_velocity_body_rad_s"]
                    for k, j in enumerate(ref["joints"]):
                        d.qpos[j["q"]] = fish["fin_angle_rad"][j["name"]]
                        d.qvel[j["v"]] = fish["fin_angular_velocity_rad_s"][k]
                d.qfrc_applied[:] = 0
                mujoco.mj_forward(m, d)
                force, torque, alpha, _, _ = dynamics_forces(m, d, g, fishids, params)
                energy = energies(m, d, fishids, params)
                for i, (fish, ref) in enumerate(
                    zip(frame["fish"], fishids, strict=True)
                ):
                    if fish["force_model_valid"]:
                        stored = np.asarray(fish["fluid_force_world_N"])
                        max_force = max(
                            max_force, float(np.max(abs(force[i] - stored)))
                        )
                        ok &= bool(np.allclose(force[i], stored, rtol=rtol, atol=atol))
                        gravity = sum(
                            (
                                np.cross(
                                    d.xipos[bid] - d.xpos[ref["body"]],
                                    np.array([0, 0, -m.body_mass[bid] * 9.81]),
                                )
                                for bid in [ref["body"]]
                                + [j["body"] for j in ref["joints"]]
                            ),
                            np.zeros(3),
                        )
                        total = torque[i] + gravity
                        stored = np.asarray(fish["torque_world_Nm"])
                        max_torque = max(max_torque, float(np.max(abs(total - stored))))
                        ok &= bool(np.allclose(total, stored, rtol=rtol, atol=atol))
                    elif (
                        fish["fluid_force_world_N"] is not None
                        or fish["force_world_N"] is not None
                    ):
                        raise ValueError("invalid model force not null")
                    max_energy = max(
                        max_energy, abs(energy[i] - fish["mechanical_energy_J"])
                    )
                    ok &= bool(
                        np.isclose(
                            energy[i], fish["mechanical_energy_J"], rtol=rtol, atol=atol
                        )
                    )
            force_checks.append(
                {
                    "id": task["id"],
                    "trace": name,
                    "sampled_frames": len(selected),
                    "fixed_roundoff_match": bool(ok),
                    "force_max_abs_N": max_force,
                    "torque_max_abs_Nm": max_torque,
                    "energy_max_abs_J": max_energy,
                }
            )
        current = endpoint(traces[0], cfg["endpoint_time_s"])
        for key in [
            "available",
            "response_count",
            "positive_work_J",
            "mean_lateral_displacement_m",
            "min_saved_center_separation_m",
        ]:
            compare(
                task["id"] + ".endpoint." + key, current[key], item["endpoint"][key]
            )
        discrepancy = paired_comparison(*traces)
        for key in [
            "paired_fish_states",
            "max_position_difference_m",
            "max_orientation_angle_rad",
            "same_termination_reason",
        ]:
            compare(
                task["id"] + ".discrepancy." + key,
                discrepancy[key],
                item["discrepancy"][key],
            )
        gate = (
            discrepancy["max_position_difference_m"] <= 0.01
            and discrepancy["max_orientation_angle_rad"] <= 0.03
        )
        if gate != item["numeric_gate_passed"]:
            raise ValueError("numeric gate boolean drift")
        peaks = traces[0]["summary"]["peaks"]
        act = {
            "torque": peaks["torque_Nm"] <= params["joint_torque_limit_Nm"] + 1e-12,
            "joint_power": peaks["positive_joint_power_W"]
            <= params["joint_positive_power_limit_W"] + 1e-12,
            "rate": peaks["joint_rate_rad_s"] <= params["actual_rate_gate_rad_s"],
            "command_rate": peaks["command_rate_rad_s"]
            <= params["command_rate_limit_rad_s"] + 1e-12,
            "work": max(traces[0]["summary"]["final_positive_work_J"])
            <= params["per_fish_positive_work_budget_J"]
            + params["work_budget_discrete_tolerance_J"],
        }
        if act != item["actuator_gates"]:
            raise ValueError(
                "Actuator gate booleans do not match saved peak/work metrics"
            )
        details.append(
            {
                "id": task["id"],
                "setting": task["setting"],
                "seed": task["seed"],
                "neighbors": task["neighbors"],
                "endpoint": current,
                "numeric_gate": gate,
                "actuator_gates": item["actuator_gates"],
                "last_time_s": traces[0]["summary"]["last_time_s"],
                "model_stop": traces[0]["summary"]["termination_reason"],
            }
        )
    result = {
        "schema": "frontier.ecology.return-audit/1",
        "collection_receipt_sha256": sha256(collection.read_bytes()).hexdigest(),
        "raw_source_summary_sha256": sha256(
            (science / "summary.json").read_bytes()
        ).hexdigest(),
        "source_partial_status": summary["status"],
        "collection_files_checked": len(receipt["artifacts"]),
        "collection_bytes_checked": sum(x["bytes"] for x in receipt["artifacts"]),
        "declared_scenarios": len(expected),
        "missing_only_continuation": continuation,
        "analysis_code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "computed_scenarios": len(details),
        "actual_main_half_simulations": 2 * len(details),
        "actual_saved_frames_checked": total_frames,
        "missing_tasks": missing,
        "source_identity_passed": True,
        "exact_metric_reproduction": all(x["exact"] for x in recomputations),
        "fixed_roundoff_metric_reproduction": all(
            x["fixed_roundoff_match"] for x in recomputations
        ),
        "fixed_roundoff_force_pose_replay": all(
            x["fixed_roundoff_match"] for x in force_checks
        ),
        "metric_checks": recomputations,
        "sampled_pose_force_checks": force_checks,
        "cases": details,
        "scope": "Same-model saved-pose integrity and fixed postprocessing reproduction. Not an independent biological experiment or new physical validation.",
    }
    dump(out, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--continuation", action="store_true")
    args = parser.parse_args()
    result = audit(args.collection, args.out, args.continuation)
    print(
        {
            k: v
            for k, v in result.items()
            if k not in ["metric_checks", "sampled_pose_force_checks", "cases"]
        }
    )
