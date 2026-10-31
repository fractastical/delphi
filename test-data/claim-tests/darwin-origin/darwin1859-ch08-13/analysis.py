#!/usr/bin/env python3
"""Test darwin1859-ch08-13: hybrids are only slightly variable in the first generation but
extremely variable in succeeding generations. Data: Cakile edentula x C. maritima artificial
crosses (Dryad doi:10.25338/B8QS5T), file Chengjun_Experiment.csv (generation = Parents, F1,
F2, BC). Re-run:  python3 analysis.py
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
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
URL = "https://datadryad.org/api/v2/versions/105038/download"   # doi:10.25338/B8QS5T
MIN_N = 8
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
            r = requests.get(url, timeout=600, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0 delphi-claim-tests/0.1"})
            if r.status_code == 200 and r.content[:2] == b"PK":
                break
            print(f"  HTTP {r.status_code} {r.url}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  retry {attempt}: {e}", file=sys.stderr)
        time.sleep(10 * (attempt + 1))
    else:
        raise RuntimeError(f"could not fetch {url}")
    body = r.content
    meta = {"download_url": url, "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": len(body), "sha256": hashlib.sha256(body).hexdigest(),
            "note": "Dryad version zip assembled on request (archive hash varies between downloads; member_files hashes are stable); redirects to a signed S3 URL"}
    with open(path, "wb") as fh:
        fh.write(body)
    with open(meta_path, "w") as fh:
        json.dump(meta, fh)
    FILES.append(meta)
    return path


def scaled_variance(x):
    """Variance of log values for strictly positive traits; otherwise variance / mean^2."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < MIN_N:
        return None, len(x), None
    if np.all(x > 0):
        return float(np.var(np.log(x), ddof=1)), len(x), "var(log x)"
    m = x.mean()
    return (float(np.var(x, ddof=1) / m ** 2) if m != 0 else None), len(x), "var(x)/mean(x)^2"


def main():
    zpath = fetch(URL, "dryad_B8QS5T.zip")
    with zipfile.ZipFile(zpath) as z:
        raw = z.read("Chengjun_Experiment.csv")
    # Dryad assembles version zips on request, so the archive hash is not stable; record the member file's hash too
    FILES[-1]["member_files"] = [{"path": "Chengjun_Experiment.csv", "byte_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}]
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = [c.strip() for c in df.columns]
    df["generation"] = df["generation"].str.strip()
    df["PLANT TYPE"] = df["PLANT TYPE"].str.strip()
    traits = [c for c in df.columns if c not in ("generation", "PLANT TYPE", "NAME")]
    f1 = df[df["generation"] == "F1"]
    f2 = df[df["generation"] == "F2"]
    par_e = df[(df["generation"] == "Parents") & df["PLANT TYPE"].isin(["E", "EE"])]
    par_m = df[(df["generation"] == "Parents") & df["PLANT TYPE"].isin(["M", "MM"])]
    rows = []
    for t in traits:
        v1, n1, kind = scaled_variance(f1[t])
        v2, n2, _ = scaled_variance(f2[t])
        ve, ne, _ = scaled_variance(par_e[t])
        vm, nm, _ = scaled_variance(par_m[t])
        if v1 is None or v2 is None or v1 == 0:
            continue
        rows.append({"trait": t, "scale": kind, "n_F1": n1, "n_F2": n2, "var_F1": v1, "var_F2": v2, "ratio_F2_F1": v2 / v1,
                     "n_parent_E": ne, "var_parent_E": ve, "n_parent_M": nm, "var_parent_M": vm,
                     "mean_F1": float(f1[t].mean()), "mean_F2": float(f2[t].mean())})
    tab = pd.DataFrame(rows)
    tab.to_csv(os.path.join(DERIVED, "trait_variance_F1_F2.csv"), index=False)
    ratios = tab["ratio_F2_F1"].to_numpy()
    med = float(np.median(ratios))
    n_gt = int((ratios > 1).sum()); n_tr = len(ratios)
    p_sign = float(stats.binomtest(n_gt, n_tr, 0.5, alternative="greater").pvalue)
    majority = n_gt > n_tr / 2 and p_sign < 0.05
    if med >= 1.5 and majority:
        verdict = "supports"
    elif (majority and 1.0 < med < 1.5) or (med >= 1.5 and not majority):
        verdict = "mixed"
    elif med <= 1.0 or n_gt <= n_tr / 2:
        verdict = "refutes"
    else:
        # median ratio between 1 and 1.5 and a bare, non-significant majority: a case the pre-registration did
        # not cover; recorded as 'mixed' (heterogeneous by trait) rather than forced into pass or fail
        verdict = "mixed"
    # extra: F1 vs parents
    par_rows = tab.dropna(subset=["var_parent_E", "var_parent_M"])
    f1_vs_par = {"n_traits": int(len(par_rows)),
                 "median_ratio_F1_over_mean_parent_variance": float(np.median(par_rows["var_F1"] / ((par_rows["var_parent_E"] + par_rows["var_parent_M"]) / 2))) if len(par_rows) else None,
                 "n_traits_F1_less_variable_than_both_parents": int(((par_rows["var_F1"] < par_rows["var_parent_E"]) & (par_rows["var_F1"] < par_rows["var_parent_M"])).sum()),
                 "n_traits_F1_more_variable_than_both_parents": int(((par_rows["var_F1"] > par_rows["var_parent_E"]) & (par_rows["var_F1"] > par_rows["var_parent_M"])).sum())}
    # Levene-type robust test per trait on log scale where possible (extra)
    lev = []
    for _, r in tab.iterrows():
        a, b = f1[r["trait"]].dropna().to_numpy(float), f2[r["trait"]].dropna().to_numpy(float)
        if r["scale"] == "var(log x)":
            a, b = np.log(a), np.log(b)
        lev.append(float(stats.levene(a, b, center="median").pvalue))
    tab["levene_p"] = lev
    tab.to_csv(os.path.join(DERIVED, "trait_variance_F1_F2.csv"), index=False)

    with open(os.path.join(HERE, "result.json")) as fh:
        res = json.load(fh)
    res["datasets"] = [{
        "id": "dryad-cakile-hybrids-B8QS5T",
        "name": "Asymmetry in fitness-related traits of later-generation hybrids between two invasive species (Cakile edentula x C. maritima), file Chengjun_Experiment.csv",
        "landing_url": "https://datadryad.org/dataset/doi:10.25338/B8QS5T", "doi": "10.25338/B8QS5T",
        "version": "Dryad version (API version id 105038)", "license": "CC0 1.0", "files": FILES,
        "role": "individual-plant traits for parental, F1, F2 and backcross generations of an artificial interspecific cross",
    }]
    res["method"] = (
        f"The artificial-cross table was read; {n_tr} continuous traits had >= {MIN_N} F1 and F2 plants. For each trait the "
        f"mean-scaled variance (variance of log values, or variance over squared mean for traits with zeros) was computed in F1 "
        f"(n = {len(f1)} plants) and F2 (n = {len(f2)} plants); the median F2/F1 ratio and an exact sign test on the number of traits "
        f"with ratio > 1 were evaluated against the pre-registered thresholds. F1 variance was also compared with both parental species."
    )
    res["measured"] = {
        "value": med, "unit": "median across traits of the F2/F1 ratio of mean-scaled phenotypic variance", "n": n_tr,
        "uncertainty": f"{n_gt} of {n_tr} traits with ratio > 1; exact sign-test p = {p_sign:.4f}; ratio range {ratios.min():.2f}-{ratios.max():.2f}",
        "extra": {"n_F1_plants": int(len(f1)), "n_F2_plants": int(len(f2)), "n_traits_F2_more_variable": n_gt, "sign_test_p": p_sign,
                  "n_traits_levene_p_lt_0.05_and_F2_greater": int(((tab["levene_p"] < 0.05) & (tab["ratio_F2_F1"] > 1)).sum()),
                  "n_traits_levene_p_lt_0.05_and_F1_greater": int(((tab["levene_p"] < 0.05) & (tab["ratio_F2_F1"] < 1)).sum()),
                  "preregistered_rule_covered_outcome": bool(med >= 1.5 or med <= 1.0 or majority or n_gt <= n_tr / 2),
                  "per_trait_ratio": {r["trait"]: round(r["ratio_F2_F1"], 3) for _, r in tab.iterrows()},
                  "F1_vs_parents_extra": f1_vs_par},
    }
    res["verdict"] = verdict
    res["confidence"] = 0.5
    res["caveats"] = [
        "The outcome (median F2/F1 variance ratio between 1.0 and 1.5 with a bare, non-significant majority of traits more variable in F2) fell in a gap of the pre-registered decision rule; it is recorded as 'mixed'. By trait the pattern is strongly heterogeneous: floral and plant-size traits are 3-8 times more variable in F2, whereas seed mass, germination, phenology and fruit/seed counts are less variable in F2 than in F1.",
        "A single interspecific plant cross with 36 F2 plants; Darwin's generalisation covers many plant and animal hybrids.",
        "F1 plants come from many independent parental pairs (families), which adds between-family variance to F1 that a single-pair F1 would not have; this biases against the claim.",
        "Mean-scaled variance compares dispersion across traits of different units but is sensitive to small means for count traits.",
        "Environmental variance in a common garden is included in both generations and cannot be separated from segregational variance here.",
        "The claim's causal clause (disturbed reproductive system of hybrids) is not tested; Mendelian segregation in F2 is the modern explanation of the same pattern.",
    ]
    res["status"] = "complete"
    res["agent"]["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(HERE, "result.json"), "w") as fh:
        json.dump(res, fh, indent=2)
        fh.write("\n")
    print(json.dumps({"verdict": verdict, "measured": res["measured"]}, indent=2))


if __name__ == "__main__":
    main()
