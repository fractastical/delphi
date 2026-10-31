#!/usr/bin/env python3
"""Test of darwin1859-ch12-04: "The species of all kinds which inhabit oceanic
islands are few in number compared with those on equal continental areas".

Vascular plants: native accepted species per TDWG level-3 botanical country from
the World Checklist of Vascular Plants (WCVP), unit areas and centroids from the
TDWG WGSRPD level-3 polygons. A species-area-latitude regression fitted on
mainland-connected units predicts the richness an oceanic island unit "should"
have at its area; the ratio observed/predicted is the measured quantity.

Re-run:  python3 analysis.py   (downloads ~90 MB into ./data/, writes ./derived/)
"""
import hashlib
import io
import json
import math
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
TDWG_URL = "https://raw.githubusercontent.com/tdwg/wgsrpd/master/geojson/level3.geojson"
EARTH_R = 6371.0088
CONNECT_KM = 2.0

# Pre-registered list, with two code transcription errors corrected after the first run:
# 'TVL' (Northern Provinces, South Africa) -> 'TUV' (Tuvalu); 'TRT' (Trinidad-Tobago, a shelf
# island) removed; Trindade has no TDWG level-3 unit.
OCEANIC = """AZO MDR SEL CNY CVI STH ASC TDC BER GAL HAW MID FIJ SAM TON SCI MRQ TUA TUB COO NUE PIT EAS JNF VAN NFK
MAU REU ROD COM GGI CRL MRN MRS GIL LIN PHX WAL TOK TUV NRU WAK HBI KER CRZ ASP HMD MPE BOU ICE OGA KZN MCS CGS MDV
LDV XMS CKI SGE SOL SCZ ALD""".split()
EXCLUDE = {"ANT"}
FILES = {}


def fetch(url, name):
    path = os.path.join(DATA, name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        data = open(path, "rb").read()
    else:
        r = requests.get(url, timeout=900, stream=True)
        r.raise_for_status()
        h = hashlib.sha256()
        with open(path, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
                h.update(chunk)
        data = open(path, "rb").read()
    FILES[name] = {"download_url": url, "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    print(f"{name}: {len(data)} bytes sha256={FILES[name]['sha256'][:12]}...", file=sys.stderr)
    return path


# ---------- geometry ----------
def ring_area_km2(coords):
    lon = np.radians([c[0] for c in coords])
    lat = np.radians([c[1] for c in coords])
    lon2, lat2 = np.roll(lon, -1), np.roll(lat, -1)
    return abs(np.sum((lon2 - lon) * (2 + np.sin(lat) + np.sin(lat2)))) * EARTH_R ** 2 / 2


def unit_geometry(feature):
    g = feature["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    area = 0.0
    wlat = 0.0
    pts = []
    for poly in polys:
        a = ring_area_km2(poly[0]) - sum(ring_area_km2(h) for h in poly[1:])
        area += a
        wlat += a * float(np.mean([c[1] for c in poly[0]]))
        pts.extend(poly[0][::max(1, len(poly[0]) // 400)])  # thinned boundary points for the adjacency test
    return area, wlat / area if area else float("nan"), np.array(pts, dtype=float)


def min_dist_km(a, b):
    """Min great-circle distance between two point sets (chunked haversine)."""
    best = float("inf")
    lat_b, lon_b = np.radians(b[:, 1]), np.radians(b[:, 0])
    for i in range(0, len(a), 200):
        lat_a, lon_a = np.radians(a[i:i + 200, 1])[:, None], np.radians(a[i:i + 200, 0])[:, None]
        h = np.sin((lat_b - lat_a) / 2) ** 2 + np.cos(lat_a) * np.cos(lat_b) * np.sin((lon_b - lon_a) / 2) ** 2
        best = min(best, float(2 * EARTH_R * np.arcsin(np.sqrt(h.min()))))
    return best


def main():
    zpath = fetch(WCVP_URL, "wcvp.zip")
    gpath = fetch(TDWG_URL, "level3.geojson")

    # --- units: area, latitude, connectivity
    feats = json.load(open(gpath))["features"]
    units = {}
    for f in feats:
        code = f["properties"]["LEVEL3_COD"]
        area, lat, pts = unit_geometry(f)
        units[code] = {"name": f["properties"]["LEVEL3_NAM"], "area_km2": area, "abs_lat": abs(lat), "pts": pts,
                       "bbox": (pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max())}
    codes = sorted(units)
    connected = {c: False for c in codes}
    for i, a in enumerate(codes):
        for b in codes[i + 1:]:
            if connected[a] and connected[b]:
                continue
            ba, bb = units[a]["bbox"], units[b]["bbox"]
            if ba[0] > bb[2] + 1 or bb[0] > ba[2] + 1 or ba[1] > bb[3] + 1 or bb[1] > ba[3] + 1:
                continue
            if min_dist_km(units[a]["pts"], units[b]["pts"]) < CONNECT_KM:
                connected[a] = connected[b] = True

    # --- native richness per unit from WCVP
    with zipfile.ZipFile(zpath) as z:
        names = pd.read_csv(io.BytesIO(z.read("wcvp_names.csv")), sep="|", usecols=["plant_name_id", "taxon_rank", "taxon_status"], dtype=str)
        dist = pd.read_csv(io.BytesIO(z.read("wcvp_distribution.csv")), sep="|",
                           usecols=["plant_name_id", "area_code_l3", "introduced", "extinct", "location_doubtful"], dtype=str)
    accepted_species = set(names.loc[(names["taxon_rank"] == "Species") & (names["taxon_status"] == "Accepted"), "plant_name_id"])
    native = dist[(dist["introduced"] == "0") & (dist["extinct"] == "0") & (dist["location_doubtful"] == "0") & dist["plant_name_id"].isin(accepted_species)]
    richness = native.groupby("area_code_l3")["plant_name_id"].nunique()

    rows = []
    for c in codes:
        if c in EXCLUDE:
            continue
        u = units[c]
        grp = "oceanic" if c in OCEANIC else ("continental" if connected[c] else "other_island")
        rows.append({"code": c, "name": u["name"], "group": grp, "area_km2": u["area_km2"], "abs_lat": u["abs_lat"],
                     "native_species": int(richness.get(c, 0))})
    df = pd.DataFrame(rows)
    df = df[df["native_species"] > 0].copy()
    df["logS"] = np.log10(df["native_species"])
    df["logA"] = np.log10(df["area_km2"])

    cont = df[df["group"] == "continental"]
    X = np.column_stack([np.ones(len(cont)), cont["logA"], cont["abs_lat"]])
    beta, *_ = np.linalg.lstsq(X, cont["logS"], rcond=None)
    resid_c = cont["logS"] - X @ beta
    r2 = 1 - (resid_c ** 2).sum() / ((cont["logS"] - cont["logS"].mean()) ** 2).sum()
    # area-only fit as a sensitivity
    X1 = np.column_stack([np.ones(len(cont)), cont["logA"]])
    beta1, *_ = np.linalg.lstsq(X1, cont["logS"], rcond=None)

    amin, amax = cont["area_km2"].min(), cont["area_km2"].max()
    oc = df[df["group"] == "oceanic"].copy()
    in_range = (oc["area_km2"] >= amin) & (oc["area_km2"] <= amax)
    oc["pred_logS"] = beta[0] + beta[1] * oc["logA"] + beta[2] * oc["abs_lat"]
    oc["pred_logS_area_only"] = beta1[0] + beta1[1] * oc["logA"]
    oc["resid"] = oc["logS"] - oc["pred_logS"]
    oc["ratio_obs_pred"] = 10 ** oc["resid"]
    oc["ratio_area_only"] = 10 ** (oc["logS"] - oc["pred_logS_area_only"])
    test = oc[in_range]
    excluded_small = oc[~in_range]

    median_ratio = float(test["ratio_obs_pred"].median())
    frac_below = float((test["resid"] < 0).mean())
    w = stats.wilcoxon(test["resid"], alternative="less")
    median_ratio_area_only = float(test["ratio_area_only"].median())

    if median_ratio <= 0.5 and frac_below >= 0.8 and w.pvalue < 0.01:
        verdict = "supports"
    elif median_ratio >= 1.0 or frac_below < 0.6:
        verdict = "refutes"
    else:
        verdict = "mixed"

    # shelf / continental islands as a comparison group (not part of the rule)
    oth = df[df["group"] == "other_island"].copy()
    oth["resid"] = oth["logS"] - (beta[0] + beta[1] * oth["logA"] + beta[2] * oth["abs_lat"])

    measured = {
        "value": round(median_ratio, 4),
        "unit": "median ratio of observed native vascular plant species on oceanic island units to the richness predicted for a continental area of equal size and latitude",
        "n": int(len(test)),
        "uncertainty": f"Wilcoxon one-sided p = {w.pvalue:.2e}; interquartile range of ratio {test['ratio_obs_pred'].quantile(0.25):.3f}-{test['ratio_obs_pred'].quantile(0.75):.3f}",
        "extra": {
            "fraction_of_oceanic_units_below_prediction": round(frac_below, 4),
            "wilcoxon_statistic": float(w.statistic), "wilcoxon_p_one_sided": float(w.pvalue),
            "median_ratio_area_only_model": round(median_ratio_area_only, 4),
            "continental_fit": {"n_units": int(len(cont)), "intercept": float(beta[0]), "slope_logA": float(beta[1]), "coef_abs_lat": float(beta[2]), "r2": float(r2),
                                 "area_range_km2": [float(amin), float(amax)], "area_only_slope": float(beta1[1])},
            "n_oceanic_units_with_data": int(len(oc)), "n_oceanic_units_in_area_range": int(len(test)),
            "oceanic_units_excluded_outside_area_range": excluded_small[["code", "name", "area_km2", "native_species"]].to_dict("records"),
            "oceanic_units_above_prediction": test[test["resid"] >= 0][["code", "name", "area_km2", "native_species", "ratio_obs_pred"]].round(3).to_dict("records"),
            "example_units": test.sort_values("area_km2", ascending=False)[["code", "name", "area_km2", "native_species", "ratio_obs_pred"]].round(3).head(12).to_dict("records"),
            "other_islands_comparison": {"n": int(len(oth)), "median_ratio": float(10 ** oth["resid"].median()), "fraction_below": float((oth["resid"] < 0).mean())},
            "verdict_by_rule": verdict,
        },
    }
    df.drop(columns=["logS", "logA"]).round(3).to_csv(os.path.join(DERIVED, "units.csv"), index=False)
    oc.drop(columns=["logS", "logA"]).round(4).to_csv(os.path.join(DERIVED, "oceanic_units.csv"), index=False)
    json.dump({"measured": measured, "files": FILES}, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
