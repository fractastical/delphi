#!/usr/bin/env python3
"""aristotle-ha07-02: NHANES age at menarche versus 'about fourteen'.

Rules are those in result.json. Run: python3 analysis.py
Needs pandas.
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
FILES = {
    "RHQ_J.xpt": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/RHQ_J.xpt",
    "DEMO_J.xpt": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.xpt",
}


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
    for name, url in FILES.items():
        path, info = fetch(name, url)
        infos.append(info)
        frames[name] = pd.read_sas(path, format="xport")

    rhq = frames["RHQ_J.xpt"]
    demo = frames["DEMO_J.xpt"]
    need = ["SEQN", "RHQ010"]
    if any(c not in rhq.columns for c in need) or "WTINT2YR" not in demo.columns or "RIDAGEYR" not in demo.columns:
        result.update({
            "status": "complete", "verdict": "inconclusive", "reason": "data-unavailable",
            "confidence": 0.3, "data_kind": "none",
            "measured": {"value": None, "unit": "years", "n": 0, "extra": {"rhq_columns": list(map(str, rhq.columns))[:40]}},
            "method": "The NHANES files loaded but a required column was absent.",
            "datasets": [{"id": "nhanes-2017-2018-rhq-demo", "name": "NHANES 2017-2018 reproductive health and demographics",
                          "landing_url": "https://wwwn.cdc.gov/nchs/nhanes/search/datapage.aspx?Component=Questionnaire&Cycle=2017-2018",
                          "doi": None, "version": "2017-2018", "license": "public domain (U.S. government work)",
                          "files": infos, "role": "age at first menstrual period and interview weights"}],
        })
        RESULT.write_text(json.dumps(result, indent=2) + "\n")
        print("inconclusive columns")
        return

    keep = ["SEQN", "RIDAGEYR", "WTINT2YR"] + (["RIAGENDR"] if "RIAGENDR" in demo.columns else [])
    df = rhq[["SEQN", "RHQ010"]].merge(demo[keep], on="SEQN", how="inner")
    if "RIAGENDR" in df.columns:
        df = df[df["RIAGENDR"] == 2]
    df = df[(df["RIDAGEYR"] >= 20) & (df["RHQ010"] >= 6) & (df["RHQ010"] <= 19) & (df["WTINT2YR"] > 0)]
    n = int(df.shape[0])
    if n < 200:
        measured = {"value": None, "unit": "years", "n": n, "extra": {}}
        verdict, reason, conf = "inconclusive", "underpowered", 0.35
        median = None
    else:
        ages = df["RHQ010"].to_numpy()
        weights = df["WTINT2YR"].to_numpy()
        median = weighted_quantile(ages, weights, 0.5)
        unweighted = float(np.median(ages))
        at_or_below = float(weights[ages <= median].sum() / weights.sum())
        measured = {
            "value": round(median, 4),
            "unit": "years, survey-weighted median age at menarche",
            "n": n,
            "extra": {
                "unweighted_median_years": unweighted,
                "weight_sum": float(weights.sum()),
                "cumulative_weight_share_at_or_below_median": round(at_or_below, 6),
                "min_years": float(ages.min()),
                "max_years": float(ages.max()),
            },
        }
        if 13.0 <= median <= 15.0:
            verdict, reason, conf = "supports", None, 0.7
        elif median < 12.0 or median > 16.0:
            verdict, reason, conf = "refutes", None, 0.75
        else:
            verdict, reason, conf = "mixed", None, 0.55
        if abs(median - 13) < 0.25 or abs(median - 15) < 0.25 or abs(median - 12) < 0.25 or abs(median - 16) < 0.25:
            conf = min(conf, 0.45)
        if 0.49 <= at_or_below <= 0.52:
            result.setdefault("caveats", []).append(
                "The cumulative interview weight first reaches one half inside the median age year, within 0.02 of one half, so the weighted median sits on a boundary between two integer ages."
            )

    result.update({
        "status": "complete",
        "verdict": verdict,
        "confidence": conf,
        "data_kind": "biological" if reason != "data-unavailable" else "none",
        "measured": measured,
        "method": "Joined NHANES 2017-2018 RHQ_J to DEMO_J on SEQN, kept females aged 20 or older with RHQ010 from 6 to 19 and a positive interview weight, and computed the weighted median defined in the pre-registration.",
        "datasets": [{
            "id": "nhanes-2017-2018-rhq-demo",
            "name": "NHANES 2017-2018 reproductive health questionnaire and demographics",
            "landing_url": "https://wwwn.cdc.gov/nchs/nhanes/search/datapage.aspx?Component=Questionnaire&Cycle=2017-2018",
            "doi": None,
            "version": "2017-2018",
            "license": "public domain (U.S. government work)",
            "files": infos,
            "role": "age at first menstrual period (RHQ010) and interview weights (WTINT2YR)",
        }],
    })
    if reason:
        result["reason"] = reason
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, measured.get("value"), n)


if __name__ == "__main__":
    main()
