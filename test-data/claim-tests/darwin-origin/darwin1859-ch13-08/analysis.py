#!/usr/bin/env python3
"""Test darwin1859-ch13-08: distinct lineages adapted to similar conditions converge in
external form; such resemblances conceal relationship between groups but indicate affinity
within a group. Data: AVONET (Tobias et al. 2022), BirdLife taxonomy version.

Re-run:  python3 analysis.py   (downloads the 17.8 MB AVONET ELEData.zip into ./data)
"""
import hashlib
import io
import json
import os
import sys
import time
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

ZIP_URL = "https://ndownloader.figshare.com/files/38429873"  # AVONET figshare article 16586228, ELEData.zip
CSV_IN_ZIP = "ELEData/TraitData/AVONET1_BirdLife.csv"
TRAITS = ["Beak.Length_Culmen", "Beak.Length_Nares", "Beak.Width", "Beak.Depth", "Tarsus.Length",
          "Wing.Length", "Kipps.Distance", "Secondary1", "Hand-Wing.Index", "Tail.Length", "Mass"]
K = 5
N_PERM = 200
CHUNK = 400
RNG = np.random.default_rng(20261031)
FILES = []


def fetch(url, fname):
    path = os.path.join(DATA, fname)
    meta_path = path + ".meta.json"
    if os.path.exists(path) and os.path.exists(meta_path):
        with open(meta_path) as fh:
            FILES.append(json.load(fh))
        return path
    for attempt in range(5):
        try:
            r = requests.get(url, timeout=600, headers={"User-Agent": "delphi-claim-tests/0.1"})
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
    return path


def kappa(y_true, y_pred):
    labels, t = np.unique(np.concatenate([y_true, y_pred]), return_inverse=True)
    t_true, t_pred = t[: len(y_true)], t[len(y_true):]
    po = float(np.mean(t_true == t_pred))
    pt = np.bincount(t_true, minlength=len(labels)) / len(t_true)
    pp = np.bincount(t_pred, minlength=len(labels)) / len(t_pred)
    pe = float(np.sum(pt * pp))
    return (po - pe) / (1 - pe) if pe < 1 else 0.0


def knn_predict(X, labels, k, exclude_same_group=None):
    """Leave-one-out k-NN (majority vote, ties -> nearest). exclude_same_group: array of group
    ids; neighbours sharing the query's group id are excluded from the pool (e.g. congeners)."""
    n = len(X)
    pred = np.empty(n, dtype=object)
    sq = np.sum(X ** 2, axis=1)
    for s in range(0, n, CHUNK):
        e = min(n, s + CHUNK)
        d = sq[s:e, None] + sq[None, :] - 2 * X[s:e] @ X.T
        rows = np.arange(s, e)
        d[np.arange(e - s), rows] = np.inf
        if exclude_same_group is not None:
            d[exclude_same_group[s:e, None] == exclude_same_group[None, :]] = np.inf
        idx = np.argpartition(d, k, axis=1)[:, :k]
        for i in range(e - s):
            nb = idx[i]
            nb = nb[np.argsort(d[i, nb])]
            nb = nb[np.isfinite(d[i, nb])]
            if len(nb) == 0:
                pred[s + i] = None
                continue
            votes = pd.Series(labels[nb]).value_counts()
            top = votes[votes == votes.iloc[0]].index
            pred[s + i] = labels[nb][0] if len(top) > 1 else top[0]
    return pred


def main():
    zpath = fetch(ZIP_URL, "AVONET_ELEData.zip")
    with zipfile.ZipFile(zpath) as z:
        with z.open(CSV_IN_ZIP) as fh:
            df = pd.read_csv(io.BytesIO(fh.read()), na_values=["NA"])
    df = df.dropna(subset=TRAITS + ["Order1", "Family1", "Trophic.Niche", "Primary.Lifestyle"]).copy()
    df = df[(df[TRAITS] > 0).all(axis=1)]
    X = np.log(df[TRAITS].to_numpy(dtype=float))
    X = (X - X.mean(axis=0)) / X.std(axis=0)
    order = df["Order1"].to_numpy()
    family = df["Family1"].to_numpy()
    genus = df["Species1"].str.split().str[0].to_numpy()
    tn = df["Trophic.Niche"].to_numpy()
    pl = df["Primary.Lifestyle"].to_numpy()
    niche = np.array([f"{a}|{b}" for a, b in zip(tn, pl)])
    n = len(df)
    print(f"{n} species, {len(set(order))} orders, {len(set(family))} families", file=sys.stderr)

    # ---- clause (a): between-order pairs, same niche vs different niche
    _, tn_i = np.unique(tn, return_inverse=True)
    _, pl_i = np.unique(pl, return_inverse=True)
    _, or_i = np.unique(order, return_inverse=True)
    perms = [RNG.permutation(n) for _ in range(N_PERM)]
    sums = np.zeros((N_PERM + 1, 2))   # [perm][same, diff] distance sums
    cnts = np.zeros((N_PERM + 1, 2))
    sq = np.sum(X ** 2, axis=1)
    for s in range(0, n, CHUNK):
        e = min(n, s + CHUNK)
        d2 = sq[s:e, None] + sq[None, :] - 2 * X[s:e] @ X.T
        d = np.sqrt(np.clip(d2, 0, None))
        between = or_i[s:e, None] != or_i[None, :]
        upper = np.arange(n)[None, :] > np.arange(s, e)[:, None]  # each pair once
        base = between & upper
        dB = d[base]
        for p in range(N_PERM + 1):
            if p == 0:
                t_, l_ = tn_i, pl_i
            else:
                t_, l_ = tn_i[perms[p - 1]], pl_i[perms[p - 1]]
            same = (t_[s:e, None] == t_[None, :]) & (l_[s:e, None] == l_[None, :])
            diff = (t_[s:e, None] != t_[None, :]) & (l_[s:e, None] != l_[None, :])
            sm, df_ = same[base], diff[base]
            sums[p, 0] += dB[sm].sum(); cnts[p, 0] += sm.sum()
            sums[p, 1] += dB[df_].sum(); cnts[p, 1] += df_.sum()
        print(f"  pairs chunk {s}/{n}", file=sys.stderr)
    means = sums / cnts
    obs_ratio = float(means[0, 0] / means[0, 1])
    perm_ratios = means[1:, 0] / means[1:, 1]
    p_a = float((np.sum(perm_ratios <= obs_ratio) + 1) / (N_PERM + 1))
    clause_a = obs_ratio <= 0.90 and p_a < 0.01

    # ---- clause (b): kappa for niche vs order from LOO k-NN
    pred_niche = knn_predict(X, niche, K)
    pred_order = knn_predict(X, order, K)
    kap_niche = kappa(niche, pred_niche)
    kap_order = kappa(order, pred_order)
    acc_niche = float(np.mean(pred_niche == niche))
    acc_order = float(np.mean(pred_order == order))
    clause_b = kap_niche > kap_order

    # ---- clause (c): within orders, predict family (congeners excluded from the pool)
    rows = []
    for o in sorted(set(order)):
        m = order == o
        fams = set(family[m])
        if len(fams) < 3 or m.sum() < 30:
            continue
        _, g_i = np.unique(genus[m], return_inverse=True)
        pred = knn_predict(X[m], family[m], K, exclude_same_group=g_i)
        ok = np.array([p is not None for p in pred])
        kap = kappa(family[m][ok], pred[ok].astype(str))
        rows.append({"order": o, "n_species": int(m.sum()), "n_families": len(fams),
                     "n_predicted": int(ok.sum()), "kappa_family": kap,
                     "accuracy_family": float(np.mean(pred[ok].astype(str) == family[m][ok]))})
    fam_tab = pd.DataFrame(rows)
    fam_tab.to_csv(os.path.join(DERIVED, "within_order_family_knn.csv"), index=False)
    n_orders = len(fam_tab)
    n_pass = int((fam_tab["kappa_family"] > 0.3).sum())
    clause_c = n_pass > n_orders / 2

    n_true = int(clause_a) + int(clause_b) + int(clause_c)
    verdict = "supports" if n_true == 3 else ("mixed" if n_true >= 1 else "refutes")
    pd.DataFrame({"statistic": ["mean_dist_same_niche", "mean_dist_diff_niche", "n_pairs_same", "n_pairs_diff"],
                  "value": [means[0, 0], means[0, 1], cnts[0, 0], cnts[0, 1]]}).to_csv(
        os.path.join(DERIVED, "between_order_pair_distances.csv"), index=False)

    with open(os.path.join(HERE, "result.json")) as fh:
        res = json.load(fh)
    res["datasets"] = [{
        "id": "avonet-tobias2022-figshare",
        "name": "AVONET: morphological, ecological and geographical data for all birds (ELEData.zip, file TraitData/AVONET1_BirdLife.csv)",
        "landing_url": "https://figshare.com/articles/dataset/AVONET_morphological_ecological_and_geographical_data_for_all_birds_Tobias_et_al_2021_Ecology_Letters_/16586228",
        "doi": "10.6084/m9.figshare.16586228.v7",
        "version": "figshare v7; paper doi:10.1111/ele.13898",
        "license": "CC BY 4.0",
        "files": FILES,
        "role": "external morphological measurements, trophic niche, primary lifestyle, BirdLife order and family for all bird species",
    }]
    res["method"] = (
        f"AVONET1 (BirdLife taxonomy) species with complete values for 11 external measurements were log-transformed and "
        f"z-scored (n = {n}). (a) For every between-order species pair the Euclidean distance was computed; the mean distance "
        f"for pairs with identical trophic niche and primary lifestyle was compared with pairs differing in both, and the ratio "
        f"was tested against {N_PERM} permutations of niche labels across species. (b) Leave-one-out {K}-nearest-neighbour "
        f"prediction from morphology was scored with Cohen's kappa for niche (trophic niche x lifestyle) and for order. "
        f"(c) Within each order with >= 3 families and >= 30 species, family was predicted by LOO {K}-NN with congeners "
        f"excluded from the neighbour pool, and kappa recorded."
    )
    res["measured"] = {
        "value": obs_ratio,
        "unit": "ratio of mean morphological distance, same-niche / different-niche between-order species pairs",
        "n": n,
        "uncertainty": f"permutation p = {p_a:.4f} ({N_PERM} permutations); permutation ratios ranged {perm_ratios.min():.3f}-{perm_ratios.max():.3f}",
        "extra": {
            "clause_a": {"mean_dist_same_niche": float(means[0, 0]), "mean_dist_diff_niche": float(means[0, 1]),
                          "n_pairs_same_niche": int(cnts[0, 0]), "n_pairs_diff_niche": int(cnts[0, 1]),
                          "ratio": obs_ratio, "perm_p": p_a, "pass": bool(clause_a)},
            "clause_b": {"kappa_niche": kap_niche, "kappa_order": kap_order, "accuracy_niche": acc_niche,
                          "accuracy_order": acc_order, "n_niche_classes": int(len(set(niche))),
                          "n_orders": int(len(set(order))), "pass": bool(clause_b)},
            "clause_c": {"n_eligible_orders": n_orders, "n_orders_kappa_gt_0.3": n_pass,
                          "median_kappa_family": float(fam_tab["kappa_family"].median()), "pass": bool(clause_c)},
        },
    }
    res["verdict"] = verdict
    res["confidence"] = 0.75
    res["caveats"] = [
        "Birds only; Darwin's claim covers animals generally and plants by extension.",
        "AVONET measurements are linear external dimensions and mass; 'close external resemblance' in Darwin's sense also covers colour, texture and overall habitus, which are not measured.",
        "Ecological niche categories are coarse (10 trophic niches x 5 lifestyles) and were partly assigned with knowledge of morphology, which could inflate morphology-niche association.",
        "Orders are used as 'very distinct lines of descent'; divergence times between orders vary widely and no dated tree was used.",
        "k-NN kappa for order and for niche are not on identical footing (different class counts and class imbalance); kappa corrects for chance agreement but not fully for class structure.",
        "Some AVONET trait values are inferred from congeners (Inference column); these were retained and slightly inflate within-genus similarity, which clause (c) mitigates by excluding congeners from the neighbour pool.",
    ]
    res["status"] = "complete"
    res["agent"]["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(HERE, "result.json"), "w") as fh:
        json.dump(res, fh, indent=2)
        fh.write("\n")
    print(json.dumps({"verdict": verdict, "measured": res["measured"]}, indent=2, default=float))


if __name__ == "__main__":
    main()
