#!/usr/bin/env python3
"""Test darwin1859-ch10-12: marine forms of life change almost simultaneously throughout the world.

Data: Paleobiology Database data service 1.2, occs/taxa per stage per continent (marine Metazoa genera).
Usage: python3 analysis.py [--write-result]
"""
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
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

PBDB = "https://paleobiodb.org/data1.2"
CONTINENTS = {"NOA": "North America", "SOA": "South America", "EUR": "Europe", "AFR": "Africa", "ASI": "Asia", "AUS": "Australia"}
MIN_DURATION_MYR = 1.0
MIN_GENERA = 100
N_PERM = 2000
SEED = 20261031
FILES = []


def get_cached(url, cache_name, role):
    path = os.path.join(DATA, cache_name)
    meta = path + ".meta"
    if not (os.path.exists(path) and os.path.exists(meta)):
        for attempt in range(6):
            try:
                r = requests.get(url, timeout=600)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(3 * 2 ** attempt)
        r.raise_for_status()
        open(path, "wb").write(r.content)
        open(meta, "w").write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    content = open(path, "rb").read()
    rec = {"download_url": url, "retrieved_at": open(meta).read().strip(), "byte_size": len(content),
           "sha256": hashlib.sha256(content).hexdigest(), "role": role}
    return json.loads(content.decode("utf-8")), rec


def stage_table():
    d, rec = get_cached(f"{PBDB}/intervals/list.json?scale=1", "intervals_scale1.json", "ICS stage ages")
    FILES.append(rec)
    st = [r for r in d["records"] if r["itp"] == "age"]
    df = pd.DataFrame([{"name": r["nam"], "early_ma": r["eag"], "late_ma": r["lag"]} for r in st])
    df["duration"] = df.early_ma - df.late_ma
    df["mid_ma"] = (df.early_ma + df.late_ma) / 2
    df = df[df.duration >= MIN_DURATION_MYR]
    return df.sort_values("early_ma", ascending=False).reset_index(drop=True)


def genera(stage, cc):
    url = (f"{PBDB}/occs/taxa.json?base_name=Metazoa&interval={requests.utils.quote(stage)}&rank=genus"
           f"&envtype=marine&timerule=major&cc={cc}&limit=all")
    d, rec = get_cached(url, f"occs_taxa_{cc}_{stage.replace(' ', '_')}.json", f"marine Metazoa genera, {stage}, {cc}")
    return (stage, cc), {r["nam"] for r in d.get("records", []) if r.get("rnk") == 5 and "nam" in r}, rec


def jaccard(a, b):
    u = len(a | b)
    return len(a & b) / u if u else 0.0


def main():
    write_result = "--write-result" in sys.argv
    rng = np.random.default_rng(SEED)
    stages = stage_table()
    names = stages.name.tolist()
    n = len(names)

    jobs = [(s, cc) for s in names for cc in CONTINENTS]
    G = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        for key, gset, rec in ex.map(lambda j: genera(*j), jobs):
            G[key] = gset
            FILES.append(rec)

    counts = pd.DataFrame({cc: [len(G[(s, cc)]) for s in names] for cc in CONTINENTS}, index=names)
    counts.to_csv(os.path.join(DERIVED, "genera_counts.csv"))

    # (A) cross-continent stage identification
    pooled_other = {}
    for cc in CONTINENTS:
        for i, s in enumerate(names):
            pooled_other[(s, cc)] = set().union(*[G[(s, o)] for o in CONTINENTS if o != cc])
    match_rows = []
    for cc in CONTINENTS:
        for i, s in enumerate(names):
            if len(G[(s, cc)]) < MIN_GENERA:
                continue
            sims = [jaccard(G[(s, cc)], pooled_other[(names[j], cc)]) for j in range(n)]
            j_best = int(np.argmax(sims))
            match_rows.append({"continent": cc, "stage": s, "stage_index": i, "best_match_stage": names[j_best],
                               "offset_stages": j_best - i, "jaccard_best": round(sims[j_best], 5), "jaccard_true": round(sims[i], 5),
                               "n_genera": len(G[(s, cc)])})
    M = pd.DataFrame(match_rows)
    M.to_csv(os.path.join(DERIVED, "stage_matching.csv"), index=False)
    exact = float((M.offset_stages == 0).mean())
    within1 = float((M.offset_stages.abs() <= 1).mean())
    within2 = float((M.offset_stages.abs() <= 2).mean())

    # (B) synchrony of proportional genus loss between consecutive stages
    loss = pd.DataFrame(index=names[:-1], columns=list(CONTINENTS), dtype=float)
    for cc in CONTINENTS:
        for i in range(n - 1):
            a, b = G[(names[i], cc)], G[(names[i + 1], cc)]
            if len(a) >= MIN_GENERA and len(b) >= MIN_GENERA:
                loss.loc[names[i], cc] = 1 - len(a & b) / len(a)
    loss.to_csv(os.path.join(DERIVED, "proportional_loss.csv"))
    pair_rows = []
    rhos = []
    for a, b in combinations(CONTINENTS, 2):
        sub = loss[[a, b]].dropna()
        if len(sub) >= 10:
            rho, p = stats.spearmanr(sub[a], sub[b])
            rhos.append(rho)
            pair_rows.append({"continent_a": a, "continent_b": b, "n_boundaries": len(sub), "spearman_rho": round(float(rho), 4), "p_value": round(float(p), 5)})
    mean_rho = float(np.mean(rhos))

    def mean_rho_of(frame):
        vals = []
        for a, b in combinations(CONTINENTS, 2):
            sub = frame[[a, b]].dropna()
            if len(sub) >= 10:
                vals.append(stats.spearmanr(sub[a], sub[b])[0])
        return np.mean(vals)
    worse = 0
    for _ in range(N_PERM):
        perm = loss.copy()
        for cc in CONTINENTS:
            col = perm[cc].values.copy()
            idx = np.where(~np.isnan(col))[0]
            col[idx] = col[rng.permutation(idx)]
            perm[cc] = col
        worse += mean_rho_of(perm) >= mean_rho
    p_perm = (worse + 1) / (N_PERM + 1)
    pd.DataFrame(pair_rows).to_csv(os.path.join(DERIVED, "turnover_correlations.csv"), index=False)

    cond_a = within1 >= 0.85
    cond_b = mean_rho > 0 and p_perm < 0.01
    if cond_a and cond_b:
        verdict = "supports"
    elif within1 < 0.60 or mean_rho <= 0:
        verdict = "refutes"
    else:
        verdict = "mixed"

    measured = {
        "value": round(within1, 4),
        "unit": "fraction of continent-stages (>= 100 genera) whose fauna best matches the same or an adjacent stage on the other continents",
        "n": int(len(M)),
        "uncertainty": f"95% Wilson CI {wilson(int((M.offset_stages.abs() <= 1).sum()), len(M))}",
        "extra": {
            "stages_used": n, "continents": CONTINENTS,
            "continent_stages_evaluated_by_continent": M.groupby("continent").size().to_dict(),
            "exact_match_fraction": round(exact, 4), "within_1_stage_fraction": round(within1, 4), "within_2_stages_fraction": round(within2, 4),
            "median_abs_offset_stages": float(M.offset_stages.abs().median()),
            "mean_pairwise_spearman_turnover": round(mean_rho, 4), "permutation_p_mean_rho": round(p_perm, 4),
            "pairwise_turnover_correlations": pair_rows,
            "n_boundaries_with_both_continents_sampled_median": int(np.median([r["n_boundaries"] for r in pair_rows])) if pair_rows else None,
            "conditions": {"A_within_1_stage_ge_0.85": bool(cond_a), "B_mean_rho_gt_0_p_lt_0.01": bool(cond_b)},
            "rule_based_verdict": verdict,
        },
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2, default=float)
    json.dump(FILES, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2, default=float))

    if write_result:
        rp = os.path.join(HERE, "result.json")
        res = json.load(open(rp))
        res["measured"] = json.loads(json.dumps(measured, default=float))
        fl = FILES
        res["datasets"][0]["files"] = [
            {k: v for k, v in fl[0].items() if k != "role"} | {"note": fl[0]["role"]},
            {"download_url": f"{PBDB}/occs/taxa.json?base_name=Metazoa&interval=<stage>&rank=genus&envtype=marine&timerule=major&cc=<continent>&limit=all (one call per stage and continent; per-call SHA-256 in derived/files.json)",
             "retrieved_at": min(f["retrieved_at"] for f in fl[1:]), "byte_size": sum(f["byte_size"] for f in fl[1:]),
             "sha256": hashlib.sha256("".join(f["sha256"] for f in fl[1:]).encode()).hexdigest(),
             "note": f"{len(fl) - 1} API responses; sha256 is the SHA-256 of the concatenated per-response SHA-256 hex digests"}]
        res["datasets"][0]["version"] = f"PBDB live data service, retrieved {fl[0]['retrieved_at'][:10]}"
        json.dump(res, open(rp, "w"), indent=2, ensure_ascii=False)
        open(rp, "a").write("\n")


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5
    return f"[{(centre - half) / denom:.3f}, {(centre + half) / denom:.3f}]"


if __name__ == "__main__":
    main()
