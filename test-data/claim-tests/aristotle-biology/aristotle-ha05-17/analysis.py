#!/usr/bin/env python3
"""aristotle-ha05-17: size order of four Greek pigeons in AVONET species means.

Re-run: python3 analysis.py
Downloads the AVONET ELEData zip into ./data (gitignored; the zip is about 18 MB).
"""
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
URL = "https://ndownloader.figshare.com/files/38429873"
CSV_IN_ZIP = "ELEData/TraitData/AVONET1_BirdLife.csv"
ORDER = ["Columba palumbus", "Columba oenas", "Columba livia", "Streptopelia turtur"]
UA = {"User-Agent": "delphi-claim-tests/1.0 (aristotle-ha05-17)"}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch():
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / "ELEData.zip"
    meta_path = dest.with_suffix(".zip.meta.json")
    if dest.exists() and dest.stat().st_size > 0 and meta_path.exists():
        return json.loads(meta_path.read_text()), dest.read_bytes()
    r = requests.get(URL, timeout=180, headers=UA)
    r.raise_for_status()
    meta = {
        "download_url": r.url,
        "requested_url": URL,
        "retrieved_at": now(),
        "byte_size": len(r.content),
        "sha256": hashlib.sha256(r.content).hexdigest(),
    }
    dest.write_bytes(r.content)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return meta, r.content


def relation(larger, smaller):
    if larger is None or smaller is None or smaller == 0 or larger <= 0:
        return "missing"
    ratio = larger / smaller
    if ratio > 1.01:
        return "larger"
    if smaller / larger > 1.01:
        return "reversed"
    return "tie"


def order_state(values):
    if any(v is None or not (v > 0) for v in values):
        return "missing"
    rels = [relation(values[i], values[i + 1]) for i in range(3)]
    if all(r == "larger" for r in rels):
        return "match"
    if any(r == "reversed" for r in rels):
        return "reversed"
    return "tie"


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    meta, blob = fetch()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        df = pd.read_csv(io.BytesIO(zf.read(CSV_IN_ZIP)), na_values=["NA"])
    rows = {}
    for sp in ORDER:
        hit = df[df["Species1"] == sp]
        if len(hit) != 1:
            rows[sp] = None
            continue
        rec = hit.iloc[0]
        mass = float(rec["Mass"]) if pd.notna(rec["Mass"]) else None
        wing = float(rec["Wing.Length"]) if pd.notna(rec["Wing.Length"]) else None
        rows[sp] = {"mass_g": mass, "wing_mm": wing}
    missing = [sp for sp in ORDER if rows[sp] is None or rows[sp]["mass_g"] is None or rows[sp]["wing_mm"] is None or rows[sp]["mass_g"] <= 0 or rows[sp]["wing_mm"] <= 0]
    if missing:
        verdict, confidence, reason = "inconclusive", 0.70, "data-unavailable"
        mass_state = wing_state = "missing"
        ratio = None
        little = False
    else:
        masses = [rows[sp]["mass_g"] for sp in ORDER]
        wings = [rows[sp]["wing_mm"] for sp in ORDER]
        mass_state = order_state(masses)
        wing_state = order_state(wings)
        ratio = masses[1] / masses[2]
        little = 1.01 < ratio <= 1.25
        if mass_state == "match" and wing_state == "match" and little:
            gaps = [masses[i] / masses[i + 1] for i in range(3)]
            confidence = 0.85 if min(gaps) >= 1.10 else 0.65
            verdict, reason = "supports", None
        elif mass_state == "reversed" and wing_state == "reversed":
            verdict, confidence, reason = "refutes", 0.85, None
        else:
            verdict, confidence, reason = "mixed", 0.60, None
    table = [{"species": sp, **(rows[sp] or {"mass_g": None, "wing_mm": None})} for sp in ORDER]
    pd.DataFrame(table).to_csv(DERIVED / "columbid_means.csv", index=False)
    measured = {
        "value": None if rows[ORDER[0]] is None else rows[ORDER[0]]["mass_g"],
        "unit": "species-mean body mass of Columba palumbus, grams",
        "n": 4 - len(missing) if not missing else sum(rows[sp] is not None for sp in ORDER),
        "uncertainty": "AVONET species means; a pair is a tie when the ratio is within 1 percent",
        "extra": {
            "mass_order_state": mass_state if not missing else "missing",
            "wing_order_state": wing_state if not missing else "missing",
            "oenas_over_livia_mass": None if missing else round(ratio, 4),
            "little_larger_band": False if missing else little,
            "means": table,
            "missing": missing,
        },
    }
    # fix states when missing path didn't set them in extra consistently
    if missing:
        measured["extra"]["mass_order_state"] = "missing"
        measured["extra"]["wing_order_state"] = "missing"
    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = confidence
    result["data_kind"] = "none" if missing and all(rows[sp] is None for sp in ORDER) else "biological"
    if reason:
        result["reason"] = reason
    result["datasets"] = [{
        "id": "avonet-tobias2022-eledata-birdlife",
        "name": "AVONET ELEData.zip, TraitData/AVONET1_BirdLife.csv species means",
        "landing_url": "https://figshare.com/articles/dataset/AVONET_morphological_ecological_and_geographical_data_for_all_birds_Tobias_et_al_2021_Ecology_Letters_/16586228",
        "doi": "10.6084/m9.figshare.16586228.v7",
        "version": "figshare ELEData.zip; paper 10.1111/ele.13898",
        "license": "CC BY 4.0",
        "files": [{k: meta[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
        "role": "species-mean body mass and wing length of the four columbids",
    }]
    result["method"] = (
        "Downloaded the AVONET ELEData zip, read AVONET1_BirdLife.csv, and kept the four exact Species1 rows. "
        "Adjacent species were compared on mass and on wing length with a 1.01 ratio required for a strict difference. "
        "The stock dove counts as a little larger than the rock pigeon only when its mass ratio is above 1.01 and at most 1.25. "
        "Both measurements must show the full order, and the mass ratio must fall in that band, to support the claim."
    )
    result["measured"] = measured
    if verdict == "supports":
        headline = "Wood pigeon, stock dove, rock pigeon, and turtle dove decrease in that order in mass and in wing length, and the stock dove is only a little heavier than the rock pigeon."
    elif verdict == "refutes":
        headline = (
            f"The wood pigeon is heaviest ({masses[0]:.1f} g) and the turtle dove lightest ({masses[3]:.1f} g), "
            f"but the stock dove ({masses[1]:.1f} g, wing {wings[1]:.1f} mm) is smaller than the rock pigeon "
            f"({masses[2]:.1f} g, wing {wings[2]:.1f} mm) on both measurements, so both reverse the claimed order."
        )
    elif verdict == "mixed":
        headline = "Mass and wing length do not both show the claimed order with the stock dove only a little larger than the rock pigeon."
    else:
        headline = "AVONET is missing a mass or a wing length for at least one of the four pigeons."
    result["results_summary"] = [headline]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "confidence": confidence, "extra": measured["extra"]}, indent=2))


if __name__ == "__main__":
    main()
