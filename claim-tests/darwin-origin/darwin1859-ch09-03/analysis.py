#!/usr/bin/env python3
"""Test of darwin1859-ch09-03: "the denudation of the Weald must have required
306,662,400 years; or say three hundred million years", and "a far longer period
than 300 million years has elapsed since the latter part of the Secondary period".

The test compares Darwin's 300 Myr with the radiometrically calibrated age of the
top of the Cretaceous (= top of the Mesozoic / "Secondary") in the International
Chronostratigraphic Chart, read from two independent servers (Macrostrat and the
Paleobiology Database), and with the age range the British Geological Survey
Lexicon assigns to the Chalk Group, the youngest unit removed over the Weald.

Re-run:  python3 analysis.py   (downloads ~100 KB into ./data/, writes ./derived/)
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

DARWIN_MYR = 300.0
REFUTE_IF_BELOW_MA = 150.0  # pre-registered: refuted outright if < half of 300

FILES = {
    "macrostrat_periods": {
        "url": "https://macrostrat.org/api/v2/defs/intervals?timescale_id=3",
        "headers": {},
    },
    "macrostrat_ages": {
        "url": "https://macrostrat.org/api/v2/defs/intervals?timescale_id=1",
        "headers": {},
    },
    "macrostrat_eras": {
        "url": "https://macrostrat.org/api/v2/defs/intervals?timescale_id=13",
        "headers": {},
    },
    "pbdb_scale1": {
        "url": "https://paleobiodb.org/data1.2/intervals/list.json?scale_id=1",
        "headers": {},
    },
    "pbdb_scale1_ref": {
        "url": "https://paleobiodb.org/data1.2/refs/single.json?id=ref:87596",
        "headers": {},
    },
    "bgs_lexicon_chalk": {
        "url": "https://data.bgs.ac.uk/id/Lexicon/NamedRockUnit/CK",
        "headers": {"Accept": "text/turtle"},
    },
}


def fetch(key):
    spec = FILES[key]
    path = os.path.join(DATA, key)
    r = requests.get(spec["url"], headers=spec["headers"], timeout=60, allow_redirects=True)
    r.raise_for_status()
    with open(path, "wb") as fh:
        fh.write(r.content)
    rec = {
        "download_url": spec["url"],
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(r.content),
        "sha256": hashlib.sha256(r.content).hexdigest(),
    }
    return path, rec


def macrostrat_interval(path, name):
    d = json.load(open(path))
    for row in d["success"]["data"]:
        if row["name"] == name:
            return {"b_age": float(row["b_age"]), "t_age": float(row["t_age"])}
    raise KeyError(name)


def pbdb_interval(path, name):
    d = json.load(open(path))
    for row in d["records"]:
        if row["nam"] == name:
            return {"early_age": float(row["eag"]), "late_age": float(row["lag"])}
    raise KeyError(name)


def bgs_ages(path):
    txt = open(path, encoding="utf-8").read()
    young = re.search(r"hasYoungestAgeValue\s+([0-9.eE+-]+)", txt)
    old = re.search(r"hasOldestAgeValue\s+([0-9.eE+-]+)", txt)
    label = re.search(r'skos:prefLabel\s+"([^"]+)"', txt)
    return {
        "unit": label.group(1) if label else None,
        "oldest_age_ma": float(old.group(1)),
        "youngest_age_ma": float(young.group(1)),
    }


def main():
    files = {}
    paths = {}
    for key in FILES:
        paths[key], files[key] = fetch(key)
        print(f"fetched {key}: {files[key]['byte_size']} bytes sha256={files[key]['sha256'][:12]}...", file=sys.stderr)

    ms_cret = macrostrat_interval(paths["macrostrat_periods"], "Cretaceous")
    ms_mesoz = macrostrat_interval(paths["macrostrat_eras"], "Mesozoic")
    ms_maas = macrostrat_interval(paths["macrostrat_ages"], "Maastrichtian")
    ms_ceno = macrostrat_interval(paths["macrostrat_ages"], "Cenomanian")

    pb_cret = pbdb_interval(paths["pbdb_scale1"], "Cretaceous")
    pb_mesoz = pbdb_interval(paths["pbdb_scale1"], "Mesozoic")
    pb_maas = pbdb_interval(paths["pbdb_scale1"], "Maastrichtian")
    pb_ref = json.load(open(paths["pbdb_scale1_ref"]))["records"][0]

    bgs = bgs_ages(paths["bgs_lexicon_chalk"])

    top_k_values = {
        "macrostrat_top_cretaceous": ms_cret["t_age"],
        "macrostrat_top_mesozoic": ms_mesoz["t_age"],
        "macrostrat_top_maastrichtian": ms_maas["t_age"],
        "pbdb_top_cretaceous": pb_cret["late_age"],
        "pbdb_top_mesozoic": pb_mesoz["late_age"],
        "pbdb_top_maastrichtian": pb_maas["late_age"],
        "bgs_chalk_group_youngest": bgs["youngest_age_ma"],
    }
    vals = sorted(set(top_k_values.values()))
    top_k = max(vals)  # most generous value for Darwin
    ratio = DARWIN_MYR / top_k

    measured = {
        "value": top_k,
        "unit": "Ma (age of the top of the Cretaceous / Mesozoic = end of Chalk deposition)",
        "n": len(top_k_values),
        "uncertainty": f"all {len(top_k_values)} readings agree to within {max(vals) - min(vals):g} Myr; ICS quotes no error bar on the K/Pg boundary age",
        "extra": {
            "darwin_claim_myr": DARWIN_MYR,
            "darwin_over_measured": round(ratio, 2),
            "readings_ma": top_k_values,
            "chalk_group_bgs": bgs,
            "cretaceous_duration_myr_macrostrat": round(ms_cret["b_age"] - ms_cret["t_age"], 3),
            "mesozoic_base_ma_macrostrat": ms_mesoz["b_age"],
            "cenomanian_base_ma_macrostrat": ms_ceno["b_age"],
            "pbdb_timescale_reference": pb_ref.get("tit"),
            "pass_threshold_ma": DARWIN_MYR,
            "outright_refutation_threshold_ma": REFUTE_IF_BELOW_MA,
        },
    }
    if top_k >= DARWIN_MYR:
        verdict = "supports"
    elif top_k < REFUTE_IF_BELOW_MA:
        verdict = "refutes"
    else:
        verdict = "mixed"
    measured["extra"]["verdict_by_rule"] = verdict

    json.dump({"measured": measured, "files": files}, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))
    print("verdict by pre-registered rule:", verdict)


if __name__ == "__main__":
    main()
