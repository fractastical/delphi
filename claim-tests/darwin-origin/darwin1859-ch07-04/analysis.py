#!/usr/bin/env python3
"""Test of darwin1859-ch07-04: instincts vary within species in nature; "the migratory
instinct, both in extent and direction, and in its total loss".

Primary: AVONET (Tobias et al. 2022) Migration score per bird species (1 sedentary,
2 partially migratory, 3 migratory) -> share of species that are partial migrants.
Secondary: GBIF occurrence counts in 5-degree latitude bands (0-80 N, years >= 2000)
for 12 pre-registered species -> winter residency index W = fraction of Dec-Feb records
inside the bands holding the central 80 % of Jun-Jul records; compared between the
partial-migrant and obligate-migrant sets.

Re-run:  python3 analysis.py   (downloads the 21 MB AVONET xlsx into ./data/, ~400 GBIF calls)
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
from scipy.stats import mannwhitneyu

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

AVONET_URL = "https://ndownloader.figshare.com/files/34480856"
GBIF_OCC = "https://api.gbif.org/v1/occurrence/search"
GBIF_MATCH = "https://api.gbif.org/v1/species/match"
BASIS = ["HUMAN_OBSERVATION", "PRESERVED_SPECIMEN", "MATERIAL_SAMPLE", "OCCURRENCE", "MACHINE_OBSERVATION", "MATERIAL_CITATION"]
PARTIAL = ["Erithacus rubecula", "Turdus merula", "Sylvia atricapilla", "Fringilla coelebs", "Sturnus vulgaris", "Turdus migratorius"]
OBLIGATE = ["Hirundo rustica", "Apus apus", "Phylloscopus trochilus", "Setophaga striata", "Tyrannus tyrannus", "Cuculus canorus"]
BANDS = [(lo, lo + 5) for lo in range(0, 80, 5)]
SUMMER, WINTER = ("6,7",), ("12", "1,2")   # GBIF month ranges cannot wrap the year
YEARS = "2000,2030"
P_SUPPORT, P_REFUTE, W_MEDIAN_SUPPORT = 0.20, 0.05, 0.25

REQUESTS = []


def record(label, r):
    REQUESTS.append({"label": label, "download_url": r.url, "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()})
    return REQUESTS[-1]


def get(url, params=None, label="", stream_to=None):
    for attempt in range(6):
        try:
            r = requests.get(url, params=params, timeout=600)
            if r.status_code == 200:
                rec = record(label, r)
                if stream_to:
                    open(stream_to, "wb").write(r.content)
                return r, rec
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed: {url}")


def count(params, label):
    p = [("basisOfRecord", b) for b in BASIS] + list(params.items())
    return get(GBIF_OCC, p, label)[0].json()["count"]


def main():
    # ---- primary: AVONET
    xpath = os.path.join(DATA, "AVONET_Supplementary_dataset_1.xlsx")
    if os.path.exists(xpath) and os.path.getsize(xpath) > 0:
        data = open(xpath, "rb").read()
        avonet_rec = {"download_url": AVONET_URL, "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    else:
        _, avonet_rec = get(AVONET_URL, label="avonet-xlsx", stream_to=xpath)
    sheets = pd.ExcelFile(xpath).sheet_names
    sheet = [s for s in sheets if "BirdLife" in s and "AVONET1" in s.replace("_", "")][0]
    av = pd.read_excel(xpath, sheet_name=sheet)
    mig = pd.to_numeric(av["Migration"], errors="coerce").dropna().astype(int)
    counts = mig.value_counts().to_dict()
    n_all = int(mig.size)
    n1, n2, n3 = (int(counts.get(k, 0)) for k in (1, 2, 3))
    P = n2 / n_all
    Q = n2 / (n2 + n3)
    by_order = av.assign(Migration=pd.to_numeric(av["Migration"], errors="coerce")).dropna(subset=["Migration"]).groupby("Order1")["Migration"] \
        .agg(n="size", partial=lambda s: int((s == 2).sum()), migratory=lambda s: int((s == 3).sum()))
    by_order["share_partial"] = (by_order["partial"] / by_order["n"]).round(3)
    by_order.sort_values("n", ascending=False).to_csv(os.path.join(DERIVED, "avonet_migration_by_order.csv"))
    print(f"AVONET sheet {sheet}: n={n_all} sedentary={n1} partial={n2} migratory={n3} P={P:.4f} Q={Q:.4f}", file=sys.stderr)
    avonet_species = {}
    for sp in PARTIAL + OBLIGATE:
        row = av[av["Species1"] == sp]
        avonet_species[sp] = int(row["Migration"].iloc[0]) if len(row) else None

    # ---- secondary: GBIF latitude-band counts
    band_rows = []
    W = {}
    shift = {}
    for sp in PARTIAL + OBLIGATE:
        m = get(GBIF_MATCH, {"name": sp, "rank": "SPECIES", "strict": "true"}, label=f"match:{sp}")[0].json()
        key = m.get("usageKey")
        prof = {}
        for season in (SUMMER, WINTER):
            arr = []
            for lo, hi in BANDS:
                c = sum(count({"taxonKey": key, "limit": 0, "hasCoordinate": "true", "hasGeospatialIssue": "false", "year": YEARS,
                               "month": mo, "decimalLatitude": f"{lo},{hi}"}, f"band:{sp}:{mo}:{lo}") for mo in season)
                arr.append(c)
                band_rows.append({"species": sp, "season": "summer" if season == SUMMER else "winter", "lat_lo": lo, "lat_hi": hi, "records": c})
            prof[season] = np.array(arr, dtype=float)
        s, w = prof[SUMMER], prof[WINTER]
        cum = np.cumsum(s) / s.sum()
        # a band is in the core if it overlaps the 10th-90th percentile interval of summer records
        core = np.array([(cum[i] > 0.10) and ((cum[i] - s[i] / s.sum()) < 0.90) for i in range(len(BANDS))])
        W[sp] = float(w[core].sum() / w.sum()) if w.sum() else float("nan")
        mids = np.array([(lo + hi) / 2 for lo, hi in BANDS])
        shift[sp] = float(np.average(mids, weights=s) - np.average(mids, weights=w)) if w.sum() else float("nan")
        print(f"{sp:24s} key={key} summer={int(s.sum()):9d} winter={int(w.sum()):9d} W={W[sp]:.3f} shift={shift[sp]:+.1f} deg core={[BANDS[i][0] for i in range(len(BANDS)) if core[i]]}", file=sys.stderr)
    pd.DataFrame(band_rows).to_csv(os.path.join(DERIVED, "gbif_latitude_bands.csv"), index=False)

    wp = [W[s] for s in PARTIAL]
    wo = [W[s] for s in OBLIGATE]
    mw = mannwhitneyu(wp, wo, alternative="greater")
    med_p, med_o = float(np.median(wp)), float(np.median(wo))

    if P < P_REFUTE or med_o >= med_p:
        verdict = "refutes"
    elif P >= P_SUPPORT and mw.pvalue < 0.05 and med_p >= W_MEDIAN_SUPPORT:
        verdict = "supports"
    else:
        verdict = "mixed"

    measured = {
        "value": round(P, 4),
        "unit": "share of bird species coded as partially migratory (AVONET Migration = 2) among all species with a migration score",
        "n": n_all,
        "uncertainty": "AVONET expert coding; GBIF winter residency index from 5-degree band counts (eBird-dominated, effort-biased)",
        "extra": {
            "avonet_sheet": sheet, "n_sedentary": n1, "n_partial": n2, "n_migratory": n3,
            "share_partial_among_nonsedentary_Q": round(Q, 4),
            "share_nonsedentary": round((n2 + n3) / n_all, 4),
            "avonet_migration_code_of_test_species": avonet_species,
            "winter_residency_index_W": {k: round(v, 4) for k, v in W.items()},
            "summer_minus_winter_mean_latitude_deg": {k: round(v, 2) for k, v in shift.items()},
            "median_W_partial_set": round(med_p, 4), "median_W_obligate_set": round(med_o, 4),
            "mann_whitney_U": float(mw.statistic), "mann_whitney_p_one_sided": float(mw.pvalue),
            "verdict_by_rule": verdict,
        },
    }
    files = {"avonet": avonet_rec, "gbif_calls": len([q for q in REQUESTS if q["label"].startswith("band:")])}
    basis_qs = "&".join(f"basisOfRecord={b}" for b in BASIS)
    const = [f"basisOfRecord={b}" for b in BASIS] + ["limit=0", "hasCoordinate=true", "hasGeospatialIssue=false", "year=2000%2C2030"]

    def strip(url):
        for c in const:
            url = url.replace("&" + c, "").replace("?" + c + "&", "?")
        return url
    compact = [{**q, "download_url": strip(q["download_url"])} for q in REQUESTS if q["label"] != "avonet-xlsx"]
    with open(os.path.join(DERIVED, "requests.csv"), "w") as fh:
        fh.write(f"# GBIF occurrence URLs omit the constant query parameters {' '.join(const)}\n")
        pd.DataFrame(compact).to_csv(fh, index=False)
    json.dump({"measured": measured, "files": files}, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
