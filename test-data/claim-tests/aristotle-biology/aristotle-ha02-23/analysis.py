#!/usr/bin/env python3
"""Test aristotle-ha02-23: no fish or bird has kidneys or a bladder."""
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
QUERIES = {
    "fish_kidney": '(Actinopterygii[Organism] OR Chondrichthyes[Organism]) AND (kidney[All Fields] OR pronephros[All Fields] OR mesonephros[All Fields] OR "head kidney"[All Fields])',
    "bird_kidney": 'Aves[Organism] AND (kidney[All Fields] OR metanephros[All Fields])',
    "fish_bladder": '(Actinopterygii[Organism] OR Chondrichthyes[Organism]) AND "urinary bladder"[All Fields]',
    "bird_bladder": 'Aves[Organism] AND "urinary bladder"[All Fields]',
}
KIDNEY_RE = re.compile(r"head kidney|pronephros|mesonephros|metanephros|\bkidneys?\b", re.I)
BLADDER_RE = re.compile(r"urinary bladder", re.I)


def search(term, pattern, n=30):
    r = requests.get(ESEARCH, params={
        "db": "biosample", "term": term, "retmode": "json", "retmax": n, "tool": "delphi-claim-test"
    }, timeout=120)
    r.raise_for_status()
    es = r.json()["esearchresult"]
    raw = int(es.get("count") or 0)
    ids = es.get("idlist") or []
    file_meta = {
        "download_url": ESEARCH + "?db=biosample&term=" + requests.utils.quote(term) + "&retmode=json&retmax=" + str(n),
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(r.content),
        "sha256": hashlib.sha256(r.content).hexdigest(),
        "label": term[:160],
    }
    time.sleep(0.4)
    validated = []
    if ids:
        s = requests.get(ESUMMARY, params={
            "db": "biosample", "id": ",".join(ids), "retmode": "json", "tool": "delphi-claim-test"
        }, timeout=120)
        s.raise_for_status()
        result = s.json()["result"]
        for uid in result.get("uids", []):
            rec = result[uid]
            title = rec.get("title") or ""
            sample = rec.get("sampledata") or ""
            attrs = " ".join(re.findall(r">([^<]{0,200})<", sample))
            blob = title + " " + attrs
            if pattern.search(blob):
                validated.append({
                    "uid": uid,
                    "accession": rec.get("accession"),
                    "organism": rec.get("organism"),
                    "title": title,
                })
        time.sleep(0.4)
    return raw, validated, file_meta


def main():
    out = {}
    files = []
    for key, term in QUERIES.items():
        pattern = KIDNEY_RE if "kidney" in key else BLADDER_RE
        raw, validated, meta = search(term, pattern)
        out[key] = {"raw_count": raw, "validated_in_sample": len(validated), "sample_checked": min(30, raw), "examples": validated[:8]}
        files.append(meta)
        json.dump(validated, open(os.path.join(DERIVED, key + ".json"), "w"), indent=2)

    fish_v = out["fish_kidney"]["validated_in_sample"]
    bird_v = out["bird_kidney"]["validated_in_sample"]
    if fish_v >= 5 or bird_v >= 5:
        verdict, reason = "refutes", None
        confidence = 0.9 if fish_v >= 5 and bird_v >= 5 else 0.75
    elif fish_v >= 1 or bird_v >= 1:
        verdict, reason = "mixed", None
        confidence = 0.5
    else:
        verdict, reason = "inconclusive", "data-unavailable"
        confidence = 0.4

    measured = {
        "value": fish_v + bird_v,
        "unit": "validated kidney-tissue biosamples in the inspected fish sample plus the inspected bird sample",
        "n": out["fish_kidney"]["sample_checked"] + out["bird_kidney"]["sample_checked"],
        "uncertainty": "validated counts are a lower bound from the first 30 search ids, not a census",
        "extra": out,
    }
    json.dump({"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured},
              open(os.path.join(DERIVED, "summary.json"), "w"), indent=2)

    if "--write-result" in sys.argv:
        result = json.load(open(os.path.join(HERE, "result.json")))
        result["status"] = "complete"
        result["data_kind"] = "biological" if verdict != "inconclusive" else "none"
        result["verdict"] = verdict
        if reason:
            result["reason"] = reason
        result["confidence"] = confidence
        result["measured"] = measured
        result["datasets"] = [{
            "id": "ncbi-biosample-fish-bird-kidney",
            "name": "NCBI BioSample searches for fish and bird kidney and urinary bladder",
            "landing_url": "https://www.ncbi.nlm.nih.gov/biosample/",
            "doi": None,
            "version": "E-utilities, retrieved with this run",
            "license": "NCBI public access",
            "role": "organism and tissue text for kidney and urinary bladder",
            "files": files,
        }]
        result["method"] = (
            "analysis.py runs four NCBI BioSample searches and validates up to 30 summaries each. "
            "A summary counts when its title or attribute text names the organ. "
            f"Fish kidney validated {fish_v} (raw {out['fish_kidney']['raw_count']}). "
            f"Bird kidney validated {bird_v} (raw {out['bird_kidney']['raw_count']}). "
            f"Fish urinary bladder raw {out['fish_bladder']['raw_count']}, validated {out['fish_bladder']['validated_in_sample']}. "
            f"Bird urinary bladder raw {out['bird_bladder']['raw_count']}, validated {out['bird_bladder']['validated_in_sample']}. "
            "Five validated kidney samples in either clade refute the universal absence. Zero samples would not have supported it."
        )
        result["deviations"] = [{
            "field": "ncbi query syntax",
            "change": "kidney[ATTR] and kidney[Attribute] returned phrasesnotfound. The searches use [All Fields] and then require the organ word in the title or attribute text. Thresholds are unchanged.",
            "why": "E-utilities did not accept the pre-registered field abbreviation.",
        }]
        result["caveats"] = [
            "A biosample shows that someone collected the named tissue. It is not a survey of how many species lack the organ.",
            "Validation is on the first 30 ids, so the validated number is a lower bound on the raw count.",
            "Urinary-bladder wording can be missed when a paper says only 'bladder'. Those counts are extra and do not rescue a kidney counterexample.",
            "No absence matrix was in this archive, so the claim could not have been supported here.",
        ]
        json.dump(result, open(os.path.join(HERE, "result.json"), "w"), indent=2)
        open(os.path.join(HERE, "result.json"), "a").write("\n")
    print(json.dumps({"verdict": verdict, "fish": fish_v, "bird": bird_v, "raw_fish": out["fish_kidney"]["raw_count"], "raw_bird": out["bird_kidney"]["raw_count"]}))


if __name__ == "__main__":
    main()
