#!/usr/bin/env python3
"""Test aristotle-ga03-26 for Anguilla anguilla against FishBase and GBIF.

Re-run from this directory: python3 analysis.py
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

BASE = "https://data.source.coop/cboettig/fishbase/fb/v24.07/parquet/"
PARENTAL = re.compile(r"\beggs?\b|spawn|fertiliz|ovipar|dioec|leptocephal|\blarva\b|\bsargasso\b", re.I)
SPONTANEOUS = re.compile(r"spontaneous|without parent|asexual|parthenogen", re.I)
WKT = "POLYGON((-80 20,-40 20,-40 35,-80 35,-80 20))"
CARD_URLS = ["https://source.coop/cboettig/fishbase", "https://source.coop/repositories/cboettig/fishbase"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def fetch(url, params=None):
    r = requests.get(url, params=params, timeout=180, headers={"User-Agent": "DelphiClaimTest/1.0"})
    r.raise_for_status()
    return r


def fishbase_license():
    for url in CARD_URLS:
        try:
            page = fetch(url)
        except requests.RequestException:
            continue
        text = page.content.decode("utf-8", "replace")
        m = re.search(r"CC[- ]BY[- ]NC(?:[- ]\d(?:\.\d)?)?", text, re.I)
        if m:
            return m.group(0), page.url
    return "not stated on the source.coop card retrieved with this run", CARD_URLS[0]


def inside(lat, lon):
    return lat is not None and lon is not None and 20 <= float(lat) <= 35 and -80 <= float(lon) <= -40


def gbif_count(taxon_key):
    url = "https://api.gbif.org/v1/occurrence/search"
    params = {"taxonKey": taxon_key, "geometry": WKT, "hasCoordinate": "true", "limit": 20}
    r = fetch(url, params)
    payload = r.json()
    recs = payload.get("results") or []
    first_ok = all(inside(rec.get("decimalLatitude"), rec.get("decimalLongitude")) for rec in recs) if recs else True
    count = payload.get("count")
    method = "api_count"
    if recs and not first_ok:
        method = "paged"
        count = 0
        offset = 0
        while True:
            page = fetch(url, {"taxonKey": taxon_key, "geometry": WKT, "hasCoordinate": "true", "limit": 300, "offset": offset}).json()
            batch = page.get("results") or []
            count += sum(1 for rec in batch if inside(rec.get("decimalLatitude"), rec.get("decimalLongitude")))
            offset += len(batch)
            if not batch or page.get("endOfRecords", True) or offset >= page.get("count", 0):
                break
    return {
        "count": count,
        "method": method,
        "first_page_inside_box": first_ok,
        "n_first_page": len(recs),
        "response_sha256": sha256(r.content),
        "response_bytes": len(r.content),
        "retrieved_at": now(),
        "download_url": r.url,
    }


def main():
    fb_license, fb_card = fishbase_license()
    files = []
    frames = {}
    for name in ("species.parquet", "reproduc.parquet"):
        r = fetch(BASE + name)
        path = os.path.join(DATA, name)
        open(path, "wb").write(r.content)
        frames[name] = pd.read_parquet(path)
        files.append({
            "download_url": BASE + name,
            "retrieved_at": now(),
            "byte_size": len(r.content),
            "sha256": sha256(r.content),
            "content_type": r.headers.get("content-type", ""),
        })
    species = frames["species.parquet"]
    reproduc = frames["reproduc.parquet"]
    hit = species[(species["Genus"].astype(str) == "Anguilla") & (species["Species"].astype(str) == "anguilla")]
    reason = None
    if hit.empty:
        verdict, reason = "inconclusive", "data-unavailable"
        measured_extra = {"species_found": False}
        gbif = None
    else:
        code = int(hit.iloc[0]["SpecCode"])
        rows = reproduc[pd.to_numeric(reproduc["SpecCode"], errors="coerce") == code]
        text = " ".join(" ".join(rows[c].dropna().astype(str)) for c in rows.columns)
        parental = bool(PARENTAL.search(text))
        spontaneous = bool(SPONTANEOUS.search(text))
        try:
            match = fetch("https://api.gbif.org/v1/species/match", {"name": "Anguilla anguilla"}).json()
            key = match.get("usageKey")
            gbif = gbif_count(key) if key else None
            if gbif is None:
                raise RuntimeError("no usageKey")
            gbif["usageKey"] = key
            gbif["match_scientificName"] = match.get("scientificName")
            gbif["match_status"] = match.get("matchType")
        except Exception as exc:
            gbif = None
            match_error = str(exc)
        else:
            match_error = None
        count = None if gbif is None else gbif["count"]
        if gbif is None:
            verdict, reason = "inconclusive", "data-unavailable"
        elif spontaneous and not parental and count == 0:
            verdict = "supports"
        elif parental and count is not None and count >= 10:
            verdict = "refutes"
        elif parental and count is not None and count < 10:
            verdict = "mixed"
        elif spontaneous and count is not None and count >= 10:
            verdict = "mixed"
        else:
            verdict, reason = "inconclusive", "other"
        measured_extra = {
            "spec_code": code,
            "n_reproduction_rows": int(len(rows)),
            "parental_pattern": parental,
            "spontaneous_pattern": spontaneous,
            "reproduction_text": text[:2000],
            "gbif": gbif,
            "gbif_error": match_error,
            "verdict_by_rule": verdict,
        }

    measured = {
        "value": None if not measured_extra.get("gbif") else measured_extra["gbif"]["count"],
        "unit": "GBIF occurrences of Anguilla anguilla inside latitude 20-35 and longitude -80 to -40",
        "n": measured_extra.get("n_reproduction_rows", 0),
        "uncertainty": "FishBase text match is a pattern on the concatenated reproduction row; the box is the pre-registered rectangle",
        "extra": measured_extra,
    }
    result = json.load(open(os.path.join(HERE, "result.json")))
    result["status"] = "complete"
    result["data_kind"] = "none" if reason == "data-unavailable" else "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    result["confidence"] = 0.9 if verdict == "refutes" else 0.55
    result["datasets"] = [
        {
            "id": "fishbase-v24.07-anguilla-reproduc",
            "name": "FishBase v24.07 species and reproduc tables",
            "landing_url": fb_card,
            "doi": None,
            "version": "fb/v24.07",
            "license": fb_license,
            "files": files,
            "role": "binomial Anguilla anguilla and its reproduction fields",
        },
        {
            "id": "gbif-anguilla-anguilla-sargasso",
            "name": "GBIF occurrence search for Anguilla anguilla in the pre-registered Sargasso box",
            "landing_url": "https://api.gbif.org/v1/occurrence/search",
            "doi": None,
            "version": "GBIF occurrence API",
            "license": "not included in the occurrence search response",
            "files": [] if not measured_extra.get("gbif") else [{
                "download_url": measured_extra["gbif"]["download_url"],
                "retrieved_at": measured_extra["gbif"]["retrieved_at"],
                "byte_size": measured_extra["gbif"]["response_bytes"],
                "sha256": measured_extra["gbif"]["response_sha256"],
            }],
            "role": "georeferenced occurrences inside the box",
        },
    ]
    result["method"] = (
        "Anguilla anguilla was joined from the species table to reproduc on SpecCode. "
        "The concatenated row was tested for the parental pattern (egg, spawn, fertiliz, ovipar, dioec, leptocephal, larva, Sargasso) "
        "and the spontaneous pattern (spontaneous, without parent, asexual, parthenogen). "
        "GBIF species/match supplied the usage key. The occurrence count is the API count when the first 20 records all fall inside the box; otherwise the script pages and counts."
    )
    result["measured"] = measured
    result["caveats"] = [
        "The unnamed mullet and the other river fishes in the claim are not in the verdict.",
        "The Sargasso box is the pre-registered rectangle, latitude 20 to 35 and longitude -80 to -40, not the whole ocean.",
        "A parental pattern on a FishBase text field is a description of reproduction, not a count of eels watched spawning.",
    ]
    with open(os.path.join(HERE, "result.json"), "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps({"verdict": verdict, "reason": reason, "parental": measured_extra.get("parental_pattern"), "spontaneous": measured_extra.get("spontaneous_pattern"), "gbif": None if not measured_extra.get("gbif") else measured_extra["gbif"]["count"]}, indent=2))


if __name__ == "__main__":
    main()
