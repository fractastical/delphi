"""Download ICES DATRAS NS-IBTS age (CA) records, 2000-2024, quarters 1 and 3, into data/ (git-ignored).

Uses the public DATRAS Download API (the same endpoint as icesDatras::getDatrasUnaggregated).
Each request returns a zip holding DATRASDataTable.csv. One request per survey year and quarter so that
each file has its own checksum; the manifest in data/manifest.json records URL, time, size and SHA-256.
"""
import hashlib
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
BASE = "https://datras.ices.dk/Data_products/Download/DATRASDownloadAPI.aspx"
SURVEY = "NS-IBTS"
YEARS = range(2000, 2025)
QUARTERS = (1, 3)


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
    for year in YEARS:
        for q in QUARTERS:
            key = f"CA_{SURVEY}_{year}_Q{q}"
            out = os.path.join(DATA, key + ".zip")
            if os.path.exists(out) and key in manifest:
                continue
            url = f"{BASE}?recordtype=CA&survey={SURVEY}&year={year}&quarter={q}"
            for attempt in range(4):
                try:
                    r = requests.get(url, headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=600)
                    r.raise_for_status()
                    break
                except Exception as e:  # noqa: BLE001
                    if attempt == 3:
                        raise
                    time.sleep(4 * 2 ** attempt)
            with open(out, "wb") as f:
                f.write(r.content)
            manifest[key] = {
                "download_url": url,
                "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "byte_size": os.path.getsize(out),
                "sha256": sha256(out),
            }
            json.dump(manifest, open(manifest_path, "w"), indent=1)
            print(key, manifest[key]["byte_size"], file=sys.stderr)
    total = sum(v["byte_size"] for v in manifest.values())
    print(json.dumps({"files": len(manifest), "total_bytes": total,
                      "first_retrieved_at": min(v["retrieved_at"] for v in manifest.values()),
                      "last_retrieved_at": max(v["retrieved_at"] for v in manifest.values())}, indent=1))


if __name__ == "__main__":
    main()
