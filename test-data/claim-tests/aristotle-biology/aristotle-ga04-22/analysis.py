#!/usr/bin/env python3
"""Human prenatal size, puberty and old age by sex."""
import csv
import hashlib
import io
import json
import re
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
UA = "delphi-claim-test/1.0 (research; aristotle-biology)"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
BOYS = "https://cdn.who.int/media/docs/default-source/child-growth/child-growth-standards/indicators/weight-for-age/wfa_boys_0-to-13-weeks_zscores.xlsx?sfvrsn=6e3a980f_7"
GIRLS = "https://cdn.who.int/media/docs/default-source/child-growth/child-growth-standards/indicators/weight-for-age/wfa_girls_0-to-13-weeks_zscores.xlsx?sfvrsn=c4f4ba9f_7"
ANAGE_URL = "https://genomics.senescence.info/species/dataset.zip"
YEARS = ("2022", "2021", "2020", "2019")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return {
        "download_url": url,
        "retrieved_at": now(),
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def col_index(letters):
    number = 0
    for char in letters:
        number = number * 26 + (ord(char) - 64)
    return number - 1


def xlsx_rows(path):
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", NS):
                shared.append("".join(node.text or "" for node in item.findall(".//m:t", NS)))
        sheet = "xl/worksheets/sheet1.xml"
        root = ET.fromstring(archive.read(sheet))
    rows = []
    for row in root.findall("m:sheetData/m:row", NS):
        cells = {}
        for cell in row.findall("m:c", NS):
            ref = cell.get("r") or "A1"
            match = re.match(r"[A-Z]+", ref)
            if not match:
                continue
            index = col_index(match.group(0))
            kind = cell.get("t")
            value = cell.find("m:v", NS)
            inline = cell.find("m:is", NS)
            if kind == "s" and value is not None and value.text:
                text = shared[int(value.text)]
            elif kind == "inlineStr" and inline is not None:
                text = "".join(node.text or "" for node in inline.findall(".//m:t", NS))
            elif value is not None and value.text is not None:
                text = value.text
            else:
                text = ""
            cells[index] = text
        if not cells:
            rows.append([])
            continue
        width = max(cells) + 1
        rows.append([cells.get(i, "") for i in range(width)])
    return rows


def week0_median(rows):
    header_i = None
    for i, row in enumerate(rows[:25]):
        lowered = [str(cell).strip().lower() for cell in row]
        if any(cell == "week" or cell.startswith("week") or cell == "age" for cell in lowered):
            header_i = i
            break
    if header_i is None:
        raise RuntimeError(f"no week header in first rows: {rows[:8]}")
    header = [str(cell).strip().lower() for cell in rows[header_i]]
    mcol = None
    for prefer in ("m", "median"):
        if prefer in header:
            mcol = header.index(prefer)
            break
    if mcol is None:
        raise RuntimeError(f"no median column in {header}")
    weekcol = 0
    for i, cell in enumerate(header):
        if cell == "week" or cell.startswith("week") or cell == "age":
            weekcol = i
            break
    for row in rows[header_i + 1 :]:
        if weekcol >= len(row) or mcol >= len(row):
            continue
        try:
            week = float(str(row[weekcol]).strip())
            median = float(str(row[mcol]).strip())
        except ValueError:
            continue
        if week == 0:
            return median, header[mcol]
    raise RuntimeError("no week 0 row")


def anage_maturity(path):
    with zipfile.ZipFile(path) as archive:
        name = next(item for item in archive.namelist() if item.lower().endswith(".txt"))
        text = archive.read(name).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    headers = reader.fieldnames or []

    def find(*needles):
        for header in headers:
            lowered = header.lower()
            if all(needle in lowered for needle in needles):
                return header
        return None

    c_genus, c_species = find("genus"), find("species")
    c_female, c_male = find("female", "maturity"), find("male", "maturity")
    if not all([c_genus, c_species, c_female, c_male]):
        raise RuntimeError(f"AnAge maturity columns missing: {headers}")
    for record in reader:
        if (record.get(c_genus) or "").strip().lower() == "homo" and (
            record.get(c_species) or ""
        ).strip().lower() == "sapiens":
            def num(key):
                text = (record.get(key) or "").strip()
                if text == "" or text.lower() in {"na", "nan"}:
                    return None
                return float(text)
            return num(c_female), num(c_male), name
    return None, None, name


def world_bank(indicator, year):
    url = (
        "https://api.worldbank.org/v2/country/all/indicator/"
        f"{indicator}?date={year}&format=json&per_page=20000"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    payload = json.loads(data.decode("utf-8"))
    rows = payload[1] or []
    out = {}
    for row in rows:
        iso = (row.get("countryiso3code") or "").strip()
        if len(iso) != 3 or row.get("value") is None:
            continue
        out[iso] = float(row["value"])
    return out, {
        "download_url": url.split("?")[0] + f"?date={year}&format=json&per_page=20000",
        "retrieved_at": now(),
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "name": f"{indicator}-{year}.json",
    }


def clause_size(female, male):
    if female < male:
        return "supports"
    return "refutes"


def clause_puberty(female, male):
    if female is None or male is None:
        return "untested"
    if female < male:
        return "supports"
    if female > male:
        return "refutes"
    return "mixed"


def clause_old(n_female_shorter, n):
    if n < 100:
        return "untested"
    shorter = n_female_shorter / n
    longer = 1 - shorter  # ties are not in shorter; caller passes only strict counts separately
    return shorter, longer


def overall(parts):
    scored = [part for part in parts if part in {"supports", "refutes", "mixed"}]
    if len(scored) < 2:
        return "inconclusive", "data-unavailable"
    if any(part == "mixed" for part in scored):
        return "mixed", None
    if all(part == "supports" for part in scored) and len(scored) == 3:
        return "supports", None
    if all(part == "refutes" for part in scored) and len(scored) == 3:
        return "refutes", None
    if "supports" in scored and "refutes" in scored:
        return "mixed", None
    # two of three, both the same direction, one untested
    if len(scored) == 2 and len(set(scored)) == 1:
        return "mixed", None
    return "mixed", None


def self_test():
    assert clause_size(3.2, 3.3) == "supports"
    assert clause_size(3.4, 3.3) == "refutes"
    assert clause_puberty(4700, 5100) == "supports"
    assert clause_puberty(5100, 4700) == "refutes"
    assert overall(["supports", "supports", "refutes"])[0] == "mixed"
    assert overall(["supports", "supports", "supports"])[0] == "supports"
    assert overall(["refutes", "refutes", "refutes"])[0] == "refutes"
    assert overall(["supports", "untested", "untested"])[0] == "inconclusive"
    print("self-test ok")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    result = json.loads((ROOT / "result.json").read_text())
    boys_meta = fetch(BOYS, CACHE / "wfa_boys.xlsx")
    girls_meta = fetch(GIRLS, CACHE / "wfa_girls.xlsx")
    anage_meta = fetch(ANAGE_URL, CACHE / "anage.zip")
    boy_median, boy_col = week0_median(xlsx_rows(CACHE / "wfa_boys.xlsx"))
    girl_median, girl_col = week0_median(xlsx_rows(CACHE / "wfa_girls.xlsx"))
    female_days, male_days, anage_inner = anage_maturity(CACHE / "anage.zip")
    size = clause_size(girl_median, boy_median)
    puberty = clause_puberty(female_days, male_days)
    chosen = None
    female_le = male_le = None
    file_meta = []
    for year in YEARS:
        female_le, female_file = world_bank("SP.DYN.LE00.FE.IN", year)
        male_le, male_file = world_bank("SP.DYN.LE00.MA.IN", year)
        file_meta.extend([female_file, male_file])
        both = sorted(set(female_le) & set(male_le))
        if len(both) >= 100:
            chosen = year
            break
    old = "untested"
    n_countries = 0
    n_shorter = n_longer = n_tie = 0
    median_gap = None
    if chosen:
        both = sorted(set(female_le) & set(male_le))
        gaps = []
        for iso in both:
            gap = female_le[iso] - male_le[iso]
            gaps.append(gap)
            if gap < 0:
                n_shorter += 1
            elif gap > 0:
                n_longer += 1
            else:
                n_tie += 1
        n_countries = len(both)
        gaps.sort()
        median_gap = gaps[len(gaps) // 2]
        share_shorter = n_shorter / n_countries
        share_longer = n_longer / n_countries
        if share_shorter >= 0.90:
            old = "supports"
        elif share_longer >= 0.90:
            old = "refutes"
        else:
            old = "mixed"
    verdict, reason = overall([size, puberty, old])
    measured = {
        "value": None if median_gap is None else round(median_gap, 3),
        "unit": "median female minus male life expectancy at birth, years",
        "n": n_countries,
        "uncertainty": "World Bank point estimates; median of country gaps",
        "extra": {
            "size_clause": size,
            "girl_birth_median_kg": girl_median,
            "boy_birth_median_kg": boy_median,
            "median_column": {"girls": girl_col, "boys": boy_col},
            "puberty_clause": puberty,
            "female_maturity_days": female_days,
            "male_maturity_days": male_days,
            "old_age_clause": old,
            "year": chosen,
            "countries_female_le_shorter": n_shorter,
            "countries_female_le_longer": n_longer,
            "countries_tie": n_tie,
        },
    }
    data_kind = "none" if verdict == "inconclusive" else "biological"
    result.update(
        {
            "status": "complete",
            "verdict": verdict,
            "confidence": 0.8 if verdict == "mixed" else 0.7,
            "data_kind": data_kind,
            "method": (
                "Read WHO weight-for-age week-0 LMS medians for girls and boys, AnAge female and male "
                "maturity for Homo sapiens, and World Bank male and female life expectancy at birth for the "
                "first of 2022–2019 with at least 100 countries. The conjunction is supported only if all three "
                "clauses support and refuted only if all three refute. Prime of life and gestational duration "
                "were not scored."
            ),
            "datasets": [
                {
                    "id": "who-wfa-0-13-weeks",
                    "name": "WHO Child Growth Standards weight-for-age, birth to 13 weeks",
                    "landing_url": "https://www.who.int/tools/child-growth-standards/standards/weight-for-age",
                    "doi": None,
                    "version": "z-score tables",
                    "license": None,
                    "files": [
                        {**boys_meta, "name": "wfa_boys_0-to-13-weeks_zscores.xlsx"},
                        {**girls_meta, "name": "wfa_girls_0-to-13-weeks_zscores.xlsx"},
                    ],
                    "role": "sex-specific median weight at week 0",
                },
                {
                    "id": "anage-hagr",
                    "name": "AnAge Homo sapiens maturity ages",
                    "landing_url": "https://genomics.senescence.info/species/index.html",
                    "doi": None,
                    "version": anage_inner,
                    "license": "CC BY 3.0",
                    "files": [{**anage_meta, "name": "dataset.zip"}],
                    "role": "female and male maturity in days",
                },
                {
                    "id": "worldbank-life-expectancy-sex",
                    "name": "World Bank life expectancy at birth by sex",
                    "landing_url": "https://data.worldbank.org/indicator/SP.DYN.LE00.FE.IN",
                    "doi": None,
                    "version": chosen,
                    "license": None,
                    "files": file_meta,
                    "role": "female and male period life expectancy at birth",
                },
            ],
            "measured": measured,
            "results_summary": [
                f"size {size}; puberty {puberty}; old age {old}; year {chosen}; countries {n_countries}."
            ],
        }
    )
    if reason:
        result["reason"] = reason
    (ROOT / "derived").mkdir(exist_ok=True)
    (ROOT / "derived" / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, measured["extra"])


if __name__ == "__main__":
    main()
