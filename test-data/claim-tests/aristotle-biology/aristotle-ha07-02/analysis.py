#!/usr/bin/env python3
"""Age at menarche in NHANES 2017-2018.

Decision rule: result.json pass_criterion, committed before the XPT files were downloaded.
Breast development is not in the file and is not scored.
"""
import datetime as dt
import hashlib
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
FILES = {
    "RHQ_J.xpt": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/RHQ_J.xpt",
    "DEMO_J.xpt": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.xpt",
}
LOCKED = {
    "hypothesis", "pass_criterion", "fail_criterion", "planned_datasets", "test_contract",
    "claim_id", "claim_iri", "project", "preregistered_at", "interpretation",
}


def fetch_all():
    DATA.mkdir(parents=True, exist_ok=True)
    out = []
    for name, url in FILES.items():
        dest = DATA / name
        last = None
        if not dest.exists() or dest.stat().st_size == 0:
            for i in range(3):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "delphisci-claim-test"})
                    with urllib.request.urlopen(req, timeout=180) as resp:
                        dest.write_bytes(resp.read())
                    break
                except Exception as exc:  # noqa: BLE001
                    last = exc
                    time.sleep(2 * (i + 1))
            else:
                raise last
        raw = dest.read_bytes()
        out.append({
            "name": name,
            "download_url": url,
            "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    return out


def numeric(series):
    if series.dtype == object:
        series = series.apply(lambda x: x.decode() if isinstance(x, (bytes, bytearray)) else x)
    return pd.to_numeric(series, errors="coerce")


def weighted_median(ages, weights):
    order = sorted(range(len(ages)), key=lambda i: ages[i])
    total = sum(weights[i] for i in order)
    if total <= 0:
        return None
    running = 0.0
    half = 0.5 * total
    for i in order:
        running += weights[i]
        if running >= half:
            return float(ages[i])
    return float(ages[order[-1]])


def bin_of(value):
    if value < 12 or value > 16:
        return "far"
    if 13 <= value <= 15:
        return "near"
    return "gray"


def write_result(fields):
    doc = json.loads(RESULT.read_text())
    for key in fields:
        if key in LOCKED:
            raise SystemExit("refusing to edit locked field " + key)
    doc.update(fields)
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")


def datasets(files):
    return [
        {
            "id": "nhanes-2017-2018-rhq-j",
            "name": "NHANES 2017-2018 Reproductive Health (RHQ_J)",
            "landing_url": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/RHQ_J.htm",
            "doi": None,
            "version": "2017-2018",
            "license": "U.S. government public-use file (National Center for Health Statistics)",
            "files": [f for f in files if f["name"] == "RHQ_J.xpt"],
            "role": "recalled age at first menstrual period (RHQ010)",
        },
        {
            "id": "nhanes-2017-2018-demo-j",
            "name": "NHANES 2017-2018 Demographics (DEMO_J)",
            "landing_url": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.htm",
            "doi": None,
            "version": "2017-2018",
            "license": "U.S. government public-use file (National Center for Health Statistics)",
            "files": [f for f in files if f["name"] == "DEMO_J.xpt"],
            "role": "interview weight WTINT2YR",
        },
    ]


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    try:
        files = fetch_all()
        rhq = pd.read_sas(DATA / "RHQ_J.xpt", format="xport")
        demo = pd.read_sas(DATA / "DEMO_J.xpt", format="xport")
    except Exception as exc:  # noqa: BLE001
        measured = {"value": None, "unit": "years (weighted median age at menarche)", "n": 0, "uncertainty": None, "extra": {"error": str(exc)}}
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        write_result({
            "status": "complete", "verdict": "inconclusive", "reason": "data-unavailable",
            "confidence": 0.3, "data_kind": "none", "measured": measured,
            "method": "An NHANES file could not be downloaded or read.",
            "results_summary": [str(exc)],
        })
        print("download failed", exc)
        return
    if "RHQ010" not in rhq.columns or "SEQN" not in rhq.columns or "WTINT2YR" not in demo.columns or "SEQN" not in demo.columns:
        write_result({
            "status": "complete", "verdict": "inconclusive", "reason": "data-unavailable",
            "confidence": 0.35, "data_kind": "none",
            "measured": {"value": None, "unit": "years (weighted median age at menarche)", "n": 0, "uncertainty": None, "extra": {"rhq_columns": [c for c in rhq.columns if str(c).startswith("RHQ")][:20], "demo_has_weight": "WTINT2YR" in demo.columns}},
            "datasets": datasets(files),
            "method": "RHQ010 or WTINT2YR was absent, so no median was computed from a substitute column.",
            "results_summary": ["Required column missing."],
        })
        return
    rhq = rhq.copy()
    demo = demo.copy()
    rhq["SEQN"] = numeric(rhq["SEQN"]).astype("int64")
    demo["SEQN"] = numeric(demo["SEQN"]).astype("int64")
    demo["WTINT2YR"] = numeric(demo["WTINT2YR"])
    merged = rhq.merge(demo[["SEQN", "WTINT2YR"]], on="SEQN", how="left")
    if merged["WTINT2YR"].notna().sum() == 0:
        write_result({
            "status": "complete", "verdict": "inconclusive", "reason": "data-unavailable",
            "confidence": 0.35, "data_kind": "none",
            "measured": {"value": None, "unit": "years (weighted median age at menarche)", "n": 0, "uncertainty": None, "extra": {}},
            "datasets": datasets(files),
            "method": "The interview weight did not join to any reproductive-health row.",
            "results_summary": ["WTINT2YR join failed."],
        })
        return
    age = numeric(merged["RHQ010"])
    nonmissing = age.notna()
    n_nonmissing = int(nonmissing.sum())
    n_excluded_bounds = int(((age == 0) | (age == 20)).sum())
    if n_nonmissing and n_excluded_bounds / n_nonmissing > 0.10:
        measured = {"value": None, "unit": "years (weighted median age at menarche)", "n": n_nonmissing, "uncertainty": None, "extra": {"share_code_0_or_20": n_excluded_bounds / n_nonmissing}}
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        write_result({
            "status": "complete", "verdict": "inconclusive", "reason": "other", "confidence": 0.4,
            "data_kind": "biological", "measured": measured, "datasets": datasets(files),
            "method": "Codes 0 and 20 exceeded the pre-registered 10 percent gate, so the median was not interpreted.",
            "results_summary": [f"Share of codes 0 or 20 among non-missing RHQ010: {n_excluded_bounds / n_nonmissing:.4f}."],
        })
        return
    exact = (age >= 6) & (age <= 19)
    use = merged.loc[exact].copy()
    use_age = age.loc[exact].astype(float)
    weights = use["WTINT2YR"].astype(float)
    positive = weights > 0
    ages = use_age.loc[positive].tolist()
    wts = weights.loc[positive].tolist()
    if len(ages) < 200:
        measured = {"value": None, "unit": "years (weighted median age at menarche)", "n": len(ages), "uncertainty": None, "extra": {}}
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        write_result({
            "status": "complete", "verdict": "inconclusive", "reason": "underpowered", "confidence": 0.4,
            "data_kind": "biological", "measured": measured, "datasets": datasets(files),
            "method": "Fewer than 200 exact ages remained.",
            "results_summary": [f"Exact ages: {len(ages)}."],
        })
        return
    w_med = weighted_median(ages, wts)
    u_med = weighted_median(ages, [1.0] * len(ages))
    w_bin = bin_of(w_med)
    u_bin = bin_of(u_med)
    if w_bin == "near" and u_bin == "near":
        verdict, confidence = "supports", 0.50
    elif w_bin == "far" and u_bin == "far":
        verdict, confidence = "refutes", 0.75
    else:
        verdict, confidence = "mixed", 0.55
    measured = {
        "value": w_med,
        "unit": "years (weighted median age at first menstrual period, RHQ010)",
        "n": len(ages),
        "uncertainty": None,
        "extra": {
            "weighted_median_years": w_med,
            "unweighted_median_years": u_med,
            "weighted_bin": w_bin,
            "unweighted_bin": u_bin,
            "n_nonmissing_rhq010": n_nonmissing,
            "n_code_0_or_20": n_excluded_bounds,
            "thelarche_measured": False,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    write_result({
        "status": "complete",
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological",
        "measured": measured,
        "datasets": datasets(files),
        "method": "Joined RHQ_J to DEMO_J on SEQN, kept exact RHQ010 ages 6 through 19, and computed the pre-registered weighted and unweighted medians with WTINT2YR. Breast development was not in the file and was not scored.",
        "results_summary": [
            f"Weighted median {w_med} years ({w_bin}); unweighted median {u_med} years ({u_bin}); n={len(ages)}.",
            "Thelarche was not measured.",
        ],
    })
    print(verdict, w_med, u_med, len(ages))


if __name__ == "__main__":
    main()
