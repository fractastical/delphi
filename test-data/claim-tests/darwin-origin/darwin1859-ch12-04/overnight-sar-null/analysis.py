#!/usr/bin/env python3
"""Coleman random-placement null for the island species-area exponent.

Implements the grid fixed in result.json before any download. The Triantis
et al. 2012 per-dataset exponents were not obtainable from a public file, so
this script does not read, simulate, or invent observed z values. It reports
the null distribution on the pre-registered fallback geometries.

Run: python3 analysis.py
Requires numpy, scipy, pandas.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parent
RESULT_PATH = ROOT / "result.json"
DERIVED = ROOT / "derived"

# Frozen with the pre-registration. Do not retune after seeing output.
J_GRID = (10**3, 10**5, 10**7, 10**9)
SIGMAS = (1.0, 2.0, 3.0)
S0_GRID = (20, 100, 500)
ALPHAS = (5.0, 50.0, 500.0)
N_ISLANDS = (5, 10, 20, 40)
LOG10_SPANS = (1, 2, 3, 4)
CONVENTIONS = ("partition", "embedded")
STOC_SEED = 20261101
STOC_J = 10**3
MIN_RICHNESS = 0.5
MIN_ISLANDS = 4

FROZEN_FIELDS = (
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "test_contract",
)


def largest_remainder(weights: np.ndarray, total: int) -> np.ndarray | None:
    """Positive weights to integers that sum to total, each at least 1."""
    total = int(total)
    weights = np.asarray(weights, dtype=float)
    n = int(weights.size)
    if n == 0 or n > total or not np.all(weights > 0) or not np.isfinite(weights).all():
        return None
    scaled = weights / weights.sum() * total
    floors = np.floor(scaled).astype(np.int64)
    leftover = total - int(floors.sum())
    order = np.argsort(-(scaled - floors), kind="mergesort")
    for k in range(leftover):
        floors[order[k % n]] += 1
    guard = 0
    while np.any(floors < 1):
        zeros = np.flatnonzero(floors < 1)
        donors = np.flatnonzero(floors > 1)
        if donors.size == 0:
            return None
        donor = donors[np.argmax(floors[donors])]
        floors[zeros[0]] += 1
        floors[donor] -= 1
        guard += 1
        if guard > total:
            return None
    if int(floors.sum()) != total or np.any(floors < 1):
        return None
    return floors


def lognormal_abundances(sigma: float, s0: int, total: int) -> np.ndarray | None:
    """Quantile lognormal scaled to `total`, then largest-remainder integers."""
    if s0 > total:
        return None
    probs = (np.arange(1, s0 + 1) - 0.5) / s0
    raw = np.exp(sigma * norm.ppf(probs))
    return largest_remainder(raw, total)


def preston_community(s0: int) -> tuple[np.ndarray, float, int]:
    """Canonical lognormal: veil line at 1, individuals mode at the richest species.

    Sigma on the natural-log abundance scale equals the upper normal quantile
    of the species sample, which is the unique value that places the mode of
    the individuals curve on the most abundant species.
    """
    probs = (np.arange(1, s0 + 1) - 0.5) / s0
    u = norm.ppf(probs)
    sigma = float(u[-1])
    continuous = np.exp(sigma * (u - u[0]))
    mu = -sigma * float(u[0])
    mode = mu + sigma**2
    richest = float(np.log(continuous[-1]))
    if abs(mode - richest) > 1e-8:
        raise RuntimeError(f"Preston constraint failed for S0={s0}: {mode} vs {richest}")
    target = int(np.round(continuous.sum()))
    integer = largest_remainder(continuous, target)
    if integer is None:
        raise RuntimeError(f"Preston rounding failed for S0={s0}")
    # Keep the veil line at one individual after rounding.
    if int(integer[0]) != 1:
        integer = integer.copy()
        delta = 1 - int(integer[0])
        donor = int(np.argmax(integer))
        if int(integer[donor]) - delta < 1:
            raise RuntimeError(f"Preston veil-line adjustment failed for S0={s0}")
        integer[0] += delta
        integer[donor] -= delta
    if int(integer.sum()) != target or np.any(integer < 1):
        raise RuntimeError(f"Preston integer community invalid for S0={s0}")
    return integer, sigma, int(integer.sum())


def expected_richness(abundances: np.ndarray, area: float) -> float:
    """Coleman E[S(a)] = sum_i 1 - (1-a)^{n_i}."""
    a = float(area)
    if a <= 0.0:
        return 0.0
    if a >= 1.0:
        return float(np.count_nonzero(abundances))
    log_term = abundances.astype(float) * np.log1p(-a)
    contribution = np.empty(log_term.shape, dtype=float)
    huge = log_term < -700.0
    tiny = log_term > -1e-8
    mid = ~huge & ~tiny
    contribution[huge] = 1.0
    contribution[tiny] = -log_term[tiny]
    contribution[mid] = -np.expm1(log_term[mid])
    return float(contribution.sum())


def logseries_richness(alpha: float, total: int, area: float) -> float:
    """Closed form of the Coleman sum under Fisher's log-series."""
    return float(alpha * np.log1p(area * total / alpha))


def relative_areas(n_islands: int, log10_span: int, convention: str) -> np.ndarray:
    areas = np.geomspace(1.0, 10.0**log10_span, n_islands)
    if convention == "partition":
        return areas / areas.sum()
    if convention == "embedded":
        return areas / (10.0 * areas.max())
    raise ValueError(convention)


def fit_z(areas: np.ndarray, richness: np.ndarray) -> tuple[float, float, int] | None:
    keep = richness >= MIN_RICHNESS
    if int(keep.sum()) < MIN_ISLANDS:
        return None
    log_a = np.log(areas[keep])
    log_s = np.log(richness[keep])
    if not np.isfinite(log_s).all():
        return None
    slope, intercept = np.polyfit(log_a, log_s, 1)
    predicted = slope * log_a + intercept
    residual = float(np.sum((log_s - predicted) ** 2))
    total = float(np.sum((log_s - log_s.mean()) ** 2))
    r2 = 1.0 - residual / total if total > 0.0 else float("nan")
    return float(slope), r2, int(keep.sum())


def geometries() -> list[tuple[int, int, str, np.ndarray]]:
    rows = []
    for n_islands in N_ISLANDS:
        for span in LOG10_SPANS:
            for convention in CONVENTIONS:
                areas = relative_areas(n_islands, span, convention)
                if np.any(areas <= 0.0) or np.any(areas >= 1.0):
                    raise RuntimeError(f"area fraction out of (0,1): {n_islands} {span} {convention}")
                rows.append((n_islands, span, convention, areas))
    return rows


def adjust_to_total(abundances: list[int], total: int, rng: np.random.Generator) -> tuple[np.ndarray, int]:
    values = [int(x) for x in abundances if int(x) > 0]
    if not values:
        values = [1]
    current = sum(values)
    steps = 0
    limit = abs(current - total) + total + 5
    while current > total and steps < limit:
        index = int(rng.integers(len(values)))
        if values[index] > 1:
            values[index] -= 1
            current -= 1
        elif len(values) > 1:
            current -= values.pop(index)
        else:
            values[0] = total
            current = total
        steps += 1
    while current < total and steps < limit:
        if values and float(rng.random()) < 0.5:
            values[int(rng.integers(len(values)))] += 1
        else:
            values.append(1)
        current += 1
        steps += 1
    if sum(values) != total:
        raise RuntimeError("stochastic abundance adjustment did not hit J")
    return np.asarray(values, dtype=np.int64), steps


def stochastic_lognormal(sigma: float, s0: int, total: int, rng: np.random.Generator) -> np.ndarray | None:
    raw = np.exp(sigma * rng.normal(size=s0))
    return largest_remainder(raw, total)


def stochastic_logseries(alpha: float, total: int, rng: np.random.Generator) -> tuple[np.ndarray, int]:
    x = total / (total + alpha)
    n_max = int(np.ceil(np.log(1e-3 / total) / np.log(x)))
    n_max = max(n_max, 1)
    ns = np.arange(1, n_max + 1)
    means = alpha * np.exp(ns * np.log(x) - np.log(ns))
    counts = rng.poisson(means)
    abundances = np.repeat(ns, counts).astype(int).tolist()
    return adjust_to_total(abundances, total, rng)


def check_logseries_closed_form() -> float:
    """Max absolute gap between the truncated Coleman sum and the closed form."""
    worst = 0.0
    for alpha in (5.0, 20.0, 500.0):
        for total in (1000, 10000):
            x = total / (total + alpha)
            n_max = int(np.ceil(np.log(1e-12 / total) / np.log(x)))
            ns = np.arange(1, n_max + 1)
            expected_species = alpha * np.exp(ns * np.log(x) - np.log(ns))
            for area in (1e-4, 0.01, 0.1, 0.5):
                stay = np.exp(ns * np.log1p(-area))
                summed = float(np.sum(expected_species * (1.0 - stay)))
                closed = logseries_richness(alpha, total, area)
                worst = max(worst, abs(summed - closed))
    if worst > 1e-6:
        raise RuntimeError(f"log-series closed form disagrees with the Coleman sum by {worst}")
    return worst


def eta_squared(values: np.ndarray, groups: pd.Series) -> float:
    grand = float(values.mean())
    ss_total = float(np.sum((values - grand) ** 2))
    if ss_total == 0.0:
        return 0.0
    ss_between = 0.0
    for level in groups.unique():
        subset = values[groups.to_numpy() == level]
        ss_between += subset.size * (float(subset.mean()) - grand) ** 2
    return ss_between / ss_total


def distribution(values: np.ndarray) -> dict:
    return {
        "n": int(values.size),
        "min": float(np.min(values)),
        "p05": float(np.percentile(values, 5)),
        "p25": float(np.percentile(values, 25)),
        "median": float(np.median(values)),
        "p75": float(np.percentile(values, 75)),
        "p95": float(np.percentile(values, 95)),
        "max": float(np.max(values)),
        "mean": float(np.mean(values)),
        "sd": float(np.std(values, ddof=1)) if values.size > 1 else 0.0,
    }


def build_null(geoms) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(STOC_SEED)
    stoc_ln = {
        (sigma, s0): stochastic_lognormal(sigma, s0, STOC_J, rng)
        for sigma in SIGMAS
        for s0 in S0_GRID
    }
    stoc_ls = {}
    stoc_ls_steps = {}
    for alpha in ALPHAS:
        abundances, steps = stochastic_logseries(alpha, STOC_J, rng)
        stoc_ls[alpha] = abundances
        stoc_ls_steps[alpha] = steps

    rows = []
    for n_islands, span, convention, areas in geoms:
        for sigma in SIGMAS:
            for s0 in S0_GRID:
                for total in J_GRID:
                    abundances = lognormal_abundances(sigma, s0, total)
                    analytical = None if abundances is None else np.array(
                        [expected_richness(abundances, a) for a in areas]
                    )
                    fitted = None if analytical is None else fit_z(areas, analytical)
                    stoc_z = None
                    if total == STOC_J and stoc_ln[(sigma, s0)] is not None:
                        stoc_rich = np.array(
                            [expected_richness(stoc_ln[(sigma, s0)], a) for a in areas]
                        )
                        stoc_fit = fit_z(areas, stoc_rich)
                        stoc_z = None if stoc_fit is None else stoc_fit[0]
                    rows.append(
                        {
                            "family": "lognormal",
                            "sigma": sigma,
                            "alpha": np.nan,
                            "S0": s0,
                            "J": total,
                            "n_islands": n_islands,
                            "log10_span": span,
                            "convention": convention,
                            "z": None if fitted is None else fitted[0],
                            "r2": None if fitted is None else fitted[1],
                            "n_used": 0 if fitted is None else fitted[2],
                            "feasible": fitted is not None,
                            "z_stochastic": stoc_z,
                        }
                    )
        for alpha in ALPHAS:
            for total in J_GRID:
                richness = np.array([logseries_richness(alpha, total, a) for a in areas])
                fitted = fit_z(areas, richness)
                stoc_rich = np.array([expected_richness(stoc_ls[alpha], a) for a in areas]) if total == STOC_J else None
                stoc_fit = None if stoc_rich is None else fit_z(areas, stoc_rich)
                rows.append(
                    {
                        "family": "logseries",
                        "sigma": np.nan,
                        "alpha": alpha,
                        "S0": float(alpha * np.log1p(total / alpha)),
                        "J": total,
                        "n_islands": n_islands,
                        "log10_span": span,
                        "convention": convention,
                        "z": None if fitted is None else fitted[0],
                        "r2": None if fitted is None else fitted[1],
                        "n_used": 0 if fitted is None else fitted[2],
                        "feasible": fitted is not None,
                        "z_stochastic": None if stoc_fit is None else stoc_fit[0],
                    }
                )
        for s0 in S0_GRID:
            abundances, sigma, realized_j = preston_community(s0)
            richness = np.array([expected_richness(abundances, a) for a in areas])
            fitted = fit_z(areas, richness)
            rows.append(
                {
                    "family": "preston_canonical",
                    "sigma": sigma,
                    "alpha": np.nan,
                    "S0": s0,
                    "J": realized_j,
                    "n_islands": n_islands,
                    "log10_span": span,
                    "convention": convention,
                    "z": None if fitted is None else fitted[0],
                    "r2": None if fitted is None else fitted[1],
                    "n_used": 0 if fitted is None else fitted[2],
                    "feasible": fitted is not None,
                    "z_stochastic": None,
                }
            )

    frame = pd.DataFrame(rows)
    # Polyfit noise on a saturated curve is about 1e-15, not a negative exponent.
    noisy = frame["feasible"] & frame["z"].notna() & (frame["z"].abs() < 1e-8)
    frame.loc[noisy, "z"] = 0.0
    feasible = frame[frame["feasible"]].copy()
    if feasible.empty:
        raise RuntimeError("no feasible null cells")
    if (feasible["z"] < -1e-9).any():
        raise RuntimeError("Coleman slope was negative; the richness curve should increase with area")
    both = feasible[feasible["z_stochastic"].notna()]
    delta = (both["z_stochastic"] - both["z"]).to_numpy(dtype=float)
    z = feasible["z"].to_numpy(dtype=float)
    by_family = {
        family: distribution(feasible.loc[feasible["family"] == family, "z"].to_numpy(dtype=float))
        for family in ("lognormal", "logseries", "preston_canonical")
    }
    on_j_grid = feasible[feasible["family"].isin(["lognormal", "logseries"])]
    by_j = {
        str(int(total)): distribution(
            on_j_grid.loc[on_j_grid["J"] == total, "z"].to_numpy(dtype=float)
        )
        for total in J_GRID
    }
    summary = {
        "closed_form_max_abs_error": check_logseries_closed_form(),
        "n_cells": int(len(frame)),
        "n_feasible": int(len(feasible)),
        "n_infeasible": int((~frame["feasible"]).sum()),
        "null_z": distribution(z),
        "by_family": by_family,
        "by_J_lognormal_and_logseries": by_j,
        "share_z_positive": float(np.mean(z > 1e-6)),
        "share_z_between_0_20_and_0_30": float(np.mean((z >= 0.20) & (z <= 0.30))),
        "within_null_eta_squared": {
            "family": eta_squared(z, feasible["family"]),
            "log10_span": eta_squared(z, feasible["log10_span"]),
            "n_islands": eta_squared(z, feasible["n_islands"]),
            "convention": eta_squared(z, feasible["convention"]),
            "J_on_lognormal_and_logseries": eta_squared(
                on_j_grid["z"].to_numpy(dtype=float), on_j_grid["J"]
            ),
        },
        "stochastic_j_1000": {
            "seed": STOC_SEED,
            "n_comparisons": int(delta.size),
            "mean_abs_dz": float(np.mean(np.abs(delta))) if delta.size else None,
            "max_abs_dz": float(np.max(np.abs(delta))) if delta.size else None,
            "logseries_adjustment_steps": {str(int(k)): int(v) for k, v in stoc_ls_steps.items()},
        },
        "preston_sigma": {
            str(s0): float(norm.ppf((s0 - 0.5) / s0)) for s0 in S0_GRID
        },
        "preston_realized_J": {
            str(s0): int(preston_community(s0)[2]) for s0 in S0_GRID
        },
        "observed_z_used": False,
        "anderson_darling": {"status": "not_run", "reason": "data-unavailable"},
    }
    return frame, summary


def write_result(summary: dict) -> None:
    result = json.loads(RESULT_PATH.read_text())
    frozen = {key: result[key] for key in FROZEN_FIELDS}
    null_z = summary["null_z"]
    result["status"] = "complete"
    result["data_kind"] = "computational"
    result["interpretation"] = (
        "Darwin's sentence says oceanic islands hold far fewer species than continental areas of equal size, "
        "and that physical conditions do not explain the difference. The open problem asks what sets the "
        "species-area exponent z. This run maps that question onto Coleman's random-placement curve, "
        "E[S(a)] = sum_i 1-(1-a)^{n_i}, which already predicts fewer species in a smaller sample. "
        "The numbers below are that null, not a measurement of islands. Preston's canonical constraint "
        "is implemented as a lognormal whose least abundant species has one individual and whose "
        "individuals-curve mode sits on the richest species; it is not rescaled onto the J grid, because "
        "that rescaling would move the veil line. The classic claim that a canonical lognormal yields "
        "z around 0.25 is a different sampling construction from the ordinary-least-squares slope of "
        "this Coleman curve on the pre-registered windows."
    )
    result["datasets"] = []
    result["method"] = (
        "No public file supplied the Triantis et al. 2012 per-dataset exponents or island areas, so the "
        "null was evaluated on the fallback geometries named in the pre-registered contract: 5, 10, 20 and "
        "40 geometrically spaced islands, area spans of 1, 2, 3 and 4 orders of magnitude, and two pool "
        "conventions (island areas partition the pool, or the pool is ten times the largest island). "
        "Lognormal communities use sigma in {1, 2, 3} and S0 in {20, 100, 500}, with normal quantiles "
        "scaled to J in {1e3, 1e5, 1e7, 1e9} and largest-remainder rounded to integers of at least 1. "
        "Log-series communities use alpha in {5, 50, 500} and the closed form alpha*ln(1+a*J/alpha), "
        "checked against a truncated Coleman sum. Preston communities use S0 in {20, 100, 500} with sigma "
        "equal to the upper normal quantile, which enforces the canonical mode condition. z is the "
        "ordinary-least-squares slope of log expected richness on log relative area, dropping islands "
        "with expected richness below 0.5 and requiring at least four islands. For J=1000 only, one "
        "stochastic abundance draw from Generator seed 20261101 was compared with the analytical z and "
        "was not treated as an observation. The Anderson-Darling comparison was not run."
    )
    result["measured"] = {
        "value": null_z["median"],
        "unit": "Coleman-null power-law exponent z on the pre-registered grid",
        "n": null_z["n"],
        "uncertainty": f"5th–95th percentile {null_z['p05']:.4f} to {null_z['p95']:.4f}",
        "extra": summary,
    }
    result["verdict"] = "inconclusive"
    result["reason"] = "data-unavailable"
    result["confidence"] = 0.8
    result["caveats"] = [
        "The comparison with observed exponents was not run. No Dryad, Zenodo, Figshare or DataCite record of the Triantis, Guilhaumon and Whittaker 2012 compilation (DOI 10.1111/j.1365-2699.2011.02652.x) was found, Unpaywall and OpenAlex mark the paper closed, and Europe PMC records no supplement. Wiley returned HTTP 403, so a subscription appendix was not inspected. Observed z values were not invented.",
        "The CRAN package sars cites the paper and is the only OpenAlex dataset that does so. Its data files are seven small examples (aegean, aegean2, cole_sim, countryside, galap, habitat, niering), not the 601-dataset compilation, and they were not used as observations.",
        "Without per-dataset area lists, null exponents use the pre-registered fallback windows. Those windows are not the archipelagos in the compilation, so the null spread is not an estimate of between-dataset variance.",
        (
            "A power-law slope is a local summary of a Coleman curve that is not itself a power law. "
            "On the lognormal and log-series cells, total abundance J accounts for "
            f"{summary['within_null_eta_squared']['J_on_lognormal_and_logseries']:.0%} of the variation in null z: "
            f"the median is {summary['by_J_lognormal_and_logseries']['1000']['median']:.3f} at J=10^3 and "
            f"{summary['by_J_lognormal_and_logseries']['1000000000']['median']:.3f} at J=10^9. "
            "Species-abundance family, area span, island count and pool convention each have a small main-effect share. "
            "The null can therefore sit almost anywhere in (0, 1) when J is free. "
            "That is a property of these curves, not a comparison with islands."
        ),
        "The stochastic check is one draw at J=1000. It is a numerical comparison with the analytical curve, not a second null distribution and not biological data.",
    ]
    result["agent"] = {
        "kind": "cursor-agent",
        "model": "grok-4.7",
        "run": "species-area-exponent--claude-opus-5-5--2",
        "date": "2026-11-01",
    }
    for key, value in frozen.items():
        if result[key] != value:
            raise RuntimeError(f"refusing to rewrite pre-registered field {key}")
    RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n")


def main() -> None:
    DERIVED.mkdir(exist_ok=True)
    frame, summary = build_null(geometries())
    # check_logseries is called inside build_null; keep the stored error.
    out_csv = DERIVED / "null_z.csv"
    compact = frame.copy()
    for column in ("z", "r2", "z_stochastic", "S0", "sigma", "alpha"):
        compact[column] = pd.to_numeric(compact[column], errors="coerce").round(6)
    compact.to_csv(out_csv, index=False)
    (DERIVED / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_result(summary)
    null_z = summary["null_z"]
    print(
        f"feasible {summary['n_feasible']}/{summary['n_cells']} "
        f"median_z {null_z['median']:.4f} "
        f"p05 {null_z['p05']:.4f} p95 {null_z['p95']:.4f} "
        f"csv_bytes {out_csv.stat().st_size}"
    )


if __name__ == "__main__":
    main()
