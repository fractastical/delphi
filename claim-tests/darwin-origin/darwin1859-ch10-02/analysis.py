#!/usr/bin/env python3
"""Test darwin1859-ch10-02: species of different genera and classes change at different
rates. Taxonomic turnover proxy: stratigraphic durations of extinct genera in PBDB, compared
across 14 higher taxa (clause A) and across orders within each higher taxon (clause B).

Re-run:  python3 analysis.py   (downloads 14 PBDB taxa lists, ~40 MB, into ./data)
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
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

PBDB = "https://paleobiodb.org/data1.2"
TAXA = ["Trilobita", "Brachiopoda", "Bivalvia", "Gastropoda", "Cephalopoda", "Anthozoa", "Echinoidea",
        "Crinoidea", "Ostracoda", "Bryozoa", "Mammalia", "Reptilia", "Actinopterygii", "Chondrichthyes"]
MIN_OCCS = 5
MIN_OCCS_SENS = 20
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


def load_group(name):
    body = fetch(f"{PBDB}/taxa/list.json", f"pbdb_taxa_{name}.json",
                 params={"base_name": name, "rank": "genus", "show": "app,class", "vocab": "pbdb"})
    rows = []
    for r in json.loads(body)["records"]:
        if r.get("taxon_no") != r.get("accepted_no") or r.get("accepted_rank") != "genus":
            continue
        if r.get("is_extant") != "extinct" or any(r.get(k) is None for k in
                                                   ("firstapp_max_ma", "firstapp_min_ma", "lastapp_max_ma", "lastapp_min_ma")):
            continue
        fad = (float(r["firstapp_max_ma"]) + float(r["firstapp_min_ma"])) / 2
        lad = (float(r["lastapp_max_ma"]) + float(r["lastapp_min_ma"])) / 2
        rows.append({"group": name, "genus": r["accepted_name"], "order": r.get("order"),
                     "n_occs": int(r.get("n_occs", 0)), "fad_mid": fad, "lad_mid": lad, "duration": max(0.0, fad - lad)})
    return pd.DataFrame(rows)


def epsilon_squared(H, n, k):
    return float((H - k + 1) / (n - k)) if n > k else float("nan")


def run(df, min_occs):
    d = df[df["n_occs"] >= min_occs]
    groups = [g["duration"].to_numpy() for _, g in d.groupby("group")]
    H, p = stats.kruskal(*groups)
    k, n = len(groups), len(d)
    eps = epsilon_squared(H, n, k)
    med = d.groupby("group")["duration"].median()
    ratio = float(med.max() / med.min()) if med.min() > 0 else float("inf")
    clause_a = bool(p < 0.001 and eps >= 0.02 and ratio >= 2)
    summary = d.groupby("group")["duration"].agg(n="size", median="median", mean="mean", q25=lambda x: x.quantile(0.25),
                                                  q75=lambda x: x.quantile(0.75)).reset_index()

    per_class = []
    for name, g in d.groupby("group"):
        g = g.dropna(subset=["order"])
        g = g[~g["order"].str.startswith("NO_")]
        counts = g["order"].value_counts()
        orders = counts[counts >= 20].index
        if len(orders) < 3:
            continue
        sub = g[g["order"].isin(orders)]
        og = [x["duration"].to_numpy() for _, x in sub.groupby("order")]
        Hc, pc = stats.kruskal(*og)
        epsc = epsilon_squared(Hc, len(sub), len(og))
        omed = sub.groupby("order")["duration"].median()
        per_class.append({"group": name, "n_orders": len(og), "n_genera": int(len(sub)), "H": float(Hc), "p": float(pc),
                          "epsilon2": epsc, "order_median_min": float(omed.min()), "order_median_max": float(omed.max()),
                          "pass": bool(pc < 0.001 and epsc >= 0.02)})
    pc_df = pd.DataFrame(per_class)
    clause_b = bool(pc_df["pass"].sum() > len(pc_df) / 2) if len(pc_df) else False
    return {"min_occs": min_occs, "n_genera": int(n), "n_groups": k, "kruskal_H": float(H), "p": float(p),
            "epsilon2": eps, "median_duration_by_group_myr": {r["group"]: float(r["median"]) for _, r in summary.iterrows()},
            "n_by_group": {r["group"]: int(r["n"]) for _, r in summary.iterrows()},
            "max_min_median_ratio": ratio, "clause_a_pass": clause_a,
            "within_class_orders": per_class, "n_classes_eligible": int(len(pc_df)),
            "n_classes_orders_differ": int(pc_df["pass"].sum()) if len(pc_df) else 0, "clause_b_pass": clause_b}, summary, pc_df


def main():
    df = pd.concat([load_group(t) for t in TAXA], ignore_index=True)
    main_res, summary, pc_df = run(df, MIN_OCCS)
    sens_res, _, _ = run(df, MIN_OCCS_SENS)
    summary.to_csv(os.path.join(DERIVED, "genus_duration_by_group.csv"), index=False)
    pc_df.to_csv(os.path.join(DERIVED, "genus_duration_orders_within_group.csv"), index=False)

    a, b = main_res["clause_a_pass"], main_res["clause_b_pass"]
    verdict = "supports" if a and b else ("mixed" if a or b else "refutes")
    flipped = (a != sens_res["clause_a_pass"]) or (b != sens_res["clause_b_pass"])
    if flipped and verdict == "supports":
        verdict = "mixed"

    with open(os.path.join(HERE, "result.json")) as fh:
        res = json.load(fh)
    res["datasets"] = [{
        "id": "pbdb-taxa-genus-appearances-14-higher-taxa",
        "name": "Paleobiology Database taxa lists (genus rank, show=app,class) for 14 higher taxa",
        "landing_url": "https://paleobiodb.org/", "doi": None,
        "version": "live API data1.2, retrieved " + FILES[0]["retrieved_at"][:10], "license": "CC BY 4.0",
        "files": FILES, "role": "first/last appearance ages, extant flag, occurrence count and order of each genus",
    }]
    res["method"] = (
        f"For each of 14 higher taxa the PBDB genus list with appearance ages was downloaded; accepted extinct genera with "
        f">= {MIN_OCCS} occurrences were kept and duration computed as the difference between first- and last-appearance "
        f"midpoints. Clause A: Kruskal-Wallis across higher taxa with epsilon-squared effect size and the ratio of extreme group "
        f"medians. Clause B: within each higher taxon with >= 3 orders of >= 20 genera, Kruskal-Wallis across orders. The whole "
        f"procedure was repeated with >= {MIN_OCCS_SENS} occurrences as a sensitivity check."
    )
    res["measured"] = {
        "value": main_res["max_min_median_ratio"],
        "unit": "ratio of largest to smallest median genus duration among the 14 higher taxa (Myr/Myr)",
        "n": main_res["n_genera"],
        "uncertainty": f"Kruskal-Wallis H = {main_res['kruskal_H']:.1f}, p = {main_res['p']:.2e}, epsilon2 = {main_res['epsilon2']:.3f}",
        "extra": {"main": main_res, "sensitivity_min_occs_20": {k: v for k, v in sens_res.items() if k != "within_class_orders"},
                  "sensitivity_flipped_a_clause": flipped},
    }
    res["verdict"] = verdict
    res["confidence"] = 0.7
    res["caveats"] = [
        "Genus duration is a taxonomic proxy for rate of change; it conflates true evolutionary rate with preservation potential, sampling intensity and how finely each class is split by taxonomists.",
        "Durations of genera with few occurrences are truncated; the >= 5 occurrence filter (and the >= 20 sensitivity run) reduces but does not remove range truncation, which differs among classes.",
        "Groups are not all of class rank (Brachiopoda and Bryozoa are phyla) because PBDB class membership is unstable for them.",
        "Only extinct genera are included (extant genera have open-ended durations), which excludes the long-lived 'living fossil' lineages Darwin also had in mind and so is conservative with respect to the spread of rates.",
        "Darwin's phrase covers rate 'or degree' of change; morphological degree of change is not measured here.",
    ]
    res["status"] = "complete"
    res["agent"]["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(HERE, "result.json"), "w") as fh:
        json.dump(res, fh, indent=2)
        fh.write("\n")
    print(json.dumps({"verdict": verdict, "main": {k: v for k, v in main_res.items() if k != "within_class_orders"},
                      "sens": {k: v for k, v in sens_res.items() if k not in ("within_class_orders", "median_duration_by_group_myr", "n_by_group")}},
                     indent=2))


if __name__ == "__main__":
    main()
