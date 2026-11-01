"""Download the UN World Population Prospects 2024 Demographic Indicators (medium variant, CSV, gzipped) into data/ (git-ignored).

Records URL, retrieval time, byte size and SHA-256 in data/manifest.json.
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
    "wpp2024_indicators": "https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/CSV_FILES/WPP2024_Demographic_Indicators_Medium.csv.gz",
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
        out = os.path.join(DATA, "WPP2024_Demographic_Indicators_Medium.csv.gz")
        if os.path.exists(out) and key in manifest:
            continue
        retrieved = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with requests.get(url, headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=600, stream=True) as r:
            r.raise_for_status()
            with open(out, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        manifest[key] = {"download_url": url, "retrieved_at": retrieved, "byte_size": os.path.getsize(out), "sha256": sha256(out)}
        json.dump(manifest, open(mpath, "w"), indent=1)
        print(key, manifest[key]["byte_size"], file=sys.stderr)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
