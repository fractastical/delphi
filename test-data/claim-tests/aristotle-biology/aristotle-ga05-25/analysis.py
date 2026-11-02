#!/usr/bin/env python3
"""aristotle-ga05-25: the last human grinders erupt at about twenty.

NHANES 2015–2016 and 2017–2018 tooth-count codes. The half-plateau age
and the 17–23 window are fixed in result.json. Stops without a verdict
if code 2 never occurs, so the code map can be corrected from the label
rather than from the age curve.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
UA = "delphisci-claim-test/aristotle-biology"
# The paths named at registration (wwwn.cdc.gov/Nchs/Nhanes/<cycle>/<FILE>.XPT) return a CDC
# 404 HTML page. The same public files are served from the current DataFiles directory.
CYCLES = [
    {
        "id": "2015-2016",
        "demo": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/DEMO_I.xpt",
        "ohx": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/OHXDEN_I.xpt",
    },
    {
        "id": "2017-2018",
        "demo": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.xpt",
        "ohx": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/OHXDEN_J.xpt",
    },
]
TEETH = ["OHX01TC", "OHX16TC", "OHX17TC", "OHX32TC"]
PRESENT = 2
ASSESSED = {1, 2, 3, 4, 5}


def fetch(url: str, dest: Path) -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size == 0:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as resp:
            dest.write_bytes(resp.read())
    raw = dest.read_bytes()
    return {
        "download_url": url,
        "retrieved_at": datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "name": dest.name,
    }


def colnames(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [c.decode() if isinstance(c, (bytes, bytearray)) else str(c) for c in frame.columns]
    frame.columns = [c.upper() for c in frame.columns]
    return frame


def read_xpt(path: Path) -> pd.DataFrame:
    return colnames(pd.read_sas(path, format="xport"))


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    files = []
    frames = []
    deviations = []
    for cycle in CYCLES:
        demo_meta = fetch(cycle["demo"], DATA / Path(cycle["demo"]).name)
        ohx_meta = fetch(cycle["ohx"], DATA / Path(cycle["ohx"]).name)
        files.extend([demo_meta, ohx_meta])
        demo = read_xpt(DATA / Path(cycle["demo"]).name)
        ohx = read_xpt(DATA / Path(cycle["ohx"]).name)
        if "WTMEC2YR" not in demo.columns:
            write_stop("data-unavailable", "WTMEC2YR was not in the demographic file.", files)
            return
        missing_teeth = [c for c in TEETH if c not in ohx.columns]
        if missing_teeth:
            write_stop("data-unavailable", f"Missing tooth columns {missing_teeth}.", files)
            return
        keep_demo = ["SEQN", "RIDAGEYR", "WTMEC2YR"]
        keep_ohx = ["SEQN"] + TEETH + (["OHDEXSTS"] if "OHDEXSTS" in ohx.columns else [])
        if "OHDEXSTS" not in ohx.columns:
            deviations.append(f"{cycle['id']}: OHDEXSTS was absent, so the exam-status filter was skipped.")
        merged = demo[keep_demo].merge(ohx[keep_ohx], on="SEQN", how="inner")
        merged["cycle"] = cycle["id"]
        frames.append(merged)

    df = pd.concat(frames, ignore_index=True)
    for col in TEETH + ["RIDAGEYR", "WTMEC2YR", "OHDEXSTS", "SEQN"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    codes = df[TEETH].melt(value_name="code")["code"].dropna()
    if int((codes == PRESENT).sum()) == 0:
        counts = {str(k): int(v) for k, v in codes.value_counts(dropna=False).items()}
        (DERIVED / "code_counts.json").write_text(json.dumps(counts, indent=2) + "\n")
        raise SystemExit(
            "Code 2 does not occur in the third-molar columns. No verdict written. "
            f"Observed codes: {counts}"
        )

    if "OHDEXSTS" in df.columns:
        df = df[df["OHDEXSTS"] == 1]
    assessed = df[TEETH].isin(list(ASSESSED)).any(axis=1)
    df = df.loc[assessed & df["RIDAGEYR"].between(12, 29) & df["WTMEC2YR"].gt(0)].copy()
    df["weight"] = df["WTMEC2YR"] / 2.0
    df["erupted"] = df[TEETH].eq(PRESENT).any(axis=1)

    by_age = []
    for age in range(12, 30):
        sub = df[df["RIDAGEYR"] == age]
        w = float(sub["weight"].sum())
        prev = float(sub.loc[sub["erupted"], "weight"].sum() / w) if w else None
        by_age.append({"age": age, "n": int(len(sub)), "weight": w, "prevalence": prev})
    plateau_ages = [row for row in by_age if row["age"] >= 25 and row["prevalence"] is not None and row["n"] > 0]
    plateau = float(np.mean([row["prevalence"] for row in plateau_ages])) if plateau_ages else None
    proxy = None
    if plateau and plateau > 0:
        half = 0.5 * plateau
        for row in by_age:
            if row["prevalence"] is not None and row["prevalence"] >= half:
                proxy = row["age"]
                break
    n_15_25 = int(df["RIDAGEYR"].between(15, 25).sum())

    if plateau is None or plateau < 0.15 or proxy is None or n_15_25 < 400:
        verdict, reason, conf = "inconclusive", "underpowered", 0.35
    elif 17 <= proxy <= 23:
        verdict, reason, conf = "supports", None, 0.6
    elif proxy <= 15 or proxy >= 26:
        verdict, reason, conf = "refutes", None, 0.55
    else:
        verdict, reason, conf = "mixed", None, 0.45

    measured = {
        "value": proxy,
        "unit": "youngest age in years at which weighted third-molar prevalence reaches half the age-25-to-29 mean",
        "n": n_15_25,
        "uncertainty": None if plateau is None else f"late-twenties plateau prevalence {plateau:.4f}",
        "extra": {
            "plateau_prevalence": plateau,
            "half_plateau": None if plateau is None else 0.5 * plateau,
            "by_age": by_age,
            "n_examined_ages_12_29": int(len(df)),
            "present_code": PRESENT,
            "cycles": [c["id"] for c in CYCLES],
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = conf
    result["method"] = (
        "Pooled NHANES 2015–2016 and 2017–2018 dental examinations. "
        "A third molar counted as erupted when its tooth-count code was 2. "
        "Exam weights WTMEC2YR were divided by 2. "
        "Prevalence by year of age from 12 to 29 was compared with half the mean prevalence at ages 25–29."
    )
    result["measured"] = measured
    result["results_summary"] = [
        f"Counted examinees aged 15–25: {n_15_25}. Plateau prevalence: {plateau}. Half-plateau age: {proxy}.",
        f"Verdict {verdict}. Eruption in old age was not tested.",
    ]
    deviations.insert(0, "The registration URLs under /Nchs/Nhanes/<cycle>/ returned a CDC 404 page. The same public XPT files were downloaded from /Nchs/Data/Nhanes/Public/<year>/DataFiles/. Tooth codes, weights and age thresholds are unchanged.")
    result["deviations"] = deviations
    result["datasets"] = [
        {
            "id": "nhanes-2015-2016-ohxden-demo",
            "name": "NHANES 2015–2016 demographics and oral health dentition",
            "landing_url": "https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/default.aspx?BeginYear=2015",
            "doi": None,
            "version": "2015-2016",
            "license": "public domain (U.S. government work)",
            "files": [f for f in files if "2015-2016" in f["download_url"]],
            "role": "age, exam weight and third-molar tooth-count codes",
        },
        {
            "id": "nhanes-2017-2018-ohxden-demo",
            "name": "NHANES 2017–2018 demographics and oral health dentition",
            "landing_url": "https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/default.aspx?BeginYear=2017",
            "doi": None,
            "version": "2017-2018",
            "license": "public domain (U.S. government work)",
            "files": [f for f in files if "2017-2018" in f["download_url"]],
            "role": "age, exam weight and third-molar tooth-count codes",
        },
    ]
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "proxy": proxy, "plateau": plateau, "n": n_15_25}, indent=2))


def write_stop(reason: str, message: str, files: list) -> None:
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["verdict"] = "inconclusive"
    result["reason"] = reason
    result["data_kind"] = "none"
    result["confidence"] = 0.3
    result["method"] = message
    result["measured"] = {"value": None, "unit": "years", "n": 0, "extra": {"stop": message}}
    result["datasets"] = [{
        "id": "nhanes-oral-health",
        "name": "NHANES oral health and demographics",
        "landing_url": "https://wwwn.cdc.gov/nchs/nhanes/",
        "doi": None,
        "version": None,
        "license": "public domain (U.S. government work)",
        "files": files,
        "role": "third-molar presence by age",
    }]
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(message)


if __name__ == "__main__":
    main()
