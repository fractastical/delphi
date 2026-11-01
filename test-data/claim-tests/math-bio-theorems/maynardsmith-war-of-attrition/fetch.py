"""Try to download fight.csv and README.md from Dryad doi:10.5061/dryad.bg79cnpjg (spider contest displays) into data/ (git-ignored).

Dryad serves a JavaScript proof-of-work challenge (Anubis) to scripted requests. This script does not circumvent it. If the
response is not the CSV, it records the block in data/manifest.json and exits with status 2; the test is then inconclusive
(data-unavailable). If a person downloads the files in a browser and saves them as data/fight.csv (and data/README.md),
re-running this script records their byte sizes and SHA-256 and the analysis can proceed.
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
LANDING = "https://datadryad.org/dataset/doi:10.5061/dryad.bg79cnpjg"
FILES = {
    "fight.csv": "https://datadryad.org/stash/downloads/file_stream/3037112",
    "README.md": "https://datadryad.org/stash/downloads/file_stream/3037114",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def looks_like_text_data(body):
    low = body[:4000].lower()
    return b"<html" not in low and b"anubis" not in low and b"<!doctype" not in low


def main():
    os.makedirs(DATA, exist_ok=True)
    mpath = os.path.join(DATA, "manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    any_blocked = False
    for name, url in FILES.items():
        out = os.path.join(DATA, name)
        if os.path.exists(out):
            with open(out, "rb") as f:
                body = f.read()
            if looks_like_text_data(body):
                manifest[name] = {"download_url": url, "landing_url": LANDING, "retrieved_at": manifest.get(name, {}).get("retrieved_at", now),
                                  "byte_size": len(body), "sha256": sha256(out), "obtained": "file present (manual browser download or earlier run)"}
                continue
        r = requests.get(url, headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=120, allow_redirects=True)
        body = r.content
        if r.ok and looks_like_text_data(body):
            with open(out, "wb") as f:
                f.write(body)
            manifest[name] = {"download_url": url, "landing_url": LANDING, "retrieved_at": now, "byte_size": len(body), "sha256": sha256(out), "obtained": "direct"}
        else:
            any_blocked = True
            manifest[name] = {"download_url": url, "landing_url": LANDING, "attempted_at": now, "http_status": r.status_code, "blocked": True,
                              "note": "Dryad returned a proof-of-work challenge page / 403 to the scripted request; not circumvented"}
    json.dump(manifest, open(mpath, "w"), indent=1)
    print(json.dumps(manifest, indent=1))
    if any_blocked and not manifest.get("fight.csv", {}).get("sha256"):
        sys.exit(2)


if __name__ == "__main__":
    main()
