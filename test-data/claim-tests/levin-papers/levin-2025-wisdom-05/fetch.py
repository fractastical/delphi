#!/usr/bin/env python3
"""Download the GEO GSE98084 supplementary files into data/ and record URL, time, size, SHA-256.

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
BASE = "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE98nnn/GSE98084/suppl/"
FILES = ["GSE98084_All_Data_BaCl2.xlsx", "GSE98084_FPKM_Replicate_1.xlsx", "GSE98084_FPKM_Replicate_2.xlsx"]
SOFT = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE98084&targ=all&form=text&view=brief"


def get(url, name):
    for attempt in range(5):
        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 4:
                raise
            time.sleep(3)
    path = os.path.join(DATA, name)
    with open(path, "wb") as fh:
        fh.write(r.content)
    return {"name": name, "download_url": url,
            "retrieved_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}


def main():
    os.makedirs(DATA, exist_ok=True)
    manifest = [get(BASE + f, f) for f in FILES]
    manifest.append(get(SOFT, "GSE98084_family_brief.soft"))
    with open(os.path.join(DATA, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
