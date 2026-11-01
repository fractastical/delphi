"""Test of thompson1917-ch03-07 (weight varies as the cube of linear dimensions during growth) on NHANES 2013-2018.

Reads data/BMX_{H,I,J}.xpt and data/DEMO_{H,I,J}.xpt (run fetch.py first). Writes derived/age_bins.csv and derived/summary.json.
"""
import json
import os

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")


def load():
    parts = []
    for s in "HIJ":
        b = pd.read_sas(os.path.join(DATA, f"BMX_{s}.xpt"), format="xport")[["SEQN", "BMXWT", "BMXHT"]]
        d = pd.read_sas(os.path.join(DATA, f"DEMO_{s}.xpt"), format="xport")[["SEQN", "RIAGENDR", "RIDAGEYR", "WTMEC2YR"]]
        m = b.merge(d, on="SEQN")
        m["cycle"] = s
        parts.append(m)
    df = pd.concat(parts, ignore_index=True)
    df = df[(df["RIDAGEYR"] >= 2) & (df["RIDAGEYR"] <= 19) & df["BMXWT"].notna() & df["BMXHT"].notna() & (df["WTMEC2YR"] > 0)]
    return df


def per_sex(df):
    g = df.groupby("RIDAGEYR")
    w = g.apply(lambda x: np.average(x["BMXWT"], weights=x["WTMEC2YR"]), include_groups=False)
    h = g.apply(lambda x: np.average(x["BMXHT"], weights=x["WTMEC2YR"]), include_groups=False)
    n = g.size()
    bins = pd.DataFrame({"age": w.index.astype(int), "mean_weight_kg": w.values, "mean_height_cm": h.values, "n": n.values})
    lw, lh = np.log(bins["mean_weight_kg"]), np.log(bins["mean_height_cm"])
    free = stats.linregress(lh, lw)
    tcrit = stats.t.ppf(0.975, len(bins) - 2)
    logk = float(np.mean(lw - 3 * lh))
    pred = np.exp(logk) * bins["mean_height_cm"] ** 3
    ss_res = float(np.sum((bins["mean_weight_kg"] - pred) ** 2))
    ss_tot = float(np.sum((bins["mean_weight_kg"] - bins["mean_weight_kg"].mean()) ** 2))
    r2 = 1 - ss_res / ss_tot
    bins["cubic_model_weight_kg"] = pred.values
    return bins, {"n_participants": int(len(df)), "n_age_bins": int(len(bins)), "free_exponent_b": float(free.slope),
                  "b_ci95": [float(free.slope - tcrit * free.stderr), float(free.slope + tcrit * free.stderr)], "free_fit_r2_log": float(free.rvalue ** 2),
                  "cubic_k_kg_per_cm3": float(np.exp(logk)), "cubic_model_r2_original_scale": float(r2),
                  "height_range_cm": [float(bins["mean_height_cm"].min()), float(bins["mean_height_cm"].max())],
                  "weight_range_kg": [float(bins["mean_weight_kg"].min()), float(bins["mean_weight_kg"].max())]}


def main():
    os.makedirs(DERIVED, exist_ok=True)
    df = load()
    res, tables = {}, []
    for code, name in ((1, "male"), (2, "female")):
        bins, r = per_sex(df[df["RIAGENDR"] == code])
        bins.insert(0, "sex", name)
        tables.append(bins)
        r["passes"] = bool(2.5 <= r["free_exponent_b"] <= 3.5 and r["cubic_model_r2_original_scale"] >= 0.90)
        res[name] = r
    p = [res["male"]["passes"], res["female"]["passes"]]
    verdict = "supports" if all(p) else ("refutes" if not any(p) else "mixed")
    out = {"cycles": ["2013-2014", "2015-2016", "2017-2018"], "ages": "2-19 completed years", **res, "verdict": verdict}
    pd.concat(tables).to_csv(os.path.join(DERIVED, "age_bins.csv"), index=False)
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
