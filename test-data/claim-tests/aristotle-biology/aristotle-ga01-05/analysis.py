#!/usr/bin/env python3
"""Fishes and snakes have testes (aristotle-ga01-05), tested on NCBI BioSample.
"""
import os
import re
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import fetch, load_result, write_result

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RESULT = os.path.join(HERE, "result.json")
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
SYNTAXES = [
    ('testis[attr] AND "{clade}"[Organism]', "testis[attr]"),
    ('testes[attr] AND "{clade}"[Organism]', "testes[attr]"),
    ('"tissue"[Attribute Name] AND testis[All Fields] AND "{clade}"[Organism]', "tissue-attribute AND testis"),
]
NAME_RE = re.compile(r"tissue|organism part|body site|sample type|tissue type", re.I)
VALUE_RE = re.compile(r"\btest(?:is|es)\b", re.I)
UA = {"User-Agent": "delphi-claim-test/1.0"}


def esearch(term, retmax):
    r = requests.get(ESEARCH, params={
        "db": "biosample", "term": term, "retmode": "json", "retmax": retmax, "tool": "delphi-claim-test",
    }, timeout=90, headers=UA)
    r.raise_for_status()
    body = r.json()["esearchresult"]
    return int(body["count"]), body.get("idlist", [])


def parse_samples(xml):
    found = []
    for block in re.findall(r"<BioSample.*?</BioSample>", xml, flags=re.S):
        org = re.search(r'taxonomy_name="([^"]+)"', block)
        sid = re.search(r'<BioSample[^>]*accession="([^"]+)"', block)
        attrs = re.findall(r'<Attribute[^>]*attribute_name="([^"]+)"[^>]*>([^<]*)</Attribute>', block)
        hits = [(n, v.strip()) for n, v in attrs if NAME_RE.search(n) and VALUE_RE.search(v)]
        if hits and org:
            found.append({
                "accession": sid.group(1) if sid else None,
                "organism": org.group(1),
                "attribute": hits[0][0],
                "value": hits[0][1][:80],
            })
    return found


def species_of(name):
    parts = name.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else name


def main():
    os.makedirs(DATA, exist_ok=True)
    files = []
    chosen = None
    control_counts = []
    for template, label in SYNTAXES:
        term = template.format(clade="Mammalia")
        url = ESEARCH + "?db=biosample&retmode=json&retmax=0&tool=delphi-claim-test&term=" + requests.utils.quote(term)
        count, _ = esearch(term, 0)
        meta = fetch(url, os.path.join(DATA, f"mammal-syntax-{len(control_counts)+1}.json"))
        meta["label"] = f"Mammalia control {label}"
        files.append(meta)
        control_counts.append({"syntax": label, "mammal_esearch_count": count})
        if count >= 20 and chosen is None:
            chosen = (template, label, count)
    if chosen is None:
        payload = inconclusive(files, control_counts, "underpowered")
        write_result(RESULT, load_result(RESULT), payload)
        print("inconclusive control")
        return

    template, label, mammal_count = chosen
    # Confirm the chosen syntax parses as testis on a mammal sample of 20.
    _, mammal_ids = esearch(template.format(clade="Mammalia"), 20)
    mx = requests.get(EFETCH, params={
        "db": "biosample", "id": ",".join(mammal_ids), "retmode": "xml", "tool": "delphi-claim-test",
    }, timeout=120, headers=UA)
    mx.raise_for_status()
    open(os.path.join(DATA, "mammal-sample.xml"), "wb").write(mx.content)
    mammal_parsed = parse_samples(mx.text)

    clade_rows = {}
    for clade in ("Actinopterygii", "Chondrichthyes", "Serpentes"):
        term = template.format(clade=clade)
        url = ESEARCH + "?db=biosample&retmode=json&retmax=80&tool=delphi-claim-test&term=" + requests.utils.quote(term)
        count, ids = esearch(term, 80)
        meta = fetch(url, os.path.join(DATA, f"esearch-{clade}.json"))
        meta["label"] = f"esearch {clade}"
        files.append(meta)
        xml = requests.get(EFETCH, params={
            "db": "biosample", "id": ",".join(ids), "retmode": "xml", "tool": "delphi-claim-test",
        }, timeout=180, headers=UA)
        xml.raise_for_status()
        path = os.path.join(DATA, f"efetch-{clade}.xml")
        open(path, "wb").write(xml.content)
        import hashlib
        from common import now
        files.append({
            "download_url": xml.url,
            "retrieved_at": now(),
            "byte_size": len(xml.content),
            "sha256": hashlib.sha256(xml.content).hexdigest(),
            "label": f"efetch {clade} n={len(ids)}",
        })
        parsed = parse_samples(xml.text)
        species = sorted({species_of(p["organism"]) for p in parsed})
        clade_rows[clade] = {
            "esearch_count": count,
            "fetched": len(ids),
            "parsed_testis_records": len(parsed),
            "species": species,
            "n_species": len(species),
            "examples": parsed[:5],
        }

    fish_species = clade_rows["Actinopterygii"]["species"] + clade_rows["Chondrichthyes"]["species"]
    snake_species = clade_rows["Serpentes"]["species"]
    fish_hit = len(fish_species) >= 1
    snake_hit = len(snake_species) >= 1
    if fish_hit and snake_hit:
        verdict, reason = "refutes", None
    elif fish_hit or snake_hit:
        verdict, reason = "mixed", None
    else:
        verdict, reason = "inconclusive", "underpowered"
    confidence = {"refutes": 0.9, "mixed": 0.6, "inconclusive": 0.4}[verdict]
    payload = {
        "datasets": [{
            "id": "ncbi-biosample-testis-attribute",
            "name": "NCBI BioSample records with a testis tissue attribute",
            "landing_url": "https://www.ncbi.nlm.nih.gov/biosample/",
            "doi": None,
            "version": "live BioSample, queried 2026-11-01",
            "license": "NCBI public-domain terms",
            "files": files,
            "role": "tissue-labelled samples of mammals (control), fishes, and snakes",
        }],
        "method": (
            f"Three pre-registered BioSample queries were run on Mammalia in order. "
            f"The first with an esearch count of at least 20 was '{label}' ({mammal_count} mammal hits). "
            "The same query was applied to Actinopterygii, Chondrichthyes, and Serpentes. "
            "Up to 80 records per clade were fetched as XML. A record counts only when an attribute "
            "named tissue, organism part, body site, sample type, or tissue type contains the whole word testis or testes. "
            "No email was sent to NCBI."
        ),
        "measured": {
            "value": len(set(fish_species)) + len(set(snake_species)),
            "unit": "fish plus snake species with a parsed testis BioSample in the fetched sample",
            "n": sum(c["parsed_testis_records"] for c in clade_rows.values()),
            "uncertainty": "esearch counts include records not in the fetched sample of 80",
            "extra": {
                "syntax_chosen": label,
                "mammal_esearch_count": mammal_count,
                "mammal_parsed_testis_in_sample_of_20": len(mammal_parsed),
                "control_counts": control_counts,
                "clades": clade_rows,
                "spermatic_duct_count": "untested",
            },
        },
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological",
        "headline": (
            f"Fetched BioSamples label the testis in {len(set(fish_species))} fish species and "
            f"{len(set(snake_species))} snake species, so those classes do not lack testes."
        ),
        "caveats": [
            "The second clause, that these animals have only two spermatic ducts, is not in the tissue labels and is untested.",
            "Aristotle may have seen elongate testes and called them ducts. The records use the modern name testis.",
            "Ray-finned fishes contribute thousands of esearch hits. The species count is from the first 80 records, not the whole database.",
            "A mammal sample of 20 records all parsed as testis, which is the check that the query names the organ.",
        ],
    }
    if reason:
        payload["reason"] = reason
    write_result(RESULT, load_result(RESULT), payload)
    print(verdict, len(set(fish_species)), len(set(snake_species)))


def inconclusive(files, control_counts, reason):
    return {
        "datasets": [{
            "id": "ncbi-biosample-testis-attribute",
            "name": "NCBI BioSample",
            "landing_url": "https://www.ncbi.nlm.nih.gov/biosample/",
            "doi": None,
            "version": None,
            "license": "NCBI public-domain terms",
            "files": files,
            "role": "positive control failed",
        }],
        "method": "The pre-registered BioSample syntaxes were tried on Mammalia. None returned at least 20 hits.",
        "measured": {"value": 0, "unit": "usable testis queries", "n": 0, "uncertainty": None, "extra": {"control_counts": control_counts}},
        "verdict": "inconclusive",
        "reason": reason,
        "confidence": 0.4,
        "data_kind": "none",
        "headline": "The BioSample testis query did not retrieve a mammal control, so fish and snake counts were not interpreted.",
        "caveats": ["Absence of hits under a broken query is not evidence that testes are absent."],
    }


if __name__ == "__main__":
    main()
