#!/usr/bin/env python3
"""Finite binary supply networks and the local metabolic exponent.

Primary volume: the sum of fixed terminal service volumes.
Alternative volume: total tube volume under area-preserving radii and
space-filling lengths. Both exponents come from one branching construction.

No datasets. The primary exponent is an exact integer identity. Tube-volume
exponents use decimal arithmetic. Nothing here is a measurement on an animal.

Re-run from this directory: python3 analysis.py
Writes derived/summary.json and prints the same object to stdout.
"""

from __future__ import annotations

import json
from decimal import Decimal, getcontext
from fractions import Fraction
from pathlib import Path

getcontext().prec = 80

GENERATIONS = range(2, 25)  # inclusive upper bound 24
BRANCHING = 2
THREE_QUARTERS = Decimal(3) / Decimal(4)
TOLERANCE = Decimal("0.01")
# Digits kept in the emitted strings. The working precision is 80.
EMIT = 40


def pow2(exponent: Decimal) -> Decimal:
    """2^exponent at the working precision. Integer exponents stay exact."""
    if exponent == exponent.to_integral_value() and exponent >= 0:
        return Decimal(1 << int(exponent))
    return Decimal(2) ** exponent


def tube_volume(generation: int) -> Decimal:
    """Sum of cylindrical vessel volumes in units of pi * r_c^2 * l_c.

    Level k = 0 is the root and k = G the terminals. Area preservation gives
    r_k^2 = r_c^2 * 2^(G-k). Space-filling gives l_k = l_c * 2^((G-k)/3).
    The level-k contribution is then 2^G * 2^((G-k)/3). The closed form
    2^G * (2^((G+1)/3) - 1) / (2^(1/3) - 1) is checked against the sum.
    """
    g = Decimal(generation)
    one_third = Decimal(1) / Decimal(3)
    summed = Decimal(0)
    for k in range(generation + 1):
        summed += pow2(g) * pow2((g - Decimal(k)) * one_third)
    closed = pow2(g) * (pow2((g + 1) * one_third) - 1) / (pow2(one_third) - 1)
    if abs(summed - closed) > Decimal("1e-60") * closed:
        raise SystemExit(f"tube-volume sum and closed form disagree at G={generation}")
    return summed


def local_exponent(flow_ratio: Decimal, volume_ratio: Decimal) -> Decimal:
    if volume_ratio <= 0 or flow_ratio <= 0:
        raise SystemExit("non-positive ratio in a local exponent")
    return flow_ratio.ln() / volume_ratio.ln()


def ols_slope(xs: list[Decimal], ys: list[Decimal]) -> Decimal:
    n = Decimal(len(xs))
    sx = sum(xs, Decimal(0))
    sy = sum(ys, Decimal(0))
    sxx = sum((x * x for x in xs), Decimal(0))
    sxy = sum((x * y for x, y in zip(xs, ys)), Decimal(0))
    return (n * sxy - sx * sy) / (n * sxx - sx * sx)


def emit(value: Decimal) -> str:
    return format(value, f".{EMIT}f")


def main() -> None:
    generations = list(GENERATIONS)
    # Primary: flow and service volume are both exactly 2^G.
    primary_flow = {g: 1 << g for g in generations}
    primary_volume = {g: 1 << g for g in generations}
    tube = {g: tube_volume(g) for g in generations}

    primary_local = []
    tube_local = []
    for g in generations[1:]:
        # Successive pair (g-1, g). Flow ratio is exactly 2 on both networks.
        flow_ratio = Fraction(primary_flow[g], primary_flow[g - 1])
        volume_ratio = Fraction(primary_volume[g], primary_volume[g - 1])
        if flow_ratio != 2 or volume_ratio != 2:
            raise SystemExit("primary ratios are not exactly 2")
        # log(2)/log(2) = 1 exactly; recorded as a fraction, not a float.
        exponent = Fraction(1, 1)
        primary_local.append(
            {
                "from_generation": g - 1,
                "to_generation": g,
                "exponent": "1/1",
                "exponent_exact": 1,
                "abs_deviation_from_3_4": "1/4",
            }
        )
        tube_ratio = tube[g] / tube[g - 1]
        tube_exponent = local_exponent(Decimal(2), tube_ratio)
        deviation = abs(tube_exponent - THREE_QUARTERS)
        tube_local.append(
            {
                "from_generation": g - 1,
                "to_generation": g,
                "exponent": emit(tube_exponent),
                "abs_deviation_from_3_4": emit(deviation),
                "within_0_01_of_3_4": deviation <= TOLERANCE,
            }
        )

    primary_within = any(
        Fraction(row["abs_deviation_from_3_4"]) <= Fraction(1, 100) for row in primary_local
    )
    tube_within_rows = [row for row in tube_local if row["within_0_01_of_3_4"]]

    # Ordinary least squares of log(flow) on log(volume), generations 2..24.
    # Primary: both logs are G * log(2), so the slope is exactly 1.
    log2 = Decimal(2).ln()
    primary_x = [Decimal(g) * log2 for g in generations]
    primary_y = [Decimal(g) * log2 for g in generations]
    primary_slope = ols_slope(primary_x, primary_y)
    if abs(primary_slope - 1) > Decimal("1e-60"):
        raise SystemExit("primary regression is not exactly 1")
    tube_x = [v.ln() for v in (tube[g] for g in generations)]
    tube_y = [Decimal(g) * log2 for g in generations]
    tube_slope = ols_slope(tube_x, tube_y)

    summary = {
        "branching_ratio": BRANCHING,
        "generations": [generations[0], generations[-1]],
        "n_successive_pairs": len(primary_local),
        "primary": {
            "service_volume": "sum of fixed terminal service volumes",
            "flow": "total terminal flow = 2^G",
            "local_exponent_exact": "1/1",
            "abs_deviation_from_3_4_exact": "1/4",
            "any_local_exponent_within_0_01_of_3_4": primary_within,
            "ols_slope_log_flow_on_log_volume": "1/1",
            "local_exponents": primary_local,
        },
        "alternative_tube_volume": {
            "volume": "sum of cylindrical vessel volumes, area-preserving radii, length ratio 2^(-1/3)",
            "normalization": "pi * r_c^2 * l_c; the factor cancels in every ratio",
            "ols_slope_log_flow_on_log_volume": emit(tube_slope),
            "first_generation_within_0_01_of_3_4": (
                tube_within_rows[0]["to_generation"] if tube_within_rows else None
            ),
            "exponent_at_generation_24": tube_local[-1]["exponent"],
            "abs_deviation_at_generation_24": tube_local[-1]["abs_deviation_from_3_4"],
            "within_0_01_at_generation_24": tube_local[-1]["within_0_01_of_3_4"],
            "local_exponents": tube_local,
        },
        "preregistered_primary_passes": primary_within,
    }
    out = Path(__file__).resolve().parent / "derived" / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    tube_rows = summary["alternative_tube_volume"]["local_exponents"]
    by_g = {row["to_generation"]: row for row in tube_rows}
    print(json.dumps({
        "primary_passes": summary["preregistered_primary_passes"],
        "primary_local_exponent": summary["primary"]["local_exponent_exact"],
        "primary_deviation": summary["primary"]["abs_deviation_from_3_4_exact"],
        "primary_ols": summary["primary"]["ols_slope_log_flow_on_log_volume"],
        "n_pairs": summary["n_successive_pairs"],
        "tube_ols": summary["alternative_tube_volume"]["ols_slope_log_flow_on_log_volume"],
        "tube_first_within": summary["alternative_tube_volume"]["first_generation_within_0_01_of_3_4"],
        "tube_exponent_at_12": by_g[12]["exponent"],
        "tube_deviation_at_12": by_g[12]["abs_deviation_from_3_4"],
        "tube_exponent_at_13": by_g[13]["exponent"],
        "tube_deviation_at_13": by_g[13]["abs_deviation_from_3_4"],
        "tube_exponent_at_24": summary["alternative_tube_volume"]["exponent_at_generation_24"],
        "tube_deviation_at_24": summary["alternative_tube_volume"]["abs_deviation_at_generation_24"],
    }, indent=2))


if __name__ == "__main__":
    main()
