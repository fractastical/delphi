#!/usr/bin/env python3
"""aristotle-ha08-19: Camelus maximum longevity against 'about thirty' and 'a hundred'.

Thresholds are those committed in result.json. Run: python3 analysis.py
"""
import csv
import datetime as dt
import hashlib
import io
import json
import statistics
import zipfile
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
ZIP_URL = "https://genomics.senescence.info/species/dataset.zip"
UA = "delphisci-claim-test/aristotle-ha08-19"


def fetch_zip():
    DATA.mkdir(exist_ok=True)
    path = DATA / "dataset.zip"
    if not path.exists():
        r = requests.get(ZIP_URL, headers={"User-Agent": UA}, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
        retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        retrieved = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return path.read_bytes(), retrieved


def num(value):
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main():
    raw, retrieved = fetch_zip()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("anage_data.txt"))
        text = zf.read(name).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    rows = list(reader)
    result = json.loads((HERE / "result.json").read_text())
    result["datasets"] = [{
        "id": "anage-build-15",
        "name": "AnAge: The Animal Ageing and Longevity Database, build 15",
        "landing_url": "https://genomics.senescence.info/species/",
        "doi": "10.1093/nar/gks1155",
        "version": "build 15",
        "license": "CC BY 3.0 (Human Ageing Genomic Resources terms)",
        "files": [{
            "name": "dataset.zip",
            "download_url": ZIP_URL,
            "retrieved_at": retrieved,
            "byte_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }],
        "role": "maximum longevity of Camelus species",
    }]
    needed = ["Genus", "Species", "Maximum longevity (yrs)", "Data quality", "Specimen origin", "Common name"]
    missing = [c for c in needed if c not in reader.fieldnames]
    if missing:
        result.update(status="complete", verdict="inconclusive", reason="data-unavailable",
                      data_kind="none", confidence=0.40)
        result["measured"] = {"value": None, "unit": "years", "n": 0, "uncertainty": None,
                              "extra": {"missing_columns": missing}}
        result["method"] = "The AnAge zip did not contain the expected longevity columns."
        (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print("missing", missing)
        return

    species = []
    for row in rows:
        if (row.get("Genus") or "").strip().casefold() != "camelus":
            continue
        years = num(row.get("Maximum longevity (yrs)"))
        if years is None or years <= 0:
            continue
        species.append({
            "binomial": f"Camelus {(row.get('Species') or '').strip()}",
            "common_name": (row.get("Common name") or "").strip(),
            "maximum_longevity_yrs": years,
            "data_quality": (row.get("Data quality") or "").strip(),
            "specimen_origin": (row.get("Specimen origin") or "").strip(),
        })
    if not species:
        result.update(status="complete", verdict="inconclusive", reason="data-unavailable",
                      data_kind="none", confidence=0.40)
        result["measured"] = {"value": None, "unit": "years (median of species maxima)", "n": 0,
                              "uncertainty": None, "extra": {"species": []}}
        result["method"] = "The AnAge table was read. No Camelus row had a positive maximum longevity."
        result["results_summary"] = ["No Camelus maximum longevity was present."]
        (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print("no camelus")
        return

    values = [s["maximum_longevity_yrs"] for s in species]
    median_m = float(statistics.median(values))
    max_m = max(values)
    thirty = 20 <= median_m <= 45
    hundred = max_m >= 90
    if thirty and hundred:
        verdict = "supports"
    elif thirty or hundred:
        verdict = "mixed"
    else:
        verdict = "refutes"
    reliable = [s for s in species if s["data_quality"].casefold() != "questionable"]
    if reliable:
        rel_values = [s["maximum_longevity_yrs"] for s in reliable]
        sens = {
            "n": len(reliable),
            "median": float(statistics.median(rel_values)),
            "maximum": max(rel_values),
        }
    else:
        sens = None
    result.update(status="complete", verdict=verdict, data_kind="biological", confidence=0.62)
    result.pop("reason", None)
    result["measured"] = {
        "value": median_m,
        "unit": "years (median of Camelus maximum longevities)",
        "n": len(species),
        "uncertainty": None,
        "extra": {
            "maximum_yrs": max_m,
            "clause_about_thirty_holds": thirty,
            "clause_to_a_hundred_holds": hundred,
            "species": species,
            "excluding_questionable": sens,
        },
    }
    result["method"] = (
        "Downloaded the AnAge build zip, kept genus Camelus rows with a positive maximum longevity "
        "in years, and applied the pre-registered windows: median in [20, 45] for the thirty-year "
        "clause and maximum >= 90 for the hundred-year clause. Both clauses must hold to support; "
        "a split is mixed; both failing refutes."
    )
    result["results_summary"] = [
        f"Camelus species n={len(species)}, median maximum longevity {median_m} years, maximum {max_m} years.",
        f"About-thirty clause holds: {thirty}. Hundred-year clause holds: {hundred}. Verdict {verdict}.",
    ]
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(result["measured"], indent=2) + "\n")
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, median_m, max_m, species)


if __name__ == "__main__":
    main()
