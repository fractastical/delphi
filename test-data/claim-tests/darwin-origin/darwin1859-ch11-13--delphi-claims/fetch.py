"""Download the LR04 benthic d18O stack (Lisiecki and Raymo 2005, author's file) and the EPICA Dome C EDC3 deuterium temperature
record (Jouzel et al. 2007, NOAA paleoclimatology) into data/ (git-ignored); record URL, time, size and SHA-256 in data/manifest.json.
Run: python fetch.py   (needs `requests`)
"""
import hashlib
import json
import os
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FILES = {
    "lr04": "https://lorraine-lisiecki.com/LR04stack.txt",
    "edc": "https://www.ncei.noaa.gov/pub/data/paleo/icecore/antarctica/epica_domec/edc3deuttemp2007.txt",
}


def main():
    os.makedirs(DATA, exist_ok=True)
    manifest = {}
    for key, url in FILES.items():
        out = os.path.join(DATA, url.rsplit("/", 1)[-1])
        retrieved = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        r = requests.get(url, headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=120)
        r.raise_for_status()
        with open(out, "wb") as f:
            f.write(r.content)
        manifest[key] = {"download_url": url, "retrieved_at": retrieved, "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}
    json.dump(manifest, open(os.path.join(DATA, "manifest.json"), "w"), indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
