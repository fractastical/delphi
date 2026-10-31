#!/usr/bin/env python3
"""Test of darwin1859-ch11-16: "very many European productions cover the ground in La
Plata, and in a lesser degree in Australia ... whereas extremely few southern forms
have become naturalised in any part of Europe".

Data: World Checklist of Vascular Plants (WCVP) distribution table, which codes each
species' presence in TDWG level-3 units as native or introduced. For each pair
(Europe <-> La Plata, Europe <-> Australia) the number of species native to one side
(and not the other) that are recorded as introduced on the other side is counted.

Re-run:  python3 analysis.py   (downloads the 88 MB WCVP zip into ./data/ if absent)
"""
import hashlib
import io
import json
import os
import sys
import zipfile
from datetime import datetime, timezone

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

WCVP_URL = "https://sftp.kew.org/pub/data-repositories/WCVP/wcvp.zip"
EUROPE_L1 = "1"
LA_PLATA = {"AGE", "URU"}
LA_PLATA_WIDE = {"AGE", "AGW", "AGS", "URU", "PAR"}
AUSTRALIA_L2 = "50"
SUPPORT_RATIO, REFUTE_RATIO = 5.0, 2.0


def fetch(url, name):
    path = os.path.join(DATA, name)
    if not (os.path.exists(path) and os.path.getsize(path) > 0):
        r = requests.get(url, timeout=900, stream=True)
        r.raise_for_status()
        with open(path, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    data = open(path, "rb").read()
    rec = {"download_url": url, "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    print(f"{name}: {rec['byte_size']} bytes sha256={rec['sha256'][:12]}...", file=sys.stderr)
    return path, rec


def main():
    zpath, rec = fetch(WCVP_URL, "wcvp.zip")
    with zipfile.ZipFile(zpath) as z:
        names = pd.read_csv(io.BytesIO(z.read("wcvp_names.csv")), sep="|", usecols=["plant_name_id", "taxon_rank", "taxon_status", "taxon_name"], dtype=str)
        dist = pd.read_csv(io.BytesIO(z.read("wcvp_distribution.csv")), sep="|",
                           usecols=["plant_name_id", "continent_code_l1", "region_code_l2", "area_code_l3", "introduced", "extinct", "location_doubtful"], dtype=str)
    acc = names[(names["taxon_rank"] == "Species") & (names["taxon_status"] == "Accepted")]
    name_of = acc.set_index("plant_name_id")["taxon_name"]
    dist = dist[dist["plant_name_id"].isin(set(acc["plant_name_id"])) & (dist["location_doubtful"] == "0") & (dist["extinct"] == "0")]
    dist["region"] = None
    dist.loc[dist["continent_code_l1"] == EUROPE_L1, "region"] = "Europe"
    dist.loc[dist["area_code_l3"].isin(LA_PLATA), "region"] = "La Plata"
    dist.loc[dist["region_code_l2"] == AUSTRALIA_L2, "region"] = "Australia"
    wide = dist.copy()
    wide.loc[wide["area_code_l3"].isin(LA_PLATA_WIDE), "region"] = "La Plata (wide)"

    def sets(d):
        nat = {r: set(g.loc[g["introduced"] == "0", "plant_name_id"]) for r, g in d.dropna(subset=["region"]).groupby("region")}
        intro = {r: set(g.loc[g["introduced"] == "1", "plant_name_id"]) for r, g in d.dropna(subset=["region"]).groupby("region")}
        return nat, intro

    nat, intro = sets(dist)
    natw, introw = sets(wide)

    def exchange(nat, intro, south):
        a = (nat["Europe"] - nat[south]) & intro[south]          # European natives naturalised in the south
        b = (nat[south] - nat["Europe"]) & intro["Europe"]       # southern natives naturalised in Europe
        return a, b

    out = {}
    lists = {}
    for south, (n_, i_) in {"La Plata": (nat, intro), "Australia": (nat, intro), "La Plata (wide)": (natw, introw)}.items():
        a, b = exchange(n_, i_, south)
        out[south] = {"europe_to_south": len(a), "south_to_europe": len(b),
                      "ratio": round(len(a) / len(b), 3) if b else None,
                      "europe_native_pool": len(n_["Europe"]), "south_native_pool": len(n_[south]),
                      "europe_to_south_per_1000_source_species": round(1000 * len(a) / len(n_["Europe"]), 2),
                      "south_to_europe_per_1000_source_species": round(1000 * len(b) / len(n_[south]), 2)}
        lists[south] = {"europe_to_south": sorted(name_of.get(i) for i in a), "south_to_europe": sorted(name_of.get(i) for i in b)}

    # Sensitivity (not part of the pre-registered rule): restrict each source pool to species whose
    # entire native range lies within the source continent (TDWG level 1: Europe=1, South America=8,
    # Australasia=5), so that pantropical weeds native to La Plata but introduced to Europe from
    # elsewhere do not inflate the south-to-Europe count (and vice versa for Eurasian species).
    native_rows = dist[dist["introduced"] == "0"]
    l1_sets = native_rows.groupby("plant_name_id")["continent_code_l1"].agg(lambda s: set(s))
    confined = {c: set(l1_sets[l1_sets.apply(lambda s, c=c: s == {c})].index) for c in ("1", "8", "5")}
    strict = {}
    for south, cont in (("La Plata", "8"), ("Australia", "5")):
        a = (nat["Europe"] & confined["1"]) & intro[south]
        b = (nat[south] & confined[cont]) & intro["Europe"]
        strict[south] = {"europe_to_south": len(a), "south_to_europe": len(b), "ratio": round(len(a) / len(b), 3) if b else None,
                         "europe_confined_pool": len(nat["Europe"] & confined["1"]), "south_confined_pool": len(nat[south] & confined[cont])}
        lists[south + " (continent-confined natives)"] = {"europe_to_south": sorted(name_of.get(i) for i in a), "south_to_europe": sorted(name_of.get(i) for i in b)}

    lp, au = out["La Plata"], out["Australia"]
    r_lp = lp["europe_to_south"] / max(lp["south_to_europe"], 1)
    r_au = au["europe_to_south"] / max(au["south_to_europe"], 1)
    if r_lp >= SUPPORT_RATIO and r_au >= SUPPORT_RATIO:
        verdict = "supports"
    elif r_lp < REFUTE_RATIO or r_au < REFUTE_RATIO:
        verdict = "refutes"
    else:
        verdict = "mixed"

    measured = {
        "value": round(r_lp, 3),
        "unit": "ratio of European plant species naturalised in La Plata to La Plata species naturalised in Europe (WCVP)",
        "n": lp["europe_to_south"] + lp["south_to_europe"],
        "uncertainty": "exact counts from WCVP status flags; depends on completeness of introduced-status coding",
        "extra": {
            "la_plata": lp, "australia": au, "la_plata_wide_sensitivity": out["La Plata (wide)"],
            "ratio_australia": round(r_au, 3),
            "continent_confined_natives_sensitivity": strict,
            "secondary_clause_la_plata_more_than_australia": bool(lp["europe_to_south"] > au["europe_to_south"]),
            "southern_species_naturalised_in_europe_examples": {"La Plata": lists["La Plata"]["south_to_europe"][:40], "Australia": lists["Australia"]["south_to_europe"][:40]},
            "european_species_naturalised_in_la_plata_examples": lists["La Plata"]["europe_to_south"][:40],
            "verdict_by_rule": verdict,
        },
    }
    json.dump(lists, open(os.path.join(DERIVED, "species_lists.json"), "w"), indent=1, ensure_ascii=False)
    json.dump({"measured": measured, "files": {"wcvp.zip": rec}}, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2, ensure_ascii=False)
    print(json.dumps(measured, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
