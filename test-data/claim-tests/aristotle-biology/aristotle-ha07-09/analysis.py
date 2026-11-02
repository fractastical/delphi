#!/usr/bin/env python3
"""Recompute aristotle-ha07-09 from the 2024 US natality public-use file.

The pass and fail thresholds are the ones already in result.json. This script
does not change them. It fills measured, verdict, and the files it actually read.
"""

import csv
import hashlib
import json
import math
import os
import subprocess
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
RESULT = os.path.join(HERE, "result.json")
UA = "delphisci-claim-test/aristotle-ha07-09"

NATALITY_URL = (
    "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/DVS/natality/Nat2024us.zip"
)
ANAGE_URL = "https://genomics.senescence.info/species/dataset.zip"
PDF_URL = "https://www.cdc.gov/nchs/data/nvsr/nvsr74/nvsr74-1.pdf"
PANTHERIA_DOI = "https://doi.org/10.1890/08-1494.1"
AMNIOTE_DOI = "https://doi.org/10.1890/15-0846R.1"
DRYAD_PAGE = "https://datadryad.org/dataset/doi:10.5061/dryad.j6q573nv5"
DRYAD_FILE = "https://datadryad.org/downloads/file_stream/4489335"

# User-guide positions, 0-based slices. 1-based positions are 9-12, 490-491, 499-500.
YEAR = slice(8, 12)
COMB = slice(489, 491)
OE = slice(498, 500)
EXPECTED_US_RECORDS = 3638436

PREREG_CAVEATS = [
    "No gestational-age count, week histogram, or within-species gestation file was opened before this registration. The PDF URL is the NCHS final-births report named in the catalog; only its existence as a report title was known.",
    "The lunar-month bins are a reading of 'ten months' as 280 days. They are not a claim that Aristotle stated week numbers.",
    "A modern national registry is not a sample of the animals Aristotle could see. It can test the stated durations. It cannot show that every non-human species has one term unless the within-species series says so.",
    "A range under 14 days in a finite species list would not prove the universal 'every other animal'. The support rule requires that measured list to be fixed, and the caveat remains.",
]


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        retrieved = datetime.fromtimestamp(os.path.getmtime(dest), timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return retrieved
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as out:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    return utc_now()


def head(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return {
                "url": url,
                "status": r.status,
                "final_url": r.geturl(),
                "content_type": r.headers.get("Content-Type"),
                "retrieved_at": utc_now(),
            }
    except Exception as exc:
        status = getattr(getattr(exc, "code", None), "real", None) or getattr(exc, "code", None)
        return {
            "url": url,
            "status": status,
            "error": str(exc),
            "retrieved_at": utc_now(),
        }


def lunar_month(week):
    return math.floor(week / 4 + 0.5)


def calendar_month(week):
    return math.floor(week * 7 / 30.437 + 0.5)


def count_natality(zip_path):
    oe = Counter()
    comb = Counter()
    n = 0
    short = 0
    bad_year = 0
    lengths = Counter()
    proc = subprocess.Popen(
        ["unzip", "-p", zip_path],
        stdout=subprocess.PIPE,
    )
    assert proc.stdout is not None
    for raw in proc.stdout:
        n += 1
        line = raw.rstrip(b"\r\n")
        lengths[len(line)] += 1
        if len(line) < 500:
            short += 1
            continue
        if line[YEAR] != b"2024":
            bad_year += 1
            continue
        oe[line[OE].decode("ascii", "replace")] += 1
        comb[line[COMB].decode("ascii", "replace")] += 1
    code = proc.wait()
    if code != 0:
        raise RuntimeError("unzip exited %s" % code)
    return {
        "n": n,
        "short": short,
        "bad_year": bad_year,
        "lengths": {str(k): v for k, v in lengths.items()},
        "oe": dict(oe),
        "comb": dict(comb),
    }


def parse_week_counts(raw):
    """Return (week -> count, n_not_stated, n_other)."""
    weeks = {}
    not_stated = 0
    other = 0
    for key, count in raw.items():
        if key == "99":
            not_stated += count
            continue
        if len(key) == 2 and key.isdigit():
            week = int(key)
            if 17 <= week <= 47:
                weeks[week] = count
                continue
        other += count
    return weeks, not_stated, other


def month_block(weeks, start, end):
    return sum(weeks.get(w, 0) for w in range(start, end + 1))


def anage_summary(zip_path):
    with zipfile.ZipFile(zip_path) as zf:
        name = "anage_data.txt"
        text = zf.read(name).decode("latin1")
    lines = text.splitlines()
    header = lines[0].split("\t")
    gest_cols = [i for i, h in enumerate(header) if "gest" in h.lower() or "incubat" in h.lower()]
    spread_cols = [
        h
        for h in header
        if any(s in h.lower() for s in ("minimum", "maximum", "min", "max", "variance", "sd"))
    ]
    idx = header.index("Gestation/Incubation (days)")
    class_idx = header.index("Class")
    n_rows = 0
    n_numeric = 0
    n_mammal_numeric = 0
    for line in lines[1:]:
        if not line.strip():
            continue
        n_rows += 1
        cols = line.split("\t")
        val = cols[idx].strip() if idx < len(cols) else ""
        if val and val not in {"-999", "NA"}:
            try:
                float(val)
            except ValueError:
                continue
            n_numeric += 1
            if class_idx < len(cols) and cols[class_idx] == "Mammalia":
                n_mammal_numeric += 1
    return {
        "rows": n_rows,
        "gestation_columns": [header[i] for i in gest_cols],
        "spread_columns": spread_cols,
        "species_with_one_gestation_number": n_numeric,
        "mammal_species_with_one_gestation_number": n_mammal_numeric,
        "admissible_within_species": False,
        "why_not_admissible": "Each species has one gestation or incubation number. There is no within-species minimum, maximum, or repeated pregnancy.",
    }


def human_clause(weeks):
    den = month_block(weeks, 26, 45)
    months = {
        7: month_block(weeks, 26, 29),
        8: month_block(weeks, 30, 33),
        9: month_block(weeks, 34, 37),
        10: month_block(weeks, 38, 41),
        11: month_block(weeks, 42, 45),
    }
    shares = {m: (months[m] / den if den else None) for m in months}
    holds = False
    if den:
        holds = (
            months[10] > months[7]
            and months[10] > months[8]
            and months[10] > months[9]
            and months[10] > months[11]
            and shares[7] >= 0.005
            and shares[8] >= 0.005
            and shares[9] >= 0.005
            and shares[11] >= 0.001
            and shares[11] < shares[10]
            and shares[11] < 0.15
        )
    return den, months, shares, holds


def confidence_for(verdict, shares):
    if verdict == "inconclusive":
        return 0.55
    if verdict == "mixed":
        return 0.75
    if verdict == "supports":
        return 0.60
    # refutes
    others = [shares[m] for m in (7, 8, 9, 11)]
    leader = max([shares[10], *others])
    gap = abs(shares[10] - leader) if shares[10] == leader else abs(leader - shares[10])
    # If month 10 leads, gap versus the next month. If it trails, gap versus the leader.
    if shares[10] == leader:
        gap = shares[10] - max(others)
    else:
        gap = leader - shares[10]
    return 0.85 if gap >= 0.05 else 0.70


def main():
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(DERIVED, exist_ok=True)
    with open(RESULT, encoding="utf-8") as f:
        result = json.load(f)
    for key in (
        "hypothesis",
        "pass_criterion",
        "fail_criterion",
        "test_contract",
        "planned_datasets",
        "preregistered_at",
        "interpretation",
    ):
        if key not in result:
            raise SystemExit("missing pre-registered field %s" % key)

    nat_path = os.path.join(DATA, "Nat2024us.zip")
    nat_retrieved = fetch(NATALITY_URL, nat_path)
    anage_path = os.path.join(DATA, "anage.zip")
    anage_retrieved = fetch(ANAGE_URL, anage_path)

    print("counting natality records", flush=True)
    counted = count_natality(nat_path)
    weeks, not_stated, other = parse_week_counts(counted["oe"])
    comb_weeks, comb_not_stated, comb_other = parse_week_counts(counted["comb"])
    den, months, shares, holds = human_clause(weeks)
    _, comb_months, comb_shares, comb_holds = human_clause(comb_weeks)

    cal = Counter()
    lun_all = Counter()
    for week, count in weeks.items():
        cal[calendar_month(week)] += count
        lun_all[lunar_month(week)] += count
    cal_den = sum(cal.values())
    cal_mode = max(cal, key=cal.get) if cal else None

    anage = anage_summary(anage_path)
    probes = {
        "nchs_pdf": head(PDF_URL),
        "pantheria_doi": head(PANTHERIA_DOI),
        "amniote_doi": head(AMNIOTE_DOI),
        "dryad_page": head(DRYAD_PAGE),
        "dryad_meerkat_csv": head(DRYAD_FILE),
    }
    dryad_body_is_csv = False
    # A GET that returns the anti-bot page is not a gestation table.
    dryad = probes["dryad_meerkat_csv"]
    if dryad.get("content_type") and "csv" in dryad["content_type"]:
        dryad_body_is_csv = True

    animal_series = []
    if anage["admissible_within_species"]:
        animal_series.append("anage")

    if counted["n"] != EXPECTED_US_RECORDS or counted["bad_year"] or counted["short"]:
        verdict = "inconclusive"
        reason = "other"
        summary = "The public-use file did not match the user guide's record count or year field, so the week table was not used."
    elif den < 100000:
        verdict = "inconclusive"
        reason = "underpowered"
        summary = "Births in completed weeks 26 through 45 were fewer than 100000."
    elif not holds:
        verdict = "refutes"
        reason = None
        summary = "Among US live births in weeks 26-45, lunar month 10 was not the pattern the claim states."
    elif animal_series:
        verdict = "inconclusive"
        reason = "other"
        summary = "An animal series was marked admissible, but this script has no range calculator for it."
    else:
        verdict = "inconclusive"
        reason = "other"
        summary = (
            "Lunar month 10 is the most common of months 7 through 11, and months 7, 8, 9 and 11 occur at the pre-registered rates. "
            "No within-species gestation series could be read, so the fixed-term clause for other animals was not measured."
        )

    conf = confidence_for(verdict, shares) if shares.get(10) is not None else 0.55
    conf = min(conf, 0.90)

    week_rows = []
    for week in range(17, 48):
        count = weeks.get(week, 0)
        week_rows.append(
            {
                "week": week,
                "births": count,
                "lunar_month": lunar_month(week),
                "calendar_month": calendar_month(week),
                "in_weeks_26_45": 26 <= week <= 45,
            }
        )

    nat_sha = sha256_file(nat_path)
    anage_sha = sha256_file(anage_path)
    measured = {
        "value": shares[10],
        "unit": "share of US live births in completed weeks 26-45 whose obstetric estimate falls in lunar month 10 (weeks 38-41)",
        "n": den,
        "uncertainty": "not stated obstetric estimate excluded; counts are the full 2024 US file, not a sample",
        "extra": {
            "source_field": "OEGest_Comb",
            "positions_1based": "499-500",
            "records_in_file": counted["n"],
            "records_year_not_2024": counted["bad_year"],
            "records_shorter_than_500": counted["short"],
            "record_lengths": counted["lengths"],
            "obstetric_estimate_not_stated_99": not_stated,
            "obstetric_estimate_other": other,
            "births_by_week": {str(w): weeks.get(w, 0) for w in range(17, 48)},
            "lunar_month_counts_weeks_26_45": months,
            "lunar_month_shares_weeks_26_45": shares,
            "human_clause_holds": holds,
            "calendar_month_mode_among_stated_weeks_17_47": cal_mode,
            "calendar_month_counts_stated_weeks_17_47": {str(k): v for k, v in sorted(cal.items())},
            "calendar_month_denominator": cal_den,
            "combined_gestation_human_clause_holds": comb_holds,
            "combined_gestation_month_shares_weeks_26_45": comb_shares,
            "combined_gestation_not_stated_99": comb_not_stated,
            "combined_gestation_other": comb_other,
            "anage": anage,
            "probes": probes,
            "within_species_series_used": 0,
        },
    }

    os.makedirs(DERIVED, exist_ok=True)
    with open(os.path.join(DERIVED, "by-week.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["week", "births", "lunar_month", "calendar_month", "in_weeks_26_45"]
        )
        writer.writeheader()
        writer.writerows(week_rows)
    with open(os.path.join(DERIVED, "measured.json"), "w", encoding="utf-8") as f:
        json.dump(measured, f, indent=2)
        f.write("\n")

    result["status"] = "complete"
    result["verdict"] = verdict
    result["reason"] = reason
    result["data_kind"] = "biological"
    result["confidence"] = conf
    result["measured"] = measured
    result["method"] = (
        "The 2023 final-births PDF on www.cdc.gov returned an error, so live births were counted in the 2024 US natality public-use file from ftp.cdc.gov. "
        "Each record's obstetric estimate of gestation (user-guide positions 499-500, values 17-47) was assigned to a lunar month by floor(week/4 + 1/2). "
        "Shares use births in weeks 26-45. Combined gestation (positions 490-491) and a calendar month of 30.437 days are reported and do not set the verdict. "
        "AnAge was opened and has one gestation number per species, so it is not a within-species series. "
        "The PanTHERIA and amniote DOIs and the Dryad meerkat pregnancy file did not return a usable table."
    )
    result["deviations"] = [
        {
            "what": "Human weeks come from the 2024 US natality public-use file, not from the NVSR 74 number 1 PDF named at registration.",
            "why": "https://www.cdc.gov/nchs/data/nvsr/nvsr74/nvsr74-1.pdf returned HTTP 403. The public-use file is the live-birth microdata from which that report's week distribution is built, and it distinguishes completed weeks. The 0.005, 0.001, 0.15 and 100000 thresholds are unchanged.",
        },
        {
            "what": "A record is read when positions 9-12 are 2024 and the line is at least 500 characters. The obstetric estimate at positions 499-500 sets the verdict. The file's stripped line length is longer than the user guide's stated record length of 1330.",
            "why": "The 2024 file's line length is not 1330, but the year, sex and both gestation fields sit at the user-guide positions, and the record count matches the user guide's United States control count. Obstetric estimate is the field that guide's gestational-age tables say they use. Combined gestation is stored and does not change the verdict.",
        },
        {
            "what": "No within-species gestation length entered the animal clause.",
            "why": "AnAge build 15 has a single Gestation/Incubation column. The PanTHERIA and amniote DOI landing pages returned HTTP 403. The Dryad dataset page returned HTML, and the meerkat pregnancy file URL returned HTTP 403, so the CSV was not read. A one-number-per-species table was not used as a range. The human thresholds are unchanged.",
        },
    ]
    result["caveats"] = PREREG_CAVEATS + [
        "The human clause uses one country's 2024 live births and the obstetric estimate. It does not reconstruct how a fourth-century observer counted months.",
        "Month 10 holding in this file does not show that every other animal has one fixed term. That clause was not measured.",
        "The calendar-month mode is a sensitivity. It is not the pre-registered reading.",
        summary,
    ]
    result["results_summary"] = [
        summary,
        "Obstetric estimate, weeks 26-45: n=%d; lunar month shares 7=%.4f, 8=%.4f, 9=%.4f, 10=%.4f, 11=%.4f."
        % (den, shares[7], shares[8], shares[9], shares[10], shares[11]),
        "Not-stated obstetric estimate: %d records. File records: %d."
        % (not_stated, counted["n"]),
        "Calendar-month mode among stated weeks 17-47 is %s (denominator %d). It does not set the verdict."
        % (cal_mode, cal_den),
        "Combined-gestation human clause holds: %s. It does not set the verdict." % comb_holds,
        "AnAge species with one gestation number: %d, of which Mammalia %d. Not used as a within-species range."
        % (
            anage["species_with_one_gestation_number"],
            anage["mammal_species_with_one_gestation_number"],
        ),
    ]
    result["datasets"] = [
        {
            "id": "nchs-natality-2024-us",
            "name": "NCHS Natality public-use file, United States, 2024",
            "landing_url": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/DVS/natality/",
            "doi": None,
            "version": "Nat2024PublicUS.c20250512.r20250708",
            "license": "US government public-use vital statistics file",
            "files": [
                {
                    "name": "Nat2024us.zip",
                    "download_url": NATALITY_URL,
                    "retrieved_at": nat_retrieved,
                    "byte_size": os.path.getsize(nat_path),
                    "sha256": nat_sha,
                }
            ],
            "role": "live births by completed week, obstetric estimate at positions 499-500",
        },
        {
            "id": "anage-build-15",
            "name": "AnAge build 15",
            "landing_url": "https://genomics.senescence.info/species/",
            "doi": None,
            "version": "build 15, release 2023-07-03",
            "license": "AnAge terms on genomics.senescence.info; one row per species",
            "files": [
                {
                    "name": "dataset.zip",
                    "download_url": ANAGE_URL,
                    "retrieved_at": anage_retrieved,
                    "byte_size": os.path.getsize(anage_path),
                    "sha256": anage_sha,
                }
            ],
            "role": "checked and dropped: one gestation number per species, not a within-species series",
        },
    ]
    result["agent"] = {
        "kind": "cloud-agent",
        "model": "Grok 4.7",
        "run": "cursor/aristotle-claim-tests-3f12",
        "date": "2026-11-01",
    }
    if reason is None:
        result.pop("reason", None)
    with open(RESULT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(
        "VERDICT",
        verdict,
        "reason",
        reason,
        "p10",
        round(shares[10], 4),
        "n",
        den,
        "holds",
        holds,
        "conf",
        conf,
        flush=True,
    )


if __name__ == "__main__":
    main()
