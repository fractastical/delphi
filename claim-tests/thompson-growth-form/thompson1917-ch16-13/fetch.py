"""Download the two Dryad datasets used by analysis.py into data/ (git-ignored, > 1 MB in total).

Dryad's per-file API endpoints require a bearer token, but the per-version zip assembly is public.
Both versions are the only published versions of their datasets (checked 2026-10-31).
"""
import hashlib
import json
import os
import sys
import time
import zipfile

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

SOURCES = {
    "figueirido2021": {
        "doi": "10.5061/dryad.3j9kd51ft",
        "url": "https://datadryad.org/api/v2/versions/72212/download",
        "zip": "doi_10_5061_dryad_3j9kd51ft.zip",
    },
    "gillet2019": {
        "doi": "10.5061/dryad.7dj6850",
        "url": "https://datadryad.org/api/v2/versions/41370/download",
        "zip": "doi_10_5061_dryad_7dj6850.zip",
    },
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
    for key, src in SOURCES.items():
        out = os.path.join(DATA, src["zip"])
        if not os.path.exists(out):
            r = requests.get(src["url"], headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=300)
            r.raise_for_status()
            with open(out, "wb") as f:
                f.write(r.content)
            manifest[key] = {
                "download_url": src["url"],
                "doi": src["doi"],
                "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "byte_size": os.path.getsize(out),
                "sha256": sha256(out),
            }
        with zipfile.ZipFile(out) as z:
            z.extractall(os.path.join(DATA, key))
            manifest.setdefault(key, {})["members"] = [
                {"name": i.filename, "byte_size": i.file_size} for i in z.infolist()
            ]
    json.dump(manifest, open(manifest_path, "w"), indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    sys.exit(main())
