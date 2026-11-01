"""Test of maynardsmith-war-of-attrition on Trichonephila clavipes contest durations (Dryad doi:10.5061/dryad.bg79cnpjg, fight.csv).

Runs only if data/fight.csv is present (Dryad blocks scripted download; see fetch.py). Columns are matched by meaning:
a contest-duration column (seconds) and an escalation / physical-contact indicator; only non-escalated contests are used.
Test: Kolmogorov-Smirnov distance to an exponential with the sample-mean rate, p-value from 10,000 parametric bootstrap
replicates (Lilliefors-type), plus the coefficient of variation. Writes derived/summary.json.
"""
import json
import os
import re

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "data", "fight.csv")
DERIVED = os.path.join(HERE, "derived")
B = 10_000


def find_col(cols, *patterns):
    for p in patterns:
        for c in cols:
            if re.search(p, str(c), re.I):
                return c
    return None


def ks_exp(x):
    return stats.kstest(x, "expon", args=(0, x.mean())).statistic


def main():
    os.makedirs(DERIVED, exist_ok=True)
    if not os.path.exists(CSV):
        out = {"verdict": "inconclusive", "reason": "data-unavailable", "note": "data/fight.csv not present; Dryad blocks scripted download"}
        json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1); print(json.dumps(out, indent=1)); return
    df = pd.read_csv(CSV)
    cols = list(df.columns)
    dur = find_col(cols, r"duration", r"time", r"length")
    esc = find_col(cols, r"escalat", r"contact", r"physical", r"phase")
    if dur is None:
        out = {"verdict": "inconclusive", "reason": "not-operationalizable", "columns": list(map(str, cols))}
        json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1); print(json.dumps(out, indent=1)); return
    x_all = pd.to_numeric(df[dur], errors="coerce")
    if esc is not None:
        e = df[esc]
        non_esc = ~(e.astype(str).str.contains(r"^(1|yes|true|y|escalat|contact)", case=False, regex=True)) if e.dtype == object else (pd.to_numeric(e, errors="coerce") == 0)
        x = x_all[non_esc]
        sel = f"non-escalated contests by column '{esc}'"
    else:
        x = x_all; sel = "no escalation column found; all contests used"
    x = x.dropna().to_numpy(dtype=float)
    x = x[x > 0]
    n = len(x)
    if n < 20:
        out = {"verdict": "inconclusive", "reason": "underpowered", "n": int(n), "selection": sel}
        json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1); print(json.dumps(out, indent=1)); return
    rng = np.random.default_rng(20261031)
    d_obs = ks_exp(x)
    boots = np.array([ks_exp(rng.exponential(x.mean(), n)) for _ in range(B)])
    p = float((np.sum(boots >= d_obs) + 1) / (B + 1))
    cv = float(x.std(ddof=1) / x.mean())
    if p > 0.05 and 0.7 <= cv <= 1.3:
        verdict = "supports"
    elif p < 0.01 and (cv < 0.5 or cv > 1.5):
        verdict = "refutes"
    else:
        verdict = "mixed"
    out = {"duration_column": dur, "escalation_column": esc, "selection": sel, "n": int(n), "n_all_contests": int(x_all.notna().sum()), "mean_duration": float(x.mean()),
           "median_duration": float(np.median(x)), "min_duration": float(x.min()), "ks_statistic": float(d_obs), "bootstrap_p": p, "coefficient_of_variation": cv, "verdict": verdict}
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
