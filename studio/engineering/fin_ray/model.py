"""Alben et al. 2007 Eq3.14/5.2 for one uniform, fused-tip planar ray.

All values are NONDIMENSIONAL as specified by the paper's Section3.3.
G is normalized shear-modulus times intraray area, not a modulus in Pa.
This is not the aggregate constant-EI fin scaffold or a muscle/servo model.
"""

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import itertools
import json
from pathlib import Path
import platform
import subprocess
import time

import numpy as np
import scipy
from scipy.integrate import cumulative_simpson, quad, solve_bvp

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/fin-ray"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


@dataclass(frozen=True)
class Parameters:
    B: float = 1.0
    G: float = 200.0
    d: float = .01
    phi0: float = .01
    p: float = 200.0

    def __post_init__(self):
        if not np.isfinite(list(asdict(self).values())).all():
            raise ValueError("Finite nondimensional inputs required")
        if self.B <= 0 or self.G < 0 or not 0 < self.d <= .05:
            raise ValueError("B>0, G>=0, 0<d<=.05 required in this bounded adapter")
        if np.sqrt(self.G / (2 * self.B)) > 100:
            raise ValueError("Hyperbolic localization beyond supported numeric envelope")


def analytic(s, parameters):
    """Printed Eq5.2 and its derivative, including the regular G=0 limit."""
    b, g, d, phi0, p = asdict(parameters).values()
    s = np.asarray(s)
    if g == 0:
        slope = -phi0 + p * d / (6 * b)
        phi = phi0 + slope * s - p * d / (2 * b) * (s**2 / 2 - s**3 / 6)
        derivative = slope - p * d / (2 * b) * (s - s**2 / 2)
    else:
        a = np.sqrt(g / (2 * b))
        c = p * d / g
        phi = (phi0 - c) * np.sinh(a * (1 - s)) / np.sinh(a) + c * (1 - s)
        derivative = -(phi0 - c) * a * np.cosh(a * (1 - s)) / np.sinh(a) - c
    return phi, derivative


def numerical(parameters, tolerance=1e-10):
    """Solve the second-order balance directly, starting from a linear guess."""
    b, g, d, phi0, p = asdict(parameters).values()

    def equation(s, value):
        return np.vstack((value[1], (g * value[0] - p * d * (1 - s)) / (2 * b)))

    def boundary(left, right):
        return np.array([left[0] - phi0, right[0]])

    s = np.linspace(0, 1, 101)
    guess = np.vstack((phi0 * (1 - s), np.full_like(s, -phi0)))
    solution = solve_bvp(equation, boundary, s, guess, tol=tolerance, max_nodes=10000)
    if not solution.success:
        raise RuntimeError(f"BVP failed: {solution.message}")
    return solution


def unloaded_stiffness(parameters):
    """Derived d²U/dphi0², only p=0; dimensional analogue has units N/m."""
    if parameters.p != 0:
        return None
    a = np.sqrt(parameters.G / (2 * parameters.B))
    factor = a / np.tanh(a) if a else 1.0
    return float(2 * parameters.B * factor / parameters.d**2)


def compute(parameters, tolerance=1e-10):
    solution = numerical(parameters, tolerance)
    s = np.linspace(0, 1, 1001)
    phi, derivative = solution.sol(s)
    exact_phi, exact_derivative = analytic(s, parameters)
    kappa = -derivative / parameters.d
    theta = (parameters.phi0 - phi) / parameters.d
    x = cumulative_simpson(np.cos(theta), x=s, initial=0)
    y = cumulative_simpson(np.sin(theta), x=s, initial=0)

    def integrand(position):
        value, slope = solution.sol(position)
        return (parameters.B * slope**2 + parameters.G * value**2 / 2) / parameters.d**2

    energy, energy_quadrature_error = quad(integrand, 0, 1, epsabs=1e-11, epsrel=1e-11)
    stiffness = unloaded_stiffness(parameters)
    energy_stiffness = (
        float(2 * energy / parameters.phi0**2)
        if parameters.p == 0 and parameters.phi0 != 0 else None
    )
    summary = {
        "parameters": asdict(parameters), "BVP_tolerance": tolerance,
        "BVP_mesh_nodes": len(solution.x),
        "phi_max_absolute_error_vs_Eq5_2": float(np.max(abs(phi - exact_phi))),
        "curvature_max_absolute_error_vs_Eq5_2": float(np.max(abs(kappa + exact_derivative / parameters.d))),
        "BC_max_absolute_error": float(max(abs(phi[0] - parameters.phi0), abs(phi[-1]))),
        "tip_xy_over_L": [float(x[-1]), float(y[-1])],
        "base_tip_curvature_times_L": [float(kappa[0]), float(kappa[-1])],
        "min_max_curvature_times_L": [float(kappa.min()), float(kappa.max())],
        "max_abs_curvature_times_gap": float(np.max(abs(kappa * parameters.d))),
        "curvature_gap_caution_at_engineering_reference_0_1": bool(np.max(abs(kappa * parameters.d)) >= .1),
        "internal_energy_L_over_B0": energy,
        "energy_quadrature_absolute_error_estimate": energy_quadrature_error,
        "unloaded_generalized_sliding_stiffness_L3_over_B0": stiffness,
        "unloaded_stiffness_from_numerical_energy": energy_stiffness,
        "stiffness_relative_error": float(abs(energy_stiffness / stiffness - 1)) if energy_stiffness is not None else None,
        "empirical_validation": "unknown",
        "SI_ray_length_m": None, "SI_base_hemitrich_B0_N_m2": None,
    }
    return summary, dict(s=s, phi=phi, kappa=kappa, theta=theta, x=x, y=y)


def controls():
    cfg = json.loads((ART / "protocol.json").read_text())["controls"]
    source, trace = compute(Parameters())
    s = trace["s"]
    limit, _ = compute(Parameters(G=0, p=0))
    wrong_phi, _ = analytic(s, Parameters(p=-200))
    circle_error = max(abs(trace["x"][-1] - np.sin(1)), abs(trace["y"][-1] - (1 - np.cos(1))))
    checks = {
        "printed_source_closed_form_phi": source["phi_max_absolute_error_vs_Eq5_2"] <= cfg["closed_form_max_phi_absolute_error"],
        "printed_source_closed_form_curvature": source["curvature_max_absolute_error_vs_Eq5_2"] <= cfg["closed_form_max_curvature_absolute_error"],
        "printed_source_BCs": source["BC_max_absolute_error"] <= cfg["BC_absolute_error"],
        "G0_unloaded_constant_curvature": max(abs(x - 1) for x in limit["base_tip_curvature_times_L"]) <= cfg["closed_form_max_curvature_absolute_error"],
        "printed_source_exact_cancellation": float(200 * .01 / 200) == .01,
        "printed_source_circle_tip": circle_error <= cfg["circle_tip_absolute_error"],
        "wrong_curvature_sign_rejected": float(np.max(abs(-trace["kappa"] - 1))) > cfg["closed_form_max_curvature_absolute_error"],
        "wrong_load_sign_rejected": float(np.max(abs(trace["phi"] - wrong_phi))) > cfg["closed_form_max_phi_absolute_error"],
    }
    checks = {name: bool(value) for name, value in checks.items()}
    return {"checks": checks, "passed": all(checks.values()), "source_case": source, "circle_tip_error": float(circle_error), "scope": "Printed-equation numeric and mutation controls; not the inconsistent printed Fig8 curve or empirical ray reproduction"}


def run(out):
    if out.exists():
        raise ValueError("Fresh output directory required")
    out.mkdir(parents=True)
    start = time.monotonic()
    cfg = json.loads((ART / "protocol.json").read_text())
    result = controls()
    dump(out / "controls.json", result)
    if not result["passed"]:
        raise RuntimeError("Frozen numerical controls failed; no parameter run")
    cases = []
    for i, (g, phi0, p) in enumerate(itertools.product(cfg["cases"]["G"], cfg["cases"]["phi0"], cfg["cases"]["p"])):
        parameters = Parameters(G=g, phi0=phi0, p=p)
        record, trace = compute(parameters)
        coarse, _ = compute(parameters, 1e-8)
        record.update(id=f"ray-{i:02d}", tolerance_refinement={
            "coarse_tolerance": 1e-8,
            "coarse_phi_error": coarse["phi_max_absolute_error_vs_Eq5_2"],
            "coarse_curvature_error": coarse["curvature_max_absolute_error_vs_Eq5_2"],
            "scope": "Two solver tolerances compared with exact solution; no order/rate inference",
        })
        record["numerical_controls_passed"] = (
            record["phi_max_absolute_error_vs_Eq5_2"] <= cfg["controls"]["closed_form_max_phi_absolute_error"]
            and record["curvature_max_absolute_error_vs_Eq5_2"] <= cfg["controls"]["closed_form_max_curvature_absolute_error"]
            and record["BC_max_absolute_error"] <= cfg["controls"]["BC_absolute_error"]
        )
        path = out / f"{record['id']}.npz"
        np.savez_compressed(path, **trace)
        record["states"] = {"path": path.name, "sha256": digest(path), "bytes": path.stat().st_size}
        cases.append(record)
        dump(out / "results.json", {"cases": cases, "declared": cfg["cases"]["count"]})
    receipt = {
        "schema": "frontier.fin-ray.receipt/1", "source_model": cfg["source"],
        "protocol_sha256": digest(ART / "protocol.json"),
        "code_sha256": digest(Path(__file__)),
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "wall_seconds": time.monotonic() - start, "dollars": None,
        "cases_returned": len(cases), "numerical_controls_passed": sum(x["numerical_controls_passed"] for x in cases),
        "empirical_validation": "unknown", "figure8_reproduction": "NOT achieved; printed source discrepancy retained",
        "files": [{"path": path.name, "sha256": digest(path), "bytes": path.stat().st_size} for path in sorted(out.iterdir()) if path.is_file()],
    }
    dump(out / "receipt.json", receipt)
    print({k: v for k, v in receipt.items() if k not in ["files", "source_model"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)
