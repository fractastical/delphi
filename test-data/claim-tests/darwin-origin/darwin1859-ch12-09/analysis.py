#!/usr/bin/env python3
"""Test of darwin1859-ch12-09: no "terrestrial mammal (excluding domesticated animals
kept by the natives) inhabiting an island situated above 300 miles from a continent
or great continental island".

1. Natural Earth 1:50m land polygons: landmasses with area >= 100,000 km2 are the
   "continents or great continental islands". Each pre-registered island unit gets
   the great-circle distance from its representative point(s) to the nearest such
   landmass (polygon containing the point excluded).
2. For units farther than 300 statute miles (482.8 km), GBIF mammal occurrences are
   faceted by species; bats, cetaceans, sirenians, pinnipeds and humans are removed
   via the GBIF species API; a species is endemic (hence native) if it has >= 10
   records worldwide and >= 95 % of them inside the unit.

Re-run:  python3 analysis.py   (downloads ~1.6 MB into ./data/, several hundred GBIF calls)
"""
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_land.geojson"
GBIF_OCC = "https://api.gbif.org/v1/occurrence/search"
GBIF_SP = "https://api.gbif.org/v1/species/"
MAMMALIA_CLASS_KEY = 359
BASIS = ["HUMAN_OBSERVATION", "PRESERVED_SPECIMEN", "MATERIAL_SAMPLE", "OCCURRENCE",
         "MACHINE_OBSERVATION", "MATERIAL_CITATION"]
THRESHOLD_KM = 300 * 1.609344
GREAT_LAND_KM2 = 100_000
MIN_RECORDS = 10
ENDEMIC_FRACTION = 0.95
EARTH_R = 6371.0088

EXCLUDED_ORDERS = {"Chiroptera", "Cetacea", "Sirenia"}
EXCLUDED_FAMILIES = {"Otariidae", "Phocidae", "Odobenidae", "Delphinidae", "Balaenopteridae",
                     "Physeteridae", "Ziphiidae", "Kogiidae", "Phocoenidae", "Balaenidae",
                     "Eschrichtiidae", "Neobalaenidae", "Iniidae", "Platanistidae",
                     "Pontoporiidae", "Lipotidae", "Monodontidae", "Hominidae"}

# name: (gbif filter, [(lon, lat), ...])
UNITS = {
    "Galapagos": ({"box": (-92.2, -1.6, -89.0, 1.8)}, [(-90.5, -0.6)]),
    "Hawaii": ({"box": (-161.0, 18.5, -154.5, 22.5)}, [(-157.0, 21.0)]),
    "Bermuda": ({"country": "BM"}, [(-64.75, 32.3)]),
    "Azores": ({"box": (-31.5, 36.8, -24.8, 39.9)}, [(-25.7, 37.75)]),
    "Madeira": ({"box": (-17.4, 32.3, -16.2, 33.2)}, [(-16.9, 32.75)]),
    "Canary Islands": ({"box": (-18.3, 27.5, -13.3, 29.5)}, [(-15.5, 28.3)]),
    "Cape Verde": ({"country": "CV"}, [(-23.6, 15.1)]),
    "Sao Tome and Principe": ({"country": "ST"}, [(6.6, 0.25)]),
    "St Helena, Ascension and Tristan da Cunha": ({"country": "SH"}, [(-5.7, -15.95), (-14.36, -7.95), (-12.3, -37.1)]),
    "Fernando de Noronha": ({"box": (-32.6, -3.95, -32.3, -3.75)}, [(-32.42, -3.85)]),
    "Falkland Islands": ({"country": "FK"}, [(-59.0, -51.7)]),
    "South Georgia": ({"country": "GS"}, [(-36.5, -54.3)]),
    "Juan Fernandez": ({"box": (-81.0, -34.0, -78.5, -33.4)}, [(-78.85, -33.65)]),
    "Easter Island": ({"box": (-109.6, -27.3, -109.1, -27.0)}, [(-109.35, -27.1)]),
    "Pitcairn": ({"country": "PN"}, [(-130.1, -25.07)]),
    "French Polynesia": ({"country": "PF"}, [(-149.4, -17.6), (-139.5, -9.5)]),
    "Cook Islands": ({"country": "CK"}, [(-159.8, -21.2)]),
    "Niue": ({"country": "NU"}, [(-169.9, -19.05)]),
    "Tonga": ({"country": "TO"}, [(-175.2, -21.2)]),
    "Samoa": ({"country": "WS"}, [(-172.1, -13.6)]),
    "American Samoa": ({"country": "AS"}, [(-170.7, -14.3)]),
    "Wallis and Futuna": ({"country": "WF"}, [(-176.2, -13.3)]),
    "Tokelau": ({"country": "TK"}, [(-171.8, -9.2)]),
    "Tuvalu": ({"country": "TV"}, [(179.2, -8.5)]),
    "Fiji": ({"country": "FJ"}, [(178.0, -17.8)]),
    "Kiribati": ({"country": "KI"}, [(173.0, 1.4)]),
    "Nauru": ({"country": "NR"}, [(166.93, -0.53)]),
    "Marshall Islands": ({"country": "MH"}, [(171.2, 7.1)]),
    "Micronesia (Federated States)": ({"country": "FM"}, [(158.2, 6.9)]),
    "Palau": ({"country": "PW"}, [(134.5, 7.5)]),
    "Northern Mariana Islands": ({"country": "MP"}, [(145.75, 15.2)]),
    "Guam": ({"country": "GU"}, [(144.8, 13.45)]),
    "Ogasawara (Bonin)": ({"box": (141.8, 26.4, 142.4, 27.8)}, [(142.2, 27.1)]),
    "Vanuatu": ({"country": "VU"}, [(167.2, -15.9)]),
    "Solomon Islands": ({"country": "SB"}, [(160.0, -9.5)]),
    "New Caledonia": ({"country": "NC"}, [(165.5, -21.3)]),
    "Norfolk Island": ({"country": "NF"}, [(167.95, -29.03)]),
    "Lord Howe Island": ({"box": (159.0, -31.65, 159.2, -31.45)}, [(159.08, -31.55)]),
    "Christmas Island": ({"country": "CX"}, [(105.65, -10.5)]),
    "Cocos (Keeling) Islands": ({"country": "CC"}, [(96.85, -12.15)]),
    "Andaman and Nicobar": ({"box": (92.0, 6.5, 94.2, 13.8)}, [(92.8, 12.0)]),
    "Maldives": ({"country": "MV"}, [(73.5, 3.2)]),
    "Chagos": ({"country": "IO"}, [(72.4, -7.3)]),
    "Seychelles": ({"country": "SC"}, [(55.5, -4.6)]),
    "Mauritius": ({"country": "MU"}, [(57.55, -20.3)]),
    "Reunion": ({"country": "RE"}, [(55.5, -21.1)]),
    "Comoros": ({"country": "KM"}, [(43.8, -12.0)]),
    "Mayotte": ({"country": "YT"}, [(45.15, -12.8)]),
    "Socotra": ({"box": (53.2, 12.2, 54.6, 12.8)}, [(54.0, 12.5)]),
    "Kerguelen / French Southern Territories": ({"country": "TF"}, [(69.3, -49.3)]),
    "Iceland": ({"country": "IS"}, [(-18.5, 65.0)]),
    "Faroe Islands": ({"country": "FO"}, [(-6.9, 62.0)]),
}

REQUESTS = []


def record(label, r):
    REQUESTS.append({"label": label, "download_url": r.url,
                     "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()})
    return REQUESTS[-1]


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


# ---------- geometry ----------
def ring_area_km2(coords):
    """Spherical polygon area (km2) for a lon/lat ring (Chamberlain & Duquette)."""
    lon = np.radians(np.array([c[0] for c in coords]))
    lat = np.radians(np.array([c[1] for c in coords]))
    lon2 = np.roll(lon, -1)
    lat2 = np.roll(lat, -1)
    s = np.sum((lon2 - lon) * (2 + np.sin(lat) + np.sin(lat2)))
    return abs(s) * EARTH_R ** 2 / 2


def densify(coords, step_deg=0.1):
    out = []
    for (x0, y0), (x1, y1) in zip(coords, coords[1:]):
        n = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) / step_deg))
        for i in range(n):
            t = i / n
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    out.append(coords[-1])
    return out


def haversine_km(lon, lat, lons, lats):
    p1, p2 = math.radians(lat), np.radians(lats)
    dphi = p2 - p1
    dl = np.radians(lons) - math.radians(lon)
    a = np.sin(dphi / 2) ** 2 + math.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


def point_in_ring(lon, lat, ring):
    inside = False
    n = len(ring)
    for i in range(n - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        if (y0 > lat) != (y1 > lat):
            xint = x0 + (lat - y0) * (x1 - x0) / (y1 - y0)
            if lon < xint:
                inside = not inside
    return inside


def load_landmasses(path):
    gj = json.load(open(path))
    masses = []
    for feat in gj["features"]:
        g = feat["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            outer = poly[0]
            area = ring_area_km2(outer)
            if area >= GREAT_LAND_KM2:
                dense = densify(outer)
                masses.append({"area_km2": area, "ring": outer,
                               "lons": np.array([c[0] for c in dense]), "lats": np.array([c[1] for c in dense])})
    return masses


def nearest_great_land_km(lon, lat, masses):
    best = float("inf")
    for m in masses:
        if point_in_ring(lon, lat, m["ring"]):
            continue
        d = float(haversine_km(lon, lat, m["lons"], m["lats"]).min())
        best = min(best, d)
    return best


# ---------- GBIF ----------
def box_wkt(b):
    x0, y0, x1, y1 = b
    return f"POLYGON(({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))"


def occ(params, label):
    p = [("basisOfRecord", b) for b in BASIS] + list(params.items())
    return get(GBIF_OCC, p, label).json()


def unit_filter(spec):
    return {"country": spec["country"]} if "country" in spec else {"geometry": box_wkt(spec["box"])}


def main():
    r = get(NE_URL, label="natural-earth-50m-land")
    ne_path = os.path.join(DATA, "ne_50m_land.geojson")
    open(ne_path, "wb").write(r.content)
    masses = load_landmasses(ne_path)
    print(f"{len(masses)} landmasses >= {GREAT_LAND_KM2} km2", file=sys.stderr)

    distances = {}
    for name, (spec, pts) in UNITS.items():
        distances[name] = round(max(nearest_great_land_km(lon, lat, masses) for lon, lat in pts), 1)
    far = {n: d for n, d in distances.items() if d > THRESHOLD_KM}
    near = {n: d for n, d in distances.items() if d <= THRESHOLD_KM}
    print(f"far units ({len(far)}): {sorted(far)}", file=sys.stderr)

    taxon_cache = {}
    species_cache = {}
    results = {}
    for name in sorted(far):
        spec, _ = UNITS[name]
        extra = {"hasGeospatialIssue": "false"} if "box" in spec else {}
        d = occ({"classKey": MAMMALIA_CLASS_KEY, "limit": 0, "facet": "speciesKey", "facetLimit": 1000, **extra, **unit_filter(spec)}, f"unit-facet:{name}")
        species = []
        for f in (d["facets"][0]["counts"] if d.get("facets") else []):
            key = int(f["name"])
            in_unit = int(f["count"])
            if key not in taxon_cache:
                t = get(GBIF_SP + str(key), label=f"species-taxonomy:{key}").json()
                taxon_cache[key] = {"name": t.get("canonicalName") or t.get("scientificName"),
                                    "order": t.get("order"), "family": t.get("family")}
            tx = taxon_cache[key]
            if tx["order"] in EXCLUDED_ORDERS or tx["family"] in EXCLUDED_FAMILIES:
                continue
            # Box units only see georeferenced records, so their denominator must be
            # georeferenced records too; country units see all records with a country code.
            georef = "box" in spec
            ck = (key, georef)
            if ck not in species_cache:
                extra = {"hasCoordinate": "true", "hasGeospatialIssue": "false"} if georef else {}
                g = occ({"speciesKey": key, "limit": 0, **extra}, f"species-global:{key}:{'georef' if georef else 'all'}")
                species_cache[ck] = g["count"]
            glob = species_cache[ck]
            frac = in_unit / glob if glob else 0.0
            species.append({"speciesKey": key, "species": tx["name"], "order": tx["order"], "family": tx["family"],
                            "records_in_unit": in_unit, "records_global": glob, "fraction_in_unit": round(frac, 4),
                            "endemic": bool(glob >= MIN_RECORDS and frac >= ENDEMIC_FRACTION)})
        species.sort(key=lambda s: -s["records_in_unit"])
        endemics = [s for s in species if s["endemic"]]
        results[name] = {"distance_km": distances[name], "filter": unit_filter(spec), "n_terrestrial_species_recorded": len(species),
                         "n_endemic_species": len(endemics), "endemic_species": [s["species"] for s in endemics], "species": species}
        print(f"{name:42s} {distances[name]:7.1f} km  species={len(species):3d} endemic={len(endemics)} {[s['species'] for s in endemics]}", file=sys.stderr)

    units_with = {n: r_["endemic_species"] for n, r_ in results.items() if r_["n_endemic_species"] > 0}
    n_units_with = len(units_with)
    max_per_unit = max([r_["n_endemic_species"] for r_ in results.values()] + [0])
    if n_units_with == 0:
        verdict = "supports"
    elif n_units_with >= 2 or max_per_unit >= 2:
        verdict = "refutes"
    else:
        verdict = "mixed"

    measured = {
        "value": n_units_with,
        "unit": "island units > 300 miles from a continent or great island with >= 1 endemic non-volant terrestrial mammal species",
        "n": len(far),
        "uncertainty": "distances from 1:50m coastlines and a representative point per unit (tens of km); endemism rule >= 10 records, >= 95 % inside unit; GBIF snapshot counts",
        "extra": {
            "threshold_km": round(THRESHOLD_KM, 1),
            "great_landmass_min_area_km2": GREAT_LAND_KM2,
            "n_great_landmasses": len(masses),
            "units_with_native_terrestrial_mammals": units_with,
            "fraction_of_far_units_with_native_terrestrial_mammals": round(n_units_with / len(far), 3) if far else None,
            "total_endemic_species": sum(r_["n_endemic_species"] for r_ in results.values()),
            "far_unit_distances_km": far,
            "near_units_excluded_km": near,
            "verdict_by_rule": verdict,
        },
    }
    json.dump(results, open(os.path.join(DERIVED, "units.json"), "w"), indent=1)
    # compact log of every API call: the constant basisOfRecord query string is factored out
    basis_qs = "&".join(f"basisOfRecord={b}" for b in BASIS)
    compact = [{**q, "download_url": q["download_url"].replace(basis_qs + "&", "").replace("&" + basis_qs, "")} for q in REQUESTS]
    json.dump({"note": f"GBIF occurrence URLs below omit the constant query string '{basis_qs}' that every call carried",
               "requests": compact}, open(os.path.join(DERIVED, "requests.json"), "w"), indent=1)
    files = {q["label"]: {k: v for k, v in q.items() if k != "label"} for q in REQUESTS
             if q["label"] == "natural-earth-50m-land" or q["label"].startswith("unit-facet:")}
    json.dump({"measured": measured, "files": files}, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
