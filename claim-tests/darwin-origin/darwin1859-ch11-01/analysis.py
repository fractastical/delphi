#!/usr/bin/env python3
"""Test darwin1859-ch11-01: physical conditions do not explain the similarity of regional biotas.

Data: GBIF occurrence genus facets within pre-registered 5x5 degree boxes (derived/regions.csv),
NASA POWER climatology at five points per box.
Usage: python3 analysis.py [--write-result]
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from itertools import combinations

import numpy as np
import pandas as pd
import requests
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

GBIF = "https://api.gbif.org/v1/occurrence/search"
POWER = "https://power.larc.nasa.gov/api/temporal/climatology/point"
GROUPS = {"Mammalia": 359, "Aves": 212, "Tracheophyta": 7707728}
MIN_RECORDS = 3
MIN_GENERA = 20
MIN_REGIONS = 15
N_PERM = 2000
SEED = 20261031
FILES = []


def get_cached(url, cache_name, role):
    path = os.path.join(DATA, cache_name)
    meta = path + ".meta"
    if not (os.path.exists(path) and os.path.exists(meta)):
        for attempt in range(6):
            try:
                r = requests.get(url, timeout=180)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(2 ** attempt)
        r.raise_for_status()
        open(path, "wb").write(r.content)
        open(meta, "w").write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    content = open(path, "rb").read()
    FILES.append({"download_url": url, "retrieved_at": open(meta).read().strip(), "byte_size": len(content),
                  "sha256": hashlib.sha256(content).hexdigest(), "role": role})
    return json.loads(content.decode("utf-8"))


def genus_list(region, taxon_key):
    url = (f"{GBIF}?limit=0&facet=genusKey&facetLimit=50000&taxonKey={taxon_key}"
           f"&decimalLatitude={region.lat_min},{region.lat_max}&decimalLongitude={region.lon_min},{region.lon_max}"
           f"&hasCoordinate=true&hasGeospatialIssue=false&occurrenceStatus=PRESENT")
    d = get_cached(url, f"gbif_{region.region_id}_{taxon_key}.json", f"genus facet, {region.region_id}")
    counts = d["facets"][0]["counts"] if d.get("facets") else []
    return {int(c["name"]) for c in counts if c["count"] >= MIN_RECORDS}, d["count"]


def climate(region):
    lat0, lat1, lon0, lon1 = region.lat_min, region.lat_max, region.lon_min, region.lon_max
    cy, cx = (lat0 + lat1) / 2, (lon0 + lon1) / 2
    pts = [(cy, cx), (lat0 + 1, lon0 + 1), (lat0 + 1, lon1 - 1), (lat1 - 1, lon0 + 1), (lat1 - 1, lon1 - 1)]
    vals = []
    for la, lo in pts:
        url = f"{POWER}?parameters=T2M,PRECTOTCORR&community=AG&longitude={lo}&latitude={la}&format=JSON"
        d = get_cached(url, f"power_{region.region_id}_{la}_{lo}.json", f"climatology point, {region.region_id}")
        p = d["properties"]["parameter"]
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        t = [p["T2M"][m] for m in months]
        pr = [p["PRECTOTCORR"][m] for m in months]  # mm/day
        days = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        vals.append((np.mean(t), sum(a * b for a, b in zip(pr, days)), max(t) - min(t)))
    v = np.array(vals)
    return {"t_mean": v[:, 0].mean(), "p_annual_mm": v[:, 1].mean(), "t_range": v[:, 2].mean()}


def jaccard_dissim(a, b):
    u = len(a | b)
    return 1 - len(a & b) / u if u else np.nan


def fit(y, X):
    X1 = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    resid = y - X1 @ beta
    r2 = 1 - resid.var() / y.var()
    return beta, r2


def mantel_regression(D, Xc, S, rng):
    """D: response dissimilarity matrix; Xc: climate distance matrix; S: same-continent matrix (1/0)."""
    n = D.shape[0]
    iu = np.triu_indices(n, 1)
    y = D[iu]
    Xmat = np.column_stack([Xc[iu], S[iu]])
    beta, r2 = fit(y, Xmat)
    _, r2_no_clim = fit(y, Xmat[:, [1]])
    _, r2_no_cont = fit(y, Xmat[:, [0]])
    partial_clim, partial_cont = r2 - r2_no_clim, r2 - r2_no_cont
    # Permute region labels of the response matrix (Mantel-type permutation test)
    b_clim = b_cont = 0
    for _ in range(N_PERM):
        perm = rng.permutation(n)
        yp = D[np.ix_(perm, perm)][iu]
        bp, _ = fit(yp, Xmat)
        b_clim += abs(bp[1]) >= abs(beta[1])
        b_cont += abs(bp[2]) >= abs(beta[2])
    return {"beta_climate": beta[1], "beta_same_continent": beta[2], "r2_full": r2,
            "partial_r2_climate": partial_clim, "partial_r2_same_continent": partial_cont,
            "p_climate": (b_clim + 1) / (N_PERM + 1), "p_same_continent": (b_cont + 1) / (N_PERM + 1)}


def main():
    write_result = "--write-result" in sys.argv
    regions = pd.read_csv(os.path.join(DERIVED, "regions.csv"))
    rng = np.random.default_rng(SEED)

    clim = pd.DataFrame([climate(r) for r in regions.itertuples()], index=regions.region_id)
    cz = clim.copy()
    cz["p_annual_mm"] = np.log(cz["p_annual_mm"] + 1)
    cz = (cz - cz.mean()) / cz.std(ddof=1)
    n = len(regions)
    Xc = np.zeros((n, n))
    S = np.zeros((n, n))
    for i, j in combinations(range(n), 2):
        Xc[i, j] = Xc[j, i] = np.linalg.norm(cz.iloc[i].values - cz.iloc[j].values)
        S[i, j] = S[j, i] = 1.0 if regions.continent[i] == regions.continent[j] else 0.0

    results = {}
    pair_rows = []
    region_rows = []
    for gname, key in GROUPS.items():
        lists, totals = {}, {}
        for r in regions.itertuples():
            gl, total = genus_list(r, key)
            lists[r.region_id] = gl
            totals[r.region_id] = total
            region_rows.append({"group": gname, "region_id": r.region_id, "records": total, "genera": len(gl)})
        keep = [i for i, r in enumerate(regions.itertuples()) if len(lists[r.region_id]) >= MIN_GENERA]
        if len(keep) < MIN_REGIONS:
            results[gname] = {"evaluated": False, "regions": len(keep)}
            continue
        ids = [regions.region_id[i] for i in keep]
        m = len(keep)
        D = np.zeros((m, m))
        for a, b in combinations(range(m), 2):
            D[a, b] = D[b, a] = jaccard_dissim(lists[ids[a]], lists[ids[b]])
        sub = np.ix_(keep, keep)
        reg = mantel_regression(D, Xc[sub], S[sub], rng)
        # climate-matched cross-continent vs climate-mismatched same-continent
        matched_cross, mismatched_same, triad = [], [], []
        for a, b in combinations(range(m), 2):
            ia, ib = keep[a], keep[b]
            same_cont = regions.continent[ia] == regions.continent[ib]
            same_clim = regions.climate_class[ia] == regions.climate_class[ib]
            sim = 1 - D[a, b]
            pair_rows.append({"group": gname, "region_a": ids[a], "region_b": ids[b], "jaccard_similarity": round(sim, 5),
                              "climate_distance": round(Xc[ia, ib], 4), "same_continent": int(same_cont), "same_climate_class": int(same_clim)})
            if same_clim and not same_cont:
                matched_cross.append(sim)
            if same_cont and not same_clim:
                mismatched_same.append(sim)
            if {ids[a], ids[b]} <= {"AUS_SW", "AFR_CAPE", "SAM_CHILE"}:
                triad.append(sim)
        mw = stats.mannwhitneyu(matched_cross, mismatched_same, alternative="less") if matched_cross and mismatched_same else None
        cond_a = reg["p_same_continent"] < 0.05 and reg["partial_r2_same_continent"] > reg["partial_r2_climate"]
        cond_b = np.mean(matched_cross) < np.mean(mismatched_same)
        results[gname] = {
            "evaluated": True, "regions": m, "regions_dropped": [regions.region_id[i] for i in range(n) if i not in keep],
            "median_genera_per_region": float(np.median([len(lists[i]) for i in ids])),
            **{k: round(float(v), 5) for k, v in reg.items()},
            "mean_similarity_climate_matched_cross_continent": round(float(np.mean(matched_cross)), 5),
            "n_pairs_climate_matched_cross_continent": len(matched_cross),
            "mean_similarity_climate_mismatched_same_continent": round(float(np.mean(mismatched_same)), 5),
            "n_pairs_climate_mismatched_same_continent": len(mismatched_same),
            "mannwhitney_p_matched_cross_less_than_mismatched_same": None if mw is None else round(float(mw.pvalue), 5),
            "darwin_triad_mean_similarity_AUS_SW_AFR_CAPE_SAM_CHILE": round(float(np.mean(triad)), 5) if triad else None,
            "condition_a_continent_dominates": bool(cond_a), "condition_b_matched_cross_lt_mismatched_same": bool(cond_b),
            "passes_both": bool(cond_a and cond_b),
            "fails": bool((reg["partial_r2_climate"] > reg["partial_r2_same_continent"] and reg["p_same_continent"] >= 0.05) or not cond_b),
        }

    pd.DataFrame(pair_rows).to_csv(os.path.join(DERIVED, "pairs.csv"), index=False)
    pd.DataFrame(region_rows).to_csv(os.path.join(DERIVED, "regions_counts.csv"), index=False)
    clim.round(3).to_csv(os.path.join(DERIVED, "climate.csv"))

    evaluated = [g for g in results.values() if g.get("evaluated")]
    n_pass = sum(1 for g in evaluated if g["passes_both"])
    n_fail = sum(1 for g in evaluated if g["fails"])
    if len(evaluated) == 0:
        verdict = "inconclusive"
    elif n_pass >= 2:
        verdict = "supports"
    elif n_fail >= 2:
        verdict = "refutes"
    else:
        verdict = "mixed"

    measured = {
        "value": n_pass,
        "unit": "taxon groups (of 3) in which same-continent membership outweighs climate distance and climate-matched cross-continental pairs are less similar than climate-mismatched same-continent pairs",
        "n": int(n * (n - 1) / 2),
        "uncertainty": "permutation p-values per group in extra",
        "extra": {"groups": results, "n_regions": int(n), "n_permutations": N_PERM, "seed": SEED, "rule_based_verdict": verdict},
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2, default=float)
    json.dump(FILES, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2, default=float))

    if write_result:
        rp = os.path.join(HERE, "result.json")
        res = json.load(open(rp))
        res["measured"] = json.loads(json.dumps(measured, default=float))
        for ds in res["datasets"]:
            host = "gbif.org" if ds["id"].startswith("gbif") else "power.larc.nasa.gov"
            fl = [f for f in FILES if host in f["download_url"]]
            ds["files"] = [{
                "download_url": fl[0]["download_url"].split("?")[0] + "?... (one call per region/group; full list with per-call SHA-256 in derived/files.json)",
                "retrieved_at": min(f["retrieved_at"] for f in fl),
                "byte_size": sum(f["byte_size"] for f in fl),
                "sha256": hashlib.sha256("".join(f["sha256"] for f in fl).encode()).hexdigest(),
                "note": f"{len(fl)} API responses; sha256 is the SHA-256 of the concatenated per-response SHA-256 hex digests",
            }]
        json.dump(res, open(rp, "w"), indent=2, ensure_ascii=False)
        open(rp, "a").write("\n")


if __name__ == "__main__":
    main()
