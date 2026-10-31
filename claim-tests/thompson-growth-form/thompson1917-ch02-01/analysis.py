#!/usr/bin/env python3
"""Is k = W / L^3 constant across the size range of growing fishes? (claim ch02-01)

Reads derived/ns_ibts_lw_bins.csv (per species x quarter x 1-cm length class: n,
sum and sum of squares of log10 W, after the pre-registered individual-level
cleaning in fetch.py).  For every eligible species fits
    log10 W = a + b1 x + b2 x^2,   x = log10 L  (L = class lower bound + 0.5 cm)
by weighted least squares on class means (weights n), which equals individual-level
OLS because every fish in a class shares the same L; the residual variance is
recovered from the within-class sums of squares.  Compares with the cube law
(b1 = 3, b2 = 0) by an F-test and measures the range of fitted k across the
species' 2.5th-97.5th percentile lengths.  Rules in result.json."""
import json, os

import numpy as np
import pandas as pd
from scipy.stats import f as fdist

HERE = os.path.dirname(os.path.abspath(__file__))
PLAICE = "127143"
# WoRMS names for the eligible Aphia IDs (looked up at https://www.marinespecies.org/rest/ on 2026-10-31).
NAMES = {"105814": "Scyliorhinus canicula", "105821": "Mustelus asterias", "105865": "Amblyraja radiata",
         "105883": "Raja clavata", "105923": "Squalus acanthias", "126417": "Clupea harengus",
         "126421": "Sardina pilchardus", "126436": "Gadus morhua", "126437": "Melanogrammus aeglefinus",
         "126438": "Merlangius merlangus", "126484": "Merluccius merluccius", "126555": "Lophius piscatorius",
         "127139": "Limanda limanda", "127143": "Pleuronectes platessa", "127160": "Solea solea",
         "135301": "Cyanea capillata (jellyfish)", "135302": "Cyanea lamarckii (jellyfish)",
         "135304": "Chrysaora hysoscella (jellyfish)", "150636": "Eutrigla (genus-level records)",
         "150637": "Eutrigla gurnardus"}
JELLYFISH = {"135301", "135302", "135304"}
MIN_N, MIN_RANGE, P_F, K_RATIO = 500, 3.0, 0.001, 1.10


def fit(cells):
    n = cells["n"].to_numpy(float); L = cells["length_cm_class"].to_numpy(float) + 0.5
    x = np.log10(L); ybar = cells["sum_log10w"].to_numpy(float) / n
    sq = cells["sum_log10w_sq"].to_numpy(float)
    N = n.sum()
    ss_within = float(np.sum(sq - cells["sum_log10w"].to_numpy(float) ** 2 / n))
    # Cube-law model: y - 3x = a  (one parameter).
    a0 = float(np.sum(n * (ybar - 3 * x)) / N)
    rss0 = float(np.sum(n * (ybar - 3 * x - a0) ** 2)) + ss_within
    # Quadratic model.
    xc = x - np.average(x, weights=n)
    X = np.column_stack([np.ones_like(x), xc, xc ** 2]); W = np.sqrt(n)
    beta, *_ = np.linalg.lstsq(X * W[:, None], ybar * W, rcond=None)
    fitted = X @ beta
    rss1 = float(np.sum(n * (ybar - fitted) ** 2)) + ss_within
    df1, df2 = 2, N - 3
    F = ((rss0 - rss1) / df1) / (rss1 / df2)
    p = float(fdist.sf(F, df1, df2))
    # Linear model slope b (for reporting).
    Xl = X[:, :2]
    bl, *_ = np.linalg.lstsq(Xl * W[:, None], ybar * W, rcond=None)
    rssl = float(np.sum(n * (ybar - Xl @ bl) ** 2)) + ss_within
    cov = (rssl / (N - 2)) * np.linalg.pinv((Xl * n[:, None]).T @ Xl)
    b, se_b = float(bl[1]), float(np.sqrt(cov[1, 1]))
    # Fitted k across central 95% of lengths (individual quantiles from class counts).
    order = np.argsort(L); cum = np.cumsum(n[order]) / N
    L_lo = L[order][np.searchsorted(cum, 0.025)]; L_hi = L[order][np.searchsorted(cum, 0.975)]
    grid = np.linspace(np.log10(L_lo), np.log10(L_hi), 200) - np.average(x, weights=n)
    logk = beta[0] + beta[1] * grid + beta[2] * grid ** 2 - 3 * (grid + np.average(x, weights=n))
    k_ratio = float(10 ** (logk.max() - logk.min()))
    k_peak_L = float(10 ** (grid[np.argmax(logk)] + np.average(x, weights=n)))
    return {"n": int(N), "L_2.5": float(L_lo), "L_97.5": float(L_hi), "range_ratio": round(float(L_hi / L_lo), 2),
            "b_linear": round(b, 4), "b_se": round(se_b, 4), "b_ci95": [round(b - 1.96 * se_b, 4), round(b + 1.96 * se_b, 4)],
            "quad_b1": round(float(beta[1]), 4), "quad_b2": round(float(beta[2]), 4),
            "F_vs_cube": round(float(F), 2), "p_vs_cube": float(f"{p:.3g}"), "k_max_over_k_min": round(k_ratio, 4),
            "k_peak_length_cm": round(k_peak_L, 1),
            "r2_linear": round(1 - rssl / (float(np.sum(n * (ybar - np.average(ybar, weights=n)) ** 2)) + ss_within), 4),
            "variable_k": bool(p < P_F and k_ratio >= K_RATIO)}


def main():
    bins = pd.read_csv(os.path.join(HERE, "derived", "ns_ibts_lw_bins.csv"), dtype={"aphia": str})
    pooled = bins.groupby(["aphia", "length_cm_class"]).agg(n=("n", "sum"), sum_log10w=("sum_log10w", "sum"),
                                                            sum_log10w_sq=("sum_log10w_sq", "sum")).reset_index()
    results = {}
    for sp, g in pooled.groupby("aphia"):
        if g["n"].sum() < MIN_N:
            continue
        r = fit(g)
        if r["range_ratio"] < MIN_RANGE:
            continue
        r["name"] = NAMES.get(sp, "")
        results[sp] = r
        for q in (1, 3):
            gq = bins[(bins.aphia == sp) & (bins.quarter == q)]
            if gq["n"].sum() >= MIN_N:
                rq = fit(gq)
                r[f"Q{q}"] = {k: rq[k] for k in ("n", "b_linear", "p_vs_cube", "k_max_over_k_min", "variable_k")}
    n_el = len(results); n_var = sum(r["variable_k"] for r in results.values())
    frac = n_var / n_el if n_el else float("nan")
    verdict = "inconclusive" if n_el < 10 else "supports" if frac >= 0.7 else "refutes" if frac <= 0.3 else "mixed"
    bs = np.array([r["b_linear"] for r in results.values()])
    within_q = [r[f"Q{q}"]["variable_k"] for r in results.values() for q in (1, 3) if f"Q{q}" in r]
    # Plaice k profile by 1-cm class (secondary, descriptive).
    pl = pooled[pooled.aphia == PLAICE].copy()
    pl["mean_k"] = 10 ** (pl.sum_log10w / pl.n) / (pl.length_cm_class + 0.5) ** 3 * 100
    pl5 = pl[pl.n >= 30].copy(); pl5["bin5"] = (pl5.length_cm_class // 5) * 5
    prof = pl5.groupby("bin5").apply(lambda g: float(np.average(g.mean_k, weights=g.n)), include_groups=False).round(4)
    pk = pl[pl.n >= 30]
    peak_L = float(pk.loc[pk.mean_k.idxmax(), "length_cm_class"]) if len(pk) else None
    fish = {sp: r for sp, r in results.items() if sp not in JELLYFISH}
    out = {"eligible_species": n_el,
           "fish_only_sensitivity": {"eligible": len(fish), "variable_k": int(sum(r["variable_k"] for r in fish.values())),
                                     "fraction": round(sum(r["variable_k"] for r in fish.values()) / len(fish), 3) if fish else None}, "variable_k_species": n_var, "fraction_variable_k": round(frac, 3),
           "b_linear_median": round(float(np.median(bs)), 3), "b_linear_range": [round(float(bs.min()), 3), round(float(bs.max()), 3)],
           "species_with_abs_b_minus_3_gt_0.1": int(np.sum(np.abs(bs - 3) > 0.1)),
           "species_cube_rejected_p_lt_0.001": int(sum(r["p_vs_cube"] < P_F for r in results.values())),
           "species_k_ratio_ge_1.10": int(sum(r["k_max_over_k_min"] >= K_RATIO for r in results.values())),
           "within_quarter_fits": {"n": len(within_q), "variable_k": int(sum(within_q))},
           "plaice": {"peak_k_1cm_class_with_n_ge_30": peak_L, "mean_k_by_5cm_bin": {int(k): v for k, v in prof.items()},
                      "fit": {k: v for k, v in results.get(PLAICE, {}).items() if k not in ("Q1", "Q3")}},
           "verdict": verdict, "species": results}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
