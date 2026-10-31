#!/usr/bin/env python3
"""thompson1917-ch03-07: weight tends to vary as the cube of stature during growth (NHANES 2007-2018).

Fits log weight on log stature across individuals aged 0-19 and on the age-median curve, and
measures how much of the shape difference between the normalised stature and weight curves is
removed by cubing the stature curve. Writes derived/measured.json and derived/files.json.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

CYCLES = [("2007", "E"), ("2009", "F"), ("2011", "G"), ("2013", "H"), ("2015", "I"), ("2017", "J")]
BASE = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{name}_{suffix}.xpt"


def fetch(url, dest):
    if not os.path.exists(dest):
        r = requests.get(url, timeout=300, headers={"User-Agent": "delphi-claim-tests/1.0"})
        r.raise_for_status()
        with open(dest, "wb") as fh:
            fh.write(r.content)
        retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        retrieved = datetime.fromtimestamp(os.path.getmtime(dest), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    h = hashlib.sha256()
    with open(dest, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return {"download_url": url, "retrieved_at": retrieved, "byte_size": os.path.getsize(dest), "sha256": h.hexdigest()}


def load_nhanes():
    files = {"demo": [], "bmx": []}
    frames = []
    for year, suf in CYCLES:
        parts = {}
        for name in ("DEMO", "BMX"):
            url = BASE.format(year=year, name=name, suffix=suf)
            dest = os.path.join(DATA, f"{name}_{suf}.xpt")
            files[name.lower()].append(fetch(url, dest))
            parts[name] = pd.read_sas(dest, format="xport")
        d = parts["DEMO"]
        if "RIDEXAGM" in d.columns:
            agem = d["RIDEXAGM"].where(d["RIDEXAGM"].notna(), d["RIDAGEMN"])
        else:
            agem = d["RIDAGEMN"]
        d = pd.DataFrame({"SEQN": d["SEQN"], "sex": d["RIAGENDR"], "agem": agem})
        frames.append(d.merge(parts["BMX"][["SEQN", "BMXWT", "BMXHT", "BMXRECUM"]], on="SEQN", how="inner"))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["agem"].notna() & (df["agem"] < 240)].copy()
    df["ht"] = np.where(df["agem"] < 24, df["BMXRECUM"], df["BMXHT"])
    df["wt"] = df["BMXWT"]
    df = df[df["ht"].notna() & df["wt"].notna() & (df["ht"] > 0) & (df["wt"] > 0)].copy()
    df["month"] = df["agem"].astype(int)
    return df, files


def slopes(logh, logw):
    ols = stats.linregress(logh, logw)
    rma = float(np.std(logw, ddof=1) / np.std(logh, ddof=1)) * np.sign(ols.rvalue)
    return {"ols_slope": float(ols.slope), "ols_slope_ci95": [float(ols.slope - 1.96 * ols.stderr), float(ols.slope + 1.96 * ols.stderr)],
            "ols_intercept": float(ols.intercept), "r2": float(ols.rvalue ** 2), "rma_slope": rma, "n": int(len(logh))}


def curve_discrepancy(H, W, p):
    """Mean absolute difference between normalised weight curve and the p-th power of the normalised stature curve."""
    return float(np.mean(np.abs(W - H ** p)))


def analyse(df, label):
    out = {"label": label}
    out["individuals"] = slopes(np.log10(df["ht"].values), np.log10(df["wt"].values))
    med = df.groupby("month")[["ht", "wt"]].median()
    med = med[med.index <= 239]
    out["age_median_curve"] = slopes(np.log10(med["ht"].values), np.log10(med["wt"].values))
    # Normalise to the 19-yr value (mean of monthly medians for months 228-239).
    ref = med[(med.index >= 228) & (med.index <= 239)].mean()
    H = med["ht"].values / ref["ht"]
    W = med["wt"].values / ref["wt"]
    D = {str(p): curve_discrepancy(H, W, p) for p in (1, 2, 3, 4)}
    ps = np.arange(1.0, 5.001, 0.01)
    Dp = np.array([curve_discrepancy(H, W, p) for p in ps])
    out["curve_shape"] = {
        "D_by_exponent": D,
        "D3_over_D1": D["3"] / D["1"],
        "best_exponent": float(ps[np.argmin(Dp)]),
        "D_best": float(np.min(Dp)),
        "reference_19yr_median_height_cm": float(ref["ht"]),
        "reference_19yr_median_weight_kg": float(ref["wt"]),
        "normalised_curve_by_year": {str(int(mo // 12)): {"H": round(float(h), 4), "W": round(float(w), 4), "H3": round(float(h ** 3), 4)}
                                     for mo, h, w in zip(med.index, H, W) if mo % 12 == 6},
    }
    return out


def main():
    df, files = load_nhanes()
    out = {"n_total": int(len(df))}
    out["pooled"] = analyse(df, "both sexes")
    out["boys"] = analyse(df[df["sex"] == 1.0], "boys")
    out["girls"] = analyse(df[df["sex"] == 2.0], "girls")
    # Age-window sensitivity (not pre-registered as criteria; descriptive).
    out["slope_by_age_window"] = {}
    for lo, hi in ((0, 2), (2, 10), (10, 20), (2, 20)):
        sub = df[(df["agem"] >= lo * 12) & (df["agem"] < hi * 12)]
        out["slope_by_age_window"][f"{lo}-{hi}yr"] = slopes(np.log10(sub["ht"].values), np.log10(sub["wt"].values))
    b = out["pooled"]["individuals"]["ols_slope"]
    bc = out["pooled"]["age_median_curve"]["ols_slope"]
    ratio = out["pooled"]["curve_shape"]["D3_over_D1"]
    crit = {"1_individual_slope_in_2.5_3.5": 2.5 <= b <= 3.5, "1_curve_slope_in_2.5_3.5": 2.5 <= bc <= 3.5, "2_D3_over_D1_le_0.5": ratio <= 0.5}
    out["criteria"] = crit
    if all(crit.values()):
        verdict = "supports"
    elif (b < 2.0 or b > 4.0) or ratio > 1.0:
        verdict = "refutes"
    else:
        verdict = "mixed"
    out["verdict_by_prereg_rule"] = verdict
    with open(os.path.join(DERIVED, "measured.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(DERIVED, "files.json"), "w") as fh:
        json.dump(files, fh, indent=2)
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
