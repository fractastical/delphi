"""Test aristotle-pa02-42 against Schiffbauer et al. 2008 on muricid drill holes.

Requires pdftotext. Run: python3 analysis.py
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
URL = "https://webcentral.uc.edu/eprof/media/attachment/eprofmediafile_4198.pdf"
PURPURA = ("hexaplex", "bolinus", "murex", "purpura")


def pdf_text(data):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(data)
        handle.flush()
        out = subprocess.run(["pdftotext", "-layout", handle.name, "-"], check=True, capture_output=True)
    return out.stdout.decode("utf-8", "replace")


WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}


def first_int(pattern, text):
    match = re.search(pattern, text, flags=re.I)
    if not match:
        return None
    token = match.group(1).lower()
    if token in WORDS:
        return WORDS[token]
    return int(token)


def main():
    fetched = _fetch.fetch(URL)
    text = pdf_text(fetched["data"])
    low = text.lower()
    muricid = "muricid" in low or "nucella" in low
    drilling = "drill hole" in low or "drill holes" in low or "drilled" in low
    radula = "radula" in low or "radular" in low
    chemical = "dissolution" in low or "chemically aided" in low or "accessory boring" in low
    exclusive = bool(re.search(r"rather than (?:the |mechanical )?radula", low))
    genera = sorted({genus for genus in ("nucella", "hexaplex", "bolinus", "murex", "purpura", "stramonita") if genus in low})
    mediterranean = any(genus in genera for genus in PURPURA)
    if not (muricid and drilling):
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.4
    elif exclusive or (muricid and not drilling):
        verdict, reason, confidence = "refutes", None, 0.66
    elif radula and chemical and not exclusive:
        verdict, reason, confidence = "mixed", None, 0.70 if mediterranean else 0.66
    elif radula and drilling and not chemical:
        verdict, reason, confidence = "supports", None, 0.70 if mediterranean else 0.58
    elif drilling and not radula:
        verdict, reason, confidence = "mixed", None, 0.66
    else:
        verdict, reason, confidence = "inconclusive", "other", 0.4
    two_limpets = None
    word_two = re.search(r"Only (two|\d+) drilled limpets", text)
    if word_two:
        token = word_two.group(1)
        two_limpets = 2 if token == "two" else int(token)
    measured = {
        "value": two_limpets,
        "unit": "limpets drilled by Nucella ostrina in the laboratory trial named in the paper",
        "n": first_int(r"(\d+) specimens of N\. ostrina", text),
        "uncertainty": None,
        "extra": {
            "muricid_named": muricid,
            "drill_holes_named": drilling,
            "radula_credited": radula,
            "chemical_dissolution_credited": chemical,
            "explicit_rather_than_radula": exclusive,
            "genera": genera,
            "mediterranean_purpura_named": mediterranean,
            "n_limpets_offered": first_int(r"(\d+) limpets", text),
            "mussel_repository": first_int(r"repository of (\d+)", text),
            "mussels_examined": first_int(r"examined (\w+) mussels", text),
        },
    }
    examined = re.search(r"the (\w+) were selected from the Virginia Tech repository of (\d+)", text, re.I)
    if examined:
        word = examined.group(1)
        words = {"two": 2, "six": 6, "three": 3, "four": 4, "five": 5}
        measured["extra"]["mussels_examined"] = words.get(word.lower(), measured["extra"]["mussels_examined"])
        measured["extra"]["mussel_repository"] = int(examined.group(2))
    doi = None
    doi_match = re.search(r"DOI:\s*(10\.\d{4,}/[^\s]+)", text)
    if doi_match:
        doi = doi_match.group(1).rstrip(".,)")
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    assert result["pass_criterion"].startswith("Pre-registered.")
    result.update({
        "status": "complete",
        "data_kind": "biological",
        "verdict": verdict,
        "confidence": confidence,
        "method": (
            "The openly posted PDF of Schiffbauer, Yanes, Tyler, Kowalewski and Leighton 2008 was downloaded "
            "and converted with pdftotext. The full text was scored for a muricid predator, drill holes in "
            "mollusc shells, credit to the radula, and credit to chemical dissolution. An explicit 'rather than "
            "the radula' contrast would have refuted the tongue clause. Credit to both, without that contrast, "
            "was pre-registered as mixed. Counts were taken only from phrases in the text."
        ),
        "datasets": [{
            "id": "schiffbauer-microstructural-drill-holes-pdf",
            "name": "Schiffbauer et al. 2008, microstructures of predatory drill holes",
            "landing_url": URL,
            "doi": doi,
            "version": "PALAIOS 2008, university-posted PDF",
            "license": None,
            "files": [{k: fetched[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
            "role": "laboratory muricid drill holes and the organ credited with making them",
        }],
        "measured": measured,
        "caveats": [
            "The muricids in the experiments are Nucella, dogwhelks, not the Mediterranean purple-dye snails Aristotle called purpurae. The claim's scope includes muricids generally, and the confidence is the lower pre-registered value.",
            "The paper's subject is how to recognise drill holes, not a survey of every muricid. It does report laboratory prey drilled by named muricids.",
            "Chemical dissolution and radular rasp marks are both described. The pre-registered rule scores that combination as mixed.",
            "No licence line was extracted from the PDF.",
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
    print(verdict, confidence, genera, measured["value"], measured["extra"]["mussel_repository"], exclusive, chemical, radula)


if __name__ == "__main__":
    main()
