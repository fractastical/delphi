#!/usr/bin/env python3
"""Seasonal condition of North Sea plaice at fixed length (claim ch03-18).

Reads derived/plaice_condition_week.csv (cells: quarter, week, sex, maturity group,
1-cm length class; n, sum of day-of-year, sum and sum of squares of log10 K, with
K = 100 W / L^3) and fits, by weighted least squares on cell means with weights n,
log10 K = a + b * day_of_year + length-class effects + sex effects.  Because every
fish in a cell shares the same regressor values except day-of-year (mean of the
week used), this reproduces individual-level OLS up to that within-week
approximation; residual variance is recovered from the within-cell sums of squares.
Pre-registered tests P1, P2, P3, M and verdict rules are in result.json."""
import json, os

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
LMIN, LMAX = 15, 55
MATURE = ("maturing", "spawning", "spent", "resting")


def wls(cells, y_sum, y_sq, X):
    n = cells["n"].to_numpy(float)
    ybar = cells[y_sum].to_numpy(float) / n
    W = np.sqrt(n)
    beta, *_ = np.linalg.lstsq(X * W[:, None], ybar * W, rcond=None)
    fitted = X @ beta
    ss_between = float(np.sum(n * (ybar - fitted) ** 2))
    ss_within = float(np.sum(cells[y_sq].to_numpy(float) - cells[y_sum].to_numpy(float) ** 2 / n))
    N = n.sum(); p = X.shape[1]
    sigma2 = (ss_between + ss_within) / (N - p)
    cov = sigma2 * np.linalg.pinv((X * n[:, None]).T @ X)
    return beta, np.sqrt(np.diag(cov)), int(N)


def design(cells, extra=None):
    cols = [np.ones(len(cells))]
    if extra is not None:
        cols.append(extra)
    for col in ("length_cm_class", "sex"):
        levels = sorted(cells[col].unique())
        for lv in levels[1:]:
            cols.append((cells[col] == lv).to_numpy(float))
    return np.column_stack(cols)


def slope_per_30d(cells):
    """Trend of log10 K with date, adjusted for length class and sex."""
    doy = cells["sum_doy"].to_numpy(float) / cells["n"].to_numpy(float)
    X = design(cells, extra=doy - doy.mean())
    beta, se, N = wls(cells, "sum_log10k", "sum_log10k_sq", X)
    b, s = 30 * beta[1], 30 * se[1]
    lo, hi = b - 1.96 * s, b + 1.96 * s
    return {"n_fish": N, "n_cells": int(len(cells)), "doy_range": [int(doy.min()), int(doy.max())],
            "slope_log10k_per_30d": round(float(b), 5), "se": round(float(s), 5),
            "ci95": [round(float(lo), 5), round(float(hi), 5)],
            "pct_change_K_per_30d": round(float((10 ** b - 1) * 100), 2),
            "pct_ci95": [round(float((10 ** lo - 1) * 100), 2), round(float((10 ** hi - 1) * 100), 2)],
            "p_two_sided": float(f"{2 * norm.sf(abs(b / s)):.3g}")}


def stage_contrast(cells, stage, ref="maturing"):
    """Mean log10 K of `stage` minus `ref`, adjusted for length class and sex."""
    sub = cells[cells.matgroup.isin([stage, ref])]
    X = design(sub, extra=(sub.matgroup == stage).to_numpy(float))
    beta, se, N = wls(sub, "sum_log10k", "sum_log10k_sq", X)
    d, s = beta[1], se[1]
    return {"n_fish": N, "n_stage": int(sub.loc[sub.matgroup == stage, "n"].sum()),
            "diff_log10k": round(float(d), 5), "ci95": [round(float(d - 1.96 * s), 5), round(float(d + 1.96 * s), 5)],
            "pct_K": round(float((10 ** d - 1) * 100), 2), "p_two_sided": float(f"{2 * norm.sf(abs(d / s)):.3g}")}


def quarter_contrast(cells, group):
    sub = cells[cells.matgroup.isin(group)]
    X = design(sub, extra=(sub.quarter == 3).to_numpy(float))
    beta, se, N = wls(sub, "sum_log10k", "sum_log10k_sq", X)
    d, s = beta[1], se[1]
    return {"n_fish": N, "q3_minus_q1_log10k": round(float(d), 5), "pct_K": round(float((10 ** d - 1) * 100), 2),
            "ci95_pct": [round(float((10 ** (d - 1.96 * s) - 1) * 100), 2), round(float((10 ** (d + 1.96 * s) - 1) * 100), 2)]}


def main():
    wk = pd.read_csv(os.path.join(HERE, "derived", "plaice_condition_week.csv"))
    wk = wk[(wk.length_cm_class >= LMIN) & (wk.length_cm_class <= LMAX)]
    out = {"counts": {g: int(wk.loc[wk.matgroup == g, "n"].sum()) for g in sorted(wk.matgroup.unique())}}
    for q in (1, 3):
        qc = wk[wk.quarter == q]
        out[f"Q{q}"] = {
            "mature_trend": slope_per_30d(qc[qc.matgroup.isin(MATURE)]),
            "immature_trend": slope_per_30d(qc[qc.matgroup == "immature"]),
            "by_stage_trend": {g: slope_per_30d(qc[qc.matgroup == g]) for g in sorted(qc.matgroup.unique())
                               if qc.loc[qc.matgroup == g, "n"].sum() >= 200},
            "by_sex_mature_trend": {s: slope_per_30d(qc[qc.matgroup.isin(MATURE) & (qc.sex == s)]) for s in ("F", "M")},
            "weekly_mean_log10k_mature_adjusted_note": "see weekly table below",
        }
    q1 = wk[wk.quarter == 1]
    out["Q1_stage_contrasts_vs_maturing"] = {st: stage_contrast(q1, st) for st in ("spawning", "spent", "resting", "immature")}
    out["Q3_vs_Q1_adjusted"] = {"mature": quarter_contrast(wk, MATURE), "immature": quarter_contrast(wk, ["immature"])}
    # Weekly profile (length- and sex-adjusted means are not needed for a picture; raw means at 25-35 cm shown).
    mid = wk[(wk.length_cm_class >= 25) & (wk.length_cm_class <= 35)]
    prof = mid.groupby(["quarter", "week", "matgroup"]).agg(n=("n", "sum"), s=("sum_log10k", "sum")).reset_index()
    prof["mean_K"] = (10 ** (prof.s / prof.n)).round(4)
    out["weekly_mean_K_25_35cm"] = {f"Q{q}": prof[(prof.quarter == q) & (prof.n >= 30)][["week", "matgroup", "n", "mean_K"]]
                                    .to_dict("records") for q in (1, 3)}
    # Year-by-year robustness of the Q3 - Q1 contrast (pre-registered as a check, not part of the verdict).
    yr = pd.read_csv(os.path.join(HERE, "derived", "plaice_condition_year.csv"))
    yr = yr[(yr.length_cm_class >= LMIN) & (yr.length_cm_class <= LMAX)]
    out["Q3_vs_Q1_by_year_pct_K"] = {}
    for y, g in yr.groupby("year"):
        row = {}
        for name, grp in (("mature", MATURE), ("immature", ["immature"])):
            sub = g[g.matgroup.isin(grp)]
            if sub.quarter.nunique() == 2 and sub.loc[sub.quarter == 3, "n"].sum() >= 50:
                row[name] = quarter_contrast(sub, grp)["pct_K"]
        out["Q3_vs_Q1_by_year_pct_K"][int(y)] = row
    # Verdict (pre-registered rules).
    m1 = out["Q1"]["mature_trend"]; i1 = out["Q1"]["immature_trend"]
    m3 = out["Q3"]["mature_trend"]; sp = out["Q1_stage_contrasts_vs_maturing"]["spent"]
    P1 = m1["ci95"][1] < 0 and m1["pct_change_K_per_30d"] <= -2.0
    P2 = m3["ci95"][0] > 0
    P3 = sp["diff_log10k"] <= -np.log10(1.05) and sp["ci95"][1] < 0
    ratio = i1["slope_log10k_per_30d"] / m1["slope_log10k_per_30d"] if m1["slope_log10k_per_30d"] != 0 else float("nan")
    imm_sig_decline = i1["ci95"][1] < 0
    M = (ratio < 0.5) or (not imm_sig_decline)
    P1_reversed = m1["ci95"][0] > 0
    if P1 and P2 and P3 and M:
        verdict = "supports"
    elif P1_reversed or (P1 and imm_sig_decline and ratio >= 0.8):
        verdict = "refutes"
    else:
        verdict = "mixed"
    out["tests"] = {"P1_mature_Q1_decline": bool(P1), "P2_mature_Q3_rise": bool(P2), "P3_spent_below_maturing": bool(P3),
                    "M_immature_decline_lt_half_of_mature_or_ns": bool(M), "immature_over_mature_Q1_slope_ratio": round(float(ratio), 3),
                    "immature_Q1_decline_significant": bool(imm_sig_decline), "P1_reversed": bool(P1_reversed), "verdict": verdict}
    print(json.dumps(out, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


if __name__ == "__main__":
    main()
