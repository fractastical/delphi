"""Download the model sources used by analysis.py into data/ and record provenance in data/manifest.json."""
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone

import requests

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
BETSE_COMMIT = "4bba0624092f02ef52711d715d16ae7007d49aea"
RAW = f"https://raw.githubusercontent.com/betsee/betse/{BETSE_COMMIT}/"

FILES = {
    "betse_vg_funny.py": RAW + "betse/science/channels/vg_funny.py",
    "betse_vg_k.py": RAW + "betse/science/channels/vg_k.py",
    "betse_channelsabc.py": RAW + "betse/science/channels/channelsabc.py",
    "betse_gap_junction.py": RAW + "betse/science/channels/gap_junction.py",
    "betse_sim_config.yaml": RAW + "betse/data/yaml/sim_config.yaml",
    "pai2018_fulltext.xml": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5843655/fullTextXML",
    "pai2018_supplementary.zip": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5843655/supplementaryFiles",
}


def main():
    DATA.mkdir(exist_ok=True)
    manifest_path = DATA / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for name, url in FILES.items():
        if name in sys.argv[1:] or (not sys.argv[1:] and not (DATA / name).exists()):
            try:
                r = requests.get(url, timeout=300)
                r.raise_for_status()
            except Exception as e:
                print(f"FAILED {name}: {e}")
                continue
            body = r.content
            (DATA / name).write_bytes(body)
            manifest[name] = {
                "download_url": url,
                "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "byte_size": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
            print(name, len(body))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
