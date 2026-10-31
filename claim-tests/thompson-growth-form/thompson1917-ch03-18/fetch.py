#!/usr/bin/env python3
"""Download ICES DATRAS NS-IBTS CA (age/weight/maturity) and HH (haul) records,
Q1 and Q3, 2015-2024, and build the small derived tables used by analysis.py
(this directory, claim ch03-18) and by ../thompson1917-ch02-01/analysis.py.

Raw XML goes to data/ (git-ignored); data/manifest.json records URL, time,
size and SHA-256 of every file.  Usage: python3 fetch.py [--derive-only]
"""
import csv, hashlib, json, math, os, sys, time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
BASE = "https://datras.ices.dk/WebServices/DATRASWebService.asmx"
SURVEY = "NS-IBTS"
YEARS = range(2015, 2025)
QUARTERS = (1, 3)
PLAICE_APHIA = "127143"
NS = "{ices.dk.local/DATRAS}"

# Maturity code mapping fixed in the pre-registration (result.json).
MAT_GROUP = {
    "1": "immature", "61": "immature", "A": "immature", "I": "immature",
    "2": "maturing", "62": "maturing", "B": "maturing",
    "3": "spawning", "63": "spawning", "C": "spawning",
    "4": "spent", "64": "spent", "D": "spent",
    "5": "resting", "65": "resting", "E": "resting",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(kind, year, quarter, manifest):
    url = f"{BASE}/get{kind}data?survey={SURVEY}&year={year}&quarter={quarter}"
    name = f"{SURVEY}_{year}_Q{quarter}_{kind}.xml"
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        for attempt in range(4):
            try:
                r = requests.get(url, timeout=600)
                r.raise_for_status()
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 3:
                    raise
                print("retry", name, e, file=sys.stderr)
                time.sleep(5 * (attempt + 1))
        with open(path, "wb") as f:
            f.write(r.content)
        manifest[name] = {
            "download_url": url,
            "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "byte_size": len(r.content),
            "sha256": sha256(path),
        }
        print("downloaded", name, len(r.content), file=sys.stderr)
    return path


def records(path):
    """Yield dicts of stripped field values from a DATRAS XML file."""
    for _, el in ET.iterparse(path, events=("end",)):
        if el.tag in (NS + "Cls_DatrasExchange_CA", NS + "Cls_DatrasExchange_HH"):
            yield {child.tag[len(NS):]: (child.text or "").strip() for child in el}
            el.clear()


def haul_key(r):
    return (r["Year"], r["Quarter"], r["Country"], r["Ship"], r["Gear"], r["StNo"], r["HaulNo"])


def length_cm(r):
    code, cls = r["LngtCode"], float(r["LngtClass"])
    if cls < 0:
        return None
    if code == "1":
        return cls
    if code in (".", "0"):
        return cls / 10.0
    return None


def derive():
    """Pass over all CA files once, keep individual weighed fish in memory, apply the
    pre-registered cleaning rules at the individual level, then aggregate."""
    import pandas as pd
    import numpy as np
    manifest = json.load(open(os.path.join(DATA, "manifest.json")))
    mat_codes = defaultdict(int)
    n_ca = 0
    rows = []     # all weighed single fish: aphia, quarter, L, log10W
    prows = []    # plaice with mapped maturity: year, quarter, sex, matgroup, L, log10K, doy (or -1)
    for year in YEARS:
        for q in QUARTERS:
            hh = {}
            for r in records(os.path.join(DATA, f"{SURVEY}_{year}_Q{q}_HH.xml")):
                try:
                    d = date(int(r["Year"]), int(r["Month"]), int(r["Day"]))
                except ValueError:
                    continue
                hh[haul_key(r)] = d
            for r in records(os.path.join(DATA, f"{SURVEY}_{year}_Q{q}_CA.xml")):
                n_ca += 1
                try:
                    w = float(r["IndWgt"])
                    nal = float(r["CANoAtLngt"])
                except ValueError:
                    continue
                L = length_cm(r)
                if w <= 0 or L is None or L <= 0 or nal != 1:
                    continue
                sp = r["Valid_Aphia"] or r["SpecCode"]
                rows.append((sp, q, L, math.log10(w)))
                if sp != PLAICE_APHIA:
                    continue
                mat_codes[r["Maturity"]] += 1
                grp = MAT_GROUP.get(r["Maturity"])
                if grp is None:
                    continue
                sex = r["Sex"] if r["Sex"] in ("F", "M") else "U"
                d = hh.get(haul_key(r))
                doy = d.timetuple().tm_yday if d is not None else -1
                prows.append((year, q, sex, grp, L, math.log10(100.0 * w / L ** 3), doy))
    os.makedirs(DERIVED, exist_ok=True)

    # --- ch02-01: length-weight bins per species, after dropping |resid| > 0.5 from a
    # preliminary per-species fit of log10 W on log10 L (pre-registered cleaning).
    lw = pd.DataFrame(rows, columns=["aphia", "quarter", "L", "log10w"])
    lw["log10L"] = np.log10(lw["L"])
    dropped = {}
    keep = np.ones(len(lw), dtype=bool)
    for sp, g in lw.groupby("aphia"):
        if len(g) < 3 or g["log10L"].nunique() < 2:
            continue
        b, a = np.polyfit(g["log10L"], g["log10w"], 1)
        resid = g["log10w"] - (a + b * g["log10L"])
        bad = resid.abs() > 0.5
        if bad.any():
            dropped[sp] = int(bad.sum())
            keep[g.index[bad]] = False
    lw_clean = lw[keep].copy()
    lw_clean["lcls"] = np.floor(lw_clean["L"]).astype(int)  # 1-cm class (lower bound)
    agg = lw_clean.groupby(["aphia", "quarter", "lcls"]).agg(
        n=("log10w", "size"), sum_log10w=("log10w", "sum"),
        sum_log10w_sq=("log10w", lambda s: float((s ** 2).sum()))).reset_index()
    agg.rename(columns={"lcls": "length_cm_class"}).to_csv(
        os.path.join(DERIVED, "ns_ibts_lw_bins.csv"), index=False, float_format="%.6f")

    # --- ch03-18: plaice condition cells, after dropping |log10K - cell mean| > 0.3
    # where the cell is (quarter, sex, 1-cm class) (pre-registered cleaning).
    pl = pd.DataFrame(prows, columns=["year", "quarter", "sex", "matgroup", "L", "log10k", "doy"])
    pl["lcls"] = np.floor(pl["L"]).astype(int)
    mean = pl.groupby(["quarter", "sex", "lcls"])["log10k"].transform("mean")
    bad_pl = (pl["log10k"] - mean).abs() > 0.3
    pl = pl[~bad_pl].copy()
    yr = pl.groupby(["year", "quarter", "sex", "matgroup", "lcls"]).agg(
        n=("log10k", "size"), sum_log10k=("log10k", "sum"),
        sum_log10k_sq=("log10k", lambda s: float((s ** 2).sum()))).reset_index()
    yr.rename(columns={"lcls": "length_cm_class"}).to_csv(
        os.path.join(DERIVED, "plaice_condition_year.csv"), index=False, float_format="%.6f")
    dated = pl[pl["doy"] > 0].copy()
    dated["week"] = (dated["doy"] - 1) // 7 + 1
    wk = dated.groupby(["quarter", "week", "sex", "matgroup", "lcls"]).agg(
        n=("log10k", "size"), sum_doy=("doy", "sum"), sum_log10k=("log10k", "sum"),
        sum_log10k_sq=("log10k", lambda s: float((s ** 2).sum()))).reset_index()
    wk.rename(columns={"lcls": "length_cm_class"}).to_csv(
        os.path.join(DERIVED, "plaice_condition_week.csv"), index=False, float_format="%.6f")

    summary = {
        "ca_records": n_ca, "weighed_single_fish": int(len(lw)),
        "lw_fish_dropped_resid_gt_0.5": int((~keep).sum()), "lw_dropped_by_species": dropped,
        "weighed_plaice": int(sum(mat_codes.values())),
        "plaice_with_mapped_maturity": int(len(prows)), "plaice_dropped_resid_gt_0.3": int(bad_pl.sum()),
        "plaice_kept": int(len(pl)), "plaice_kept_with_haul_date": int(len(dated)),
        "plaice_maturity_codes": dict(sorted(mat_codes.items(), key=lambda kv: -kv[1])),
        "files": manifest,
    }
    json.dump(summary, open(os.path.join(DERIVED, "fetch_summary.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "files"}, indent=1))


def main():
    os.makedirs(DATA, exist_ok=True)
    mpath = os.path.join(DATA, "manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    if "--derive-only" not in sys.argv:
        for year in YEARS:
            for q in QUARTERS:
                for kind in ("HH", "CA"):
                    download(kind, year, q, manifest)
                    json.dump(manifest, open(mpath, "w"), indent=1)
    derive()


if __name__ == "__main__":
    main()
