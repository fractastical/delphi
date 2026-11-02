#!/usr/bin/env python3
"""aristotle-ha05-26: dromedary gestation of twelve months, and one young.

Pass band for gestation: (334.813, 395.687) days, one month of 30.437 days
either side of 365.25. Mixed if one to two months off. Refute at or beyond
304.37 or 426.118 days. Litter: [1, 1.05] pass, (1.05, 1.5) or below 1 mixed,
>= 1.5 refute. Camelus bactrianus is printed and does not vote.

Run: python3 analysis.py
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
VOTE = "Camelus dromedarius"
PASS_LOW, PASS_HIGH = 334.813, 395.687
REFUTE_LOW, REFUTE_HIGH = 304.37, 426.118


def fetch(url, name):
    DATA.mkdir(exist_ok=True)
    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
        final = resp.geturl()
    (DATA / name).write_bytes(raw)
    return {"download_url": url, "final_url": final, "retrieved_at": retrieved,
            "byte_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "raw": raw}


def number(cell):
    cell = (cell or "").strip()
    if cell == "":
        return None
    try:
        value = float(cell)
    except ValueError:
        return None
    if value < 0:
        return None
    return value


def gestation_band(value):
    if value is None:
        return "missing"
    if PASS_LOW < value < PASS_HIGH:
        return "pass"
    if value <= REFUTE_LOW or value >= REFUTE_HIGH:
        return "refute"
    return "mixed"


def litter_band(value):
    if value is None:
        return "missing"
    if 1.0 <= value <= 1.05:
        return "pass"
    if value >= 1.5:
        return "refute"
    return "mixed"


def anage_rows(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        lines = archive.read("anage_data.txt").decode("utf-8").splitlines()
        release = archive.read("release.html").decode("utf-8", "replace")
    header = lines[0].split("\t")
    index = {name: i for i, name in enumerate(header)}
    rows = []
    for line in lines[1:]:
        cells = line.split("\t")
        if len(cells) <= index["Species"]:
            continue
        if cells[index["Genus"]] != "Camelus":
            continue
        rows.append({
            "database": "anage",
            "species": f"{cells[index['Genus']]} {cells[index['Species']]}",
            "gestation_days": number(cells[index["Gestation/Incubation (days)"]]),
            "litter_size": number(cells[index["Litter/Clutch size"]]),
        })
    build = "build 15" if "Build 15" in release else "unknown build"
    return rows, build


def pantheria_rows(raw):
    lines = raw.decode("latin-1").splitlines()
    header = lines[0].split("\t")
    index = {name: i for i, name in enumerate(header)}
    rows = []
    for line in lines[1:]:
        cells = line.split("\t")
        if len(cells) <= index["MSW05_Binomial"]:
            continue
        if cells[index["MSW05_Genus"]] != "Camelus":
            continue
        rows.append({
            "database": "pantheria",
            "species": cells[index["MSW05_Binomial"]],
            "gestation_days": number(cells[index["9-1_GestationLen_d"]]),
            "litter_size": number(cells[index["15-1_LitterSize"]]),
        })
    return rows


def combine(bands):
    bands = [b for b in bands if b != "missing"]
    if not bands:
        return "missing"
    if "refute" in bands and "pass" in bands:
        return "mixed"
    if "refute" in bands:
        return "refutes"
    if "mixed" in bands:
        return "mixed"
    if all(b == "pass" for b in bands):
        return "supports"
    return "mixed"


def main():
    anage = fetch(ANAGE_URL, "anage-dataset.zip")
    pantheria = fetch(PANTHERIA_URL, "PanTHERIA_1-0_WR05_Aug2008.txt")
    anage_table, build = anage_rows(anage["raw"])
    rows = anage_table + pantheria_rows(pantheria["raw"])
    for row in rows:
        row["gestation_band"] = gestation_band(row["gestation_days"])
        row["litter_band"] = litter_band(row["litter_size"])
        row["gestation_months"] = None if row["gestation_days"] is None else round(row["gestation_days"] / 30.437, 3)
        row["votes"] = row["species"] == VOTE

    voting = [r for r in rows if r["votes"]]
    g_clause = combine([r["gestation_band"] for r in voting])
    l_clause = combine([r["litter_band"] for r in voting])
    if g_clause == "missing":
        verdict, reason = "inconclusive", "data-unavailable"
    elif g_clause == "refutes" or l_clause == "refutes":
        verdict, reason = "refutes", None
    elif g_clause == "supports" and l_clause == "missing":
        verdict, reason = "inconclusive", "data-unavailable"
    elif g_clause == "supports" and l_clause == "supports":
        verdict, reason = "supports", None
    elif g_clause == "mixed" or l_clause == "mixed":
        verdict, reason = "mixed", None
    else:
        verdict, reason = "inconclusive", "other"

    if verdict == "supports":
        confidence = 0.8
    elif verdict == "mixed":
        confidence = 0.64
    elif verdict == "refutes":
        confidence = 0.8
    else:
        confidence = 0.55

    gestations = [r["gestation_days"] for r in voting if r["gestation_days"] is not None]
    litters = [r["litter_size"] for r in voting if r["litter_size"] is not None]
    measured = {
        "value": gestations[0] if len(gestations) == 1 else (round(sum(gestations) / len(gestations), 2) if gestations else None),
        "unit": "days, mean of reported Camelus dromedarius gestation values",
        "n": len([r for r in voting if r["gestation_days"] is not None or r["litter_size"] is not None]),
        "uncertainty": f"gestation clause {g_clause}; litter clause {l_clause}; days {gestations}; litter {litters}",
        "extra": {"rows": rows, "gestation_clause": g_clause, "litter_clause": l_clause},
    }

    def file_record(got, label):
        return {"name": label, "download_url": got["download_url"], "final_url": got["final_url"],
                "retrieved_at": got["retrieved_at"], "byte_size": got["byte_size"], "sha256": got["sha256"]}

    datasets = [
        {"id": "anage-dataset-zip", "name": f"AnAge life-history table ({build})",
         "landing_url": "https://genomics.senescence.info/species/", "doi": "10.1093/nar/gkx1042",
         "version": build, "license": "CC BY 3.0", "files": [file_record(anage, "dataset.zip")],
         "role": "gestation and litter size for Camelus dromedarius"},
        {"id": "pantheria-1-0-wr05-aug2008", "name": "PanTHERIA 1.0 WR05 August 2008",
         "landing_url": "https://esapubs.org/archive/ecol/E090/184/", "doi": "10.1890/08-1494.1",
         "version": "1.0 (WR05, Aug 2008)",
         "license": "Ecological Archives; copyright restrictions stated as none",
         "files": [file_record(pantheria, "PanTHERIA_1-0_WR05_Aug2008.txt")],
         "role": "independent gestation and litter size for Camelus dromedarius"},
    ]
    result = json.loads((HERE / "result.json").read_text())
    result.update({
        "status": "complete",
        "data_kind": "none" if reason == "data-unavailable" else "biological",
        "verdict": verdict,
        "confidence": confidence,
        "datasets": datasets,
        "measured": measured,
        "deviations": [],
        "method": (
            "Downloaded AnAge and PanTHERIA, kept genus Camelus, and scored only Camelus dromedarius. "
            f"Gestation clause {g_clause}. Litter clause {l_clause}. "
            "Camelus bactrianus is listed in measured.extra and does not vote."
        ),
        "results_summary": [
            f"Dromedary gestation days: {gestations}. Litter sizes: {litters}.",
            f"Gestation clause {g_clause}; litter clause {l_clause}; verdict {verdict}.",
        ],
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({
        "verdict": verdict, "reason": reason, "rows": rows,
    }, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
