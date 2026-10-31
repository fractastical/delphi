# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""Fetch the Wikimedia Commons images in inputs/sources.json and prepare them for Cellpose.

Downloads each file from `download_url`, checks its SHA-256 against `download_sha256`,
applies the recorded crop, and writes inputs/images/<id>.png. The prepared PNG's SHA-256
is compared with `prepared_png_sha256`, the hash of the file Nebius segmented; a mismatch
(e.g. a different PNG encoder) is reported but the pixels are what the masks describe.

    uv run claim-sources/cell-geometry/fetch_inputs.py
"""
import hashlib
import io
import json
import urllib.request
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "delphisci/0.1 (https://github.com/fractastical/delphisci)"}


def main():
    sources = json.loads((HERE / "inputs" / "sources.json").read_text())
    (HERE / "inputs" / "images").mkdir(parents=True, exist_ok=True)
    for image_id, m in sources.items():
        data = urllib.request.urlopen(urllib.request.Request(m["download_url"], headers=UA), timeout=120).read()
        sha = hashlib.sha256(data).hexdigest()
        if sha != m["download_sha256"]:
            print(f"{image_id}: DOWNLOAD CHANGED (sha256 {sha}, expected {m['download_sha256']})")
            continue
        im = Image.open(io.BytesIO(data)).convert("RGB")
        if m.get("crop"):
            im = im.crop(tuple(m["crop"]))
        out = HERE / "inputs" / m["image"]
        im.save(out)
        png = hashlib.sha256(out.read_bytes()).hexdigest()
        note = "matches" if png == m.get("prepared_png_sha256") else "differs from the segmented file's hash (encoder difference?)"
        print(f"{image_id}: ok; prepared PNG {note}")


if __name__ == "__main__":
    main()
