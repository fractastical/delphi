"""Frozen rigid/frozen-load/two-way static coupling; separate rigidized glide."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import multiprocessing
from pathlib import Path
import platform
import time

import numpy as np
import scipy

from engineering.cfd3d import vlm
from engineering.fin_mechanics import beam
from .controls import run as controls
from .flight import trajectory
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


def validity(fin, forces, EI):
    locations = np.unique(
        np.r_[np.linspace(0, fin["length"], 513), fin["response"].stations]
    )
    w, s = fin["response"].evaluate(locations, forces, EI)
    g = protocol()["gates"]
    result = beam.check_small_deformation(
        float(w[-1]),
        float(max(abs(s))),
        fin["length"],
        g["small_deflection_tip_over_span_max"],
        g["small_slope_max_rad"],
    )
    result["max_sampled_deflection_over_span"] = float(max(abs(w)) / fin["length"])
    result["valid"] &= (
        result["max_sampled_deflection_over_span"]
        <= g["small_deflection_tip_over_span_max"]
    )
    return result


def solve_arm(compliance, speed, mesh, arm, directory, deadline, grid_override=None):
    p = protocol()
    g = p["gates"]
    params = p["parameters"]
    grid = params["meshes"][mesh] if grid_override is None else grid_override
    fins = setup(grid["span"], grid["chord"])
    rho = params["rho_kg_m3"]
    alpha = params["alpha_deg"]
    EI = {
        name: params["EI_inputs"][name]["EI_Nm2_by_compliance"][str(compliance)]
        for name in fins
    }
    current = {
        name: np.zeros(len(fin["lattice"]["area"])) for name, fin in fins.items()
    }
    area = float(sum(fin["source"]["area_flat_m2"] for fin in fins.values()))
    lift_direction = np.array(
        [-np.sin(np.deg2rad(alpha)), 0, np.cos(np.deg2rad(alpha))]
    )
    histories = []
    arrays = {}
    previous_CL = None
    status = "unconverged: iteration budget"
    final = None
    max_iterations = (
        1
        if arm == "rigid"
        else 2
        if arm == "one-way-frozen-load"
        else params["maximum_iterations"]
    )
    for iteration in range(max_iterations):
        if time.monotonic() > deadline:
            status = "partial: deadline"
            break
        checks = {
            name: validity(fin, current[name], EI[name]) for name, fin in fins.items()
        }
        if not all(x["valid"] for x in checks.values()):
            status = "model-domain exit: linear beam"
            break
        lattices = {
            name: deform(fin, current[name], EI[name]) for name, fin in fins.items()
        }
        combined = vlm.combine(lattices)
        _, unitF, _, _ = vlm.solve(combined, alpha)
        physical = unitF * rho * speed**2
        if not np.isfinite(physical).all():
            status = "failed: nonfinite force"
            break
        target = {}
        ledgers = {}
        offset = 0
        residual = 0
        allquads = []
        for name, fin in fins.items():
            size = len(fin["lattice"]["area"])
            force = physical[offset : offset + size]
            offset += size
            target[name], ledgers[name] = transfer(fin, lattices[name], force)
            x = np.linspace(0, fin["length"], 129)
            old, _ = fin["response"].evaluate(x, current[name], EI[name])
            new, _ = fin["response"].evaluate(x, target[name], EI[name])
            residual = max(residual, float(max(abs(old - new)) / fin["length"]))
            sourcequad = np.asarray(fin["source"]["quads_m"])
            quads = displaced(fin, sourcequad, current[name], EI[name])
            allquads.append(quads)
            values = {
                "shape_load_N": current[name],
                "aero_load_normal_N": target[name],
                "aero_force_N": force,
                "quads_m": quads,
                "lattice_A_m": lattices[name]["A"],
                "lattice_B_m": lattices[name]["B"],
                "lattice_C_m": lattices[name]["C"],
                "lattice_unit_normal": lattices[name]["N"],
            }
            for key, value in values.items():
                arrays.setdefault(name + "__" + key, []).append(
                    np.asarray(value).copy()
                )
        CL = float(
            physical.sum(axis=0) @ lift_direction / (0.5 * rho * speed**2 * area)
        )
        delta = None if previous_CL is None else abs(CL - previous_CL)
        metric = {
            "iteration": iteration,
            "iteration_is_NOT_physical_time": True,
            "CL_on_fixed_source_area": CL,
            "total_force_N": physical.sum(axis=0).tolist(),
            "shape_residual_over_span": residual,
            "CL_change": delta,
            "shape_validity": checks,
            "transfer": ledgers,
        }
        histories.append(metric)
        if not all(x["passed"] for x in ledgers.values()):
            status = "failed: conservative transfer"
            break
        final = {
            "CL": CL,
            "quads": allquads,
            "shape_load": {name: value.copy() for name, value in current.items()},
            "validity": checks,
        }
        if arm == "rigid":
            status = "computed rigid"
            break
        if arm == "one-way-frozen-load" and iteration == 1:
            status = "computed one-way"
            break
        if (
            arm == "two-way-static-feedback"
            and delta is not None
            and residual <= g["fixed_point_shape_change_over_span_max"]
            and delta <= g["fixed_point_CL_absolute_change_max"]
        ):
            status = "converged static feedback"
            break
        proposed = {
            name: validity(fin, target[name], EI[name]) for name, fin in fins.items()
        }
        if not all(x["valid"] for x in proposed.values()):
            status = "model-domain exit: proposed linear-beam shape"
            metric["rejected_proposed_shape"] = proposed
            break
        for name in current:
            current[name] = (
                target[name]
                if arm == "one-way-frozen-load"
                else (1 - params["underrelaxation"]) * current[name]
                + params["underrelaxation"] * target[name]
            )
        previous_CL = CL
    directory.mkdir(parents=True, exist_ok=True)
    statefile = directory / "static-states.npz"
    np.savez_compressed(
        statefile, **{key: np.asarray(value) for key, value in arrays.items()}
    )
    valid = status in [
        "computed rigid",
        "computed one-way",
        "converged static feedback",
    ]
    result = {
        "schema": "frontier.aeroelastic.arm/1",
        "compliance": compliance,
        "speed_m_s": speed,
        "mesh": mesh,
        "actual_lattice": grid,
        "local_control_not_production_arm": grid_override is not None,
        "arm": arm,
        "status": status,
        "valid_for_declared_transfer": valid,
        "EI_Nm2": EI,
        "iterations": histories,
        "static_state_artifact": {
            "path": str(statefile),
            "sha256": sha256(statefile.read_bytes()).hexdigest(),
            "bytes": statefile.stat().st_size,
        },
        "flight": None,
        "biological_success_probability": None,
    }
    if valid and final is not None:
        outline = []
        for name, fin in fins.items():
            outline.append(
                displaced(
                    fin,
                    np.asarray(fin["source"]["outline_m"]),
                    final["shape_load"][name],
                    EI[name],
                )
            )
        wingspan = float(np.ptp(np.vstack(outline)[:, 1]))
        AR = wingspan**2 / area
        flights = []
        for label, dt in [
            ("main", p["glide"]["dt_s"]),
            ("half", p["glide"]["half_dt_s"]),
        ]:
            series, metrics = trajectory(final["CL"], area, AR, speed, dt)
            path = directory / f"glide-{label}.npz"
            np.savez_compressed(path, **series)
            flights.append(
                {
                    **metrics,
                    "artifact": {
                        "path": str(path),
                        "sha256": sha256(path.read_bytes()).hexdigest(),
                        "bytes": path.stat().st_size,
                    },
                }
            )
        relative = abs(flights[0]["range_m"] - flights[1]["range_m"]) / max(
            abs(flights[1]["range_m"]), 1e-12
        )
        result["flight"] = {
            "main": flights[0],
            "half": flights[1],
            "range_relative_difference": relative,
            "dt_gate_passed": relative <= p["glide"]["range_relative_discrepancy_max"],
            "scope": p["glide"]["scope"],
        }
    dump(directory / "result.json", result)
    return result


def context(payload):
    compliance, speed, out, deadline = payload
    out = Path(out)
    results = []
    for mesh in ["main", "fine"]:
        for arm in protocol()["parameters"]["arms"]:
            name = f"chi{compliance}-u{speed:g}-{mesh}-{arm}"
            if time.monotonic() > deadline:
                results.append(
                    {
                        "id": name,
                        "status": "not-started: deadline",
                        "valid_for_declared_transfer": False,
                    }
                )
                continue
            try:
                result = solve_arm(compliance, speed, mesh, arm, out / name, deadline)
            except Exception as exc:
                result = {
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "valid_for_declared_transfer": False,
                }
                dump(out / name / "failure.json", result)
            result["id"] = name
            results.append(result)
            dump(out / "progress" / f"chi{compliance}-u{speed:g}.json", results)
    paired = []
    for arm in protocol()["parameters"]["arms"]:
        good = [
            x
            for x in results
            if x.get("arm") == arm and x["valid_for_declared_transfer"]
        ]
        row = {
            "compliance": compliance,
            "speed_m_s": speed,
            "arm": arm,
            "eligible": len(good) == 2,
            "lattice_gate_passed": False,
        }
        if len(good) == 2:
            a, b = [next(x for x in good if x["mesh"] == m) for m in ["main", "fine"]]
            ca, cb = [x["iterations"][-1]["CL_on_fixed_source_area"] for x in [a, b]]
            cdelta = abs(ca - cb) / max(abs(cb), 1e-12)
            tip = max(
                abs(
                    a["iterations"][-1]["shape_validity"][name]["tip_over_L"]
                    - b["iterations"][-1]["shape_validity"][name]["tip_over_L"]
                )
                for name in protocol()["geometry"]["fins"]
            )
            row.update(
                CL_relative_difference=cdelta,
                tip_difference_over_span=tip,
                lattice_gate_passed=cdelta
                <= protocol()["gates"]["lattice_CL_relative_change_max"]
                and tip <= protocol()["gates"]["lattice_tip_difference_over_span_max"],
            )
        paired.append(row)
    return {
        "compliance": compliance,
        "speed_m_s": speed,
        "arms": results,
        "paired_refinement": paired,
    }


def run(out):
    if out.exists():
        raise ValueError("Fresh output directory required")
    out = out.resolve()
    out.mkdir(parents=True)
    p = protocol()
    started = time.monotonic()
    failure = None
    results = []
    try:
        if np.__version__ != "2.5.4" or scipy.__version__ != "1.17.1":
            raise ValueError("Exact frozen NumPy/SciPy pins required")
        check_inputs()
        check = controls(out / "controls.json")
        if not check["passed"]:
            raise RuntimeError("Frozen numerical controls failed")
        deadline = started + p["resources"]["soft_no_new_work_seconds"]
        tasks = [
            (c, u, str(out), deadline)
            for c in p["parameters"]["compliance_design_values"]
            for u in p["parameters"]["airspeeds_m_s"]
        ]
        with ProcessPoolExecutor(
            max_workers=2, mp_context=multiprocessing.get_context("spawn")
        ) as pool:
            for item in as_completed([pool.submit(context, task) for task in tasks]):
                results.append(item.result())
                dump(out / "progress.json", results)
        arms = [x for r in results for x in r["arms"]]
        summary = {
            "schema": "frontier.aeroelastic.results/1",
            "execution_status": "all declared arms returned"
            if len(arms) == 36
            else "partial",
            "declared_arms": 36,
            "returned_arms": len(arms),
            "not_started_arms": sum(
                x["status"].startswith("not-started") for x in arms
            ),
            "partial_arms": sum(x["status"].startswith("partial") for x in arms),
            "failed_arms": sum(x["status"].startswith("failed") for x in arms),
            "model_domain_exits": sum(
                x["status"].startswith("model-domain") for x in arms
            ),
            "unconverged_arms": sum(
                x["status"].startswith("unconverged") for x in arms
            ),
            "valid_transfer_arms": sum(x["valid_for_declared_transfer"] for x in arms),
            "contexts": results,
            "scope": p["question"],
            "biological_success_probability": None,
        }
        dump(out / "summary.json", summary)
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        dump(out / "failure.json", {"error": failure, "contexts": results})
    files = [
        path
        for path in out.rglob("*")
        if path.is_file() and path.name != "receipt.json"
    ]
    sources = [
        *Path(__file__).parent.glob("*.py"),
        ROOT / "engineering/fin_mechanics/beam.py",
        ROOT / "engineering/cfd3d/vlm.py",
        ROOT / "engineering/cfd3d/gates_vlm.json",
        ROOT / "engineering/simulation/glide.py",
        ROOT / "engineering/simulation/schema.py",
    ]
    receipt = {
        "schema": "frontier.aeroelastic.receipt/1",
        "protocol_sha256": sha256((ART / "protocol.json").read_bytes()).hexdigest(),
        "sources": {
            str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
            for path in sources
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "device": "CPU",
        },
        "wall_seconds": time.monotonic() - started,
        "failure": failure,
        "files": [
            {
                "path": str(path.relative_to(out)),
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
            for path in files
        ],
        "dollars": None,
    }
    receipt["output_bytes"] = sum(x["bytes"] for x in receipt["files"])
    receipt["output_cap_exceeded"] = (
        receipt["output_bytes"] > p["resources"]["output_cap_bytes"]
    )
    dump(out / "receipt.json", receipt)
    print(
        {
            "failure": failure,
            "contexts_returned": len(results),
            "bytes": receipt["output_bytes"],
            "wall_seconds": receipt["wall_seconds"],
        },
        flush=True,
    )
    incomplete = any(
        x["status"].startswith(("not-started", "partial"))
        for context_result in results
        for x in context_result["arms"]
    )
    return (
        1
        if failure or receipt["output_cap_exceeded"] or len(results) != 6 or incomplete
        else 0
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.out))
