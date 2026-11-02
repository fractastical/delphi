#!/usr/bin/env python3
"""Human rabies deaths in WHO GHO NTD_RAB2, with an OWID concordance check.

Decision rule: result.json pass_criterion, committed before either file was downloaded.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import re
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
WHO_URL = "https://apps.who.int/gho/athena/api/GHO/NTD_RAB2.json?profile=simple"
OWID_URL = "https://ourworldindata.org/grapher/reported-rabies-deaths.csv?v=1&csvType=full&useColumnShortNames=false"
REGION_CODES = {"GLOBAL", "AFR", "AMR", "EMR", "EUR", "SEAR", "WPR"}
REGION_NAMES = {
    "global", "world", "africa", "americas", "eastern mediterranean", "europe",
    "south-east asia", "southeast asia", "western pacific",
}
LOCKED = {
    "hypothesis", "pass_criterion", "fail_criterion", "planned_datasets", "test_contract",
    "claim_id", "claim_iri", "project", "preregistered_at", "interpretation",
}


def fetch(url, dest):
    DATA.mkdir(parents=True, exist_ok=True)
    last = None
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "delphisci-claim-test", "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = resp.read()
            dest.write_bytes(raw)
            break
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 * (i + 1))
    else:
        raise last
    raw = dest.read_bytes()
    return {
        "name": dest.name,
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }, raw


def number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text == "" or text.lower() in {"null", "none", "na", "n/a"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def who_rows(payload):
    """Return (rows, parsed) where each row is country, year, deaths."""
    rows = []
    if isinstance(payload, dict) and isinstance(payload.get("fact"), list):
        for fact in payload["fact"]:
            dim = fact.get("dim") or {}
            if str(dim.get("REGION") or dim.get("REGIONCODE") or "").upper() in REGION_CODES and not dim.get("COUNTRY"):
                continue
            spatial_type = str(dim.get("SPATIALDIMTYPE") or dim.get("SpatialDimType") or "").upper()
            if spatial_type == "REGION":
                continue
            country = dim.get("COUNTRY") or dim.get("COUNTRYCODE") or dim.get("SpatialDim")
            year = dim.get("YEAR") or dim.get("TimeDim")
            if country is None or year is None:
                continue
            if str(country).strip().upper() in REGION_CODES or str(country).strip().lower() in REGION_NAMES:
                continue
            deaths = number(fact.get("Value", fact.get("NumericValue")))
            if deaths is None:
                continue
            rows.append({"country": str(country), "year": str(year), "deaths": deaths})
        if rows:
            return rows, True
    values = None
    if isinstance(payload, dict) and isinstance(payload.get("value"), list):
        values = payload["value"]
    elif isinstance(payload, list):
        values = payload
    if values:
        for item in values:
            if not isinstance(item, dict):
                continue
            spatial_type = str(item.get("SpatialDimType") or "").upper()
            if spatial_type and spatial_type != "COUNTRY":
                continue
            country = item.get("SpatialDim") or item.get("COUNTRY") or item.get("Country")
            year = item.get("TimeDim") or item.get("YEAR") or item.get("Year")
            if country is None or year is None:
                continue
            if str(country).strip().upper() in REGION_CODES or str(country).strip().lower() in REGION_NAMES:
                continue
            deaths = number(item.get("NumericValue", item.get("Value")))
            if deaths is None:
                continue
            rows.append({"country": str(country), "year": str(year), "deaths": deaths})
        return rows, bool(rows)
    return [], False


def owid_rows(raw):
    text = raw.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    header_i = None
    for i, line in enumerate(lines[:30]):
        if "Year" in line and ("," in line or "\t" in line):
            header_i = i
            break
    if header_i is None:
        return [], False
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_i:])))
    fields = reader.fieldnames or []
    code_col = next((c for c in fields if c and c.lower() in {"code", "iso_code", "iso3"}), None)
    year_col = next((c for c in fields if c and c.lower() == "year"), None)
    death_col = next((c for c in fields if c and re.search(r"rabies|death", c, re.I) and c != year_col), None)
    if death_col is None:
        numeric_candidates = [c for c in fields if c and c not in {code_col, year_col, "Entity", "entity"}]
        death_col = numeric_candidates[-1] if numeric_candidates else None
    if not death_col or not year_col:
        return [], False
    rows = []
    for row in reader:
        code = (row.get(code_col) or "").strip() if code_col else ""
        entity = (row.get("Entity") or row.get("entity") or "").strip()
        if not re.fullmatch(r"[A-Za-z]{3}", code):
            continue
        if entity.lower() in REGION_NAMES:
            continue
        deaths = number(row.get(death_col))
        if deaths is None:
            continue
        rows.append({"country": code.upper(), "year": row.get(year_col), "deaths": deaths})
    return rows, bool(rows)


def write_result(fields):
    doc = json.loads(RESULT.read_text())
    for key in fields:
        if key in LOCKED:
            raise SystemExit("refusing to edit locked field " + key)
    caveats = list(doc.get("caveats") or [])
    if fields.pop("_caveat", None):
        caveats.append(fields.pop("_caveat"))
    # pop handled below
    doc.update(fields)
    doc["caveats"] = caveats
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    who_info = None
    try:
        who_info, who_raw = fetch(WHO_URL, DATA / "ntd_rab2.json")
        stripped = who_raw.lstrip()
        if not stripped.startswith(b"{") and not stripped.startswith(b"["):
            raise ValueError("WHO response was not JSON; it begins with " + stripped[:40].decode("utf-8", errors="replace"))
        who_payload = json.loads(who_raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        measured = {"value": None, "unit": "WHO country-years with at least one reported human rabies death", "n": 0, "uncertainty": None, "extra": {"error": str(exc)}}
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        doc = json.loads(RESULT.read_text())
        datasets = []
        if who_info:
            datasets = [{
                "id": "who-gho-ntd-rab2",
                "name": "WHO GHO athena request for NTD_RAB2",
                "landing_url": "https://www.who.int/data/gho/data/indicators/indicator-details/GHO/reported-number-of-human-rabies-deaths",
                "doi": None,
                "version": "athena profile=simple at retrieval",
                "license": "WHO Global Health Observatory",
                "files": [who_info],
                "role": "intended country-year death series; the body received was not JSON",
            }]
        doc.update({
            "status": "complete", "verdict": "inconclusive", "reason": "data-unavailable",
            "confidence": 0.3, "data_kind": "none", "measured": measured, "datasets": datasets,
            "method": "The pre-registered WHO athena URL was fetched. The body was not a JSON series, so no death count was computed and the OWID file was not used as a substitute.",
            "results_summary": [f"WHO request failed: {exc}"],
        })
        RESULT.write_text(json.dumps(doc, indent=2) + "\n")
        print("inconclusive", exc)
        return
    rows, parsed = who_rows(who_payload)
    if not parsed:
        keys = list(who_payload)[:20] if isinstance(who_payload, dict) else [type(who_payload).__name__]
        measured = {"value": None, "unit": "WHO country-years with at least one reported human rabies death", "n": 0, "uncertainty": None, "extra": {"top_level_keys": keys}}
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        doc = json.loads(RESULT.read_text())
        doc.update({
            "status": "complete", "verdict": "inconclusive", "reason": "data-unavailable",
            "confidence": 0.35, "data_kind": "none", "measured": measured,
            "datasets": [{
                "id": "who-gho-ntd-rab2",
                "name": "WHO GHO reported number of human rabies deaths (NTD_RAB2)",
                "landing_url": "https://www.who.int/data/gho/data/indicators/indicator-details/GHO/reported-number-of-human-rabies-deaths",
                "doi": None, "version": "athena profile=simple at retrieval",
                "license": "WHO Global Health Observatory",
                "files": [who_info],
                "role": "country-year reported human rabies deaths",
            }],
            "method": "The WHO file downloaded, but no country-year numeric values were identified. No substitute source was scored.",
            "results_summary": ["WHO JSON keys: " + ", ".join(map(str, keys))],
        })
        RESULT.write_text(json.dumps(doc, indent=2) + "\n")
        print("unparsed", keys)
        return

    positive = [r for r in rows if r["deaths"] >= 1]
    positive.sort(key=lambda r: (-r["deaths"], r["country"], r["year"]))
    owid_note = None
    owid_positive = None
    owid_info = None
    try:
        owid_info, owid_raw = fetch(OWID_URL, DATA / "reported-rabies-deaths.csv")
        owid, owid_ok = owid_rows(owid_raw)
        if owid_ok:
            owid_positive = sum(1 for r in owid if r["deaths"] >= 1)
        else:
            owid_note = "The OWID file downloaded but did not yield country-year death counts, so the verdict follows WHO."
    except Exception as exc:  # noqa: BLE001
        owid_note = f"The OWID concordance file could not be fetched ({exc}); the verdict follows WHO."

    if len(rows) >= 50 and not positive:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.45
    elif positive and owid_positive == 0:
        verdict, reason, confidence = "mixed", None, 0.40
    elif positive:
        verdict, reason, confidence = "refutes", None, (0.88 if len(positive) >= 10 else 0.70)
    else:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.4

    measured = {
        "value": len(positive),
        "unit": "WHO country-years with at least one reported human rabies death",
        "n": len(rows),
        "uncertainty": None,
        "extra": {
            "who_death_sum": sum(r["deaths"] for r in rows),
            "who_positive_country_years": len(positive),
            "who_countries_with_a_death": len({r["country"] for r in positive}),
            "who_year_min": min((r["year"] for r in rows), default=None),
            "who_year_max": max((r["year"] for r in rows), default=None),
            "highest_country_years": positive[:10],
            "owid_positive_country_years": owid_positive,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    datasets = [{
        "id": "who-gho-ntd-rab2",
        "name": "WHO GHO reported number of human rabies deaths (NTD_RAB2)",
        "landing_url": "https://www.who.int/data/gho/data/indicators/indicator-details/GHO/reported-number-of-human-rabies-deaths",
        "doi": None,
        "version": "athena profile=simple at retrieval",
        "license": "WHO Global Health Observatory",
        "files": [who_info],
        "role": "primary country-year counts of reported human rabies deaths",
    }]
    if owid_info:
        datasets.append({
            "id": "owid-reported-rabies-deaths",
            "name": "Our World in Data, reported deaths from rabies",
            "landing_url": "https://ourworldindata.org/grapher/reported-rabies-deaths",
            "doi": None,
            "version": "chart CSV at retrieval",
            "license": "Our World in Data chart download of the WHO GHO series; OWID's general licence was not re-read from a metadata file in this run",
            "files": [owid_info],
            "role": "concordance check on the sign of the WHO series",
        })
    doc = json.loads(RESULT.read_text())
    if owid_note:
        doc["caveats"] = list(doc.get("caveats") or []) + [owid_note]
    doc.update({
        "status": "complete",
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological",
        "measured": measured,
        "datasets": datasets,
        "method": "Downloaded the WHO athena series for NTD_RAB2, kept country-year numeric death counts, dropped the pre-listed regional aggregates, and counted country-years with at least one death. The OWID CSV was the concordance check and was not allowed to create a support.",
        "results_summary": [
            f"WHO country-year rows: {len(rows)}. Rows with at least one death: {len(positive)}. Sum of reported deaths: {measured['extra']['who_death_sum']}.",
            f"OWID positive country-years: {owid_positive}.",
            "Animal fatality was not scored.",
        ],
    })
    if reason:
        doc["reason"] = reason
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    print(verdict, len(positive), owid_positive)


if __name__ == "__main__":
    main()
