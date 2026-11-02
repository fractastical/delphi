#!/usr/bin/env python3
"""Clutch size of the common kestrel against other raptors and owls.

Decision rule: result.json pass_criterion, committed before the figshare zip was downloaded.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
URL = "https://ndownloader.figshare.com/files/8067269"
MD5_DATABASE = "10e7c14395d95ed7f53258f96fadb4f7"
MD5_RANGE = "8095602c7d10befc52feaf22db8e6c76"
ORDERS = {"accipitriformes", "falconiformes", "strigiformes"}
LOCKED = {
    "hypothesis", "pass_criterion", "fail_criterion", "planned_datasets", "test_contract",
    "claim_id", "claim_iri", "project", "preregistered_at", "interpretation",
}


def fetch():
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / "ECOL_96_269.zip"
    last = None
    if not dest.exists() or dest.stat().st_size == 0:
        for i in range(3):
            try:
                req = urllib.request.Request(URL, headers={"User-Agent": "delphisci-claim-test"})
                with urllib.request.urlopen(req, timeout=180) as resp:
                    dest.write_bytes(resp.read())
                break
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(2 * (i + 1))
        else:
            raise last
    raw = dest.read_bytes()
    info = {
        "name": "ECOL_96_269.zip",
        "download_url": URL,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    return info, raw


def members(raw):
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = zf.namelist()
    csvs = [n for n in names if n.lower().endswith(".csv")]
    nested = [n for n in names if n.lower().endswith(".zip")]
    if not csvs and nested:
        zf = zipfile.ZipFile(io.BytesIO(zf.read(nested[0])))
    found = {}
    for name in zf.namelist():
        base = name.split("/")[-1].lower()
        if base.startswith("amniote_database_aug_2015") and base.endswith(".csv") and "reference" not in base:
            found["database"] = zf.read(name)
            found["database_name"] = name
        elif "range_count" in base and base.endswith(".csv"):
            found["range"] = zf.read(name)
            found["range_name"] = name
    return found


def norm(name):
    return "".join(ch for ch in name.lower() if ch.isalnum())


def column(fieldnames, token):
    token = norm(token)
    for name in fieldnames:
        if norm(name) == token:
            return name
    return None


def rows_of(blob):
    text = blob.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    header = 0
    for i, line in enumerate(lines[:15]):
        if "litter_or_clutch_size" in line or "genus" in line.lower():
            header = i
            break
    return list(csv.DictReader(io.StringIO("\n".join(lines[header:]))))


def num(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value < 0:
        return None
    return value


def blank(text):
    text = (text or "").strip()
    return text == "" or text in {"-999", "-999.0"}


def write_result(fields):
    doc = json.loads(RESULT.read_text())
    for key in fields:
        if key in LOCKED:
            raise SystemExit("refusing to edit locked field " + key)
    doc.update(fields)
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")


def dataset(info, extra_files):
    return [{
        "id": "myhrvold-2015-amniote-figshare-3563457-v1",
        "name": "An amniote life-history database (Myhrvold et al. 2015), figshare Full Archive",
        "landing_url": "https://doi.org/10.6084/m9.figshare.3563457.v1",
        "doi": "10.6084/m9.figshare.3563457.v1",
        "version": "v1",
        "license": "CC0",
        "files": [info, *extra_files],
        "role": "species-level median clutch size and recorded clutch-size maximum for birds",
    }]


def stop(verdict, reason, confidence, measured, info, method, summary, data_kind="none"):
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    fields = {
        "status": "complete", "verdict": verdict, "confidence": confidence, "data_kind": data_kind,
        "measured": measured, "datasets": dataset(info, []), "method": method, "results_summary": summary,
    }
    if reason:
        fields["reason"] = reason
    write_result(fields)


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    try:
        info, raw = fetch()
        found = members(raw)
    except Exception as exc:  # noqa: BLE001
        measured = {"value": None, "unit": "eggs (median clutch of Falco tinnunculus)", "n": 0, "uncertainty": None, "extra": {"error": str(exc)}}
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        doc = json.loads(RESULT.read_text())
        doc.update({
            "status": "complete", "verdict": "inconclusive", "reason": "data-unavailable",
            "confidence": 0.3, "data_kind": "none", "measured": measured,
            "method": "The figshare zip could not be downloaded or opened.",
            "results_summary": [str(exc)],
        })
        RESULT.write_text(json.dumps(doc, indent=2) + "\n")
        print("download failed", exc)
        return
    if "database" not in found or "range" not in found:
        stop("inconclusive", "data-unavailable", 0.3,
             {"value": None, "unit": "eggs (median clutch of Falco tinnunculus)", "n": 0, "uncertainty": None, "extra": {"entries": list(found)}},
             info, "The zip did not contain both pre-registered CSV files.", ["Required CSV missing."])
        return
    db_md5 = hashlib.md5(found["database"]).hexdigest()
    range_md5 = hashlib.md5(found["range"]).hexdigest()
    if db_md5 != MD5_DATABASE or range_md5 != MD5_RANGE:
        stop("inconclusive", "data-unavailable", 0.4,
             {"value": None, "unit": "eggs (median clutch of Falco tinnunculus)", "n": 0, "uncertainty": None,
              "extra": {"database_md5": db_md5, "range_md5": range_md5, "database_md5_expected": MD5_DATABASE, "range_md5_expected": MD5_RANGE}},
             info, "A CSV checksum did not match the Ecological Archives MD5, so clutch sizes were not used.",
             [f"database md5 {db_md5}", f"range md5 {range_md5}"])
        print("md5 mismatch", db_md5, range_md5)
        return
    db_rows = rows_of(found["database"])
    range_rows = rows_of(found["range"])
    if not db_rows:
        stop("inconclusive", "data-unavailable", 0.3, {"value": None, "unit": "eggs", "n": 0, "uncertainty": None, "extra": {}}, info, "The database CSV had no rows.", ["Empty database."])
        return
    fields = db_rows[0].keys()
    c_class = column(fields, "class")
    c_order = column(fields, "order")
    c_genus = column(fields, "genus")
    c_species = column(fields, "species")
    c_sub = column(fields, "subspecies")
    c_clutch = column(fields, "litter_or_clutch_size_n")
    c_name = column(fields, "common_name")
    if not all([c_class, c_order, c_genus, c_species, c_clutch]):
        stop("inconclusive", "other", 0.3,
             {"value": None, "unit": "eggs", "n": 0, "uncertainty": None, "extra": {"columns": list(fields)}},
             info, "The database header did not contain the pre-registered columns.", ["Header: " + ", ".join(fields)])
        return
    rfields = range_rows[0].keys() if range_rows else []
    r_genus = column(rfields, "genus")
    r_species = column(rfields, "species")
    r_sub = column(rfields, "subspecies")
    r_max = column(rfields, "max_litter_clutch_size")
    maxima = {}
    for row in range_rows:
        if not r_genus or not r_species or not r_max:
            break
        if r_sub and not blank(row.get(r_sub)):
            continue
        key = ((row.get(r_genus) or "").strip().lower(), (row.get(r_species) or "").strip().lower())
        maxima[key] = num(row.get(r_max))

    species_rows = {}
    duplicates = set()
    for row in db_rows:
        if (row.get(c_class) or "").strip().lower() != "aves":
            continue
        if (row.get(c_order) or "").strip().lower() not in ORDERS:
            continue
        if c_sub and not blank(row.get(c_sub)):
            continue
        clutch = num(row.get(c_clutch))
        if clutch is None or clutch <= 0:
            continue
        key = ((row.get(c_genus) or "").strip().lower(), (row.get(c_species) or "").strip().lower())
        if key in species_rows:
            duplicates.add(key)
            continue
        species_rows[key] = {
            "genus": (row.get(c_genus) or "").strip(),
            "species": (row.get(c_species) or "").strip(),
            "order": (row.get(c_order) or "").strip(),
            "common_name": (row.get(c_name) or "").strip() if c_name else "",
            "median": clutch,
            "maximum": maxima.get(key),
        }
    for key in duplicates:
        species_rows.pop(key, None)
    kestrel_keys = [k for k in species_rows if k == ("falco", "tinnunculus")]
    if len(kestrel_keys) != 1:
        stop("inconclusive", "underpowered" if len(kestrel_keys) == 0 else "other", 0.4,
             {"value": None, "unit": "eggs (median clutch of Falco tinnunculus)", "n": len(species_rows), "uncertainty": None,
              "extra": {"n_species_level_raptors_with_clutch": len(species_rows), "kestrel_rows": len(kestrel_keys)}},
             info, "Falco tinnunculus did not have exactly one species-level median.", [f"Kestrel species-level rows: {len(kestrel_keys)}."],
             data_kind="biological")
        return
    kestrel = species_rows[("falco", "tinnunculus")]
    others = [r for k, r in species_rows.items() if k != ("falco", "tinnunculus")]
    if len(others) < 30 or kestrel["maximum"] is None:
        reason = "underpowered" if len(others) < 30 else "data-unavailable"
        stop("inconclusive", reason, 0.4,
             {"value": kestrel["median"], "unit": "eggs (median clutch of Falco tinnunculus)", "n": len(others), "uncertainty": None,
              "extra": {"kestrel_maximum": kestrel["maximum"], "n_other": len(others)}},
             info, "The pre-registered sample size or the kestrel maximum was missing.",
             [f"Other raptors: {len(others)}. Kestrel maximum: {kestrel['maximum']}."],
             data_kind="biological" if len(others) else "none")
        return
    kmed = kestrel["median"]
    kmax = kestrel["maximum"]
    other_medians = [r["median"] for r in others]
    max_other = max(other_medians)
    c1 = all(m <= 3 for m in other_medians)
    c2 = kmed > max_other
    c3 = kmax >= 5
    above = [r for r in others if r["median"] >= kmed]
    above.sort(key=lambda r: -r["median"])
    not_unprolific = [r for r in others if r["median"] > 3]
    if c1 and c2 and c3:
        verdict, confidence = "supports", 0.80
    elif kmax < 4 or above:
        verdict, confidence = "refutes", 0.80
    elif kmax >= 4 and c2 and (not c1 or kmax == 4):
        verdict, confidence = "mixed", 0.55
    else:
        verdict, confidence = "mixed", 0.55
    measured = {
        "value": kmed,
        "unit": "eggs (median clutch of Falco tinnunculus)",
        "n": len(others) + 1,
        "uncertainty": None,
        "extra": {
            "kestrel_median": kmed,
            "kestrel_maximum": kmax,
            "n_other": len(others),
            "max_other_median": max_other,
            "n_other_median_above_3": len(not_unprolific),
            "n_other_median_ge_kestrel": len(above),
            "c1_all_others_median_le_3": c1,
            "c2_kestrel_strictly_highest_median": c2,
            "c3_kestrel_maximum_ge_5": c3,
            "others_at_or_above_kestrel": [
                {"binomial": r["genus"] + " " + r["species"], "order": r["order"], "median": r["median"], "maximum": r["maximum"], "common_name": r["common_name"]}
                for r in above[:15]
            ],
            "largest_other_clutches": [
                {"binomial": r["genus"] + " " + r["species"], "order": r["order"], "median": r["median"], "common_name": r["common_name"]}
                for r in sorted(others, key=lambda r: -r["median"])[:10]
            ],
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    inner = [
        {"name": found["database_name"], "byte_size": len(found["database"]), "md5": db_md5, "sha256": hashlib.sha256(found["database"]).hexdigest()},
        {"name": found["range_name"], "byte_size": len(found["range"]), "md5": range_md5, "sha256": hashlib.sha256(found["range"]).hexdigest()},
    ]
    doc = json.loads(RESULT.read_text())
    odd = [r for r in others if r["maximum"] is not None and r["maximum"] >= 15]
    if odd:
        note = "Recorded maxima of species other than the kestrel are not used in the verdict. At least one of those maxima is 15 or above, which is left as published in the range file."
        caveats = list(doc.get("caveats") or [])
        if note not in caveats:
            caveats.append(note)
        doc["caveats"] = caveats
        RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    write_result({
        "status": "complete",
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological",
        "measured": measured,
        "datasets": dataset(info, inner),
        "method": "Downloaded the figshare archive, checked both CSV files against the Ecological Archives MD5 values, and compared species-level median clutch size for Aves in Accipitriformes, Falconiformes, and Strigiformes. The kestrel maximum came from the range file. Orders were not added after the values were read.",
        "results_summary": [
            f"Falco tinnunculus median {kmed}, maximum {kmax}. Other species with a median: {len(others)}. Largest other median: {max_other}.",
            f"C1 all others <= 3: {c1}. C2 kestrel strictly highest: {c2}. C3 maximum >= 5: {c3}.",
            f"Other species with median > 3: {len(not_unprolific)}. Other species with median >= kestrel: {len(above)}.",
        ],
    })
    print(verdict, kmed, kmax, len(others), max_other)


if __name__ == "__main__":
    main()
