#!/usr/bin/env python3
"""Download the CDC 2000 growth-chart LMS tables and the WHO 2007 height-for-age
reference (expanded monthly tables), record checksums, and write derived/lms.csv
(one row per source x sex x age with L, M, S).  Raw files go to data/ (git-ignored).
"""
import csv, hashlib, io, json, os, time

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")

FILES = {
    "statage.csv": "https://www.cdc.gov/growthcharts/data/zscore/statage.csv",
    "wtage.csv": "https://www.cdc.gov/growthcharts/data/zscore/wtage.csv",
    "lenageinf.csv": "https://www.cdc.gov/growthcharts/data/zscore/lenageinf.csv",
    "wtageinf.csv": "https://www.cdc.gov/growthcharts/data/zscore/wtageinf.csv",
    "hfa-boys-z-who-2007-exp.xlsx": "https://cdn.who.int/media/docs/default-source/child-growth/growth-reference-5-19-years/height-for-age-(5-19-years)/hfa-boys-z-who-2007-exp.xlsx",
    "hfa-girls-z-who-2007-exp.xlsx": "https://cdn.who.int/media/docs/default-source/child-growth/growth-reference-5-19-years/height-for-age-(5-19-years)/hfa-girls-z-who-2007-exp.xlsx",
}
# CDC tables: Sex 1 = male, 2 = female; Agemos in months.
CDC_SERIES = {"statage.csv": "cdc_stature", "wtage.csv": "cdc_weight",
              "lenageinf.csv": "cdc_infant_length", "wtageinf.csv": "cdc_infant_weight"}


def main():
    os.makedirs(DATA, exist_ok=True); os.makedirs(DERIVED, exist_ok=True)
    manifest = {}
    for name, url in FILES.items():
        path = os.path.join(DATA, name)
        r = requests.get(url, timeout=120); r.raise_for_status()
        open(path, "wb").write(r.content)
        manifest[name] = {"download_url": url,
                          "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                          "byte_size": len(r.content),
                          "sha256": hashlib.sha256(r.content).hexdigest()}
    rows = []
    for name, series in CDC_SERIES.items():
        df = pd.read_csv(os.path.join(DATA, name))
        df = df[df["Sex"].astype(str) != "Sex"]  # lenageinf.csv repeats its header line mid-file
        for _, r in df.iterrows():
            sex = {1: "M", 2: "F"}.get(int(r["Sex"]))
            if sex is None:
                continue
            rows.append([series, sex, float(r["Agemos"]) / 12.0, float(r["L"]), float(r["M"]), float(r["S"])])
    for sex, name in (("M", "hfa-boys-z-who-2007-exp.xlsx"), ("F", "hfa-girls-z-who-2007-exp.xlsx")):
        df = pd.read_excel(os.path.join(DATA, name))
        cols = {c.lower(): c for c in df.columns}
        for _, r in df.iterrows():
            rows.append(["who_height", sex, float(r[cols["month"]]) / 12.0, float(r[cols["l"]]), float(r[cols["m"]]), float(r[cols["s"]])])
    with open(os.path.join(DERIVED, "lms.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "sex", "age_years", "L", "M", "S"])
        for row in rows:
            w.writerow([row[0], row[1], f"{row[2]:.6f}", f"{row[3]:.9g}", f"{row[4]:.9g}", f"{row[5]:.9g}"])
    json.dump(manifest, open(os.path.join(DERIVED, "manifest.json"), "w"), indent=1)
    print(json.dumps(manifest, indent=1))
    print(len(rows), "rows")


if __name__ == "__main__":
    main()
