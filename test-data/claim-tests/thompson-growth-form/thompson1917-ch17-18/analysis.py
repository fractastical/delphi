#!/usr/bin/env python3
"""Test of thompson1917-ch17-18: in related fishes depth and width vary inversely, so that
mass at a given length (k = W/L^3) changes less than either transverse dimension.

Data: FishShapes v1 (Price et al. 2022, Dryad doi:10.5061/dryad.vt4b8gtvf), 16,523 Smithsonian
specimens with standard length, maximum body depth, maximum fish width and mass.
Packages: requests, numpy, pandas, scipy.
Writes derived/summary.json and derived/families.csv.
"""
import hashlib
import io
import json
import os
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
PRE = json.load(open(os.path.join(HERE, "result.json")))["preregistration"]
URL = "https://datadryad.org/api/v2/versions/183047/download"
CSV = "FishShapes_specimensv1.csv"
CSV_SHA256 = "7447fdc92c5fd5c9ecf1d9713bbd4207d2de7ab4b2ea0e320871041da8e34264"  # Dryad file digest


def fetch():
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, "dryad_vt4b8gtvf_v183047.zip")
    log = os.path.join(DATA, "fetch.json")
    if not os.path.exists(path):
        r = requests.get(URL, timeout=300, headers={"User-Agent": "delphi-claim-tests/0.1"})
        r.raise_for_status()
        open(path, "wb").write(r.content)
        json.dump({"download_url": URL, "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}, open(log, "w"), indent=1)
    raw = zipfile.ZipFile(path).read(CSV)
    assert hashlib.sha256(raw).hexdigest() == CSV_SHA256, "FishShapes CSV checksum mismatch"
    return pd.read_csv(io.BytesIO(raw)), json.load(open(log))


def main():
    df, fetch_log = fetch()
    cols = ["Total_weight", "Standard_length", "Max_body_depth", "Max_fish_width"]
    sp = df.dropna(subset=cols)
    sp = sp[(sp[cols] > 0).all(axis=1)].copy()
    n_specimens = len(sp)
    for c in cols:
        sp["ln_" + c] = np.log(sp[c])
    g = sp.groupby(["Tree_name", "Family"])[["ln_" + c for c in cols]].mean().reset_index()  # geometric means
    g["d"] = g.ln_Max_body_depth - g.ln_Standard_length
    g["w"] = g.ln_Max_fish_width - g.ln_Standard_length
    g["k"] = g.ln_Total_weight - 3 * g.ln_Standard_length
    fam_n = g.groupby("Family").size()
    keep = fam_n[fam_n >= PRE["min_species_per_family"]].index
    f = g[g.Family.isin(keep)].copy()
    for v in "dwk":
        f[v + "_c"] = f[v] - f.groupby("Family")[v].transform("mean")
    rho, p2 = stats.spearmanr(f.d_c, f.w_c)
    p_one = p2 / 2 if rho < 0 else 1 - p2 / 2
    pr, _ = stats.pearsonr(f.d_c, f.w_c)
    sd = {v: float(f[v + "_c"].std(ddof=1)) for v in "dwk"}
    fam_rho = []
    for fam, sub in f.groupby("Family"):
        fam_rho.append({"family": fam, "n_species": len(sub),
                        "spearman_rho_d_w": float(stats.spearmanr(sub.d, sub.w)[0]),
                        "sd_d": float(sub.d.std(ddof=1)), "sd_w": float(sub.w.std(ddof=1)), "sd_k": float(sub.k.std(ddof=1))})
    fam_df = pd.DataFrame(fam_rho).sort_values("n_species", ascending=False)
    os.makedirs(DERIVED, exist_ok=True)
    fam_df.to_csv(os.path.join(DERIVED, "families.csv"), index=False, float_format="%.4f")

    pair = {}
    names = {"plaice": PRE["pair_check"]["plaice"].replace(" ", "_"), "haddock": PRE["pair_check"]["haddock"].replace(" ", "_")}
    if all((g.Tree_name == n).any() for n in names.values()):
        a = g[g.Tree_name == names["plaice"]].iloc[0]
        b = g[g.Tree_name == names["haddock"]].iloc[0]
        pair = {"depth_ratio": float(np.exp(a.d - b.d)), "width_ratio": float(np.exp(a.w - b.w)), "k_ratio": float(np.exp(a.k - b.k)),
                "plaice": {"depth_over_SL": float(np.exp(a.d)), "width_over_SL": float(np.exp(a.w)), "k_g_per_mm3": float(np.exp(a.k))},
                "haddock": {"depth_over_SL": float(np.exp(b.d)), "width_over_SL": float(np.exp(b.w)), "k_g_per_mm3": float(np.exp(b.k))}}
    else:
        pair = {"missing": [k for k, n in names.items() if not (g.Tree_name == n).any()]}

    A = bool(rho < 0 and p_one < PRE["alpha_one_sided"])
    B = bool(sd["k"] < min(sd["d"], sd["w"]))
    n_fam, n_sp = int(len(keep)), int(len(f))
    if n_fam < PRE["min_families"] or n_sp < PRE["min_species"]:
        verdict = "inconclusive"
    elif A and B:
        verdict = "supports"
    elif rho >= 0 and not B:
        verdict = "refutes"
    else:
        verdict = "mixed"
    measured = {
        "value": round(float(rho), 4),
        "unit": "Spearman rho between family-centred ln(body depth/SL) and ln(body width/SL) across teleost species",
        "n": n_sp,
        "uncertainty": f"one-sided p (rho<0) = {p_one:.3g}; {n_fam} families with >= {PRE['min_species_per_family']} species",
        "extra": {
            "pearson_r_d_w_centred": float(pr),
            "sd_centred_ln_depth_ratio": sd["d"], "sd_centred_ln_width_ratio": sd["w"], "sd_centred_ln_k": sd["k"],
            "condition_A_negative_covariation": A, "condition_B_k_less_variable": B,
            "fraction_families_rho_negative": float((fam_df.spearman_rho_d_w < 0).mean()),
            "median_family_rho": float(fam_df.spearman_rho_d_w.median()),
            "n_specimens_used": int(n_specimens), "n_species_all": int(len(g)), "n_families": n_fam,
            "pair_check_plaice_vs_haddock": pair,
        },
    }
    out = {"measured": measured, "verdict": verdict, "fetch": fetch_log}
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
