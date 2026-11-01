#!/usr/bin/env python3
"""Test of darwin1859-ch12-14: naturalised species are usually not closely allied to the natives
they join (genus novelty of naturalised plants vs the pool of species naturalised elsewhere).

Requires: requests, numpy, pandas, scipy.
Data: WCVP checklist (Kew). The 88 MB zip is cached in /tmp, not committed; URL, size and
SHA-256 go to derived/fetch_log.json. Per-region statistics: derived/regions.csv.
"""
import hashlib
import json
import os
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)
PRE = json.load(open(os.path.join(HERE, "result.json")))["preregistration"]
CACHE = os.environ.get("DELPHI_CACHE", "/tmp/delphi-data")
os.makedirs(CACHE, exist_ok=True)
LOG = []


def fetch(url, name):
    path = os.path.join(CACHE, name)
    when = None
    if not os.path.exists(path):
        with requests.get(url, stream=True, timeout=1800) as r:
            r.raise_for_status()
            with open(path + ".part", "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        os.rename(path + ".part", path)
        when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    LOG.append({"download_url": url, "retrieved_at": when or datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "byte_size": os.path.getsize(path), "sha256": h.hexdigest()})
    return path


def load_wcvp():
    z = zipfile.ZipFile(fetch(PRE["wcvp_url"], "wcvp.zip"))
    names = pd.read_csv(z.open("wcvp_names.csv"), sep="|", dtype=str, keep_default_na=False,
                        usecols=["plant_name_id", "taxon_rank", "taxon_status", "genus_hybrid", "genus", "species_hybrid", "species"])
    names = names[(names.taxon_rank == "Species") & (names.taxon_status == "Accepted")
                  & (names.genus_hybrid == "") & (names.species_hybrid == "")]
    dist = pd.read_csv(z.open("wcvp_distribution.csv"), sep="|", dtype=str, keep_default_na=False,
                       usecols=["plant_name_id", "area_code_l3", "introduced", "extinct", "location_doubtful"])
    dist = dist[dist.plant_name_id.isin(names.plant_name_id) & (dist.location_doubtful == "0")]
    return dist.merge(names[["plant_name_id", "genus"]], on="plant_name_id")


def main():
    d = load_wcvp()
    intro = d[d.introduced == "1"]
    native_any = d[d.introduced == "0"]
    intro_regions = intro.groupby("plant_name_id").area_code_l3.apply(set)
    sp_genus = d.drop_duplicates("plant_name_id").set_index("plant_name_id").genus
    present_codes = set(d.area_code_l3)
    rows, missing = [], []
    for R in PRE["regions_l3"]:
        if R not in present_codes:
            missing.append(R)
            continue
        inR = d[d.area_code_l3 == R]
        native_R = set(inR[inR.introduced == "0"].plant_name_id)
        G_R = set(inR[(inR.introduced == "0") & (inR.extinct == "0")].genus)
        N_R = set(inR[inR.introduced == "1"].plant_name_id) - native_R
        recorded_R = set(inR.plant_name_id)
        P_R = {s for s, regs in intro_regions.items() if (regs - {R}) and s not in recorded_R}
        nov_N = sum(sp_genus[s] not in G_R for s in N_R)
        nov_P = sum(sp_genus[s] not in G_R for s in P_R)
        table = [[nov_N, len(N_R) - nov_N], [nov_P, len(P_R) - nov_P]]
        odds = stats.contingency.odds_ratio(table, kind="sample").statistic if min(len(N_R), len(P_R)) else np.nan
        rows.append({"region": R, "n_native_genera": len(G_R), "n_naturalised": len(N_R), "n_pool": len(P_R),
                     "frac_novel_naturalised": nov_N / len(N_R) if N_R else np.nan,
                     "frac_novel_pool": nov_P / len(P_R) if P_R else np.nan, "odds_ratio": odds,
                     "p_greater": stats.fisher_exact(table, alternative="greater")[1],
                     "p_less": stats.fisher_exact(table, alternative="less")[1]})
    reg = pd.DataFrame(rows)
    reg.to_csv(os.path.join(DERIVED, "regions.csv"), index=False, float_format="%.6g")
    use = reg[reg.n_naturalised >= PRE["min_naturalised_per_region"]]
    n = len(use)
    a = PRE["alpha_one_sided"]
    n_sup = int(((use.odds_ratio > 1) & (use.p_greater < a)).sum())
    n_ref = int(((use.odds_ratio < 1) & (use.p_less < a)).sum())
    measured = {
        "value": round(n_ref / n, 4) if n else None,
        "unit": "fraction of regions where naturalised plants are significantly MORE likely than the colonist pool to belong to genera already native (OR < 1, one-sided p < 0.05)",
        "n": int(n),
        "uncertainty": f"regions significant in Darwin's direction: {n_sup}/{n}; opposite direction: {n_ref}/{n}",
        "extra": {
            "n_regions_supporting_direction": n_sup,
            "n_regions_opposite_direction": n_ref,
            "median_odds_ratio": float(use.odds_ratio.median()),
            "median_frac_naturalised_in_novel_genera": float(use.frac_novel_naturalised.median()),
            "median_frac_pool_in_novel_genera": float(use.frac_novel_pool.median()),
            "regions_missing_from_wcvp": missing,
            "regions_dropped_lt_min_naturalised": reg[reg.n_naturalised < PRE["min_naturalised_per_region"]].region.tolist(),
            "per_region": {r.region: {"OR": round(float(r.odds_ratio), 3), "novel_nat": round(float(r.frac_novel_naturalised), 3),
                                      "novel_pool": round(float(r.frac_novel_pool), 3), "n_nat": int(r.n_naturalised)}
                           for r in use.itertuples()},
        },
    }
    thr = PRE["region_share_threshold"]
    if n < PRE["min_regions"]:
        verdict = "inconclusive"
    elif n_sup / n >= thr:
        verdict = "supports"
    elif n_ref / n >= thr:
        verdict = "refutes"
    else:
        verdict = "mixed"
    print(json.dumps(measured, indent=1))
    print("verdict:", verdict)
    json.dump(LOG, open(os.path.join(DERIVED, "fetch_log.json"), "w"), indent=1)
    json.dump({"measured": measured, "verdict": verdict}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
