#!/usr/bin/env python3
"""Test of darwin1859-ch02-13: species very closely allied to others have restricted ranges.

Requires: requests, numpy, pandas, scipy.
Data: Smith & Brown 2018 GBMB dated seed plant tree (GitHub release v0.1) and the WCVP
checklist (Kew). Both downloads (11 MB and 88 MB) are cached in /tmp, not committed; URL,
size and SHA-256 go to derived/fetch_log.json. Per-genus statistics: derived/genera.csv.
"""
import hashlib
import json
import os
import re
import zipfile
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
LOG = []


def fetch(url, name):
    path = os.path.join(CACHE, name)
    when = None
    if not os.path.exists(path):
        with requests.get(url, stream=True, timeout=1800) as r:
            r.raise_for_status()
            with open(path + ".part", "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        os.rename(path + ".part", path)
        when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    LOG.append({"download_url": url, "retrieved_at": when or datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "byte_size": os.path.getsize(path), "sha256": h.hexdigest()})
    return path


def load_wcvp():
    z = zipfile.ZipFile(fetch(PRE["wcvp_url"], "wcvp.zip"))
    names = pd.read_csv(z.open("wcvp_names.csv"), sep="|", dtype=str, keep_default_na=False,
                        usecols=["plant_name_id", "taxon_rank", "taxon_status", "genus_hybrid", "genus", "species_hybrid", "species"])
    names = names[(names.taxon_rank == "Species") & (names.taxon_status == "Accepted")
                  & (names.genus_hybrid == "") & (names.species_hybrid == "")].copy()
    names["binomial"] = names.genus + " " + names.species
    dist = pd.read_csv(z.open("wcvp_distribution.csv"), sep="|", dtype=str, keep_default_na=False,
                       usecols=["plant_name_id", "area_code_l3", "introduced", "extinct", "location_doubtful"])
    dist = dist[dist.plant_name_id.isin(names.plant_name_id) & (dist.location_doubtful == "0")]
    return names, dist


def main():
    zpath = fetch(PRE["tree_url"], "v0.1.zip")
    newick = zipfile.ZipFile(zpath).read("v0.1/" + PRE["tree_file"]).decode()
    tips = re.findall(r"[(,]([^(),:;\[\]]+):([0-9.eE+-]+)", newick)
    tree = pd.DataFrame(tips, columns=["tip", "d"])
    tree["d"] = tree.d.astype(float)
    tree["binomial"] = tree.tip.str.replace("_", " ").str.strip()
    tree = tree.drop_duplicates("binomial", keep=False)

    names, dist = load_wcvp()
    native = dist[(dist.introduced == "0") & (dist.extinct == "0")]
    rng = native.groupby("plant_name_id").area_code_l3.nunique().rename("r")
    grb = set(native[native.area_code_l3 == "GRB"].plant_name_id)
    names = names.drop_duplicates("binomial", keep=False)
    genus_size = names.groupby("genus").size().rename("genus_accepted")
    df = tree.merge(names[["binomial", "plant_name_id", "genus"]], on="binomial").merge(rng, left_on="plant_name_id", right_index=True)
    df = df.merge(genus_size, left_on="genus", right_index=True)
    df["in_grb"] = df.plant_name_id.isin(grb)

    def combine(frame, min_n, min_frac):
        rows = []
        for g, s in frame.groupby("genus"):
            n = len(s)
            if n < min_n or n / s.genus_accepted.iloc[0] < min_frac:
                continue
            if s.d.nunique() < 2 or s.r.nunique() < 2:
                rows.append({"genus": g, "n": n, "sampling": n / s.genus_accepted.iloc[0], "rho": np.nan})
                continue
            rows.append({"genus": g, "n": n, "sampling": n / s.genus_accepted.iloc[0], "rho": stats.spearmanr(s.d, s.r)[0]})
        gt = pd.DataFrame(rows)
        ok = gt[gt.rho.notna() & (gt.n > 3)]
        z = np.arctanh(ok.rho.clip(-0.999999, 0.999999))
        w = ok.n - 3
        zbar = float((z * w).sum() / w.sum())
        zstat = zbar * np.sqrt(w.sum())
        return gt, ok, float(np.tanh(zbar)), float(2 * stats.norm.sf(abs(zstat))), float((ok.rho > 0).mean())

    gt, ok, rho_w, p, share_pos = combine(df, PRE["min_species_per_genus"], PRE["min_sampling_fraction"])
    gt.to_csv(os.path.join(DERIVED, "genera.csv"), index=False, float_format="%.4f")
    sub = df[df.genus.isin(gt.genus)]
    q = sub.groupby("genus").d.rank(pct=True)
    gb_genera = df[df.in_grb].genus.unique()
    _, ok_gb, rho_gb, p_gb, _ = combine(df[df.genus.isin(gb_genera)], 3, 0.0)
    measured = {
        "value": round(rho_w, 4),
        "unit": "weighted mean within-genus Spearman rho between terminal branch length (Myr) and number of native TDWG level-3 regions",
        "n": int(len(ok)),
        "uncertainty": f"combined two-sided p={p:.3g}; species in qualifying genera={len(sub)}",
        "extra": {
            "combined_p_two_sided": p,
            "share_genera_rho_positive": share_pos,
            "n_genera_qualifying_incl_ties": int(len(gt)),
            "n_species_in_qualifying_genera": int(len(sub)),
            "n_tree_tips": int(len(tips)),
            "n_tips_matched_with_range": int(len(df)),
            "median_range_shortest_quartile_within_genus": float(sub.r[q <= 0.25].median()),
            "median_range_longest_quartile_within_genus": float(sub.r[q > 0.75].median()),
            "pooled_spearman_rho_all_matched": float(stats.spearmanr(df.d, df.r)[0]),
            "british_genera_weighted_rho": rho_gb,
            "british_genera_combined_p": p_gb,
            "british_genera_n": int(len(ok_gb)),
        },
    }
    if len(ok) < PRE["min_genera"]:
        verdict = "inconclusive"
    elif rho_w <= 0:
        verdict = "refutes"
    elif rho_w >= PRE["rho_support"] and p < PRE["alpha"] and share_pos > 0.5:
        verdict = "supports"
    else:
        verdict = "mixed"
    print(json.dumps(measured, indent=1))
    print("verdict:", verdict)
    json.dump(LOG, open(os.path.join(DERIVED, "fetch_log.json"), "w"), indent=1)
    json.dump({"measured": measured, "verdict": verdict}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
