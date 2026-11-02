#!/usr/bin/env python3
"""Test aristotle-pa04-07 against Felgenhauer and Abele on decapod foreguts.

Re-run from this directory: python3 analysis.py
The PDF is about 15 MB and is not committed.
"""
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

PDF_URL = "https://research.nhm.org/pdfs/2492/2492-001.pdf"
CARABI = ["Cambarus", "Astacus", "Homarus", "Nephrops", "Panulirus", "Palinurus", "Procambarus", "Cherax", "Jasus", "Euastacus", "Orconectes", "Faxonius"]
CRABS = ["Cancer", "Carcinus", "Callinectes", "Uca", "Portunus", "Maja", "Xantho", "Pachygrapsus", "Brachyura"]
POSITIVE = ["gastric mill", "median tooth", "lateral teeth", "gastric teeth", "ossicle"]
ABSENT_PHRASES = ["no gastric mill", "lacks a gastric mill", "without a gastric mill", "gastric mill is absent"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def windows(text, name):
    hits = []
    for m in re.finditer(r"\b" + re.escape(name) + r"\b", text):
        start = max(0, m.start() - 250)
        end = min(len(text), m.end() + 250)
        hits.append(text[start:end])
    return hits


def score_name(text, name):
    found = windows(text, name)
    present_windows = []
    absent_windows = []
    for window in found:
        low = window.lower()
        positive = any(term in low for term in POSITIVE)
        blocked = bool(re.search(r"\b(?:absent|lacking|missing)\b", low))
        if positive and not blocked:
            present_windows.append(window)
        if any(phrase in low for phrase in ABSENT_PHRASES):
            absent_windows.append(window)
    # Present test is applied first. A name that meets it is scored present
    # even when a neighboring absence phrase also falls inside 250 characters.
    if present_windows:
        return "present", present_windows[0]
    if absent_windows:
        return "absent", absent_windows[0]
    if found:
        return "mentioned", found[0]
    return "not_mentioned", None


def main():
    r = requests.get(PDF_URL, timeout=180, headers={"User-Agent": "DelphiClaimTest/1.0"})
    r.raise_for_status()
    pdf = r.content
    path = os.path.join(DATA, "felgenhauer-abele.pdf")
    open(path, "wb").write(pdf)
    text = subprocess.check_output(["pdftotext", "-layout", path, "-"], stderr=subprocess.DEVNULL).decode("utf-8", "replace")
    flat = re.sub(r"\s+", " ", text)

    scored = {}
    for name in CARABI + CRABS:
        label, window = score_name(flat, name)
        scored[name] = {"score": label, "window": (window or "")[:500]}

    carabi_mentioned = [n for n in CARABI if scored[n]["score"] != "not_mentioned"]
    carabi_present = [n for n in CARABI if scored[n]["score"] == "present"]
    carabi_absent = [n for n in CARABI if scored[n]["score"] == "absent"]
    crab_present = [n for n in CRABS if scored[n]["score"] == "present"]
    crab_mentioned = [n for n in CRABS if scored[n]["score"] != "not_mentioned"]
    crab_absent = [n for n in CRABS if scored[n]["score"] == "absent"]
    crabs_discussed = len(crab_mentioned) > 0

    reason = None
    if not carabi_mentioned:
        verdict, reason = "inconclusive", "data-unavailable"
    elif carabi_present and crab_present:
        verdict = "supports"
    elif carabi_present and not crab_present:
        verdict = "mixed"
    elif carabi_mentioned and all(scored[n]["score"] == "absent" for n in carabi_mentioned):
        verdict = "refutes"
    elif crabs_discussed and crab_mentioned and all(scored[n]["score"] == "absent" for n in crab_mentioned) and not crab_present:
        verdict = "refutes"
    else:
        verdict, reason = "inconclusive", "other"

    confidence = 0.62 if verdict == "mixed" else (0.8 if verdict == "supports" else 0.45)
    measured = {
        "value": len(carabi_present) + len(crab_present),
        "unit": "list names scored present for a gastric mill or stomach teeth",
        "n": len(carabi_mentioned) + len(crab_mentioned),
        "uncertainty": "250-character windows on whitespace-collapsed pdftotext",
        "extra": {
            "carabi_present": carabi_present,
            "carabi_absent": carabi_absent,
            "carabi_mentioned": carabi_mentioned,
            "crab_present": crab_present,
            "crab_absent": crab_absent,
            "crab_mentioned": crab_mentioned,
            "scores": {n: scored[n]["score"] for n in scored},
            "present_windows": {n: scored[n]["window"] for n in carabi_present + crab_present},
            "because_front_teeth_insufficient": "untested",
            "verdict_by_rule": verdict,
        },
    }
    result = json.load(open(os.path.join(HERE, "result.json")))
    result["status"] = "complete"
    result["data_kind"] = "biological" if verdict != "inconclusive" or reason != "data-unavailable" else "none"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    result["confidence"] = confidence
    result["datasets"] = [{
        "id": "felgenhauer-abele-foregut-nhm",
        "name": "Felgenhauer and Abele, Phylogenetic relationships among shrimp-like decapods",
        "landing_url": PDF_URL,
        "doi": None,
        "version": "Offprint from Frederick R. Schram (ed.), Crustacean Phylogeny, A.A. Balkema, Rotterdam, as printed on the PDF",
        "license": "not stated on the file",
        "files": [{
            "download_url": PDF_URL,
            "retrieved_at": now(),
            "byte_size": len(pdf),
            "sha256": sha256(pdf),
            "content_type": r.headers.get("content-type", ""),
            "final_url": r.url,
        }],
        "role": "comparative decapod foregut text",
    }]
    result["method"] = (
        "pdftotext extracted the chapter. Whitespace was collapsed so line breaks do not split terms. "
        "A name is present when it sits within 250 characters of gastric mill, median tooth, lateral teeth, gastric teeth, or ossicle, "
        "and that window does not contain the words absent, lacking, or missing. "
        "A name is absent only when it is not present and it sits within 250 characters of an absence phrase. "
        "The adaptive 'because' clause is not scored."
    )
    result["measured"] = measured
    result["caveats"] = [
        "The chapter is about shrimp-like decapods. Cambarus is described in a reptant comparison, not as the paper's main subject.",
        "Brachyura occurs in a sentence about gastric-mill development increasing toward crabs. If the 250-character window also contains the word absent from the preceding caridean clause, Brachyura is not scored present.",
        "The claim's 'because the front teeth are insufficient' clause is untested.",
    ]
    with open(os.path.join(HERE, "result.json"), "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps({"verdict": verdict, "reason": reason, "carabi_present": carabi_present, "crab_present": crab_present, "scores": measured["extra"]["scores"]}, indent=2))


if __name__ == "__main__":
    main()
