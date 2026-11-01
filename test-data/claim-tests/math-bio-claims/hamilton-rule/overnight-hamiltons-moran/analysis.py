#!/usr/bin/env python3
"""Exact paired-population Moran calculation for Hamilton's rule."""

from __future__ import annotations

import csv
import json
from fractions import Fraction
from itertools import product
from pathlib import Path

N = 6
B = Fraction(5)
C = Fraction(1)
PAIRS = ((0, 1), (2, 3), (4, 5))
PARTNER = {a: b for a, b in PAIRS for a, b in ((a, b), (b, a))}
OUT = Path(__file__).with_name("derived")


def q(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def sign(value: Fraction) -> int:
    return (value > 0) - (value < 0)


def fitnesses(config: tuple[int, ...]) -> tuple[Fraction, ...]:
    return tuple(
        Fraction(1) - C * x + B * x * config[PARTNER[i]]
        for i, x in enumerate(config)
    )


def solve(matrix: list[list[Fraction]], vector: list[Fraction]) -> list[Fraction]:
    """Solve a nonsingular square system by exact Gauss-Jordan elimination."""
    a = [row[:] + [rhs] for row, rhs in zip(matrix, vector)]
    n = len(a)
    for col in range(n):
        pivot = next(row for row in range(col, n) if a[row][col])
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        a[col] = [v / scale for v in a[col]]
        for row in range(n):
            if row != col and a[row][col]:
                scale = a[row][col]
                a[row] = [x - scale * y for x, y in zip(a[row], a[col])]
    return [a[i][-1] for i in range(n)]


def ols(rows: list[tuple[Fraction, Fraction, Fraction]]) -> tuple[Fraction, Fraction, Fraction]:
    """Fit w = intercept + beta_x*x + beta_y*y exactly."""
    design = [(Fraction(1), x, y) for x, y, _ in rows]
    xtx = [[sum(a[i] * a[j] for a in design) for j in range(3)] for i in range(3)]
    xtw = [sum(a[i] * row[2] for a, row in zip(design, rows)) for i in range(3)]
    return tuple(solve(xtx, xtw))


def regression_y_on_x(rows: list[tuple[Fraction, Fraction, Fraction]]) -> Fraction:
    mean_x = sum(row[0] for row in rows) / len(rows)
    mean_y = sum(row[1] for row in rows) / len(rows)
    covariance = sum((row[0] - mean_x) * (row[1] - mean_y) for row in rows)
    variance = sum((row[0] - mean_x) ** 2 for row in rows)
    return covariance / variance


def config_transition(config: tuple[int, ...]) -> tuple[dict[tuple[int, ...], Fraction], Fraction]:
    fit = fitnesses(config)
    total = sum(fit)
    transitions: dict[tuple[int, ...], Fraction] = {}
    for parent in range(N):
        for dead in range(N):
            nxt = list(config)
            nxt[dead] = config[parent]
            nxt_tuple = tuple(nxt)
            probability = fit[parent] / total / N
            transitions[nxt_tuple] = transitions.get(nxt_tuple, Fraction()) + probability
    expected_delta_p = sum(
        probability * Fraction(sum(nxt) - sum(config), N)
        for nxt, probability in transitions.items()
    )
    return transitions, expected_delta_p


def main() -> None:
    OUT.mkdir(exist_ok=True)
    configs = list(product((0, 1), repeat=N))
    by_count = {k: [cfg for cfg in configs if sum(cfg) == k] for k in range(N + 1)}

    # The requested seven-state table is the uniform-within-count aggregation.
    transition = [[Fraction() for _ in range(N + 1)] for _ in range(N + 1)]
    deltas: dict[int, Fraction] = {}
    rows_by_count: dict[int, list[tuple[Fraction, Fraction, Fraction]]] = {}
    within_count_deltas: dict[int, set[Fraction]] = {}
    for k, group in by_count.items():
        pooled_rows = []
        config_deltas = set()
        for cfg in group:
            fit = fitnesses(cfg)
            pooled_rows.extend(
                (Fraction(cfg[i]), Fraction(cfg[PARTNER[i]]), fit[i]) for i in range(N)
            )
            cfg_transition, cfg_delta = config_transition(cfg)
            config_deltas.add(cfg_delta)
            for nxt, probability in cfg_transition.items():
                transition[k][sum(nxt)] += probability / len(group)
        rows_by_count[k] = pooled_rows
        within_count_deltas[k] = config_deltas
        deltas[k] = sum(
            transition[k][j] * Fraction(j - k, N) for j in range(N + 1)
        )

    frozen_intercept, frozen_beta_x, frozen_b = ols(rows_by_count[3])
    frozen_c = -frozen_beta_x
    comparison = []
    refit_matches = True
    frozen_disagreements = []
    for k in range(1, N):
        intercept, beta_x, fitted_b = ols(rows_by_count[k])
        fitted_c = -beta_x
        r = regression_y_on_x(rows_by_count[k])
        refit = r * fitted_b - fitted_c
        frozen = r * frozen_b - frozen_c
        exact_sign = sign(deltas[k])
        refit_match = sign(refit) == exact_sign
        frozen_match = sign(frozen) == exact_sign
        refit_matches &= refit_match
        if not frozen_match:
            frozen_disagreements.append(k)
        comparison.append(
            {
                "cooperators": k,
                "expected_delta_frequency": q(deltas[k]),
                "relatedness_regression": q(r),
                "refit_b": q(fitted_b),
                "refit_c": q(fitted_c),
                "refit_rb_minus_c": q(refit),
                "frozen_b": q(frozen_b),
                "frozen_c": q(frozen_c),
                "frozen_rb_minus_c": q(frozen),
                "exact_sign": exact_sign,
                "refit_match": refit_match,
                "frozen_match": frozen_match,
                "distinct_config_deltas_at_count": len(within_count_deltas[k]),
            }
        )

    endpoint_disagreements = [k for k in frozen_disagreements if k in (1, N - 1)]
    passed = refit_matches and bool(endpoint_disagreements)

    with (OUT / "state-comparison.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=comparison[0].keys())
        writer.writeheader()
        writer.writerows(comparison)
    with (OUT / "transition-matrix.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["from_count"] + [f"to_{j}" for j in range(N + 1)])
        for k, row in enumerate(transition):
            writer.writerow([k] + [q(value) for value in row])

    summary = {
        "arithmetic": "fractions.Fraction",
        "population_size": N,
        "configurations_enumerated": len(configs),
        "frozen_fit_at_cooperators": 3,
        "frozen_intercept": q(frozen_intercept),
        "frozen_b": q(frozen_b),
        "frozen_c": q(frozen_c),
        "refit_matches_all_nonzero_states": refit_matches,
        "frozen_disagreement_states": frozen_disagreements,
        "frozen_endpoint_disagreement_states": endpoint_disagreements,
        "preregistered_pass": passed,
        "count_projection_is_lumpable": all(
            len(within_count_deltas[k]) == 1 for k in range(N + 1)
        ),
        "distinct_config_delta_counts": {
            str(k): len(within_count_deltas[k]) for k in range(N + 1)
        },
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
