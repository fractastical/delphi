#!/usr/bin/env python3
"""Test darwin1859-ch12-18: closer relatives are closer together in time and space.

Space: extant birds, patristic distance on the BirdTree Hackett MCC tree (as shipped with
AVONET) vs great-circle distance between AVONET range centroids.
Time: PBDB genera of Mammalia and Mollusca, |difference in first-appearance age| for
same-family vs different-family (same order) genus pairs.

Re-run:  python3 analysis.py   (downloads AVONET ELEData.zip, 17.8 MB, and two PBDB taxa lists)
"""
import hashlib
import io
import json
import os
import re
import sys
import time
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

ZIP_URL = "https://ndownloader.figshare.com/files/38429873"
CSV_IN_ZIP = "ELEData/TraitData/AVONET1_BirdLife.csv"
TREE_IN_ZIP = "ELEData/PhylogeneticData/HackettStage1_0001_1000_MCCTreeTargetHeights.nex"
XWALK_IN_ZIP = "ELEData/PhylogeneticData/BirdLife-BirdTree crosswalk.csv"
PBDB = "https://paleobiodb.org/data1.2"
GROUPS = ["Mammalia", "Mollusca"]
N_PAIRS = 2_000_000
N_PERM = 99
PAIRS_PER_ORDER_CAP = 500_000
RNG = np.random.default_rng(20261031)
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


# ----------------------------------------------------------------------------- tree utilities
def parse_newick(s):
    children, parent, label, brlen = [[]], [-1], [None], [0.0]
    cur, i, n = 0, 0, len(s)
    while i < n:
        ch = s[i]
        if ch == "(":
            children.append([]); parent.append(cur); label.append(None); brlen.append(0.0)
            children[cur].append(len(children) - 1); cur = len(children) - 1; i += 1
        elif ch == ",":
            cur = parent[cur]
            children.append([]); parent.append(cur); label.append(None); brlen.append(0.0)
            children[cur].append(len(children) - 1); cur = len(children) - 1; i += 1
        elif ch == ")":
            cur = parent[cur]; i += 1
        elif ch == ":":
            j = i + 1
            while j < n and s[j] not in ",();":
                j += 1
            brlen[cur] = float(s[i + 1:j]); i = j
        elif ch == ";":
            break
        else:
            j = i
            while j < n and s[j] not in ",():;":
                j += 1
            label[cur] = s[i:j].strip().strip("'"); i = j
    return children, parent, label, brlen


def load_bird_tree(zpath):
    with zipfile.ZipFile(zpath) as z:
        raw = z.read(TREE_IN_ZIP).decode("utf-8", "replace")
    txt = re.sub(r"\[[^\]]*\]", "", raw)
    translate = {}
    m = re.search(r"translate\s+(.*?);", txt, re.S | re.I)
    if m:
        for line in m.group(1).split(","):
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                translate[parts[0]] = parts[1].strip().strip("'")
    m = re.search(r"tree\s+[^=]*=\s*(\(.*?;)", txt, re.S | re.I)
    children, parent, label, brlen = parse_newick(m.group(1))
    label = [translate.get(l, l) if l else l for l in label]
    depth = [0.0] * len(children)
    order = [0]
    for node in order:
        for c in children[node]:
            depth[c] = depth[node] + brlen[c]
            order.append(c)
    tips = [i for i in range(len(children)) if not children[i]]
    tip_index = {t: k for k, t in enumerate(tips)}
    # patristic distance matrix via tips-below sets, processing nodes bottom-up
    n = len(tips)
    D = np.zeros((n, n), dtype=np.float32)
    below = [None] * len(children)
    for node in reversed(order):
        if not children[node]:
            below[node] = np.array([tip_index[node]])
            continue
        sets = [below[c] for c in children[node]]
        for a in range(len(sets)):
            for b in range(a + 1, len(sets)):
                A, B = sets[a], sets[b]
                dep = np.array([depth[tips[i]] for i in A], dtype=np.float32)[:, None] + \
                      np.array([depth[tips[j]] for j in B], dtype=np.float32)[None, :] - 2 * depth[node]
                D[np.ix_(A, B)] = dep
                D[np.ix_(B, A)] = dep.T
        below[node] = np.concatenate(sets)
        for c in children[node]:
            below[c] = None
    names = [label[t] for t in tips]
    return names, D


def haversine(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# ----------------------------------------------------------------------------- space clause
def space_clause():
    zpath = os.path.join(DATA, "AVONET_ELEData.zip")
    fetch(ZIP_URL, "AVONET_ELEData.zip")
    with zipfile.ZipFile(zpath) as z:
        av = pd.read_csv(io.BytesIO(z.read(CSV_IN_ZIP)), na_values=["NA"])
        xw = pd.read_csv(io.BytesIO(z.read(XWALK_IN_ZIP)), na_values=["NA"])
    names, D = load_bird_tree(zpath)
    tree_names = {nm.replace("_", " "): k for k, nm in enumerate(names)}
    # one-to-one BirdLife <-> BirdTree matches only
    xw = xw.dropna(subset=["Species1", "Species3"])
    xw = xw[~xw["Species1"].duplicated(keep=False) & ~xw["Species3"].duplicated(keep=False)]
    av = av.dropna(subset=["Centroid.Latitude", "Centroid.Longitude"]).merge(xw[["Species1", "Species3"]], on="Species1")
    av["tip"] = av["Species3"].map(tree_names)
    av = av.dropna(subset=["tip"]).reset_index(drop=True)
    av["tip"] = av["tip"].astype(int)
    n = len(av)
    print(f"birds matched: {n}", file=sys.stderr)
    lat = av["Centroid.Latitude"].to_numpy(); lon = av["Centroid.Longitude"].to_numpy()
    tips = av["tip"].to_numpy()
    genus = av["Species1"].str.split().str[0].to_numpy()
    fam = av["Family1"].to_numpy(); order = av["Order1"].to_numpy()

    i = RNG.integers(0, n, N_PAIRS); j = RNG.integers(0, n, N_PAIRS)
    keep = i != j
    i, j = i[keep], j[keep]
    phylo = D[tips[i], tips[j]].astype(float)
    geo = haversine(lat[i], lon[i], lat[j], lon[j])
    rho_obs = float(stats.spearmanr(phylo, geo).statistic)
    perm_rhos = []
    for _ in range(N_PERM):
        perm = RNG.permutation(n)
        g = haversine(lat[perm][i], lon[perm][i], lat[perm][j], lon[perm][j])
        perm_rhos.append(float(stats.spearmanr(phylo, g).statistic))
    perm_rhos = np.array(perm_rhos)
    p_s1 = float((np.sum(perm_rhos >= rho_obs) + 1) / (N_PERM + 1))
    congeneric = genus[i] == genus[j]
    confamilial = (fam[i] == fam[j]) & ~congeneric
    conordinal = (order[i] == order[j]) & (fam[i] != fam[j])
    med = {"congeneric": float(np.median(geo[congeneric])), "confamilial_not_congeneric": float(np.median(geo[confamilial])),
           "same_order_different_family": float(np.median(geo[conordinal])),
           "different_order": float(np.median(geo[order[i] != order[j]]))}
    cnt = {"congeneric": int(congeneric.sum()), "confamilial_not_congeneric": int(confamilial.sum()),
           "same_order_different_family": int(conordinal.sum()), "different_order": int((order[i] != order[j]).sum())}
    s1 = rho_obs > 0 and p_s1 <= 0.01
    s2 = med["congeneric"] < med["confamilial_not_congeneric"] < med["same_order_different_family"]
    pd.DataFrame({"relatedness": list(med), "median_centroid_distance_km": list(med.values()), "n_pairs": list(cnt.values())}).to_csv(
        os.path.join(DERIVED, "bird_centroid_distance_by_relatedness.csv"), index=False)
    return {"n_species": n, "n_pairs": int(len(i)), "spearman_rho_phylo_vs_geo": rho_obs,
            "perm_p": p_s1, "perm_rho_max": float(perm_rhos.max()), "perm_rho_min": float(perm_rhos.min()),
            "median_geo_km_by_relatedness": med, "n_pairs_by_relatedness": cnt, "S1_pass": bool(s1), "S2_pass": bool(s2),
            "pass": bool(s1 and s2)}


# ----------------------------------------------------------------------------- time clause
def time_clause(group):
    body = fetch(f"{PBDB}/taxa/list.json", f"pbdb_taxa_{group}.json",
                 params={"base_name": group, "rank": "genus", "show": "app,class", "vocab": "pbdb"})
    recs = json.loads(body)["records"]
    rows = []
    for r in recs:
        if r.get("taxon_no") != r.get("accepted_no") or r.get("accepted_rank") != "genus":
            continue
        fam, ordr = r.get("family"), r.get("order")
        if not fam or not ordr or fam.startswith("NO_") or ordr.startswith("NO_") or r.get("firstapp_max_ma") is None:
            continue
        rows.append({"genus": r["accepted_name"], "family": fam, "order": ordr,
                     "fad_mid": (float(r["firstapp_max_ma"]) + float(r["firstapp_min_ma"])) / 2})
    df = pd.DataFrame(rows)
    print(f"{group}: {len(df)} genera, {df['family'].nunique()} families, {df['order'].nunique()} orders", file=sys.stderr)

    same_all, diff_all = [], []
    perm_same = [[] for _ in range(N_PERM)]
    perm_diff = [[] for _ in range(N_PERM)]
    n_orders_used = 0
    for ordr, g in df.groupby("order"):
        m = len(g)
        if m < 2 or g["family"].nunique() < 2:
            continue
        fad = g["fad_mid"].to_numpy(); famc = pd.factorize(g["family"])[0]
        total = m * (m - 1) // 2
        if total <= PAIRS_PER_ORDER_CAP:
            iu, ju = np.triu_indices(m, 1)
        else:
            iu = RNG.integers(0, m, PAIRS_PER_ORDER_CAP); ju = RNG.integers(0, m, PAIRS_PER_ORDER_CAP)
            k = iu != ju; iu, ju = iu[k], ju[k]
        d = np.abs(fad[iu] - fad[ju])
        same = famc[iu] == famc[ju]
        if same.sum() == 0:
            continue
        n_orders_used += 1
        same_all.append(d[same]); diff_all.append(d[~same])
        for p in range(N_PERM):
            pf = RNG.permutation(famc)
            ps = pf[iu] == pf[ju]
            perm_same[p].append(d[ps]); perm_diff[p].append(d[~ps])
    same_all = np.concatenate(same_all); diff_all = np.concatenate(diff_all)
    obs = float(np.median(diff_all) - np.median(same_all))
    perm_stats = np.array([np.median(np.concatenate(perm_diff[p])) - np.median(np.concatenate(perm_same[p])) for p in range(N_PERM)])
    p_val = float((np.sum(perm_stats >= obs) + 1) / (N_PERM + 1))
    return {"n_genera": int(len(df)), "n_orders_used": n_orders_used,
            "n_same_family_pairs": int(len(same_all)), "n_different_family_pairs": int(len(diff_all)),
            "median_abs_dFAD_same_family_myr": float(np.median(same_all)),
            "median_abs_dFAD_different_family_same_order_myr": float(np.median(diff_all)),
            "difference_myr": obs, "perm_p": p_val, "perm_diff_max": float(perm_stats.max()),
            "pass": bool(obs > 0 and p_val <= 0.01)}


def main():
    space = space_clause()
    times = {g: time_clause(g) for g in GROUPS}
    time_pass = all(t["pass"] for t in times.values())
    verdict = "supports" if space["pass"] and time_pass else ("mixed" if space["pass"] or time_pass else "refutes")

    with open(os.path.join(HERE, "result.json")) as fh:
        res = json.load(fh)
    av_files = [f for f in FILES if "figshare" in f["download_url"]]
    pb_files = [f for f in FILES if "paleobiodb" in f["download_url"]]
    res["datasets"] = [
        {"id": "avonet-tobias2022-figshare",
         "name": "AVONET ELEData.zip: TraitData/AVONET1_BirdLife.csv (range centroids, taxonomy), PhylogeneticData/HackettStage1_0001_1000_MCCTreeTargetHeights.nex (BirdTree Hackett MCC tree, 6670 species) and BirdLife-BirdTree crosswalk.csv",
         "landing_url": "https://figshare.com/articles/dataset/AVONET_morphological_ecological_and_geographical_data_for_all_birds_Tobias_et_al_2021_Ecology_Letters_/16586228",
         "doi": "10.6084/m9.figshare.16586228.v7", "version": "figshare v7; paper doi:10.1111/ele.13898; tree from Jetz et al. 2012 doi:10.1038/nature11631",
         "license": "CC BY 4.0", "files": av_files, "role": "phylogenetic distance, range centroids and taxonomy of extant birds"},
        {"id": "pbdb-taxa-first-appearances-mammalia-mollusca",
         "name": "Paleobiology Database taxa lists (genus rank) with first/last appearance ages and classification for Mammalia and Mollusca",
         "landing_url": "https://paleobiodb.org/", "doi": None, "version": "live API data1.2, retrieved " + pb_files[0]["retrieved_at"][:10],
         "license": "CC BY 4.0", "files": pb_files, "role": "first-appearance ages and family/order of fossil genera"},
    ]
    res["method"] = (
        f"Space: {space['n_species']} bird species with a one-to-one BirdLife-BirdTree name match, a tree tip and an AVONET range "
        f"centroid. Patristic distances were computed on the MCC tree; {space['n_pairs']} random species pairs were drawn and the "
        f"Spearman correlation between patristic and great-circle centroid distance was compared with {N_PERM} permutations of "
        f"centroids among species; medians of centroid distance were tabulated for congeneric, confamilial and same-order pairs. "
        f"Time: PBDB accepted genera with family, order and first-appearance ages; within each order, genus pairs (all pairs, or "
        f"{PAIRS_PER_ORDER_CAP} random pairs for very large orders) were split into same-family and different-family, and the "
        f"difference of medians of |dFAD| was compared with {N_PERM} permutations of family labels within orders."
    )
    res["measured"] = {
        "value": space["spearman_rho_phylo_vs_geo"],
        "unit": "Spearman rho between patristic distance and centroid great-circle distance, bird species pairs",
        "n": space["n_pairs"],
        "uncertainty": f"permutation p = {space['perm_p']:.3f}; permuted rho range {space['perm_rho_min']:.4f} to {space['perm_rho_max']:.4f}",
        "extra": {"space_birds": space, "time_fossil": times, "time_clause_pass": time_pass},
    }
    res["verdict"] = verdict
    res["confidence"] = 0.75
    res["caveats"] = [
        "The overall Spearman correlation between patristic and geographic distance is small (about 0.03) although far outside the permutation null; the relationship is concentrated at shallow phylogenetic depth (congeneric and confamilial pairs) and saturates at the order level, where median centroid distance is no smaller within than between orders.",
        "Pooled permutation nulls for the fossil clause are not centred on zero because orders differ in family structure and age spread; the observed differences are judged against that null, not against zero.",
        "Space is tested in one class (birds) and time in two fossil groups at genus level; the claim is stated for all organisms, living and fossil.",
        "Range centroids collapse each species to a point; sister species with adjacent but large ranges can appear far apart, which weakens rather than inflates the correlation.",
        "Species limits in birds have historically been drawn partly on geography (allopatric forms), which can tighten the congeneric-pair pattern by construction.",
        "Fossil first appearances are truncated by sampling and concentrated in well-sampled basins and intervals; genera in the same family are often described from the same formations, which can make same-family FADs look closer than they are.",
        "Family and order assignments in PBDB are of uneven quality, especially for Mollusca; genera with unassigned family or order were dropped.",
        "Patristic distance on the BirdTree MCC tree is a model-based divergence estimate, a modern proxy for Darwin's relatedness by descent.",
    ]
    res["status"] = "complete"
    res["agent"]["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(HERE, "result.json"), "w") as fh:
        json.dump(res, fh, indent=2)
        fh.write("\n")
    print(json.dumps({"verdict": verdict, "space": space, "time": times}, indent=2))


if __name__ == "__main__":
    main()
