"""Test aristotle-ha04-02 against the FAO species sheet for Octopus vulgaris.

Requires pdftotext (poppler). Run: python3 analysis.py
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _fetch

HERE = Path(__file__).resolve().parent
URL = "https://www.fao.org/4/ac479e/ac479e34.pdf"


def pdf_text(data):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(data)
        handle.flush()
        out = subprocess.run(["pdftotext", "-layout", handle.name, "-"], check=True, capture_output=True)
    return out.stdout.decode("utf-8", "replace")


def vulgaris_block(text):
    start = text.find("En - Common octopus")
    if start < 0:
        start = text.find("Octopus vulgaris Cuvier, 1797")
    if start < 0:
        return ""
    return text[start:start + 1800]


def main():
    fetched = _fetch.fetch(URL)
    text = pdf_text(fetched["data"])
    block = vulgaris_block(text)
    low = block.lower()
    has_hecto = "hectocot" in low
    arm_iii = bool(re.search(r"arm\s+iii\b", low))
    arm_iv = bool(re.search(r"arm\s+iv\b|fourth arm|ventral arm|last arm", low))
    spoon = bool(re.search(r"spoon|ligula", low))
    fork = bool(re.search(r"fork|bifurcat|bifid|split", low))
    whitish = bool(re.search(r"whitish|white", low))
    sharp = bool(re.search(r"sharp|pointed", low))
    if not has_hecto:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.4
    elif (arm_iii and not arm_iv) or (spoon and not fork):
        verdict, reason, confidence = "refutes", None, 0.80
    elif arm_iv and not arm_iii and fork:
        verdict, reason, confidence = "supports", None, 0.82
    elif fork and spoon:
        verdict, reason, confidence = "mixed", None, 0.6
    else:
        verdict, reason, confidence = "mixed", None, 0.55
    measured = {
        "value": 3 if arm_iii else (4 if arm_iv else None),
        "unit": "FAO arm number of the hectocotylus",
        "n": 1,
        "uncertainty": None,
        "extra": {
            "block_excerpt": re.sub(r"\s+", " ", block)[:700],
            "hectocotylus_stated": has_hecto,
            "arm_iii": arm_iii,
            "arm_iv_or_last": arm_iv,
            "spoon_or_ligula": spoon,
            "forked": fork,
            "whitish_stated": whitish,
            "sharp_stated": sharp,
        },
    }
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    assert result["pass_criterion"].startswith("Pre-registered.")
    result.update({
        "status": "complete",
        "data_kind": "biological",
        "verdict": verdict,
        "confidence": confidence,
        "method": (
            "The FAO cephalopod identification sheet was downloaded and converted with pdftotext. "
            "The block beginning at the English name Common octopus was searched for the hectocotylus, "
            "the arm number, and the tip shape. Arm III fails the 'last arm' clause under the pre-registered "
            "mapping of 'last' to arm IV. A spoon-shaped ligula without fork language fails the tip clause. "
            "Colour and sharpness were recorded only when the same block stated them."
        ),
        "datasets": [{
            "id": "fao-cephalopod-sheet-ac479e-octopus-vulgaris",
            "name": "FAO species identification sheet, Octopus vulgaris (ac479e)",
            "landing_url": "https://www.fao.org/4/ac479e/ac479e34.pdf",
            "doi": None,
            "version": "FAO species identification sheets, Western Central Atlantic, cephalopods",
            "license": None,
            "files": [{k: fetched[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
            "role": "diagnostic statement of which arm is hectocotylized and the shape of its tip",
        }],
        "measured": measured,
        "caveats": [
            "Arm I dorsal to arm IV ventral is the FAO numbering, adopted before the sheet was read. Aristotle did not number arms this way.",
            "The sheet is a taxonomic diagnosis, not a count of males. One description stands for the species.",
            "Whitish colour and sharpness are not in the Octopus vulgaris diagnostic block, so those adjectives are untested.",
            "No licence line was extracted from the PDF text.",
        ],
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    derived = HERE / "derived"
    derived.mkdir(exist_ok=True)
    (derived / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    print(verdict, measured["extra"]["arm_iii"], measured["extra"]["spoon_or_ligula"], measured["extra"]["forked"])


if __name__ == "__main__":
    main()
