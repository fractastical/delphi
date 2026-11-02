#!/usr/bin/env python3
"""aristotle-ha07-14: age at natural menopause, with birth rates reported only.

Rules are those in result.json. A matching menopause pattern cannot pass, because
births past fifty are not in the birth-rate table. Run: python3 analysis.py
"""
import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
DERIVED = HERE / "derived"
DATA = HERE / "data"
NHANES = {
    "RHQ_J.xpt": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/RHQ_J.xpt",
    "DEMO_J.xpt": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.xpt",
}
BIRTH_URL = "https://data.cdc.gov/api/views/yt7u-eiyg/rows.csv?accessType=DOWNLOAD"


def fetch(name, url):
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / name
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "delphisci-claim-test"})
        path.write_bytes(urllib.request.urlopen(req, timeout=180).read())
    raw = path.read_bytes()
    return path, {
        "name": name,
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def weighted_quantile(values, weights, q):
    order = np.argsort(values)
    v = np.asarray(values, dtype=float)[order]
    w = np.asarray(weights, dtype=float)[order]
    cw = np.cumsum(w)
    idx = int(np.searchsorted(cw, q * cw[-1], side="left"))
    idx = min(idx, len(v) - 1)
    return float(v[idx])


def main():
    result = json.loads(RESULT.read_text())
    DERIVED.mkdir(parents=True, exist_ok=True)
    infos = []
    frames = {}
    for name, url in NHANES.items():
        path, info = fetch(name, url)
        infos.append(info)
        frames[name] = pd.read_sas(path, format="xport")
    birth_path, birth_info = fetch("nchs-birth-rates-by-age.csv", BIRTH_URL)
    infos.append(birth_info)
    births = pd.read_csv(birth_path)

    rhq, demo = frames["RHQ_J.xpt"], frames["DEMO_J.xpt"]
    required = ["SEQN", "RHQ060", "RHD043"]
    missing = [c for c in required if c not in rhq.columns] or [c for c in ["SEQN", "RIDAGEYR", "WTINT2YR"] if c not in demo.columns]
    if missing:
        result.update({
            "status": "complete", "verdict": "inconclusive", "reason": "data-unavailable",
            "confidence": 0.3, "data_kind": "none",
            "measured": {"value": None, "unit": "years", "n": 0, "extra": {"missing": missing}},
            "method": "NHANES loaded without the pre-registered menopause columns.",
        })
        RESULT.write_text(json.dumps(result, indent=2) + "\n")
        print("inconclusive", missing)
        return

    keep = ["SEQN", "RIDAGEYR", "WTINT2YR"] + (["RIAGENDR"] if "RIAGENDR" in demo.columns else [])
    df = rhq[["SEQN", "RHQ060", "RHD043"]].merge(demo[keep], on="SEQN", how="inner")
    if "RIAGENDR" in df.columns:
        df = df[df["RIAGENDR"] == 2]
    df = df[(df["RIDAGEYR"] >= 20) & (df["RHD043"] == 7) & (df["RHQ060"] >= 20) & (df["RHQ060"] <= 59) & (df["WTINT2YR"] > 0)]
    n = int(df.shape[0])

    birth_extra = {"columns": list(map(str, births.columns))}
    try:
        col_year = "Year" if "Year" in births.columns else "year"
        col_age = "Age Group" if "Age Group" in births.columns else "age_group"
        col_rate = "Birth Rate" if "Birth Rate" in births.columns else "birth_rate"
        births[col_year] = pd.to_numeric(births[col_year], errors="coerce")
        latest = int(births[col_year].max())
        latest_rows = births[births[col_year] == latest]
        rates = {}
        for label in ["40-44 Years", "45-49 Years"]:
            hit = latest_rows[latest_rows[col_age] == label]
            rates[label] = None if hit.empty else float(pd.to_numeric(hit.iloc[0][col_rate], errors="coerce"))
        birth_extra.update({"latest_year": latest, "rates": rates, "age_groups": sorted(births[col_age].dropna().astype(str).unique().tolist())})
    except Exception as exc:
        birth_extra["error"] = str(exc)

    if n < 100:
        measured = {"value": None, "unit": "years", "n": n, "extra": {"births": birth_extra}}
        verdict, reason, conf = "inconclusive", "underpowered", 0.35
    else:
        median = weighted_quantile(df["RHQ060"].to_numpy(), df["WTINT2YR"].to_numpy(), 0.5)
        p90 = weighted_quantile(df["RHQ060"].to_numpy(), df["WTINT2YR"].to_numpy(), 0.9)
        pattern_would_match = 38.0 <= median <= 43.0 and 48.0 <= p90 <= 55.0
        measured = {
            "value": round(median, 4),
            "unit": "years, survey-weighted median age at last menstrual period among natural menopause",
            "n": n,
            "extra": {
                "weighted_p90_years": round(p90, 4),
                "unweighted_median_years": float(np.median(df["RHQ060"].to_numpy())),
                "pattern_would_match_pass_description": bool(pattern_would_match),
                "births_descriptive": birth_extra,
            },
        }
        if median >= 47.0 or median <= 35.0:
            verdict, reason, conf = "refutes", None, 0.8 if median >= 50 or median <= 35 else 0.7
        else:
            verdict, reason, conf = "mixed", None, 0.6
        if abs(median - 47) < 1 or abs(median - 35) < 1:
            conf = min(conf, 0.45)

    result.update({
        "status": "complete",
        "verdict": verdict,
        "confidence": conf,
        "data_kind": "biological" if reason != "data-unavailable" else "none",
        "measured": measured,
        "method": "Restricted NHANES 2017-2018 to women with RHD043 = 7 and RHQ060 in 20-59, computed the weighted median and 90th percentile, and applied the pre-registered median thresholds. NCHS birth rates were summarized for the latest year and not used for the verdict.",
        "datasets": [
            {
                "id": "nhanes-2017-2018-rhq-demo",
                "name": "NHANES 2017-2018 reproductive health questionnaire and demographics",
                "landing_url": "https://wwwn.cdc.gov/nchs/nhanes/search/datapage.aspx?Component=Questionnaire&Cycle=2017-2018",
                "doi": None,
                "version": "2017-2018",
                "license": "public domain (U.S. government work)",
                "files": [i for i in infos if i["name"].endswith(".xpt")],
                "role": "age at last menstrual period among women coded as menopause",
            },
            {
                "id": "nchs-birth-rates-by-age-yt7u-eiyg",
                "name": "NCHS - Birth Rates for Females by Age Group: United States",
                "landing_url": "https://data.cdc.gov/d/yt7u-eiyg",
                "doi": None,
                "version": "as retrieved",
                "license": "public domain (U.S. government work)",
                "files": [birth_info],
                "role": "descriptive birth rates at 40-44 and 45-49; no age bin past 49",
            },
        ],
    })
    if reason:
        result["reason"] = reason
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, measured.get("value"), n)


if __name__ == "__main__":
    main()
