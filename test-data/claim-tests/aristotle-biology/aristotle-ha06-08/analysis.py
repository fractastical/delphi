#!/usr/bin/env python3
"""aristotle-ha06-08: share of bird species with female maturity under 365 days.

Pre-registered in result.json before anage_data.txt was read. Thresholds live there
and are not revised here. Run: python3 analysis.py
"""
import csv
import datetime as dt
import hashlib
import io
import json
import zipfile
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
ZIP_URL = "https://genomics.senescence.info/species/dataset.zip"
UA = "delphisci-claim-test/aristotle-ha06-08"


def fetch_zip():
    DATA.mkdir(exist_ok=True)
    path = DATA / "dataset.zip"
    if not path.exists():
        r = requests.get(ZIP_URL, headers={"User-Agent": UA}, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
        retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        retrieved = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = path.read_bytes()
    return raw, retrieved


def load_rows(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("anage_data.txt"))
        text = zf.read(name).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    return list(reader), reader.fieldnames


def num(value):
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def confidence(verdict, p):
    if verdict == "inconclusive":
        return 0.40
    if verdict == "mixed":
        return 0.55
    if verdict == "supports" and p <= 0.10:
        return 0.80
    if verdict == "refutes" and p >= 0.50:
        return 0.80
    return 0.68


def main():
    raw, retrieved = fetch_zip()
    rows, fields = load_rows(raw)
    needed = ["Class", "Female maturity (days)", "Data quality", "Genus", "Species"]
    missing = [c for c in needed if c not in fields]
    result = json.loads((HERE / "result.json").read_text())
    file_meta = {
        "name": "dataset.zip",
        "download_url": ZIP_URL,
        "retrieved_at": retrieved,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    result["datasets"] = [{
        "id": "anage-build-15",
        "name": "AnAge: The Animal Ageing and Longevity Database, build 15",
        "landing_url": "https://genomics.senescence.info/species/",
        "doi": "10.1093/nar/gks1155",
        "version": "build 15",
        "license": "CC BY 3.0 (Human Ageing Genomic Resources terms)",
        "files": [file_meta],
        "role": "female age at sexual maturity for bird species",
    }]
    if missing:
        result["status"] = "complete"
        result["verdict"] = "inconclusive"
        result["reason"] = "data-unavailable"
        result["data_kind"] = "none"
        result["confidence"] = 0.40
        result["measured"] = {"value": None, "unit": "proportion", "n": 0, "uncertainty": None, "extra": {"missing_columns": missing}}
        result["method"] = "The AnAge zip was fetched and opened, but the expected columns were not present, so no proportion was computed."
        (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print("inconclusive data-unavailable", missing)
        return

    birds = []
    for row in rows:
        if (row.get("Class") or "").strip().casefold() != "aves":
            continue
        maturity = num(row.get("Female maturity (days)"))
        if maturity is None or maturity <= 0:
            continue
        birds.append({
            "binomial": f"{(row.get('Genus') or '').strip()} {(row.get('Species') or '').strip()}".strip(),
            "maturity_days": maturity,
            "quality": (row.get("Data quality") or "").strip().casefold(),
            "origin": (row.get("Specimen origin") or "").strip(),
        })
    n = len(birds)
    n_under = sum(1 for b in birds if b["maturity_days"] < 365)
    n_at_most_365 = sum(1 for b in birds if b["maturity_days"] <= 365)
    n_under_730 = sum(1 for b in birds if b["maturity_days"] < 730)
    reliable = [b for b in birds if b["quality"] != "questionable"]
    n_rel = len(reliable)
    n_rel_under = sum(1 for b in reliable if b["maturity_days"] < 365)
    p = (n_under / n) if n else None
    p_rel = (n_rel_under / n_rel) if n_rel else None

    if n < 40:
        verdict, reason = "inconclusive", "underpowered"
    elif p <= 0.15:
        verdict, reason = "supports", None
    elif p >= 0.40:
        verdict, reason = "refutes", None
    else:
        verdict, reason = "mixed", None

    origins = {}
    for b in birds:
        origins[b["origin"] or "blank"] = origins.get(b["origin"] or "blank", 0) + 1
    extra = {
        "n_maturity_under_365": n_under,
        "proportion_maturity_le_365": (n_at_most_365 / n) if n else None,
        "proportion_maturity_under_730": (n_under_730 / n) if n else None,
        "n_excluding_questionable": n_rel,
        "proportion_excluding_questionable": p_rel,
        "specimen_origin_counts": origins,
        "min_maturity_days": min((b["maturity_days"] for b in birds), default=None),
        "max_maturity_days": max((b["maturity_days"] for b in birds), default=None),
    }
    result["status"] = "complete"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    result["data_kind"] = "biological" if verdict != "inconclusive" else "biological"
    if verdict == "inconclusive" and reason == "data-unavailable":
        result["data_kind"] = "none"
    result["confidence"] = confidence(verdict, p if p is not None else 1)
    result["measured"] = {
        "value": p,
        "unit": "proportion of bird species with female maturity under 365 days",
        "n": n,
        "uncertainty": None,
        "extra": extra,
    }
    result["method"] = (
        "Downloaded the AnAge build zip, read anage_data.txt, kept Class Aves rows with a positive "
        "female maturity in days, and computed the proportion under 365 days. The pre-registered "
        "cutoffs 0.15 and 0.40 set the verdict. Proportions that drop questionable rows, or that "
        "use 365 and 730 days, are reported and were not used for the verdict."
    )
    result["results_summary"] = [
        f"Bird species with female maturity: n={n}, of which {n_under} are under 365 days (p={p}).",
        f"Excluding questionable data quality: n={n_rel}, p={p_rel}.",
        f"Verdict {verdict} under the pre-registered cutoffs.",
    ]
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({
        "proportion": p,
        "n": n,
        "n_under_365": n_under,
        "origins": origins,
        "shortest": sorted(birds, key=lambda b: b["maturity_days"])[:15],
    }, indent=2) + "\n")
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, "p", p, "n", n)


if __name__ == "__main__":
    main()
