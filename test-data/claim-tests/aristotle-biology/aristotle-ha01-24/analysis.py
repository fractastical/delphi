#!/usr/bin/env python3
"""Which kidney lies higher (aristotle-ha01-24).
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import fetch, load_result, sentences, strip_html, write_result

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RESULT = os.path.join(HERE, "result.json")
PAGES = [
    ("openstax", "Homo sapiens", "https://openstax.org/books/anatomy-and-physiology-2e/pages/25-3-gross-anatomy-of-the-kidney"),
    ("hawaii", "Homo sapiens", "https://xrcore.jabsom.hawaii.edu/abdomen/4-4-posterior-abdominal-wall.html"),
    ("umn", "Canis familiaris and Felis catus", "https://pressbooks.umn.edu/dogcatanatomylabguide/chapter/part-2-abdominal-viscera/"),
]


def direction(sentence):
    s = sentence.lower()
    if "kidney" not in s:
        return None
    cranial = bool(re.search(
        r"right kidney is (?:located )?further cranially|"
        r"right kidney is (?:higher|more cranial|superior)|"
        r"left kidney is (?:lower|more caudal)",
        s,
    ))
    caudal = bool(re.search(
        r"right (?:kidney )?is lower|"
        r"left kidney lies more cranial|"
        r"left kidney is (?:higher|more cranial|superior)|"
        r"right kidney is (?:more caudal|inferior)",
        s,
    ))
    if cranial and caudal:
        return "conflict"
    if cranial:
        return "right_cranial"
    if caudal:
        return "right_caudal"
    return None


def main():
    os.makedirs(DATA, exist_ok=True)
    files = []
    sources = []
    for slug, species, url in PAGES:
        meta = fetch(url, os.path.join(DATA, f"{slug}.html"), timeout=90)
        meta["label"] = slug
        files.append(meta)
        text = strip_html(open(os.path.join(DATA, f"{slug}.html"), encoding="utf-8", errors="replace").read())
        hits = []
        for sentence in sentences(text):
            d = direction(sentence)
            if d:
                hits.append({"direction": d, "sentence": sentence[:500]})
        directions = {h["direction"] for h in hits}
        if directions == {"right_cranial"}:
            call = "right_cranial"
        elif directions == {"right_caudal"}:
            call = "right_caudal"
        elif len(directions) > 1:
            call = "conflict"
        else:
            call = "unscored"
        sources.append({"id": slug, "species_context": species, "call": call, "hits": hits})

    human = [s for s in sources if s["species_context"] == "Homo sapiens"]
    human_calls = {s["call"] for s in human}
    species_scores = []
    if human_calls == {"right_caudal"}:
        species_scores.append({"species": "Homo sapiens", "right_kidney": "caudal", "sources": [s["id"] for s in human]})
    elif human_calls == {"right_cranial"}:
        species_scores.append({"species": "Homo sapiens", "right_kidney": "cranial", "sources": [s["id"] for s in human]})
    elif len(human_calls) > 1:
        species_scores.append({"species": "Homo sapiens", "right_kidney": "conflict", "sources": [s["id"] for s in human]})

    umn = next(s for s in sources if s["id"] == "umn")
    if umn["call"] in ("right_cranial", "right_caudal"):
        # The sentence does not name dog or cat. It sits in the dog-and-cat dissection guide,
        # so both subjects of that guide receive the same call, with that limit recorded.
        side = "cranial" if umn["call"] == "right_cranial" else "caudal"
        for sp in ("Canis familiaris", "Felis catus"):
            species_scores.append({"species": sp, "right_kidney": side, "sources": ["umn"], "sentence_names_species": False})

    comparable = [s for s in species_scores if s["right_kidney"] in ("cranial", "caudal")]
    if any(s["right_kidney"] == "conflict" for s in species_scores) and len(comparable) <= 1:
        verdict, reason = "mixed", None
    elif any(s["right_kidney"] == "caudal" for s in comparable):
        verdict, reason = "refutes", None
    elif len(comparable) >= 2 and all(s["right_kidney"] == "cranial" for s in comparable) and any(s["species"] == "Homo sapiens" for s in comparable):
        verdict, reason = "supports", None
    elif not comparable:
        verdict, reason = "inconclusive", "data-unavailable"
    else:
        verdict, reason = "mixed", None

    n_caudal = sum(1 for s in comparable if s["right_kidney"] == "caudal")
    payload = {
        "datasets": [
            {
                "id": "openstax-anatomy-physiology-2e-25-3",
                "name": "OpenStax Anatomy and Physiology 2e, section 25.3",
                "landing_url": PAGES[0][2],
                "doi": None,
                "version": "2e",
                "license": "CC BY 4.0",
                "files": [files[0]],
                "role": "human kidney position",
            },
            {
                "id": "jabsom-hawaii-posterior-abdominal-wall",
                "name": "JABSOM posterior abdominal wall",
                "landing_url": PAGES[1][2],
                "doi": None,
                "version": None,
                "license": None,
                "files": [files[1]],
                "role": "independent human kidney position",
            },
            {
                "id": "umn-dog-cat-abdominal-viscera",
                "name": "University of Minnesota dog and cat abdominal viscera guide",
                "landing_url": PAGES[2][2],
                "doi": None,
                "version": None,
                "license": None,
                "files": [files[2]],
                "role": "non-human kidney position",
            },
        ],
        "method": (
            "Each page was stripped to sentences. A sentence scores the right kidney caudal when it says "
            "the right kidney is lower or the left lies more cranial, and cranial when it says the right "
            "kidney is further cranially. The two human pages must agree. The dog-and-cat guide scores "
            "both species only from its side-comparison sentence, which does not name one of them."
        ),
        "measured": {
            "value": n_caudal,
            "unit": "scored species in which the right kidney is caudal to the left",
            "n": len(comparable),
            "uncertainty": None,
            "extra": {"sources": sources, "species_scores": species_scores},
        },
        "verdict": verdict,
        "confidence": 0.88 if verdict == "refutes" else 0.55,
        "data_kind": "biological" if verdict != "inconclusive" else "none",
        "headline": (
            "In humans the right kidney is the lower one, in both OpenStax and the Hawaii cadaver guide, so it is not higher in every animal."
            if verdict == "refutes"
            else f"Kidney side calls: {species_scores}."
        ),
        "caveats": [
            "The dog-and-cat sentence says the right kidney is further cranial, and it does not separate the two species.",
            "A universal is refuted by the human arrangement even where a carnivore matches Aristotle.",
            "These are anatomical teaching texts, not a survey of every kidney-bearing animal.",
        ],
    }
    if reason:
        payload["reason"] = reason
    write_result(RESULT, load_result(RESULT), payload)
    print(verdict, species_scores)


if __name__ == "__main__":
    main()
