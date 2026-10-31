#!/usr/bin/env python3
"""Test of darwin1859-ch12-10: although terrestrial mammals are absent from oceanic
islands, "bats occur on almost every island" and remote islands often have their own
endemic bat species.

Units and distances are the 43 far units (> 300 statute miles from any landmass
>= 100,000 km2) of darwin1859-ch12-09, read from ../darwin1859-ch12-09/derived/units.json.
For each unit GBIF is queried for (a) the number of bird records (survey-effort proxy),
(b) Chiroptera occurrences faceted by species; each bat species' global record count
gives the fraction inside the unit, hence endemism (>= 10 records, >= 95 % inside).

Re-run:  python3 analysis.py   (a few hundred GBIF API calls, no files > 1 MB)
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)
CH1209_UNITS = os.path.join(HERE, "..", "darwin1859-ch12-09", "derived", "units.json")

GBIF_OCC = "https://api.gbif.org/v1/occurrence/search"
GBIF_SP = "https://api.gbif.org/v1/species/"
CHIROPTERA_ORDER_KEY = 734
AVES_CLASS_KEY = 212
BASIS = ["HUMAN_OBSERVATION", "PRESERVED_SPECIMEN", "MATERIAL_SAMPLE", "OCCURRENCE",
         "MACHINE_OBSERVATION", "MATERIAL_CITATION"]
MIN_BIRD_RECORDS = 500
MIN_RECORDS_PRESENT = 5
MIN_RECORDS_ENDEMIC = 10
ENDEMIC_FRACTION = 0.95
SUPPORT_OCC, SUPPORT_END = 0.80, 0.33
REFUTE_OCC, REFUTE_END = 0.50, 0.10

REQUESTS = []


def record(label, r):
    REQUESTS.append({"label": label, "download_url": r.url,
                     "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()})


def get(url, params=None, label=""):
    for attempt in range(6):
        try:
            r = requests.get(url, params=params, timeout=120)
            if r.status_code == 200:
                record(label, r)
                return r
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed: {url}")


def occ(params, label):
    p = [("basisOfRecord", b) for b in BASIS] + list(params.items())
    return get(GBIF_OCC, p, label).json()


def main():
    units = json.load(open(CH1209_UNITS))
    taxon_cache, global_cache = {}, {}
    results = {}
    for name in sorted(units):
        u = units[name]
        flt = u["filter"]
        georef = "geometry" in flt
        extra = {"hasGeospatialIssue": "false"} if georef else {}
        birds = occ({"classKey": AVES_CLASS_KEY, "limit": 0, **extra, **flt}, f"aves-count:{name}")["count"]
        d = occ({"orderKey": CHIROPTERA_ORDER_KEY, "limit": 0, "facet": "speciesKey", "facetLimit": 500, **extra, **flt}, f"unit-facet:{name}")
        species = []
        for f in (d["facets"][0]["counts"] if d.get("facets") else []):
            key = int(f["name"])
            in_unit = int(f["count"])
            if key not in taxon_cache:
                t = get(GBIF_SP + str(key), label=f"species-taxonomy:{key}").json()
                taxon_cache[key] = {"name": t.get("canonicalName") or t.get("scientificName"), "family": t.get("family")}
            ck = (key, georef)
            if ck not in global_cache:
                gextra = {"hasCoordinate": "true", "hasGeospatialIssue": "false"} if georef else {}
                global_cache[ck] = occ({"speciesKey": key, "limit": 0, **gextra}, f"species-global:{key}:{'georef' if georef else 'all'}")["count"]
            glob = global_cache[ck]
            frac = in_unit / glob if glob else 0.0
            species.append({"speciesKey": key, "species": taxon_cache[key]["name"], "family": taxon_cache[key]["family"],
                            "records_in_unit": in_unit, "records_global": glob, "fraction_in_unit": round(frac, 4),
                            "endemic": bool(glob >= MIN_RECORDS_ENDEMIC and frac >= ENDEMIC_FRACTION)})
        species.sort(key=lambda s: -s["records_in_unit"])
        endemics = [s["species"] for s in species if s["endemic"]]
        present = any(s["records_in_unit"] >= MIN_RECORDS_PRESENT for s in species)
        results[name] = {"distance_km": u["distance_km"], "filter": flt, "bird_records": birds, "surveyed": birds >= MIN_BIRD_RECORDS,
                         "bat_records": d["count"], "n_bat_species_recorded": len(species), "has_bats": present,
                         "has_bats_any_record": len(species) > 0, "n_endemic_bat_species": len(endemics), "endemic_bat_species": endemics,
                         "n_endemic_nonvolant_mammals_ch12_09": u["n_endemic_species"], "species": species}
        print(f"{name:42s} birds={birds:7d} bats={d['count']:6d} spp={len(species):2d} present={present!s:5s} endemic={endemics}", file=sys.stderr)

    surveyed = {n: r for n, r in results.items() if r["surveyed"]}
    with_bats = {n: r for n, r in surveyed.items() if r["has_bats"]}
    with_endemic = {n: r for n, r in with_bats.items() if r["n_endemic_bat_species"] > 0}
    f_occ = len(with_bats) / len(surveyed) if surveyed else 0.0
    f_end = len(with_endemic) / len(with_bats) if with_bats else 0.0
    if f_occ >= SUPPORT_OCC and f_end >= SUPPORT_END:
        verdict = "supports"
    elif f_occ < REFUTE_OCC or f_end < REFUTE_END:
        verdict = "refutes"
    else:
        verdict = "mixed"

    all_with_bats_any = [n for n, r in results.items() if r["has_bats_any_record"]]
    # Sensitivity (not part of the verdict): looser endemism cut-off of >= 80 % of records inside the
    # unit, because island endemics often have a few museum records lacking a country code.
    relaxed = {n: [s["species"] for s in r["species"] if s["records_global"] >= MIN_RECORDS_ENDEMIC and s["fraction_in_unit"] >= 0.80]
               for n, r in results.items()}
    relaxed = {n: v for n, v in relaxed.items() if v}
    n_relaxed_with_bats = sum(1 for n in with_bats if n in relaxed)
    measured = {
        "value": round(f_occ, 4),
        "unit": "fraction of surveyed far island units (>= 500 GBIF bird records) with a bat species having >= 5 GBIF records",
        "n": len(surveyed),
        "uncertainty": "GBIF snapshot counts; endemism rule >= 10 records and >= 95 % inside unit; units are archipelago-level",
        "extra": {
            "n_far_units": len(results),
            "n_surveyed_units": len(surveyed),
            "n_surveyed_with_bats": len(with_bats),
            "n_surveyed_with_bats_with_endemic_bat": len(with_endemic),
            "fraction_bat_units_with_endemic_bat": round(f_end, 4),
            "surveyed_units_without_bats": {n: {"bird_records": r["bird_records"], "bat_records": r["bat_records"], "species": [(s["species"], s["records_in_unit"]) for s in r["species"]]} for n, r in surveyed.items() if not r["has_bats"]},
            "unsurveyed_units": {n: {"bird_records": r["bird_records"], "has_bats": r["has_bats"]} for n, r in results.items() if not r["surveyed"]},
            "endemic_bats_by_unit": {n: r["endemic_bat_species"] for n, r in results.items() if r["n_endemic_bat_species"] > 0},
            "total_endemic_bat_species": sum(r["n_endemic_bat_species"] for r in results.values()),
            "sensitivity_endemic_80pct": {"endemic_bats_by_unit": relaxed, "n_surveyed_bat_units_with_endemic": n_relaxed_with_bats,
                                          "fraction_bat_units_with_endemic_bat": round(n_relaxed_with_bats / len(with_bats), 4) if with_bats else None,
                                          "total_endemic_bat_species": sum(len(v) for v in relaxed.values())},
            "sensitivity_any_record": {"n_far_units_with_any_bat_record": len(all_with_bats_any), "fraction_of_all_far_units": round(len(all_with_bats_any) / len(results), 4)},
            "contrast_nonvolant_mammals": {
                "far_units_with_endemic_bat": sum(1 for r in results.values() if r["n_endemic_bat_species"] > 0),
                "far_units_with_endemic_nonvolant_mammal_ch12_09": sum(1 for r in results.values() if r["n_endemic_nonvolant_mammals_ch12_09"] > 0),
                "n_far_units": len(results)},
            "verdict_by_rule": verdict,
        },
    }
    json.dump(results, open(os.path.join(DERIVED, "units.json"), "w"), indent=1)
    basis_qs = "&".join(f"basisOfRecord={b}" for b in BASIS)
    compact = [{**q, "download_url": q["download_url"].replace(basis_qs + "&", "").replace("&" + basis_qs, "")} for q in REQUESTS]
    json.dump({"note": f"GBIF occurrence URLs below omit the constant query string '{basis_qs}' that every call carried",
               "requests": compact}, open(os.path.join(DERIVED, "requests.json"), "w"), indent=1)
    files = {q["label"]: {k: v for k, v in q.items() if k != "label"} for q in REQUESTS if q["label"].startswith(("unit-facet:", "aves-count:"))}
    json.dump({"measured": measured, "files": files}, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
