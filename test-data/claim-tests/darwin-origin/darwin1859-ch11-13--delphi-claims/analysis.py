"""Test of darwin1859-ch11-13 (long, world-wide Glacial period) on the LR04 benthic d18O stack and the EPICA Dome C temperature record.

Reads data/LR04stack.txt and data/edc3deuttemp2007.txt (run fetch.py first). Writes derived/cold_intervals.csv and derived/summary.json.
"""
import json
import os
import re

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")


def read_lr04():
    rows = []
    for line in open(os.path.join(DATA, "LR04stack.txt"), encoding="utf-8", errors="replace"):
        p = line.strip().split("\t")
        if len(p) >= 2:
            try:
                rows.append((float(p[0]), float(p[1])))
            except ValueError:
                continue
    a = np.array(rows)
    return a[:, 0], a[:, 1]  # age ka, d18O per mil


def read_edc():
    rows = []
    started = False
    for line in open(os.path.join(DATA, "edc3deuttemp2007.txt"), encoding="utf-8", errors="replace"):
        if re.match(r"\s*Bag\s+ztop\s+Age", line):
            started = True
            continue
        if not started:
            continue
        p = line.split()
        if len(p) >= 5:
            try:
                rows.append((float(p[2]) / 1000.0, float(p[4])))  # age in ka BP, temperature anomaly
            except ValueError:
                continue
    a = np.array(rows)
    a = a[np.argsort(a[:, 0])]
    return a[:, 0], a[:, 1]


def main():
    os.makedirs(DERIVED, exist_ok=True)
    t, o = read_lr04()
    grid = np.arange(0, 2600 + 1)
    og = np.interp(grid, t, o)
    cold = og >= 4.0
    frac_cold = float(cold.mean())
    # contiguous intervals >= 4.0 per mil
    intervals = []
    start = None
    for i, c in enumerate(cold):
        if c and start is None:
            start = i
        if (not c or i == len(cold) - 1) and start is not None:
            end = i if c else i - 1
            intervals.append((int(grid[start]), int(grid[end]), int(grid[end] - grid[start] + 1)))
            start = None
    long_intervals = [iv for iv in intervals if iv[2] >= 10]
    lgm = float(og[(grid >= 18) & (grid <= 26)].mean())
    # criterion C: Antarctic temperature vs -d18O, 0-800 ka, lags -6..+6 kyr
    te, Te = read_edc()
    g2 = np.arange(0, 800 + 1)
    Tg = np.interp(g2, te, Te)
    neg_o = -np.interp(g2, t, o)
    best = None
    for lag in range(-6, 7):
        if lag >= 0:
            x, y = Tg[lag:], neg_o[: len(neg_o) - lag]
        else:
            x, y = Tg[: len(Tg) + lag], neg_o[-lag:]
        r = float(np.corrcoef(x, y)[0, 1])
        if best is None or r > best[1]:
            best = (lag, r)
    r0 = float(np.corrcoef(Tg, neg_o)[0, 1])
    A = frac_cold >= 0.20 and len(long_intervals) >= 5
    B = lgm >= 4.5
    C = best[1] >= 0.6
    if A and B and C:
        verdict = "supports"
    elif frac_cold < 0.10 or len(long_intervals) < 2 or lgm < 4.2 or best[1] < 0.3:
        verdict = "refutes"
    else:
        verdict = "mixed"
    out = {"lr04_n_points": int(len(t)), "lr04_age_range_ka": [float(t.min()), float(t.max())],
           "fraction_0_2600ka_d18O_ge_4": frac_cold, "n_contiguous_intervals_ge_4": len(intervals), "n_intervals_ge_4_lasting_ge_10kyr": len(long_intervals),
           "longest_cold_interval_kyr": max((iv[2] for iv in intervals), default=0), "mean_d18O_18_26ka": lgm,
           "edc_n_points": int(len(te)), "edc_age_range_ka": [float(te.min()), float(te.max())],
           "corr_edc_temp_vs_neg_d18O_0_800ka_lag0": r0, "max_lagged_corr": best[1], "best_lag_kyr_edc_relative_to_lr04": best[0],
           "criterion_A": bool(A), "criterion_B": bool(B), "criterion_C": bool(C), "verdict": verdict}
    pd.DataFrame(intervals, columns=["start_ka", "end_ka", "duration_kyr"]).to_csv(os.path.join(DERIVED, "cold_intervals.csv"), index=False)
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
