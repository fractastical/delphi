#!/usr/bin/env python3
"""Test of darwin1859-ch11-14: plants of lofty (incl. tropical) mountains and of the temperate
lowlands of both hemispheres are sometimes identical, much more often distinct but allied.

Data: GBIF occurrence search API facet counts (speciesKey, genusKey) for vascular plants
inside pre-registered bounding boxes and elevation bands. Response checksums are written
to derived/fetch_log.json; sharing statistics to derived/pair_sharing.csv.
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
from scipy.stats import binomtest

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)
RESULT = json.load(open(os.path.join(HERE, "result.json")))
PRE = RESULT["preregistration"]
API = "https://api.gbif.org/v1"
FETCH_LOG = []
S = requests.Session()
S.headers["User-Agent"] = "delphi-claim-tests/0.1 (https://github.com/fractastical/delphi)"
BASIS_ALLOWED = ["PRESERVED_SPECIMEN", "HUMAN_OBSERVATION", "MACHINE_OBSERVATION",
                 "MATERIAL_SAMPLE", "OBSERVATION", "OCCURRENCE", "MATERIAL_CITATION"]


def get(url, params=None, tries=6):
    for attempt in range(tries):
        try:
            time.sleep(0.5)
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


def facet_set(region, facet):
    params = [("taxonKey", PRE["taxon_key"]), ("geometry", bbox_wkt(region["bbox"])),
              ("elevation", f"{region['elevation'][0]},{region['elevation'][1]}"),
              ("hasCoordinate", "true"), ("hasGeospatialIssue", "false"), ("occurrenceStatus", "PRESENT"),
              ("year", PRE["year_range"]), ("facet", facet), ("facetLimit", 100000), ("limit", 0)]
    params += [("basisOfRecord", b) for b in BASIS_ALLOWED]
    d = get(API + "/occurrence/search", params)
    return d["count"], {int(c["name"]) for c in d["facets"][0]["counts"] if c["count"] >= PRE["min_records"]}


def main():
    regions = PRE["regions"]
    sp, gen, rows = {}, {}, []
    for name, r in regions.items():
        n, sp[name] = facet_set(r, "speciesKey")
        _, gen[name] = facet_set(r, "genusKey")
        rows.append({"region": name, "type": r["type"], "n_records": n, "n_species": len(sp[name]), "n_genera": len(gen[name])})
        print(name, n, len(sp[name]), len(gen[name]), flush=True)
    reg_df = pd.DataFrame(rows)
    reg_df.to_csv(os.path.join(DERIVED, "region_counts.csv"), index=False)

    def f_sp(a, b):
        return len(sp[a] & sp[b]) / len(sp[a])

    def f_gen(a, b):
        return len(gen[a] & gen[b]) / len(gen[a])

    mountains = [k for k, v in regions.items() if v["type"] == "tropical-mountain" and len(sp[k]) >= 50]
    dropped = [k for k, v in regions.items() if v["type"] == "tropical-mountain" and len(sp[k]) < 50]
    controls = [regions[m]["control"] for m in mountains]
    north = [k for k, v in regions.items() if v["type"] == "north-temperate-lowland"]
    south = [k for k, v in regions.items() if v["type"] == "south-temperate-lowland"]
    temperate = north + south

    pair_rows = []
    A_ok = B_ok = 0
    for m in mountains:
        c = regions[m]["control"]
        for L in temperate:
            fs, fg, fgc = f_sp(m, L), f_gen(m, L), f_gen(c, L)
            a = (0 < fs < 0.5 * fg)
            b = fg > fgc
            A_ok += a
            B_ok += b
            pair_rows.append({"mountain": m, "temperate": L, "f_sp_mountain": fs, "f_gen_mountain": fg,
                              "f_sp_control": f_sp(c, L), "f_gen_control": fgc,
                              "shared_species": len(sp[m] & sp[L]), "shared_genera": len(gen[m] & gen[L]),
                              "A_identical_minority": a, "B_mountain_more_allied_than_lowland": b})
    pairs = pd.DataFrame(pair_rows)
    pairs.to_csv(os.path.join(DERIVED, "pair_sharing.csv"), index=False)
    n_pairs = len(pairs)

    ns_rows = []
    C_ok = 0
    for n_ in north:
        for s_ in south:
            fg = f_gen(n_, s_)
            fgc = float(np.mean([f_gen(c, s_) for c in controls]))
            ok = fg > fgc
            C_ok += ok
            ns_rows.append({"north": n_, "south": s_, "f_sp": f_sp(n_, s_), "f_gen": fg,
                            "mean_f_gen_tropical_lowland_to_south": fgc, "C_ok": ok})
    ns = pd.DataFrame(ns_rows)
    ns.to_csv(os.path.join(DERIVED, "north_south_sharing.csv"), index=False)

    p_B = binomtest(B_ok, n_pairs, 0.5, alternative="greater").pvalue
    measured = {
        "value": B_ok,
        "unit": f"of {n_pairs} (tropical mountain, temperate lowland) pairs in which the mountain flora shares a larger fraction of its genera with the temperate flora than the adjacent tropical lowland flora does",
        "n": n_pairs,
        "uncertainty": f"one-sided binomial sign test vs 0.5: p={p_B:.2e}",
        "extra": {
            "A_pairs_identical_species_present_but_minority": int(A_ok),
            "B_pairs_mountain_more_allied_than_tropical_lowland": int(B_ok),
            "C_north_south_pairs_more_allied_than_tropical_lowland": int(C_ok),
            "n_north_south_pairs": int(len(ns)),
            "median_f_sp_mountain_temperate": float(pairs.f_sp_mountain.median()),
            "median_f_gen_mountain_temperate": float(pairs.f_gen_mountain.median()),
            "median_f_gen_control_temperate": float(pairs.f_gen_control.median()),
            "median_f_sp_north_south": float(ns.f_sp.median()),
            "median_f_gen_north_south": float(ns.f_gen.median()),
            "median_f_gen_tropical_lowland_south": float(ns.mean_f_gen_tropical_lowland_to_south.median()),
            "per_mountain_mean_f_gen": {m: float(pairs[pairs.mountain == m].f_gen_mountain.mean()) for m in mountains},
            "per_mountain_mean_f_gen_control": {m: float(pairs[pairs.mountain == m].f_gen_control.mean()) for m in mountains},
            "mountains_used": mountains, "mountains_dropped_lt_50_species": dropped,
            "binomial_p_B": float(p_B),
        },
    }
    if len(mountains) < 3:
        verdict = "inconclusive"
    else:
        need = 20 * n_pairs / 24  # pre-registered 20 of 24, scaled if a mountain was dropped
        if A_ok >= need and B_ok >= need and p_B < 0.01 and C_ok >= 7:
            verdict = "supports"
        elif B_ok <= 12 * n_pairs / 24 or C_ok <= 4:
            verdict = "refutes"
        else:
            verdict = "mixed"
    print(json.dumps(measured, indent=1))
    print("verdict:", verdict)
    json.dump(FETCH_LOG, open(os.path.join(DERIVED, "fetch_log.json"), "w"), indent=0)
    json.dump({"measured": measured, "verdict": verdict}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
