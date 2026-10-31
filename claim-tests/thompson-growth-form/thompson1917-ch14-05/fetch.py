#!/usr/bin/env python3
"""Fetch the Turing's Sunflowers data (Dryad doi:10.5061/dryad.f9k77) and write the small
derived table used by analysis.py.

Dryad serves file downloads behind a browser proof-of-work challenge (Anubis), so a plain
HTTP GET may return an HTML page instead of the file. This script first tries a direct GET;
if that fails it looks for the files in ./data/ (download them in a browser from
https://datadryad.org/dataset/doi:10.5061/dryad.f9k77). Either way the SHA-256 of each file is
checked against the value recorded in result.json before anything is derived.

Files (Dryad file ids 4662 and 4663):
  JS annotations for MSF007_Countdata.xlsx            53848 bytes
  MSF007_SunflowerData_20151020_anonymised.xlsx      108344 bytes
"""
import hashlib
import os
import sys

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")

FILES = {
    "JS annotations for MSF007_Countdata.xlsx": {
        "url": "https://datadryad.org/downloads/file_stream/4662",
        "sha256": "1ae05773075326e64bd110bdd5dd90a6d78986d2fdff67936532ac51167b883d",
        "size": 53848,
    },
    "MSF007_SunflowerData_20151020_anonymised.xlsx": {
        "url": "https://datadryad.org/downloads/file_stream/4663",
        "sha256": "b3df75b467d92c08eb58a5a78576aa2ee5937153de7640b3ef8df14bd143f408",
        "size": 108344,
    },
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def obtain(name, spec):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        try:
            r = requests.get(spec["url"], timeout=120, allow_redirects=True,
                             headers={"User-Agent": "delphi-claim-tests/1.0"})
            if r.ok and r.content[:2] == b"PK":
                with open(path, "wb") as f:
                    f.write(r.content)
        except requests.RequestException as e:
            print(f"direct download failed: {e}", file=sys.stderr)
    if not os.path.exists(path):
        sys.exit(f"{name} not available. Download it from "
                 f"https://datadryad.org/dataset/doi:10.5061/dryad.f9k77 into {DATA}/")
    got = sha256(path)
    if got != spec["sha256"]:
        sys.exit(f"checksum mismatch for {name}: {got}")
    print(f"ok {name} {os.path.getsize(path)} bytes sha256={got}")
    return path


def main():
    j = pd.read_excel(obtain("JS annotations for MSF007_Countdata.xlsx",
                             FILES["JS annotations for MSF007_Countdata.xlsx"]),
                      sheet_name="JS annotation")
    g = pd.read_excel(obtain("MSF007_SunflowerData_20151020_anonymised.xlsx",
                             FILES["MSF007_SunflowerData_20151020_anonymised.xlsx"]),
                      sheet_name="Sheet1")
    j = j[["ID", "PhotoCount", "Countable", "JS.P1", "H1", "d1", "JS.P2", "H2", "d2"]]
    # Column semantics from the authors' MOSIpaperPE.Rnw: Spiral.Count.A = submitter's
    # clockwise count, Spiral.Count.B = submitter's anticlockwise count.
    g = g[["ID", "Species", "Cultivar", "Head.diameter", "Spiral.Count.A", "Spiral.Count.B"]]
    g = g.rename(columns={"Spiral.Count.A": "Public.Count.CW", "Spiral.Count.B": "Public.Count.CCW"})
    m = j.merge(g, on="ID", how="outer").sort_values("ID")
    for c in ("H1", "H2", "d1", "d2", "Countable", "JS.P1", "JS.P2"):
        m[c] = m[c].astype("string").str.strip()
    os.makedirs(DERIVED, exist_ok=True)
    out = os.path.join(DERIVED, "sunflower_counts.csv")
    m.to_csv(out, index=False)
    print(f"wrote {out} ({len(m)} rows)")


if __name__ == "__main__":
    main()
