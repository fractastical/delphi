#!/usr/bin/env python3
"""Test aristotle-ha09-22 against Josef et al. 2012 full text.

The octopus matches adjacent objects, including when hunting and when alarmed.
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3359305/fullTextXML"
LANDING = "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0037579"


def fetch(url, name):
    path = os.path.join(DATA, name)
    meta = path + ".retrieved"
    if not (os.path.exists(path) and os.path.exists(meta)):
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        open(path, "wb").write(r.content)
        open(meta, "w").write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    content = open(path, "rb").read()
    return content, {
        "download_url": url,
        "retrieved_at": open(meta).read().strip(),
        "byte_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def section_text(root, titles):
    chunks = []
    for sec in root.iter("sec"):
        title = "".join(sec.findtext("title") or "")
        if title.strip().lower() in titles:
            chunks.append(" ".join(sec.itertext()))
    return re.sub(r"\s+", " ", " ".join(chunks))


def main():
    raw, file_meta = fetch(URL, "PMC3359305.fulltext.xml")
    root = ET.fromstring(raw)
    full = re.sub(r"\s+", " ", " ".join(root.itertext()))
    methods = section_text(root, {"methods", "materials and methods", "method"})
    results = section_text(root, {"results"})
    if not methods:
        methods = full
    if not results:
        results = full

    sentences = re.split(r"(?<=\.)\s+", results)
    chosen = None
    for sent in sentences:
        m = re.search(r"(\d+)\s+out of\s+(\d+)\s+octopuses", sent, re.I)
        if m and re.search(r"resembl|match|landmark|rock", sent, re.I):
            chosen = (int(m.group(1)), int(m.group(2)), sent.strip())
            break
    if chosen is None:
        m = re.search(r"(\d+)\s+out of\s+(\d+)\s+octopuses", full, re.I)
        if m:
            start = max(0, m.start() - 200)
            chosen = (int(m.group(1)), int(m.group(2)), full[start:m.end() + 300])

    hunting = bool(re.search(r"\b(prey|hunting|forag\w*)\b", methods, re.I))
    alarm = bool(re.search(r"\b(alarm\w*|threat\w*|disturb\w*|startl\w*)\b", methods, re.I))
    concealment = bool(re.search(r"camoufla\w*|conceal\w*", methods, re.I))
    species = sorted(set(re.findall(r"Octopus\s+[a-z]+", full)))

    if chosen is None:
        fraction = None
        rocks = False
        sentence = ""
        num = den = None
    else:
        num, den, sentence = chosen
        fraction = num / den
        rocks = bool(re.search(r"\brocks?\b|\bstones?\b", sentence, re.I))

    if fraction is None:
        verdict, reason = "inconclusive", "data-unavailable"
        confidence = 0.35
    elif fraction <= 0.5:
        verdict, reason = "refutes", None
        confidence = 0.7
    elif hunting and alarm and rocks:
        verdict, reason = "supports", None
        confidence = 0.6
    else:
        # Majority match that does not meet both named contexts is the partial outcome.
        verdict, reason = "mixed", None
        confidence = 0.64

    measured = {
        "value": None if fraction is None else round(fraction, 4),
        "unit": "fraction of imaged octopuses reported to match a nearby object",
        "n": den,
        "uncertainty": None if num is None else f"{num} of {den}; one case noted as not clear in the same sentence" if "not clear" in sentence else f"{num} of {den}",
        "extra": {
            "numerator": num,
            "denominator": den,
            "rocks_or_stones_in_match_sentence": rocks,
            "methods_mention_hunting_or_prey": hunting,
            "methods_mention_alarm_or_disturbance": alarm,
            "methods_mention_camouflage": concealment,
            "octopus_names_in_full_text": species,
            "match_sentence": sentence[:500],
        },
    }
    summary = {
        "verdict": verdict,
        "reason": reason,
        "confidence": confidence,
        "measured": measured,
        "data_kind": "biological" if fraction is not None else "none",
        "file": file_meta,
    }
    json.dump(summary, open(os.path.join(DERIVED, "summary.json"), "w"), indent=2)
    open(os.path.join(DERIVED, "match-sentence.txt"), "w").write(sentence + "\n")

    if "--write-result" in sys.argv:
        result_path = os.path.join(HERE, "result.json")
        result = json.load(open(result_path))
        result["status"] = "complete"
        result["data_kind"] = summary["data_kind"]
        result["verdict"] = verdict
        if reason:
            result["reason"] = reason
        result["confidence"] = confidence
        result["measured"] = measured
        result["datasets"] = [{
            "id": "josef2012-plosone-pmc3359305",
            "name": "Josef, Amodio, Fiorito and Shashar 2012, PLOS ONE e37579, Europe PMC full text",
            "landing_url": LANDING,
            "doi": "10.1371/journal.pone.0037579",
            "version": "PMC3359305",
            "license": "CC BY 4.0",
            "role": "field image counts of octopus background matching",
            "files": [file_meta],
        }]
        result["method"] = (
            "analysis.py downloads the Europe PMC JATS full text of PMC3359305 and takes the "
            "fraction in the results sentence that reports how many octopuses matched a nearby landmark. "
            f"That fraction is {num} of {den}. "
            f"The matched-object sentence names rocks: {rocks}. "
            f"The methods section mentions hunting or prey: {hunting}; alarm or disturbance: {alarm}; "
            f"camouflage: {concealment}. "
            "Support required a majority match, rocks or stones, and both a hunting context and an alarm context. "
            "A majority match that does not meet both contexts is the partial outcome named in the fail criterion."
        )
        result["caveats"] = [
            "Eleven images from one reef (Eilat) are not a sample of all octopuses.",
            "The animals were photographed already camouflaged. The methods do not record a prey approach or an alarm stimulus, so the two occasions Aristotle names are not separated.",
            "Octopus cyanea and O. vulgaris are both named; the 10-of-11 count is not split by species.",
            "A web-search snippet showed this count before preregistration. The threshold stayed a majority.",
            "Matching a nearby rock, coral, sand patch, or alga is a broader reading than matching only stones.",
        ]
        json.dump(result, open(result_path, "w"), indent=2)
        open(result_path, "a").write("\n")
    print(json.dumps({"verdict": verdict, "fraction": fraction, "hunting": hunting, "alarm": alarm, "rocks": rocks, "confidence": confidence}))


if __name__ == "__main__":
    main()
