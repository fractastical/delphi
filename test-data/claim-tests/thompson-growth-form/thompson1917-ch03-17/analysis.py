#!/usr/bin/env python3
"""thompson1917-ch03-17: plaice weight-length coefficient k = W/L^3 peaks near 30 cm, about the size at maturity.

Downloads ICES DATRAS CA exchange records (NS-IBTS) via the public web service, extracts plaice with
individual weights and maturity codes, and tests the pre-registered hump/maturity criteria.
Raw XML (~50 MB per survey-year) stays under data/ (not committed); checksums are recorded.
Writes derived/measured.json, derived/files.json, derived/k_by_length.csv.
"""
import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
UA = {"User-Agent": "delphi-claim-tests/1.0"}
URL = "https://datras.ices.dk/WebServices/DATRASWebService.asmx/getCAdata?survey=NS-IBTS&year={year}&quarter={q}"
PRIMARY = [(y, 1) for y in range(2015, 2020)]
SECONDARY = [(y, 3) for y in range(2017, 2020)]
PLAICE = "127143"
NS = {"d": "ices.dk.local/DATRAS"}
LMIN, LMAX, MIN_N = 15, 50, 30


def fetch(url, dest):
    if not os.path.exists(dest):
        r = requests.get(url, timeout=900, headers=UA)
        r.raise_for_status()
        open(dest, "wb").write(r.content)
    h = hashlib.sha256()
    with open(dest, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return {"download_url": url, "retrieved_at": datetime.fromtimestamp(os.path.getmtime(dest), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": os.path.getsize(dest), "sha256": h.hexdigest()}


def parse_plaice(path):
    rows = []
    for _, el in ET.iterparse(path, events=("end",)):
        if not el.tag.endswith("Cls_DatrasExchange_CA"):
            continue
        g = {c.tag.split("}")[-1]: (c.text or "").strip() for c in el}
        el.clear()
        if g.get("Valid_Aphia", g.get("SpecCode")) != PLAICE:
            continue
        try:
            w = float(g.get("IndWgt", "-9"))
            lc = float(g["LngtClass"])
        except ValueError:
            continue
        code = g.get("LngtCode", "")
        length_cm = lc / 10.0 if code in (".", "0") else lc  # '.' and '0' = mm classes; '1' = cm; '5' = 5-cm
        if code == "5":
            continue
        rows.append({"year": int(g["Year"]), "quarter": int(g["Quarter"]), "length_cm": length_cm, "wgt_g": w,
                     "sex": g.get("Sex", ""), "maturity": g.get("Maturity", ""), "scale": g.get("MaturityScale", ""),
                     "n_at_lngt": float(g.get("CANoAtLngt", "1") or 1)})
    return pd.DataFrame(rows)


def maturity_flag(code):
    """ICES maturity codes end in 1 = immature, 2-5 = maturing/spawning/spent/resting (mature); 6/-9 = abnormal/unknown."""
    c = code.strip()
    if not c or c == "-9":
        return np.nan
    last = c[-1]
    if last == "1":
        return 0.0
    if last in "2345":
        return 1.0
    return np.nan


def l50_logistic(length, mature):
    """Logistic maturity ogive by maximum likelihood; returns L50 (cm) and slope."""
    x = np.asarray(length, float)
    y = np.asarray(mature, float)

    def nll(p):
        a, b = p
        z = a + b * x
        return np.sum(np.logaddexp(0, z) - y * z)

    res = minimize(nll, x0=[-10.0, 0.4], method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-8, "maxiter": 5000})
    a, b = res.x
    return float(-a / b), float(b)


def k_profile(df):
    d = df[(df["wgt_g"] > 0) & (df["length_cm"] >= LMIN) & (df["length_cm"] <= LMAX)].copy()
    d["k"] = 10000.0 * d["wgt_g"] / d["length_cm"] ** 3  # Thompson's scaling: plaice k is near 100
    # individual k outside 30-300 (a factor of ~3 from typical) marks unit or transcription errors
    d = d[(d["k"] > 30) & (d["k"] < 300)]
    d["lclass"] = np.floor(d["length_cm"]).astype(int)
    g = d.groupby("lclass")["k"].agg(["mean", "count", "std"])
    g = g[g["count"] >= MIN_N]
    g["smooth"] = g["mean"].rolling(3, center=True).mean()
    prof = g.dropna(subset=["smooth"])
    return d, g, prof


def hump_test(prof):
    if len(prof) < 5:
        return {"enough_classes": False}
    lo, hi = int(prof.index.min()), int(prof.index.max())
    istar = int(prof["smooth"].idxmax())
    kstar = float(prof.loc[istar, "smooth"])
    k_lo, k_hi = float(prof.loc[lo, "smooth"]), float(prof.loc[hi, "smooth"])
    rng = float((prof["smooth"].max() - prof["smooth"].min()) / prof["smooth"].mean())
    return {"enough_classes": True, "L_star_cm": istar, "k_star_x10000": kstar, "analysed_range_cm": [lo, hi],
            "k_at_low_end": k_lo, "k_at_high_end": k_hi, "rise_over_low_end_frac": kstar / k_lo - 1, "rise_over_high_end_frac": kstar / k_hi - 1,
            "relative_range_of_smoothed_k": rng,
            "interior": (istar >= lo + 3) and (istar <= hi - 3),
            "hump_ge_3pct_both_sides": (kstar / k_lo - 1 >= 0.03) and (kstar / k_hi - 1 >= 0.03),
            "flat_lt_3pct": rng < 0.03, "monotonic_max_at_end": istar in (lo, hi)}


def analyse(df, label):
    d, g, prof = k_profile(df)
    out = {"label": label, "n_fish_with_weight_15_50cm": int(len(d)), "n_classes_analysed": int(len(prof))}
    out.update(hump_test(prof))
    m = df.copy()
    m["mature"] = m["maturity"].map(maturity_flag)
    m = m[m["mature"].notna() & (m["length_cm"] >= 10) & (m["length_cm"] <= 60)]
    out["n_fish_with_maturity"] = int(len(m))
    if len(m) >= 100 and m["mature"].nunique() == 2:
        l50, slope = l50_logistic(m["length_cm"], m["mature"])
        out["L50_cm"] = l50
        out["L50_by_sex"] = {}
        for sx, lab in (("F", "female"), ("M", "male")):
            ms = m[m["sex"] == sx]
            if len(ms) >= 100 and ms["mature"].nunique() == 2:
                out["L50_by_sex"][lab] = l50_logistic(ms["length_cm"], ms["mature"])[0]
        if out.get("enough_classes"):
            out["Lstar_minus_L50_cm"] = out["L_star_cm"] - l50
    return out, g


def main():
    files = {"q1": [], "q3": []}
    frames = {"q1": [], "q3": []}
    for key, combos in (("q1", PRIMARY), ("q3", SECONDARY)):
        for year, q in combos:
            dest = os.path.join(DATA, f"NS-IBTS_{year}_Q{q}_CA.xml")
            files[key].append(fetch(URL.format(year=year, q=q), dest))
            frames[key].append(parse_plaice(dest))
    q1 = pd.concat(frames["q1"], ignore_index=True)
    q3 = pd.concat(frames["q3"], ignore_index=True)
    out = {"n_plaice_records_q1": int(len(q1)), "n_plaice_records_q3": int(len(q3))}
    out["primary_q1_pooled"], g1 = analyse(q1, "NS-IBTS Q1 2015-2019, sexes pooled")
    out["q1_female"], _ = analyse(q1[q1["sex"] == "F"], "Q1 females")
    out["q1_male"], _ = analyse(q1[q1["sex"] == "M"], "Q1 males")
    out["q1_by_year"] = {str(y): {k: v for k, v in analyse(q1[q1["year"] == y], f"Q1 {y}")[0].items() if k in ("L_star_cm", "rise_over_low_end_frac", "rise_over_high_end_frac", "n_fish_with_weight_15_50cm", "L50_cm")} for y in sorted(q1["year"].unique())}
    out["secondary_q3_pooled"], g3 = analyse(q3, "NS-IBTS Q3 2017-2019, sexes pooled")
    g1.rename(columns=lambda c: f"q1_{c}").join(g3.rename(columns=lambda c: f"q3_{c}"), how="outer").to_csv(os.path.join(DERIVED, "k_by_length.csv"))
    p = out["primary_q1_pooled"]
    c1 = p.get("interior", False) and p.get("hump_ge_3pct_both_sides", False)
    c2 = p.get("enough_classes") and 25 <= p["L_star_cm"] <= 35
    c3 = "Lstar_minus_L50_cm" in p and abs(p["Lstar_minus_L50_cm"]) <= 5
    out["criteria"] = {"1_hump": bool(c1), "2_Lstar_25_35": bool(c2), "3_within_5cm_of_L50": bool(c3)}
    if c1 and c2 and c3:
        verdict = "supports"
    elif p.get("flat_lt_3pct") or p.get("monotonic_max_at_end") or (p.get("enough_classes") and not (22 <= p["L_star_cm"] <= 38)):
        verdict = "refutes"
    else:
        verdict = "mixed"
    out["verdict_by_prereg_rule"] = verdict
    json.dump(out, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    json.dump(files, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
