"""Download NHANES Body Measures and Demographics XPT files for cycles 2013-2014 (H), 2015-2016 (I) and 2017-2018 (J)
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
CYCLES = {"H": 2013, "I": 2015, "J": 2017}


def main():
    os.makedirs(DATA, exist_ok=True)
    manifest = {}
    for suffix, year in CYCLES.items():
        for comp in ("BMX", "DEMO"):
            url = f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{comp}_{suffix}.xpt"
            out = os.path.join(DATA, f"{comp}_{suffix}.xpt")
            retrieved = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            with requests.get(url, headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=600, stream=True) as r:
                r.raise_for_status()
                h = hashlib.sha256()
                with open(out, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk); h.update(chunk)
            manifest[f"{comp}_{suffix}"] = {"download_url": url, "retrieved_at": retrieved, "byte_size": os.path.getsize(out), "sha256": h.hexdigest()}
    json.dump(manifest, open(os.path.join(DATA, "manifest.json"), "w"), indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
