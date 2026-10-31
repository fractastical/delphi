#!/usr/bin/env python3
"""Test of darwin1859-ch12-11: the depth of sea between an island and the neighbouring
mainland predicts whether they share the same (or allied) terrestrial mammals.

Data: GBIF occurrence search API (species facets for Mammalia and the excluded groups in
island and mainland boxes) and GEBCO 2020 bathymetry via the OpenTopoData API (straight
transects between nearest shores). Checksums go to derived/fetch_log.csv.gz; per-island
statistics to derived/islands.csv.
"""
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)
RESULT = json.load(open(os.path.join(HERE, "result.json")))
PRE = RESULT["preregistration"]
API = "https://api.gbif.org/v1"
BACKBONE = "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"
FETCH_LOG = []
S = requests.Session()
S.headers["User-Agent"] = "delphi-claim-tests/0.1 (https://github.com/fractastical/delphi)"
BASIS_ALLOWED = ["PRESERVED_SPECIMEN", "HUMAN_OBSERVATION", "MACHINE_OBSERVATION",
                 "MATERIAL_SAMPLE", "OBSERVATION", "OCCURRENCE", "MATERIAL_CITATION"]


def get(url, params=None, tries=6, pause=0.4):
    for attempt in range(tries):
        try:
            time.sleep(pause)
            r = S.get(url, params=params, timeout=180)
            if r.status_code == 200:
                FETCH_LOG.append({"download_url": r.url,
                                  "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                  "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()})
                return r.json()
            print("HTTP", r.status_code, r.url[:120], file=sys.stderr)
        except requests.RequestException as e:
            print("retry", attempt, e, file=sys.stderr)
        time.sleep(3 * (attempt + 1))
    raise RuntimeError("request failed: " + url)


def bbox_wkt(b):
    w, s, e, n = b
    return f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"


def species_set(taxon_key, bbox):
    params = [("taxonKey", taxon_key), ("geometry", bbox_wkt(bbox)), ("hasCoordinate", "true"),
              ("hasGeospatialIssue", "false"), ("occurrenceStatus", "PRESENT"), ("year", PRE["year_range"]),
              ("facet", "speciesKey"), ("facet", "genusKey"), ("facetLimit", 100000), ("limit", 0)]
    params += [("basisOfRecord", b) for b in BASIS_ALLOWED]
    d = get(API + "/occurrence/search", params)
    out = {}
    for f in d["facets"]:
        out[f["field"]] = {int(c["name"]): c["count"] for c in f["counts"] if c["count"] >= PRE["min_records_per_species"]}
    return out.get("SPECIES_KEY", {}), out.get("GENUS_KEY", {})


def backbone_key(name, rank):
    d = get(API + "/species/match", {"name": name, "rank": rank, "kingdom": "Animalia", "strict": "true"})
    if d.get("matchType") == "EXACT" and d.get("rank") == rank and d.get("class") == "Mammalia":
        return d["usageKey"]
    d = get(API + "/species", {"name": name, "rank": rank, "datasetKey": BACKBONE, "limit": 50})
    hits = [r for r in d.get("results", []) if r.get("canonicalName") == name and r.get("class") == "Mammalia"
            and r.get("taxonomicStatus") == "ACCEPTED"]
    return hits[0]["key"] if hits else None


def haversine_km(p, q):
    lat1, lon1, lat2, lon2 = map(math.radians, (p[0], p[1], q[0], q[1]))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def channel_depth(transect):
    (lat1, lon1), (lat2, lon2) = transect
    n = PRE["transect_points"]
    pts = [(lat1 + (lat2 - lat1) * i / (n - 1), lon1 + (lon2 - lon1) * i / (n - 1)) for i in range(n)]
    locs = "|".join(f"{la:.5f},{lo:.5f}" for la, lo in pts)
    d = get(PRE["bathymetry_api"], {"locations": locs}, pause=1.1)
    elev = [r["elevation"] for r in d["results"] if r["elevation"] is not None]
    depth = -min(elev) if elev else float("nan")
    return max(depth, 0.0), sum(1 for e in elev if e > 0)


def partial_spearman(x, y, z):
    rx, ry, rz = (stats.rankdata(v) for v in (x, y, z))
    def resid(a, b):
        slope, intercept = np.polyfit(b, a, 1)
        return a - (slope * b + intercept)
    r = stats.pearsonr(resid(rx, rz), resid(ry, rz))[0]
    n = len(x)
    t = r * math.sqrt((n - 3) / (1 - r ** 2))
    return float(r), float(stats.t.cdf(t, n - 3))  # one-sided p for r < 0


def main():
    excl_keys = {}
    for nm in PRE["excluded_higher_taxa"]:
        excl_keys[nm] = backbone_key(nm, "ORDER" if nm in ("Chiroptera", "Cetacea", "Sirenia") else "FAMILY")
    for nm in PRE["excluded_genera"]:
        excl_keys[nm] = backbone_key(nm, "GENUS")
    print("exclusion keys:", excl_keys, flush=True)
    if excl_keys.get("Cetacea") is None:
        # GBIF backbone may place whales inside Artiodactyla/Cetartiodactyla; fall back to the infraorder
        excl_keys["Cetacea"] = backbone_key("Cetacea", "INFRAORDER") or backbone_key("Cetacea", "SUBORDER")
        print("Cetacea fallback key:", excl_keys["Cetacea"], flush=True)

    def terrestrial_set(bbox):
        sp, gen = species_set(PRE["mammalia_key"], bbox)
        sp, gen = set(sp), set(gen)
        for nm, k in excl_keys.items():
            if k is None:
                continue
            bad_sp, bad_gen = species_set(k, bbox)
            sp -= set(bad_sp)
            gen -= set(bad_gen)
        return sp, gen

    rows = []
    for isl in PRE["islands"]:
        isp, igen = terrestrial_set(isl["island"])
        msp, mgen = terrestrial_set(isl["mainland"])
        depth, n_land = channel_depth(isl["transect"])
        width = haversine_km(*isl["transect"])
        row = {"island": isl["id"], "mainland": isl["mainland_note"], "n_island_species": len(isp), "n_mainland_species": len(msp),
               "shared_species": len(isp & msp), "f_shared_species": len(isp & msp) / len(isp) if isp else float("nan"),
               "n_island_genera": len(igen), "f_shared_genera": len(igen & mgen) / len(igen) if igen else float("nan"),
               "channel_depth_m": depth, "transect_points_on_land": n_land, "channel_width_km": width}
        rows.append(row)
        print(json.dumps(row), flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(DERIVED, "islands.csv"), index=False)

    use = df[(df.n_island_species >= PRE["min_species_per_island"]) & df.channel_depth_m.notna()].copy()
    n = len(use)
    use["log_depth"] = np.log(use.channel_depth_m.clip(lower=1))
    use["log_width"] = np.log(use.channel_width_km.clip(lower=0.1))
    rho, p2 = stats.spearmanr(use.f_shared_species, use.log_depth)
    p_one = p2 / 2 if rho < 0 else 1 - p2 / 2
    prho, pp = partial_spearman(use.f_shared_species.values, use.log_depth.values, use.log_width.values)
    shallow = use[use.channel_depth_m <= PRE["low_stand_depth_m"]]
    deep = use[use.channel_depth_m > PRE["low_stand_depth_m"]]
    rho_w = stats.spearmanr(use.f_shared_species, use.log_width)[0]
    rho_gen = stats.spearmanr(use.f_shared_genera, use.log_depth)[0]
    measured = {
        "value": round(float(rho), 4),
        "unit": "Spearman rho between log channel depth and the fraction of island terrestrial mammal species shared with the neighbouring mainland",
        "n": int(n),
        "uncertainty": f"one-sided p={p_one:.3f}; partial rho controlling log channel width={prho:.3f}, one-sided p={pp:.3f}",
        "extra": {
            "spearman_p_one_sided": float(p_one), "partial_rho_given_log_width": prho, "partial_p_one_sided": pp,
            "mean_f_shallow_le_120m": float(shallow.f_shared_species.mean()), "n_shallow": int(len(shallow)),
            "mean_f_deep_gt_120m": float(deep.f_shared_species.mean()), "n_deep": int(len(deep)),
            "mannwhitney_p_shallow_greater": float(stats.mannwhitneyu(shallow.f_shared_species, deep.f_shared_species, alternative="greater").pvalue) if len(shallow) and len(deep) else None,
            "spearman_rho_width_vs_f": float(rho_w), "spearman_rho_depth_vs_f_genus_level": float(rho_gen),
            "islands_dropped": df[~df.island.isin(use.island)].island.tolist(),
            "exclusion_keys": excl_keys,
        },
    }
    if n < PRE["min_islands"]:
        verdict = "inconclusive"
    elif rho < 0 and p_one < 0.05 and prho < 0 and pp < 0.05 and shallow.f_shared_species.mean() > deep.f_shared_species.mean():
        verdict = "supports"
    elif rho >= 0 or shallow.f_shared_species.mean() <= deep.f_shared_species.mean():
        verdict = "refutes"
    else:
        verdict = "mixed"
    print(json.dumps(measured, indent=1))
    print("verdict:", verdict)
    pd.DataFrame(FETCH_LOG).to_csv(os.path.join(DERIVED, "fetch_log.csv.gz"), index=False, compression="gzip")
    json.dump({"measured": measured, "verdict": verdict}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
