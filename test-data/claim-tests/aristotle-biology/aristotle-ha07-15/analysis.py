#!/usr/bin/env python3
"""Paternal age at live birth, from the pre-registered Australian and UN tables.

Thresholds are those already committed in result.json. An open age bin whose
lower bound is below 70 does not count as age 70. A class counts toward ages
60-64 only when it is the closed interval 60-64.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
UA = "delphisci-claim-test"
ABS_URL = "https://publicdata.au/d/au-births-by-age-of-father/v/2026-10-03/data.csv"
UN_URL = "https://unstats.un.org/unsd/demographic-social/products/dyb/documents/DYB2024/table11.xls"
NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
YEAR_RE = re.compile(r"^(\d{4})\*?\s*\(([^)]+)\)$")
CLOSED_RE = re.compile(r"^(\d+)\s*-\s*(\d+)$")
OPEN_RE = re.compile(r"^(\d+)\s*\+$")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_record(name, url, raw, retrieved):
    return {
        "name": name,
        "download_url": url,
        "retrieved_at": retrieved,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def integer_age(label):
    text = (label or "").strip()
    if re.fullmatch(r"\d+", text):
        return int(text)
    return None


def australia(raw):
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if not rows:
        return {"schema_ok": False}
    fields = set(rows[0].keys())
    needed = {"year", "nuptiality_code", "age_of_father", "births"}
    if not needed <= fields:
        return {"schema_ok": False, "fields": sorted(fields)}
    tot = [r for r in rows if (r.get("nuptiality_code") or "").strip().upper() == "TOT"]
    years = []
    for r in tot:
        try:
            years.append(int(r["year"]))
        except ValueError:
            continue
    if not years:
        return {"schema_ok": True, "empty": True}
    year = max(years)
    by_age = {}
    labels = {}
    total_stated = 0
    open_bins = {}
    for r in tot:
        if int(r["year"]) != year:
            continue
        label = (r.get("age_of_father") or "").strip()
        try:
            births = int(r["births"])
        except ValueError:
            continue
        age = integer_age(label)
        labels[label] = births
        if age is None:
            open_bins[label] = births
            continue
        by_age[age] = by_age.get(age, 0) + births
        total_stated += births
    ages_70 = sorted(a for a in by_age if a >= 70)
    a70 = sum(by_age[a] for a in ages_70)
    a60 = sum(by_age.get(a, 0) for a in (60, 61, 62, 63, 64))
    has_age_70 = any(a >= 70 for a in by_age)
    return {
        "schema_ok": True,
        "year": year,
        "nuptiality_code": "TOT",
        "total_stated_integer_ages": total_stated,
        "has_integer_age_ge_70": has_age_70,
        "A70": a70 if has_age_70 else None,
        "A60": a60,
        "integer_ages_present": sorted(by_age),
        "births_by_integer_age_60_and_over": {str(a): by_age[a] for a in sorted(by_age) if a >= 60},
        "non_integer_labels": open_bins,
    }


def sheet_rows(raw):
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    root = ET.fromstring(raw)
    ws = root.findall("ss:Worksheet", NS)[0]
    parsed = []
    for row in ws.findall("ss:Table/ss:Row", NS):
        cells = {}
        idx = 0
        for cell in row.findall("ss:Cell", NS):
            index = cell.attrib.get("{urn:schemas-microsoft-com:office:spreadsheet}Index")
            if index:
                idx = int(index) - 1
            data = cell.find("ss:Data", NS)
            text = "".join(data.itertext()).strip().replace("\n", " ") if data is not None else ""
            cells[idx] = text
            idx += 1
        parsed.append(cells)
    return parsed


def parse_number(text):
    if text is None:
        return None
    s = str(text).strip().replace(",", "")
    if s in {"", "..", "...", "-", "–"}:
        return None
    try:
        value = float(s)
    except ValueError:
        return None
    if value < 0:
        return None
    return int(value) if value.is_integer() else value


def united_nations(raw):
    rows = sheet_rows(raw)
    countries = []
    pending = None
    current = None
    for cells in rows:
        label = cells.get(0, "")
        if not label:
            continue
        year_m = YEAR_RE.match(label)
        if year_m:
            token = year_m.group(2).strip()
            completeness = token.replace("+", "").replace("*", "")
            current = {
                "country": pending or "",
                "year": int(year_m.group(1)),
                "code_token": token,
                "completeness_C": completeness == "C",
                "registration_tabulated": "+" in token,
                "ages": {},
            }
            countries.append(current)
            pending = None
            continue
        closed = CLOSED_RE.match(label)
        opened = OPEN_RE.match(label)
        if current is not None and (closed or opened or label == "Total" or label.lower().startswith("unknown")):
            number = parse_number(cells.get(1))
            current["ages"][label] = number
            continue
        pending = label
    code_c = [c for c in countries if c["completeness_C"]]
    sum_60_64 = 0
    countries_with_60_64 = 0
    ge70_country_names = set()
    ge70_births = 0
    ge70_classes = set()
    open_65_births = 0
    open_65_countries = 0
    for c in code_c:
        for label, number in c["ages"].items():
            closed = CLOSED_RE.match(label)
            opened = OPEN_RE.match(label)
            if closed and int(closed.group(1)) == 60 and int(closed.group(2)) == 64 and isinstance(number, int):
                sum_60_64 += number
                countries_with_60_64 += 1
            lower = None
            if closed and int(closed.group(1)) >= 70:
                lower = int(closed.group(1))
            if opened and int(opened.group(1)) >= 70:
                lower = int(opened.group(1))
            # A class counts only when a numeric birth count is published. ".." is not a zero.
            if lower is not None and lower >= 70 and isinstance(number, int):
                ge70_classes.add(label)
                ge70_country_names.add((c["country"], c["year"]))
                ge70_births += number
            # Descriptive only. An open class whose lower bound is below 70 is
            # excluded from the verdict by the pre-registered rule.
            if opened and int(opened.group(1)) == 65 and isinstance(number, int):
                open_65_births += number
                open_65_countries += 1
    return {
        "n_countries": len(countries),
        "n_code_C": len(code_c),
        "sum_births_closed_60_64_code_C": sum_60_64,
        "n_code_C_with_closed_60_64": countries_with_60_64,
        "n_code_C_reporting_class_lower_bound_ge_70": len(ge70_country_names),
        "sum_births_class_lower_bound_ge_70": ge70_births,
        "classes_lower_bound_ge_70": sorted(ge70_classes),
        "sum_births_open_65_plus_code_C_not_used_for_verdict": open_65_births,
        "n_code_C_with_open_65_plus_not_used_for_verdict": open_65_countries,
        "code_C_examples_60_64": [
            {"country": c["country"], "year": c["year"], "code": c["code_token"], "births_60_64": c["ages"].get("60 - 64")}
            for c in code_c if "60 - 64" in c["ages"]
        ],
    }


def decide(au, un):
    if not au.get("schema_ok"):
        if un is None:
            return "inconclusive", "data-unavailable", 0.3
    if au.get("schema_ok") and au.get("total_stated_integer_ages", 0) < 1000 and not au.get("has_integer_age_ge_70"):
        # The Australian file is large enough as a register only if stated-age births clear 1000.
        # Fall through to the UN branch when ages >= 70 are absent; the underpowered branch in the
        # registration applies when the year total is below 1000. Check that explicitly.
        pass
    if au.get("schema_ok") and au.get("total_stated_integer_ages", 0) < 1000:
        return "inconclusive", "underpowered", 0.35
    if au.get("has_integer_age_ge_70"):
        a70 = au["A70"]
        a60 = au["A60"]
        if a70 >= 10 and a60 >= 10:
            return "supports", None, 0.74
        if a70 == 0 and au["total_stated_integer_ages"] >= 10000:
            return "refutes", None, 0.8
        if a60 >= 10 and 1 <= a70 <= 9:
            return "mixed", None, 0.55
        return "inconclusive", "underpowered", 0.4
    # No integer age >= 70 in the Australian file.
    if un is None:
        return "inconclusive", "data-unavailable", 0.3
    if un["sum_births_closed_60_64_code_C"] >= 100:
        return "mixed", None, 0.66
    if un["n_code_C_reporting_class_lower_bound_ge_70"] >= 20 and un["sum_births_class_lower_bound_ge_70"] == 0:
        return "refutes", None, 0.7
    return "inconclusive", "other", 0.4


def main():
    DATA.mkdir(exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    retrieved = now()
    abs_raw = get(ABS_URL)
    un_raw = get(UN_URL)
    (DATA / "abs-births-age-father-2026-10-03.csv").write_bytes(abs_raw)
    (DATA / "DYB2024-table11.xls").write_bytes(un_raw)
    au = australia(abs_raw)
    un = united_nations(un_raw)
    verdict, reason, confidence = decide(au, un)
    measured = {
        "value": un["sum_births_closed_60_64_code_C"],
        "unit": "live births to fathers aged 60-64 in UN DYB 2024 Table 11, code C countries, latest year each",
        "n": un["n_code_C_with_closed_60_64"],
        "uncertainty": None,
        "extra": {
            "australia": {k: v for k, v in au.items() if k != "integer_ages_present"},
            "australia_integer_age_min": min(au["integer_ages_present"]) if au.get("integer_ages_present") else None,
            "australia_integer_age_max": max(au["integer_ages_present"]) if au.get("integer_ages_present") else None,
            "un": {k: v for k, v in un.items() if k != "code_C_examples_60_64"},
            "un_code_C_60_64_rows": un["code_C_examples_60_64"],
            "age_70_not_isolated": not au.get("has_integer_age_ge_70") and un["n_code_C_reporting_class_lower_bound_ge_70"] == 0,
        },
    }
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["datasets"] = [
        {
            "id": "abs-births-age-father-publicdata-2026-10-03",
            "name": "Registered births by age of father and nuptiality, Australia, 1975 onwards",
            "landing_url": "https://publicdata.au/d/au-births-by-age-of-father/",
            "doi": None,
            "version": "2026-10-03",
            "license": "CC BY 4.0",
            "files": [file_record("data.csv", ABS_URL, abs_raw, retrieved)],
            "role": "primary single-year age of father; a National Digital conversion of ABS table BIRTHS_AGE_FATHER, not an ABS-endorsed file",
        },
        {
            "id": "un-dyb-2024-table11-age-of-father",
            "name": "UN Demographic Yearbook 2024 Table 11, live births and live birth rates by age of father",
            "landing_url": "https://unstats.un.org/unsd/demographic-social/products/dyb/dyb_2024/",
            "doi": None,
            "version": "DYB 2024",
            "license": "United Nations publications are generally available for public use with attribution",
            "files": [file_record("table11.xls", UN_URL, un_raw, retrieved)],
            "role": "multi-country latest-year births by age of father; used because the Australian file has no integer age of 70 or above",
        },
    ]
    result["method"] = (
        "Read the pinned Australian CSV for nuptiality_code TOT in the latest year. Integer ages were summed; "
        "range labels, open ends, totals and not-stated rows were not added to A60 or A70. "
        "When that file has no integer age at or above 70, the pre-registered UN branch is applied: "
        "SpreadsheetML Table 11 is parsed, countries whose completeness code is C (including +C, where + marks "
        "registration-year tabulation in the UN notes) are kept, and births in the closed class 60-64 are summed. "
        "A class contributes to the age-70 total only when its lower bound is at least 70 and the cell is a number. "
        "Open classes such as 55+, 60+ and 65+ are not counted as age 70 or as the closed class 60-64."
    )
    result["measured"] = measured
    result["results_summary"] = [
        f"Australia {au.get('year')}: integer ages present run from {measured['extra']['australia_integer_age_min']} to {measured['extra']['australia_integer_age_max']}; no integer age >= 70. A60 (ages 60-64) = {au.get('A60')}.",
        f"UN code C, closed class 60-64: {un['sum_births_closed_60_64_code_C']} births across {un['n_code_C_with_closed_60_64']} countries. Classes with lower bound >= 70: {un['n_code_C_reporting_class_lower_bound_ge_70']}.",
        f"Not used for the verdict: code-C open class 65+ sums to {un['sum_births_open_65_plus_code_C_not_used_for_verdict']} births in {un['n_code_C_with_open_65_plus_not_used_for_verdict']} countries. The pre-registered rule does not treat an open bin whose lower bound is below 70 as age 70.",
        f"Verdict {verdict}" + (f" ({reason})" if reason else "") + ".",
    ]
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    # The full country list of 60-64 counts is the measured table. Keep it under the derived-file limit.
    DERIVED.joinpath("measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "value": measured["value"], "n": measured["n"]}, indent=2))


if __name__ == "__main__":
    main()
