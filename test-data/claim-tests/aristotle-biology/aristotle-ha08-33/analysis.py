#!/usr/bin/env python3
"""aristotle-ha08-33: reported human rabies deaths versus the exception for man.

Rules are those in result.json. Run: python3 analysis.py
"""
import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
DERIVED = HERE / "derived"
DATA = HERE / "data"
OWID_URL = "https://ourworldindata.org/grapher/reported-rabies-deaths.csv"
NNDSS_URL = "https://data.cdc.gov/api/views/6uy5-4d9d/rows.csv?accessType=DOWNLOAD"


def fetch(name, url):
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / name
    req = urllib.request.Request(url, headers={"User-Agent": "delphisci-claim-test"})
    try:
        raw = urllib.request.urlopen(req, timeout=180).read()
    except Exception as exc:
        return None, {"name": name, "download_url": url, "error": str(exc)}
    path.write_bytes(raw)
    return path, {
        "name": name,
        "download_url": url,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def parse_number(cell):
    if cell is None:
        return None
    s = str(cell).strip().replace(",", "")
    if s == "" or s.upper() in {"NA", "N/A", "-", "—", "U"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def owid_sum(path):
    import csv
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    death_col = "Reported number of human rabies deaths"
    if death_col not in rows[0]:
        return None
    total = 0.0
    n_rows = 0
    n_positive = 0
    max_cell = 0.0
    for r in rows:
        code = (r.get("Code") or "").strip()
        if len(code) != 3 or not code.isalpha():
            continue
        val = parse_number(r.get(death_col))
        if val is None:
            continue
        total += val
        n_rows += 1
        if val > 0:
            n_positive += 1
        if val > max_cell:
            max_cell = val
    return {"sum_deaths": total, "n_country_rows": n_rows, "n_positive_rows": n_positive, "max_cell": max_cell}


def nndss_totals(path):
    import csv
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    fields = rows[0].keys()
    human_cum = next((c for c in fields if c.lower().startswith("rabies_human_cum_") and "flag" not in c.lower()), None)
    animal_cum = next((c for c in fields if c.lower().startswith("rabies_animal_cum_") and "flag" not in c.lower()), None)
    human_week = next((c for c in fields if "rabies_human_current_week" in c.lower() and "flag" not in c.lower()), None)
    area_col = "Reporting Area" if "Reporting Area" in fields else "reporting_area"
    week_col = "MMWR Week" if "MMWR Week" in fields else "mmwr_week"

    def area_of(r):
        return (r.get(area_col) or "").strip().upper()

    totals = [r for r in rows if area_of(r) == "TOTAL"]
    if not totals:
        totals = [r for r in rows if area_of(r) in {"UNITED STATES", "US"}]
    if not totals:
        return {"error": "no total row", "columns": list(fields)}

    def week_num(r):
        v = parse_number(r.get(week_col))
        return v if v is not None else -1

    last = max(totals, key=week_num)
    human = parse_number(last.get(human_cum)) if human_cum else None
    animal = parse_number(last.get(animal_cum)) if animal_cum else None
    fallback = None
    if human is None and human_week:
        vals = [parse_number(r.get(human_week)) for r in totals]
        nums = [v for v in vals if v is not None]
        fallback = sum(nums) if nums else None
        human = fallback
    return {
        "human_cumulative": human,
        "animal_cumulative": animal,
        "human_from_week_sum": fallback,
        "mmwr_week": week_num(last),
        "reporting_area": area_of(last),
        "human_column": human_cum,
        "animal_column": animal_cum,
    }


def main():
    result = json.loads(RESULT.read_text())
    DERIVED.mkdir(parents=True, exist_ok=True)
    owid_path, owid_info = fetch("owid-reported-rabies-deaths.csv", OWID_URL)
    nndss_path, nndss_info = fetch("nndss-1cc-2022.csv", NNDSS_URL)
    owid = owid_sum(owid_path) if owid_path else None
    nndss = nndss_totals(nndss_path) if nndss_path else None
    owid_positive = owid is not None and owid["sum_deaths"] >= 1
    nndss_positive = nndss is not None and nndss.get("human_cumulative") is not None and nndss["human_cumulative"] >= 1
    owid_zero = owid is not None and owid["n_country_rows"] >= 30 and owid["sum_deaths"] == 0
    nndss_zero_or_missing = nndss is None or nndss.get("human_cumulative") in {None, 0}

    if owid is None and (nndss is None or nndss.get("human_cumulative") is None):
        verdict, reason, conf = "inconclusive", "data-unavailable", 0.25
        data_kind = "none"
    elif owid_positive or nndss_positive:
        verdict, reason, conf = "refutes", None, 0.9
        data_kind = "biological"
    elif owid_zero and nndss_zero_or_missing:
        verdict, reason, conf = "supports", None, 0.55
        data_kind = "biological"
    else:
        verdict, reason, conf = "inconclusive", "data-unavailable", 0.3
        data_kind = "none"

    measured = {
        "value": None if owid is None else owid["sum_deaths"],
        "unit": "reported human rabies deaths, sum of OWID country rows",
        "n": None if owid is None else owid["n_country_rows"],
        "extra": {"owid": owid, "nndss_2022": nndss},
    }
    result.update({
        "status": "complete",
        "verdict": verdict,
        "confidence": conf,
        "data_kind": data_kind,
        "measured": measured,
        "method": "Summed reported human rabies deaths on OWID rows with a three-letter country code, and read the NNDSS 2022 national total cumulative human count at the last MMWR week. A positive count on either source refutes the exception for man. Animal counts were stored and not scored.",
        "datasets": [
            {
                "id": "owid-reported-human-rabies-deaths",
                "name": "Our World in Data, reported number of human rabies deaths",
                "landing_url": "https://ourworldindata.org/grapher/reported-rabies-deaths",
                "doi": None,
                "version": "as retrieved",
                "license": "CC BY",
                "files": [owid_info],
                "role": "country-year reported human rabies deaths",
            },
            {
                "id": "nndss-table-1cc-2022-6uy5-4d9d",
                "name": "NNDSS Table 1CC, Rabies animal and human, 2022",
                "landing_url": "https://data.cdc.gov/d/6uy5-4d9d",
                "doi": None,
                "version": "2022",
                "license": "public domain (U.S. government work)",
                "files": [nndss_info],
                "role": "United States provisional cumulative human and animal rabies cases for 2022",
            },
        ],
    })
    if reason:
        result["reason"] = reason
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, measured["value"])


if __name__ == "__main__":
    main()
