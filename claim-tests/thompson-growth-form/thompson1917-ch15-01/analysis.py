#!/usr/bin/env python3
"""thompson1917-ch15-01: hard-shelled eggs are prolate, never oblate.

Uses the Amniote Life-History Database (Myhrvold et al. 2015, Ecology 96:3109, data paper E096-269,
CC0), which records species-mean egg length and width for birds and reptiles. The two Dryad
compilations named in the pre-registration could not be downloaded (Dryad's file downloads sit
behind an interactive anti-bot challenge), so this database, which holds the same two variables for
a broader set of taxa, replaces them. Writes derived/measured.json, derived/files.json and
derived/near_spherical_species.csv.
"""
import hashlib
import json
import os
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

URL = "https://esapubs.org/archive/ecol/E096/269/Data_Files/Amniote_Database_Aug_2015.csv"
DEST = os.path.join(DATA, "Amniote_Database_Aug_2015.csv")


def fetch(url, dest):
    if not os.path.exists(dest):
        r = requests.get(url, timeout=300, headers={"User-Agent": "delphi-claim-tests/1.0"})
        r.raise_for_status()
        open(dest, "wb").write(r.content)
    h = hashlib.sha256(open(dest, "rb").read()).hexdigest()
    return {"download_url": url, "retrieved_at": datetime.fromtimestamp(os.path.getmtime(dest), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": os.path.getsize(dest), "sha256": h}


def group_stats(sub):
    ratio = sub["LB"]
    return {
        "n_species": int(len(sub)),
        "n_oblate_LB_lt_1.00": int((ratio < 1.00).sum()),
        "n_robustly_oblate_LB_lt_0.98": int((ratio < 0.98).sum()),
        "n_near_spherical_LB_lt_1.05": int((ratio < 1.05).sum()),
        "frac_near_spherical_LB_lt_1.05": float((ratio < 1.05).mean()),
        "min_LB": float(ratio.min()),
        "min_LB_species": " ".join(sub.loc[ratio.idxmin(), ["genus", "species"]].tolist()),
        "median_LB": float(ratio.median()),
        "max_LB": float(ratio.max()),
        "quantiles_LB": {q: float(ratio.quantile(float(q))) for q in ("0.01", "0.05", "0.5", "0.95", "0.99")},
    }


def main():
    files = [fetch(URL, DEST)]
    df = pd.read_csv(DEST, low_memory=False, na_values=["-999"])
    eggs = df[(df["egg_length_mm"] > 0) & (df["egg_width_mm"] > 0)].copy()
    eggs["LB"] = eggs["egg_length_mm"] / eggs["egg_width_mm"]
    # The database follows the convention length = pole-to-pole; flag rows where width > length as recorded.
    out = {"source_rows": int(len(df)), "rows_with_egg_length_and_width": int(len(eggs))}
    groups = {
        "Aves": eggs[eggs["class"] == "Aves"],
        "Testudines": eggs[(eggs["class"] == "Reptilia") & (eggs["order"] == "Testudines")],
        "Crocodylia": eggs[(eggs["class"] == "Reptilia") & (eggs["order"].isin(["Crocodylia", "Crocodilia"]))],
        "Squamata_out_of_scope": eggs[(eggs["class"] == "Reptilia") & (eggs["order"] == "Squamata")],
    }
    out["reptile_orders_present"] = {k: int(v) for k, v in eggs[eggs["class"] == "Reptilia"]["order"].value_counts().items()}
    out["groups"] = {g: group_stats(sub) for g, sub in groups.items() if len(sub)}
    in_scope = pd.concat([groups["Aves"], groups["Testudines"], groups["Crocodylia"]])
    out["in_scope_total"] = group_stats(in_scope)
    near = in_scope[in_scope["LB"] < 1.05].sort_values("LB")[["class", "order", "family", "genus", "species", "egg_length_mm", "egg_width_mm", "LB"]]
    near.to_csv(os.path.join(DERIVED, "near_spherical_species.csv"), index=False)
    out["near_spherical_in_scope_species"] = near.head(40).to_dict(orient="records")
    # Any recorded width > length in scope?
    oblate = in_scope[in_scope["LB"] < 1.0][["class", "order", "family", "genus", "species", "egg_length_mm", "egg_width_mm", "LB"]]
    out["oblate_records_in_scope"] = oblate.to_dict(orient="records")
    n_obl = int((in_scope["LB"] < 1.0).sum())
    n_rob = int((in_scope["LB"] < 0.98).sum())
    if n_rob > 0:
        verdict = "refutes"
    elif n_obl > 0:
        verdict = "mixed"
    else:
        verdict = "supports"
    out["criteria"] = {"zero_species_LB_lt_1.00_in_scope": n_obl == 0, "zero_species_LB_lt_0.98_in_scope": n_rob == 0}
    out["verdict_by_prereg_rule"] = verdict
    json.dump(out, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    json.dump(files, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
