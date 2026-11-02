#!/usr/bin/env python3
"""aristotle-ha05-27: elephant gestation of two years, and one young at a time.

Pre-registered window: gestation in (547.875, 913.125) days, nearer to
730.5 days than to 365.25 or 1095.75. Litter size in [1.0, 1.05] passes;
(1.05, 1.5) is the intermediate band; >= 1.5 refutes. A value below 1.0
was not given a band. It is not a pass and it is not a >= 1.5 refutation,
so it blocks a support.

Run: python3 analysis.py
Standard library only. Downloads stay in data/ and are not committed.
"""

import datetime as dt
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test/1.0"}

ANAGE_URL = "https://genomics.senescence.info/species/dataset.zip"
PANTHERIA_URL = "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt"

LOW = 547.875
HIGH = 913.125
REQUIRED = ("Elephas maximus", "Loxodonta africana")
GENERA = ("Elephas", "Loxodonta")


def fetch(url, name):
    DATA.mkdir(exist_ok=True)
    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
        final = resp.geturl()
    path = DATA / name
    path.write_bytes(raw)
    return {
        "download_url": url,
        "final_url": final,
        "retrieved_at": retrieved,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "raw": raw,
    }


def number(cell):
    cell = (cell or "").strip()
    if cell == "" or cell.lower() in {"na", "nan", "-"}:
        return None
    try:
        value = float(cell)
    except ValueError:
        return None
    if value < 0:
        return None
    return value


def litter_band(value):
    if value is None:
        return "missing"
    if 1.0 <= value <= 1.05:
        return "pass"
    if 1.05 < value < 1.5:
        return "intermediate"
    if value >= 1.5:
        return "refute"
    return "below"


def gestation_band(value):
    if value is None:
        return "missing"
    if LOW < value < HIGH:
        return "inside"
    return "outside"


def anage_rows(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        text = archive.read("anage_data.txt").decode("utf-8")
        release = archive.read("release.html").decode("utf-8", "replace")
    lines = text.splitlines()
    header = lines[0].split("\t")
    index = {name: i for i, name in enumerate(header)}
    rows = []
    for line in lines[1:]:
        cells = line.split("\t")
        if len(cells) <= index["Genus"]:
            continue
        genus = cells[index["Genus"]]
        if genus not in GENERA:
            continue
        species = f"{genus} {cells[index['Species']]}"
        rows.append({
            "database": "anage",
            "species": species,
            "gestation_days": number(cells[index["Gestation/Incubation (days)"]]),
            "litter_size": number(cells[index["Litter/Clutch size"]]),
        })
    build = "build 15" if "Build 15" in release else "unknown build"
    return rows, build


def pantheria_rows(raw):
    text = raw.decode("latin-1")
    lines = text.splitlines()
    header = lines[0].split("\t")
    index = {name: i for i, name in enumerate(header)}
    rows = []
    for line in lines[1:]:
        cells = line.split("\t")
        if len(cells) <= index["MSW05_Binomial"]:
            continue
        genus = cells[index["MSW05_Genus"]]
        if genus not in GENERA:
            continue
        rows.append({
            "database": "pantheria",
            "species": cells[index["MSW05_Binomial"]],
            "gestation_days": number(cells[index["9-1_GestationLen_d"]]),
            "litter_size": number(cells[index["15-1_LitterSize"]]),
        })
    return rows


def clause(rows):
    """Return gestation_clause, litter_clause, coverage notes."""
    present = {}
    for row in rows:
        if row["gestation_days"] is None and row["litter_size"] is None:
            continue
        present.setdefault(row["species"], []).append(row)

    gest_bands = []
    litter_bands = []
    per_species = {}
    for species, items in sorted(present.items()):
        g = [gestation_band(r["gestation_days"]) for r in items if r["gestation_days"] is not None]
        lit = [litter_band(r["litter_size"]) for r in items if r["litter_size"] is not None]
        # databases disagree when both an inside and an outside are present
        if "inside" in g and "outside" in g:
            g_clause = "mixed"
        elif g and all(x == "outside" for x in g):
            g_clause = "refutes"
        elif g and all(x == "inside" for x in g):
            g_clause = "supports"
        else:
            g_clause = "missing"
        if "refute" in lit:
            l_clause = "refutes"
        elif lit and all(x == "pass" for x in lit):
            l_clause = "supports"
        elif lit:
            l_clause = "mixed"
        else:
            l_clause = "missing"
        per_species[species] = {"gestation": g_clause, "litter": l_clause, "rows": items}
        gest_bands.append(g_clause)
        litter_bands.append(l_clause)

    def combine(parts, kind):
        if not parts or all(p == "missing" for p in parts):
            return "missing"
        if "refutes" in parts:
            return "refutes"
        if "mixed" in parts:
            return "mixed"
        if all(p == "supports" for p in parts):
            return "supports"
        return "mixed"

    return combine(gest_bands, "gestation"), combine(litter_bands, "litter"), per_species


def overall(gestation, litter, per_species):
    have = set(per_species)
    both = all(s in have for s in REQUIRED)
    if gestation == "missing":
        return "inconclusive", "data-unavailable"
    if gestation == "refutes" or litter == "refutes":
        return "refutes", None
    if gestation == "supports" and litter == "missing":
        return "inconclusive", "data-unavailable"
    if gestation == "supports" and litter == "supports" and both:
        # every required species must itself support both clauses
        for species in REQUIRED:
            info = per_species[species]
            if info["gestation"] != "supports" or info["litter"] != "supports":
                return "mixed", None
        return "supports", None
    if not both and gestation == "supports" and litter == "supports":
        return "inconclusive", "underpowered"
    if gestation == "mixed" or litter == "mixed":
        return "mixed", None
    return "inconclusive", "other"


def main():
    anage = fetch(ANAGE_URL, "anage-dataset.zip")
    pantheria = fetch(PANTHERIA_URL, "PanTHERIA_1-0_WR05_Aug2008.txt")
    anage_table, build = anage_rows(anage["raw"])
    pan_table = pantheria_rows(pantheria["raw"])
    rows = anage_table + pan_table
    scored = [r for r in rows if r["gestation_days"] is not None or r["litter_size"] is not None]
    gestation, litter, per_species = clause(scored)
    verdict, reason = overall(gestation, litter, per_species)

    gestations = [r["gestation_days"] for r in scored if r["gestation_days"] is not None]
    litters = [r["litter_size"] for r in scored if r["litter_size"] is not None]
    if verdict == "supports" and len(set(g and True for g in gestations)) and gestation == "supports":
        confidence = 0.85
    elif verdict == "mixed" and gestation == "supports":
        confidence = 0.74
    elif verdict == "refutes":
        confidence = 0.8
    else:
        confidence = 0.4

    measured = {
        "value": max(litters) if litters else None,
        "unit": "maximum recorded litter size among elephant rows with a value",
        "n": len(scored),
        "uncertainty": (
            f"gestation clause {gestation}; litter clause {litter}; "
            f"gestation days {gestations}"
        ),
        "extra": {
            "gestation_clause": gestation,
            "litter_clause": litter,
            "window_days": [LOW, HIGH],
            "rows": [
                {
                    **r,
                    "gestation_band": gestation_band(r["gestation_days"]),
                    "litter_band": litter_band(r["litter_size"]),
                    "gestation_years": None if r["gestation_days"] is None else round(r["gestation_days"] / 365.25, 4),
                }
                for r in rows
            ],
        },
    }

    def file_record(fetched, label):
        return {
            "name": label,
            "download_url": fetched["download_url"],
            "final_url": fetched["final_url"],
            "retrieved_at": fetched["retrieved_at"],
            "byte_size": fetched["byte_size"],
            "sha256": fetched["sha256"],
        }

    datasets = [
        {
            "id": "anage-dataset-zip",
            "name": f"AnAge life-history table ({build})",
            "landing_url": "https://genomics.senescence.info/species/",
            "doi": "10.1093/nar/gkx1042",
            "version": build,
            "license": "CC BY 3.0",
            "files": [file_record(anage, "dataset.zip")],
            "role": "gestation length and litter size for Elephas and Loxodonta",
        },
        {
            "id": "pantheria-1-0-wr05-aug2008",
            "name": "PanTHERIA 1.0 WR05 August 2008",
            "landing_url": "https://esapubs.org/archive/ecol/E090/184/",
            "doi": "10.1890/08-1494.1",
            "version": "1.0 (WR05, Aug 2008)",
            "license": "Ecological Archives; copyright restrictions stated as none",
            "files": [file_record(pantheria, "PanTHERIA_1-0_WR05_Aug2008.txt")],
            "role": "independent gestation length and litter size for the same elephants",
        },
    ]

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = confidence
    result["datasets"] = datasets
    result["measured"] = measured
    result["deviations"] = [
        {
            "what": "A litter size below 1.0 had no named band in the pre-registration.",
            "why": "The pass interval is [1.0, 1.05] and the refute threshold is >= 1.5. A value below 1 fails the pass interval and does not meet the refute threshold, so it is scored with the intermediate band as mixed. The thresholds themselves were not changed.",
        }
    ]
    result["method"] = (
        "Downloaded the AnAge build zip and the PanTHERIA WR05 table. Kept rows whose genus is "
        "Elephas or Loxodonta, read gestation in days and litter size, treated negative sentinels "
        "as missing, and applied the pre-registered day window and litter bands. "
        f"Gestation clause: {gestation}. Litter clause: {litter}."
    )
    result["results_summary"] = [
        f"Scored rows: {len(scored)}. Gestation days: {gestations}.",
        f"Litter sizes: {litters}. Maximum litter size {measured['value']}.",
        f"Gestation clause {gestation}; litter clause {litter}; verdict {verdict}.",
    ]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({
        "verdict": verdict,
        "reason": reason,
        "gestation_clause": gestation,
        "litter_clause": litter,
        "rows": measured["extra"]["rows"],
    }, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "gestation": gestation, "litter": litter,
                      "rows": measured["extra"]["rows"]}, indent=2))


if __name__ == "__main__":
    main()
