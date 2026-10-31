#!/usr/bin/env python3
"""Test of darwin1859-ch11-03: affinity of the productions of the same continent across
different stations (habitats), versus the same station on different continents.

Data: GBIF occurrence search API (facet counts of genusKey / familyKey inside fixed
bounding boxes). Re-running fetches live data, so counts drift slowly as GBIF grows; the
retrieval times and SHA-256 of every response are written to derived/fetch_log.json.
"""
import hashlib
import itertools
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from scipy.stats import mannwhitneyu

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)
RESULT = json.load(open(os.path.join(HERE, "result.json")))
PRE = RESULT["preregistration"]
API = "https://api.gbif.org/v1"
FETCH_LOG = []
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "delphi-claim-tests/0.1 (https://github.com/fractastical/delphi)"


def get(url, params=None, tries=5):
    for attempt in range(tries):
        try:
            time.sleep(0.5)
            r = SESSION.get(url, params=params, timeout=120)
            if r.status_code == 200:
                FETCH_LOG.append({
                    "download_url": r.url,
                    "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "byte_size": len(r.content),
                    "sha256": hashlib.sha256(r.content).hexdigest(),
                })
                return r.json()
            print("HTTP", r.status_code, r.url, file=sys.stderr)
        except requests.RequestException as e:
            print("retry", attempt, e, file=sys.stderr)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError("GBIF request failed: " + url)


def bbox_wkt(b):
    w, s, e, n = b
    return f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"


BASIS_ALLOWED = ["PRESERVED_SPECIMEN", "HUMAN_OBSERVATION", "MACHINE_OBSERVATION",
                 "MATERIAL_SAMPLE", "OBSERVATION", "OCCURRENCE", "MATERIAL_CITATION"]


def facet_counts(taxon_key, bbox, facet):
    params = [("taxonKey", taxon_key), ("geometry", bbox_wkt(bbox)), ("hasCoordinate", "true"),
              ("hasGeospatialIssue", "false"), ("occurrenceStatus", "PRESENT"),
              ("year", PRE["year_range"].replace("-", ",")), ("facet", facet),
              ("facetLimit", 50000), ("limit", 0)] + [("basisOfRecord", b) for b in BASIS_ALLOWED]
    d = get(API + "/occurrence/search", params)
    counts = {int(c["name"]): c["count"] for c in d["facets"][0]["counts"]}
    return d["count"], counts


def main():
    # Resolve excluded genera to GBIF keys (kingdom fixed to avoid homonyms).
    # Homonyms (e.g. Mus, Columba) make species/match fall back to the kingdom, so look the
    # accepted backbone genus up directly and keep the vertebrate one.
    BACKBONE = "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"
    excluded_keys = {}
    for name in PRE["excluded_genera"]:
        d = get(API + "/species", {"name": name, "rank": "GENUS", "datasetKey": BACKBONE, "limit": 50})
        hits = [r for r in d.get("results", []) if r.get("canonicalName") == name and r.get("kingdom") == "Animalia"
                and r.get("class") in ("Mammalia", "Aves") and r.get("taxonomicStatus") == "ACCEPTED"]
        if hits:
            excluded_keys[name] = hits[0]["key"]
        else:
            print("WARNING: could not resolve excluded genus", name, file=sys.stderr)
    print("excluded genus keys:", excluded_keys)

    # Verify group keys resolve to the named taxa.
    for gname, key in PRE["groups"].items():
        d = get(API + f"/species/{key}")
        assert d["canonicalName"] == gname, (gname, d.get("canonicalName"))

    regions = PRE["regions"]
    min_rec = PRE["min_records_per_genus"]
    sets = {}   # (group, region, level) -> set of keys
    region_rows = []
    for gname, key in PRE["groups"].items():
        for rname, r in regions.items():
            total, gen = facet_counts(key, r["bbox"], "genusKey")
            _, fam = facet_counts(key, r["bbox"], "familyKey")
            gset = {k for k, c in gen.items() if c >= min_rec and k not in excluded_keys.values()}
            fset = {k for k, c in fam.items() if c >= min_rec}
            sets[(gname, rname, "genus")] = gset
            sets[(gname, rname, "family")] = fset
            region_rows.append({"group": gname, "region": rname, "continent": r["continent"],
                                "habitat": r["habitat"], "n_records": total,
                                "n_genera": len(gset), "n_families": len(fset)})
            print(gname, rname, total, len(gset), len(fset), flush=True)
    region_df = pd.DataFrame(region_rows)
    region_df.to_csv(os.path.join(DERIVED, "region_group_counts.csv"), index=False)

    def sorensen(a, b):
        return 2 * len(a & b) / (len(a) + len(b)) if (a or b) else float("nan")

    pair_rows = []
    for gname in PRE["groups"]:
        for r1, r2 in itertools.combinations(regions, 2):
            same_cont = regions[r1]["continent"] == regions[r2]["continent"]
            same_hab = regions[r1]["habitat"] == regions[r2]["habitat"]
            if same_cont and not same_hab:
                cat = "within-continent/different-habitat"
            elif not same_cont and same_hab:
                cat = "between-continent/same-habitat"
            else:
                cat = "between-continent/different-habitat"
            pair_rows.append({"group": gname, "region_a": r1, "region_b": r2, "category": cat,
                              "sorensen_genus": sorensen(sets[(gname, r1, "genus")], sets[(gname, r2, "genus")]),
                              "sorensen_family": sorensen(sets[(gname, r1, "family")], sets[(gname, r2, "family")]),
                              "shared_genera": len(sets[(gname, r1, "genus")] & sets[(gname, r2, "genus")])})
    pairs = pd.DataFrame(pair_rows)
    pairs.to_csv(os.path.join(DERIVED, "pair_similarity.csv"), index=False)

    WI, BS, BD = ("within-continent/different-habitat", "between-continent/same-habitat",
                  "between-continent/different-habitat")
    per_group = {}
    n_groups_pass = 0
    underpowered_groups = []
    for gname in PRE["groups"]:
        p = pairs[pairs.group == gname]
        m = {cat: float(p[p.category == cat].sorensen_genus.mean()) for cat in (WI, BS, BD)}
        mf = {cat: float(p[p.category == cat].sorensen_family.mean()) for cat in (WI, BS, BD)}
        per_group[gname] = {"mean_sorensen_genus": m, "mean_sorensen_family": mf,
                            "min_genera_in_a_region": int(region_df[region_df.group == gname].n_genera.min())}
        if m[WI] > m[BS]:
            n_groups_pass += 1
        if region_df[region_df.group == gname].n_genera.min() < 20:
            underpowered_groups.append(gname)
    wi = pairs[pairs.category == WI].sorensen_genus.dropna()
    bs = pairs[pairs.category == BS].sorensen_genus.dropna()
    u_greater = mannwhitneyu(wi, bs, alternative="greater")
    u_less = mannwhitneyu(wi, bs, alternative="less")
    wif = pairs[pairs.category == WI].sorensen_family.dropna()
    bsf = pairs[pairs.category == BS].sorensen_family.dropna()
    u_fam = mannwhitneyu(wif, bsf, alternative="greater")

    measured = {
        "value": n_groups_pass,
        "unit": "groups (of 5) where within-continent/different-habitat mean genus Sørensen > between-continent/same-habitat mean",
        "n": int(len(pairs)),
        "uncertainty": f"pooled one-sided Mann-Whitney (within > between-same-habitat), genus level: U={u_greater.statistic:.0f}, p={u_greater.pvalue:.2e}",
        "extra": {
            "pooled_mean_sorensen_genus": {WI: float(wi.mean()), BS: float(bs.mean()),
                                           BD: float(pairs[pairs.category == BD].sorensen_genus.mean())},
            "pooled_mean_sorensen_family": {WI: float(wif.mean()), BS: float(bsf.mean())},
            "mannwhitney_p_within_greater_genus": float(u_greater.pvalue),
            "mannwhitney_p_within_less_genus": float(u_less.pvalue),
            "mannwhitney_p_within_greater_family": float(u_fam.pvalue),
            "n_pairs_within": int(len(wi)), "n_pairs_between_same_habitat": int(len(bs)),
            "per_group": per_group,
            "underpowered_groups": underpowered_groups,
            "excluded_genus_keys": excluded_keys,
        },
    }
    if len(PRE["groups"]) - len(underpowered_groups) < 4:
        verdict = "inconclusive"
    elif n_groups_pass >= 4 and u_greater.pvalue < 0.01:
        verdict = "supports"
    elif n_groups_pass <= 2 or u_less.pvalue < 0.05:
        verdict = "refutes"
    else:
        verdict = "mixed"
    print(json.dumps(measured, indent=1))
    print("verdict:", verdict)
    json.dump(FETCH_LOG, open(os.path.join(DERIVED, "fetch_log.json"), "w"), indent=0)
    json.dump({"measured": measured, "verdict": verdict}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
