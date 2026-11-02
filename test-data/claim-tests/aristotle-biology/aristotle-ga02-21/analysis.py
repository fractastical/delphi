#!/usr/bin/env python3
"""Test aristotle-ga02-21: eels are neither male nor female."""
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import pandas as pd
import pyarrow.parquet as pq
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

BASE = "https://s3.us-west-2.amazonaws.com/us-west-2.opendata.source.coop/cboettig/fishbase/fb/v24.07/parquet/"
TABLES = ["reproduc.parquet", "species.parquet", "maturity.parquet"]
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


def fetch(name):
    url = BASE + name
    path = os.path.join(DATA, name)
    meta = path + ".retrieved"
    if not (os.path.exists(path) and os.path.exists(meta)):
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        open(path, "wb").write(r.content)
        open(meta, "w").write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    content = open(path, "rb").read()
    return path, {
        "download_url": url,
        "retrieved_at": open(meta).read().strip(),
        "byte_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def biosample_sex(sex_word):
    term = f"Anguilla[Organism] AND {sex_word}[All Fields]"
    r = requests.get(ESEARCH, params={
        "db": "biosample", "term": term, "retmode": "json", "retmax": 20, "tool": "delphi-claim-test"
    }, timeout=90)
    r.raise_for_status()
    es = r.json()["esearchresult"]
    raw = int(es.get("count") or 0)
    ids = es.get("idlist") or []
    meta = {
        "download_url": ESEARCH + "?db=biosample&term=" + requests.utils.quote(term) + "&retmode=json&retmax=20",
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(r.content),
        "sha256": hashlib.sha256(r.content).hexdigest(),
        "label": term,
    }
    time.sleep(0.4)
    validated = []
    if ids:
        s = requests.get(ESUMMARY, params={
            "db": "biosample", "id": ",".join(ids), "retmode": "json", "tool": "delphi-claim-test"
        }, timeout=90)
        s.raise_for_status()
        result = s.json()["result"]
        for uid in result.get("uids", []):
            rec = result[uid]
            sample = rec.get("sampledata") or ""
            attrs = re.findall(r'attribute_name="([^"]+)"[^>]*>([^<]*)', sample)
            sex_vals = [v.strip().lower() for n, v in attrs if "sex" in n.lower()]
            if sex_word in sex_vals:
                validated.append({"uid": uid, "accession": rec.get("accession"), "title": rec.get("title"), "sex": sex_vals})
        time.sleep(0.4)
    return raw, validated, meta


def main():
    paths, files = {}, {}
    for name in TABLES:
        paths[name], files[name] = fetch(name)
    species = pq.read_table(paths["species.parquet"], columns=["SpecCode", "Genus", "Species"]).to_pandas()
    repro = pq.read_table(paths["reproduc.parquet"], columns=["SpecCode", "ReproMode"]).to_pandas()
    maturity = pq.read_table(paths["maturity.parquet"], columns=["Speccode", "Sex"]).to_pandas()
    maturity = maturity.rename(columns={"Speccode": "SpecCode"})
    ang = species[species["Genus"].str.lower() == "anguilla"].copy()
    merged = ang.merge(repro, on="SpecCode", how="left")
    dioecious = merged["ReproMode"].fillna("").str.lower().str.startswith("dioec")
    separate = merged[dioecious][["Genus", "Species", "ReproMode"]].drop_duplicates()
    mat = ang.merge(maturity, on="SpecCode", how="inner")
    mat["sex_norm"] = mat["Sex"].str.lower()
    both = []
    for (genus, sp), g in mat.groupby(["Genus", "Species"]):
        sexes = set(g["sex_norm"])
        if "male" in sexes and "female" in sexes:
            both.append({"genus": genus, "species": sp, "male_rows": int((g.sex_norm == "male").sum()),
                         "female_rows": int((g.sex_norm == "female").sum())})
    separate.to_csv(os.path.join(DERIVED, "anguilla-repromode.csv"), index=False)
    json.dump(both, open(os.path.join(DERIVED, "anguilla-maturity-both-sexes.json"), "w"), indent=2)

    mug = species[(species.Genus.str.lower() == "mugil") & (species.Species.str.lower() == "cephalus")]
    mug_mode = None
    if len(mug):
        mm = mug.merge(repro, on="SpecCode", how="left")
        mug_mode = sorted(set(mm["ReproMode"].dropna().astype(str)))

    raw_m, val_m, meta_m = biosample_sex("male")
    raw_f, val_f, meta_f = biosample_sex("female")
    json.dump({"male": val_m, "female": val_f}, open(os.path.join(DERIVED, "anguilla-biosample-sex.json"), "w"), indent=2)

    fishbase_separate = len(separate) > 0 or len(both) > 0
    biosample_both = len(val_m) >= 5 and len(val_f) >= 5
    recorded = merged[merged["ReproMode"].notna()]
    sexless_codes = recorded["ReproMode"].fillna("").str.lower().str.contains(r"undifferentiated|no sex|neither")
    if fishbase_separate or biosample_both:
        verdict, reason = "refutes", None
        confidence = 0.93 if len(separate) >= 5 and len(both) >= 1 else 0.8
    elif len(recorded) and bool(sexless_codes.all()) and len(val_m) == 0 and len(val_f) == 0:
        verdict, reason = "supports", None
        confidence = 0.6
    elif len(recorded) == 0 and len(val_m) == 0 and len(val_f) == 0:
        verdict, reason = "inconclusive", "data-unavailable"
        confidence = 0.35
    else:
        verdict, reason = "mixed", None
        confidence = 0.5

    measured = {
        "value": int(len(separate)),
        "unit": "Anguilla species whose FishBase ReproMode starts with dioec",
        "n": int(ang["SpecCode"].nunique()),
        "uncertainty": "species count in FishBase 24.07; one reproduction row per listed species",
        "extra": {
            "anguilla_species_in_species_table": int(ang["SpecCode"].nunique()),
            "anguilla_species_with_repromode": int(recorded["Species"].nunique()) if len(recorded) else 0,
            "repromode_values": sorted(set(recorded["ReproMode"].dropna().astype(str))) if len(recorded) else [],
            "species_with_male_and_female_maturity_rows": both,
            "biosample_male_raw": raw_m,
            "biosample_female_raw": raw_f,
            "biosample_male_validated": len(val_m),
            "biosample_female_validated": len(val_f),
            "mugil_cephalus_repromode": mug_mode,
        },
    }
    json.dump({"verdict": verdict, "measured": measured}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=2)

    if "--write-result" in sys.argv:
        result = json.load(open(os.path.join(HERE, "result.json")))
        result["status"] = "complete"
        result["data_kind"] = "biological"
        result["verdict"] = verdict
        if reason:
            result["reason"] = reason
        result["confidence"] = confidence
        result["measured"] = measured
        result["datasets"] = [
            {
                "id": "fishbase-24.07-" + key.replace(".parquet", ""),
                "name": "FishBase 24.07 " + key,
                "landing_url": "https://source.coop/cboettig/fishbase/fb/v24.07",
                "doi": None,
                "version": "24.07",
                "license": "CC BY-NC 3.0",
                "role": key,
                "files": [files[key]],
            }
            for key in TABLES
        ] + [{
            "id": "ncbi-biosample-anguilla-sex",
            "name": "NCBI BioSample Anguilla records whose sex attribute is male or female",
            "landing_url": "https://www.ncbi.nlm.nih.gov/biosample/",
            "doi": None,
            "version": "E-utilities",
            "license": "NCBI public access",
            "role": "sexed eel samples",
            "files": [meta_m, meta_f],
        }]
        result["method"] = (
            "analysis.py joins FishBase species, reproduc, and maturity on SpecCode and keeps genus Anguilla. "
            "A ReproMode value beginning with 'dioec' is the table's dioecism code and is read as the pre-registered separate-sex code. "
            f"{len(separate)} Anguilla species have that code. "
            f"{len(both)} species have both male and female rows in the maturity table. "
            "BioSample hits count only when a sex attribute equals male or female. "
            f"Validated males {len(val_m)} of raw {raw_m}; validated females {len(val_f)} of raw {raw_f}. "
            "Mugil cephalus is reported and does not set the verdict."
        )
        result["deviations"] = [{
            "field": "FishBase ReproMode spelling and biosample field",
            "change": "The fail criterion names 'dioecious'. FishBase stores 'dioecism'. Values whose lowercase form starts with 'dioec' are counted. BioSample [ATTR] was not used; [All Fields] was used and a sex attribute had to equal the sex word.",
            "why": "The reproduction table's controlled vocabulary uses the noun dioecism for separate sexes, and the attribute qualifier was rejected by E-utilities.",
        }]
        result["caveats"] = [
            "Eel gonads are small until the fish matures, which is why an ancient observer could miss them. The test asks whether males and females exist, not whether they are obvious in a market fish.",
            "The unnamed mullet of stagnant waters is not identified. Mugil cephalus is a pre-specified side note.",
            "FishBase is CC BY-NC and is not redistributed here.",
        ]
        json.dump(result, open(os.path.join(HERE, "result.json"), "w"), indent=2)
        open(os.path.join(HERE, "result.json"), "a").write("\n")
    print(json.dumps({"verdict": verdict, "dioecious_species": int(len(separate)), "both_maturity": len(both),
                      "val_m": len(val_m), "val_f": len(val_f)}))


if __name__ == "__main__":
    main()
