#!/usr/bin/env python3
"""Test darwin1859-ch12-05: oceanic islands have few species but a very high proportion of endemics.

Data: Kew WCVP (names + distributions) and TDWG WGSRPD level-3 GeoJSON (areas).
Usage: python3 analysis.py [--write-result]
"""
import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

WCVP_URL = "https://sftp.kew.org/pub/data-repositories/WCVP/wcvp.zip"
L3_URL = "https://raw.githubusercontent.com/tdwg/wgsrpd/master/geojson/level3.geojson"
MIN_NATIVE = 20
R_EARTH_KM = 6371.0088


def fetch(url, name):
    path = os.path.join(DATA, name)
    meta = path + ".meta"
    if not (os.path.exists(path) and os.path.exists(meta)):
        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        open(meta, "w").write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return path, {"download_url": url, "retrieved_at": open(meta).read().strip(),
                  "byte_size": os.path.getsize(path), "sha256": h.hexdigest()}


def spherical_ring_area_km2(ring):
    """Area of a lon/lat ring on the sphere (signed, via the spherical excess of lune strips)."""
    lon = np.deg2rad(np.asarray(ring, dtype=float)[:, 0])
    lat = np.deg2rad(np.asarray(ring, dtype=float)[:, 1])
    if lon[0] != lon[-1] or lat[0] != lat[-1]:
        lon = np.append(lon, lon[0]); lat = np.append(lat, lat[0])
    dlon = np.diff(lon)
    dlon = (dlon + np.pi) % (2 * np.pi) - np.pi
    area = np.sum(dlon * (2 + np.sin(lat[:-1]) + np.sin(lat[1:])) / 2)
    return abs(area) * R_EARTH_KM ** 2


def polygon_area(geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    total = 0.0
    for poly in polys:
        total += spherical_ring_area_km2(poly[0])
        for hole in poly[1:]:
            total -= spherical_ring_area_km2(hole)
    return total


def main():
    write_result = "--write-result" in sys.argv
    zpath, wcvp_info = fetch(WCVP_URL, "wcvp.zip")
    with zipfile.ZipFile(zpath) as z:
        z.extractall(DATA)
    l3path, l3_info = fetch(L3_URL, "level3.geojson")
    gj = json.load(open(l3path))
    areas = pd.DataFrame([{"area_code_l3": f["properties"]["LEVEL3_COD"], "l3_name": f["properties"]["LEVEL3_NAM"],
                           "area_km2": polygon_area(f["geometry"])} for f in gj["features"]]).set_index("area_code_l3")

    names = pd.read_csv(os.path.join(DATA, "wcvp_names.csv"), sep="|", quoting=3, dtype=str,
                        usecols=["plant_name_id", "taxon_rank", "taxon_status", "genus_hybrid", "species_hybrid"])
    sp = names[(names.taxon_rank == "Species") & (names.taxon_status == "Accepted") & names.genus_hybrid.isna() & names.species_hybrid.isna()]
    spid = set(sp.plant_name_id)
    dist = pd.read_csv(os.path.join(DATA, "wcvp_distribution.csv"), sep="|", quoting=3, dtype=str,
                       usecols=["plant_name_id", "area_code_l3", "introduced", "location_doubtful"])
    dist = dist[(dist.location_doubtful == "0") & (dist.introduced == "0") & dist.plant_name_id.isin(spid)]
    dist = dist[["plant_name_id", "area_code_l3"]].drop_duplicates()
    n_areas_per_species = dist.groupby("plant_name_id").area_code_l3.nunique()
    dist["single_area"] = dist.plant_name_id.map(n_areas_per_species) == 1
    per_area = dist.groupby("area_code_l3").agg(native_species=("plant_name_id", "nunique"), endemic_species=("single_area", "sum"))
    per_area["endemic_proportion"] = per_area.endemic_species / per_area.native_species

    classes = pd.read_csv(os.path.join(DERIVED, "island_classes.csv")).set_index("area_code_l3")
    df = per_area.join(areas, how="left")
    df["class"] = classes["class"].reindex(df.index).fillna("mainland")
    df["note"] = classes["note"].reindex(df.index)
    df.to_csv(os.path.join(DERIVED, "areas.csv"), float_format="%.6g")

    main = df[(df["class"] == "mainland") & (df.native_species >= MIN_NATIVE) & df.area_km2.notna()]
    oce_all = df[df["class"] == "oceanic"]
    oce = oce_all[(oce_all.native_species >= MIN_NATIVE) & oce_all.area_km2.notna()]
    oth = df[(df["class"] == "other-island") & (df.native_species >= MIN_NATIVE) & df.area_km2.notna()]

    def logit(p):
        p = np.clip(p, 1e-4, 1 - 1e-4)
        return np.log(p / (1 - p))
    slope, intercept, r, p_reg, se = stats.linregress(np.log10(main.area_km2), logit(main.endemic_proportion))
    oce_resid = logit(oce.endemic_proportion) - (intercept + slope * np.log10(oce.area_km2))
    oth_resid = logit(oth.endemic_proportion) - (intercept + slope * np.log10(oth.area_km2))
    frac_above = float((oce_resid > 0).mean())
    mw = stats.mannwhitneyu(oce.endemic_proportion, main.endemic_proportion, alternative="greater")

    med_S_oce, med_S_main = float(oce_all.native_species.median()), float(main.native_species.median())
    med_E_oce, med_E_main, med_E_oth = float(oce.endemic_proportion.median()), float(main.endemic_proportion.median()), float(oth.endemic_proportion.median())
    cond1 = med_S_oce < med_S_main
    cond2 = med_E_oce >= 2 * med_E_main
    cond3 = frac_above >= 0.70
    if cond1 and cond2 and cond3:
        verdict = "supports"
    elif med_E_oce <= med_E_main or frac_above < 0.50:
        verdict = "refutes"
    else:
        verdict = "mixed"

    top = oce.sort_values("endemic_proportion", ascending=False).head(10)
    measured = {
        "value": round(med_E_oce, 4),
        "unit": "median proportion of native vascular plant species endemic to a single level-3 area, oceanic islands with >= 20 native species",
        "n": int(len(oce)),
        "uncertainty": f"Mann-Whitney one-sided p vs mainland = {mw.pvalue:.2e}; IQR {oce.endemic_proportion.quantile(0.25):.3f}-{oce.endemic_proportion.quantile(0.75):.3f}",
        "extra": {
            "wcvp_version": "16 (extracted 2026-06-04, per README_WCVP.xlsx in the zip)",
            "n_oceanic_islands_total": int(len(oce_all)), "n_oceanic_islands_ge_20_native": int(len(oce)),
            "n_mainland_areas": int(len(main)), "n_other_islands": int(len(oth)),
            "median_native_species_oceanic": med_S_oce, "median_native_species_mainland": med_S_main,
            "median_endemic_proportion_oceanic": round(med_E_oce, 4), "median_endemic_proportion_mainland": round(med_E_main, 4),
            "median_endemic_proportion_other_islands": round(med_E_oth, 4),
            "ratio_oceanic_over_mainland_median": round(med_E_oce / med_E_main, 3) if med_E_main > 0 else None,
            "fraction_oceanic_above_mainland_area_regression": round(frac_above, 4),
            "fraction_other_islands_above_mainland_area_regression": round(float((oth_resid > 0).mean()), 4),
            "mainland_regression_logit_endemism_on_log10_area": {"slope": round(float(slope), 4), "intercept": round(float(intercept), 4), "r": round(float(r), 4), "p": float(p_reg)},
            "median_oceanic_logit_residual": round(float(np.median(oce_resid)), 3),
            "fraction_oceanic_with_endemism_ge_0.25": round(float((oce.endemic_proportion >= 0.25).mean()), 4),
            "median_area_km2_oceanic": round(float(oce.area_km2.median()), 1), "median_area_km2_mainland": round(float(main.area_km2.median()), 1),
            "top_oceanic_islands": [{"code": i, "name": r.l3_name, "native": int(r.native_species), "endemic": int(r.endemic_species), "proportion": round(r.endemic_proportion, 3)} for i, r in top.iterrows()],
            "conditions": {"scanty_median_S": bool(cond1), "endemism_ge_2x_mainland": bool(cond2), "ge_70pct_above_area_regression": bool(cond3)},
            "rule_based_verdict": verdict,
        },
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    json.dump([wcvp_info, l3_info], open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))

    if write_result:
        rp = os.path.join(HERE, "result.json")
        res = json.load(open(rp))
        res["measured"] = measured
        res["datasets"][0]["files"] = [wcvp_info]
        res["datasets"][0]["version"] = "16 (2026-06-04)"
        res["datasets"][1]["files"] = [l3_info]
        json.dump(res, open(rp, "w"), indent=2, ensure_ascii=False)
        open(rp, "a").write("\n")


if __name__ == "__main__":
    main()
