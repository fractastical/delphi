#!/usr/bin/env python3
"""thompson1917-ch14-05: do parastichy numbers rise with the size of the sunflower head?

Data: derived/sunflower_counts.csv (from fetch.py; Turing's Sunflowers, Dryad doi:10.5061/dryad.f9k77).
Head size = grower-reported Head.diameter (cm). Parastichy pair = photoreviewed counts where
both are present and form an adjacent Fibonacci-type pair, otherwise the submitter's counts.
"""
import json
import os
import re

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, kruskal

HERE = os.path.dirname(os.path.abspath(__file__))

SEQS = {
    "Fibonacci": [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233],
    "Lucas": [1, 3, 4, 7, 11, 18, 29, 47, 76, 123, 199],
    "double Fibonacci": [2, 4, 6, 10, 16, 26, 42, 68, 110, 178],
    "F4": [1, 4, 5, 9, 14, 23, 37, 60, 97, 157],
}
ADJACENT = {}
for name, s in SEQS.items():
    for a, b in zip(s, s[1:]):
        if a >= 2:
            ADJACENT[(a, b)] = name


def parse_count(x):
    if pd.isna(x):
        return np.nan
    if isinstance(x, (int, float, np.integer, np.floating)):
        return int(x) if float(x).is_integer() else np.nan
    m = re.match(r"^\s*(\d+)\s*(\(.*)?$", str(x))
    return int(m.group(1)) if m else np.nan


def pair_of(a, b):
    a, b = parse_count(a), parse_count(b)
    if np.isnan(a) or np.isnan(b) or a == b:
        return None
    lo, hi = sorted([int(a), int(b)])
    return (lo, hi, ADJACENT[(lo, hi)]) if (lo, hi) in ADJACENT else None


def main():
    df = pd.read_csv(os.path.join(HERE, "derived", "sunflower_counts.csv"))
    rows = []
    for _, r in df.iterrows():
        if pd.isna(r["Head.diameter"]):
            continue
        p = pair_of(r["JS.P1"], r["JS.P2"])
        src = "photoreviewed"
        if p is None:
            p = pair_of(r["Public.Count.CW"], r["Public.Count.CCW"])
            src = "submitter"
        if p is None:
            continue
        rows.append({"ID": r["ID"], "diameter_cm": float(r["Head.diameter"]), "lo": p[0], "hi": p[1],
                     "seq": p[2], "pair": f"{p[0]}/{p[1]}", "source": src})
    d = pd.DataFrame(rows)

    rho, pval = spearmanr(d["diameter_cm"], d["hi"])
    out = {"n_heads": len(d), "n_photoreviewed": int((d.source == "photoreviewed").sum()),
           "n_submitter_only": int((d.source == "submitter").sum()),
           "spearman_rho_diameter_vs_larger_parastichy": round(float(rho), 4),
           "spearman_p": float(f"{pval:.3g}")}

    ph = d[d.source == "photoreviewed"]
    rho2, p2 = spearmanr(ph["diameter_cm"], ph["hi"])
    out["photoreviewed_only"] = {"n": len(ph), "rho": round(float(rho2), 4), "p": float(f"{p2:.3g}")}

    fib = d[d.seq == "Fibonacci"]
    classes = {}
    for pair, g in fib.groupby("hi"):
        classes[f"{g.lo.iloc[0]}/{pair}"] = {"n": len(g), "median_cm": float(g.diameter_cm.median()),
                                             "q1_cm": float(g.diameter_cm.quantile(.25)),
                                             "q3_cm": float(g.diameter_cm.quantile(.75)),
                                             "hi": int(pair)}
    out["fibonacci_pair_classes"] = classes
    big = [v for v in sorted(classes.values(), key=lambda v: v["hi"]) if v["n"] >= 10]
    medians = [v["median_cm"] for v in big]
    monotone = all(x < y for x, y in zip(medians, medians[1:]))
    out["classes_n_ge_10_in_order"] = [f"{v['hi']}:{v['median_cm']}" for v in big]
    out["median_diameter_monotone_increasing"] = monotone
    if len(big) >= 2:
        kw = kruskal(*[fib[fib.hi == v["hi"]].diameter_cm for v in big])
        out["kruskal_wallis_across_classes"] = {"H": round(float(kw.statistic), 3), "p": float(f"{kw.pvalue:.3g}")}

    # the classes Thompson names
    out["thompson_named_pairs_median_cm"] = {k: classes[k]["median_cm"] for k in ("34/55", "55/89", "89/144") if k in classes}

    if len(d) < 50:
        verdict = "inconclusive (underpowered)"
    elif rho >= 0.30 and pval < 0.01 and monotone:
        verdict = "supports"
    elif rho <= 0.10 or pval >= 0.05 or not monotone:
        verdict = "refutes"
    else:
        verdict = "mixed"
    out["verdict"] = verdict
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
