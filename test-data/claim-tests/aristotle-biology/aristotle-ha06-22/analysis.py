#!/usr/bin/env python3
"""Look for a milt-exposed versus unexposed hatch contrast in the USGS lake-trout file.

Hatch counts are summed only if an unexposed column is present. A checksum
mismatch or a missing contrast is inconclusive and does not use the counts.
"""
import csv
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test/aristotle-ha06-22"}


def fetch(url, dest):
    DATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size == 0:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r:
            dest.write_bytes(r.read())
    raw = dest.read_bytes()
    return {
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "md5": hashlib.md5(raw).hexdigest(),
    }


def main():
    result = json.loads(RESULT.read_text())
    rules = result["rules"]
    exp = result["expected_files"][0]
    meta = fetch(exp["download_url"], DATA / exp["name"])
    checksum_ok = meta["md5"] == exp["md5"] and meta["byte_size"] == exp["byte_size"]
    pattern = re.compile(rules["unexposed_column"])
    with (DATA / exp["name"]).open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        headers = next(reader)
        n_rows = sum(1 for _ in reader)
    contrast_cols = [h for h in headers if pattern.search(h or "")]
    measured = {
        "value": None,
        "unit": "hatch count in a no-milt arm",
        "n": n_rows,
        "extra": {
            "checksum_ok": checksum_ok,
            "columns": headers,
            "contrast_columns": contrast_cols,
            "contrast_present": bool(contrast_cols) and checksum_ok,
        },
    }
    if not checksum_ok:
        verdict, reason, conf = "inconclusive", "data-unavailable", rules["confidence_bad_file"]
        method = "The downloaded file did not match the ScienceBase md5 or byte size, so it was not interpreted."
    elif not contrast_cols:
        verdict, reason, conf = "inconclusive", "data-unavailable", rules["confidence_no_contrast"]
        method = (
            "Downloaded LakeTroutEggHatchData.csv and checked md5 and size against ScienceBase. "
            "The header has no column matching the preregistered unexposed-arm pattern. "
            "Unfertilized_Removed, dead, hatched, and larval-mortality columns were pre-registered "
            "as counts inside inseminated lots, so those counts were not summed."
        )
    else:
        verdict, reason, conf = "inconclusive", "other", rules["confidence_bad_file"]
        method = (
            "An unexposed-arm column was present, but this script has no summing branch because "
            "the preregistered file's dictionary did not include one. The column names are recorded "
            "and the verdict is left inconclusive rather than inventing a contrast."
        )
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    result["status"] = "complete"
    result["verdict"] = verdict
    result["reason"] = reason
    result["confidence"] = conf
    result["data_kind"] = "none"
    result["measured"] = measured
    result["method"] = method
    result["datasets"] = [{
        "id": "usgs-lake-trout-hatch-p9h094s2",
        "name": "Lake trout hatch rates, Northern Refuge, Lake Michigan, 2019",
        "landing_url": exp["landing_url"],
        "doi": exp["doi"],
        "version": "2022",
        "license": exp["license"],
        "files": [meta],
        "role": "incubation counts checked for a no-milt arm",
    }]
    result["results_summary"] = [
        f"Checksum match: {checksum_ok}. Data rows: {n_rows}.",
        f"Columns: {', '.join(headers)}.",
        f"Unexposed-arm columns: {contrast_cols or 'none'}. Verdict {verdict} ({reason}).",
    ]
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, reason, "cols", contrast_cols)


if __name__ == "__main__":
    main()
