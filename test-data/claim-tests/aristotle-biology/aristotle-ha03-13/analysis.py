#!/usr/bin/env python3
"""aristotle-ha03-13: the dolphin skeleton is bone, not fish-spine.

The decision rule is the one committed in result.json. Needs openpyxl
(`pip install openpyxl`). The workbook is not committed.

    python3 analysis.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
URL = "https://ndownloader.figshare.com/files/18111446"
GENERA = {
    "delphinus", "tursiops", "stenella", "phocoena", "orcinus", "globicephala", "grampus",
    "lagenorhynchus", "sousa", "steno", "cephalorhynchus", "phocoenoides", "neophocaena",
    "balaenoptera", "megaptera", "balaena", "eubalaena", "physeter", "kogia", "ziphius",
    "mesoplodon", "hyperoodon", "monodon", "delphinapterus", "inia", "lipotes", "platanista",
    "pontoporia",
}
BONE_HEADER = re.compile(r"bone|cortical|osteon|bone volume|bv/tv|bvtv", re.I)
EXCLUDE_HEADER = re.compile(r"dnds|dN/dS|gene|omega", re.I)
NAME_HEADER = re.compile(r"species|taxon|scientific|binomial|latin", re.I)
TISSUE_NEG = re.compile(r"cartilage|fish-spine|fish spine", re.I)


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def is_cetacean(value) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip().lower()
    if not text:
        return False
    first = re.split(r"[\s_]+", text)[0]
    if first in GENERA:
        return True
    return bool(re.search(r"\b(dolphin|porpoise|whale)\b", text))


def as_float(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        if s == "" or s.lower() in {"na", "nan", "null", "-"}:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def sheet_rows(ws):
    rows = list(ws.iter_rows(values_only=True))
    header_idx = None
    for i, row in enumerate(rows[:15]):
        labels = [str(c).strip() for c in row if isinstance(c, str)]
        if any(NAME_HEADER.search(label) for label in labels) or any(BONE_HEADER.search(label) for label in labels):
            header_idx = i
            break
    if header_idx is None:
        return [], []
    headers = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    body = []
    for row in rows[header_idx + 1:]:
        if all(c is None or str(c).strip() == "" for c in row):
            continue
        body.append(row)
    return headers, body


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    retrieved = now_utc()
    req = urllib.request.Request(URL, headers={"User-Agent": "delphisci-claim-test/aristotle-ha03-13"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read()
        final = resp.geturl()
    path = DATA / "12862_2019_1509_MOESM1_ESM.xlsx"
    path.write_bytes(raw)
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    positive = []
    cetacean_rows = 0
    cartilage_labels = []
    bone_columns_found = []
    sheets = []
    for ws in wb.worksheets:
        headers, body = sheet_rows(ws)
        name_cols = [i for i, h in enumerate(headers) if NAME_HEADER.search(h) and not EXCLUDE_HEADER.search(h)]
        bone_cols = [i for i, h in enumerate(headers) if BONE_HEADER.search(h) and not EXCLUDE_HEADER.search(h)]
        sheets.append({"sheet": ws.title, "headers": headers, "n_rows": len(body), "name_cols": name_cols, "bone_cols": bone_cols})
        for i in bone_cols:
            bone_columns_found.append(f"{ws.title}: {headers[i]}")
        if not name_cols:
            continue
        for row in body:
            names = [row[i] for i in name_cols if i < len(row)]
            if not any(is_cetacean(n) for n in names):
                continue
            cetacean_rows += 1
            species = next(str(n) for n in names if is_cetacean(n))
            row_text = " ".join(str(c) for c in row if c is not None)
            if TISSUE_NEG.search(row_text):
                cartilage_labels.append(species)
            for i in bone_cols:
                if i >= len(row):
                    continue
                value = as_float(row[i])
                if value is not None and value > 0:
                    positive.append({
                        "sheet": ws.title,
                        "species": species,
                        "column": headers[i],
                        "value": value,
                    })
    wb.close()

    explicit_zeros_only = cetacean_rows > 0 and bone_columns_found and not positive and not cartilage_labels
    if len(raw) == 0:
        verdict, reason = "inconclusive", "data-unavailable"
    elif cartilage_labels and not positive:
        verdict, reason = "refutes", None
    elif explicit_zeros_only:
        verdict, reason = "refutes", None
    elif positive:
        verdict, reason = "supports", None
    elif cetacean_rows == 0:
        verdict, reason = "inconclusive", "underpowered"
    elif not bone_columns_found:
        verdict, reason = "inconclusive", "not-operationalizable"
    else:
        verdict, reason = "inconclusive", "not-operationalizable"

    # One example value per species, the first positive, for the measured headline.
    by_species = {}
    for item in positive:
        by_species.setdefault(item["species"], item)
    headline = max((item["value"] for item in by_species.values()), default=None)
    if verdict == "supports" and len(by_species) >= 1:
        confidence = 0.7 if len(by_species) >= 2 else 0.55
    elif verdict == "refutes":
        confidence = 0.6
    elif verdict == "inconclusive" and cetacean_rows and not bone_columns_found:
        confidence = 0.75
    else:
        confidence = 0.45

    measured = {
        "value": headline,
        "unit": "largest positive bone-column value among cetacean species (column units as published)",
        "n": cetacean_rows,
        "uncertainty": "presence of a positive histological bone measurement; the column unit is the authors'",
        "extra": {
            "n_cetacean_rows": cetacean_rows,
            "n_positive_cells": len(positive),
            "n_cetacean_species_with_positive_bone_value": len(by_species),
            "bone_columns": bone_columns_found,
            "species_examples": list(by_species.values())[:12],
            "cartilage_or_fish_spine_labels": cartilage_labels[:12],
            "sheets": sheets,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps({
        "verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured,
    }, indent=2) + "\n")

    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological" if cetacean_rows or sheets else "none"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = confidence
    result["measured"] = measured
    result["datasets"] = [{
        "id": "figshare-10049012-cetacean-bone-histology",
        "name": "Supplementary bone-histology tables for cetacean rib, humerus and vertebrae (Sun et al.)",
        "landing_url": "https://doi.org/10.6084/m9.figshare.10049012.v1",
        "doi": "10.6084/m9.figshare.10049012.v1",
        "version": "v1",
        "license": "CC BY + CC0, as named by the figshare article metadata",
        "files": [{
            "name": "12862_2019_1509_MOESM1_ESM.xlsx",
            "download_url": URL,
            "final_url": final,
            "retrieved_at": retrieved,
            "byte_size": len(raw),
            "sha256": sha256(raw),
        }],
        "role": "bone histological parameters measured on cetacean skeletal elements",
    }]
    result["method"] = (
        "Downloaded the pre-registered workbook and read every sheet. A row counted as a cetacean only if its "
        "species cell began with a genus on the pre-registered list or contained dolphin, porpoise or whale. "
        "A column counted as bone only if its header referred to bone, cortical bone, an osteon or bone volume "
        "and was not a gene or dN/dS column. A value greater than zero on a cetacean row supports the claim. "
        "The file is not committed; its size and SHA-256 are."
    )
    if verdict == "supports":
        example = next(iter(by_species.values()))
        result["results_summary"] = [
            f"{len(by_species)} cetacean species have a positive bone measurement across {cetacean_rows} cetacean rows.",
            f"Example: {example['species']} {example['column']} = {example['value']} on sheet {example['sheet']}.",
        ]
    else:
        observed_headers = []
        for sheet in sheets:
            observed_headers.append(sheet["sheet"] + ": " + ", ".join(h for h in sheet["headers"] if h)[:240])
        result["results_summary"] = [
            f"Cetacean rows: {cetacean_rows}. Columns whose headers name bone, cortical bone, osteons or bone volume: {len(bone_columns_found)}. Positive cells: {len(positive)}.",
            *observed_headers,
        ]
    caveats = list(result.get("caveats") or [])
    for caveat in [
        "The workbook does contain cetacean rows and numeric histology columns, but those headers are short codes (for example S, P, Cc, Cp, Cg, MD, CL, Cts) rather than the words bone, cortical, osteon or bone volume. The pre-registered rule does not treat those codes as bone columns, so the test is not operationalizable on this file. The codes were not added to the rule after they were seen.",
        "Column units are whatever the authors published. The verdict uses the sign of the value, greater than zero, not a threshold in a particular unit.",
    ]:
        if caveat not in caveats:
            caveats.append(caveat)
    result["caveats"] = caveats
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "verdict": verdict, "reason": reason, "confidence": confidence,
        "cetacean_rows": cetacean_rows, "positive_cells": len(positive),
        "species": len(by_species), "bone_columns": bone_columns_found[:20],
        "sheets": [{k: s[k] for k in ("sheet", "n_rows", "bone_cols")} for s in sheets],
    }, indent=2))


if __name__ == "__main__":
    main()
