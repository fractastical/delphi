#!/usr/bin/env python3
"""Test darwin1859-ch10-16: fossils from consecutive formations are more alike than those from remote ones.

Data: Paleobiology Database data service 1.2 (intervals/list for stage ages; occs/taxa for
marine Metazoa genus lists per stage).
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

PBDB = "https://paleobiodb.org/data1.2"
MIN_DURATION_MYR = 1.0
MIN_GENERA = 200
REMOTE_GAP = 5
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
    FILES.append({"download_url": url, "retrieved_at": open(meta).read().strip(), "byte_size": len(content),
                  "sha256": hashlib.sha256(content).hexdigest(), "role": role})
    return json.loads(content.decode("utf-8"))


def stage_table():
    d = get_cached(f"{PBDB}/intervals/list.json?scale=1", "intervals_scale1.json", "ICS stage ages")
    st = [r for r in d["records"] if r["itp"] == "age"]
    df = pd.DataFrame([{"name": r["nam"], "early_ma": r["eag"], "late_ma": r["lag"]} for r in st])
    df["duration"] = df.early_ma - df.late_ma
    df["mid_ma"] = (df.early_ma + df.late_ma) / 2
    return df.sort_values("early_ma", ascending=False).reset_index(drop=True)  # oldest first


def genera_for_stage(name):
    url = (f"{PBDB}/occs/taxa.json?base_name=Metazoa&interval={requests.utils.quote(name)}&rank=genus"
           f"&envtype=marine&timerule=major&limit=all")
    d = get_cached(url, f"occs_taxa_{name.replace(' ', '_')}.json", f"marine Metazoa genera, {name}")
    return {r["nam"] for r in d.get("records", []) if r.get("rnk") == 5 and "nam" in r}


def jaccard(a, b):
    u = len(a | b)
    return len(a & b) / u if u else np.nan


def main():
    write_result = "--write-result" in sys.argv
    rng = np.random.default_rng(SEED)
    stages = stage_table()
    stages = stages[stages.duration >= MIN_DURATION_MYR].reset_index(drop=True)
    gen = {}
    for s in stages.itertuples():
        gen[s.name] = genera_for_stage(s.name)
    stages["n_genera"] = [len(gen[n]) for n in stages.name]
    excluded_small = stages[stages.n_genera < MIN_GENERA].name.tolist()
    stages = stages[stages.n_genera >= MIN_GENERA].reset_index(drop=True)
    names = stages.name.tolist()
    n = len(names)

    J = np.zeros((n, n))
    T = np.zeros((n, n))
    for i, j in combinations(range(n), 2):
        J[i, j] = J[j, i] = jaccard(gen[names[i]], gen[names[j]])
        T[i, j] = T[j, i] = abs(stages.mid_ma[i] - stages.mid_ma[j])
    iu = np.triu_indices(n, 1)
    rho, _ = stats.spearmanr(J[iu], T[iu])
    worse = 0
    for _ in range(N_PERM):
        p = rng.permutation(n)
        rp, _ = stats.spearmanr(J[np.ix_(p, p)][iu], T[iu])
        worse += rp <= rho
    p_perm = (worse + 1) / (N_PERM + 1)

    gap = np.abs(np.subtract.outer(np.arange(n), np.arange(n)))
    consec = J[gap == 1]
    remote = J[(gap >= REMOTE_GAP) & (gap > 0)]
    ratio = consec.mean() / remote.mean()

    inter = []
    for i in range(1, n - 1):
        inter.append(J[i - 1, i + 1] <= min(J[i - 1, i], J[i, i + 1]))
    frac_inter = float(np.mean(inter))

    # Similarity profile by number of intervening stages
    profile = {int(g): round(float(J[gap == g].mean()), 5) for g in range(1, min(n, 21))}

    pd.DataFrame(J, index=names, columns=names).round(5).to_csv(os.path.join(DERIVED, "jaccard_matrix.csv"))
    stages.to_csv(os.path.join(DERIVED, "stages.csv"), index=False)
    pd.DataFrame({"stage": names[1:-1], "J_prev_next": [J[i - 1, i + 1] for i in range(1, n - 1)],
                  "J_prev_mid": [J[i - 1, i] for i in range(1, n - 1)], "J_mid_next": [J[i, i + 1] for i in range(1, n - 1)],
                  "intermediate": inter}).round(5).to_csv(os.path.join(DERIVED, "intermediacy.csv"), index=False)

    cond1 = rho <= -0.5 and p_perm < 0.001
    cond2 = ratio >= 2.0
    cond3 = frac_inter >= 0.80
    if cond1 and cond2 and cond3:
        verdict = "supports"
    elif rho > -0.2 or ratio < 1.2 or frac_inter < 0.50:
        verdict = "refutes"
    else:
        verdict = "mixed"

    measured = {
        "value": round(float(rho), 4),
        "unit": "Spearman rho between pairwise Jaccard genus similarity of stages and their midpoint age separation (Myr)",
        "n": int(n * (n - 1) / 2),
        "uncertainty": f"Mantel permutation p = {p_perm:.4f} ({N_PERM} permutations)",
        "extra": {
            "stages_used": int(n), "stages_excluded_short": int(101 - len(stage_table()[stage_table().duration >= MIN_DURATION_MYR])),
            "stages_excluded_few_genera": excluded_small,
            "total_distinct_genera": len(set().union(*gen.values())),
            "median_genera_per_stage": float(stages.n_genera.median()),
            "mean_jaccard_consecutive": round(float(consec.mean()), 5),
            "mean_jaccard_remote_gap_ge_5": round(float(remote.mean()), 5),
            "consecutive_over_remote_ratio": round(float(ratio), 3),
            "fraction_stages_intermediate": round(frac_inter, 4),
            "n_stages_tested_for_intermediacy": len(inter),
            "mean_jaccard_by_number_of_intervening_stages_plus_one": profile,
            "conditions": {"decay_rho_le_-0.5_p_lt_0.001": bool(cond1), "consecutive_ge_2x_remote": bool(cond2), "intermediacy_ge_0.8": bool(cond3)},
            "rule_based_verdict": verdict,
        },
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    json.dump(FILES, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))

    if write_result:
        rp = os.path.join(HERE, "result.json")
        res = json.load(open(rp))
        res["measured"] = measured
        fl = FILES
        res["datasets"][0]["files"] = [
            {k: v for k, v in fl[0].items() if k != "role"} | {"note": fl[0]["role"]},
            {"download_url": f"{PBDB}/occs/taxa.json?base_name=Metazoa&interval=<stage>&rank=genus&envtype=marine&timerule=major&limit=all (one call per stage; per-call SHA-256 in derived/files.json)",
             "retrieved_at": min(f["retrieved_at"] for f in fl[1:]), "byte_size": sum(f["byte_size"] for f in fl[1:]),
             "sha256": hashlib.sha256("".join(f["sha256"] for f in fl[1:]).encode()).hexdigest(),
             "note": f"{len(fl) - 1} API responses; sha256 is the SHA-256 of the concatenated per-response SHA-256 hex digests"}]
        res["datasets"][0]["version"] = f"PBDB live data service, retrieved {fl[0]['retrieved_at'][:10]}"
        json.dump(res, open(rp, "w"), indent=2, ensure_ascii=False)
        open(rp, "a").write("\n")


if __name__ == "__main__":
    main()
