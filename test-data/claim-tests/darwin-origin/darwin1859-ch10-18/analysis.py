#!/usr/bin/env python3
"""Test darwin1859-ch10-18: later-Tertiary extinct forms of a continent are closely allied to
its living inhabitants (law of succession of types). Family level, terrestrial mammals.

Fossil side: PBDB Miocene-Pliocene occurrences per continent. Living side: GBIF family facets
per continent. Re-run:  python3 analysis.py
"""
import hashlib
import io
import itertools
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

PBDB = "https://paleobiodb.org/data1.2"
GBIF = "https://api.gbif.org/v1"
MAMMALIA_KEY = 359
CONTINENTS = ["Africa", "Eurasia", "North America", "South America", "Australia"]
PBDB_CC = {"Africa": ["AFR"], "Eurasia": ["EUR", "ASI"], "North America": ["NOA"], "South America": ["SOA"], "Australia": ["AUS"]}
GBIF_CONT = {"Africa": ["AFRICA"], "Eurasia": ["EUROPE", "ASIA"], "North America": ["NORTH_AMERICA"],
             "South America": ["SOUTH_AMERICA"], "Australia": ["OCEANIA"]}
MARINE_ORDERS = {"Cetacea", "Sirenia", "Desmostylia", "Artiodactyla/Cetacea", "Cetartiodactyla/Cetacea"}
MARINE_FAMILIES = {"Phocidae", "Otariidae", "Odobenidae", "Desmostylidae", "Paleoparadoxiidae", "Dugongidae", "Trichechidae",
                   "Prorastomidae", "Protosirenidae", "Balaenidae", "Balaenopteridae", "Delphinidae", "Phocoenidae", "Physeteridae",
                   "Ziphiidae", "Kogiidae", "Platanistidae", "Iniidae", "Pontoporiidae", "Monodontidae", "Eschrichtiidae", "Cetotheriidae",
                   "Kentriodontidae", "Squalodontidae", "Eurhinodelphinidae", "Allodelphinidae", "Aetiocetidae", "Eomysticetidae",
                   "Pelagiarctos", "Enaliarctidae", "Desmatophocidae", "Lipotidae", "Neobalaenidae", "Squalodelphinidae",
                   "Waipatiidae", "Albireonidae", "Inticetidae", "Pakicetidae", "Protocetidae", "Basilosauridae", "Ambulocetidae",
                   "Remingtonocetidae", "Mammalodontidae", "Llanocetidae", "Pinnipedia", "Odontoceti", "Mysticeti"}
MIN_FOSSIL_OCCS = 2
MIN_LIVING_RECORDS = 20
BASIS = ["PRESERVED_SPECIMEN", "HUMAN_OBSERVATION", "MATERIAL_SAMPLE", "OBSERVATION", "MACHINE_OBSERVATION", "OCCURRENCE", "MATERIAL_CITATION"]
FILES = []
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "delphi-claim-tests/0.1 (https://github.com/fractastical/delphi)"


def fetch(url, fname, params=None):
    path = os.path.join(DATA, fname)
    meta_path = path + ".meta.json"
    if os.path.exists(path) and os.path.exists(meta_path):
        with open(meta_path) as fh:
            FILES.append(json.load(fh))
        with open(path, "rb") as fh:
            return fh.read()
    for attempt in range(5):
        try:
            r = SESSION.get(url, params=params, timeout=900)
            if r.status_code == 200:
                break
        except requests.RequestException as e:
            print(f"  retry {attempt}: {e}", file=sys.stderr)
        time.sleep(10 * (attempt + 1))
    else:
        raise RuntimeError(f"could not fetch {url}")
    body = r.content
    meta = {"download_url": r.url, "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    with open(path, "wb") as fh:
        fh.write(body)
    with open(meta_path, "w") as fh:
        json.dump(meta, fh)
    FILES.append(meta)
    return body


def is_marine(order, family):
    return (order in MARINE_ORDERS) or (family in MARINE_FAMILIES)


def fossil_sets():
    fam_sets, gen_sets, gen_status = {}, {}, {}
    for cont in CONTINENTS:
        frames = []
        for cc in PBDB_CC[cont]:
            body = fetch(f"{PBDB}/occs/list.csv", f"pbdb_occs_Mammalia_{cc}.csv",
                         params={"base_name": "Mammalia", "interval": "Miocene,Pliocene", "idreso": "genus", "cc": cc, "show": "class"})
            text = body.decode("utf-8", "replace")
            if text.startswith('"occurrence_no"'):
                frames.append(pd.read_csv(io.StringIO(text), dtype=str))
        df = pd.concat(frames, ignore_index=True)
        df = df[df["family"].notna() & ~df["family"].str.startswith("NO_")]
        df = df[~df.apply(lambda r: is_marine(r["order"], r["family"]), axis=1)]
        fc = df["family"].value_counts()
        fam_sets[cont] = set(fc[fc >= MIN_FOSSIL_OCCS].index)
        df["genus_name"] = df["genus"].fillna("").str.replace(r"\s*\(.*?\)", "", regex=True).str.split().str[0]
        gc = df["genus_name"].value_counts()
        gen_sets[cont] = set(g for g in gc[gc >= MIN_FOSSIL_OCCS].index if g)
        print(f"  {cont}: {len(df)} fossil occurrences, {len(fam_sets[cont])} families, {len(gen_sets[cont])} genera", file=sys.stderr)
    return fam_sets, gen_sets


def living_sets():
    fam_counts, gen_counts = {c: {} for c in CONTINENTS}, {c: {} for c in CONTINENTS}
    for cont in CONTINENTS:
        for gc in GBIF_CONT[cont]:
            params = [("classKey", MAMMALIA_KEY), ("continent", gc), ("hasCoordinate", "true"), ("hasGeospatialIssue", "false"),
                      ("limit", 0), ("facetLimit", 100000), ("facet", "familyKey"), ("facet", "genusKey")]
            params += [("basisOfRecord", b) for b in BASIS]
            d = json.loads(fetch(f"{GBIF}/occurrence/search", f"gbif_Mammalia_{gc}.json", params=params))
            for fac in d["facets"]:
                tgt = fam_counts if fac["field"] == "FAMILY_KEY" else gen_counts
                for c in fac["counts"]:
                    tgt[cont][int(c["name"])] = tgt[cont].get(int(c["name"]), 0) + int(c["count"])
    keys = sorted({k for c in CONTINENTS for k in list(fam_counts[c]) + list(gen_counts[c])})

    def name_of(k):
        d = json.loads(fetch(f"{GBIF}/species/{k}", f"gbif_species_{k}.json"))
        return k, d.get("canonicalName"), d.get("rank"), d.get("order"), d.get("family")
    with ThreadPoolExecutor(max_workers=6) as ex:
        names = {k: (nm, rk, od, fm) for k, nm, rk, od, fm in ex.map(name_of, keys)}
    fam_sets, gen_sets = {}, {}
    for cont in CONTINENTS:
        fam_sets[cont] = {names[k][0] for k, n in fam_counts[cont].items()
                          if n >= MIN_LIVING_RECORDS and names[k][1] == "FAMILY" and not is_marine(names[k][2], names[k][0])}
        gen_sets[cont] = {names[k][0] for k, n in gen_counts[cont].items()
                          if n >= MIN_LIVING_RECORDS and names[k][1] == "GENUS" and not is_marine(names[k][2], names[k][3])}
    return fam_sets, gen_sets


def succession(fossil, living):
    S, O, rows = {}, {}, []
    for X in CONTINENTS:
        fx = fossil[X]
        if not fx:
            continue
        S[X] = len(fx & living[X]) / len(fx)
        others = [len(fx & living[Y]) / len(fx) for Y in CONTINENTS if Y != X]
        O[X] = float(np.mean(others))
        rows.append({"continent": X, "n_fossil_taxa": len(fx), "same_continent_living_fraction": S[X],
                     "other_continents_mean_living_fraction": O[X],
                     **{f"living_on_{Y.replace(' ', '_')}": len(fx & living[Y]) / len(fx) for Y in CONTINENTS}})
    obs = sum(S.values())
    perm_sums = []
    for perm in itertools.permutations(CONTINENTS):
        mapping = dict(zip(CONTINENTS, perm))
        perm_sums.append(sum(len(fossil[X] & living[mapping[X]]) / len(fossil[X]) for X in CONTINENTS if fossil[X]))
    perm_sums = np.array(perm_sums)
    n_ge = int(np.sum(perm_sums >= obs - 1e-12))
    return {"S": S, "O": O, "n_continents_S_gt_O": sum(1 for X in S if S[X] > O[X]),
            "pooled_ratio": float(np.mean(list(S.values())) / np.mean(list(O.values()))),
            "sum_S_observed": obs, "n_permutations_ge_observed": n_ge, "exact_p": n_ge / len(perm_sums)}, pd.DataFrame(rows)


def main():
    f_fam, f_gen = fossil_sets()
    l_fam, l_gen = living_sets()
    fam_res, fam_tab = succession(f_fam, l_fam)
    gen_res, gen_tab = succession(f_gen, l_gen)
    fam_tab.to_csv(os.path.join(DERIVED, "family_succession_by_continent.csv"), index=False)
    gen_tab.to_csv(os.path.join(DERIVED, "genus_succession_by_continent.csv"), index=False)
    pd.DataFrame([{"continent": c, "fossil_families": ";".join(sorted(f_fam[c])), "living_families": ";".join(sorted(l_fam[c]))}
                  for c in CONTINENTS]).to_csv(os.path.join(DERIVED, "family_sets.csv"), index=False)

    all_gt = fam_res["n_continents_S_gt_O"] == len(fam_res["S"])
    ratio_ok = fam_res["pooled_ratio"] >= 1.2
    perm_ok = fam_res["n_permutations_ge_observed"] == 1 or (fam_res["n_permutations_ge_observed"] <= 2 and fam_res["exact_p"] <= 1 / 60)
    if all_gt and ratio_ok and perm_ok:
        verdict = "supports"
    elif fam_res["n_continents_S_gt_O"] >= len(fam_res["S"]) - 1 and ratio_ok and perm_ok:
        verdict = "mixed"
    else:
        verdict = "refutes"

    with open(os.path.join(HERE, "result.json")) as fh:
        res = json.load(fh)
    pb = [f for f in FILES if "paleobiodb" in f["download_url"]]
    gf = [f for f in FILES if "occurrence/search" in f["download_url"]]
    gs = [f for f in FILES if "/species/" in f["download_url"]]
    res["datasets"] = [
        {"id": "pbdb-occurrences-mammalia-miocene-pliocene-by-continent",
         "name": "Paleobiology Database Mammalia occurrences, Miocene-Pliocene, genus-resolved, per continent (AFR, EUR, ASI, NOA, SOA, AUS)",
         "landing_url": "https://paleobiodb.org/", "doi": None, "version": "live API data1.2, retrieved " + pb[0]["retrieved_at"][:10],
         "license": "CC BY 4.0", "files": pb, "role": "later-Tertiary fossil families and genera per continent"},
        {"id": "gbif-occurrence-facets-mammalia-family-by-continent",
         "name": "GBIF occurrence search API, Mammalia, family and genus facets per continent (non-fossil, non-captive records)",
         "landing_url": "https://www.gbif.org/occurrence/search", "doi": None, "version": "live index, retrieved " + gf[0]["retrieved_at"][:10],
         "license": "mixed per publishing dataset (CC0, CC BY, CC BY-NC)", "files": gf, "role": "living families and genera per continent"},
        {"id": "gbif-species-api-family-names",
         "name": "GBIF Backbone Taxonomy species API (names, ranks and orders for family and genus keys)",
         "landing_url": "https://www.gbif.org/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c", "doi": "10.15468/39omei",
         "version": "live, retrieved " + gs[0]["retrieved_at"][:10], "license": "CC BY 4.0",
         "files": [{"download_url": GBIF + "/species/{key}", "retrieved_at": gs[0]["retrieved_at"], "byte_size": sum(f["byte_size"] for f in gs),
                    "sha256": hashlib.sha256("".join(sorted(f["sha256"] for f in gs)).encode()).hexdigest(),
                    "note": f"{len(gs)} per-key JSON responses; sha256 of the sorted concatenation of their digests"}],
         "role": "map GBIF keys to family/genus names and orders"},
    ]
    res["method"] = (
        "Miocene-Pliocene mammal occurrences were downloaded from PBDB for each continent and reduced to families (and genera) "
        f"with >= {MIN_FOSSIL_OCCS} occurrences, excluding marine orders and families. Living families (and genera) per continent were "
        f"taken from GBIF family/genus occurrence facets (>= {MIN_LIVING_RECORDS} non-fossil, non-captive records). For each continent "
        "the fraction of its fossil families living there today (S) was compared with the mean fraction living on each other continent "
        "(O), and the sum of S was compared with all 120 reassignments of living-family sets to continents."
    )
    res["measured"] = {
        "value": fam_res["pooled_ratio"],
        "unit": "ratio of mean same-continent survival fraction to mean other-continent survival fraction, later-Tertiary mammal families",
        "n": int(sum(len(v) for v in f_fam.values())),
        "uncertainty": f"exact permutation p = {fam_res['exact_p']:.4f} ({fam_res['n_permutations_ge_observed']} of 120 label permutations >= observed)",
        "extra": {"family_level": fam_res, "genus_level_extra": gen_res,
                  "n_fossil_families_by_continent": {c: len(f_fam[c]) for c in CONTINENTS},
                  "n_living_families_by_continent": {c: len(l_fam[c]) for c in CONTINENTS}},
    }
    res["verdict"] = verdict
    res["confidence"] = 0.8
    res["caveats"] = [
        "Family-level alliance is coarse; cosmopolitan families (Bovidae, Felidae, Canidae, Muridae) raise both same- and other-continent fractions and dilute the signal, while endemic families (marsupial and xenarthran families) carry it, as in Darwin's own examples.",
        "GBIF 'living on a continent' includes introduced and feral species (e.g. Muridae and Leporidae in Australia), which biases toward sharing with other continents and so against the claim.",
        "PBDB family assignments and GBIF backbone family names are mostly but not entirely harmonised; mismatched spellings or re-ranked families count as 'not living', equally on all continents.",
        "The Great American Biotic Interchange (c. 3 Ma) means part of South America's Pliocene fauna is of North American origin, which Darwin could not know; it makes the North/South America comparison conservative.",
        "Birds, molluscs and islands, also in the claim's scope, were not tested.",
    ]
    res["status"] = "complete"
    res["agent"]["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(HERE, "result.json"), "w") as fh:
        json.dump(res, fh, indent=2)
        fh.write("\n")
    print(json.dumps({"verdict": verdict, "family": fam_res, "genus": gen_res}, indent=2))


if __name__ == "__main__":
    main()
