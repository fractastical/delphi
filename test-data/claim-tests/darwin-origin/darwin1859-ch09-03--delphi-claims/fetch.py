"""Download the ICS international chronostratigraphic ages from the Macrostrat API (defs/intervals, timescale 'international ages')
into data/ (git-ignored) and record URL, retrieval time, byte size and SHA-256 in data/manifest.json.
Run: python fetch.py   (needs `requests`)
"""
import hashlib
import json
import os
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
URL = "https://macrostrat.org/api/v2/defs/intervals?timescale=international%20ages"


def main():
    os.makedirs(DATA, exist_ok=True)
    out = os.path.join(DATA, "macrostrat_international_ages.json")
    retrieved = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    r = requests.get(URL, headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=120)
    r.raise_for_status()
    with open(out, "wb") as f:
        f.write(r.content)
    manifest = {"macrostrat_international_ages": {"download_url": URL, "retrieved_at": retrieved, "byte_size": len(r.content),
                                                  "sha256": hashlib.sha256(r.content).hexdigest()}}
    json.dump(manifest, open(os.path.join(DATA, "manifest.json"), "w"), indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
