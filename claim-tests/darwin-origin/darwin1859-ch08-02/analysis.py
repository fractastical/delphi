#!/usr/bin/env python3
"""Test darwin1859-ch08-02: close interbreeding lessens fertility; an occasional cross with a
distinct stock increases it.

Dataset 1: Auclair et al. 2025 Pyrenean brown bear pedigree (Dryad), litter size vs inbreeding.
Dataset 2: Pekkala et al. 2014 Drosophila littoralis inbreeding/heterosis experiment (Dryad),
offspring fecundity for within-population, inter-population and full-sib crosses.

Re-run:  python3 analysis.py   (downloads two small Dryad version archives into ./data)
"""
import hashlib
import io
import json
import math
import os
import re
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
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
BEAR_URL = "https://datadryad.org/api/v2/versions/402719/download"   # doi:10.5061/dryad.w9ghx3g1s v3
FLY_URL = "https://datadryad.org/api/v2/versions/6545/download"      # doi:10.5061/dryad.10154
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
            "byte_size": len(body), "sha256": hashlib.sha256(body).hexdigest(), "note": "Dryad version zip; redirects to a signed S3 URL"}
    with open(path, "wb") as fh:
        fh.write(body)
    with open(meta_path, "w") as fh:
        json.dump(meta, fh)
    FILES.append(meta)
    return path


def read_xlsx_sheet(xlsx_bytes, sheet_path="xl/worksheets/sheet1.xml"):
    """Minimal .xlsx reader (shared strings + inline values) -> DataFrame with header row."""
    z = zipfile.ZipFile(io.BytesIO(xlsx_bytes))
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", ns):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
    root = ET.fromstring(z.read(sheet_path))
    rows = {}
    for c in root.iter("{%s}c" % ns["m"]):
        ref = c.get("r")
        col = re.match(r"[A-Z]+", ref).group(0)
        row = int(ref[len(col):])
        v = c.find("m:v", ns)
        t = c.get("t")
        if v is None:
            val = None
        elif t == "s":
            val = shared[int(v.text)]
        elif t == "str" or t == "inlineStr":
            val = v.text
        else:
            try:
                val = float(v.text)
            except ValueError:
                val = v.text
        rows.setdefault(row, {})[col] = val
    def col_idx(col):
        n = 0
        for ch in col:
            n = n * 26 + ord(ch) - 64
        return n
    header_row = min(rows)
    header = rows[header_row]
    cols = sorted(header, key=col_idx)
    data = []
    for r in sorted(rows):
        if r == header_row:
            continue
        data.append([rows[r].get(c) for c in cols])
    return pd.DataFrame(data, columns=[str(header[c]).strip() for c in cols])


def bear():
    zpath = fetch(BEAR_URL, "dryad_w9ghx3g1s_v3.zip")
    with zipfile.ZipFile(zpath) as z:
        df = pd.read_csv(io.BytesIO(z.read("litter_size_dt.csv")))
    df = df.dropna(subset=["Litter_size", "Inbreeding_mother"])
    x, y = df["Inbreeding_mother"].to_numpy(float), df["Litter_size"].to_numpy(float)
    res = stats.linregress(x, y)
    p_one = res.pvalue / 2 if res.slope < 0 else 1 - res.pvalue / 2
    rho, prho = stats.spearmanr(x, y)
    out = {"n_litters": int(len(df)), "n_mothers": int(df["Id_mother"].nunique()),
           "slope_litter_size_per_unit_F_mother": float(res.slope), "intercept": float(res.intercept),
           "slope_se": float(res.stderr), "p_two_sided": float(res.pvalue), "p_one_sided_negative": float(p_one),
           "spearman_rho": float(rho), "spearman_p": float(prho),
           "F_mother_range": [float(x.min()), float(x.max())], "mean_litter_size": float(y.mean()),
           "pass": bool(res.slope < 0 and p_one < 0.05)}
    # extra: inbreeding of the litter itself (parents' relatedness), the more direct reading of 'close interbreeding'
    d2 = df.dropna(subset=["Inbreeding_individual"])
    r2 = stats.linregress(d2["Inbreeding_individual"].to_numpy(float), d2["Litter_size"].to_numpy(float))
    out["extra_litter_F"] = {"n": int(len(d2)), "slope_litter_size_per_unit_F_litter": float(r2.slope), "p_two_sided": float(r2.pvalue),
                             "p_one_sided_negative": float(r2.pvalue / 2 if r2.slope < 0 else 1 - r2.pvalue / 2)}
    # mother-level means
    m = df.groupby("Id_mother").agg(F=("Inbreeding_mother", "first"), ls=("Litter_size", "mean"))
    r3 = stats.linregress(m["F"].to_numpy(float), m["ls"].to_numpy(float))
    out["mother_level"] = {"n_mothers": int(len(m)), "slope": float(r3.slope), "p_two_sided": float(r3.pvalue)}
    df[["Birth_year", "Id_mother", "Litter_size", "Inbreeding_individual", "Inbreeding_mother", "Mother_age", "Primiparity"]].to_csv(
        os.path.join(DERIVED, "bear_litter_size_inbreeding.csv"), index=False)
    return out


def fly():
    zpath = fetch(FLY_URL, "dryad_10154.zip")
    with zipfile.ZipFile(zpath) as z:
        xlsx = z.read("Data Pekkala et al EVOL APPL.xlsx")
    df = read_xlsx_sheet(xlsx, "xl/worksheets/sheet1.xml")
    df.columns = [c.strip() for c in df.columns]
    fec_col = [c for c in df.columns if c.lower().startswith("f eggs")][0]
    cross_col = [c for c in df.columns if c.lower().startswith("p cross")][0]
    size_col = [c for c in df.columns if c.lower().startswith("pop size")][0]
    gen_col = [c for c in df.columns if c.lower().startswith("f exp gen")][0]
    finbr_col = [c for c in df.columns if c.lower().startswith("f est inbr")][0]
    pop1_col = [c for c in df.columns if c.lower().startswith("pop 1")][0]
    df = df.dropna(subset=[fec_col, cross_col])
    df[fec_col] = pd.to_numeric(df[fec_col], errors="coerce")
    df = df.dropna(subset=[fec_col])
    df["cross"] = pd.to_numeric(df[cross_col], errors="coerce")
    df["size"] = df[size_col].astype(str).str.strip()
    df["gen"] = pd.to_numeric(df[gen_col], errors="coerce")
    df["F_est"] = pd.to_numeric(df[finbr_col], errors="coerce")
    sizes = sorted(df["size"].unique())
    print(f"fly rows {len(df)}, size labels {sizes}, cross types {sorted(df['cross'].dropna().unique())}", file=sys.stderr)
    df[["size", gen_col, cross_col, pop1_col, finbr_col, fec_col]].to_csv(os.path.join(DERIVED, "fly_fecundity_by_cross.csv"), index=False)

    # (a) inbred populations (within-population random mating, cross type 1) vs the outbred control.
    # The outbred control is the large population (size label >= 100, i.e. the N = 500 control of the paper);
    # any non-numeric label is also treated as control. Failing both, rows with estimated F = 0 are used.
    within = df[df["cross"] == 1]
    def as_num(s):
        try:
            return float(s)
        except ValueError:
            return None
    control_labels = [s for s in sizes if as_num(s) is None or as_num(s) >= 100]
    if control_labels:
        control = within[within["size"].isin(control_labels)]
        treat = within[~within["size"].isin(control_labels)]
    else:
        control = within[within["F_est"].fillna(0) <= 0]
        treat = within[within["F_est"].fillna(0) > 0]
    ctrl_mean = float(control[fec_col].mean()) if len(control) else float("nan")
    by_size = {}
    n_below = 0
    for s, g in treat.groupby("size"):
        m = float(g[fec_col].mean())
        t = stats.ttest_ind(control[fec_col], g[fec_col], equal_var=False) if len(control) > 1 and len(g) > 1 else None
        by_size[s] = {"n": int(len(g)), "mean_fecundity": m, "control_mean": ctrl_mean,
                      "welch_p_two_sided": float(t.pvalue) if t else None, "below_control": bool(m < ctrl_mean)}
        n_below += int(m < ctrl_mean)
    # dose-response: fecundity vs estimated inbreeding coefficient over all within-population rows
    dd = within.dropna(subset=["F_est"])
    slope = stats.linregress(dd["F_est"].to_numpy(float), dd[fec_col].to_numpy(float)) if len(dd) > 2 else None
    pass_a = n_below >= 2 and len(by_size) >= 2

    # (b) heterosis: inter-population crosses (type 2) vs within-population random crosses (type 1), by size x generation
    het_rows = []
    for (s, gen), g in df[df["cross"].isin([1, 2])].groupby(["size", "gen"]):
        w, b = g[g["cross"] == 1][fec_col], g[g["cross"] == 2][fec_col]
        if len(w) and len(b):
            het_rows.append({"size": s, "gen": gen, "n_within": int(len(w)), "n_between": int(len(b)),
                             "mean_within": float(w.mean()), "mean_between": float(b.mean()),
                             "heterosis": float((b.mean() - w.mean()) / w.mean()) if w.mean() else None})
    het = pd.DataFrame(het_rows)
    het.to_csv(os.path.join(DERIVED, "fly_heterosis_by_size_generation.csv"), index=False)
    n_pos = int((het["heterosis"] > 0).sum()) if len(het) else 0
    pass_b = len(het) > 0 and n_pos > len(het) / 2
    allw = df[df["cross"] == 1][fec_col]; allb = df[df["cross"] == 2][fec_col]
    mw = stats.mannwhitneyu(allb, allw, alternative="greater") if len(allw) and len(allb) else None
    fullsib = df[df["cross"] == 3][fec_col]
    return {"n_rows": int(len(df)), "size_labels": sizes, "control_labels": control_labels, "control_n": int(len(control)),
            "control_mean_fecundity": ctrl_mean, "inbred_by_size": by_size, "n_sizes_below_control": n_below,
            "slope_fecundity_vs_F_est": float(slope.slope) if slope else None, "slope_p": float(slope.pvalue) if slope else None,
            "pass_a": bool(pass_a), "heterosis_cells": het_rows, "n_cells_positive_heterosis": n_pos, "n_cells": int(len(het)),
            "pooled_mean_within": float(allw.mean()), "pooled_mean_between": float(allb.mean()),
            "mannwhitney_p_between_gt_within": float(mw.pvalue) if mw else None,
            "fullsib_mean_fecundity": float(fullsib.mean()) if len(fullsib) else None, "pass_b": bool(pass_b)}


def main():
    b = bear()
    f = fly()
    d1, a, bb = b["pass"], f["pass_a"], f["pass_b"]
    if d1 and a and bb:
        verdict = "supports"
    elif (d1 and (a or bb)) or (not d1 and a and bb):
        verdict = "mixed"
    elif not d1 and not a:
        verdict = "refutes"
    else:
        verdict = "mixed"

    with open(os.path.join(HERE, "result.json")) as fh:
        res = json.load(fh)
    res["datasets"] = [
        {"id": "dryad-auclair2025-pyrenean-brown-bear-inbreeding",
         "name": "Data from: Inbreeding depression across multiple life history traits in a long-lived mammal (Pyrenean brown bear), file litter_size_dt.csv",
         "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.w9ghx3g1s", "doi": "10.5061/dryad.w9ghx3g1s",
         "version": "Dryad version 3 (paper doi:10.1111/mec.70123)", "license": "CC0 1.0", "files": FILES[:1],
         "role": "litter size and pedigree inbreeding coefficients of mother and litter"},
        {"id": "dryad-pekkala2014-drosophila-littoralis-inbreeding-heterosis",
         "name": "Data from: The effect of inbreeding rate on fitness, inbreeding depression and heterosis over a range of inbreeding coefficients (Drosophila littoralis)",
         "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.10154", "doi": "10.5061/dryad.10154",
         "version": "Dryad version 1 (paper doi:10.1111/eva.12145)", "license": "CC0 1.0", "files": FILES[1:],
         "role": "offspring fecundity for within-population, inter-population and full-sib crosses at three population sizes"},
    ]
    res["method"] = (
        f"Bear: ordinary least-squares regression of litter size on the mother's pedigree inbreeding coefficient over {b['n_litters']} litters "
        f"({b['n_mothers']} mothers), one-sided test for a negative slope; the litter's own inbreeding coefficient and mother-level means are "
        f"reported as extras. Fly: the DATA sheet of the Dryad workbook was parsed; offspring fecundity ('F eggs per vial') of within-population "
        f"random crosses (type 1) in the inbred treatments was compared with the outbred control, and inter-population crosses (type 2) were "
        f"compared with within-population crosses in each population-size x generation cell (relative heterosis), plus a pooled one-sided Mann-Whitney test."
    )
    res["measured"] = {
        "value": b["slope_litter_size_per_unit_F_mother"], "unit": "cubs per litter per unit maternal inbreeding coefficient (OLS slope)",
        "n": b["n_litters"], "uncertainty": f"SE {b['slope_se']:.3f}; one-sided p = {b['p_one_sided_negative']:.4f}",
        "extra": {"bear": b, "fly": f},
    }
    res["verdict"] = verdict
    res["confidence"] = 0.65
    res["caveats"] = [
        "The pre-registered bear test is marginal (one-sided p = 0.044, n = 66 litters); the litter's own inbreeding coefficient gives a clearer signal (p = 0.001). In the fly data the N = 40 treatment was not less fecund than the N = 500 control, so inbreeding depression in fecundity appears only at the two smallest population sizes, although fecundity declines significantly with the estimated inbreeding coefficient overall.",
        "Two datasets only (one wild mammal population of a few dozen mothers; one laboratory Drosophila experiment); Darwin's claim is about plants and animals generally.",
        "The pre-registered bear test uses the mother's inbreeding coefficient; the litter's own coefficient (closeness of the parents) is the more literal reading of 'close interbreeding' and is reported as an extra.",
        "Bear litter sizes are counts (1-3) observed in the field; detection delay and maternal age are confounders that the simple regression does not model (the source paper fits mixed models with these covariates).",
        "In the fly experiment 'distinct variety' is another inbred laboratory population of the same species, not a distinct variety in Darwin's sense; heterosis there reflects complementation of different fixed deleterious alleles.",
        "The clause attributing the decline of hybrids over generations to close interbreeding is not tested.",
    ]
    res["status"] = "complete"
    res["agent"]["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(HERE, "result.json"), "w") as fh:
        json.dump(res, fh, indent=2)
        fh.write("\n")
    print(json.dumps({"verdict": verdict, "bear": b, "fly": {k: v for k, v in f.items() if k != "heterosis_cells"}}, indent=2))


if __name__ == "__main__":
    main()
