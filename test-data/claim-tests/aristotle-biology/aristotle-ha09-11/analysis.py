#!/usr/bin/env python3
"""Habitat of fully web-footed bird families for aristotle-ha09-11.

Support only if every coded species in the pre-registered families uses
wetland, river, coast, or open sea. Refute if the exception rate is at
least 0.05. Mixed if exceptions exist and stay under 0.05. The family
list and the cuts were committed before the workbook was downloaded.
"""
import datetime as dt
import hashlib
import json
import math
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
URL = "https://ndownloader.figshare.com/files/55634729"
MD5 = "36d53d59af1e449db1fc4c30062d9d1f"
SIZE = 6683628
UA = "delphisci-claim-test/1.0"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

FAMILIES = {
    "anatidae", "podicipedidae", "gaviidae", "spheniscidae", "diomedeidae",
    "procellariidae", "hydrobatidae", "oceanitidae", "pelecanoididae",
    "pelecanidae", "sulidae", "phalacrocoracidae", "anhingidae", "fregatidae",
    "phaethontidae", "phoenicopteridae", "laridae", "stercorariidae", "alcidae",
}
HABITAT_CODES = ["F", "BM", "WD", "SH", "SV", "G", "PL", "R", "D", "A", "RV", "C", "W", "SE", "O"]
WATER = {"RV", "C", "W", "SE"}


def fetch():
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / "BIRDBASE_v2025.1.xlsx"
    raw = dest.read_bytes() if dest.exists() else b""
    if hashlib.md5(raw).hexdigest() != MD5 or len(raw) != SIZE:
        req = urllib.request.Request(URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read()
        dest.write_bytes(raw)
    got = hashlib.md5(raw).hexdigest()
    if got != MD5 or len(raw) != SIZE:
        raise RuntimeError(f"checksum mismatch md5 {got} size {len(raw)}")
    return {
        "name": "BIRDBASE v2025.1 Sekercioglu et al. Final.xlsx",
        "download_url": URL,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "md5": got,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def read_data_sheet(path):
    with zipfile.ZipFile(path) as zf:
        shared = []
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            shared.append("".join((t.text or "") for t in si.iter(f"{NS}t")))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        target = None
        for sh in wb.findall(f"{NS}sheets/{NS}sheet"):
            if sh.attrib["name"] == "Data":
                target = rid[sh.attrib[REL]]
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        root = ET.fromstring(zf.read(target))
        table = []
        for row in root.findall(f".//{NS}sheetData/{NS}row"):
            vals = {}
            for cell in row.findall(f"{NS}c"):
                ref = cell.attrib.get("r", "")
                col = "".join(ch for ch in ref if ch.isalpha())
                n = 0
                for ch in col:
                    n = n * 26 + ord(ch.upper()) - 64
                if n < 1 or n > 120:
                    continue
                kind = cell.attrib.get("t")
                v = cell.find(f"{NS}v")
                if kind == "s" and v is not None and v.text:
                    val = shared[int(v.text)]
                elif v is not None and v.text:
                    val = v.text
                else:
                    val = ""
                vals[n - 1] = val
            if vals:
                width = max(vals) + 1
                table.append([vals.get(i, "") for i in range(width)])
    return table


def family_match(text):
    v = text.strip().lower()
    if not v:
        return False
    for fam in FAMILIES:
        if v == fam or v.startswith(fam + " ") or v.startswith(fam + "("):
            return True
    return False


def positive(text):
    s = str(text).strip()
    if not s:
        return False
    try:
        return float(s) > 0
    except ValueError:
        return False


def settle_caveats(existing, additions):
    stale = (
        "has not been downloaded",
        "have not been re-hashed",
        "No maturity value has been read",
        "No Camelus number has been read",
        "No age has been read",
        "No species habitat value has been read",
        "No body mass or litter size has been read",
        "No brain or body mass value has been read",
    )
    kept = []
    for item in list(existing) + list(additions):
        if any(mark in item for mark in stale):
            continue
        if item not in kept:
            kept.append(item)
    return kept


def main():
    meta = fetch()
    table = read_data_sheet(DATA / "BIRDBASE_v2025.1.xlsx")
    header_i = None
    for i, row in enumerate(table[:8]):
        if any(cell.strip().startswith("Family") for cell in row):
            header_i = i
            break
    if header_i is None:
        write_stop("inconclusive", "data-unavailable", meta, "no family header row")
        return
    header = table[header_i]
    family_idx = [i for i, h in enumerate(header) if h.strip().lower().startswith("family")]
    habitat_idx = {}
    for code in HABITAT_CODES:
        for i, h in enumerate(header):
            if h.strip() == code:
                habitat_idx[code] = i
                break
    if not family_idx or len(habitat_idx) < len(HABITAT_CODES):
        write_stop(
            "inconclusive",
            "data-unavailable",
            meta,
            f"family columns {len(family_idx)}, habitat columns {sorted(habitat_idx)}",
        )
        return
    latin_i = next((i for i, h in enumerate(header) if h.strip().lower().startswith("latin")), None)
    deviations = [
        "Habitat codes are separate columns (F, BM, WD, SH, SV, G, PL, R, D, A, RV, C, W, SE, O) holding a numeric preference rank, not tokens packed into one cell. A species uses a habitat when that column is a positive number. The water set remains {W, RV, C, SE}. The header row is the second row of the Data sheet; the first row is a group label. Thresholds are unchanged."
    ]
    coded = []
    by_family = {}
    for row in table[header_i + 1:]:
        matched = []
        for i in family_idx:
            if i < len(row) and family_match(row[i]):
                matched.append(row[i].strip())
        if not matched:
            continue
        used = [code for code, i in habitat_idx.items() if i < len(row) and positive(row[i])]
        if not used:
            continue
        water = [code for code in used if code in WATER]
        name = row[latin_i].strip() if latin_i is not None and latin_i < len(row) else ""
        rec = {"name": name, "families": matched, "habitats": used, "water": water, "exception": not water}
        coded.append(rec)
        seen = set()
        for fam in matched:
            if fam in seen:
                continue
            seen.add(fam)
            by_family.setdefault(fam, {"n": 0, "exceptions": 0})
            by_family[fam]["n"] += 1
            if rec["exception"]:
                by_family[fam]["exceptions"] += 1
    n = len(coded)
    n_ex = sum(1 for r in coded if r["exception"])
    rate = (n_ex / n) if n else None
    if n < 200:
        verdict, reason = "inconclusive", "underpowered" if n else "other"
    elif n_ex == 0:
        verdict, reason = "supports", None
    elif rate >= 0.05:
        verdict, reason = "refutes", None
    else:
        verdict, reason = "mixed", None
    if verdict == "refutes" and rate is not None and rate >= 0.15:
        confidence = 0.85
    elif verdict == "refutes":
        confidence = 0.75
    elif verdict == "supports":
        confidence = 0.7
    elif verdict == "mixed":
        confidence = 0.65
    else:
        confidence = 0.45
    primary_water = 0
    primary_known = 0
    name_to_primary = {}
    for row in table[header_i + 1:]:
        if not any(i < len(row) and family_match(row[i]) for i in family_idx):
            continue
        used = [code for code, i in habitat_idx.items() if i < len(row) and positive(row[i])]
        if not used:
            continue
        rank1 = [code for code, i in habitat_idx.items() if i < len(row) and str(row[i]).strip() in {"1", "1.0"}]
        if not rank1:
            continue
        primary_known += 1
        if any(code in WATER for code in rank1):
            primary_water += 1
    exceptions = [{"name": r["name"], "families": r["families"], "habitats": r["habitats"]} for r in coded if r["exception"]]
    # cap the stored exception list so derived stays small
    measured = {
        "value": rate,
        "unit": "share of web-footed species with no wetland, river, coast, or open-sea habitat",
        "n": n,
        "uncertainty": None,
        "extra": {
            "n_exceptions": n_ex,
            "primary_rank1_n": primary_known,
            "primary_rank1_water_n": primary_water,
            "primary_rank1_water_share": (primary_water / primary_known) if primary_known else None,
            "by_family": by_family,
            "exception_examples": exceptions[:30],
            "n_exception_examples_truncated": max(0, len(exceptions) - 30),
        },
    }
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["datasets"] = [{
        "id": "birdbase-2025-figshare-27051040",
        "name": "BIRDBASE: avian biogeography, conservation, ecology and life history traits",
        "landing_url": "https://doi.org/10.6084/m9.figshare.27051040.v1",
        "doi": "10.6084/m9.figshare.27051040.v1",
        "version": "v2025.1",
        "license": "CC BY 4.0",
        "files": [meta],
        "role": "habitat ranks and family names for bird species",
    }]
    result["method"] = (
        "Downloaded the BIRDBASE workbook, checked MD5 and byte size, and read the Data sheet. "
        "A species entered the web-footed set when any of the four family columns matched the pre-registered list. "
        "It uses a habitat when that habitat column is a positive rank. "
        "An exception has at least one habitat rank and none of RV, C, W, or SE. "
        "The share whose rank-1 habitat is a water code is descriptive and does not set the verdict."
    )
    result["measured"] = measured
    result["verdict"] = verdict
    result["data_kind"] = "biological" if n else "none"
    result["confidence"] = confidence
    result["deviations"] = deviations
    if reason:
        result["reason"] = reason
    result["results_summary"] = [
        f"Web-footed species with a habitat rank: n={n}. Exceptions with no water habitat: {n_ex}. Rate: {rate}.",
        f"Among species with a rank of 1, {primary_water} of {primary_known} have a water code as that primary rank (descriptive).",
    ]
    result["caveats"] = settle_caveats(result.get("caveats", []), [
        "A positive rank means the compilers recorded that habitat, not that a GPS fix fell within a set distance of water.",
        "Semipalmate families and Anhimidae and Anseranatidae stay outside the set, as registered, so they cannot create exceptions.",
    ])
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.mkdir(exist_ok=True)
    # drop the long by_family only if the file would be large; it is small
    (DERIVED / "measured.json").write_text(json.dumps({"verdict": verdict, "reason": reason, "measured": measured}, indent=2) + "\n")
    print(verdict, reason, "n", n, "exceptions", n_ex, "rate", rate)


def write_stop(verdict, reason, meta, note):
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["verdict"] = verdict
    result["reason"] = reason
    result["data_kind"] = "none"
    result["confidence"] = 0.4
    result["method"] = note
    result["results_summary"] = [note]
    result["datasets"] = [{
        "id": "birdbase-2025-figshare-27051040",
        "name": "BIRDBASE",
        "landing_url": "https://doi.org/10.6084/m9.figshare.27051040.v1",
        "doi": "10.6084/m9.figshare.27051040.v1",
        "version": "v2025.1",
        "license": "CC BY 4.0",
        "files": [meta],
        "role": "habitat and family",
    }]
    result["measured"] = {"value": None, "unit": "exception rate", "n": 0, "uncertainty": note, "extra": {}}
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, reason, note)


if __name__ == "__main__":
    main()
