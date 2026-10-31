"""Try to download DryadData.xlsx from Dryad doi:10.5061/dryad.15nj0 (Cook et al. 2015) into data/ (git-ignored).

Dryad serves a JavaScript proof-of-work challenge (Anubis) to scripted requests. This script does not circumvent it. If the
response is not a spreadsheet, it records the block in data/manifest.json and exits with status 2; the test is then
inconclusive (data-unavailable). If a person downloads the file in a browser and saves it as data/DryadData.xlsx, re-running
this script records its byte size and SHA-256 and the analysis can proceed.
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
URL = "https://datadryad.org/stash/downloads/file_stream/54407"
LANDING = "https://datadryad.org/dataset/doi:10.5061/dryad.15nj0"
OUT = os.path.join(DATA, "DryadData.xlsx")


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
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if os.path.exists(OUT):
        with open(OUT, "rb") as f:
            head = f.read(4)
        if head[:2] == b"PK":
            manifest["dryad_file"] = {"download_url": URL, "landing_url": LANDING, "retrieved_at": manifest.get("dryad_file", {}).get("retrieved_at", now),
                                      "byte_size": os.path.getsize(OUT), "sha256": sha256(OUT), "obtained": "file present (manual browser download or earlier run)"}
            json.dump(manifest, open(mpath, "w"), indent=1)
            print(json.dumps(manifest, indent=1))
            return
    r = requests.get(URL, headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=120, allow_redirects=True)
    body = r.content
    if r.ok and body[:2] == b"PK":
        with open(OUT, "wb") as f:
            f.write(body)
        manifest["dryad_file"] = {"download_url": URL, "landing_url": LANDING, "retrieved_at": now, "byte_size": len(body), "sha256": sha256(OUT), "obtained": "direct"}
        json.dump(manifest, open(mpath, "w"), indent=1)
        print(json.dumps(manifest, indent=1))
        return
    blocked = b"anubis" in body.lower() or r.status_code in (403, 401)
    manifest["dryad_file"] = {"download_url": URL, "landing_url": LANDING, "attempted_at": now, "http_status": r.status_code,
                              "blocked": blocked, "note": "Dryad returned a proof-of-work challenge page / 403 to the scripted request; not circumvented"}
    json.dump(manifest, open(mpath, "w"), indent=1)
    print(json.dumps(manifest, indent=1))
    sys.exit(2)


if __name__ == "__main__":
    main()
