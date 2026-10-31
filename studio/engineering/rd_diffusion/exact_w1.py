"""Exact empirical 1-D Wasserstein-1 (area between empirical CDFs). The frozen pilot's 'W1' (rd_ddpm.py ens_metrics and marginals) is a midpoint-quantile approximation
with linear interpolation; it equals this only in special cases. This module is the separately registered secondary metric (see AMENDMENT_1.md); it replaces nothing."""

import numpy as np


def exact_w1(a, b) -> float:
    a, b = np.sort(np.asarray(a, float).ravel()), np.sort(np.asarray(b, float).ravel())
    if (
        a.size == 0
        or b.size == 0
        or not (np.isfinite(a).all() and np.isfinite(b).all())
    ):
        raise ValueError("exact_w1 needs non-empty finite samples")
    x = np.sort(np.concatenate([a, b]))
    fa = np.searchsorted(a, x[:-1], side="right") / a.size
    fb = np.searchsorted(b, x[:-1], side="right") / b.size
    return float((np.abs(fa - fb) * np.diff(x)).sum())
