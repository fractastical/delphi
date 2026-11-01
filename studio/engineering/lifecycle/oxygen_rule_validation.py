"""Numerically check the shared center-oxygen rule against existing profiles.

This is an arithmetic/implementation check with a deliberately dimensionless
fixture. It is not a measurement or a tissue-parameter calibration.
"""

from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path
from typing import Any

from engineering.lifecycle.diffusion import (
    slab_limit_thickness,
    slab_profile,
    sphere_limit_radius,
    sphere_profile,
)

TOLERANCE = 1e-12


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _close(actual: float, expected: float, *, label: str, rows: list[dict[str, Any]]) -> None:
    error = abs(actual - expected)
    passed = math.isfinite(actual) and error <= TOLERANCE * max(1.0, abs(expected))
    rows.append({"check": label, "actual": actual, "expected": expected, "absolute_error": error,
                 "tolerance": TOLERANCE, "status": "pass" if passed else "fail"})
    if not passed:
        raise AssertionError(f"{label}: {actual} != {expected} (error {error})")


def validate_profiles() -> dict[str, Any]:
    """Check center equations, boundary values, zero-size and threshold cases."""
    D, a, C0 = 2.0, 1.0, 3.0  # dimensionless arithmetic fixture; not measured inputs
    rows: list[dict[str, Any]] = []

    sphere_limit_sq = 6.0 * D * C0 / a
    sphere_limit = math.sqrt(sphere_limit_sq)
    _close(sphere_limit_radius(D, C0 / a), sphere_limit,
           label="sphere_limit_helper_matches_stated_bound", rows=rows)
    for label, radius in (("under", 2.0), ("limit", sphere_limit), ("over", 7.0), ("zero_radius", 0.0)):
        center = sphere_profile(0.0, radius, D, C0, a)
        equation_center = C0 - a * radius**2 / (6.0 * D)
        _close(center, equation_center, label=f"sphere_{label}_profile_matches_center_equation", rows=rows)
        if label == "under":
            assert a * radius**2 <= 6.0 * D * C0 and center > 0
        elif label == "limit":
            assert math.isclose(a * radius**2, 6.0 * D * C0, rel_tol=0, abs_tol=TOLERANCE)
            _close(center, 0.0, label="sphere_center_at_limit_is_zero", rows=rows)
        elif label == "over":
            assert a * radius**2 > 6.0 * D * C0 and center < 0
        else:
            _close(center, C0, label="sphere_zero_radius_equals_boundary", rows=rows)
        _close(sphere_profile(radius, radius, D, C0, a), C0,
               label=f"sphere_{label}_outer_boundary_equals_C0", rows=rows)

    slab_limit_sq = 2.0 * D * C0 / a
    slab_limit = math.sqrt(slab_limit_sq)
    _close(slab_limit_thickness(D, C0 / a), slab_limit,
           label="slab_limit_helper_matches_stated_bound", rows=rows)
    for label, half_thickness in (("under", 2.0), ("limit", slab_limit), ("over", 4.0), ("zero_thickness", 0.0)):
        center = slab_profile(0.0, half_thickness, D, C0, a)
        equation_center = C0 - a * half_thickness**2 / (2.0 * D)
        _close(center, equation_center, label=f"slab_{label}_profile_matches_center_equation", rows=rows)
        if label == "under":
            assert a * half_thickness**2 <= 2.0 * D * C0 and center > 0
        elif label == "limit":
            assert math.isclose(a * half_thickness**2, 2.0 * D * C0, rel_tol=0, abs_tol=TOLERANCE)
            _close(center, 0.0, label="slab_center_at_limit_is_zero", rows=rows)
        elif label == "over":
            assert a * half_thickness**2 > 2.0 * D * C0 and center < 0
        else:
            _close(center, C0, label="slab_zero_thickness_equals_boundary", rows=rows)
        _close(slab_profile(half_thickness, half_thickness, D, C0, a), C0,
               label=f"slab_{label}_outer_boundary_equals_C0", rows=rows)

    return {
        "schema": "frontier.oxygen-diffusion-numerical-check/1",
        "status": "pass",
        "scope": "dimensionless arithmetic fixture checked against the repository's existing analytical profiles",
        "source_pins": {
            "diffusion_model": {"path": "engineering/lifecycle/diffusion.py",
                                 "sha256": _sha256(Path(__file__).with_name("diffusion.py"))},
            "validation_code": {"path": "engineering/lifecycle/oxygen_rule_validation.py",
                                "sha256": _sha256(Path(__file__))}
        },
        "fixture": {"D": D, "a": a, "C0": C0, "units": "dimensionless test values; not tissue calibration"},
        "sphere_limit_radius": sphere_limit,
        "slab_limit_half_thickness": slab_limit,
        "checks": rows,
        "check_count": len(rows),
        "limitations": [
            "This compares analytic profile implementations and boundary cases; it is not an independent biological validation.",
            "The over-limit negative center is a model-domain warning, not a physically negative oxygen concentration.",
            "No cell-viability threshold, perfusion, spatially varying demand, transient response, or empirical parameter was checked."
        ]
    }


def main() -> int:
    result = validate_profiles()
    out = Path("artifacts/oxygen-diffusion-rule/numerical-checks.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "checks": result["check_count"], "output": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
