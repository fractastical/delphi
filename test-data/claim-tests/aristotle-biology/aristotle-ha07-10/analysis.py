#!/usr/bin/env python3
"""aristotle-ha07-10: survival of live births before 28 completed weeks.

Thresholds are the ones committed in result.json before this workbook was
opened. The workbook is larger than 1 MB and is not committed.

Run: python3 analysis.py
Requires openpyxl.
"""

import csv
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"

FILE_NAME = "cimdeathcohort2024.xlsx"
FILE_URL = (
    "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/"
    "birthsdeathsandmarriages/deaths/datasets/"
    "childmortalitystatisticschildhoodinfantandperinatalchildhoodinfantandperinatalmortalityinenglandandwales/"
    "2024/cimdeathcohort2024.xlsx"
)
FILE_SHA256 = "f66f81a39cbfedb39db152c377a807ad0cdcbda7c600dd6a1054b2083b973c09"
FILE_SIZE = 1501092


def utc_stamp(path, downloaded_now):
    if downloaded_now:
        return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch():
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / FILE_NAME
    downloaded_now = False
    if not path.exists():
        req = urllib.request.Request(FILE_URL, headers={"User-Agent": "delphisci-claim-test/1.0"})
        path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        downloaded_now = True
    raw = path.read_bytes()
    return path, {
        "name": FILE_NAME,
        "download_url": FILE_URL,
        "retrieved_at": utc_stamp(path, downloaded_now),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "matches_registered_sha256": hashlib.sha256(raw).hexdigest() == FILE_SHA256,
        "matches_registered_size": len(raw) == FILE_SIZE,
    }


def as_int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if re.fullmatch(r"-?\d+", text):
            return int(text)
    return None


def classify_gestation(label):
    text = str(label).strip().lower()
    under = re.fullmatch(r"under\s+(\d+)\s+weeks", text)
    if under:
        # "Under N weeks" contains completed weeks 0 through N-1.
        highest_week = int(under.group(1)) - 1
        return {"label": str(label), "highest_week": highest_week, "admissible": highest_week <= 27, "seven_month": False}
    span = re.fullmatch(r"(\d+)\s+to\s+(\d+)\s+weeks", text)
    if span:
        high = int(span.group(2))
        low = int(span.group(1))
        return {
            "label": str(label),
            "highest_week": high,
            "admissible": high <= 27,
            "seven_month": low == 28 and high == 31,
        }
    return {"label": str(label), "highest_week": None, "admissible": False, "seven_month": False}


def load_rows(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Table_8"]
    header = None
    rows = []
    for row in ws.iter_rows(values_only=True):
        if row and row[0] == "Year":
            header = [str(c).strip() if c is not None else "" for c in row]
            continue
        if header is None or row is None or row[0] != 2024:
            continue
        record = {header[i]: row[i] if i < len(row) else None for i in range(len(header))}
        rows.append(record)
    return rows


def main():
    path, info = fetch()
    if not (info["matches_registered_sha256"] and info["matches_registered_size"]):
        finish(info, "inconclusive", "data-unavailable", 0.8, {"checksums_ok": False}, ["The workbook did not match the recorded size or checksum."], [])
        return
    rows = load_rows(path)
    chosen = [
        r for r in rows
        if r.get("Country") == "England and Wales"
        and r.get("Ethnicity") == "All ethnicities"
        and r.get("Cause group") == "All causes"
    ]
    by_gestation = {}
    for record in chosen:
        label = record.get("Gestational age")
        event = record.get("Event")
        if label is None or event is None:
            continue
        slot = by_gestation.setdefault(str(label), {"class": classify_gestation(label), "events": {}})
        slot["events"][str(event)] = as_int(record.get("Number"))

    bins = []
    for label, slot in by_gestation.items():
        klass = slot["class"]
        births = slot["events"].get("Live birth")
        infant_deaths = slot["events"].get("Infant death")
        neonatal_deaths = slot["events"].get("Neonatal death")
        if not (klass["admissible"] or klass["seven_month"]):
            continue
        survivors = None if births is None or infant_deaths is None else births - infant_deaths
        neonatal_survivors = None if births is None or neonatal_deaths is None else births - neonatal_deaths
        bins.append({
            "gestational_age": label,
            "highest_completed_week": klass["highest_week"],
            "admissible_before_28_weeks": klass["admissible"],
            "seven_month_bin": klass["seven_month"],
            "live_births": births,
            "infant_deaths_under_1_year": infant_deaths,
            "neonatal_deaths_under_28_days": neonatal_deaths,
            "survivors_to_1_year_period_difference": survivors,
            "alive_at_28_days_period_difference": neonatal_survivors,
        })

    admissible = [b for b in bins if b["admissible_before_28_weeks"]]
    usable = [b for b in admissible if b["live_births"] is not None and b["survivors_to_1_year_period_difference"] is not None and b["survivors_to_1_year_period_difference"] >= 0]
    unusable = [b for b in admissible if b not in usable]
    seven = [b for b in bins if b["seven_month_bin"]]
    births = sum(b["live_births"] for b in usable)
    survivors = sum(b["survivors_to_1_year_period_difference"] for b in usable)
    deaths = sum(b["infant_deaths_under_1_year"] for b in usable)

    extra = {
        "checksums_ok": True,
        "filters": "Year 2024, country England and Wales, ethnicity All ethnicities, cause group All causes",
        "horizon": "infant death under 1 year",
        "bins": bins,
        "admissible_bins_unusable": [b["gestational_age"] for b in unusable],
        "live_births_before_28_weeks": births,
        "infant_deaths_before_28_weeks": deaths,
        "survivors_before_28_weeks": survivors,
        "death_cohort_note": (
            "Table 8 is a death cohort: infant deaths occurring in 2024 are divided by live births in 2024. "
            "Deaths of infants born in 2023 can sit in the numerator, so births minus deaths is a lower bound on survivors of the 2024 births, not an exact cohort count."
        ),
    }
    if not admissible or not usable:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.8
        summary = ["No gestational-age bin lying entirely below 28 completed weeks had both a live-birth count and an infant-death count."]
    elif survivors >= 1:
        verdict, reason = "refutes", None
        confidence = 0.9 if survivors >= 10 and births >= 100 else 0.75
        summary = [
            f"Live births below 28 completed weeks: {births}. Infant deaths under one year in those bins: {deaths}. Births minus deaths: {survivors}.",
            "Bins: " + "; ".join(
                f"{b['gestational_age']}: {b['live_births']} live births, {b['infant_deaths_under_1_year']} infant deaths, difference {b['survivors_to_1_year_period_difference']}"
                for b in usable
            ) + ".",
            "The difference is positive in a death-cohort table, so it understates rather than invents survivors of this year's births.",
        ]
    elif births >= 100:
        if seven and any((b.get("survivors_to_1_year_period_difference") or 0) >= 1 for b in seven):
            verdict, reason, confidence = "supports", None, 0.55
            summary = [f"No survivor in {births} live births below 28 weeks, and the 28-to-31-week bin has a survivor."]
        elif not seven:
            verdict, reason, confidence = "inconclusive", "other", 0.6
            summary = [f"No survivor in {births} live births below 28 weeks, and the 28-to-31-week bin is absent."]
        else:
            verdict, reason, confidence = "inconclusive", "other", 0.6
            summary = [f"No survivor below 28 weeks in {births} live births, and the 28-to-31-week bin has no counted survivor."]
    else:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.5
        summary = [f"Zero survivors but only {births} live births below 28 weeks."]

    finish(info, verdict, reason, confidence, extra, summary, usable)
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "births": births, "deaths": deaths, "survivors": survivors}, indent=2))


def finish(info, verdict, reason, confidence, extra, summary, usable):
    DERIVED.mkdir(parents=True, exist_ok=True)
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "none" if reason == "data-unavailable" else "biological"
    result["datasets"] = [
        {
            "id": "ons-england-wales-child-infant-mortality-2024-cimdeathcohort",
            "name": "Child and infant mortality (by year of death), England and Wales, 2024",
            "landing_url": "https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/deaths/datasets/childmortalitystatisticschildhoodinfantandperinatalchildhoodinfantandperinatalmortalityinenglandandwales/2024",
            "doi": None,
            "version": "2024 release, corrected workbook cimdeathcohort2024.xlsx",
            "license": "Open Government Licence v3.0",
            "files": [info],
            "role": "live births and infant deaths by gestational age in England and Wales, Table 8",
        }
    ]
    result["measured"] = {
        "value": extra.get("survivors_before_28_weeks"),
        "unit": "live births below 28 completed weeks minus infant deaths under one year in those bins",
        "n": extra.get("live_births_before_28_weeks") or 0,
        "uncertainty": "death-cohort numerator can include infants born in the previous year, so a positive difference is a lower bound",
        "extra": extra,
    }
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["method"] = (
        "Downloaded the ONS 2024 death-cohort workbook and checked its size and SHA-256. "
        "From Table 8 kept the 2024 rows for England and Wales, all ethnicities and all causes, so country, ethnicity and cause subgroups were not added twice. "
        "Treated 'Under 24 weeks' and '24 to 27 weeks' as the bins lying entirely below 28 completed weeks. "
        "Subtracted infant deaths under one year from live births in each of those bins and applied the pre-registered rule. "
        "'Most of them are weakly' was not scored."
    )
    result["results_summary"] = summary
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    with (DERIVED / "gestation-bins.csv").open("w", newline="") as fh:
        fields = ["gestational_age", "highest_completed_week", "admissible_before_28_weeks", "seven_month_bin", "live_births", "infant_deaths_under_1_year", "neonatal_deaths_under_28_days", "survivors_to_1_year_period_difference", "alive_at_28_days_period_difference"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in extra.get("bins", []):
            writer.writerow(row)
    (DERIVED / "measured.json").write_text(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "measured": result["measured"]}, indent=2) + "\n")


if __name__ == "__main__":
    main()
