#!/usr/bin/env python3
"""Test darwin1859-ch14-07: organic change between consecutive formations is a fair though
imperfect measure of elapsed time. Stage-level genus turnover (PBDB occs/diversity, marine
animals, Phanerozoic) vs radiometric stage duration.

Re-run:  python3 analysis.py
"""
import hashlib
import json
import math
import os
import sys
import time
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
PBDB = "https://paleobiodb.org/data1.2"
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
            r = SESSION.get(url, params=params, timeout=1800)
            if r.status_code == 200:
                break
            print(f"  HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  retry {attempt}: {e}", file=sys.stderr)
        time.sleep(15 * (attempt + 1))
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


def partial_spearman(x, y, z):
    rx, ry, rz = stats.rankdata(x), stats.rankdata(y), stats.rankdata(z)
    def resid(a, b):
        A = np.vstack([np.ones_like(b), b]).T
        coef, *_ = np.linalg.lstsq(A, a, rcond=None)
        return a - A @ coef
    r = float(np.corrcoef(resid(rx, rz), resid(ry, rz))[0, 1])
    n = len(x)
    t = r * math.sqrt((n - 3) / max(1e-12, 1 - r * r))
    return r, float(2 * stats.t.sf(abs(t), n - 3))


def main():
    body = fetch(f"{PBDB}/occs/diversity.json", "pbdb_diversity_marine_animalia_stage.json",
                 params={"base_name": "Animalia", "interval": "Phanerozoic", "envtype": "marine",
                         "count": "genera", "time_reso": "stage", "vocab": "pbdb"})
    recs = json.loads(body)["records"]
    df = pd.DataFrame(recs)
    for c in ["max_ma", "min_ma", "X_Ft", "X_bL", "X_FL", "X_bt", "sampled_in_bin", "n_occs"]:
        df[c] = pd.to_numeric(df[c])
    df = df.sort_values("max_ma", ascending=False).reset_index(drop=True)   # oldest first
    df["present"] = df["X_Ft"] + df["X_bL"] + df["X_FL"] + df["X_bt"]
    df["turnover"] = (df["X_bL"] + df["X_FL"]) / df["present"]
    df["duration_myr"] = df["max_ma"] - df["min_ma"]
    df = df[df["present"] > 0]
    # drop the two youngest stages (Recent edge)
    df = df.iloc[:-2].copy()
    df["log_n_occs"] = np.log(df["n_occs"].clip(lower=1))
    df[["interval_name", "max_ma", "min_ma", "duration_myr", "present", "X_bL", "X_FL", "turnover", "n_occs"]].to_csv(
        os.path.join(DERIVED, "stage_turnover_vs_duration.csv"), index=False)

    rho, p = stats.spearmanr(df["turnover"], df["duration_myr"])
    prho, pp = partial_spearman(df["turnover"].to_numpy(), df["duration_myr"].to_numpy(), df["log_n_occs"].to_numpy())
    top5 = df.nlargest(5, "turnover")["interval_name"].tolist()
    sub = df[~df["interval_name"].isin(top5)]
    rho_sub, p_sub = stats.spearmanr(sub["turnover"], sub["duration_myr"])
    c1 = rho > 0 and p < 0.05
    c2 = prho > 0 and pp < 0.05
    c3 = rho_sub > 0
    if c1 and c2 and c3 and rho >= 0.2:
        verdict = "supports"
    elif c1:
        verdict = "mixed"
    else:
        verdict = "refutes"
    # simple per-Myr rate as descriptive extra
    df["turnover_per_myr"] = df["turnover"] / df["duration_myr"]

    with open(os.path.join(HERE, "result.json")) as fh:
        res = json.load(fh)
    res["datasets"] = [{
        "id": "pbdb-occs-diversity-marine-genera-by-stage",
        "name": "Paleobiology Database occs/diversity: marine Animalia genus counts per stage (Phanerozoic), with Foote range categories",
        "landing_url": "https://paleobiodb.org/data1.2/occs/diversity_doc.html", "doi": None,
        "version": "live API data1.2, retrieved " + FILES[0]["retrieved_at"][:10], "license": "CC BY 4.0",
        "files": FILES, "role": "per-stage genus range categories (X_Ft, X_bL, X_FL, X_bt), occurrence counts and stage ages",
    }]
    res["method"] = (
        f"The PBDB diversity table for marine animal genera at stage resolution was downloaded for the whole Phanerozoic; for each "
        f"of the {len(df)} stages retained (two youngest dropped) turnover was computed as the share of genera present that make their "
        f"last appearance in the stage, and stage duration as the difference of its PBDB/ICS boundary ages. Spearman correlation of "
        f"turnover with duration, the partial Spearman correlation controlling log occurrences, and the correlation after removing "
        f"the five highest-turnover stages ({', '.join(top5)}) were computed."
    )
    res["measured"] = {
        "value": float(rho), "unit": "Spearman rho, stage turnover vs stage duration (Myr)", "n": int(len(df)),
        "uncertainty": f"p = {p:.4g}",
        "extra": {"partial_rho_controlling_log_occurrences": prho, "partial_p": pp,
                  "rho_without_top5_turnover_stages": float(rho_sub), "p_without_top5": float(p_sub), "top5_turnover_stages": top5,
                  "median_turnover": float(df["turnover"].median()), "median_duration_myr": float(df["duration_myr"].median()),
                  "pearson_r_turnover_duration": float(stats.pearsonr(df["turnover"], df["duration_myr"])[0]),
                  "conditions": {"c1_raw_positive": bool(c1), "c2_partial_positive": bool(c2), "c3_positive_without_mass_extinctions": bool(c3)}},
    }
    res["verdict"] = verdict
    res["confidence"] = 0.7
    res["caveats"] = [
        "Turnover measured on stages correlated by biostratigraphy is partly circular: stage boundaries were historically placed at faunal changes, which inflates turnover at boundaries regardless of duration; the test asks whether, given those boundaries, longer stages still show more change.",
        "Stage-level genus ranges are affected by uneven sampling across stages; the partial correlation controls only for occurrence count, not for facies or geographic coverage.",
        "Taxonomic turnover is a proxy for Darwin's 'amount of organic change', which he meant morphologically; a few stages with mass extinctions dominate the upper tail of turnover.",
        "The claim's practical use (estimating blank intervals between formations) is tested only through its premise that change tracks time.",
    ]
    res["status"] = "complete"
    res["agent"]["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(HERE, "result.json"), "w") as fh:
        json.dump(res, fh, indent=2)
        fh.write("\n")
    print(json.dumps({"verdict": verdict, "measured": res["measured"]}, indent=2))


if __name__ == "__main__":
    main()
