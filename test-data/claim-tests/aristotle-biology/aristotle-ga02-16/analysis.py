#!/usr/bin/env python3
"""Reproductive mode of sharks and rays in Sharkipedia traits v1.0.

Rules are the preregistered result.json. The script downloads the CSV,
checks the provider md5 and size, and classifies Reproductive mode values.
"""
import csv
import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test/aristotle-ga02-16"}


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest):
    DATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size == 0:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r:
            dest.write_bytes(r.read())
    raw = dest.read_bytes()
    return {
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "md5": hashlib.md5(raw).hexdigest(),
        "path": str(dest.name),
    }


def classify(value):
    v = (value or "").casefold()
    if not v.strip():
        return "blank"
    if "aplacental" in v:
        return "not_uterine_connection"
    if "placent" in v:
        return "placental"
    if "histotroph" in v or "trophonema" in v:
        return "uterine_nonplacental"
    if any(s in v for s in ("ovipar", "egg-lay", "egg lay", "lecithotroph")):
        return "not_uterine_connection"
    return "ambiguous"


PRIORITY = ["placental", "uterine_nonplacental", "ambiguous", "not_uterine_connection", "blank"]


def main():
    result = json.loads(RESULT.read_text())
    rules = result["rules"]
    exp = result["expected_files"][0]
    meta = fetch(exp["download_url"], DATA / exp["name"])
    checksum_ok = meta["md5"] == exp["md5"] and meta["byte_size"] == exp["byte_size"]
    rows = []
    with (DATA / exp["name"]).open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        if "trait_name" not in headers or "value" not in headers or "species_name" not in headers:
            result["status"] = "complete"
            result["verdict"] = "inconclusive"
            result["reason"] = "data-unavailable"
            result["confidence"] = rules["confidence"]["inconclusive"]
            result["data_kind"] = "none"
            result["measured"] = {"value": None, "unit": "placental species", "n": 0, "extra": {"headers": headers}}
            result["method"] = "The traits file did not have trait_name, value, and species_name columns, so no reproductive mode was classified."
            result["datasets"] = [_dataset(exp, meta, "reproductive mode of sharks and rays")]
            RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            return
        for row in reader:
            if (row.get("trait_name") or "").strip().casefold() == rules["trait_name"]:
                rows.append(row)
    by_species = {}
    value_counts = {}
    for row in rows:
        species = (row.get("species_name") or "").strip()
        if not species:
            continue
        label = classify(row.get("value"))
        value_counts[row.get("value") or ""] = value_counts.get(row.get("value") or "", 0) + 1
        by_species.setdefault(species, set()).add(label)
    species_class = {}
    for species, labels in by_species.items():
        for label in PRIORITY:
            if label in labels:
                species_class[species] = label
                break
    counts = {k: 0 for k in PRIORITY}
    for label in species_class.values():
        counts[label] += 1
    placental = sorted(s for s, lab in species_class.items() if lab == "placental")
    n = len(species_class)
    n_plac = len(placental)
    if not checksum_ok:
        verdict, reason, conf = "inconclusive", "data-unavailable", rules["confidence"]["inconclusive"]
    elif n_plac >= 1:
        verdict, reason = "supports", None
        conf = rules["confidence"]["supports_at_least_5"] if n_plac >= 5 else rules["confidence"]["supports_1_to_4"]
    elif counts["uterine_nonplacental"] >= 1:
        verdict, reason, conf = "mixed", None, rules["confidence"]["mixed"]
    elif n >= rules["min_species_to_refute"] and counts["ambiguous"] == 0 and counts["blank"] == 0:
        verdict, reason, conf = "refutes", None, rules["confidence"]["refutes"]
    elif n < rules["min_species_to_refute"]:
        verdict, reason, conf = "inconclusive", "underpowered", rules["confidence"]["inconclusive"]
    else:
        verdict, reason, conf = "inconclusive", "underpowered", rules["confidence"]["inconclusive"]
    measured = {
        "value": n_plac,
        "unit": "species with a placental reproductive-mode record",
        "n": n,
        "extra": {
            "checksum_ok": checksum_ok,
            "n_records": len(rows),
            "species_class_counts": counts,
            "placental_species": placental,
            "value_record_counts": dict(sorted(value_counts.items(), key=lambda kv: -kv[1])),
        },
    }
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2, ensure_ascii=False) + "\n")
    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = conf
    result["data_kind"] = "biological" if checksum_ok else "none"
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["measured"] = measured
    result["datasets"] = [_dataset(exp, meta, "reproductive mode of sharks and rays")]
    result["method"] = (
        "Downloaded Sharkipedia-Traits-v1.0, checked md5 and byte size against the Zenodo record, "
        "kept rows whose trait_name is Reproductive mode, classified each value with the preregistered "
        "substrings (aplacental before placent), and collapsed to one class per species with placental priority."
    )
    result["results_summary"] = [
        f"Reproductive-mode records: {len(rows)} rows, {n} species.",
        f"Placental species: {n_plac}. Uterine non-placental species: {counts['uterine_nonplacental']}. "
        f"Negative species: {counts['not_uterine_connection']}. Ambiguous species: {counts['ambiguous']}.",
        f"Verdict {verdict}.",
    ]
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, "placental", n_plac, "of", n)


def _dataset(exp, meta, role):
    return {
        "id": "sharkipedia-traits-v1.0-zenodo-6656525",
        "name": "Sharkipedia traits v1.0 (22 Jan 2025 export)",
        "landing_url": exp["landing_url"],
        "doi": exp["doi"],
        "version": "1.0",
        "license": exp["license"],
        "files": [{k: meta[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256", "md5")}],
        "role": role,
    }


if __name__ == "__main__":
    main()
