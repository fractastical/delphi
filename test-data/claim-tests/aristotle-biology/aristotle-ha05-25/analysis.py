#!/usr/bin/env python3
"""Human reproductive ages (aristotle-ha05-25).

Female clause: WPP 2024 single-year fertility in 1950, countries with TFR >= 6.
Male clause: Demographic Yearbook 2024 Table 11 birth counts by age of father.
Thresholds are the ones committed in result.json before either file was opened.

Run from this directory: python3 analysis.py
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import re
from pathlib import Path

import xml.etree.ElementTree as ET

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test/1.0 (aristotle-ha05-25)"}
WPP_URL = (
    "https://population.un.org/wpp/assets/Excel%20Files/"
    "1_Indicator%20(Standard)/CSV_FILES/WPP2024_Fertility_by_Age1.csv.gz"
)
DYB_URL = "https://unstats.un.org/unsd/demographic-social/products/dyb/documents/DYB2024/table11.xls"
NAME_DROP = re.compile(
    r"income|developed regions|least developed|less developed|more developed|"
    r"small island|land-locked|landlocked|world bank|sdg |geographic region|"
    r"^world$|^africa$|^asia$|^europe$|^oceania$|latin america and the caribbean|"
    r"^northern america$",
    re.I,
)


def now_iso(path: Path) -> str:
    stamp = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, dest: Path) -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size == 0:
        with requests.get(url, headers=UA, timeout=600, stream=True) as response:
            response.raise_for_status()
            partial = dest.with_suffix(dest.suffix + ".part")
            with partial.open("wb") as handle:
                for chunk in response.iter_content(1 << 20):
                    if chunk:
                        handle.write(chunk)
            partial.replace(dest)
    raw = dest.read_bytes()
    return {
        "download_url": url,
        "retrieved_at": now_iso(dest),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def pick(columns, pattern, forbid=None):
    hits = []
    for name in columns:
        low = str(name).lower()
        if re.search(pattern, low) and not (forbid and re.search(forbid, low)):
            hits.append(name)
    return hits[0] if hits else None


def as_year(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    match = re.match(r"^(\d{4})", text)
    if not match:
        return None
    return int(match.group(1))


def as_float(value):
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def female_schedules(path: Path, deviations: list) -> dict:
    """Stream the gzipped CSV. Keep 1950 and 2023 country schedules only."""
    kept = {1950: {}, 2023: {}}
    columns = None
    mapping = {}
    max_rate = 0.0
    n_rows = 0
    with gzip.open(path, "rt", newline="") as handle:
        reader = pd.read_csv(handle, chunksize=200_000, low_memory=False)
        for chunk in reader:
            if columns is None:
                columns = list(chunk.columns)
                mapping = {
                    "location": pick(columns, r"^location$") or pick(columns, r"location", r"code|id|type"),
                    "iso3": pick(columns, r"iso3"),
                    "variant": pick(columns, r"variant"),
                    "year": pick(columns, r"^time$|^year$|midperiod", r"id|label"),
                    "age": pick(columns, r"agegrpstart|^agestart$|^age$"),
                    "span": pick(columns, r"agegrpspan|agespan|^span$"),
                    "rate": pick(columns, r"^asfr$|^value$|fertilityrate", r"id|note|label"),
                }
                if mapping["rate"] is None:
                    mapping["rate"] = pick(columns, r"asfr|fertility")
                if mapping["year"] is None:
                    mapping["year"] = pick(columns, r"time")
                if mapping["age"] is None:
                    mapping["age"] = pick(columns, r"age", r"id|label|span|end|grp$")
                deviations.append(f"WPP columns used: {mapping}. All columns: {columns}")
            n_rows += len(chunk)
            year_series = chunk[mapping["year"]].map(as_year) if mapping["year"] else None
            if year_series is None:
                break
            chunk = chunk[year_series.isin([1950, 2023])].copy()
            if chunk.empty:
                continue
            if mapping["variant"]:
                variant = chunk[mapping["variant"]].astype(str).str.lower()
                medium = variant.str.contains("medium") | variant.str.contains("estimat")
                if medium.any():
                    chunk = chunk[medium]
            for row in chunk.itertuples(index=False):
                # itertuples renames columns; use _asdict if available via named tuples
                pass
            records = chunk.to_dict("records")
            for row in records:
                year = as_year(row.get(mapping["year"]))
                if year not in (1950, 2023):
                    continue
                iso = row.get(mapping["iso3"]) if mapping["iso3"] else None
                iso_text = "" if iso is None or (isinstance(iso, float) and pd.isna(iso)) else str(iso).strip()
                if not iso_text or iso_text.lower() in {"nan", "none"}:
                    continue
                location = str(row.get(mapping["location"]) or iso_text)
                if NAME_DROP.search(location):
                    continue
                age = as_float(row.get(mapping["age"]))
                rate = as_float(row.get(mapping["rate"]))
                span = as_float(row.get(mapping["span"])) if mapping["span"] else 1.0
                if age is None or rate is None:
                    continue
                if span is None:
                    span = 1.0
                max_rate = max(max_rate, rate)
                bucket = kept[year].setdefault(iso_text, {"location": location, "ages": {}})
                bucket["ages"][int(age)] = {"rate": rate, "span": span}
    scale = 1000.0 if max_rate > 5 else 1.0
    return {"schedules": kept, "scale": scale, "max_rate_raw": max_rate, "n_rows_scanned": n_rows, "columns": mapping}


def schedule_shares(bucket: dict, scale: float) -> dict | None:
    items = []
    for age, payload in bucket["ages"].items():
        rate = payload["rate"] / scale
        span = payload["span"] or 1.0
        items.append((age, span, rate))
    if not items:
        return None
    # Single-year file: contribution is the rate. Five-year file: contribution is rate * span
    # when span is stored and is greater than 1.
    spans = [span for _, span, _ in items]
    use_span = (sum(spans) / len(spans)) > 1.5
    total = 0.0
    bands = {"40-44": 0.0, "45-49": 0.0, "50+": 0.0}
    oldest_at_least_0001 = None
    for age, span, rate in items:
        contribution = rate * span if use_span else rate
        total += contribution
        hi = age + (span if use_span else 1) - 1
        # overlap of [age, hi] with each band, assuming a flat rate inside the bin
        def overlap(lo_b, hi_b):
            left = max(age, lo_b)
            right = min(hi, hi_b)
            if right < left:
                return 0.0
            width = (hi - age + 1) or 1
            return contribution * ((right - left + 1) / width)

        bands["40-44"] += overlap(40, 44)
        bands["45-49"] += overlap(45, 49)
        bands["50+"] += overlap(50, 120)
        if rate >= 0.001 and (oldest_at_least_0001 is None or age > oldest_at_least_0001):
            oldest_at_least_0001 = age
    if total <= 0:
        return None
    return {
        "tfr": total,
        "s4044": bands["40-44"] / total,
        "s4549": bands["45-49"] / total,
        "s50": bands["50+"] / total,
        "oldest_rate_ge_0.001": oldest_at_least_0001,
        "max_age": max(age for age, _, _ in items),
    }


def median(values):
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return None
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def female_clause(path: Path, deviations: list) -> dict:
    raw = female_schedules(path, deviations)
    scale = raw["scale"]
    out = {"scale_divisor": scale, "max_rate_raw": raw["max_rate_raw"], "n_rows_scanned": raw["n_rows_scanned"]}
    year_stats = {}
    for year, schedules in raw["schedules"].items():
        rows = []
        for iso, bucket in schedules.items():
            shares = schedule_shares(bucket, scale)
            if not shares:
                continue
            shares["iso3"] = iso
            shares["location"] = bucket["location"]
            rows.append(shares)
        high = [row for row in rows if row["tfr"] >= 6.0]
        year_stats[year] = {
            "n_countries": len(rows),
            "n_tfr_ge_6": len(high),
            "median_tfr_high": median([row["tfr"] for row in high]),
            "S4044": median([row["s4044"] for row in high]),
            "S4549": median([row["s4549"] for row in high]),
            "S50": median([row["s50"] for row in high]),
            "median_oldest_rate_ge_0.001": median(
                [row["oldest_rate_ge_0.001"] for row in high if row["oldest_rate_ge_0.001"] is not None]
            ),
            "max_age_seen": max((row["max_age"] for row in rows), default=None),
        }
    primary = year_stats.get(1950, {})
    n_high = primary.get("n_tfr_ge_6") or 0
    if n_high < 10:
        call = "underpowered"
    else:
        s4044 = primary["S4044"]
        s4549 = primary["S4549"]
        s50 = primary["S50"]
        oldest = primary["median_oldest_rate_ge_0.001"]
        max_age = primary["max_age_seen"] or 0
        refute = (
            (s50 is not None and s50 > 0.02)
            or (s4549 is not None and s4549 > 0.08)
            or (s4044 is not None and s4044 < 0.005 and oldest is not None and oldest <= 40)
        )
        can_pass_50 = max_age >= 50
        passes = (
            can_pass_50
            and s4044 is not None
            and s4549 is not None
            and s50 is not None
            and s4044 >= 0.02
            and s4549 <= 0.03
            and s50 <= 0.005
        )
        if refute:
            call = "refutes"
        elif passes:
            call = "supports"
        else:
            call = "mixed"
    out["by_year"] = {
        str(year): {key: (None if isinstance(value, float) and pd.isna(value) else value) for key, value in stats.items()}
        for year, stats in year_stats.items()
    }
    # round floats for the JSON
    for stats in out["by_year"].values():
        for key, value in list(stats.items()):
            if isinstance(value, float):
                stats[key] = round(value, 6)
    out["call"] = call
    out["primary_year"] = 1950
    return out


def cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return str(value)
    return str(value).strip()


def age_kind(text: str):
    low = text.lower().replace("–", "-").replace("—", "-")
    low = re.sub(r"\s+", "", low)
    if re.search(r"65\+|65and|65or|>=65|≥65", low):
        return "65+"
    match = re.search(r"(\d{2})-(\d{2})", low)
    if match:
        lo, hi = int(match.group(1)), int(match.group(2))
        return f"{lo}-{hi}"
    if low in {"total", "allages"}:
        return "total"
    if "unknown" in low or low in {"...", "…"}:
        return "unknown"
    if re.search(r"under20|<20|0-19", low):
        return "0-19"
    return None


SS = "{urn:schemas-microsoft-com:office:spreadsheet}"
FATHER_BINS = ("50-54", "55-59", "60-64", "65+")


def parse_fathers(path: Path, deviations: list) -> dict:
    """Table 11 is SpreadsheetML with a UTF-8 BOM, one age group per row.

    The count is the first integer cell. sDataIntegerItalic is the Yearbook's
    italics mark for incomplete registration, so those country-years are dropped.
    """
    deviations.append(
        "Table 11 is Office SpreadsheetML (it begins with an XML declaration, not a BIFF workbook). "
        "Counts were read from that XML. Incomplete registration is the italic integer style "
        "sDataIntegerItalic on the Total row, and those country-years were dropped."
    )
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    root = ET.fromstring(raw)
    countries = []
    country = None
    year = None
    counts = {}
    italic_total = False

    def flush():
        nonlocal counts, italic_total
        if country and year and "total" in counts and not italic_total:
            if NAME_DROP.search(country):
                counts = {}
                italic_total = False
                return
            total = counts["total"]
            if all(key in counts for key in FATHER_BINS) and total >= 10000:
                countries.append({"country": country, "year": year, "counts": dict(counts), "total": total})
        counts = {}
        italic_total = False

    for row in root.iter(f"{SS}Row"):
        cells = []
        for cell in list(row):
            if not cell.tag.endswith("Cell"):
                continue
            style = cell.attrib.get(f"{SS}StyleID", "")
            data = None
            for child in cell:
                if child.tag.endswith("Data"):
                    data = "".join(child.itertext()).strip()
            cells.append((style, data))
        if not cells or cells[0][1] is None:
            continue
        style, text = cells[0]
        if style == "sCountryName":
            flush()
            country = text.split(" - ")[0].strip()
            year = None
        elif style == "sRefDate":
            flush()
            year = as_year(text)
        elif style == "sAgeGroup":
            kind = age_kind(text)
            number = None
            number_style = ""
            for cell_style, cell_text_value in cells[1:]:
                if "Integer" in cell_style and cell_text_value not in {None, "", ".."}:
                    try:
                        number = float(cell_text_value)
                        number_style = cell_style
                    except ValueError:
                        number = None
                    break
            if kind and number is not None:
                counts[kind] = number
                if kind == "total" and "Italic" in number_style:
                    italic_total = True
    flush()
    # latest year per country
    latest = {}
    for row in countries:
        previous = latest.get(row["country"])
        if previous is None or row["year"] > previous["year"]:
            latest[row["country"]] = row
    kept = []
    dropped_unbalanced = 0
    for row in latest.values():
        counts = row["counts"]
        bins = {key: counts.get(key) or 0 for key in FATHER_BINS}
        accounted = sum(value for key, value in counts.items() if key != "total")
        if row["total"] <= 0 or abs(accounted - row["total"]) / row["total"] > 0.02:
            dropped_unbalanced += 1
            continue
        unknown = counts.get("unknown") or 0
        known = row["total"] - unknown
        if known <= 0:
            continue
        kept.append({**row, "known": known, "bins": bins})
    pool_known = sum(row["known"] for row in kept)
    pool_bins = {key: sum(row["bins"][key] for row in kept) for key in FATHER_BINS}
    if pool_known == 0:
        return {"call": "data-unavailable", "n_countries": 0, "dropped_unbalanced": dropped_unbalanced}
    share_65 = pool_bins["65+"] / pool_known
    share_5064 = (pool_bins["50-54"] + pool_bins["55-59"] + pool_bins["60-64"]) / pool_known
    if share_65 >= 0.02 or (pool_known >= 500_000 and share_5064 == 0 and pool_bins["65+"] == 0):
        call = "refutes"
    elif pool_bins["60-64"] > 0 and pool_bins["65+"] > 0 and share_65 < 0.005 and share_5064 >= 0.005:
        call = "supports"
    else:
        call = "mixed"
    return {
        "call": call,
        "n_countries": len(kept),
        "pooled_births_known_age": pool_known,
        "pooled_bins": pool_bins,
        "share_65_plus": round(share_65, 6),
        "share_50_64": round(share_5064, 6),
        "dropped_unbalanced": dropped_unbalanced,
        "n_country_years_read": len(countries),
    }


def combine(female_call: str, male_call: str):
    if female_call == "refutes" or male_call == "refutes":
        return "refutes", None
    if female_call == "underpowered":
        return "inconclusive", "underpowered"
    if male_call == "data-unavailable":
        if female_call == "supports":
            return "inconclusive", "data-unavailable"
        if female_call == "mixed":
            return "mixed", None
        return "inconclusive", "data-unavailable"
    if female_call == "supports" and male_call == "supports":
        return "supports", None
    return "mixed", None


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    deviations = []
    wpp = fetch(WPP_URL, DATA / "WPP2024_Fertility_by_Age1.csv.gz")
    dyb = fetch(DYB_URL, DATA / "table11.xls")
    female = female_clause(DATA / "WPP2024_Fertility_by_Age1.csv.gz", deviations)
    male = parse_fathers(DATA / "table11.xls", deviations)
    verdict, reason = combine(female["call"], male["call"])
    if verdict == "supports":
        confidence = 0.55
    elif verdict == "refutes":
        confidence = 0.7
    elif verdict == "mixed":
        confidence = 0.5
    else:
        confidence = 0.3
    primary = female.get("by_year", {}).get("1950", {})
    measured = {
        "value": primary.get("S4044"),
        "unit": "median share of 1950 fertility at maternal ages 40-44, countries with TFR >= 6",
        "n": primary.get("n_tfr_ge_6"),
        "uncertainty": None,
        "extra": {
            "female": female,
            "male": {key: value for key, value in male.items() if key != "countries"},
        },
    }
    summary = [
        f"Female 1950 call {female['call']}: n_TFR>=6 = {primary.get('n_tfr_ge_6')}, "
        f"S40-44={primary.get('S4044')}, S45-49={primary.get('S4549')}, S50+={primary.get('S50')}.",
        f"Female 2023 (not used for the verdict): {female.get('by_year', {}).get('2023')}.",
        f"Male call {male.get('call')}: countries={male.get('n_countries')}, "
        f"births={male.get('pooled_births_known_age')}, share_65+={male.get('share_65_plus')}, "
        f"share_50-64={male.get('share_50_64')}.",
        f"Verdict {verdict}.",
    ]
    (DERIVED / "measured.json").write_text(
        json.dumps({"measured": measured, "summary": summary, "deviations": deviations}, indent=2) + "\n"
    )
    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    result["method"] = (
        "Streamed WPP 2024 single-year age-specific fertility, kept country rows with an ISO3 code "
        "for 1950, converted rates per 1,000 women when the raw maximum exceeded 5, and took the "
        "unweighted median share of fertility at 40-44, 45-49 and 50+ among countries with total "
        "fertility at least 6. Parsed Demographic Yearbook 2024 Table 11 birth counts, pooled the "
        "latest year with at least 10,000 births per country, and applied the registered share rules. "
        "The 2023 female schedule was computed and not used for the verdict."
    )
    result["measured"] = measured
    result["results_summary"] = summary
    if deviations:
        result["deviations"] = deviations
    result["datasets"] = [
        {
            "id": "un-wpp-2024-fertility-by-single-age",
            "name": "World Population Prospects 2024, fertility by single age of mother",
            "landing_url": "https://population.un.org/wpp/",
            "doi": None,
            "version": "2024",
            "license": None,
            "files": [{"name": "WPP2024_Fertility_by_Age1.csv.gz", **wpp}],
            "role": "age-specific fertility of women in 1950 and, descriptively, 2023",
        },
        {
            "id": "un-dyb-2024-table11-births-by-age-of-father",
            "name": "United Nations Demographic Yearbook 2024, Table 11",
            "landing_url": "https://unstats.un.org/unsd/demographic-social/products/dyb/dyb_2024/",
            "doi": None,
            "version": "2024",
            "license": None,
            "files": [{"name": "table11.xls", **dyb}],
            "role": "live births by age of father",
        },
    ]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "confidence": confidence, "reason": reason, "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
