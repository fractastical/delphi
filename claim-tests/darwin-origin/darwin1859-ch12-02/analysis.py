#!/usr/bin/env python3
"""Test of darwin1859-ch12-02: "the same species [of fish] never occur in the fresh
waters of distant continents".

Data: FishBase (version 24.07) species, country and countref tables, distributed as
CSV by the rfishbase project on Hugging Face. Strictly fresh-water, non-diadromous
species are intersected with their native/endemic country records; countries are
mapped to continents with FishBase's own Continent field; species native on both
sides of an ocean-separated continent pair are counted.

Re-run:  python3 analysis.py   (downloads ~58 MB into ./data/, writes ./derived/)
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from itertools import combinations

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

BASE = "https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/fb/v24.07/csv/"
FILES = {"species": "species.csv", "country": "country.csv", "countref": "countref.csv"}

NATIVE_STATUS = {"native", "endemic"}
DIADROMOUS = {"anadromous", "catadromous", "amphidromous", "oceanodromous", "oceano-estuarine"}

# Landmasses as Darwin would count "distant continents": Europe and Asia are one
# landmass; North and South America are joined by Panama; Africa touches Asia at Sinai.
LANDMASS = {"Europe": "Eurasia", "Asia": "Eurasia", "Africa": "Africa",
            "North America": "North America", "South America": "South America",
            "Oceania": "Oceania"}
LAND_JOINED = {frozenset({"Eurasia", "Africa"}), frozenset({"North America", "South America"})}
OCEAN_PAIRS = [frozenset(p) for p in combinations(sorted(set(LANDMASS.values())), 2)
               if frozenset(p) not in LAND_JOINED]

ROBUST_MIN_COUNTRIES = 2
REFUTE_MIN_ROBUST = 5


def fetch(key):
    url = BASE + FILES[key]
    path = os.path.join(DATA, FILES[key])
    r = requests.get(url, timeout=300, stream=True)
    r.raise_for_status()
    h = hashlib.sha256()
    n = 0
    with open(path, "wb") as fh:
        for chunk in r.iter_content(1 << 20):
            fh.write(chunk)
            h.update(chunk)
            n += len(chunk)
    rec = {"download_url": url,
           "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "byte_size": n, "sha256": h.hexdigest()}
    print(f"fetched {FILES[key]}: {n} bytes sha256={rec['sha256'][:12]}...", file=sys.stderr)
    return path, rec


def main():
    paths, files = {}, {}
    for k in FILES:
        paths[k], files[k] = fetch(k)

    sp = pd.read_csv(paths["species"], usecols=["SpecCode", "Genus", "Species", "Fresh", "Brack", "Saltwater", "AnaCat"], low_memory=False)
    co = pd.read_csv(paths["country"], usecols=["SpecCode", "C_Code", "Status"], low_memory=False)
    cr = pd.read_csv(paths["countref"], usecols=["C_Code", "PAESE", "Continent"], low_memory=False)

    # FishBase stores boolean flags as -1/1 (Access) or 0/1; treat any non-zero as true.
    for col in ("Fresh", "Brack", "Saltwater"):
        sp[col] = pd.to_numeric(sp[col], errors="coerce").fillna(0).astype(int) != 0
    anacat = sp["AnaCat"].fillna("").str.strip().str.lower()
    strictly_fw = sp[sp["Fresh"] & ~sp["Brack"] & ~sp["Saltwater"] & ~anacat.isin(DIADROMOUS)].copy()
    strictly_fw["name"] = strictly_fw["Genus"] + " " + strictly_fw["Species"]

    co["Status"] = co["Status"].fillna("").str.strip().str.lower()
    nat = co[co["Status"].isin(NATIVE_STATUS)].merge(cr, on="C_Code", how="left")
    nat = nat[nat["Continent"].isin(LANDMASS)].copy()
    nat["landmass"] = nat["Continent"].map(LANDMASS)
    nat = nat[nat["SpecCode"].isin(strictly_fw["SpecCode"])]
    nat = nat.drop_duplicates(["SpecCode", "C_Code"])

    # per species: countries per landmass and per continent
    per_lm = nat.groupby(["SpecCode", "landmass"])["C_Code"].nunique().unstack(fill_value=0)
    per_ct = nat.groupby(["SpecCode", "Continent"])["C_Code"].nunique().unstack(fill_value=0)
    names = strictly_fw.set_index("SpecCode")["name"]
    countries = nat.groupby(["SpecCode", "landmass"])["PAESE"].apply(lambda s: sorted(set(s)))

    rows = []
    for spec, row in per_lm.iterrows():
        present = {lm for lm, n in row.items() if n > 0}
        for pair in OCEAN_PAIRS:
            a, b = sorted(pair)
            if a in present and b in present:
                rows.append({
                    "SpecCode": int(spec), "species": names.get(spec),
                    "pair": f"{a} | {b}",
                    "n_countries_a": int(row[a]), "n_countries_b": int(row[b]),
                    "countries_a": countries.get((spec, a), []), "countries_b": countries.get((spec, b), []),
                    "robust": bool(row[a] >= ROBUST_MIN_COUNTRIES and row[b] >= ROBUST_MIN_COUNTRIES),
                })
    shared = pd.DataFrame(rows)
    n_species_any = int(shared["SpecCode"].nunique()) if len(shared) else 0
    n_species_robust = int(shared.loc[shared["robust"], "SpecCode"].nunique()) if len(shared) else 0

    # sensitivity: any two of FishBase's six continents (incl. Europe|Asia etc.)
    multi_ct = per_ct[(per_ct > 0).sum(axis=1) >= 2]
    n_multi_continent = int(len(multi_ct))

    n_fw = int(len(strictly_fw))
    n_fw_with_native = int(per_lm.shape[0])
    verdict = "supports" if n_species_any == 0 else ("refutes" if n_species_robust >= REFUTE_MIN_ROBUST else "mixed")

    by_pair = shared.groupby("pair")["SpecCode"].nunique().to_dict() if len(shared) else {}
    by_pair_robust = shared[shared["robust"]].groupby("pair")["SpecCode"].nunique().to_dict() if len(shared) else {}

    robust_list = (shared[shared["robust"]].sort_values(["pair", "species"])
                   [["species", "pair", "n_countries_a", "n_countries_b", "countries_a", "countries_b"]].to_dict("records"))

    # ---- Post-hoc checks (NOT pre-registered; added after inspecting the output) ----
    # (a) FishBase files Indonesia under Asia although its Papua provinces are on New
    #     Guinea, so Indonesia-only "Eurasian" records paired with Papua New Guinea /
    #     Australia are the same landmass (Sahul), not an ocean crossing. Recount the
    #     Eurasia|Oceania pair ignoring Indonesia and Timor-Leste on the Asian side.
    sahul_asia = {"Indonesia", "Timor-Leste"}
    eo = shared[shared["pair"] == "Eurasia | Oceania"].copy()
    eo["asia_ex_sahul"] = eo["countries_a"].apply(lambda l: [c for c in l if c not in sahul_asia])
    eo_clean = eo[eo["asia_ex_sahul"].str.len() > 0]
    eo_clean_robust = eo_clean[(eo_clean["asia_ex_sahul"].str.len() >= ROBUST_MIN_COUNTRIES) & (eo_clean["n_countries_b"] >= ROBUST_MIN_COUNTRIES)]
    # (b) Eurasia|North America with brackish-tolerant (but still non-diadromous,
    #     non-marine) species admitted: the classic Holarctic fresh-water fishes
    #     (pike, burbot, longnose sucker) are Brack = 1 in FishBase.
    fw_brack = sp[sp["Fresh"] & ~sp["Saltwater"] & ~anacat.isin(DIADROMOUS)]
    nat2 = co[co["Status"].isin(NATIVE_STATUS)].merge(cr, on="C_Code", how="left")
    nat2 = nat2[nat2["Continent"].isin(LANDMASS) & nat2["SpecCode"].isin(fw_brack["SpecCode"])].copy()
    nat2["landmass"] = nat2["Continent"].map(LANDMASS)
    per_lm2 = nat2.drop_duplicates(["SpecCode", "C_Code"]).groupby(["SpecCode", "landmass"])["C_Code"].nunique().unstack(fill_value=0)
    names2 = (fw_brack["Genus"] + " " + fw_brack["Species"]).set_axis(fw_brack["SpecCode"])
    if "Eurasia" in per_lm2 and "North America" in per_lm2:
        ena = per_lm2[(per_lm2["Eurasia"] > 0) & (per_lm2["North America"] > 0)]
        holarctic_brack = sorted(names2.get(i) for i in ena.index)
    else:
        holarctic_brack = []
    post_hoc = {
        "note": "post-hoc, not pre-registered",
        "eurasia_oceania_species_any_after_removing_sahul_side_of_indonesia": int(eo_clean["SpecCode"].nunique()),
        "eurasia_oceania_species_robust_after_removing_sahul_side_of_indonesia": sorted(eo_clean_robust["species"].tolist()),
        "robust_species_after_removing_sahul_artefact": sorted(set(shared.loc[shared["robust"] & (shared["pair"] != "Eurasia | Oceania"), "species"]) | set(eo_clean_robust["species"])),
        "eurasia_north_america_species_any_strict_filter": sorted(shared.loc[shared["pair"] == "Eurasia | North America", "species"].tolist()),
        "eurasia_north_america_species_if_brackish_tolerant_admitted": holarctic_brack,
        "n_eurasia_north_america_species_if_brackish_tolerant_admitted": len(holarctic_brack),
    }

    measured = {
        "value": n_species_robust,
        "unit": "strictly fresh-water, non-diadromous fish species native (>= 2 countries each side) on both sides of an ocean-separated continent pair",
        "n": n_fw_with_native,
        "uncertainty": "exact count from FishBase 24.07 status fields; FishBase status errors can move single species in or out",
        "extra": {
            "species_shared_any_country_count": n_species_any,
            "strictly_freshwater_species_total": n_fw,
            "strictly_freshwater_species_with_native_country_records": n_fw_with_native,
            "share_of_species_shared_robust": round(n_species_robust / n_fw_with_native, 5) if n_fw_with_native else None,
            "share_of_species_shared_any": round(n_species_any / n_fw_with_native, 5) if n_fw_with_native else None,
            "by_ocean_pair_any": by_pair,
            "by_ocean_pair_robust": by_pair_robust,
            "sensitivity_species_native_on_two_or_more_of_six_continents": n_multi_continent,
            "robust_species": robust_list,
            "verdict_by_rule": verdict,
            "post_hoc": post_hoc,
        },
    }
    shared.to_csv(os.path.join(DERIVED, "shared_species.csv"), index=False)
    json.dump({"measured": measured, "files": files}, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
