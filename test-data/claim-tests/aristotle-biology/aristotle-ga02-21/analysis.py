#!/usr/bin/env python3
"""Eel sexes from FishBase reproduction modes."""
import csv
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
UA = "delphi-claim-test/1.0 (research; aristotle-biology)"
SPECIES_URL = "https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/fb/v24.07/csv/species.csv"
REPRO_URL = "https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/fb/v24.07/csv/reproduc.csv"
SUPPORT = {"neither", "none", "no sex", "undifferentiated", "asexual", "sexless"}
REFUTE_PARTS = ("dioec", "gonochor", "hermaphrod", "protogyn", "protandr", "parthenogen")


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


def classify_mode(mode):
    text = mode.strip().lower()
    if text in SUPPORT:
        return "supports"
    if any(part in text for part in REFUTE_PARTS):
        return "refutes"
    return "unrecognized"


def classify_species(modes):
    kinds = {classify_mode(mode) for mode in modes if mode.strip()}
    if not kinds:
        return None
    if "refutes" in kinds:
        return "refutes"
    if kinds == {"supports"}:
        return "supports"
    return "unrecognized"


def verdict_from(species_rows):
    """species_rows: list of {name, status} for species with a non-blank mode."""
    if not species_rows:
        return "inconclusive", "data-unavailable"
    statuses = {row["status"] for row in species_rows}
    if statuses == {"supports"}:
        return "supports", None
    classified = [row for row in species_rows if row["status"] in {"supports", "refutes"}]
    if classified and all(row["status"] == "refutes" for row in classified) and "supports" not in statuses:
        return "refutes", None
    if "supports" in statuses and "refutes" in statuses:
        return "mixed", None
    return "inconclusive", "not-operationalizable"


def self_test():
    assert classify_mode("dioecism") == "refutes"
    assert classify_mode("protogyny") == "refutes"
    assert classify_mode("neither") == "supports"
    assert classify_mode("gonochorism") == "refutes"
    assert verdict_from([{"name": "Anguilla anguilla", "status": "refutes"}])[0] == "refutes"
    assert verdict_from([{"name": "Anguilla anguilla", "status": "supports"}])[0] == "supports"
    assert verdict_from([])[0] == "inconclusive"
    assert verdict_from(
        [
            {"name": "A", "status": "supports"},
            {"name": "B", "status": "refutes"},
        ]
    )[0] == "mixed"
    print("self-test ok")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    result = json.loads((ROOT / "result.json").read_text())
    try:
        species_meta = fetch(SPECIES_URL, CACHE / "species.csv")
        repro_meta = fetch(REPRO_URL, CACHE / "reproduc.csv")
    except Exception as exc:
        result.update(
            {
                "status": "complete",
                "verdict": "inconclusive",
                "reason": "data-unavailable",
                "confidence": 0.8,
                "data_kind": "none",
                "method": f"FishBase files could not be downloaded ({exc}).",
                "measured": {"value": None, "unit": "Anguilla species", "n": 0, "uncertainty": None, "extra": {}},
            }
        )
        (ROOT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print("inconclusive", exc)
        return
    anguilla = {}
    with (CACHE / "species.csv").open(newline="", encoding="utf-8", errors="replace") as handle:
        for record in csv.DictReader(handle):
            if (record.get("Genus") or "").strip().lower() == "anguilla":
                anguilla[(record.get("SpecCode") or "").strip()] = (
                    f"{(record.get('Genus') or '').strip()} {(record.get('Species') or '').strip()}"
                )
    modes = {code: [] for code in anguilla}
    with (CACHE / "reproduc.csv").open(newline="", encoding="utf-8", errors="replace") as handle:
        for record in csv.DictReader(handle):
            code = (record.get("SpecCode") or "").strip()
            if code not in anguilla:
                continue
            mode = (record.get("ReproMode") or "").strip()
            if mode:
                modes[code].append(mode)
    rows = []
    for code, name in sorted(anguilla.items(), key=lambda item: item[1]):
        status = classify_species(modes[code])
        if status is None:
            continue
        rows.append({"spec_code": code, "name": name, "modes": sorted(set(modes[code])), "status": status})
    verdict, reason = verdict_from(rows)
    n_refute = sum(1 for row in rows if row["status"] == "refutes")
    measured = {
        "value": n_refute,
        "unit": "Anguilla species whose FishBase reproduction mode refutes sexlessness",
        "n": len(rows),
        "uncertainty": "exact codes in the v24.07 reproduc table",
        "extra": {
            "anguilla_species_in_species_table": len(anguilla),
            "species": rows,
        },
    }
    result.update(
        {
            "status": "complete",
            "verdict": verdict,
            "confidence": 0.9 if verdict in {"supports", "refutes"} else 0.7,
            "data_kind": "none" if reason == "data-unavailable" else "biological",
            "method": (
                "Joined FishBase v24.07 species.csv to reproduc.csv on SpecCode for genus Anguilla. "
                "Non-blank ReproMode values were classed with the pre-registered supporting and refuting sets. "
                "The mullet clause was not scored. A species with any refuting mode is refuting."
            ),
            "datasets": [
                {
                    "id": "fishbase-v24.07-species",
                    "name": "FishBase species table v24.07",
                    "landing_url": "https://huggingface.co/datasets/cboettig/fishbase",
                    "doi": None,
                    "version": "24.07",
                    "license": "CC-BY-NC, FishBase.org Team",
                    "files": [{**species_meta, "name": "species.csv"}],
                    "role": "genus and species names for SpecCode",
                },
                {
                    "id": "fishbase-v24.07-reproduc",
                    "name": "FishBase reproduction table v24.07",
                    "landing_url": "https://huggingface.co/datasets/cboettig/fishbase",
                    "doi": None,
                    "version": "24.07",
                    "license": "CC-BY-NC, FishBase.org Team",
                    "files": [{**repro_meta, "name": "reproduc.csv"}],
                    "role": "ReproMode for eels",
                },
            ],
            "measured": measured,
            "results_summary": [f"{n_refute} of {len(rows)} classified Anguilla species refute sexlessness."],
        }
    )
    if reason:
        result["reason"] = reason
    (ROOT / "derived").mkdir(exist_ok=True)
    (ROOT / "derived" / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, rows)


if __name__ == "__main__":
    main()
