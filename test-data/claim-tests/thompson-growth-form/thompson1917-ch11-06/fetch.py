"""Download Walton & Korn (2018) ontogenetic conch-parameter data (Dryad 10.5061/dryad.c17p8) into data/."""
import hashlib
import json
import os
import time
import zipfile

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
URL = "https://datadryad.org/api/v2/versions/7242/download"  # zip assembly of the only published version


def main():
    os.makedirs(DATA, exist_ok=True)
    out = os.path.join(DATA, "doi_10_5061_dryad_c17p8.zip")
    if not os.path.exists(out):
        r = requests.get(URL, headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=300)
        r.raise_for_status()
        open(out, "wb").write(r.content)
        meta = {"download_url": URL, "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}
        json.dump(meta, open(os.path.join(DATA, "manifest.json"), "w"), indent=1)
    with zipfile.ZipFile(out) as z:
        z.extractall(os.path.join(DATA, "extracted"))
        print([(i.filename, i.file_size) for i in z.infolist()])
    print(open(os.path.join(DATA, "manifest.json")).read())


if __name__ == "__main__":
    main()
