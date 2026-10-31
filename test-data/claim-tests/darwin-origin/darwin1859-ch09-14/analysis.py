#!/usr/bin/env python3
"""Test darwin1859-ch09-14: oceans and continents have kept their present areas since the Silurian.

Data: GPlates Web Service reconstruct/coastlines (GeoJSON) for MERDITH2021 (primary) and PALEOMAP
(robustness), at 0 Ma and nine past times. Point-in-polygon on a 2x2 degree grid.
Usage: python3 analysis.py [--write-result]
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

GWS = "https://gws.gplates.org/reconstruct/coastlines/"
TIMES = [440, 400, 350, 300, 250, 200, 150, 100, 50]
MODELS = {"MERDITH2021": "merdith2021", "PALEOMAP": "paleomap"}
STEP = 2.0
FILES = []


def get_cached(url, cache_name, role):
    path = os.path.join(DATA, cache_name)
    meta = path + ".meta"
    if not (os.path.exists(path) and os.path.exists(meta)):
        for attempt in range(6):
            try:
                r = requests.get(url, timeout=600)
                if r.status_code == 200 and r.content.strip().startswith(b"{"):
                    break
            except requests.RequestException:
                pass
            time.sleep(3 * 2 ** attempt)
        r.raise_for_status()
        open(path, "wb").write(r.content)
        open(meta, "w").write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    content = open(path, "rb").read()
    FILES.append({"download_url": url, "retrieved_at": open(meta).read().strip(), "byte_size": len(content),
                  "sha256": hashlib.sha256(content).hexdigest(), "role": role})
    return json.loads(content.decode("utf-8"))


def rings_of(feature):
    g = feature["geometry"]
    if g["type"] == "Polygon":
        yield np.asarray(g["coordinates"][0], dtype=float)
    elif g["type"] == "MultiPolygon":
        for poly in g["coordinates"]:
            yield np.asarray(poly[0], dtype=float)


def points_in_ring(lon, lat, ring):
    """Even-odd ray casting, vectorised over points; ring is (k, 2) lon/lat."""
    x, y = ring[:, 0], ring[:, 1]
    inside = np.zeros(lon.shape, dtype=bool)
    sel = (lon >= x.min()) & (lon <= x.max()) & (lat >= y.min()) & (lat <= y.max())
    if not sel.any():
        return inside
    px, py = lon[sel], lat[sel]
    k = len(x)
    res = np.zeros(px.shape, dtype=bool)
    j = k - 1
    for i in range(k):
        yi, yj = y[i], y[j]
        cond = (yi > py) != (yj > py)
        if cond.any():
            xint = (x[j] - x[i]) * (py - yi) / (yj - yi + 1e-300) + x[i]
            res ^= cond & (px < xint)
        j = i
    inside[sel] = res
    return inside


def land_mask(fc, lon, lat):
    mask = np.zeros(lon.shape, dtype=bool)
    for f in fc["features"]:
        for ring in rings_of(f):
            if len(ring) < 4:
                continue
            # polygons crossing the dateline are handled by testing the ring shifted by +-360
            mask |= points_in_ring(lon, lat, ring)
            if ring[:, 0].max() - ring[:, 0].min() > 180:
                r2 = ring.copy()
                r2[r2[:, 0] < 0, 0] += 360
                mask |= points_in_ring(np.where(lon < 0, lon + 360, lon), lat, r2)
    return mask


def main():
    write_result = "--write-result" in sys.argv
    lats = np.arange(-90 + STEP / 2, 90, STEP)
    lons = np.arange(-180 + STEP / 2, 180, STEP)
    LON, LAT = np.meshgrid(lons, lats)
    lon, lat = LON.ravel(), LAT.ravel()
    w = np.cos(np.deg2rad(lat))
    w /= w.sum()

    out = {}
    for model, slug in MODELS.items():
        fc0 = get_cached(f"{GWS}?time=0&model={model}", f"coastlines_{slug}_0.json", f"{model} coastlines at 0 Ma")
        present_land = land_mask(fc0, lon, lat)
        land_frac = float(w[present_land].sum())
        per_time = {}
        land_always = present_land.copy()
        ocean_always = ~present_land
        for t in TIMES:
            fc = get_cached(f"{GWS}?time={t}&model={model}", f"coastlines_{slug}_{t}.json", f"{model} coastlines at {t} Ma")
            m = land_mask(fc, lon, lat)
            L_t = float(w[present_land & m].sum() / w[present_land].sum())
            O_t = float(w[~present_land & ~m].sum() / w[~present_land].sum())
            paleo_land_frac = float(w[m].sum())
            per_time[t] = {"L_t": round(L_t, 4), "O_t": round(O_t, 4), "paleo_land_area_fraction": round(paleo_land_frac, 4),
                           "n_polygons": len(fc["features"])}
            land_always &= m
            ocean_always &= ~m
        L_all = float(w[land_always].sum() / w[present_land].sum())
        O_all = float(w[ocean_always].sum() / w[~present_land].sum())
        out[model] = {"present_land_area_fraction": round(land_frac, 4), "L_all": round(L_all, 4), "O_all": round(O_all, 4),
                      "per_time": per_time, "n_grid_cells": int(lon.size)}
        pd.DataFrame({"lon": lon, "lat": lat, "present_land": present_land, "land_at_all_times": land_always,
                      "ocean_at_all_times": ocean_always}).to_csv(os.path.join(DERIVED, f"grid_{slug}.csv.gz"), index=False, compression="gzip")

    prim = out["MERDITH2021"]
    if prim["L_all"] >= 0.75 and prim["O_all"] >= 0.75:
        verdict = "supports"
    elif prim["L_all"] < 0.50 or prim["O_all"] < 0.50:
        verdict = "refutes"
    else:
        verdict = "mixed"

    measured = {
        "value": prim["L_all"],
        "unit": "area fraction of present-day land that lies within reconstructed continental coastlines at all nine times 440-50 Ma (MERDITH2021)",
        "n": prim["n_grid_cells"],
        "uncertainty": f"O_all (present ocean that was ocean at all times) = {prim['O_all']}; PALEOMAP robustness: L_all = {out['PALEOMAP']['L_all']}, O_all = {out['PALEOMAP']['O_all']}",
        "extra": {"models": out, "times_ma": TIMES, "grid_step_deg": STEP,
                  "random_placement_expectation_L": prim["present_land_area_fraction"],
                  "random_placement_expectation_O": round(1 - prim["present_land_area_fraction"], 4),
                  "rule_based_verdict": verdict},
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    json.dump(FILES, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))

    if write_result:
        rp = os.path.join(HERE, "result.json")
        res = json.load(open(rp))
        res["measured"] = measured
        for ds in res["datasets"]:
            model = "MERDITH2021" if "merdith" in ds["id"] else "PALEOMAP"
            ds["files"] = [{k: v for k, v in f.items() if k != "role"} | {"note": f["role"]} for f in FILES if f"model={model}" in f["download_url"]]
        json.dump(res, open(rp, "w"), indent=2, ensure_ascii=False)
        open(rp, "a").write("\n")


if __name__ == "__main__":
    main()
