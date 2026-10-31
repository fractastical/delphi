"""Test of fisher-infinitesimal on Galton's 1886 family heights.

Reads data/GaltonFamilies.csv (run fetch.py first). Writes derived/children.csv and derived/summary.json.
Criteria (pre-registered): A homoscedastic residuals across mid-parent terciles; B near-normal residuals;
C sibling intraclass correlation >= implied single-parent-offspring correlation - 0.05.
"""
import json
import os

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "GaltonFamilies.csv")
DERIVED = os.path.join(HERE, "derived")


def icc_oneway(groups):
    """One-way random-effects intraclass correlation (ANOVA estimator) for unequal group sizes."""
    k = len(groups)
    n_i = np.array([len(g) for g in groups], dtype=float)
    N = n_i.sum()
    grand = np.concatenate(groups).mean()
    means = np.array([g.mean() for g in groups])
    ssb = float(np.sum(n_i * (means - grand) ** 2))
    ssw = float(sum(np.sum((g - m) ** 2) for g, m in zip(groups, means)))
    msb = ssb / (k - 1)
    msw = ssw / (N - k)
    n0 = (N - np.sum(n_i ** 2) / N) / (k - 1)
    return float((msb - msw) / (msb + (n0 - 1) * msw)), float(n0), int(k)


def main():
    os.makedirs(DERIVED, exist_ok=True)
    d = pd.read_csv(DATA, dtype={"family": str})
    d["adj_child"] = np.where(d["gender"].str.lower().str.startswith("f"), d["childHeight"] * 1.08, d["childHeight"])
    d["midparent"] = (d["father"] + 1.08 * d["mother"]) / 2
    ols = stats.linregress(d["midparent"], d["adj_child"])
    d["resid"] = d["adj_child"] - (ols.intercept + ols.slope * d["midparent"])
    d["tercile"] = pd.qcut(d["midparent"], 3, labels=["low", "mid", "high"])
    groups = [d.loc[d["tercile"] == t, "resid"].to_numpy() for t in ["low", "mid", "high"]]
    lev_stat, lev_p = stats.levene(*groups, center="median")
    var_t = [float(np.var(g, ddof=1)) for g in groups]
    var_ratio = max(var_t) / min(var_t)
    g1 = float(stats.skew(d["resid"], bias=False))
    g2 = float(stats.kurtosis(d["resid"], bias=False))
    r_mp = float(ols.rvalue)
    r_po_implied = r_mp / np.sqrt(2)
    fam = d.groupby("family")["adj_child"].apply(lambda s: s.to_numpy())
    fam = fam[fam.apply(len) >= 2]
    icc, n0, k = icc_oneway(list(fam))
    # Direct single-parent correlations, for reference (not part of the criterion).
    r_father = float(stats.pearsonr(d["father"], d["adj_child"])[0])
    r_mother = float(stats.pearsonr(1.08 * d["mother"], d["adj_child"])[0])
    r_parents = float(stats.pearsonr(d.drop_duplicates("family")["father"], 1.08 * d.drop_duplicates("family")["mother"])[0])
    A = lev_p > 0.05 and var_ratio < 1.5
    B = abs(g1) < 0.5 and abs(g2) < 1.0
    C = icc >= r_po_implied - 0.05
    A_strong_fail = var_ratio > 2 or lev_p < 0.001
    B_strong_fail = abs(g1) > 1 or abs(g2) > 2
    C_strong_fail = icc < r_po_implied - 0.15
    if A and B and C:
        verdict = "supports"
    elif A_strong_fail or B_strong_fail or C_strong_fail:
        verdict = "refutes"
    else:
        verdict = "mixed"
    summary = {
        "n_children": int(len(d)), "n_families": int(d["family"].nunique()), "n_families_with_2plus": k,
        "ols_slope_child_on_midparent": float(ols.slope), "r_midparent": r_mp, "r_po_implied": float(r_po_implied),
        "r_father_child": r_father, "r_mother_child": r_mother, "r_father_mother": r_parents,
        "levene_p": float(lev_p), "tercile_resid_variances": var_t, "variance_ratio_max_over_min": float(var_ratio),
        "resid_skew_g1": g1, "resid_excess_kurtosis_g2": g2, "resid_sd": float(d["resid"].std(ddof=1)),
        "sibling_icc": icc, "icc_n0": n0,
        "criterion_A": bool(A), "criterion_B": bool(B), "criterion_C": bool(C), "verdict": verdict,
    }
    d[["family", "father", "mother", "midparent", "gender", "childHeight", "adj_child", "resid", "tercile"]].to_csv(os.path.join(DERIVED, "children.csv"), index=False)
    json.dump(summary, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
