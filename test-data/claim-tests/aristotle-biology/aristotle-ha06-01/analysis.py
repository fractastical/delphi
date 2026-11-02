#!/usr/bin/env python3
"""aristotle-ha06-01: raptor clutch size versus the common kestrel in AnAge.

Rules are those in result.json. Run: python3 analysis.py
"""
import csv
import datetime as dt
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RESULT = HERE / "result.json"
DERIVED = HERE / "derived"
DATA = HERE / "data"
EXPECTED_SHA = "e3ddb66e32e973a79932859ba53013e8f60d957c6ec01c6eb573e3ea3018d630"
EXPECTED_SIZE = 169150
URL = "https://genomics.senescence.info/species/dataset.zip"
VENDORED = ROOT / "test-data/organisms/darwin-origin/ch11-14/data/anage_build15_dataset.zip"
ORDERS = {"accipitriformes", "falconiformes", "strigiformes"}
RANGE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*$")


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def load_zip():
    DATA.mkdir(parents=True, exist_ok=True)
    source = "download"
    raw = None
    if VENDORED.exists():
        vendored = VENDORED.read_bytes()
        if sha256(vendored) == EXPECTED_SHA and len(vendored) == EXPECTED_SIZE:
            raw = vendored
            source = "vendored"
    if raw is None:
        req = urllib.request.Request(URL, headers={"User-Agent": "delphisci-claim-test"})
        raw = urllib.request.urlopen(req, timeout=120).read()
    (DATA / "dataset.zip").write_bytes(raw)
    return raw, {
        "name": "dataset.zip",
        "download_url": URL,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": sha256(raw),
        "source_used": source,
        "vendored_path": "test-data/organisms/darwin-origin/ch11-14/data/anage_build15_dataset.zip",
    }


def clutch_of(cell):
    if cell is None:
        return None, False
    s = str(cell).strip()
    if s == "" or s.upper() in {"NA", "N/A", "NULL"}:
        return None, False
    m = RANGE.match(s)
    if m:
        return float(m.group(2)), True
    try:
        return float(s), False
    except ValueError:
        return None, False


def main():
    result = json.loads(RESULT.read_text())
    raw, file_info = load_zip()
    DERIVED.mkdir(parents=True, exist_ok=True)
    ok = file_info["sha256"] == EXPECTED_SHA and file_info["byte_size"] == EXPECTED_SIZE

    def finish(verdict, reason, confidence, measured, method):
        result["status"] = "complete"
        result["verdict"] = verdict
        if reason:
            result["reason"] = reason
        else:
            result.pop("reason", None)
        result["confidence"] = confidence
        result["data_kind"] = "none" if reason == "data-unavailable" else "biological"
        result["measured"] = measured
        result["method"] = method
        result["datasets"] = [{
            "id": "anage-build-15",
            "name": "AnAge: The Animal Ageing and Longevity Database, build 15",
            "landing_url": "https://genomics.senescence.info/species/",
            "doi": "10.1093/nar/gkx1042",
            "version": "build 15",
            "license": "CC BY 3.0",
            "files": [file_info],
            "role": "litter/clutch size for birds of prey and the common kestrel",
        }]
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        RESULT.write_text(json.dumps(result, indent=2) + "\n")
        print(verdict, measured.get("value"), measured.get("n"))

    if not ok:
        finish("inconclusive", "data-unavailable", 0.2, {"value": None, "unit": "eggs", "n": 0, "extra": file_info},
               "The AnAge zip did not match the pre-registered checksum, so clutch sizes were not compared.")
        return

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("anage_data.txt"))
        text = zf.read(name).decode("utf-8", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
    raptors = []
    range_used = 0
    for r in rows:
        if (r.get("Class") or "").strip().lower() != "aves":
            continue
        if (r.get("Order") or "").strip().lower() not in ORDERS:
            continue
        size, used_range = clutch_of(r.get("Litter/Clutch size"))
        if used_range:
            range_used += 1
        raptors.append({
            "binomial": f"{(r.get('Genus') or '').strip()} {(r.get('Species') or '').strip()}".strip(),
            "order": (r.get("Order") or "").strip(),
            "common": (r.get("Common name") or "").strip(),
            "clutch": size,
        })
    kestrel_rows = [p for p in raptors if p["binomial"].lower() == "falco tinnunculus"]
    kestrels = [p for p in kestrel_rows if p["clutch"] is not None]
    others = [p for p in raptors if p["binomial"].lower() != "falco tinnunculus" and p["clutch"] is not None]
    if not kestrels or len(others) < 15:
        measured = {
            "value": kestrels[0]["clutch"] if kestrels else None,
            "unit": "eggs per clutch",
            "n": len(others),
            "extra": {
                "n_raptors_with_clutch": len(others) + (1 if kestrels else 0),
                "kestrel_row_present": bool(kestrel_rows),
                "kestrel_clutch_blank": bool(kestrel_rows) and not kestrels,
                "kestrel_found": bool(kestrels),
                "range_cells": range_used,
            },
        }
        reason = "underpowered" if kestrels and len(others) < 15 else "data-unavailable"
        finish("inconclusive", reason, 0.35, measured, "AnAge loaded, but the kestrel clutch or the minimum of 15 other raptor clutches was missing.")
        return

    k = kestrels[0]["clutch"]
    greater = [p for p in others if p["clutch"] > k]
    below4 = [p for p in others if p["clutch"] < 4]
    frac_below = len(below4) / len(others)
    greater.sort(key=lambda p: -p["clutch"])
    top = sorted(others, key=lambda p: -p["clutch"])[:12]
    measured = {
        "value": k,
        "unit": "eggs, Falco tinnunculus clutch size",
        "n": len(others),
        "extra": {
            "fraction_other_raptors_clutch_below_4": round(frac_below, 4),
            "n_other_below_4": len(below4),
            "n_other_strictly_greater": len(greater),
            "greater_than_kestrel": [{"binomial": p["binomial"], "order": p["order"], "clutch": p["clutch"]} for p in greater[:20]],
            "largest_other": [{"binomial": p["binomial"], "order": p["order"], "common": p["common"], "clutch": p["clutch"]} for p in top],
            "kestrel_is_unique_maximum": len(greater) == 0 and all(p["clutch"] < k for p in others),
            "range_cells_parsed_as_upper": range_used,
            "orders_present": sorted({p["order"] for p in raptors}),
        },
    }
    unique_max = all(p["clutch"] < k for p in others)
    if k >= 4 and unique_max and frac_below >= 0.80:
        verdict, reason, conf = "supports", None, 0.7
    elif k < 4 or len(greater) >= 5 or frac_below < 0.50:
        verdict, reason, conf = "refutes", None, 0.8
    else:
        verdict, reason, conf = "mixed", None, 0.6
    finish(
        verdict,
        reason,
        conf,
        measured,
        "Took clutch size for Aves in Accipitriformes, Falconiformes and Strigiformes from AnAge, parsed ranges at the upper end, and applied the pre-registered rules to Falco tinnunculus versus the other species.",
    )


if __name__ == "__main__":
    main()
