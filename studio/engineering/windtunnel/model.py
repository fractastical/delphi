"""Bounded geometry-linked 2D LBM flow; physical mapping is a declared low-Re proxy."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import time
from pathlib import Path

import numpy as np
import torch

from .geometry import MESHES, ROOT, file_sha, mask_from_mesh
from .lbm import LBM

PROTOCOL = Path(__file__).with_name("protocol.json")
NOT_ESTABLISHED = json.loads(PROTOCOL.read_text())["not_established"]


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def request_parameters(request):
    protocol = json.loads(PROTOCOL.read_text())
    base = dict(protocol["baseline"])
    if not isinstance(request, dict) or set(request) - set(base):
        raise ValueError("unknown request fields")
    base.update(request)
    limits = protocol["request_limits"]
    if base["mesh_id"] not in MESHES:
        raise ValueError("unsupported mesh_id")
    for key, value in base.items():
        if key == "mesh_id":
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"{key} must be finite numeric")
        allowed = limits[key]
        if key in ("length_cells", "lattice_speed"):
            if value not in allowed:
                raise ValueError(f"unsupported {key}")
        elif not allowed[0] <= value <= allowed[1]:
            raise ValueError(f"{key} outside protocol bounds")
    if type(base["length_cells"]) is not int or type(base["frames"]) is not int:
        raise ValueError("length_cells and frames must be integers")
    reynolds = (
        base["speed_m_s"] * base["body_length_m"] / base["kinematic_viscosity_m2_s"]
    )
    if not limits["reynolds"][0] <= reynolds <= limits["reynolds"][1]:
        raise ValueError("Reynolds number outside supported low-Re proxy domain")
    return base, reynolds


def no_body_control():
    engine = LBM(48, 24, 0.8)
    engine.set_open(0.04)
    engine.init(1.0, 0.04, 0.0)
    forces = []
    for _ in range(100):
        fx, fy = engine.step(want_force=True)
        forces.extend([abs(float(fx)), abs(float(fy))])
    rho, ux, uy = engine.macro()
    result = {
        "max_density_error": float((rho - 1).abs().max()),
        "max_velocity_error": max(
            float((ux - 0.04).abs().max()), float(uy.abs().max())
        ),
        "max_force": max(forces),
    }
    result["passed"] = all(v < 1e-12 for v in result.values())
    return result


def run_request(
    request,
    output_directory,
    *,
    device="cpu",
    analytic_receipt=None,
    mask_override=None,
):
    p, reynolds = request_parameters(request)
    if device not in ("cpu", "cuda") or (
        device == "cuda" and not torch.cuda.is_available()
    ):
        raise ValueError("requested device unavailable")
    if analytic_receipt is None or not analytic_receipt.get("all_pass"):
        raise ValueError("passing original analytic-control receipt required")
    torch.set_num_threads(2)
    started = time.perf_counter()
    protocol = json.loads(PROTOCOL.read_text())
    c, speed = p["length_cells"], p["lattice_speed"]
    mask, geometry = (
        mask_from_mesh(p["mesh_id"], c, p["aoa_deg"], p["thickness_scale"])
        if mask_override is None
        else mask_override
    )
    tau = 0.5 + 3 * speed * c / reynolds
    engine = LBM(12 * c, 6 * c, tau, solid=torch.from_numpy(mask), device=device)
    engine.set_open(speed)
    engine.init(1.0, speed, 0.0)
    engine.f = torch.where(
        engine.solid[None], engine.w.expand(9, 12 * c, 6 * c), engine.f
    )
    steps_exact = p["convective_time"] * c / speed
    steps = round(steps_exact)
    if abs(steps_exact - steps) > 1e-8 or steps > 60000:
        raise ValueError("choose an exactly representable bounded convective end time")
    dx = p["body_length_m"] / c
    dt = speed * dx / p["speed_m_s"]
    schedule = set(np.rint(np.linspace(0, steps, p["frames"])).astype(int))
    force_cadence = max(1, round(20 * (c / 24) * (0.04 / speed)))
    # Save exact sampled nodes in a bounded central ROI, not interpolated fields.
    xi = np.arange(round(1.5 * c), round(8 * c), max(1, math.ceil(6.5 * c / 192)))
    yi = np.arange(round(1.5 * c), round(4.5 * c), max(1, math.ceil(3 * c / 96)))
    frames, history, failed, max_mach, max_density = [], [], None, 0.0, 0.0
    for step in range(steps + 1):
        if step % 20 == 0 or step in schedule:
            rho, ux, uy = engine.macro()
            mach = float(
                torch.sqrt(ux[engine.fluid] ** 2 + uy[engine.fluid] ** 2).max()
            ) * math.sqrt(3)
            density_deviation = float((rho[engine.fluid] - 1).abs().max())
            max_mach, max_density = (
                max(max_mach, mach),
                max(max_density, density_deviation),
            )
            if (
                not torch.isfinite(engine.f).all()
                or mach > 0.3
                or density_deviation > 0.1
            ):
                failed = (
                    "nonfinite or predeclared Mach/density stability bound exceeded"
                )
                break
            if step in schedule:
                arrays = [a.detach().cpu().numpy() for a in (rho, ux, uy)]
                state_hash = hashlib.sha256(
                    b"".join(a.tobytes() for a in arrays)
                ).hexdigest()
                frames.append(
                    {
                        "step": step,
                        "t_s": step * dt,
                        "convective_time": step * speed / c,
                        "full_field_sha256": state_hash,
                        "rho": arrays[0][np.ix_(xi, yi)].astype(np.float32),
                        "ux": arrays[1][np.ix_(xi, yi)].astype(np.float32),
                        "uy": arrays[2][np.ix_(xi, yi)].astype(np.float32),
                    }
                )
        if step == steps:
            break
        sample_force = (step + 1) % force_cadence == 0 or step == steps - 1
        force = engine.step(want_force=sample_force)
        if sample_force:
            fx, fy = (float(a) for a in force)
            coefficient_scale = 0.5 * speed**2 * c
            rho, ux, uy = engine.macro()
            flux_in = float((rho[1, 1:-1] * ux[1, 1:-1]).sum())
            flux_out = float((rho[-2, 1:-1] * ux[-2, 1:-1]).sum())
            cd, cl = fx / coefficient_scale, fy / coefficient_scale
            physical_scale = (
                0.5 * p["density_kg_m3"] * p["speed_m_s"] ** 2 * p["body_length_m"]
            )
            history.append(
                {
                    "step": step + 1,
                    "t_s": (step + 1) * dt,
                    "convective_time": (step + 1) * speed / c,
                    "Cd": cd,
                    "Cl": cl,
                    "drag_N_per_m_span": cd * physical_scale,
                    "lift_N_per_m_span": cl * physical_scale,
                    "flux_in_lattice": flux_in,
                    "flux_out_lattice": flux_out,
                }
            )
        if time.perf_counter() - started > 500:
            failed = "runtime budget exceeded; incomplete run"
            break
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    tail = history[max(0, int(0.8 * len(history))) :]
    prior = history[max(0, int(0.6 * len(history))) : max(1, int(0.8 * len(history)))]
    cd_mean = float(np.mean([r["Cd"] for r in tail]))
    cl_mean = float(np.mean([r["Cl"] for r in tail]))
    previous = float(np.mean([r["Cd"] for r in prior]))
    stationarity = abs(cd_mean - previous) / max(abs(cd_mean), 1e-12)
    flux = abs(
        np.mean([r["flux_in_lattice"] - r["flux_out_lattice"] for r in tail])
    ) / max(abs(np.mean([r["flux_in_lattice"] for r in tail])), 1e-12)
    checks = {
        "stable": failed is None,
        "positive_drag": cd_mean > 0,
        "flux_le_5pct": bool(flux <= 0.05),
        "stationary_drag_le_5pct": stationarity <= 0.05,
    }
    status = (
        "FAIL"
        if failed or not checks["positive_drag"]
        else "SIMULATED_PENDING_REFINEMENT"
    )
    result = {
        "schema": "frontier.windtunnel.result/1",
        "evidence_kind": "simulated",
        "status": status,
        "request_echo": p,
        "geometry": geometry,
        "Re": reynolds,
        "tau": tau,
        "lattice_speed": speed,
        "dx_m": dx,
        "dt_s": dt,
        "completed_steps": step,
        "planned_steps": steps,
        "equal_time_target_convective": p["convective_time"],
        "checks": checks,
        "failure": failed,
        "mean_Cd_last20pct": cd_mean,
        "mean_Cl_last20pct": cl_mean,
        "drag_window_relative_change": stationarity,
        "flux_relative_difference": float(flux),
        "max_mach": max_mach,
        "max_density_deviation": max_density,
        "force_history": history,
        "frames": [
            {k: v for k, v in f.items() if k not in ("rho", "ux", "uy")} for f in frames
        ],
        "frame_storage": "exact sampled lattice nodes in central ROI; rho/u/v exported float32 from float64 simulation, no spatial interpolation",
        "units": {
            "velocity": "m/s = lattice velocity * speed_m_s/lattice_speed",
            "pressure": "Pa above freestream = density_kg_m3*(speed_m_s/lattice_speed)^2*(rho_lattice-1)/3",
            "force": "N/m of infinite span, not total 3D force",
            "time": "s; low-Re proxy mapping only",
        },
        "not_established": NOT_ESTABLISHED,
        "actuation_ports": protocol["actuation_ports"],
        "wall_seconds": time.perf_counter() - started,
        "provenance": {
            "input_sha256": hashlib.sha256(canonical(p)).hexdigest(),
            "protocol_sha256": file_sha(PROTOCOL),
            "analytic_receipt_sha256": hashlib.sha256(
                canonical(analytic_receipt)
            ).hexdigest(),
            "code_files": {
                str(f.relative_to(ROOT)): file_sha(f)
                for f in Path(__file__).parent.glob("*.py")
            },
            "environment": {
                "python": platform.python_version(),
                "torch": torch.__version__,
                "numpy": np.__version__,
                "device": device,
            },
        },
    }
    if frames:
        np.savez_compressed(
            output / "fields.npz",
            rho=np.stack([f["rho"] for f in frames]),
            ux=np.stack([f["ux"] for f in frames]),
            uy=np.stack([f["uy"] for f in frames]),
            solid=mask[np.ix_(xi, yi)],
            x_over_L=(xi + 0.5) / c,
            y_over_L=(yi + 0.5) / c,
            t_s=np.array([f["t_s"] for f in frames]),
            convective_time=np.array([f["convective_time"] for f in frames]),
        )
        result["fields_sha256"] = file_sha(output / "fields.npz")
    (output / "result.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    return result
