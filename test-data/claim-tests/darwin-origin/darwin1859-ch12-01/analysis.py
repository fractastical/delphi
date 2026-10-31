#!/usr/bin/env python3
"""Test of darwin1859-ch12-01: fresh-water species of different classes have enormous ranges
and allied fresh-water species prevail throughout the world.

Data: GBIF occurrence search API, facet counts of speciesKey and genusKey per family and
continent. Response checksums go to derived/fetch_log.csv.gz; per-family statistics to
derived/family_stats.csv.
"""
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
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


def family_key(name, cls):
    kingdom = "Plantae" if cls == "Magnoliopsida" else "Animalia"
    d = get(API + "/species/match", {"name": name, "rank": "FAMILY", "kingdom": kingdom, "strict": "true"})
    if d.get("matchType") == "EXACT" and d.get("rank") == "FAMILY":
        return d["usageKey"]
    d = get(API + "/species", {"name": name, "rank": "FAMILY", "datasetKey": BACKBONE, "limit": 20})
    hits = [r for r in d.get("results", []) if r.get("canonicalName") == name and r.get("kingdom") == kingdom
            and r.get("taxonomicStatus") == "ACCEPTED"]
    return hits[0]["key"] if hits else None


def continent_facets(fkey, continent):
    params = [("taxonKey", fkey), ("continent", continent), ("hasCoordinate", "true"),
              ("hasGeospatialIssue", "false"), ("occurrenceStatus", "PRESENT"), ("year", PRE["year_range"]),
              ("facet", "speciesKey"), ("facet", "genusKey"), ("facetLimit", 100000), ("limit", 0)]
    params += [("basisOfRecord", b) for b in BASIS_ALLOWED]
    d = get(API + "/occurrence/search", params)
    out = {}
    for f in d["facets"]:
        out[f["field"].replace("_", "").lower()] = {int(c["name"]) for c in f["counts"] if c["count"] >= PRE["min_records_per_continent"]}
    return d["count"], out.get("specieskey", set()), out.get("genuskey", set())


def main():
    W = PRE["wide_range_continents"]
    fam_rows, sp_rows = [], []
    class_sets = {}
    for cls, groups in PRE["classes"].items():
        for habitat, fams in groups.items():
            sp_cont = defaultdict(set)
            gen_cont = defaultdict(set)
            for fam in fams:
                fkey = family_key(fam, cls)
                if fkey is None:
                    print("WARNING unresolved family", fam, file=sys.stderr)
                    continue
                n_tot = 0
                f_sp, f_gen = defaultdict(set), defaultdict(set)
                for cont in PRE["continents"]:
                    n, sps, gens = continent_facets(fkey, cont)
                    n_tot += n
                    for s_ in sps:
                        f_sp[s_].add(cont)
                        sp_cont[s_].add(cont)
                    for g in gens:
                        f_gen[g].add(cont)
                        gen_cont[g].add(cont)
                fam_rows.append({"class": cls, "habitat": habitat, "family": fam, "gbif_key": fkey, "n_records": n_tot,
                                 "n_species": len(f_sp), "n_genera": len(f_gen),
                                 "frac_species_ge3_continents": float(np.mean([len(v) >= W for v in f_sp.values()])) if f_sp else float("nan"),
                                 "frac_genera_ge3_continents": float(np.mean([len(v) >= W for v in f_gen.values()])) if f_gen else float("nan"),
                                 "mean_continents_per_species": float(np.mean([len(v) for v in f_sp.values()])) if f_sp else float("nan")})
                print(cls, habitat, fam, n_tot, len(f_sp), len(f_gen), flush=True)
            class_sets[(cls, habitat)] = (sp_cont, gen_cont)
            for s_, conts in sp_cont.items():
                sp_rows.append({"class": cls, "habitat": habitat, "n_continents": len(conts)})
    fam_df = pd.DataFrame(fam_rows)
    fam_df.to_csv(os.path.join(DERIVED, "family_stats.csv"), index=False)
    sp_df = pd.DataFrame(sp_rows)

    per_class = {}
    classes_used, n_pass_both, n_fail = [], 0, 0
    for cls in PRE["classes"]:
        fw_sp, fw_gen = class_sets[(cls, "freshwater")]
        te_sp, te_gen = class_sets[(cls, "terrestrial")]
        if len(fw_sp) < PRE["min_species_per_set"] or len(te_sp) < PRE["min_species_per_set"]:
            per_class[cls] = {"dropped": True, "n_species_fw": len(fw_sp), "n_species_terr": len(te_sp)}
            continue
        P_sp_fw = float(np.mean([len(v) >= W for v in fw_sp.values()]))
        P_sp_te = float(np.mean([len(v) >= W for v in te_sp.values()]))
        P_gen_fw = float(np.mean([len(v) >= W for v in fw_gen.values()]))
        P_gen_te = float(np.mean([len(v) >= W for v in te_gen.values()]))
        mw = mannwhitneyu([len(v) for v in fw_sp.values()], [len(v) for v in te_sp.values()], alternative="greater")
        ok = P_sp_fw > P_sp_te and P_gen_fw > P_gen_te
        classes_used.append(cls)
        n_pass_both += ok
        n_fail += (not ok)
        per_class[cls] = {
            "n_species_fw": len(fw_sp), "n_species_terr": len(te_sp), "n_genera_fw": len(fw_gen), "n_genera_terr": len(te_gen),
            "P_sp_freshwater": P_sp_fw, "P_sp_terrestrial": P_sp_te, "P_gen_freshwater": P_gen_fw, "P_gen_terrestrial": P_gen_te,
            "ratio_P_sp": P_sp_fw / P_sp_te if P_sp_te else None, "ratio_P_gen": P_gen_fw / P_gen_te if P_gen_te else None,
            "mean_continents_per_species_fw": float(np.mean([len(v) for v in fw_sp.values()])),
            "mean_continents_per_species_terr": float(np.mean([len(v) for v in te_sp.values()])),
            "mannwhitney_p_species_fw_greater": float(mw.pvalue), "both_criteria_met": bool(ok)}
    fw_all = sp_df[sp_df.habitat == "freshwater"].n_continents
    te_all = sp_df[sp_df.habitat == "terrestrial"].n_continents
    pooled = mannwhitneyu(fw_all, te_all, alternative="greater")
    measured = {
        "value": n_pass_both,
        "unit": f"classes (of {len(classes_used)} usable) in which both the proportion of species and of genera on >= {W} continents is higher for fresh-water than for terrestrial families",
        "n": int(len(sp_df)),
        "uncertainty": f"pooled one-sided Mann-Whitney on continents per species (fresh-water > terrestrial): p={pooled.pvalue:.2e}",
        "extra": {"per_class": per_class, "pooled_P_sp_freshwater": float((fw_all >= W).mean()),
                  "pooled_P_sp_terrestrial": float((te_all >= W).mean()),
                  "pooled_mean_continents_fw": float(fw_all.mean()), "pooled_mean_continents_terr": float(te_all.mean()),
                  "pooled_mannwhitney_p": float(pooled.pvalue), "classes_used": classes_used},
    }
    if len(classes_used) < 2:
        verdict = "inconclusive"
    elif n_pass_both == len(classes_used) and pooled.pvalue < 0.001:
        verdict = "supports"
    elif n_fail >= 2:
        verdict = "refutes"
    else:
        verdict = "mixed"
    print(json.dumps(measured, indent=1))
    print("verdict:", verdict)
    pd.DataFrame(FETCH_LOG).to_csv(os.path.join(DERIVED, "fetch_log.csv.gz"), index=False, compression="gzip")
    json.dump({"measured": measured, "verdict": verdict}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
