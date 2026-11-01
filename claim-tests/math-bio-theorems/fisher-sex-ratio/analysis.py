"""Test of fisher-sex-ratio: is the human sex ratio at birth close to 1:1 and uniform across populations, 1950-1979?

Reads data/WPP2024_Demographic_Indicators_Medium.csv.gz (run fetch.py first). Writes derived/country_years.csv and
derived/summary.json. SRB is males per 100 female births as published by the UN.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "WPP2024_Demographic_Indicators_Medium.csv.gz")
DERIVED = os.path.join(HERE, "derived")


def main():
    os.makedirs(DERIVED, exist_ok=True)
    d = pd.read_csv(DATA, low_memory=False, usecols=["LocID", "ISO3_code", "Location", "LocTypeName", "Time", "TPopulation1July", "SRB"])
    d = d[(d["LocTypeName"] == "Country/Area") & (d["Time"] >= 1950) & (d["Time"] <= 1979)].copy()
    d["TPopulation1July"] = pd.to_numeric(d["TPopulation1July"], errors="coerce")  # thousands
    d["SRB"] = pd.to_numeric(d["SRB"], errors="coerce")
    d = d[(d["TPopulation1July"] >= 1000) & d["SRB"].notna()].copy()
    srb = d["SRB"].to_numpy()
    med = float(np.median(srb))
    in_90_110 = float(np.mean((srb >= 90) & (srb <= 110)))
    in_95_105 = float(np.mean((srb >= 95) & (srb <= 105)))
    a = 95 <= med <= 105
    b = in_90_110 >= 0.95
    if a and b:
        verdict = "supports"
    elif not (90 <= med <= 110) or in_90_110 < 0.80:
        verdict = "refutes"
    else:
        verdict = "mixed"
    by_country = d.groupby(["LocID", "Location"])["SRB"].agg(["mean", "min", "max", "count"]).reset_index()
    summary = {
        "n_country_years": int(len(d)),
        "n_countries": int(d["LocID"].nunique()),
        "years": [int(d["Time"].min()), int(d["Time"].max())],
        "srb_median": med,
        "srb_mean": float(srb.mean()),
        "srb_sd": float(srb.std(ddof=1)),
        "srb_min": float(srb.min()),
        "srb_max": float(srb.max()),
        "srb_p05": float(np.percentile(srb, 5)),
        "srb_p95": float(np.percentile(srb, 95)),
        "fraction_in_90_110": in_90_110,
        "fraction_in_95_105": in_95_105,
        "criterion_A_median_in_95_105": bool(a),
        "criterion_B_95pct_in_90_110": bool(b),
        "country_means_min": float(by_country["mean"].min()),
        "country_means_max": float(by_country["mean"].max()),
        "verdict": verdict,
    }
    d[["LocID", "ISO3_code", "Location", "Time", "TPopulation1July", "SRB"]].to_csv(os.path.join(DERIVED, "country_years.csv"), index=False)
    by_country.to_csv(os.path.join(DERIVED, "country_means.csv"), index=False)
    json.dump(summary, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
