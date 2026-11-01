#!/usr/bin/env python3
"""Test of darwin1859-ch10-08: the extinction of a group is generally slower than its
origination (clade-shape centre of gravity of extinct animal families).

Requires: requests, numpy, pandas, scipy.
Data: Paleobiology Database taxa API (accepted Metazoa genera with first/last appearance ages
and classification). The raw response (tens of MB) is cached in /tmp, not in the repo; its URL,
size and SHA-256 go to derived/fetch_log.json. Per-family statistics go to derived/families.csv.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)
PRE = json.load(open(os.path.join(HERE, "result.json")))["preregistration"]
CACHE = os.environ.get("DELPHI_CACHE", "/tmp/delphi-data")
os.makedirs(CACHE, exist_ok=True)


def fetch():
    path = os.path.join(CACHE, "pbdb_metazoa_genera.json")
    log_path = os.path.join(DERIVED, "fetch_log.json")
    if not os.path.exists(path):
        r = requests.get(PRE["api_url"], timeout=900,
                         headers={"User-Agent": "delphi-claim-tests/0.1"})
        r.raise_for_status()
        open(path, "wb").write(r.content)
        log = {"download_url": PRE["api_url"],
               "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    else:
        log = json.load(open(log_path)) if os.path.exists(log_path) else {"download_url": PRE["api_url"]}
    raw = open(path, "rb").read()
    log.update(byte_size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    json.dump(log, open(log_path, "w"), indent=1)
    return json.loads(raw)["records"]


def main():
    recs = fetch()
    df = pd.DataFrame(recs)
    # compact vocabulary: nam name, rnk rank, fea firstapp_max_ma, lla lastapp_min_ma,
    # ext is_extant, fml family, odl order, cll class, phl phylum
    df = df.rename(columns={"nam": "name", "fea": "fad", "lla": "lad", "ext": "extant",
                            "fml": "family", "odl": "order", "cll": "class", "phl": "phylum"})
    n_all = len(df)
    df = df[df.fad.notna() & df.lad.notna() & df.family.notna()].copy()
    df = df[~df.family.isin(["NO_FAMILY_SPECIFIED", ""])]
    df["fad"] = df.fad.astype(float)
    df["lad"] = df.lad.astype(float)
    df["extant_flag"] = df.extant.astype(str).isin(["1", "True", "true", "yes"]) if "extant" in df else False
    rows = []
    grid = PRE["grid_myr"]
    for fam, g in df.groupby("family"):
        if g.extant_flag.any() or (g.lad <= 0).any():
            continue
        if len(g) < PRE["min_genera"]:
            continue
        origin, end = g.fad.max(), g.lad.min()
        dur = origin - end
        if dur < PRE["min_duration_myr"]:
            continue
        t = np.arange(end + grid / 2, origin, grid)
        D = ((g.fad.values[None, :] >= t[:, None]) & (g.lad.values[None, :] <= t[:, None])).sum(1)
        tau = (origin - t) / dur
        cg = float((D * tau).sum() / D.sum())
        rows.append({"family": fam, "phylum": g.phylum.iloc[0], "class": g["class"].iloc[0],
                     "n_genera": len(g), "origin_ma": origin, "end_ma": end, "duration_myr": dur,
                     "peak_tau": float(tau[np.argmax(D)]), "cg": cg})
    fam = pd.DataFrame(rows).sort_values("family")
    fam.to_csv(os.path.join(DERIVED, "families.csv"), index=False, float_format="%.4f")
    n = len(fam)
    med = float(fam.cg.median())
    share = float((fam.cg < 0.5).mean())
    w = stats.wilcoxon(fam.cg - 0.5, alternative="less")
    me = np.array(PRE["mass_extinctions_ma"])
    fam["at_mass_ext"] = fam.end_ma.apply(lambda e: bool(np.any(np.abs(me - e) <= PRE["mass_extinction_window_myr"])))
    era = pd.cut(fam.origin_ma, [-1, 66.0, 251.9, 1e4], labels=["Cenozoic", "Mesozoic", "Paleozoic"])

    def summ(s):
        return {"n": int(len(s)), "median_cg": float(s.median()) if len(s) else None,
                "share_cg_below_0.5": float((s < 0.5).mean()) if len(s) else None}

    measured = {
        "value": round(med, 4),
        "unit": "median centre of gravity of range-through genus diversity of extinct animal families (0 = origin, 1 = extinction; < 0.5 = slow decline)",
        "n": int(n),
        "uncertainty": f"Wilcoxon one-sided p (CG < 0.5) = {w.pvalue:.3g}; IQR {fam.cg.quantile(.25):.3f}-{fam.cg.quantile(.75):.3f}",
        "extra": {
            "share_cg_below_0.5": share,
            "mean_cg": float(fam.cg.mean()),
            "wilcoxon_p_one_sided": float(w.pvalue),
            "median_peak_tau": float(fam.peak_tau.median()),
            "genera_records_total": int(n_all),
            "ending_at_big_five": summ(fam.cg[fam.at_mass_ext]),
            "ending_elsewhere": summ(fam.cg[~fam.at_mass_ext]),
            "paleozoic_origin": summ(fam.cg[era == "Paleozoic"]),
            "mesozoic_origin": summ(fam.cg[era == "Mesozoic"]),
            "cenozoic_origin": summ(fam.cg[era == "Cenozoic"]),
        },
    }
    if n < PRE["min_families"]:
        verdict = "inconclusive"
    elif med >= 0.5:
        verdict = "refutes"
    elif w.pvalue < PRE["alpha"] and share >= PRE["share_threshold"]:
        verdict = "supports"
    else:
        verdict = "mixed"
    print(json.dumps(measured, indent=1))
    print("verdict:", verdict)
    json.dump({"measured": measured, "verdict": verdict}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
