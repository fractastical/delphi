#!/usr/bin/env python3
"""Download the model sources used by analysis.py into data/ (git-ignored except manifest.json);
data/manifest.json records URL, retrieval time, byte size and SHA-256.

Usage: python3 fetch.py [name ...]   (no names: fetch whatever is missing)
"""
import hashlib
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
BETSE_COMMIT = "4bba0624092f02ef52711d715d16ae7007d49aea"
RAW = f"https://raw.githubusercontent.com/betsee/betse/{BETSE_COMMIT}/"

FILES = {
    "betse_vg_funny.py": RAW + "betse/science/channels/vg_funny.py",
    "betse_vg_k.py": RAW + "betse/science/channels/vg_k.py",
    "betse_channelsabc.py": RAW + "betse/science/channels/channelsabc.py",
    "betse_gap_junction.py": RAW + "betse/science/channels/gap_junction.py",
    "betse_sim_config.yaml": RAW + "betse/data/yaml/sim_config.yaml",
    "betse_sim.py": RAW + "betse/science/sim.py",
    "betse_parameters.py": RAW + "betse/science/parameters.py",
    "pai2018_fulltext.xml": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5843655/fullTextXML",
    "pai2018_supplementary.zip": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5843655/supplementaryFiles",
}


def main():
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, ".gitignore"), "w") as f:
        f.write("*\n!.gitignore\n!manifest.json\n")
    manifest_path = os.path.join(DATA, "manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}
    wanted = sys.argv[1:] or [n for n in FILES if not os.path.exists(os.path.join(DATA, n))]
    for name in wanted:
        url = FILES[name]
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "delphisci-claim-test"})
            with urllib.request.urlopen(req, timeout=600) as r:
                body = r.read()
        except Exception as e:
            print(f"FAILED {name}: {e}")
            continue
        with open(os.path.join(DATA, name), "wb") as f:
            f.write(body)
        manifest[name] = {
            "download_url": url,
            "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "byte_size": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
        print(name, len(body))
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
