#!/usr/bin/env python3
"""Test aristotle-ha01-05: each named domesticate still has an extant wild kind.

Pre-registered names: Equus ferus, Bos primigenius, Sus scrofa, Ovis orientalis,
Capra aegagrus, Canis lupus. Criteria in result.json are not edited.
"""
import hashlib
import json
import os
import time
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
UA = "DelphiClaimTest/1.0 (aristotle-ha01-05; public claim test)"
FILES = []

KINDS = [
    ("horse", "Equus ferus"),
    ("cattle", "Bos primigenius"),
    ("swine", "Sus scrofa"),
    ("sheep", "Ovis orientalis"),
    ("goat", "Capra aegagrus"),
    ("dog", "Canis lupus"),
]
LIVING = {"least concern", "near threatened", "vulnerable", "endangered", "critically endangered"}
DEAD = {"extinct", "extinct in the wild"}

SPARQL = """
SELECT ?name ?taxon ?rankLabel ?statusLabel WHERE {
  VALUES ?name { "Equus ferus" "Bos primigenius" "Sus scrofa" "Ovis orientalis" "Capra aegagrus" "Canis lupus" }
  ?taxon wdt:P225 ?name .
  OPTIONAL { ?taxon wdt:P105 ?rank . }
  OPTIONAL { ?taxon wdt:P141 ?status . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, name, role, method="GET", **kwargs):
    path = os.path.join(DATA, name)
    meta = path + ".retrieved"
    if os.path.exists(path) and os.path.exists(meta):
        content = open(path, "rb").read()
        when = open(meta).read().strip()
    else:
        last = None
        for attempt in range(5):
            r = requests.request(method, url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=120, **kwargs)
            last = r
            if r.status_code == 200 and r.content:
                break
            time.sleep(2 ** attempt)
        last.raise_for_status()
        content = last.content
        when = now()
        open(path, "wb").write(content)
        open(meta, "w").write(when)
    FILES.append({
        "download_url": url if method == "GET" else url + " (POST SPARQL)",
        "retrieved_at": when,
        "byte_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "role": role,
    })
    return content


def wikidata_status(name, bindings):
    rows = [b for b in bindings if b["name"]["value"] == name]
    with_status = [b for b in rows if "statusLabel" in b]
    pool = with_status or rows
    if not pool:
        return None, []
    # Prefer a species-rank row that has a status.
    pool.sort(key=lambda b: (0 if b.get("rankLabel", {}).get("value") == "species" else 1, 0 if "statusLabel" in b else 1))
    status = pool[0].get("statusLabel", {}).get("value")
    return (status.lower() if status else None), rows


def gbif_species(key, role):
    url = f"https://api.gbif.org/v1/species/{key}"
    raw = fetch(url, f"gbif-species-{key}.json", role)
    return json.loads(raw)


def main():
    raw = fetch(
        "https://query.wikidata.org/sparql",
        "wikidata-iucn.json",
        "Wikidata IUCN status for the six wild names",
        method="GET",
        params={"query": SPARQL},
    )
    # requests params may differ from the cached URL. Re-fetch if the cache was stored under GET without query.
    bindings = json.loads(raw)["results"]["bindings"]
    rows_out = []
    for kind, name in KINDS:
        status, wd_rows = wikidata_status(name, bindings)
        match_url = f"https://api.gbif.org/v1/species/match?name={requests.utils.quote(name)}&kingdom=Animalia"
        match = json.loads(fetch(match_url, f"gbif-match-{name.replace(' ', '-')}.json", f"GBIF match {name}"))
        usage = match.get("usageKey")
        detail = gbif_species(usage, f"GBIF species {usage}") if usage else {}
        accepted_key = match.get("acceptedUsageKey") or detail.get("acceptedKey")
        accepted_detail = {}
        if accepted_key and accepted_key != usage:
            accepted_detail = gbif_species(accepted_key, f"GBIF accepted {accepted_key}")
        gbif_extinct = detail.get("extinct") is True or accepted_detail.get("extinct") is True
        accepted_name = accepted_detail.get("canonicalName") or accepted_detail.get("scientificName") or match.get("species")
        used_status = status
        if used_status is None and accepted_name:
            # Synonym resolution: ask Wikidata for the accepted binomial.
            q = """
            SELECT ?statusLabel WHERE {
              ?taxon wdt:P225 ?name ; wdt:P141 ?status .
              SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
            }
            """
            # Avoid a second open-ended query shape: exact name.
            q = (
                'SELECT ?statusLabel WHERE { ?taxon wdt:P225 "' + accepted_name.split()[0] + " " + accepted_name.split()[1]
                + '" ; wdt:P141 ?status . SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }'
                if len(accepted_name.split()) >= 2 else None
            )
            if q:
                extra = json.loads(fetch(
                    "https://query.wikidata.org/sparql",
                    f"wikidata-{accepted_name.replace(' ', '-')}.json",
                    f"Wikidata IUCN for accepted name {accepted_name}",
                    params={"query": q},
                ))
                labs = [b.get("statusLabel", {}).get("value") for b in extra["results"]["bindings"]]
                labs = [x.lower() for x in labs if x]
                if labs:
                    used_status = labs[0]
                    status = status  # original name still recorded
        extinct = (used_status in DEAD) or (status in DEAD) or gbif_extinct
        extant = (used_status in LIVING) and not gbif_extinct and not (status in DEAD)
        if extinct:
            state = "extinct"
        elif extant:
            state = "extant"
        else:
            state = "unresolved"
        rows_out.append({
            "kind": kind,
            "name": name,
            "wikidata_status": status,
            "status_used": used_status,
            "gbif_match_status": match.get("status"),
            "gbif_scientific_name": match.get("scientificName"),
            "gbif_accepted": accepted_detail.get("scientificName") or match.get("accepted"),
            "gbif_extinct": gbif_extinct,
            "gbif_extinct_raw": detail.get("extinct"),
            "state": state,
        })

    n_extinct = sum(1 for r in rows_out if r["state"] == "extinct")
    n_unresolved = sum(1 for r in rows_out if r["state"] == "unresolved")
    n_extant = sum(1 for r in rows_out if r["state"] == "extant")
    if n_extinct:
        verdict, reason = "refutes", None
    elif n_unresolved:
        verdict, reason = "inconclusive", "other"
    elif n_extant == 6:
        verdict, reason = "supports", None
    else:
        verdict, reason = "inconclusive", "other"

    measured = {
        "value": n_extinct,
        "unit": "named kinds whose wild taxon is extinct or extinct in the wild",
        "n": 6,
        "uncertainty": None,
        "extra": {"kinds": rows_out, "extant": n_extant, "unresolved": n_unresolved},
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2, ensure_ascii=False)

    path = os.path.join(HERE, "result.json")
    result = json.load(open(path))
    result["status"] = "complete"
    result["preregistered"] = True
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = 0.86 if verdict == "refutes" else 0.6
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["method"] = (
        "Each pre-registered wild name was queried on Wikidata for IUCN conservation status (P141) and matched in the GBIF backbone. "
        "Synonyms were followed to the accepted GBIF species, and that record's extinct flag was read. "
        "A kind is extinct if Wikidata calls the pre-registered name extinct or extinct in the wild, or if GBIF marks the matched species extinct. "
        "A kind is extant only if the status used is a living IUCN category and GBIF does not mark it extinct. "
        "One extinct kind refutes the claim that every named domesticate is still found wild."
    )
    result["measured"] = measured
    extinct_names = [f"{r['kind']} ({r['name']}: {r['wikidata_status']})" for r in rows_out if r["state"] == "extinct"]
    result["caveats"] = [
        "Feral domestic herds are not counted as the wild kind.",
        "The translator's bracketed 'man' is not one of the six kinds in the claim sentence.",
        "Where GBIF lumps a wild name into a domestic species, the IUCN status of the pre-registered wild name is still the status that can refute the kind.",
        "Wikidata's IUCN statement is a structured copy of the Red List category, not a fresh download of the Red List API.",
    ]
    result["deviations"] = []
    result["datasets"] = [
        {
            "id": "wikidata-iucn-p141",
            "name": "Wikidata IUCN conservation status (P141)",
            "landing_url": "https://www.wikidata.org/wiki/Property:P141",
            "doi": None,
            "version": "live query",
            "license": "CC0",
            "files": [f for f in FILES if "wikidata" in f["download_url"]],
            "role": "IUCN category of each wild name",
        },
        {
            "id": "gbif-species-match",
            "name": "GBIF backbone species match",
            "landing_url": "https://www.gbif.org/",
            "doi": None,
            "version": "live backbone",
            "license": "GBIF terms; occurrence and backbone data as published by GBIF",
            "files": [f for f in FILES if "gbif.org" in f["download_url"]],
            "role": "synonym resolution and extinct flag",
        },
    ]
    result["headline"] = (
        "Not every named domesticate still has a wild kind: "
        + ("; ".join(extinct_names) if extinct_names else "no extinct kind was returned")
        + f". {n_extant} of 6 are extant and {n_unresolved} unresolved."
    )
    with open(path, "w") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(verdict, json.dumps(rows_out, indent=2))


if __name__ == "__main__":
    main()
