#!/usr/bin/env python3
"""Test of darwin1859-ch12-08: Batrachians (frogs, toads, newts) "have never been
found on any of the many islands with which the great oceans are studded".

For each pre-registered oceanic island unit we list every amphibian species with
GBIF occurrence records in the unit, then test whether any of those species is
endemic to the unit (>= 10 occurrence records worldwide, >= 95 % inside the unit).
An endemic amphibian cannot be a human introduction, so it proves a native
amphibian fauna. Units are ISO 3166 territory codes or WGS84 bounding boxes.

Re-run:  python3 analysis.py   (a few hundred small GBIF API calls; writes ./derived/)
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

API = "https://api.gbif.org/v1/occurrence/search"
AMPHIBIA_CLASS_KEY = 131
BASIS = ["HUMAN_OBSERVATION", "PRESERVED_SPECIMEN", "MATERIAL_SAMPLE", "OCCURRENCE",
         "MACHINE_OBSERVATION", "MATERIAL_CITATION"]  # excludes fossils and captive/zoo specimens
MIN_RECORDS = 10
ENDEMIC_FRACTION = 0.95

# Pre-registered oceanic units (see result.json). Country units use GBIF `country`;
# box units use a counter-clockwise WKT polygon (min_lon, min_lat, max_lon, max_lat).
UNITS = {
    "Fiji": {"country": "FJ"},
    "Samoa": {"country": "WS"},
    "American Samoa": {"country": "AS"},
    "Tonga": {"country": "TO"},
    "Palau": {"country": "PW"},
    "Micronesia (Federated States)": {"country": "FM"},
    "Marshall Islands": {"country": "MH"},
    "Northern Mariana Islands": {"country": "MP"},
    "Guam": {"country": "GU"},
    "French Polynesia": {"country": "PF"},
    "Cook Islands": {"country": "CK"},
    "Vanuatu": {"country": "VU"},
    "Niue": {"country": "NU"},
    "Tuvalu": {"country": "TV"},
    "Kiribati": {"country": "KI"},
    "Nauru": {"country": "NR"},
    "Wallis and Futuna": {"country": "WF"},
    "Tokelau": {"country": "TK"},
    "Pitcairn": {"country": "PN"},
    "Norfolk Island": {"country": "NF"},
    "Bermuda": {"country": "BM"},
    "St Helena, Ascension and Tristan da Cunha": {"country": "SH"},
    "Iceland": {"country": "IS"},
    "Sao Tome and Principe": {"country": "ST"},
    "Cape Verde": {"country": "CV"},
    "Comoros": {"country": "KM"},
    "Mayotte": {"country": "YT"},
    "Mauritius": {"country": "MU"},
    "Reunion": {"country": "RE"},
    "Christmas Island": {"country": "CX"},
    "Cocos (Keeling) Islands": {"country": "CC"},
    "Hawaii": {"box": (-161.0, 18.5, -154.5, 22.5)},
    "Galapagos": {"box": (-92.2, -1.6, -89.0, 1.8)},
    "Canary Islands": {"box": (-18.3, 27.5, -13.3, 29.5)},
    "Azores": {"box": (-31.5, 36.8, -24.8, 39.9)},
    "Madeira": {"box": (-17.4, 32.3, -16.2, 33.2)},
    "Juan Fernandez": {"box": (-81.0, -34.0, -78.5, -33.4)},
    "Fernando de Noronha": {"box": (-32.6, -3.95, -32.3, -3.75)},
    "Ogasawara (Bonin)": {"box": (141.8, 26.4, 142.4, 27.8)},
    "Easter Island": {"box": (-109.6, -27.3, -109.1, -27.0)},
    "Lord Howe Island": {"box": (159.0, -31.65, 159.2, -31.45)},
}

REQUESTS = []


def box_wkt(b):
    x0, y0, x1, y1 = b
    return f"POLYGON(({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))"


def gbif(params, label):
    """GET with retries; records url, time, size and sha256 of the response."""
    p = [("basisOfRecord", b) for b in BASIS] + list(params.items())
    for attempt in range(6):
        try:
            r = requests.get(API, params=p, timeout=90)
            if r.status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    r.raise_for_status()
    REQUESTS.append({
        "label": label,
        "download_url": r.url,
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(r.content),
        "sha256": hashlib.sha256(r.content).hexdigest(),
    })
    return r.json()


def unit_params(spec):
    if "country" in spec:
        return {"country": spec["country"]}
    return {"geometry": box_wkt(spec["box"])}


def main():
    results = {}
    species_cache = {}
    for name, spec in UNITS.items():
        params = {"classKey": AMPHIBIA_CLASS_KEY, "limit": 0, "facet": "speciesKey",
                  "facetLimit": 500, **unit_params(spec)}
        d = gbif(params, f"unit-facet:{name}")
        total = d["count"]
        facets = d["facets"][0]["counts"] if d.get("facets") else []
        species = []
        for f in facets:
            key = int(f["name"])
            in_unit = int(f["count"])
            if key not in species_cache:
                g = gbif({"speciesKey": key, "limit": 1}, f"species-global:{key}")
                sci = g["results"][0].get("species") or g["results"][0].get("scientificName") if g["results"] else str(key)
                species_cache[key] = {"global": g["count"], "name": sci}
            glob = species_cache[key]["global"]
            frac = in_unit / glob if glob else 0.0
            species.append({
                "speciesKey": key,
                "species": species_cache[key]["name"],
                "records_in_unit": in_unit,
                "records_global": glob,
                "fraction_in_unit": round(frac, 4),
                "endemic": bool(glob >= MIN_RECORDS and frac >= ENDEMIC_FRACTION),
            })
        species.sort(key=lambda s: -s["records_in_unit"])
        endemics = [s for s in species if s["endemic"]]
        results[name] = {
            "filter": unit_params(spec),
            "amphibian_records": total,
            "n_species_recorded": len(species),
            "n_endemic_species": len(endemics),
            "endemic_species": [s["species"] for s in endemics],
            "species": species,
        }
        print(f"{name:42s} records={total:6d} species={len(species):3d} endemic={len(endemics)} {[s['species'] for s in endemics]}", file=sys.stderr)

    units_with_endemics = [u for u, r in results.items() if r["n_endemic_species"] > 0]
    units_with_any = [u for u, r in results.items() if r["n_species_recorded"] > 0]
    n_units = len(results)
    n_end = len(units_with_endemics)
    verdict = "supports" if n_end == 0 else ("mixed" if n_end == 1 else "refutes")

    measured = {
        "value": n_end,
        "unit": "oceanic island units with >= 1 endemic (hence native) amphibian species",
        "n": n_units,
        "uncertainty": f"endemism rule: >= {MIN_RECORDS} records worldwide and >= {int(ENDEMIC_FRACTION*100)} % inside the unit; counts are GBIF snapshot values at retrieval time",
        "extra": {
            "units_with_native_amphibians": {u: results[u]["endemic_species"] for u in units_with_endemics},
            "fraction_of_units_with_native_amphibians": round(n_end / n_units, 3),
            "units_with_any_amphibian_records": len(units_with_any),
            "units_with_no_amphibian_records": sorted(set(results) - set(units_with_any)),
            "total_endemic_amphibian_species": sum(r["n_endemic_species"] for r in results.values()),
            "verdict_by_rule": verdict,
        },
    }
    json.dump(results, open(os.path.join(DERIVED, "units.json"), "w"), indent=1)
    json.dump(REQUESTS, open(os.path.join(DERIVED, "gbif-requests.json"), "w"), indent=1)
    files = {r["label"]: {k: v for k, v in r.items() if k != "label"} for r in REQUESTS if r["label"].startswith("unit-facet:")}
    json.dump({"measured": measured, "files": files}, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
