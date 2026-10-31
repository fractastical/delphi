#!/usr/bin/env python3
"""Test of darwin1859-ch11-02: barriers to migration track the differences between regional
faunas, the more impassable and long-standing the barrier the greater the difference.

Data: GBIF occurrence search API facet counts (speciesKey) for Rodentia, Squamata and
Amphibia in 52 pre-registered boxes forming 26 region pairs. Response checksums go to
derived/fetch_log.csv.gz; per-pair statistics to derived/pair_dissimilarity.csv.
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


def get(url, params=None, tries=6):
    for attempt in range(tries):
        try:
            time.sleep(0.4)
            r = S.get(url, params=params, timeout=180)
            if r.status_code == 200:
                FETCH_LOG.append({"download_url": r.url,
                                  "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                  "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()})
                return r.json()
            print("HTTP", r.status_code, r.url, file=sys.stderr)
        except requests.RequestException as e:
            print("retry", attempt, e, file=sys.stderr)
        time.sleep(3 * (attempt + 1))
    raise RuntimeError("GBIF request failed")


def bbox_wkt(b):
    w, s, e, n = b
    return f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"


def species_set(taxon_key, bbox):
    params = [("taxonKey", taxon_key), ("geometry", bbox_wkt(bbox)), ("hasCoordinate", "true"),
              ("hasGeospatialIssue", "false"), ("occurrenceStatus", "PRESENT"), ("year", PRE["year_range"]),
              ("facet", "speciesKey"), ("facetLimit", 100000), ("limit", 0)]
    params += [("basisOfRecord", b) for b in BASIS_ALLOWED]
    d = get(API + "/occurrence/search", params)
    return d["count"], {int(c["name"]) for c in d["facets"][0]["counts"] if c["count"] >= PRE["min_records_per_species"]}


def genus_key(name, cls_hint):
    d = get(API + "/species", {"name": name, "rank": "GENUS", "datasetKey": BACKBONE, "limit": 50})
    hits = [r for r in d.get("results", []) if r.get("canonicalName") == name and r.get("order") == cls_hint
            and r.get("taxonomicStatus") == "ACCEPTED"]
    return hits[0]["key"] if hits else None


def centroid(b):
    return ((b[1] + b[3]) / 2, (b[0] + b[2]) / 2)


def haversine_km(p, q):
    lat1, lon1, lat2, lon2 = map(math.radians, (p[0], p[1], q[0], q[1]))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def partial_spearman(x, y, z):
    rx, ry, rz = (stats.rankdata(v) for v in (x, y, z))
    def resid(a, b):
        slope, intercept = np.polyfit(b, a, 1)
        return a - (slope * b + intercept)
    r = stats.pearsonr(resid(rx, rz), resid(ry, rz))
    n = len(x)
    t = r[0] * math.sqrt((n - 3) / (1 - r[0] ** 2))
    p_one_sided = 1 - stats.t.cdf(t, n - 3)
    return float(r[0]), float(p_one_sided)


def main():
    for gname, key in PRE["groups"].items():
        d = get(API + f"/species/{key}")
        assert d["canonicalName"] == gname, (gname, d.get("canonicalName"))
    excl = {}
    for gname, genera in PRE["excluded_genera"].items():
        excl[gname] = {g: genus_key(g, gname) for g in genera}
    print("excluded genus keys:", excl, flush=True)

    boxes = {}
    for p in PRE["pairs"]:
        boxes[p["id"] + ":a"] = p["a"]
        boxes[p["id"] + ":b"] = p["b"]
    sets, box_rows = {}, []
    for gname, key in PRE["groups"].items():
        for bid, bbox in boxes.items():
            n, sp = species_set(key, bbox)
            for g, gk in excl.get(gname, {}).items():
                if gk:
                    _, bad = species_set(gk, bbox)
                    sp -= bad
            sets[(gname, bid)] = sp
            box_rows.append({"group": gname, "box": bid, "n_records": n, "n_species": len(sp)})
            print(gname, bid, n, len(sp), flush=True)
    pd.DataFrame(box_rows).to_csv(os.path.join(DERIVED, "box_species_counts.csv"), index=False)
    pd.DataFrame(FETCH_LOG).to_csv(os.path.join(DERIVED, "fetch_log.csv.gz"), index=False, compression="gzip")

    rows = []
    for p in PRE["pairs"]:
        row = {"pair": p["id"], "barrier": p["barrier"], "rank": PRE["barrier_ranks"][p["barrier"]],
               "distance_km": haversine_km(centroid(p["a"]), centroid(p["b"]))}
        vals = []
        for gname in PRE["groups"]:
            A, B = sets[(gname, p["id"] + ":a")], sets[(gname, p["id"] + ":b")]
            if len(A) < PRE["min_species_per_box"] or len(B) < PRE["min_species_per_box"]:
                row[f"dissim_{gname}"] = float("nan")
                continue
            dis = 1 - 2 * len(A & B) / (len(A) + len(B))
            row[f"dissim_{gname}"] = dis
            row[f"shared_{gname}"] = len(A & B)
            vals.append(dis)
        row["n_groups"] = len(vals)
        row["mean_dissim"] = float(np.mean(vals)) if vals else float("nan")
        rows.append(row)
    pairs = pd.DataFrame(rows)
    pairs.to_csv(os.path.join(DERIVED, "pair_dissimilarity.csv"), index=False)
    use = pairs.dropna(subset=["mean_dissim"])
    n = len(use)
    rho, p_rho = stats.spearmanr(use["mean_dissim"], use["rank"])
    p_rho_one = p_rho / 2 if rho > 0 else 1 - p_rho / 2
    prho, pp = partial_spearman(use["mean_dissim"].values, use["rank"].values, np.log(use["distance_km"].values))
    by_class = use.groupby("barrier").agg(n=("pair", "size"), mean_dissim=("mean_dissim", "mean"),
                                          mean_distance_km=("distance_km", "mean"), rank=("rank", "first")).sort_values("rank")
    none_mean = float(by_class.loc["none", "mean_dissim"])
    deep_ocean_mean = float(use[use["rank"] >= 4].mean_dissim.mean())
    none_below_all = all(none_mean < by_class.loc[b, "mean_dissim"] for b in by_class.index if by_class.loc[b, "rank"] >= 2)
    measured = {
        "value": round(float(rho), 4),
        "unit": "Spearman rho between barrier rank and mean species-level Sørensen dissimilarity (Rodentia, Squamata, Amphibia)",
        "n": int(n),
        "uncertainty": f"one-sided p={p_rho_one:.2e}; partial Spearman controlling log distance rho={prho:.3f}, one-sided p={pp:.2e}",
        "extra": {
            "spearman_p_one_sided": float(p_rho_one), "partial_rho_given_log_distance": prho, "partial_p_one_sided": pp,
            "spearman_rho_distance_vs_dissim": float(stats.spearmanr(use["mean_dissim"], use["distance_km"])[0]),
            "mean_dissim_by_barrier_class": {b: {"n": int(r_.n), "mean_dissim": float(r_.mean_dissim), "mean_distance_km": float(r_.mean_distance_km), "rank": int(r_["rank"])}
                                             for b, r_ in by_class.iterrows()},
            "none_mean": none_mean, "deep_strait_and_ocean_mean": deep_ocean_mean,
            "none_below_every_class_rank_ge2": bool(none_below_all),
            "pairs_with_all_three_groups": int((use.n_groups == 3).sum()),
            "per_group_spearman_rho": {g: float(stats.spearmanr(use[f"dissim_{g}"], use["rank"], nan_policy="omit")[0]) for g in PRE["groups"]},
            "excluded_genus_keys": excl,
        },
    }
    if n < 15:
        verdict = "inconclusive"
    elif rho >= 0.5 and p_rho_one < 0.01 and prho > 0 and pp < 0.05 and none_below_all:
        verdict = "supports"
    elif rho <= 0 or none_mean >= deep_ocean_mean:
        verdict = "refutes"
    else:
        verdict = "mixed"
    print(json.dumps(measured, indent=1))
    print("verdict:", verdict)
    json.dump({"measured": measured, "verdict": verdict}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
