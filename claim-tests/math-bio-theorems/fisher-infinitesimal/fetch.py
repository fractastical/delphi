"""Download Galton's 1886 family height data (HistData::GaltonFamilies as CSV from the Rdatasets mirror) into data/ (git-ignored).

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
    "galton_families": "https://raw.githubusercontent.com/vincentarelbundock/Rdatasets/master/csv/HistData/GaltonFamilies.csv",
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
        r = requests.get(url, headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=120)
        r.raise_for_status()
        with open(out, "wb") as f:
            f.write(r.content)
        manifest[key] = {"download_url": url, "retrieved_at": retrieved, "byte_size": os.path.getsize(out), "sha256": sha256(out)}
        json.dump(manifest, open(mpath, "w"), indent=1)
        print(key, manifest[key]["byte_size"], file=sys.stderr)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
