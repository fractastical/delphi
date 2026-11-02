#!/usr/bin/env python3
"""Test aristotle-ha07-01: male pubic hair and seed begin at about fourteen.

The planned NHANES SSAMH files are downloaded and inspected. The verdict follows
the pre-registered rule if they contain a Tanner pubic-hair stage.
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
UA = "DelphiClaimTest/1.0 (aristotle-ha07-01; public claim test)"
FILES = []
CYCLES = [
    ("1999", "SSAMH_A"),
    ("2001", "SSAMH_B"),
    ("2003", "SSAMH_C"),
]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, name, role):
    path = os.path.join(DATA, name)
    meta = path + ".retrieved"
    if os.path.exists(path) and os.path.exists(meta):
        content = open(path, "rb").read()
        when = open(meta).read().strip()
    else:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=120)
        r.raise_for_status()
        content, when = r.content, now()
        open(path, "wb").write(content)
        open(meta, "w").write(when)
    FILES.append({
        "download_url": url,
        "retrieved_at": when,
        "byte_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "role": role,
    })
    return path, content


def labels_from_doc(html):
    text = re.sub(r"<[^>]+>", " ", html.decode("utf-8", "replace"))
    text = re.sub(r"\s+", " ", text)
    found = re.findall(r"Variable Name:\s*(\w+)\s+SAS Label:\s*([^<]{0,120})", html.decode("utf-8", "replace"))
    # The tags were not stripped in the second pass; parse the HTML directly.
    found = re.findall(
        r"Variable Name:\s*</dt>\s*<dd[^>]*>\s*(\w+)\s*</dd>.*?SAS Label:\s*</dt>\s*<dd[^>]*>\s*([^<]+)",
        html.decode("utf-8", "replace"),
        flags=re.S,
    )
    return [(a, re.sub(r"\s+", " ", b).strip()) for a, b in found], text


def main():
    cycles = []
    pubic_cols = []
    for year, stem in CYCLES:
        xpt_url = f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{stem}.xpt"
        htm_url = f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{stem}.htm"
        xpath, _ = fetch(xpt_url, f"{stem}.xpt", f"NHANES {stem} data file")
        _, htm = fetch(htm_url, f"{stem}.htm", f"NHANES {stem} codebook")
        labels, text = labels_from_doc(htm)
        head = open(xpath, "rb").read(20)
        is_xpt = head.startswith(b"HEADER RECORD")
        columns = []
        if is_xpt:
            df = pd.read_sas(xpath, format="xport")
            columns = list(df.columns)
        pubic = [name for name, label in labels if re.search(r"pubic|tanner", label, re.I)]
        pubic += [c for c in columns if re.search(r"pubic|tanner", c, re.I)]
        pubic_cols.extend(pubic)
        cycles.append({
            "stem": stem,
            "is_xport": is_xpt,
            "columns": columns,
            "labels": labels,
            "mentions_pubic_or_tanner": bool(re.search(r"pubic|tanner", text, re.I)),
            "n_rows": int(len(df)) if is_xpt else 0,
        })

    has_stage = any(c["mentions_pubic_or_tanner"] for c in cycles) or bool(pubic_cols)
    if not has_stage:
        verdict, reason = "inconclusive", "data-unavailable"
        data_kind = "none"
        measured = {
            "value": None,
            "unit": "years at pubic-hair onset",
            "n": 0,
            "uncertainty": None,
            "extra": {"cycles": cycles},
        }
    else:
        raise RuntimeError("pubic-hair stage was found; the onset-age branch is not implemented because the files did not contain it when this test was written, and a later file layout should be handled by extending this script before a verdict")

    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2, ensure_ascii=False)
    path = os.path.join(HERE, "result.json")
    result = json.load(open(path))
    result["status"] = "complete"
    result["preregistered"] = True
    result["data_kind"] = data_kind
    result["verdict"] = verdict
    result["reason"] = reason
    result["confidence"] = 0.9
    result["deviations"] = [{
        "field": "planned file location",
        "change": "Files were read from https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/SSAMH_*.xpt rather than the older /Nchs/Nhanes/{cycle}/ path.",
        "why": "The older path returns an HTML 404. The files that resolve are surplus serum assays (anti-Müllerian hormone and inhibin B), not a Tanner pubic-hair exam. The pass and fail ages were not changed, and no substitute cohort was added.",
    }]
    result["method"] = (
        "The three planned NHANES SSAMH files and their codebooks were downloaded. "
        "Each codebook was searched for a pubic-hair or Tanner variable, and each XPT file's column names were listed. "
        "The codebooks describe anti-Müllerian hormone and inhibin B. They do not contain a pubic-hair stage or an age at spermarche. "
        "Without that variable the pre-registered onset age cannot be computed, so the verdict is inconclusive with reason data-unavailable."
    )
    result["measured"] = measured
    result["caveats"] = [
        "Hormone concentrations are not an age at pubic-hair stage 2 and were not used as a proxy.",
        "The files also contain no age column, only a respondent sequence number.",
        "A different public puberty series was not substituted after the planned files turned out to measure something else.",
    ]
    result["datasets"] = [{
        "id": "nhanes-ssamh-1999-2004",
        "name": "NHANES SSAMH files, 1999-2000, 2001-2002 and 2003-2004",
        "landing_url": "https://wwwn.cdc.gov/nchs/nhanes/",
        "doi": None,
        "version": "codebooks revised April 2022",
        "license": "public domain (US government work)",
        "files": FILES,
        "role": "planned sexual-maturity examination; the files that resolve are serum AMH and inhibin B",
    }]
    result["headline"] = (
        "The planned NHANES files do not record pubic-hair stage or spermarche, so the age at male puberty was not measured."
    )
    with open(path, "w") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(verdict, reason)
    for c in cycles:
        print(c["stem"], c["columns"], c["labels"])


if __name__ == "__main__":
    main()
