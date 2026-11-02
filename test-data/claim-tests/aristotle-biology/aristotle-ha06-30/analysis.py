#!/usr/bin/env python3
"""Test aristotle-ha06-30 against FishBase v24.07 egg development times.

Re-run from this directory: python3 analysis.py
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

PARQUET_URL = "https://data.source.coop/cboettig/fishbase/fb/v24.07/parquet/eggdev.parquet"
CARD_URLS = [
    "https://source.coop/cboettig/fishbase",
    "https://source.coop/repositories/cboettig/fishbase",
]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def fetch(url):
    r = requests.get(url, timeout=180, headers={"User-Agent": "DelphiClaimTest/1.0"})
    r.raise_for_status()
    return r.content, r.headers.get("content-type", ""), r.url


def license_from_card():
    for url in CARD_URLS:
        try:
            body, _, final = fetch(url)
        except requests.RequestException:
            continue
        text = body.decode("utf-8", "replace")
        m = re.search(r"CC[- ]BY[- ]NC(?:[- ]\d(?:\.\d)?)?", text, re.I)
        if not m:
            m = re.search(r"Creative Commons[^<]{0,80}", text, re.I)
        return {"card_url": final, "license": m.group(0) if m else None, "byte_size": len(body), "sha256": sha256(body)}
    return {"card_url": None, "license": None}


def choose_column(columns):
    names = list(columns)
    scored = []
    for name in names:
        low = name.lower()
        if not (("egg" in low and "dev" in low) or ("dev" in low and "time" in low) or "duration" in low or "days" in low):
            continue
        prefer = 1 if ("time" in low or "day" in low) else 0
        scored.append((prefer, name))
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[0][1]


def main():
    raw, ctype, final = fetch(PARQUET_URL)
    path = os.path.join(DATA, "eggdev.parquet")
    open(path, "wb").write(raw)
    file_rec = {
        "download_url": PARQUET_URL,
        "retrieved_at": now(),
        "byte_size": len(raw),
        "sha256": sha256(raw),
        "content_type": ctype,
        "final_url": final,
    }
    card = license_from_card()
    df = pd.read_parquet(path)
    col = choose_column(df.columns)
    reason = None
    if col is None or "SpecCode" not in df.columns:
        verdict, reason = "inconclusive", "data-unavailable"
        measured = {"value": None, "unit": "egg-development rows", "n": 0, "uncertainty": "duration column missing", "extra": {"columns": list(map(str, df.columns))}}
        examples = []
    else:
        values = pd.to_numeric(df[col], errors="coerce")
        positive = df.loc[values > 0].copy()
        positive["_v"] = values.loc[positive.index]
        dist = (positive["_v"] - 7 * np.round(positive["_v"] / 7)).abs()
        positive["_far"] = dist > 0.05
        positive["_over"] = positive["_v"] > 30
        positive["_refutes"] = positive["_far"] | positive["_over"]
        n_species = int(positive["SpecCode"].nunique())
        n_pos = int(len(positive))
        n_ref = int(positive["_refutes"].sum())
        n_over = int(positive["_over"].sum())
        n_far = int(positive["_far"].sum())
        if n_ref >= 1:
            verdict = "refutes"
        elif n_species >= 20:
            verdict = "supports"
        else:
            verdict, reason = "inconclusive", "underpowered"
        examples = []
        sample = positive.loc[positive["_refutes"], ["SpecCode", "_v", "_over", "_far"]].head(12)
        for rec in sample.to_dict(orient="records"):
            examples.append({
                "SpecCode": int(rec["SpecCode"]),
                "days": float(rec["_v"]),
                "over_30": bool(rec["_over"]),
                "far_from_multiple_of_7": bool(rec["_far"]),
            })
        measured = {
            "value": n_ref,
            "unit": "positive egg-development rows that exceed 30 days or miss a multiple of 7 by more than 0.05 day",
            "n": n_pos,
            "uncertainty": "each row is one printed duration; temperature is not adjusted",
            "extra": {
                "duration_column": col,
                "n_positive_rows": n_pos,
                "n_species": n_species,
                "n_over_30_days": n_over,
                "n_farther_than_0.05_from_multiple_of_7": n_far,
                "n_refuting_rows": n_ref,
                "example_refuting_rows": examples,
                "min_positive_days": float(positive["_v"].min()) if n_pos else None,
                "max_positive_days": float(positive["_v"].max()) if n_pos else None,
                "verdict_by_rule": verdict,
            },
        }
        positive[["SpecCode", "_v", "_over", "_far", "_refutes"]].rename(columns={"_v": "days"}).to_csv(
            os.path.join(DERIVED, "positive_rows.csv"), index=False
        )

    result = json.load(open(os.path.join(HERE, "result.json")))
    result["status"] = "complete"
    result["data_kind"] = "biological" if verdict != "inconclusive" or reason != "data-unavailable" else "none"
    if verdict == "inconclusive" and reason == "data-unavailable":
        result["data_kind"] = "none"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    result["confidence"] = 0.94 if verdict == "refutes" and measured["extra"].get("n_refuting_rows", 0) >= 20 else 0.7
    result["datasets"] = [{
        "id": "fishbase-v24.07-eggdev",
        "name": "FishBase v24.07 eggdev table",
        "landing_url": card.get("card_url") or "https://source.coop/cboettig/fishbase",
        "doi": None,
        "version": "fb/v24.07",
        "license": card.get("license") or "not stated on the source.coop card retrieved with this run",
        "files": [file_rec],
        "role": "egg development time in days and species identifier",
    }]
    result["method"] = (
        f"The FishBase v24.07 eggdev parquet was read. The duration column selected by the name rule is {col}. "
        "A positive value v refutes when v > 30 or the absolute distance from v to the nearest multiple of 7 exceeds 0.05. "
        "Species are distinct SpecCode values among positive rows. Zero, negative and missing values are dropped."
    )
    result["measured"] = measured
    result["caveats"] = [
        "Egg-development time is the pre-registered reading of Aristotle's gestation. It is not a degree-day total.",
        "Rows are observations. A species can contribute more than one duration, and one non-compliant row refutes the universal.",
    ]
    with open(os.path.join(HERE, "result.json"), "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    json.dump({"verdict": verdict, "measured": measured}, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps({"verdict": verdict, "reason": reason, "n": measured.get("n"), "value": measured.get("value"), "species": measured.get("extra", {}).get("n_species")}, indent=2))


if __name__ == "__main__":
    main()
