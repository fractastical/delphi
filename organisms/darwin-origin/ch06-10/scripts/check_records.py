#!/usr/bin/env python3
"""Consistency and resolvability checks for the ch06-10 slice.

* every mention points at an existing taxon file; every claim-mentioned taxon has >= 1 dataset
* dataset <-> taxon links are symmetric
* no placeholder strings
* every identifier in taxa files resolves at its authority (GBIF, NCBI, Wikidata, ITIS, WoRMS, PBDB)
* every dataset identifier / DOI / fetched distribution URL is reachable

Run from the repository root:  python3 organisms/darwin-origin/ch06-10/scripts/check_records.py
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
SLICE = HERE.parent
UA = {"User-Agent": "delphi-organisms/0.1 (https://github.com/fractastical/delphi)"}
PLACEHOLDER = re.compile(r"example\.org|\bTODO\b|\bTBD\b|\bXXX\b|lorem|~~~", re.I)
problems = []
warnings = []


def ok(url, method="get", accept_codes=(200, 202), tries=3):
    """True if reachable; "blocked" if the host exists but refuses automated requests (403)."""
    for attempt in range(tries):
        try:
            r = (requests.head if method == "head" else requests.get)(url, headers=UA, timeout=60, allow_redirects=True, stream=True)
            if r.status_code in accept_codes:
                return True
            if r.status_code in (403, 405) and method == "head":
                return ok(url, "get", accept_codes, 1)
            if r.status_code == 403:
                return "blocked"
            if r.status_code in (404, 400):
                return False
        except requests.RequestException:
            pass
        time.sleep(1 + attempt)
    return False


def main():
    datasets_only = "--datasets-only" in sys.argv
    mentions = json.loads((SLICE / "mentions.json").read_text())
    taxa = {p.stem: json.loads(p.read_text()) for p in (SLICE / "taxa").glob("*.json")}
    datasets = {p.stem: json.loads(p.read_text()) for p in (SLICE / "datasets").glob("*.json")}
    print(f"{len(mentions)} mentions, {len(taxa)} taxa, {len(datasets)} datasets")

    for m in mentions:
        if m["taxon_slug"] not in taxa:
            problems.append(f"mention of unknown taxon {m['taxon_slug']}")
    for slug, t in taxa.items():
        if t["mentioned_in"] and not t["datasets"]:
            problems.append(f"claim-mentioned taxon {slug} has no dataset")
        for d in t["datasets"]:
            if d not in datasets:
                problems.append(f"{slug} lists missing dataset {d}")
            elif slug not in datasets[d]["taxa"]:
                problems.append(f"dataset {d} does not list {slug} back")
    for did, d in datasets.items():
        if d["id"] != did:
            problems.append(f"dataset id mismatch {did}")
        for s in d["taxa"]:
            if s not in taxa:
                problems.append(f"dataset {did} lists unknown taxon {s}")
            elif did not in taxa[s]["datasets"]:
                problems.append(f"taxon {s} does not list dataset {did} back")
        if "assessment" in d:
            problems.append(f"dataset {did} carries an assessment (not allowed here)")
    for p in list((SLICE / "taxa").glob("*.json")) + list((SLICE / "datasets").glob("*.json")) + [SLICE / "mentions.json"]:
        if PLACEHOLDER.search(p.read_text()):
            problems.append(f"placeholder text in {p.name}")

    # identifiers in taxa files
    for slug, t in sorted(taxa.items()):
        if datasets_only:
            break
        ids = t["identifiers"]
        if ids.get("gbif_usage_key") and not ok(f"https://api.gbif.org/v1/species/{ids['gbif_usage_key']}"):
            problems.append(f"{slug}: GBIF key {ids['gbif_usage_key']} does not resolve")
        for c in t.get("gbif_components", []):
            if not ok(f"https://api.gbif.org/v1/species/{c['gbif_usage_key']}"):
                problems.append(f"{slug}: GBIF component key {c['gbif_usage_key']} does not resolve")
        if ids.get("ncbi_taxid"):
            r = requests.get(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=taxonomy&retmode=json&id={ids['ncbi_taxid']}", headers=UA, timeout=60)
            time.sleep(0.35)
            if r.status_code != 200 or str(ids["ncbi_taxid"]) not in r.json().get("result", {}):
                problems.append(f"{slug}: NCBI taxid {ids['ncbi_taxid']} does not resolve")
        if ids.get("wikidata_qid"):
            r = requests.get(f"https://www.wikidata.org/wiki/Special:EntityData/{ids['wikidata_qid']}.json", headers=UA, timeout=60)
            if r.status_code != 200 or ids["wikidata_qid"] not in r.json().get("entities", {}):
                problems.append(f"{slug}: Wikidata {ids['wikidata_qid']} does not resolve")
        if ids.get("itis_tsn"):
            r = requests.get(f"https://www.itis.gov/ITISWebService/jsonservice/getScientificNameFromTSN?tsn={ids['itis_tsn']}", headers=UA, timeout=60)
            if r.status_code != 200 or not r.json().get("combinedName"):
                problems.append(f"{slug}: ITIS TSN {ids['itis_tsn']} does not resolve")
        if ids.get("worms_aphia_id") and not ok(f"https://www.marinespecies.org/rest/AphiaRecordByAphiaID/{ids['worms_aphia_id']}"):
            problems.append(f"{slug}: WoRMS AphiaID {ids['worms_aphia_id']} does not resolve")
        if ids.get("pbdb_taxon_id") and not ok(f"https://paleobiodb.org/data1.2/taxa/single.json?id={ids['pbdb_taxon_id']}"):
            problems.append(f"{slug}: PBDB id {ids['pbdb_taxon_id']} does not resolve")
        print(".", end="", flush=True)
    print()

    # dataset identifiers and distributions
    seen = set()
    for did, d in sorted(datasets.items()):
        urls = [d["identifier"]]
        if d.get("doi"):
            urls.append(f"https://doi.org/api/handles/{d['doi']}")
        if d.get("is_referenced_by"):
            urls.append(d["is_referenced_by"])
        for dist in d["distributions"]:
            if dist.get("inspected") and "<" not in dist["download_url"]:
                urls.append(dist["download_url"])
        for u in urls:
            if u in seen:
                continue
            seen.add(u)
            method = "head" if any(h in u for h in ("figshare", "esapubs", "senescence", "huggingface")) else "get"
            res = ok(u, method)
            if res == "blocked":
                warnings.append(f"dataset {did}: {u} exists but returns 403 to automated requests")
            elif not res:
                problems.append(f"dataset {did}: {u} not reachable")
        print(".", end="", flush=True)
    print()

    for w in warnings:
        print("WARNING:", w)
    for p in problems:
        print("PROBLEM:", p)
    print(f"{len(problems)} problems, {len(warnings)} warnings (403 from human-facing landing pages)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
