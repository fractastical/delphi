"""Download CCDB 'statistics' CSV output for each major plant group (Angiosperms, Gymnosperms, Pteridophytes, Bryophytes)
into data/ (git-ignored); record URL, retrieval time, byte size and SHA-256 in data/manifest.json.
Run: python fetch.py   (needs `requests`)
"""
import hashlib
import json
import os
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
GROUPS = ["Angiosperms", "Gymnosperms", "Pteridophytes", "Bryophytes"]


def main():
    os.makedirs(DATA, exist_ok=True)
    manifest = {}
    for g in GROUPS:
        url = f"http://ccdb.tau.ac.il/services/statistics/?majorGroup={g}&format=csv"
        out = os.path.join(DATA, f"ccdb_statistics_{g}.csv")
        retrieved = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        r = requests.get(url, headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=600)
        r.raise_for_status()
        with open(out, "wb") as f:
            f.write(r.content)
        manifest[g] = {"download_url": url, "retrieved_at": retrieved, "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}
    json.dump(manifest, open(os.path.join(DATA, "manifest.json"), "w"), indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
