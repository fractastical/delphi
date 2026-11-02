#!/usr/bin/env python3
"""Test aristotle-ha08-28 against the USGS grizzly parturition table."""

import csv
import hashlib
import io
import json
import ssl
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

CATALOG = "https://www.sciencebase.gov/catalog/item/68716b6ed4be026e1750f346?format=json"
HERE = Path(__file__).resolve().parent


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "DelphiClaimTest/1.0"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        data = resp.read()
        retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        final = resp.geturl()
    return data, retrieved, final


def parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def preceding_solstice(day):
    if (day.month, day.day) > (12, 21):
        year = day.year
    else:
        year = day.year - 1
    return datetime(year, 12, 21).date()


def interval_contains_solstice(entry, exit_):
    year = entry.year - 1
    while year <= exit_.year:
        sol = datetime(year, 12, 21).date()
        if entry <= sol <= exit_:
            return True
        year += 1
    return False


def month_from_doy(doy):
    # Non-leap calendar, used only to name the median day-of-year.
    base = datetime(2015, 1, 1).date()
    return (base + timedelta(days=int(round(doy)) - 1)).month


def main():
    catalog_raw, catalog_at, _ = fetch(CATALOG)
    catalog = json.loads(catalog_raw.decode("utf-8"))
    files = catalog.get("files") or []
    chosen = next(f for f in files if f.get("name") == "Grizzly_bear_parturition_data.csv")
    download_url = chosen.get("downloadUri") or chosen.get("url")
    data, retrieved, final_url = fetch(download_url)
    text = data.decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))

    birth_flags = []
    solstice_flags = []
    offsets = []
    doys = []
    by_pop = {}
    feeding_fields = [
        name
        for name in (rows[0].keys() if rows else [])
        if name and any(k in name.lower() for k in ("feed", "fast", "forag", "eat"))
    ]

    for row in rows:
        entry = parse_date(row.get("EntryDate"))
        birth = parse_date(row.get("BirthDate"))
        exit_ = parse_date(row.get("ExitDate"))
        pop = (row.get("Population") or "").strip() or "unknown"
        bucket = by_pop.setdefault(pop, {"birth": [], "solstice": [], "offset": [], "doy": []})
        if entry and exit_ and entry < exit_:
            sol = interval_contains_solstice(entry, exit_)
            solstice_flags.append(sol)
            bucket["solstice"].append(sol)
            target = preceding_solstice(exit_) + timedelta(days=91)
            offset = (exit_ - target).days
            offsets.append(offset)
            doy = exit_.timetuple().tm_yday
            doys.append(doy)
            bucket["offset"].append(offset)
            bucket["doy"].append(doy)
        if entry and birth and exit_ and entry < exit_:
            inside = entry < birth < exit_
            birth_flags.append(inside)
            bucket["birth"].append(inside)

    def proportion(flags):
        if not flags:
            return None
        return sum(1 for f in flags if f) / len(flags)

    birth_p = proportion(birth_flags)
    sol_p = proportion(solstice_flags)
    med_offset = median(offsets) if offsets else None
    med_doy = median(doys) if doys else None
    med_month = month_from_doy(med_doy) if med_doy is not None else None
    spring = med_month in (3, 4, 5) if med_month is not None else False
    within_30 = med_offset is not None and abs(med_offset) <= 30

    n_birth = len(birth_flags)
    n_den = len(solstice_flags)
    underpowered = n_birth < 20 or n_den < 20
    if underpowered:
        verdict, reason = "inconclusive", "underpowered"
    elif birth_p < 0.50 or sol_p < 0.50:
        verdict, reason = "refutes", None
    elif birth_p >= 0.90 and sol_p >= 0.90 and spring and within_30:
        verdict, reason = "supports", None
    else:
        verdict, reason = "mixed", None

    populations = {}
    for pop, bucket in sorted(by_pop.items()):
        populations[pop] = {
            "n_birth": len(bucket["birth"]),
            "birth_inside_den": proportion(bucket["birth"]),
            "n_den": len(bucket["solstice"]),
            "solstice_inside_den": proportion(bucket["solstice"]),
            "median_emergence_offset_days": median(bucket["offset"]) if bucket["offset"] else None,
            "median_exit_doy": median(bucket["doy"]) if bucket["doy"] else None,
        }

    measured = {
        "value": birth_p,
        "unit": "proportion of births inside the den interval",
        "n": n_birth,
        "uncertainty": None,
        "extra": {
            "birth_inside_den": birth_p,
            "n_birth": n_birth,
            "solstice_inside_den": sol_p,
            "n_den_intervals": n_den,
            "median_emergence_offset_days": med_offset,
            "median_exit_day_of_year": med_doy,
            "median_exit_month": med_month,
            "spring_median": spring,
            "within_30_days_of_solstice_plus_91": within_30,
            "fasting_fields": feeding_fields,
            "fasting": "untested",
            "populations": populations,
            "verdict_from_criteria": verdict,
            "reason": reason,
        },
    }
    out = {
        "catalog_retrieved_at": catalog_at,
        "retrieved_at": retrieved,
        "download_url": final_url,
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "n_rows": len(rows),
        "measured": measured,
    }
    derived = HERE / "derived"
    derived.mkdir(exist_ok=True)
    (derived / "measured.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
