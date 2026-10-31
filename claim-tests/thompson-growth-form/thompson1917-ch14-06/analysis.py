#!/usr/bin/env python3
"""thompson1917-ch14-06: are the two chiralities of a parastichy pair about equally frequent?

Data: derived/sunflower_counts.csv (from fetch.py; Turing's Sunflowers, Dryad doi:10.5061/dryad.f9k77).
Primary: photoreviewed counts JS.P1/JS.P2 with handedness H1/H2 (cw / ccw as seen on the
photographed seed face). Secondary: submitter counts (Public.Count.CW / .CCW).
A head is "right-handed" when its larger parastichy family runs clockwise.
"""
import json
import os
import re

import numpy as np
import pandas as pd
from scipy.stats import binomtest

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
        if a >= 2:  # (1,2),(1,3),(1,4) are not sunflower pairs
            ADJACENT[(a, b)] = name


def parse_count(x):
    """'56(-1)' -> 56 ; '34 (+1,2)' -> 34 ; 'u'/ranges -> NaN (the authors' torange())."""
    if pd.isna(x):
        return np.nan
    if isinstance(x, (int, float, np.integer, np.floating)):
        return int(x) if float(x).is_integer() else np.nan
    m = re.match(r"^\s*(\d+)\s*(\(.*)?$", str(x))
    return int(m.group(1)) if m else np.nan


def pairs_from(df, c1, h1, c2, h2):
    rows = []
    for _, r in df.iterrows():
        a, b = parse_count(r[c1]), parse_count(r[c2])
        ha, hb = r[h1], r[h2]
        if np.isnan(a) or np.isnan(b) or pd.isna(ha) or pd.isna(hb) or a == b:
            continue
        lo, hi = sorted([int(a), int(b)])
        if (lo, hi) not in ADJACENT:
            continue
        dir_larger = ha if a > b else hb
        if dir_larger not in ("cw", "ccw"):
            continue
        rows.append({"ID": r["ID"], "pair": f"{lo}/{hi}", "seq": ADJACENT[(lo, hi)],
                     "right_handed": dir_larger == "cw"})
    return pd.DataFrame(rows)


def summarise(p):
    n = len(p)
    k = int(p["right_handed"].sum())
    bt = binomtest(k, n, 0.5)
    ci = bt.proportion_ci(confidence_level=0.95, method="exact")
    return {"n": n, "right_handed": k, "left_handed": n - k, "p_right": round(k / n, 4),
            "binomial_p_two_sided": float(f"{bt.pvalue:.3g}"),
            "ci95": [round(ci.low, 4), round(ci.high, 4)]}


def main():
    df = pd.read_csv(os.path.join(HERE, "derived", "sunflower_counts.csv"), dtype={"H1": "string", "H2": "string"})
    df["H1"] = df["H1"].str.strip()
    df["H2"] = df["H2"].str.strip()

    primary = pairs_from(df, "JS.P1", "H1", "JS.P2", "H2")
    pub = df.copy()
    pub["cw"] = "cw"
    pub["ccw"] = "ccw"
    secondary = pairs_from(pub, "Public.Count.CW", "cw", "Public.Count.CCW", "ccw")

    out = {"primary_photoreviewed": {"pooled": summarise(primary), "by_pair": {}},
           "secondary_submitter": {"pooled": summarise(secondary), "by_pair": {}}}
    for key, p in (("primary_photoreviewed", primary), ("secondary_submitter", secondary)):
        for pair, grp in p.groupby("pair"):
            out[key]["by_pair"][pair] = summarise(grp)
        out[key]["by_pair"] = dict(sorted(out[key]["by_pair"].items(), key=lambda kv: -kv[1]["n"]))

    # Pre-registered decision on the primary, pooled sample and classes with n >= 20
    pooled = out["primary_photoreviewed"]["pooled"]
    dev = abs(pooled["p_right"] - 0.5)
    big = {k: v for k, v in out["primary_photoreviewed"]["by_pair"].items() if v["n"] >= 20}
    class_ok = all(abs(v["p_right"] - 0.5) <= 0.15 or v["binomial_p_two_sided"] >= 0.05 for v in big.values())
    top2 = list(out["primary_photoreviewed"]["by_pair"].items())[:2]
    top2_fail = all(abs(v["p_right"] - 0.5) > 0.10 and v["binomial_p_two_sided"] < 0.01 for _, v in top2)
    if pooled["n"] < 100:
        verdict = "inconclusive (underpowered)"
    elif dev <= 0.10 and pooled["binomial_p_two_sided"] >= 0.05 and class_ok:
        verdict = "supports"
    elif (dev > 0.10 and pooled["binomial_p_two_sided"] < 0.01) or top2_fail:
        verdict = "refutes"
    else:
        verdict = "mixed"
    out["decision"] = {"pooled_abs_deviation_from_half": round(dev, 4), "classes_n_ge_20_pass": class_ok,
                       "top2_classes_fail": top2_fail, "verdict": verdict}
    out["thompson_1917_spruce_for_comparison"] = {"right": 224, "left": 243, "n": 467,
                                                   "p_right": round(224 / 467, 4),
                                                   "binomial_p_two_sided": float(f"{binomtest(224, 467, 0.5).pvalue:.3g}")}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
