#!/usr/bin/env python3
"""Download the Gene Ontology, the MGI GO annotations, the Mammalian Phenotype ontology and
MGI's genotype-phenotype report into data/ (git-ignored); data/manifest.json records URL,
time, size and SHA-256.

Usage: python3 fetch.py
"""
import hashlib
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FILES = {
    "go-basic.obo": "https://purl.obolibrary.org/obo/go/go-basic.obo",
    "mgi.gaf.gz": "https://current.geneontology.org/annotations/mgi.gaf.gz",
    "mp.obo": "https://purl.obolibrary.org/obo/mp.obo",
    "MGI_GenePheno.rpt": "https://www.informatics.jax.org/downloads/reports/MGI_GenePheno.rpt",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(DATA, exist_ok=True)
    manifest_path = os.path.join(DATA, "manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}
    for name, url in FILES.items():
        path = os.path.join(DATA, name)
        if not os.path.exists(path):
            req = urllib.request.Request(url, headers={"User-Agent": "delphisci-claim-tests"})
            with urllib.request.urlopen(req, timeout=900) as r, open(path, "wb") as f:
                final_url = r.geturl()
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            manifest[name] = {"download_url": url, "resolved_url": final_url,
                              "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        manifest[name].update(byte_size=os.path.getsize(path), sha256=sha256(path))
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
