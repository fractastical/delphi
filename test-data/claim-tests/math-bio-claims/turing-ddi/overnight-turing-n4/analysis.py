#!/usr/bin/env python3
"""Finite-search census/sample for diffusion-driven instability.

Pre-run constants:
* seed = 470003
* nonzero reaction magnitudes and positive diffusion coefficients are sampled
  log-uniformly on [1e-2, 1e2]
* wave numbers are 121 log-spaced values on [1e-3, 1e3]
* n=3: all 3^9 patterns x all 7 nonempty diffusion supports, 200 draws
* n=4: 2,000 distinct uniformly sampled cyclic patterns, one uniformly sampled
  nonempty support per pattern, 100 draws

A draw is Turing-capable exactly when J is Hurwitz (strict Routh-Hurwitz
inequalities) and J-k^2 D is non-Hurwitz for at least one tested k > 0.
Numerical comparisons use an absolute strictness tolerance of 1e-10.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

try:
    from scipy.stats import beta as scipy_beta
except ModuleNotFoundError:  # Keep the clean-checkout script usable with NumPy alone.
    scipy_beta = None

SEED = 470003
RATE_LOW, RATE_HIGH = 1e-2, 1e2
DIFFUSION_LOW, DIFFUSION_HIGH = 1e-2, 1e2
K_VALUES = np.logspace(-3, 3, 121)
TOL = 1e-10
N3_DRAWS = 200
N4_PATTERNS = 2000
N4_DRAWS = 100


def signs_from_codes(codes: np.ndarray, n: int) -> np.ndarray:
    """Decode integers as row-major base-3 matrices with digits -1, 0, +1."""
    powers = 3 ** np.arange(n * n, dtype=np.int64)
    digits = (codes[:, None] // powers[None, :]) % 3
    return (digits - 1).reshape(-1, n, n).astype(float)


def has_directed_cycle(signs: np.ndarray) -> bool:
    """Test the graph with edge j->i when J[i,j] is nonzero; loops count."""
    adjacency = signs.T != 0
    n = signs.shape[0]
    state = np.zeros(n, dtype=np.int8)

    def visit(node: int) -> bool:
        state[node] = 1
        for target in np.flatnonzero(adjacency[node]):
            if state[target] == 1 or (state[target] == 0 and visit(int(target))):
                return True
        state[node] = 2
        return False

    return any(state[node] == 0 and visit(node) for node in range(n))


def hurwitz3(m: np.ndarray) -> np.ndarray:
    """Strict cubic Routh-Hurwitz test for batched real 3x3 matrices."""
    a1 = -np.trace(m, axis1=-2, axis2=-1)
    a2 = (
        m[..., 0, 0] * m[..., 1, 1] - m[..., 0, 1] * m[..., 1, 0]
        + m[..., 0, 0] * m[..., 2, 2] - m[..., 0, 2] * m[..., 2, 0]
        + m[..., 1, 1] * m[..., 2, 2] - m[..., 1, 2] * m[..., 2, 1]
    )
    a3 = -np.linalg.det(m)
    return (
        (a1 > TOL) & (a2 > TOL) & (a3 > TOL)
        & (a1 * a2 - a3 > TOL)
    )


def hurwitz4(m: np.ndarray) -> np.ndarray:
    """Strict quartic Routh-Hurwitz test for batched real 4x4 matrices."""
    tr1 = np.trace(m, axis1=-2, axis2=-1)
    m2 = m @ m
    tr2 = np.trace(m2, axis1=-2, axis2=-1)
    tr3 = np.trace(m2 @ m, axis1=-2, axis2=-1)
    a1 = -tr1
    a2 = (tr1 * tr1 - tr2) / 2
    a3 = -(tr1**3 - 3 * tr1 * tr2 + 2 * tr3) / 6
    a4 = np.linalg.det(m)
    return (
        (a1 > TOL) & (a2 > TOL) & (a3 > TOL) & (a4 > TOL)
        & (a1 * a2 - a3 > TOL)
        & (a1 * a2 * a3 - a3 * a3 - a1 * a1 * a4 > TOL)
    )


def log_uniform(rng: np.random.Generator, shape: tuple[int, ...],
                low: float, high: float) -> np.ndarray:
    return np.exp(rng.uniform(np.log(low), np.log(high), size=shape))


def binomial_range_probability(n: int, p: float, first: int, last: int) -> float:
    """Stable sum of Binomial(n,p) probabilities from first through last."""
    if first > last:
        return 0.0
    if p == 0:
        return 1.0 if first <= 0 <= last else 0.0
    if p == 1:
        return 1.0 if first <= n <= last else 0.0
    logs = [
        math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
        + k * math.log(p) + (n - k) * math.log1p(-p)
        for k in range(first, last + 1)
    ]
    maximum = max(logs)
    return math.exp(maximum) * math.fsum(math.exp(x - maximum) for x in logs)


def clopper_pearson(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Two-sided exact interval, with a SciPy-free bisection fallback."""
    if scipy_beta is not None:
        lower = 0.0 if successes == 0 else float(
            scipy_beta.ppf(alpha / 2, successes, n - successes + 1)
        )
        upper = 1.0 if successes == n else float(
            scipy_beta.ppf(1 - alpha / 2, successes + 1, n - successes)
        )
        return lower, upper

    lower = 0.0
    if successes > 0:
        lo, hi = 0.0, successes / n
        for _ in range(60):
            mid = (lo + hi) / 2
            if binomial_range_probability(n, mid, successes, n) < alpha / 2:
                lo = mid
            else:
                hi = mid
        lower = (lo + hi) / 2
    upper = 1.0
    if successes < n:
        lo, hi = successes / n, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if binomial_range_probability(n, mid, 0, successes) > alpha / 2:
                lo = mid
            else:
                hi = mid
        upper = (lo + hi) / 2
    return lower, upper


def shifted(m: np.ndarray, diffusion: np.ndarray, k: float) -> np.ndarray:
    out = m.copy()
    diagonal = np.arange(m.shape[-1])
    out[..., diagonal, diagonal] -= (k * k) * diffusion
    return out


def shifted_hurwitz3(m: np.ndarray, diffusion: np.ndarray,
                     wave_numbers: np.ndarray) -> np.ndarray:
    """Cubic Routh-Hurwitz on J-k^2D using coefficient polynomials."""
    x = wave_numbers[None, None, :] ** 2
    j00, j11, j22 = m[..., 0, 0], m[..., 1, 1], m[..., 2, 2]
    d0, d1, d2 = diffusion[..., 0], diffusion[..., 1], diffusion[..., 2]
    a1_0 = -(j00 + j11 + j22)
    a2_0 = (
        j00 * j11 - m[..., 0, 1] * m[..., 1, 0]
        + j00 * j22 - m[..., 0, 2] * m[..., 2, 0]
        + j11 * j22 - m[..., 1, 2] * m[..., 2, 1]
    )
    a3_0 = -np.linalg.det(m)
    a1 = a1_0[..., None] + x * (d0 + d1 + d2)[..., None]
    a2 = (
        a2_0[..., None]
        - x * (
            d0 * (j11 + j22) + d1 * (j00 + j22) + d2 * (j00 + j11)
        )[..., None]
        + x * x * (d0 * d1 + d0 * d2 + d1 * d2)[..., None]
    )
    diagonal_cofactor = (
        d0 * (j11 * j22 - m[..., 1, 2] * m[..., 2, 1])
        + d1 * (j00 * j22 - m[..., 0, 2] * m[..., 2, 0])
        + d2 * (j00 * j11 - m[..., 0, 1] * m[..., 1, 0])
    )
    quadratic = d0 * d1 * j22 + d0 * d2 * j11 + d1 * d2 * j00
    a3 = (
        a3_0[..., None] + x * diagonal_cofactor[..., None]
        - x * x * quadratic[..., None]
        + x * x * x * (d0 * d1 * d2)[..., None]
    )
    return (
        (a1 > TOL) & (a2 > TOL) & (a3 > TOL)
        & (a1 * a2 - a3 > TOL)
    )


def detect_n3_chunk(signs: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    b = signs.shape[0]
    rates = log_uniform(rng, (b, N3_DRAWS, 3, 3), RATE_LOW, RATE_HIGH)
    jacobians = signs[:, None, :, :] * rates
    stable = hurwitz3(jacobians)
    by_support = np.zeros((b, 7), dtype=bool)

    for support_code in range(1, 8):
        support = ((support_code >> np.arange(3)) & 1).astype(bool)
        diffusion = log_uniform(
            rng, (b, N3_DRAWS, 3), DIFFUSION_LOW, DIFFUSION_HIGH
        ) * support
        unstable = ~shifted_hurwitz3(jacobians, diffusion, K_VALUES)
        found = stable & np.any(unstable, axis=2)
        by_support[:, support_code - 1] = np.any(found, axis=1)
    return np.any(by_support, axis=1), by_support


def run_n3(rng: np.random.Generator) -> dict:
    total = 3**9
    capable = np.zeros(total, dtype=bool)
    capable_by_support = np.zeros((total, 7), dtype=bool)
    cyclic = np.zeros(total, dtype=bool)
    chunk_size = 128
    for start in range(0, total, chunk_size):
        stop = min(start + chunk_size, total)
        signs = signs_from_codes(np.arange(start, stop, dtype=np.int64), 3)
        chunk_capable, chunk_support = detect_n3_chunk(signs, rng)
        capable[start:stop] = chunk_capable
        capable_by_support[start:stop] = chunk_support
        cyclic[start:stop] = [has_directed_cycle(s) for s in signs]
    return {
        "patterns": total,
        "diffusion_supports_per_pattern": 7,
        "rate_draws_per_pattern_support": N3_DRAWS,
        "detected_capable_patterns": int(np.sum(capable)),
        "detected_capable_fraction": float(np.mean(capable)),
        "cyclic_patterns": int(np.sum(cyclic)),
        "detected_capable_cyclic_patterns": int(np.sum(capable & cyclic)),
        "detected_capable_fraction_cyclic": float(np.mean(capable[cyclic])),
        "detected_capable_by_support": [
            int(x) for x in np.sum(capable_by_support, axis=0)
        ],
    }


def sample_n4_patterns(rng: np.random.Generator) -> np.ndarray:
    selected: dict[int, np.ndarray] = {}
    maximum = 3**16
    while len(selected) < N4_PATTERNS:
        codes = rng.integers(0, maximum, size=2 * (N4_PATTERNS - len(selected)))
        for code, signs in zip(codes, signs_from_codes(codes, 4)):
            key = int(code)
            if key not in selected and has_directed_cycle(signs):
                selected[key] = signs
                if len(selected) == N4_PATTERNS:
                    break
    return np.stack(list(selected.values()))


def run_n4(rng: np.random.Generator) -> dict:
    signs = sample_n4_patterns(rng)
    supports = rng.integers(1, 16, size=N4_PATTERNS)
    support_mask = ((supports[:, None] >> np.arange(4)) & 1).astype(bool)
    rates = log_uniform(
        rng, (N4_PATTERNS, N4_DRAWS, 4, 4), RATE_LOW, RATE_HIGH
    )
    jacobians = signs[:, None, :, :] * rates
    diffusion = log_uniform(
        rng, (N4_PATTERNS, N4_DRAWS, 4), DIFFUSION_LOW, DIFFUSION_HIGH
    ) * support_mask[:, None, :]
    stable = hurwitz4(jacobians)
    capable = np.zeros(N4_PATTERNS, dtype=bool)
    pattern_index, draw_index = np.nonzero(stable)
    candidates = jacobians[pattern_index, draw_index]
    candidate_diffusion = diffusion[pattern_index, draw_index]
    active = np.ones(len(candidates), dtype=bool)
    for k in K_VALUES:
        if not np.any(active):
            break
        active_indices = np.flatnonzero(active)
        unstable = ~hurwitz4(shifted(
            candidates[active_indices], candidate_diffusion[active_indices], float(k)
        ))
        found_indices = active_indices[unstable]
        capable[pattern_index[found_indices]] = True
        found = np.zeros_like(active)
        found[found_indices] = True
        active &= ~found

    successes = int(np.sum(capable))
    lower, upper = clopper_pearson(successes, N4_PATTERNS)
    return {
        "sampled_distinct_cyclic_patterns": N4_PATTERNS,
        "rate_draws_per_pattern": N4_DRAWS,
        "detected_capable_patterns": successes,
        "detected_capable_fraction": successes / N4_PATTERNS,
        "clopper_pearson_95_interval": [lower, upper],
        "supports_sampled": {
            str(code): int(np.sum(supports == code)) for code in range(1, 16)
        },
        "stable_parameter_draws": int(np.sum(stable)),
    }


def main() -> None:
    rng = np.random.default_rng(SEED)
    output = {
        "seed": SEED,
        "definition": (
            "J is strictly Hurwitz by Routh-Hurwitz; for at least one tested "
            "k>0, J-k^2D is not strictly Hurwitz."
        ),
        "reaction_rate_range_log_uniform": [RATE_LOW, RATE_HIGH],
        "diffusion_range_log_uniform": [DIFFUSION_LOW, DIFFUSION_HIGH],
        "wave_number_grid_logspace": {
            "minimum": float(K_VALUES[0]),
            "maximum": float(K_VALUES[-1]),
            "count": len(K_VALUES),
        },
        "n3_baseline": run_n3(rng),
        "n4_sample": run_n4(rng),
    }
    destination = Path(__file__).with_name("derived") / "measurements.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
