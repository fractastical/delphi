#!/usr/bin/env python3
"""Download HPO annotations and ontology, GO ontology and human GO annotations into data/,
recording URL, retrieval time, byte size and SHA-256 in data/manifest.json.

Needs: requests.  Run: python3 fetch.py
"""
import datetime
import hashlib
import json
import os
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FILES = {
    "genes_to_phenotype.txt": "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/genes_to_phenotype.txt",
    "hp.obo": "https://purl.obolibrary.org/obo/hp.obo",
    "go-basic.obo": "https://purl.obolibrary.org/obo/go/go-basic.obo",
    "goa_human.gaf.gz": "https://current.geneontology.org/annotations/goa_human.gaf.gz",
}


def get(name, url):
    for attempt in range(5):
        try:
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 4:
                raise
            time.sleep(3)
    with open(os.path.join(DATA, name), "wb") as fh:
        fh.write(r.content)
    return {"name": name, "download_url": url, "final_url": r.url,
            "retrieved_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}


def main():
    os.makedirs(DATA, exist_ok=True)
    manifest = [get(n, u) for n, u in FILES.items()]
    with open(os.path.join(DATA, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
