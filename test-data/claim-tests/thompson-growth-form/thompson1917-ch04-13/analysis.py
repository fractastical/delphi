#!/usr/bin/env python3
"""thompson1917-ch04-13: haploid chromosome numbers mostly between 6 and 16?

Plants: CCDB statistics service (species-level parsed gametophytic n) for the four major groups.
Animals: Animal Chromosome Count Database table embedded in its download page (2N, N per record).
Writes derived/measured.json, derived/files.json and derived/histograms.csv.
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
UA = {"User-Agent": "delphi-claim-tests/1.0"}

CCDB_GROUPS = ["Angiosperms", "Gymnosperms", "Pteridophytes", "Bryophytes"]
CCDB_URL = "https://ccdb.tau.ac.il/services/statistics/?majorGroup={g}&format=csv"
ACC_URL = "https://cromanpa94.github.io/ACC/category/download.html"


def fetch(url, dest):
    if not os.path.exists(dest):
        r = requests.get(url, timeout=600, headers=UA)
        r.raise_for_status()
        open(dest, "wb").write(r.content)
    h = hashlib.sha256(open(dest, "rb").read()).hexdigest()
    return {"download_url": url, "retrieved_at": datetime.fromtimestamp(os.path.getmtime(dest), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": os.path.getsize(dest), "sha256": h}


def load_ccdb():
    files, frames = [], []
    for g in CCDB_GROUPS:
        dest = os.path.join(DATA, f"ccdb_statistics_{g}.csv")
        files.append(fetch(CCDB_URL.format(g=g), dest))
        d = pd.read_csv(dest)
        d["major_group"] = g
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df["n"] = pd.to_numeric(df["median"], errors="coerce")
    df = df[df["n"].notna() & (df["n"] > 0)].copy()
    df["genus"] = df["resolved_name"].astype(str).str.split().str[0]
    df["species"] = df["resolved_name"].astype(str).str.split().str[:2].str.join(" ")
    return df, files


def load_acc():
    dest = os.path.join(DATA, "acc_download.html")
    files = [fetch(ACC_URL, dest)]
    html = open(dest, encoding="utf-8", errors="ignore").read()
    i = html.find('"data":[')
    j = html.find('],"container"', i)
    data = json.loads(html[i + len('"data":'):j + 1])
    cols = ["Phylum", "Class", "Order", "Family", "Genus", "Species", "2N", "N", "Reference"]
    df = pd.DataFrame({c: data[k] for k, c in enumerate(cols)})

    def to_num(x):
        if x is None:
            return np.nan
        s = str(x).strip()
        m = re.match(r"^(\d+(\.\d+)?)$", s)
        return float(m.group(1)) if m else np.nan

    df["N_num"] = df["N"].map(to_num)
    df["twoN_num"] = df["2N"].map(to_num)
    df["n"] = df["N_num"].where(df["N_num"].notna(), df["twoN_num"] / 2.0)
    df = df[df["n"].notna() & (df["n"] > 0)].copy()
    df["species"] = df["Genus"].astype(str).str.strip() + " " + df["Species"].astype(str).str.strip()
    df["genus"] = df["Genus"].astype(str).str.strip()
    return df, files


def tails(values):
    v = np.asarray(values, dtype=float)
    return {"n_taxa": int(len(v)), "f_low_lt6": float((v < 6).mean()), "f_mid_6_16": float(((v >= 6) & (v <= 16)).mean()),
            "f_high_gt16": float((v > 16).mean()), "median_n": float(np.median(v)), "q05": float(np.quantile(v, 0.05)),
            "q95": float(np.quantile(v, 0.95)), "mode_n": float(pd.Series(v).round().mode().iloc[0])}


def kingdom_stats(df):
    sp = df.groupby("species")["n"].median()
    gen = df.groupby("genus")["n"].median()
    return {"records": int(len(df)), "species_level": tails(sp.values), "genus_level": tails(gen.values)}, sp, gen


def main():
    plants, f1 = load_ccdb()
    animals, f2 = load_acc()
    out = {"plants": {}, "animals": {}}
    out["plants"], psp, pgen = kingdom_stats(plants)
    out["plants"]["by_major_group_species_level"] = {g: tails(sub.groupby("species")["n"].median().values) for g, sub in plants.groupby("major_group")}
    out["animals"], asp, agen = kingdom_stats(animals)
    out["animals"]["by_phylum_species_level"] = {p: tails(sub.groupby("species")["n"].median().values) for p, sub in animals.groupby("Phylum") if sub["species"].nunique() >= 50}
    # Histograms of haploid number (species level), 1..60+
    bins = list(range(1, 61)) + [np.inf]
    hist = pd.DataFrame({
        "n": [str(b) for b in range(1, 60)] + ["60+"],
        "plant_species": np.histogram(psp.values, bins=bins)[0],
        "animal_species": np.histogram(asp.values, bins=bins)[0],
        "plant_genera": np.histogram(pgen.values, bins=bins)[0],
        "animal_genera": np.histogram(agen.values, bins=bins)[0],
    })
    hist.to_csv(os.path.join(DERIVED, "histograms.csv"), index=False)
    pg, ag = out["plants"]["genus_level"], out["animals"]["genus_level"]
    supports = all(k["f_low_lt6"] <= 0.10 and k["f_high_gt16"] <= 0.10 and k["f_high_gt16"] <= k["f_low_lt6"] for k in (pg, ag))
    refutes = (pg["f_high_gt16"] >= 0.25 or ag["f_high_gt16"] >= 0.25) or (pg["f_high_gt16"] > pg["f_low_lt6"] and ag["f_high_gt16"] > ag["f_low_lt6"])
    out["criteria"] = {"supports_rule": bool(supports), "refutes_rule": bool(refutes)}
    out["verdict_by_prereg_rule"] = "supports" if supports else ("refutes" if refutes else "mixed")
    json.dump(out, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    json.dump({"ccdb": f1, "acc": f2}, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
