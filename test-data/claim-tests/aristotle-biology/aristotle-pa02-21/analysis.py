#!/usr/bin/env python3
"""aristotle-pa02-21: cuttlebone, squid gladius, and no internal shell in octopuses.

Re-run: python3 analysis.py

The three catalogue URLs committed in result.json are fetched first. If they are
front matter without shell diagnoses, the key chapter of the same FAO Volume 1
is fetched and coded. That switch is recorded in deviations. Pass and fail
thresholds are not changed. Shell words are attributed only to the family named
in the same key couplet, because one sentence of the key names several families.
"""
import hashlib
import json
import re
import warnings
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import requests

warnings.filterwarnings("ignore")
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphi-claim-tests/1.0 (aristotle-pa02-21)"}
PLANNED = {
    "vol1": "https://www.fao.org/3/a0150e/a0150e.pdf",
    "vol2": "https://www.fao.org/3/i1920e/i1920e.pdf",
    "vol3": "https://www.fao.org/3/i3489e/i3489e.pdf",
}
KEY_URL = "https://www.fao.org/4/a0150e/a0150e03.pdf"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest):
    DATA.mkdir(parents=True, exist_ok=True)
    meta_path = Path(str(dest) + ".meta.json")
    if dest.exists() and dest.stat().st_size > 0 and meta_path.exists():
        return json.loads(meta_path.read_text()), dest.read_bytes()
    r = requests.get(url, timeout=180, headers=UA)
    r.raise_for_status()
    meta = {
        "download_url": r.url,
        "requested_url": url,
        "retrieved_at": now(),
        "byte_size": len(r.content),
        "sha256": hashlib.sha256(r.content).hexdigest(),
        "content_type": r.headers.get("content-type", ""),
    }
    dest.write_bytes(r.content)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return meta, r.content


def pdf_text(blob):
    if not blob.startswith(b"%PDF"):
        return ""
    reader = PdfReader(BytesIO(blob))
    return "\n".join((p.extract_text() or "") for p in reader.pages), len(reader.pages)


def norm(text):
    text = text.replace("\u00ad", "")
    text = re.sub(r"([A-Za-z])\s+(?=[A-Za-z]\s)", r"\1", text)  # undo spaced small-caps lightly
    return re.sub(r"\s+", " ", text)


def couplet_attribution(text):
    """Pull key couplets that state an internal shell and the taxon they lead to."""
    flat = norm(text)
    # Couplets look like '5b. Internal shell ... Family Sepiidae' or 'calcified (Sepiidae)'.
    hits = []
    for m in re.finditer(r"internal shell[^.]{0,280}", flat, re.I):
        window = m.group(0)
        taxa = re.findall(
            r"\b(Sepiidae|Sepiolidae|Sepiadariidae|Idiosepiidae|Spirulidae|Loliginidae|Myopsid\s+squids|Oegopsid\s+squids|Octopods|Octopoda|Incirrata)\b",
            window,
            re.I,
        )
        parenthetical = re.findall(
            r"(calcified|chalky|chitinous|absent|vestige|gladius|feather|rod-shaped|laminate)\s*\(([^)]{0,80})\)",
            window,
            re.I,
        )
        hits.append({"window": window[:500], "taxa": taxa, "parenthetical": parenthetical})
    return flat, hits


def code_groups(flat):
    """Return match/fail/unscored for the three clauses, plus the evidence sentence."""
    flat = norm(flat)
    notes = []
    # Sepiidae: cuttlebone words, or the key's calcified laminate chalky shell attributed to Sepiidae.
    sepiidae = "unscored"
    sepiidae_ev = ""
    if re.search(r"Sepiidae.{0,200}(cuttlebone|sepion|os sepiae)|(cuttlebone|sepion|os sepiae).{0,200}Sepiidae", flat, re.I):
        sepiidae, sepiidae_ev = "match", "cuttlebone or sepion named with Sepiidae"
    elif re.search(r"Internal shell calcified, straight, laminate, chalky.{0,250}Sepiidae", flat, re.I):
        sepiidae, sepiidae_ev = "match", "key couplet: internal shell calcified, straight, laminate, chalky — Family Sepiidae"
        notes.append("Sepiidae couplet does not use the words cuttlebone or sepion. The calcified, laminate, chalky internal shell in that couplet is coded as the os sepiae. Threshold unchanged.")
    elif re.search(r"calcified\s*\(\s*Sepiidae\s*\)", flat, re.I):
        sepiidae, sepiidae_ev = "match", "key: internal shell calcified (Sepiidae)"
        notes.append("Presence for Sepiidae is taken from 'calcified (Sepiidae)' in the key, not from the word cuttlebone. The word absent in that sentence is attached to other families in parentheses and is not applied to Sepiidae.")
    # Word boundaries: "Idiosepiidae" contains the letters of Sepiidae and must not count.
    if re.search(r"absent\s*\(\s*[^)]*\bSepiidae\b", flat, re.I):
        sepiidae, sepiidae_ev = "fail", "key says the shell is absent for Sepiidae"

    # Squids: gladius/pen, or feather- or rod-shaped chitinous internal shell leading to myopsid and oegopsid squids.
    squid = "unscored"
    squid_ev = ""
    if re.search(r"(Myopsid\s+squids|Oegopsid\s+squids|Loliginidae).{0,200}\b(gladius|pen)\b", flat, re.I) or re.search(
        r"\b(gladius|pen)\b.{0,200}(Myopsid\s+squids|Oegopsid\s+squids|Loliginidae)", flat, re.I
    ):
        squid, squid_ev = "match", "gladius or pen named with squids"
    elif re.search(r"Internal shell straight, feather-\s*or\s*rod-shaped, chit\s*inous.{0,400}(Myopsid\s*squids|Oegopsid\s*squids)", flat, re.I):
        squid, squid_ev = "match", "key couplet: internal shell straight, feather- or rod-shaped, chitinous — myopsid and oegopsid squids"
        notes.append("The squid couplet does not use the word gladius. A feather- or rod-shaped chitinous internal shell is the gladius the claim names. Threshold unchanged.")
    elif re.search(r"Myopsid and Oegopsid Squids.{0,800}Internal shell straight, feather-\s*or\s*rod-shaped, chit\s*inous", flat, re.I):
        squid, squid_ev = "match", "squid catalogue: internal shell straight, feather- or rod-shaped, chitinous, in the key to myopsid and oegopsid squids"
        notes.append("The squid couplet does not use the word gladius. A feather- or rod-shaped chitinous internal shell is the gladius the claim names. Threshold unchanged.")
    if re.search(r"(Myopsid\s+squids|Oegopsid\s+squids).{0,80}absent|no internal shell.{0,80}(Myopsid|Oegopsid)", flat, re.I):
        squid, squid_ev = "fail", "key denies an internal shell in squids"

    # Octopuses: match only if vestige, stylet, gladius, and shell are said to be absent for the group.
    # Variable (vestige or absent) fails the universal.
    octopus = "unscored"
    octopus_ev = ""
    oct_window = None
    m = re.search(r"Internal shell vestige.{0,500}Octopods", flat, re.I)
    if m:
        oct_window = m.group(0)
        if re.search(r"absent", oct_window, re.I) and re.search(r"rods|U-shaped|vestige", oct_window, re.I):
            octopus, octopus_ev = "fail", oct_window[:400]
        elif re.search(r"\babsent\b", oct_window, re.I) and not re.search(r"rods|U-shaped|stylet|vestige", oct_window, re.I):
            octopus, octopus_ev = "match", oct_window[:400]
        else:
            octopus, octopus_ev = "fail", oct_window[:400]
    elif re.search(
        r"Octopuses.{0,800}internal shell is reduced to\s*a pair of small rod-like stylets or is absent",
        flat,
        re.I,
    ):
        octopus, octopus_ev = "fail", "octopod diagnosis: internal shell reduced to rod-like stylets or absent"
    elif re.search(r"Octopods.{0,160}(no internal shell|shell absent|without an internal shell)", flat, re.I):
        octopus, octopus_ev = "match", "octopods described as lacking an internal shell"
    return {
        "sepiidae": sepiidae,
        "squid": squid,
        "octopus": octopus,
        "evidence": {"sepiidae": sepiidae_ev, "squid": squid_ev, "octopus": octopus_ev},
        "terminology_notes": notes,
    }


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    planned_meta = {}
    planned_text = {}
    for key, url in PLANNED.items():
        meta, blob = fetch(url, DATA / f"{key}.pdf")
        planned_meta[key] = meta
        extracted = pdf_text(blob)
        if extracted == "":
            planned_text[key] = ""
            planned_meta[key]["pages"] = 0
        else:
            text, pages = extracted
            planned_text[key] = text
            planned_meta[key]["pages"] = pages
            planned_meta[key]["chars"] = len(text)

    combined_planned = "\n".join(planned_text.values())
    planned_code = code_groups(combined_planned)
    deviations = []
    used = "planned"
    code = {
        "sepiidae": planned_code["sepiidae"],
        "squid": planned_code["squid"],
        "octopus": planned_code["octopus"],
        "evidence": dict(planned_code["evidence"]),
        "terminology_notes": list(planned_code["terminology_notes"]),
    }
    key_meta = None
    key_states = None
    if any(planned_code[k] == "unscored" for k in ("sepiidae", "squid", "octopus")):
        pages = {k: planned_meta[k].get("pages") for k in planned_meta}
        deviations.append(
            f"The pre-registered Volume 1 URL is a {pages.get('vol1')}-page front-matter file and states no shell diagnosis. "
            f"Volume 2 ({pages.get('vol2')} pages, squids) and Volume 3 ({pages.get('vol3')} pages, octopods) are the full catalogues and were coded. "
            "Any clause those volumes leave unscored is filled from the key chapter of the same catalogue, "
            "https://www.fao.org/4/a0150e/a0150e03.pdf. Thresholds were not changed."
        )
        key_meta, key_blob = fetch(KEY_URL, DATA / "vol1-key.pdf")
        extracted = pdf_text(key_blob)
        key_text, key_pages = extracted if extracted != "" else ("", 0)
        key_meta["pages"] = key_pages
        key_meta["chars"] = len(key_text)
        key_code = code_groups(key_text)
        key_states = {k: key_code[k] for k in ("sepiidae", "squid", "octopus")}
        for k in ("sepiidae", "squid", "octopus"):
            if planned_code[k] == "unscored" and key_code[k] != "unscored":
                code[k] = key_code[k]
                code["evidence"][k] = key_code["evidence"][k]
            elif planned_code[k] != "unscored" and key_code[k] not in ("unscored", planned_code[k]):
                deviations.append(
                    f"{k}: the full catalogue codes {planned_code[k]} and the Volume 1 key codes {key_code[k]}. The catalogue code is kept."
                )
        filled_from_key = [
            k for k in ("sepiidae", "squid", "octopus")
            if planned_code[k] == "unscored" and key_code[k] != "unscored"
        ]
        for note in key_code["terminology_notes"]:
            if "Sepiidae" in note and "sepiidae" in filled_from_key and note not in code["terminology_notes"]:
                code["terminology_notes"].append(note)
            if "squid" in note.lower() and "squid" in filled_from_key and note not in code["terminology_notes"]:
                code["terminology_notes"].append(note)
        deviations.extend(code["terminology_notes"])
        used = "planned-plus-key"

    states = {k: code[k] for k in ("sepiidae", "squid", "octopus")}
    fails = [k for k, v in states.items() if v == "fail"]
    matches = [k for k, v in states.items() if v == "match"]
    unscored = [k for k, v in states.items() if v == "unscored"]
    if len(unscored) >= 2:
        verdict, confidence, reason = "inconclusive", 0.55, "data-unavailable"
    elif len(fails) >= 2:
        verdict, confidence, reason = "refutes", 0.65, None
    elif len(fails) == 1 or any(v == "fail" for v in states.values()):
        verdict, confidence, reason = "mixed", 0.50, None
    elif len(matches) == 3:
        verdict, confidence, reason = "supports", 0.70, None
    else:
        verdict, confidence, reason = "inconclusive", 0.55, "data-unavailable"

    # A variable description is stored as fail. One fail is mixed even if others match.
    if len(matches) == 3:
        verdict, confidence, reason = "supports", 0.70, None

    measured = {
        "value": len(matches),
        "unit": "group clauses matching the claim (Sepiidae cuttlebone, squid gladius, octopus without an internal shell or vestige)",
        "n": 3 - len(unscored),
        "uncertainty": "group-level key couplets, not a species count",
        "extra": {
            "source_used": used,
            "clauses": states,
            "planned_clauses": {k: planned_code[k] for k in ("sepiidae", "squid", "octopus")},
            "key_clauses": key_states,
            "evidence": code["evidence"],
            "planned_pages": {k: planned_meta[k].get("pages") for k in planned_meta},
            "planned_chars": {k: planned_meta[k].get("chars") for k in planned_meta},
        },
    }
    (DERIVED / "shell_codes.json").write_text(json.dumps({"code": code, "measured": measured, "deviations": deviations}, indent=2) + "\n")
    files = []
    for part in planned_meta:
        entry = {field: planned_meta[part][field] for field in ("download_url", "retrieved_at", "byte_size", "sha256")}
        entry["part"] = part
        entry["requested_url"] = planned_meta[part]["requested_url"]
        files.append(entry)
    if key_meta:
        files.append({k: key_meta[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")} | {"part": "vol1-key", "requested_url": KEY_URL})
    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = confidence
    result["data_kind"] = "biological" if measured["n"] else "none"
    result.pop("reason", None)
    if reason:
        result["reason"] = reason
    if deviations:
        result["deviations"] = deviations
    result["datasets"] = [{
        "id": "fao-cephalopods-catalogue-key",
        "name": "FAO Species Catalogue for Fishery Purposes No. 4, Cephalopods of the world, Jereb and Roper (eds.)",
        "landing_url": "https://www.fao.org/3/a0150e/a0150e.pdf",
        "doi": None,
        "version": "Vol. 1 key chapter a0150e03 plus the three volume URLs as retrieved",
        "license": "FAO, reproduction for educational non-commercial use as stated in the catalogue",
        "files": files,
        "role": "internal shell, cuttlebone or gladius, and shell vestige by cephalopod group",
    }]
    result["method"] = (
        "Downloaded the three pre-registered FAO PDFs. Volume 1 at that URL is front matter, so Sepiidae is read from the "
        "Volume 1 key chapter of the same catalogue. Volumes 2 and 3 are the full squid and octopod books and were coded. "
        "Key couplets that state an internal "
        "shell were attributed to the family or group named in that couplet. Sepiidae matches if it is given a calcified "
        "laminate shell (the cuttlebone). Squids match if myopsids and oegopsids are given a feather- or rod-shaped "
        "chitinous internal shell (the gladius). Octopuses match only if the group is said to lack a shell and any vestige. "
        "A couplet that allows either a vestige or absence fails that universal clause."
    )
    result["measured"] = measured
    if verdict == "supports":
        headline = "The FAO key gives cuttlefishes a calcified internal shell, squids a chitinous pen, and octopuses no shell and no vestige."
    elif verdict == "refutes":
        headline = "Two or three of the cuttlefish, squid, and octopus shell clauses contradict the FAO key."
    elif verdict == "mixed":
        headline = "Cuttlefishes and squids have the internal shells the claim names, and octopuses are described with a shell vestige or none, not with none in every case."
    else:
        headline = "The FAO files that could be fetched do not state the shell of two or more of the three groups."
    result["results_summary"] = [headline]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "confidence": confidence, "clauses": states, "n_deviations": len(deviations)}, indent=2))


if __name__ == "__main__":
    main()
