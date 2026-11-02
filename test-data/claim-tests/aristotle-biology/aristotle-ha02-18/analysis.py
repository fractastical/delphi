#!/usr/bin/env python3
"""Test aristotle-ha02-18: fishes lack hearing and smell organs."""
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
TABLES = ["otoliths.parquet", "brains.parquet", "morphdat.parquet", "species.parquet"]
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
SMELL_TERM = 'Actinopterygii[Organism] AND ("olfactory epithelium"[All Fields] OR "olfactory rosette"[All Fields] OR nares[All Fields] OR nostril[All Fields])'
SMELL_RE = re.compile(r"olfactory epithelium|olfactory rosette|\bnares\b|\bnostrils?\b", re.I)


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


def ncbi_validated(term, pattern, n=25):
    r = requests.get(ESEARCH, params={
        "db": "biosample", "term": term, "retmode": "json", "retmax": n, "tool": "delphi-claim-test"
    }, timeout=90)
    r.raise_for_status()
    es = r.json()["esearchresult"]
    raw = int(es.get("count") or 0)
    ids = es.get("idlist") or []
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
            blob = (rec.get("title") or "") + " " + (rec.get("sampledata") or "")
            if pattern.search(blob):
                validated.append({
                    "uid": uid,
                    "accession": rec.get("accession"),
                    "organism": rec.get("organism"),
                    "title": rec.get("title"),
                })
    return raw, validated, {
        "download_url": ESEARCH + "?db=biosample&term=" + requests.utils.quote(term) + "&retmode=json&retmax=" + str(n),
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(r.content),
        "sha256": hashlib.sha256(r.content).hexdigest(),
        "label": "esearch " + term[:180],
    }


def main():
    files = {}
    paths = {}
    for name in TABLES:
        paths[name], files[name] = fetch(name)

    oto = pq.read_table(paths["otoliths.parquet"]).to_pandas()
    numeric_cols = [c for c in oto.columns if any(k in c.lower() for k in ("length", "height", "weight", "size"))]
    measured_row = pd.Series(False, index=oto.index)
    for c in numeric_cols:
        measured_row = measured_row | (pd.to_numeric(oto[c], errors="coerce") > 0)
    species_with_otolith = int(oto.loc[measured_row, "SpecCode"].nunique())
    type_counts = {str(k): int(v) for k, v in oto.loc[measured_row, "Type"].value_counts().items()}

    brains_cols = pq.read_schema(paths["brains.parquet"]).names
    morph_cols = pq.read_schema(paths["morphdat.parquet"]).names
    brain_olf = [c for c in brains_cols if "olfact" in c.lower()]
    morph_olf = [c for c in morph_cols if any(k in c.lower() for k in ("naris", "nostril", "olfact"))]

    smell_species = 0
    smell_source = None
    if brain_olf:
        br = pq.read_table(paths["brains.parquet"], columns=["SpecCode"] + brain_olf).to_pandas()
        ok = pd.Series(False, index=br.index)
        for c in brain_olf:
            ok = ok | (pd.to_numeric(br[c], errors="coerce") > 0)
        smell_species = int(br.loc[ok, "SpecCode"].nunique())
        smell_source = "brains.parquet"
    elif morph_olf:
        md = pq.read_table(paths["morphdat.parquet"], columns=["Speccode"] + morph_olf).to_pandas()
        ok = md[morph_olf].notna().any(axis=1)
        smell_species = int(md.loc[ok, "Speccode"].nunique())
        smell_source = "morphdat.parquet"

    raw_smell, validated, search_file = ncbi_validated(SMELL_TERM, SMELL_RE)
    json.dump(validated, open(os.path.join(DERIVED, "smell-biosamples.json"), "w"), indent=2)

    otolith_refutes = species_with_otolith >= 10
    smell_refutes = smell_species >= 10 or len(validated) >= 5
    if otolith_refutes or smell_refutes:
        verdict, reason = "refutes", None
        confidence = 0.93 if species_with_otolith >= 100 else 0.8
    elif species_with_otolith == 0 and len(validated) == 0 and smell_species == 0:
        verdict, reason = "inconclusive", "data-unavailable"
        confidence = 0.35
    else:
        verdict, reason = "mixed", None
        confidence = 0.55

    measured = {
        "value": species_with_otolith,
        "unit": "fish species with a positive otolith length or height",
        "n": species_with_otolith,
        "uncertainty": "distinct SpecCode values; a species can have many otolith rows",
        "extra": {
            "otolith_numeric_columns": numeric_cols,
            "otolith_rows_with_positive_measurement": int(measured_row.sum()),
            "otolith_type_counts": type_counts,
            "brains_olfactory_columns": brain_olf,
            "morphdat_olfactory_or_nostril_columns": morph_olf,
            "smell_species_from_fishbase": smell_species,
            "smell_fishbase_source": smell_source,
            "smell_biosample_raw_count": raw_smell,
            "smell_biosample_validated_in_sample": len(validated),
            "smell_biosample_sample_size": 25,
        },
    }
    summary = {"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured}
    json.dump(summary, open(os.path.join(DERIVED, "summary.json"), "w"), indent=2)

    if "--write-result" in sys.argv:
        result = json.load(open(os.path.join(HERE, "result.json")))
        result["status"] = "complete"
        result["data_kind"] = "biological" if verdict != "inconclusive" else "none"
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
            "id": "ncbi-biosample-fish-olfaction",
            "name": "NCBI BioSample search for fish olfactory tissues",
            "landing_url": "https://www.ncbi.nlm.nih.gov/biosample/",
            "doi": None,
            "version": "E-utilities esearch/esummary",
            "license": "NCBI public access",
            "role": "olfactory epithelium, rosette, or nostril samples",
            "files": [search_file],
        }]
        result["method"] = (
            "analysis.py reads FishBase 24.07 otoliths, brains, morphdat, and species parquet files. "
            f"An otolith row counts when a length, height, weight, or size column is positive. "
            f"{species_with_otolith} species have such a row. "
            f"Brains columns containing 'olfact': {brain_olf or 'none'}. "
            f"Morphdat columns containing naris, nostril, or olfact: {morph_olf or 'none'}. "
            "The smell fallback is an NCBI BioSample search; a hit counts only when the summary names "
            f"olfactory epithelium, an olfactory rosette, or a nostril. Validated in the first 25 ids: {len(validated)} "
            f"(raw count {raw_smell}). Either organ at the pre-registered threshold refutes the claim that fishes have only eyes."
        )
        result["deviations"] = [{
            "field": "ncbi query syntax",
            "change": "The pre-registered smell query used [ATTR]. E-utilities returned phrasesnotfound for organ words qualified with [ATTR] or [Attribute] in a parallel kidney query, so this search uses [All Fields] and then validates the summary text. The threshold of 5 validated samples is unchanged.",
            "why": "The field abbreviation was rejected by the search service.",
        }]
        result["caveats"] = [
            "An otolith is the ear stone of the inner ear, not a test of whether the fish responds to sound.",
            "Aristotle may have meant the absence of an external ear opening. The claim also says the organs themselves are absent. Measured ear stones are those organs' stones.",
            "FishBase is CC BY-NC. The tables are not redistributed here.",
            "Nostrils are not a column in the morphology table that was checked. Smell is reported from biosample text, which can include a word outside the sampled tissue.",
        ]
        json.dump(result, open(os.path.join(HERE, "result.json"), "w"), indent=2)
        open(os.path.join(HERE, "result.json"), "a").write("\n")
    print(json.dumps({"verdict": verdict, "otolith_species": species_with_otolith, "smell_validated": len(validated), "raw_smell": raw_smell}))


if __name__ == "__main__":
    main()
