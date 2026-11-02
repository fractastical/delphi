#!/usr/bin/env python3
"""Test aristotle-ha02-07: no animal sheds molars, and the pig sheds no teeth."""
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
UA = "DelphiClaimTest/1.0 (aristotle-ha02-07; public claim test)"
FILES = []
MERCK = "https://www.merckvetmanual.com/digestive-system/dental-development-and-anatomy/estimation-of-age-by-examination-of-the-teeth-in-animals"
NCBI = "https://www.ncbi.nlm.nih.gov/books/NBK573074/"
OPENSTAX = "https://openstax.org/books/anatomy-and-physiology-2e/pages/23-3-the-mouth-pharynx-and-esophagus"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, name, role):
    path = os.path.join(DATA, name)
    meta = path + ".retrieved"
    if os.path.exists(path) and os.path.exists(meta):
        content = open(path, "rb").read()
        when = open(meta).read().strip()
    else:
        last = None
        for attempt in range(4):
            r = requests.get(url, headers={"User-Agent": UA}, timeout=120)
            last = r
            if r.status_code == 200 and r.content:
                break
            time.sleep(2 ** attempt)
        last.raise_for_status()
        content, when = last.content, now()
        open(path, "wb").write(content)
        open(meta, "w").write(when)
    FILES.append({
        "download_url": url,
        "retrieved_at": when,
        "byte_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "role": role,
    })
    return content


def is_present(cell):
    raw = cell.strip()
    low = raw.lower()
    if raw in {"", "—", "–", "-"} or "does not erupt" in low:
        return False
    return True


def parse_rows(html):
    i = html.lower().find("<table")
    j = html.lower().find("</table>", i)
    rows = []
    for row in re.findall(r"<tr[\s\S]*?</tr>", html[i:j]):
        cells = re.findall(r"<t[dh][\s\S]*?</t[dh]>", row)
        texts = []
        for c in cells:
            bits = re.findall(r'data-testid="topicText"[^>]*>(.*?)</span>', c, flags=re.S)
            bits = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", b)).strip() for b in bits]
            texts.append(" ".join(b for b in bits if b))
        if texts:
            rows.append(texts)
    header = rows[0]
    body = [r for r in rows[1:] if r and re.match(r"(?:Di|Dc|Dp|[ICPM])\d*", r[0])]
    return header, body


def main():
    html = fetch(MERCK, "merck-eruption.html", "eruption table").decode("utf-8", "replace")
    header, body = parse_rows(html)
    pig_i = header.index("Pig")
    deciduous = [r for r in body if r[0].startswith("D")]
    pig_deciduous = [{"tooth": r[0], "cell": r[pig_i], "present": is_present(r[pig_i])} for r in deciduous]
    pig_sheds = any(t["present"] for t in pig_deciduous)
    molar_rows = [r for r in body if re.match(r"Dm|deciduous molar", r[0], re.I)]
    clause2 = len(molar_rows) == 0
    clause3 = not pig_sheds

    ncbi = fetch(NCBI, "ncbi-primary.html", "planned human primary-dentition page").decode("utf-8", "replace")
    blocked = "recaptcha" in ncbi.lower() or "Checking your browser" in ncbi
    openstax = fetch(OPENSTAX, "openstax-23-3.html", "human tooth replacement").decode("utf-8", "replace")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", openstax))
    replaced = bool(re.search(r"deciduous teeth.{0,200}replaced", text, re.I))
    incisors_front = bool(re.search(r"incisors?.{0,80}front teeth", text, re.I))
    clause1 = replaced and incisors_front
    deviations = []
    if blocked:
        deviations.append({
            "field": "datasets",
            "change": "The human clause was read from OpenStax Anatomy and Physiology 2e section 23.3.",
            "why": "The NCBI Bookshelf URL returned a browser-check page. Pass and fail thresholds were not changed. Clause 1 does not decide a mixed or refutes verdict on its own.",
        })

    if not any(t["tooth"] == "Di1" for t in pig_deciduous):
        verdict, reason = "inconclusive", "data-unavailable"
    elif (not clause3) and (not clause2):
        verdict, reason = "refutes", None
    elif (not clause3) and clause2:
        verdict, reason = "mixed", None
    elif clause3 and (not clause2):
        verdict, reason = "mixed", None
    elif clause1 and clause2 and clause3:
        verdict, reason = "supports", None
    else:
        # Pig and molar clauses hold, human clause does not.
        verdict, reason = "mixed", None

    measured = {
        "value": sum(1 for t in pig_deciduous if t["present"]),
        "unit": "pig deciduous tooth classes with an eruption time",
        "n": len(pig_deciduous),
        "uncertainty": None,
        "extra": {
            "clause_man_sheds_front_teeth": clause1,
            "clause_no_species_sheds_molars": clause2,
            "clause_pig_sheds_none": clause3,
            "pig_deciduous": pig_deciduous,
            "deciduous_molar_rows": [r[0] for r in molar_rows],
            "openstax_replaced": replaced,
            "openstax_incisors_are_front": incisors_front,
        },
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2, ensure_ascii=False)
    path = os.path.join(HERE, "result.json")
    result = json.load(open(path))
    result["status"] = "complete"
    result["preregistered"] = True
    result["data_kind"] = "biological" if verdict != "inconclusive" else "none"
    result["verdict"] = verdict
    result["confidence"] = 0.83 if verdict == "mixed" else 0.5
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["deviations"] = deviations
    result["method"] = (
        "The Merck eruption table lists deciduous incisors, canines and premolars separately from permanent molars. "
        "A deciduous cell with an eruption age counts as a tooth that is shed when its permanent successor erupts. "
        "The pig sheds teeth if any such cell is filled. No species sheds molars if the table has no deciduous-molar row. "
        "OpenStax says the deciduous teeth are replaced and that the incisors are the front teeth; that is clause 1. "
        "Clause 3 failing while clause 2 holds is mixed, as pre-registered."
    )
    result["measured"] = measured
    result["caveats"] = [
        "Deciduous premolars are not counted as molars. Aristotle's 'molars' might have included cheek teeth that are now called premolars; that broader reading is not the one pre-registered.",
        "The table covers horse, cow, sheep, goat, pig, dog and cat. Elephants, which replace molars, are outside this measurement.",
        "NCBI Bookshelf did not return chapter text to this client.",
    ]
    result["datasets"] = [
        {
            "id": "merck-eruption-of-the-teeth",
            "name": "Merck Veterinary Manual, eruption of the teeth",
            "landing_url": MERCK,
            "doi": None,
            "version": "page retrieved with this run",
            "license": "publicly readable; Merck Veterinary Manual terms",
            "files": [f for f in FILES if "merckvetmanual" in f["download_url"]],
            "role": "deciduous and permanent eruption rows",
        },
        {
            "id": "ncbi-bookshelf-primary-dentition",
            "name": "NCBI Bookshelf page (blocked) and OpenStax section 23.3",
            "landing_url": OPENSTAX,
            "doi": None,
            "version": "2e",
            "license": "OpenStax CC BY 4.0; NCBI page was a browser check",
            "files": [f for f in FILES if "ncbi" in f["download_url"] or "openstax" in f["download_url"]],
            "role": "whether humans replace deciduous front teeth",
        },
    ]
    result["headline"] = (
        f"The pig has {measured['value']} deciduous tooth classes that erupt and are replaced, "
        "while the table lists no deciduous molars."
    )
    with open(path, "w") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(verdict, result["headline"])


if __name__ == "__main__":
    main()
