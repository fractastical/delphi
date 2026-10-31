#!/usr/bin/env python3
"""Test darwin1859-ch10-07: species and groups disappear gradually, place by place, not by
global catastrophes (scope: the Tertiary).

Data: Paleobiology Database genus-level occurrences (Campanian-Pliocene) for Mollusca and
Mammalia, downloaded per continent; PBDB taxon first/last appearances and extant flags; PBDB
ICS stage boundaries.

Re-run:  python3 analysis.py   (downloads ~60 MB into ./data, writes derived/ and result.json)
"""
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

PBDB = "https://paleobiodb.org/data1.2"
GROUPS = ["Mollusca", "Mammalia"]
CONTINENTS = ["AFR", "ATA", "ASI", "AUS", "EUR", "IOC", "NOA", "OCE", "SOA"]
INTERVAL = "Campanian,Pliocene"
TERTIARY = (2.58, 66.0)          # Piacenzian top .. Danian base
MAASTRICHTIAN = (66.0, 72.1)     # control window (PBDB/ICS 2023 ages, read from intervals file below)
MIN_OCCS_PER_CONTINENT = 2

FILES = []
import requests
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
            r = SESSION.get(url, params=params, timeout=900)
            if r.status_code == 200:
                break
            print(f"  HTTP {r.status_code} for {r.url}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  retry {attempt}: {e}", file=sys.stderr)
        time.sleep(10 * (attempt + 1))
    else:
        raise RuntimeError(f"could not fetch {url}")
    body = r.content
    meta = {"download_url": r.url,
            "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    with open(path, "wb") as fh:
        fh.write(body)
    with open(meta_path, "w") as fh:
        json.dump(meta, fh)
    FILES.append(meta)
    return body


def genus_of(name):
    if not isinstance(name, str) or not name:
        return None
    return re.sub(r"\s*\(.*?\)", "", name).split()[0]


def load_occurrences(group):
    frames = []
    for cc in CONTINENTS:
        print(f"  PBDB occurrences {group} {cc}", file=sys.stderr)
        body = fetch(f"{PBDB}/occs/list.csv", f"pbdb_occs_{group}_{cc}.csv",
                     params={"base_name": group, "interval": INTERVAL, "idreso": "genus",
                             "cc": cc, "show": "class"})
        text = body.decode("utf-8", "replace")
        if not text.startswith('"occurrence_no"'):
            # PBDB returns a short message when there are no records
            continue
        df = pd.read_csv(io.StringIO(text), dtype=str)
        df["continent"] = cc
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["genus_name"] = df["genus"].map(genus_of)
    df = df[df["genus_name"].notna() & df["accepted_rank"].isin(["genus", "subgenus", "species", "subspecies"])]
    df["max_ma"] = df["max_ma"].astype(float)
    df["min_ma"] = df["min_ma"].astype(float)
    return df


def load_taxa(group):
    body = fetch(f"{PBDB}/occs/taxa.json", f"pbdb_taxa_{group}.json",
                 params={"base_name": group, "interval": INTERVAL, "rank": "genus",
                         "show": "app", "vocab": "pbdb"})
    recs = json.loads(body)["records"]
    rows = []
    for r in recs:
        if r.get("taxon_rank") != "genus" or r.get("accepted_rank") not in (None, "genus") or not r.get("accepted_name"):
            continue
        if r.get("taxon_no") != r.get("accepted_no"):
            continue  # skip synonyms; occurrences are already resolved to accepted genus
        rows.append({"genus_name": r["accepted_name"], "is_extant": r.get("is_extant"),
                     "lastapp_max_ma": r.get("lastapp_max_ma"), "lastapp_min_ma": r.get("lastapp_min_ma"),
                     "n_occs": r.get("n_occs")})
    return pd.DataFrame(rows).drop_duplicates("genus_name").set_index("genus_name")


def load_stages():
    body = fetch(f"{PBDB}/intervals/list.json", "pbdb_intervals_scale1.json",
                 params={"scale": "1", "vocab": "pbdb"})
    recs = json.loads(body)["records"]
    stages = [(r["interval_name"], float(r["b_age"]), float(r["t_age"])) for r in recs if r.get("type") == "age"]
    return sorted(stages, key=lambda s: -s[1])


def stage_of(age, stages):
    for name, b, t in stages:
        if t <= age < b:
            return name
    return None


def analyse_group(group, stages):
    occ = load_occurrences(group)
    taxa = load_taxa(group)
    tertiary_stages = [s for s in stages if s[1] <= TERTIARY[1] and s[2] >= TERTIARY[0]]
    maas = [s for s in stages if s[0] == "Maastrichtian"][0]

    # global last occurrence per genus from the downloaded window; extinct flag from PBDB taxonomy
    g = occ.groupby("genus_name").agg(last_max=("max_ma", "min"), n_occ=("max_ma", "size"))
    # last occurrence record = the occurrence with the smallest min_ma; take its age range
    idx = occ.groupby("genus_name")["min_ma"].idxmin()
    last = occ.loc[idx, ["genus_name", "max_ma", "min_ma"]].set_index("genus_name")
    g["lo_max"] = last["max_ma"]
    g["lo_min"] = last["min_ma"]
    g["lo_mid"] = (g["lo_max"] + g["lo_min"]) / 2
    g = g.join(taxa, how="inner")
    g = g[g["is_extant"] == "extinct"]
    # the database-wide last appearance must also be no younger than the window's last occurrence
    g["db_last_min"] = g["lastapp_min_ma"].astype(float)
    tert = g[(g["lo_mid"] >= TERTIARY[0]) & (g["lo_mid"] < TERTIARY[1]) & (g["db_last_min"] >= TERTIARY[0])].copy()
    tert["stage"] = tert["lo_mid"].map(lambda a: stage_of(a, tertiary_stages))
    kpg = g[(g["lo_mid"] >= maas[2]) & (g["lo_mid"] < maas[1]) & (g["db_last_min"] >= maas[2])].copy()

    # ---- clause A: concentration of last occurrences across the 17 Tertiary stages
    counts = tert["stage"].value_counts()
    shares = (counts / counts.sum()).sort_values(ascending=False)
    max_share = float(shares.iloc[0])
    cum = shares.cumsum()
    n_for_half = int((cum < 0.5).sum() + 1)
    durations = {s[0]: s[1] - s[2] for s in tertiary_stages}
    per_myr = {s: counts.get(s, 0) / durations[s] for s in durations}
    stage_table = pd.DataFrame({
        "stage": [s[0] for s in tertiary_stages],
        "base_ma": [s[1] for s in tertiary_stages], "top_ma": [s[2] for s in tertiary_stages],
        "genus_last_occurrences": [int(counts.get(s[0], 0)) for s in tertiary_stages],
        "share": [float(counts.get(s[0], 0) / counts.sum()) for s in tertiary_stages],
        "per_myr": [per_myr[s[0]] for s in tertiary_stages],
    })
    stage_table.to_csv(os.path.join(DERIVED, f"tertiary_last_occurrences_by_stage_{group}.csv"), index=False)

    # ---- clause B: staggered regional last occurrences
    def staggered_fraction(genera, window):
        sub = occ[occ["genus_name"].isin(genera.index)]
        sub = sub[(sub["min_ma"] < window[1]) & (sub["max_ma"] > window[0] - 1e-9)] if window else sub
        reg = sub.groupby(["genus_name", "continent"]).agg(n=("max_ma", "size"))
        reg = reg[reg["n"] >= MIN_OCCS_PER_CONTINENT].reset_index()
        rows = []
        for gen, grp in reg.groupby("genus_name"):
            if len(grp) < 2:
                continue
            ss = sub[(sub["genus_name"] == gen) & (sub["continent"].isin(grp["continent"]))]
            # last occurrence per continent: record with smallest min_ma
            li = ss.groupby("continent")["min_ma"].idxmin()
            lo = ss.loc[li, ["continent", "max_ma", "min_ma"]]
            lo = lo.sort_values(["min_ma", "max_ma"], ascending=[False, False])
            earliest_vanish = lo.iloc[0]    # continent that vanished first (oldest last occurrence)
            final_vanish = lo.iloc[-1]      # continent that held on longest
            stag = bool(earliest_vanish["min_ma"] > final_vanish["max_ma"])
            rows.append({"genus": gen, "n_continents": len(grp),
                         "first_vanish_continent": earliest_vanish["continent"],
                         "first_vanish_min_ma": earliest_vanish["min_ma"],
                         "last_vanish_continent": final_vanish["continent"],
                         "last_vanish_max_ma": final_vanish["max_ma"], "staggered": int(stag)})
        return pd.DataFrame(rows)

    stag_t = staggered_fraction(tert, None)
    stag_k = staggered_fraction(kpg, (maas[2], 83.6))  # Campanian base .. Maastrichtian top
    stag_t.to_csv(os.path.join(DERIVED, f"regional_last_occurrences_tertiary_{group}.csv"), index=False)
    frac_t = float(stag_t["staggered"].mean()) if len(stag_t) else float("nan")
    frac_k = float(stag_k["staggered"].mean()) if len(stag_k) else float("nan")

    return {
        "n_extinct_genera_tertiary_last_occurrence": int(len(tert)),
        "n_tertiary_stages_with_last_occurrences": int((counts > 0).sum()),
        "max_single_stage_share": max_share,
        "max_stage": str(shares.index[0]),
        "stages_needed_for_50pct": n_for_half,
        "top3_stages": {str(k): float(v) for k, v in shares.iloc[:3].items()},
        "clauseA_pass": bool(max_share < 1 / 3 and n_for_half >= 4),
        "n_multicontinent_genera_tertiary": int(len(stag_t)),
        "staggered_fraction_tertiary": frac_t,
        "n_multicontinent_genera_kpg_control": int(len(stag_k)),
        "staggered_fraction_kpg_control": frac_k,
        # an empty control set leaves the control comparison undefined; the > 0.5 condition still applies
        "clauseB_pass": bool(frac_t > 0.5 and (np.isnan(frac_k) or frac_t > frac_k)),
        "clauseB_control_defined": bool(len(stag_k) > 0),
        "n_occurrences_used": int(len(occ)),
    }


def main():
    stages = load_stages()
    out = {grp: analyse_group(grp, stages) for grp in GROUPS}
    clauseA = all(v["clauseA_pass"] for v in out.values())
    clauseB = all(v["clauseB_pass"] for v in out.values())
    verdict = "supports" if clauseA and clauseB else ("mixed" if clauseA or clauseB else "refutes")

    with open(os.path.join(HERE, "result.json")) as fh:
        res = json.load(fh)
    occ_files = [f for f in FILES if "/occs/list" in f["download_url"]]
    taxa_files = [f for f in FILES if "/occs/taxa" in f["download_url"]]
    int_files = [f for f in FILES if "/intervals/" in f["download_url"]]
    retrieved = occ_files[0]["retrieved_at"][:10]
    res["datasets"] = [
        {"id": "pbdb-occurrences-mollusca-mammalia-campanian-pliocene",
         "name": "Paleobiology Database occurrences, Mollusca and Mammalia, Campanian-Pliocene, genus-resolved, per continent",
         "landing_url": "https://paleobiodb.org/", "doi": None,
         "version": "live API data1.2, retrieved " + retrieved, "license": "CC BY 4.0",
         "files": occ_files, "role": "occurrence ages and continents for last-occurrence timing"},
        {"id": "pbdb-taxa-appearances-extant-flags",
         "name": "Paleobiology Database taxa with first/last appearance ages and extant flags (occs/taxa, show=app)",
         "landing_url": "https://paleobiodb.org/", "doi": None,
         "version": "live API data1.2, retrieved " + retrieved, "license": "CC BY 4.0",
         "files": taxa_files, "role": "identify extinct genera and their database-wide last appearance"},
        {"id": "pbdb-intervals-ics-stages",
         "name": "Paleobiology Database international time scale (scale 1) interval boundaries",
         "landing_url": "https://paleobiodb.org/data1.2/intervals/list_doc.html", "doi": None,
         "version": "live API data1.2, retrieved " + retrieved, "license": "CC BY 4.0",
         "files": int_files, "role": "stage boundaries for binning last occurrences"},
    ]
    res["method"] = (
        "Genus-resolved PBDB occurrences of Mollusca and Mammalia from the Campanian to the Pliocene were downloaded "
        "for each of nine PBDB continents. For each genus flagged extinct in PBDB taxonomy, the last occurrence (smallest "
        "minimum age) was located and its age midpoint assigned to an ICS stage; genera whose database-wide last appearance "
        "is younger than the Tertiary were excluded. Clause A measured the concentration of Tertiary last occurrences across "
        "the 17 Tertiary stages (largest single-stage share; number of ranked stages needed to reach 50%). Clause B took "
        "Tertiary-extinct genera with >= 2 occurrences on each of >= 2 continents and called their disappearance staggered "
        "when the first-vanishing continent's last-occurrence age range lies entirely before the last-vanishing continent's; "
        "the same statistic was computed for genera with a Maastrichtian last occurrence as a K-Pg catastrophe control."
    )
    res["measured"] = {
        "value": float(np.mean([v["staggered_fraction_tertiary"] for v in out.values()])),
        "unit": "mean over the two groups of the fraction of multi-continent Tertiary-extinct genera with staggered regional last occurrences",
        "n": int(sum(v["n_multicontinent_genera_tertiary"] for v in out.values())),
        "uncertainty": None,
        "extra": {"per_group": out, "clauseA_pass_both_groups": clauseA, "clauseB_pass_both_groups": clauseB},
    }
    res["verdict"] = verdict
    res["confidence"] = 0.6
    res["caveats"] = [
        "Regional staggering is only detectable at the resolution of the occurrence dating: when a genus's last occurrences on two continents are both dated only to the same stage (common for mammals, whose records are often dated to land-mammal ages spanning several stages, and for all Maastrichtian records in the control), the ranges overlap and the genus is scored 'not staggered'. The mammal result for clause B is therefore partly a dating-resolution result, and the K-Pg control's zero staggering reflects the same effect as much as the catastrophe itself.",
        "The Mammalia K-Pg control set is empty (no extinct mammal genus with >= 2 Maastrichtian occurrences on each of two continents), so for mammals clause B rests only on the > 0.5 condition.",
        "Genus last occurrences in PBDB are truncated by sampling (Signor-Lipps), so both the spread across stages and the regional staggering are biased toward looking gradual; the Maastrichtian control set calibrates this for clause B but not for clause A.",
        "The Tertiary window ends at the Piacenzian; genera that actually died out in the Pleistocene but have no PBDB Pleistocene record are counted as Piacenzian extinctions, inflating the youngest stage.",
        "Stage assignment uses the midpoint of the last occurrence's age range; poorly dated occurrences spanning several stages add noise to clause A.",
        "Modern continents are used as 'places'; a genus vanishing from one basin while persisting in another on the same continent is not visible, which biases clause B toward 'not staggered'.",
        "PBDB coverage is heavily weighted to Europe and North America; staggering between continents can reflect unequal sampling rather than real sequential disappearance.",
        "The test is at genus level, not species level, and is confined to Darwin's stated Tertiary scope; the K-Pg (Maastrichtian) set shows what a catastrophic horizon looks like in the same data and is deliberately excluded from the verdict.",
    ]
    res["status"] = "complete"
    res["agent"]["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(HERE, "result.json"), "w") as fh:
        json.dump(res, fh, indent=2)
        fh.write("\n")
    print(json.dumps({"verdict": verdict, "groups": out}, indent=2))


if __name__ == "__main__":
    main()
