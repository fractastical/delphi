"""Download the 1000 Genomes Phase 3 chr22 genotype VCF and the HapMap Phase II GRCh37 genetic map into data/ (git-ignored).

Records URL, retrieval time, byte size and SHA-256 of each file in data/manifest.json.
Run: python fetch.py   (needs `requests`)
"""
import hashlib
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FILES = {
    "vcf": "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
    "map": "https://ftp.ncbi.nlm.nih.gov/hapmap/recombination/2011-01_phaseII_B37/genetic_map_HapMapII_GRCh37.tar.gz",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(DATA, exist_ok=True)
    mpath = os.path.join(DATA, "manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    for key, url in FILES.items():
        out = os.path.join(DATA, url.rsplit("/", 1)[-1])
        if os.path.exists(out) and key in manifest:
            continue
        retrieved = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for attempt in range(4):
            try:
                with requests.get(url, headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=900, stream=True) as r:
                    r.raise_for_status()
                    with open(out, "wb") as f:
                        for chunk in r.iter_content(1 << 20):
                            f.write(chunk)
                break
            except Exception:  # noqa: BLE001
                if attempt == 3:
                    raise
                time.sleep(5 * 2 ** attempt)
        manifest[key] = {"download_url": url, "retrieved_at": retrieved, "byte_size": os.path.getsize(out), "sha256": sha256(out)}
        json.dump(manifest, open(mpath, "w"), indent=1)
        print(key, manifest[key]["byte_size"], file=sys.stderr)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
