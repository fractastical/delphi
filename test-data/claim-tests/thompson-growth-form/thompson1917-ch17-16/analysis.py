#!/usr/bin/env python3
"""Test of thompson1917-ch17-16 (human vs ape skull differences form one continuous,
roughly logarithmic transformation increasing downwards and forwards).

Data: Schroeder & von Cramon-Taubadel (2017, Evolution) hominoid cranial dataset,
Zenodo record 4976293 (Dryad mirror). One sheet: species, sex and 39 natural-log
inter-landmark distances for 547 adult hominoid crania (Homo n=50, Pan troglodytes
n=96 in three subspecies, Pan paniscus n=40, Gorilla n=110, Pongo, Hylobatidae).

The deposit contains inter-landmark distances, not coordinates, so the pre-registered
secondary plan applies: size-correct each specimen's log distances by subtracting their
mean (log geometric mean), take species means, form log ratio Pan/Homo for every
distance, assign each distance to an ordered anatomical position by the regions of its
endpoints (1 neurocranium/basicranium, 2 orbit/upper face/nasal, 3 maxilla/palate/
alveolar; a distance's score is the mean of its two endpoint ranks), and test whether
the log ratio increases monotonically with that score (Spearman rho).

Usage: python3 analysis.py   (downloads ~180 kB into data/ on first run)
"""
import hashlib
import json
import os
import sys
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

URL = ("https://zenodo.org/api/records/4976293/files/"
       "Schroeder,%20von%20Cramon-Taubadel_Evolution2017.xlsx/content")
LOCAL = os.path.join(DATA, "Schroeder_vonCramonTaubadel_Evolution2017.xlsx")
EXPECTED_SHA = "ca809bdfb64f1f92eb6d8dc077d806824a898c45aab7a903429b7a952c7f7ca2"

# Landmark regions in the human skull, ordered from postero-superior (1) to
# antero-inferior (3). Abbreviations follow von Cramon-Taubadel's standard set.
REGION = {
    # 1: neurocranium, vault, occiput and cranial base
    "BR": 1, "LD": 1, "AS": 1, "OPI": 1, "BA": 1, "JP": 1, "APET": 1, "EAM": 1,
    "SP": 1, "TS": 1, "KR": 1,
    # 2: orbit, upper face, nasal region, zygomatic arch
    "NA": 2, "FM": 2, "ZS": 2, "ZYGO": 2, "NSL": 2,
    # 3: maxilla, palate, alveolar process
    "IS": 3, "PM": 3, "PNS": 3, "MT": 3, "ZI": 3,
}
REGION_NAME = {1: "neurocranium/base", 2: "orbit/upper face", 3: "maxilla/palate"}

PAN_TROG = ["PanTT", "PanTS", "PanTV"]
GORILLA = ["GorGG", "GorBG", "GorBB"]


def fetch():
    if os.path.exists(LOCAL):
        content = open(LOCAL, "rb").read()
        retrieved = None
    else:
        r = requests.get(URL, timeout=120)
        r.raise_for_status()
        content = r.content
        retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        open(LOCAL, "wb").write(content)
    sha = hashlib.sha256(content).hexdigest()
    if sha != EXPECTED_SHA:
        print(f"WARNING: sha256 {sha} differs from the pre-recorded {EXPECTED_SHA}", file=sys.stderr)
    return {"download_url": URL, "retrieved_at": retrieved, "byte_size": len(content), "sha256": sha}


def species_means(df, cols):
    # size correction: subtract each specimen's mean log distance (log geometric mean)
    X = df[cols].to_numpy(dtype=float)
    Xc = X - X.mean(axis=1, keepdims=True)
    return pd.DataFrame(Xc, columns=cols, index=df.index)


def contrast(Xc, df, taxa_a, taxon_b="Homo"):
    a = Xc[df.species.isin(taxa_a)].mean(axis=0)
    b = Xc[df.species == taxon_b].mean(axis=0)
    return a - b  # log ratio taxon_a / Homo, size-corrected


def score_table(cols):
    rows = []
    for c in cols:
        p, q = c.split("-")
        rp, rq = REGION[p], REGION[q]
        rows.append({"distance": c, "lm1": p, "lm2": q, "region1": rp, "region2": rq,
                     "score": (rp + rq) / 2.0, "same_region": rp == rq})
    return pd.DataFrame(rows).set_index("distance")


def evaluate(logratio, tab, label):
    s = tab["score"].to_numpy()
    y = logratio.loc[tab.index].to_numpy()
    rho, p = stats.spearmanr(s, y)
    medians_all = {str(k): float(np.median(y[s == k])) for k in sorted(set(s))}
    same = tab["same_region"].to_numpy()
    medians_same = {REGION_NAME[int(k)]: float(np.median(y[same & (s == k)])) for k in (1, 2, 3)}
    mono_same = medians_same[REGION_NAME[1]] < medians_same[REGION_NAME[2]] < medians_same[REGION_NAME[3]]
    vals = [medians_all[k] for k in sorted(medians_all, key=float)]
    mono_all = all(np.diff(vals) > 0)
    rho_same, p_same = stats.spearmanr(s[same], y[same])
    return {
        "label": label,
        "n_distances": int(len(y)),
        "spearman_rho_score_vs_logratio": round(float(rho), 4),
        "p_value": float(f"{p:.3g}"),
        "n_same_region_distances": int(same.sum()),
        "spearman_rho_same_region_only": round(float(rho_same), 4),
        "p_value_same_region_only": float(f"{p_same:.3g}"),
        "median_logratio_by_score": {k: round(v, 4) for k, v in medians_all.items()},
        "median_logratio_same_region": {k: round(v, 4) for k, v in medians_same.items()},
        "monotone_same_region_medians": bool(mono_same),
        "monotone_all_score_levels": bool(mono_all),
        # linear 'logarithmic order': log ratio vs score
        "ols_slope_logratio_per_region_step": round(float(np.polyfit(s, y, 1)[0]), 4),
        "ols_r2": round(float(np.corrcoef(s, y)[0, 1] ** 2), 4),
    }


def bootstrap_rho(df, Xc, tab, taxa_a, n_boot=2000, seed=17):
    rng = np.random.default_rng(seed)
    ia = np.where(df.species.isin(taxa_a))[0]
    ib = np.where(df.species == "Homo")[0]
    s = tab["score"].to_numpy()
    X = Xc.to_numpy()
    rhos = []
    for _ in range(n_boot):
        a = X[rng.choice(ia, len(ia))].mean(axis=0)
        b = X[rng.choice(ib, len(ib))].mean(axis=0)
        rhos.append(stats.spearmanr(s, a - b)[0])
    lo, hi = np.percentile(rhos, [2.5, 97.5])
    return round(float(lo), 4), round(float(hi), 4)


def main():
    meta = fetch()
    df = pd.read_excel(LOCAL)
    cols = [c for c in df.columns if c not in ("species", "sex")]
    assert len(cols) == 39, cols
    assert all(lm in REGION for c in cols for lm in c.split("-")), "unmapped landmark"
    Xc = species_means(df, cols)
    tab = score_table(cols)

    results = {}
    out = tab.copy()
    for label, taxa in [("Pan_troglodytes", PAN_TROG), ("Gorilla", GORILLA), ("Pan_paniscus", ["PanP"])]:
        lr = contrast(Xc, df, taxa)
        out[f"logratio_{label}_vs_Homo"] = lr.loc[tab.index].round(5)
        res = evaluate(lr, tab, label)
        res["n_specimens"] = int(df.species.isin(taxa).sum())
        res["bootstrap_95ci_rho"] = bootstrap_rho(df, Xc, tab, taxa)
        results[label] = res
    results["n_Homo"] = int((df.species == "Homo").sum())
    out.sort_values("score").to_csv(os.path.join(DERIVED, "distance_logratios.csv"))

    primary = results["Pan_troglodytes"]
    rho = primary["spearman_rho_score_vs_logratio"]
    if rho >= 0.6 and primary["monotone_same_region_medians"]:
        verdict = "supports"
    elif rho < 0.3:
        verdict = "refutes"
    else:
        verdict = "mixed"
    results["verdict_by_preregistered_rule"] = verdict
    results["file"] = meta
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
