#!/usr/bin/env python3
"""Test darwin1859-ch14-12: no cataclysm has ever desolated the whole world; descent was never
broken. Stage-boundary crossing fractions of marine animal genera (PBDB occs/diversity),
overall and per major lineage.

Re-run:  python3 analysis.py
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

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
PBDB = "https://paleobiodb.org/data1.2"
LINEAGES = ["Mollusca", "Brachiopoda", "Arthropoda", "Echinodermata", "Cnidaria", "Bryozoa", "Porifera", "Annelida", "Chordata"]
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


def diversity(base_name):
    body = fetch(f"{PBDB}/occs/diversity.json", f"pbdb_diversity_marine_{base_name}_stage.json",
                 params={"base_name": base_name, "interval": "Phanerozoic", "envtype": "marine",
                         "count": "genera", "time_reso": "stage", "vocab": "pbdb"})
    df = pd.DataFrame(json.loads(body)["records"])
    for c in ["max_ma", "min_ma", "X_Ft", "X_bL", "X_FL", "X_bt", "n_occs"]:
        df[c] = pd.to_numeric(df[c])
    df = df.sort_values("max_ma", ascending=False).reset_index(drop=True)
    df["present"] = df["X_Ft"] + df["X_bL"] + df["X_FL"] + df["X_bt"]
    df["crossing"] = (df["X_bt"] + df["X_Ft"]) / df["present"].where(df["present"] > 0)
    return df


def main():
    all_df = diversity("Animalia")
    all_df = all_df[all_df["present"] > 0].iloc[:-2].copy()
    worst = all_df.loc[all_df["crossing"].idxmin()]
    lineage_rows = []
    for lin in LINEAGES:
        d = diversity(lin)
        row = d[d["interval_name"] == worst["interval_name"]]
        if len(row) and row["present"].iloc[0] > 0:
            r = row.iloc[0]
            lineage_rows.append({"lineage": lin, "stage": worst["interval_name"], "present": int(r["present"]),
                                 "crossing_genera": int(r["X_bt"] + r["X_Ft"]), "crossing_fraction": float(r["crossing"])})
        else:
            lineage_rows.append({"lineage": lin, "stage": worst["interval_name"], "present": 0, "crossing_genera": 0, "crossing_fraction": None})
    lin_df = pd.DataFrame(lineage_rows)
    lin_df.to_csv(os.path.join(DERIVED, "lineage_survival_at_worst_boundary.csv"), index=False)
    all_df[["interval_name", "max_ma", "min_ma", "present", "X_bt", "X_Ft", "X_bL", "X_FL", "crossing", "n_occs"]].to_csv(
        os.path.join(DERIVED, "stage_boundary_crossing_marine_genera.csv"), index=False)

    min_c = float(worst["crossing"])
    n_lin_surv = int((lin_df["crossing_genera"] > 0).sum())
    med_c = float(all_df["crossing"].median())
    c1, c2, c3 = min_c >= 0.10, n_lin_surv >= 7, med_c >= 0.5
    if c1 and c2 and c3:
        verdict = "supports"
    elif (c1 and c2) or (0.05 <= min_c < 0.10 and c2):
        verdict = "mixed"
    else:
        verdict = "refutes"
    lowest5 = all_df.nsmallest(5, "crossing")[["interval_name", "crossing", "present"]]

    with open(os.path.join(HERE, "result.json")) as fh:
        res = json.load(fh)
    res["datasets"] = [
        {"id": "pbdb-occs-diversity-marine-genera-by-stage",
         "name": "Paleobiology Database occs/diversity: marine Animalia genus range categories per stage, Phanerozoic",
         "landing_url": "https://paleobiodb.org/data1.2/occs/diversity_doc.html", "doi": None,
         "version": "live API data1.2, retrieved " + FILES[0]["retrieved_at"][:10], "license": "CC BY 4.0",
         "files": FILES[:1], "role": "overall boundary-crossing fractions"},
        {"id": "pbdb-occs-diversity-marine-genera-by-stage-per-phylum",
         "name": "Paleobiology Database occs/diversity for nine marine animal lineages (" + ", ".join(LINEAGES) + ")",
         "landing_url": "https://paleobiodb.org/data1.2/occs/diversity_doc.html", "doi": None,
         "version": "live API data1.2, retrieved " + FILES[0]["retrieved_at"][:10], "license": "CC BY 4.0",
         "files": FILES[1:], "role": "survivors per lineage at the worst boundary"},
    ]
    res["method"] = (
        f"For each of {len(all_df)} Phanerozoic stages (two youngest dropped) the fraction of marine animal genera present that are "
        f"also recorded after the stage (X_bt + X_Ft over all present) was computed from the PBDB diversity table. The stage with the "
        f"lowest crossing fraction ({worst['interval_name']}) was identified and the same table was retrieved for nine major lineages "
        f"to count survivors across that boundary."
    )
    res["measured"] = {
        "value": min_c, "unit": "minimum stage-boundary crossing fraction of marine animal genera (Phanerozoic)", "n": int(len(all_df)),
        "uncertainty": None,
        "extra": {"worst_stage": str(worst["interval_name"]), "worst_stage_genera_present": int(worst["present"]),
                  "worst_stage_crossing_genera": int(worst["X_bt"] + worst["X_Ft"]),
                  "lineages_with_survivors_at_worst_boundary": n_lin_surv, "n_lineages": len(LINEAGES),
                  "lineage_survival": lineage_rows, "median_crossing_fraction": med_c,
                  "five_lowest_crossing_stages": lowest5.to_dict(orient="records"),
                  "conditions": {"c1_min_crossing_ge_0.10": bool(c1), "c2_ge_7_of_9_lineages_survive": bool(c2), "c3_median_ge_0.5": bool(c3)}},
    }
    res["verdict"] = verdict
    res["confidence"] = 0.85
    res["caveats"] = [
        "Only the Phanerozoic marine record is tested; the claim's Precambrian ancestry statement and terrestrial life are untested.",
        "Boundary-crossing fractions are depressed by incomplete sampling (Signor-Lipps, Lazarus taxa) and by stage boundaries having been drawn at faunal breaks; both biases work against the claim, so a pass is conservative.",
        "Genus-level survival understates species-level loss; Darwin's claim concerns continuity of descent, for which any surviving lineage suffices, so genus level is appropriate.",
        "Stage-level resolution cannot distinguish a single instantaneous event from a protracted crisis within one stage.",
    ]
    res["status"] = "complete"
    res["agent"]["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(HERE, "result.json"), "w") as fh:
        json.dump(res, fh, indent=2)
        fh.write("\n")
    print(json.dumps({"verdict": verdict, "measured": res["measured"]}, indent=2))


if __name__ == "__main__":
    main()
