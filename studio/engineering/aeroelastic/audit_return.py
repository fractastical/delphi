"""Frozen offline source/state reproduction; no new dynamics or biological validation."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np

from engineering.cfd3d import vlm
from engineering.simulation import glide
from engineering.simulation.schema import G
from .model import (
    ART,
    ROOT,
    check_inputs,
    deform,
    displaced,
    dump,
    protocol,
    setup,
    transfer,
)
from .run import validity


def read(path):
    def reject(value):
        raise ValueError("Nonfinite JSON " + value)

    return json.loads(path.read_bytes(), parse_constant=reject)


def audit(collection, out):
    frozen = read(ART / "return-audit-protocol.json")
    tol = frozen["fixed_roundoff_diagnostic"]
    p = protocol()
    check_inputs()
    transport = read(collection)
    science = collection.parent / "science"
    for ref in transport["artifacts"]:
        raw = Path(ref["local_path"]).read_bytes()
        if len(raw) != ref["bytes"] or sha256(raw).hexdigest() != ref["sha256"]:
            raise ValueError("Collection bytes changed")
    receipt = read(science / "receipt.json")
    if (
        receipt["protocol_sha256"]
        != sha256((ART / "protocol.json").read_bytes()).hexdigest()
    ):
        raise ValueError("Protocol changed")
    for name, digest in receipt["sources"].items():
        if sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Execution source changed " + name)
    for ref in receipt["files"]:
        raw = (science / ref["path"]).read_bytes()
        if len(raw) != ref["bytes"] or sha256(raw).hexdigest() != ref["sha256"]:
            raise ValueError("Native output changed")
    summary = read(science / "summary.json")
    expected = {
        f"chi{c}-u{u:g}-{mesh}-{arm}"
        for c in p["parameters"]["compliance_design_values"]
        for u in p["parameters"]["airspeeds_m_s"]
        for mesh in ["main", "fine"]
        for arm in p["parameters"]["arms"]
    }
    items = [x for context in summary["contexts"] for x in context["arms"]]
    ids = [x["id"] for x in items]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError("Declared arm identities changed/missing")
    checks = []
    force_samples = []
    states_checked = 0
    flight_states = 0
    native_gates = []

    def compare(label, actual, stored):
        a = np.asarray(actual)
        b = np.asarray(stored)
        if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
            raise ValueError("Nonfinite/shape metric " + label)
        checks.append(
            {
                "field": label,
                "exact": bool(np.array_equal(a, b)),
                "fixed_roundoff_match": bool(
                    np.allclose(a, b, rtol=tol["relative"], atol=tol["absolute"])
                ),
                "max_absolute_difference": float(np.max(abs(a - b))) if a.size else 0.0,
            }
        )

    for item in items:
        if "static_state_artifact" not in item:
            continue
        path = science / item["id"]
        statefile = path / "static-states.npz"
        raw = statefile.read_bytes()
        if sha256(raw).hexdigest() != item["static_state_artifact"]["sha256"]:
            raise ValueError("Static state changed")
        data = np.load(statefile, allow_pickle=False)
        grid = item["actual_lattice"]
        fins = setup(grid["span"], grid["chord"])
        iterations = item["iterations"]
        count = len(iterations)
        if any(not np.isfinite(data[key]).all() for key in data.files):
            raise ValueError("Nonfinite saved static field")
        if any(len(data[name + "__quads_m"]) != count for name in fins):
            raise ValueError("Frame count changed")
        final_lats = {}
        final_forces = []
        S = sum(fin["source"]["area_flat_m2"] for fin in fins.values())
        rho = p["parameters"]["rho_kg_m3"]
        speed = item["speed_m_s"]
        angle = np.deg2rad(p["parameters"]["alpha_deg"])
        lift = np.array([-np.sin(angle), 0, np.cos(angle)])
        for index, metric in enumerate(iterations):
            forces = []
            for name, fin in fins.items():
                load = data[name + "__shape_load_N"][index]
                EI = item["EI_Nm2"][name]
                lat = deform(fin, load, EI)
                for key, array in [
                    ("A", "lattice_A_m"),
                    ("B", "lattice_B_m"),
                    ("C", "lattice_C_m"),
                    ("N", "lattice_unit_normal"),
                ]:
                    compare(
                        item["id"] + f".{index}.{name}.{array}",
                        lat[key],
                        data[name + "__" + array][index],
                    )
                quads = displaced(fin, np.asarray(fin["source"]["quads_m"]), load, EI)
                compare(
                    item["id"] + f".{index}.{name}.quads",
                    quads,
                    data[name + "__quads_m"][index],
                )
                force = data[name + "__aero_force_N"][index]
                normal, ledger = transfer(fin, lat, force)
                compare(
                    item["id"] + f".{index}.{name}.normal_load",
                    normal,
                    data[name + "__aero_load_normal_N"][index],
                )
                for key in [
                    "force_relative_residual",
                    "moment_relative_residual",
                    "virtual_work_relative_residual",
                ]:
                    compare(
                        item["id"] + f".{index}.{name}.{key}",
                        ledger[key],
                        metric["transfer"][name][key],
                    )
                shape = validity(fin, load, EI)
                for key in [
                    "tip_over_L",
                    "max_slope_rad",
                    "max_sampled_deflection_over_span",
                ]:
                    compare(
                        item["id"] + f".{index}.{name}.{key}",
                        shape[key],
                        metric["shape_validity"][name][key],
                    )
                if (
                    shape["valid"] != metric["shape_validity"][name]["valid"]
                    or ledger["passed"] != metric["transfer"][name]["passed"]
                ):
                    raise ValueError("Native gate changed")
                forces.append(force)
                if index == count - 1:
                    final_lats[name] = lat
                    final_forces.append(force)
            total = np.vstack(forces).sum(axis=0)
            compare(
                item["id"] + f".{index}.CL",
                float(total @ lift / (0.5 * rho * speed**2 * S)),
                metric["CL_on_fixed_source_area"],
            )
            states_checked += 1
        if count:
            _, F, _, _ = vlm.solve(
                vlm.combine(final_lats), p["parameters"]["alpha_deg"]
            )
            actual = F * rho * speed**2
            stored = np.vstack(final_forces)
            compare(item["id"] + ".FINAL_pose_VLM_force_N", actual, stored)
            force_samples.append(item["id"])
        if item["flight"]:
            flight = item["flight"]
            ranges = []
            for label in ["main", "half"]:
                series = np.load(path / f"glide-{label}.npz", allow_pickle=False)
                t = series["time_s"]
                st = series["state_x_h_V_gamma"]
                meta = flight[label]
                if (
                    not np.isfinite(st).all()
                    or t[0] != 0
                    or not np.all(np.diff(t) > 0)
                    or len(t) != meta["actual_integrated_saved_states"]
                ):
                    raise ValueError("Glide state/time identity invalid")
                mass = p["glide"]["mass_kg"]
                energy = 0.5 * mass * st[:, 2] ** 2 + mass * G * st[:, 1]
                cd = glide.drag_coeff(
                    meta["CL_fixed"],
                    p["glide"]["CD0"],
                    p["glide"]["oswald_e"],
                    meta["AR"],
                )
                power = -0.5 * rho * st[:, 2] ** 3 * meta["reference_area_m2"] * cd
                compare(
                    item["id"] + f".glide-{label}.energy_J",
                    energy,
                    series["mechanical_energy_J"],
                )
                compare(
                    item["id"] + f".glide-{label}.drag_power_W",
                    power,
                    series["drag_power_W"],
                )
                flight_states += len(t)
                ranges.append(meta["range_m"])
            ratio = abs(ranges[0] - ranges[1]) / max(abs(ranges[1]), 1e-12)
            compare(
                item["id"] + ".glide_dt_range_ratio",
                ratio,
                flight["range_relative_difference"],
            )
            if (ratio <= p["glide"]["range_relative_discrepancy_max"]) != flight[
                "dt_gate_passed"
            ]:
                raise ValueError("Glide dt gate changed")
            native_gates.append(
                {"id": item["id"], "glide_dt_gate": flight["dt_gate_passed"]}
            )
    result = {
        "schema": "frontier.aeroelastic.return-audit/1",
        "collection_sha256": sha256(collection.read_bytes()).hexdigest(),
        "summary_sha256": sha256((science / "summary.json").read_bytes()).hexdigest(),
        "receipt_sha256": sha256((science / "receipt.json").read_bytes()).hexdigest(),
        "source_identity_passed": True,
        "collection_files_checked": len(transport["artifacts"]),
        "collection_bytes_checked": sum(x["bytes"] for x in transport["artifacts"]),
        "declared_identities": len(expected),
        "returned_identities": len(ids),
        "actual_static_frames_checked": states_checked,
        "actual_glide_states_checked": flight_states,
        "final_pose_VLM_force_samples": force_samples,
        "native_execution_status": summary["execution_status"],
        "native_statuses": {item["id"]: item["status"] for item in items},
        "checks": checks,
        "exact_reproduction": all(x["exact"] for x in checks),
        "fixed_roundoff_reproduction": all(x["fixed_roundoff_match"] for x in checks),
        "max_absolute_difference_across_different_units": max(
            (x["max_absolute_difference"] for x in checks), default=0
        ),
        "native_glide_gates": native_gates,
        "audit_protocol_sha256": sha256(
            (ART / "return-audit-protocol.json").read_bytes()
        ).hexdigest(),
        "analysis_code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "Same-author saved-state/metric reproduction, final-pose steadyforce samples and exactbyte integrity. No new dynamics, independent biological experiment or empirical validation. Exact mismatch stays distinct from fixed-roundoff diagnostic.",
    }
    dump(out, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.collection, args.out)
    print(
        {
            k: v
            for k, v in result.items()
            if k
            not in [
                "checks",
                "native_statuses",
                "native_glide_gates",
                "final_pose_VLM_force_samples",
            ]
        }
    )
    raise SystemExit(0 if result["fixed_roundoff_reproduction"] else 1)
