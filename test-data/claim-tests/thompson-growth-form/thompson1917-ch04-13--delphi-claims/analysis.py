"""Test of thompson1917-ch04-13 (germ-nucleus chromosome numbers mostly 6 to 16) on the Chromosome Counts Database (plants).

Reads data/ccdb_statistics_<group>.csv (run fetch.py first): one row per resolved species name with the median count.
CCDB 'statistics' counts are at the gametophytic (n) level (checked on reference species listed in derived/summary.json).
Writes derived/n_distribution.csv and derived/summary.json.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
GROUPS = ["Angiosperms", "Gymnosperms", "Pteridophytes", "Bryophytes"]
# Species with well-known haploid numbers, used only to confirm which level the 'median' column reports.
REFERENCE = {"Arabidopsis thaliana": 5, "Zea mays": 10, "Triticum aestivum": 21, "Oryza sativa": 12, "Pinus sylvestris": 12, "Abies alba": 12}


def main():
    os.makedirs(DERIVED, exist_ok=True)
    parts = []
    for g in GROUPS:
        d = pd.read_csv(os.path.join(DATA, f"ccdb_statistics_{g}.csv"))
        d["group"] = g
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    df["n"] = pd.to_numeric(df["median"], errors="coerce")
    df = df[df["n"].notna() & (df["n"] > 0)].drop_duplicates(subset="resolved_name")
    ref_check = {sp: (float(df.loc[df["resolved_name"] == sp, "n"].iloc[0]) if (df["resolved_name"] == sp).any() else None) for sp in REFERENCE}
    level_ok = sum(1 for sp, v in ref_check.items() if v is not None and abs(v - REFERENCE[sp]) < 0.5)
    level_2n = sum(1 for sp, v in ref_check.items() if v is not None and abs(v - 2 * REFERENCE[sp]) < 0.5)
    note = "median column matches haploid n on reference species" if level_ok > level_2n else "median column looks like 2n; halved"
    if level_2n > level_ok:
        df["n"] = df["n"] / 2
    n = df["n"].to_numpy()
    tot = len(n)
    in_range = float(np.mean((n >= 6) & (n <= 16)))
    below = float(np.mean(n < 6))
    above = float(np.mean(n > 16))
    a = in_range >= 0.70
    b = below < 0.15
    c = above < below
    if a and b and c:
        verdict = "supports"
    elif in_range < 0.50 or above >= below or above >= 0.15:
        verdict = "refutes"
    else:
        verdict = "mixed"
    by_group = df.groupby("group")["n"].agg(count="size", median="median", frac_6_16=lambda x: float(np.mean((x >= 6) & (x <= 16))),
                                            frac_below_6=lambda x: float(np.mean(x < 6)), frac_above_16=lambda x: float(np.mean(x > 16)))
    # Post-hoc sensitivity (added after the pre-registered result, at the hub's request to enumerate readings; not part of the rule):
    # (i) lowest count per species instead of the median, which removes polyploid cytotypes within a species;
    # (ii) one value per genus (median of species medians), which damps polyploid species radiations.
    df["n_min"] = pd.to_numeric(df["minimum"], errors="coerce")
    if level_2n > level_ok:
        df["n_min"] = df["n_min"] / 2
    nm = df["n_min"].dropna().to_numpy()
    df["genus"] = df["resolved_name"].astype(str).str.split().str[0]
    gen = df.groupby("genus")["n"].median().to_numpy()
    sensitivity = {
        "min_count_per_species": {"n": int(len(nm)), "fraction_6_to_16": float(np.mean((nm >= 6) & (nm <= 16))), "fraction_below_6": float(np.mean(nm < 6)), "fraction_above_16": float(np.mean(nm > 16))},
        "genus_level_median": {"n_genera": int(len(gen)), "fraction_6_to_16": float(np.mean((gen >= 6) & (gen <= 16))), "fraction_below_6": float(np.mean(gen < 6)), "fraction_above_16": float(np.mean(gen > 16))},
        "angiosperms_only_species": {"fraction_above_16": float(np.mean(df.loc[df["group"] == "Angiosperms", "n"] > 16)), "fraction_below_6": float(np.mean(df.loc[df["group"] == "Angiosperms", "n"] < 6))},
    }
    for k, v in sensitivity.items():
        v["would_refute_under_rule"] = bool(v["fraction_above_16"] >= v["fraction_below_6"] or v["fraction_above_16"] >= 0.15 or v.get("fraction_6_to_16", 1) < 0.5)
    hist = df["n"].clip(upper=60).round().astype(int).value_counts().sort_index()
    pd.DataFrame({"n_capped_at_60": hist.index, "species": hist.values}).to_csv(os.path.join(DERIVED, "n_distribution.csv"), index=False)
    out = {"n_species_with_count": int(tot), "fraction_6_to_16": in_range, "fraction_below_6": below, "fraction_above_16": above,
           "median_n": float(np.median(n)), "mode_n": int(hist.idxmax()), "n_quantiles_5_25_50_75_95": [float(x) for x in np.percentile(n, [5, 25, 50, 75, 95])],
           "reference_species_check": ref_check, "count_level_note": note, "by_group": by_group.reset_index().to_dict("records"),
           "criterion_a": bool(a), "criterion_b": bool(b), "criterion_c": bool(c), "verdict": verdict, "post_hoc_sensitivity": sensitivity}
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
