#!/usr/bin/env python3
"""Five gonads, five teeth, and five stomachs in every sea urchin (aristotle-pa04-09).
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import fetch, load_result, strip_html, write_result

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RESULT = os.path.join(HERE, "result.json")
PAGES = [
    ("mellita", "https://lanwebs.lander.edu/faculty/rsfox/invertebrates/mellita.html"),
    ("uw", "https://depts.washington.edu/embryology/index.php?id=anaphys"),
    ("digimorph", "http://digimorph.geo.utexas.edu/specimens/Encope_michelini/NPL4111/"),
]
WORDS = {
    "one": 1, "a single": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
}
# The noun may sit directly after the number ("five teeth") or after up to six other words.
NOUN_RE = re.compile(r"\b(gonads?|teeth|tooth|stomachs?)\b", re.I)
NUMBER_RE = re.compile(r"\b(a single|one|two|three|four|five|six|[1-6])\b", re.I)
RANGE_RE = re.compile(
    r"\b(?:a single|one|two|three|four|five|six|[1-6])\s+to\s+(?:a single|one|two|three|four|five|six|[1-6])\b",
    re.I,
)
NOT_NUMBER_RE = re.compile(
    r"\bnot\s+(a single|one|two|three|four|five|six|[1-6])\b",
    re.I,
)
FIG_RE = re.compile(r"\bfig(?:ure)?\.?\s*$", re.I)


def noun_key(noun):
    n = noun.lower()
    if n.startswith("gonad"):
        return "gonads"
    if n.startswith("tooth") or n.startswith("teeth"):
        return "teeth"
    return "stomachs"


def _blank(match):
    return " " * len(match.group(0))


def nearest_count(cleaned, noun_start):
    """Last number word in the same sentence, within six words, ignoring figure numbers and clock times."""
    sentence_start = cleaned.rfind(".", 0, noun_start) + 1
    before = cleaned[sentence_start:noun_start]
    chosen = None
    for match in NUMBER_RE.finditer(before):
        abs_start = sentence_start + match.start()
        if FIG_RE.search(cleaned[max(0, abs_start - 12):abs_start]):
            continue
        if cleaned[sentence_start + match.end():sentence_start + match.end() + 1] == ":":
            continue
        intervening = re.findall(r"\b[\w']+\b", before[match.end():])
        if len(intervening) > 6:
            continue
        chosen = match
    if chosen is None:
        return None
    return WORDS[chosen.group(1).lower()]


def extract(text, drop_regular_urchin_asides=False):
    # A range such as 'two to five' is not an explicit single count.
    # 'Not five' is a denial, not a count of five. Blanking keeps indexes aligned
    # so the stored sentence is the original wording.
    cleaned = NOT_NUMBER_RE.sub(_blank, RANGE_RE.sub(_blank, text))
    found = {"gonads": set(), "teeth": set(), "stomachs": set(), "sentences": []}
    for match in NOUN_RE.finditer(cleaned):
        number = nearest_count(cleaned, match.start())
        if number is None:
            continue
        left = text.rfind(".", 0, match.start())
        right = text.find(".", match.end())
        sentence = text[left + 1: right if right != -1 else match.end() + 80].strip()
        if drop_regular_urchin_asides and re.search(r"regular urchins?", sentence, re.I):
            if not re.search(r"clypeasteroid|irregular|Mellita", sentence, re.I):
                continue
        key = noun_key(match.group(1))
        found[key].add(number)
        found["sentences"].append({"sentence": sentence[:400], "counts": [{key: number}]})
    return found


def species_label(slug, text):
    if slug == "mellita":
        m = re.search(r"Mellita\s+[a-z]+", text)
        return (m.group(0) if m else "Mellita"), "irregular"
    if slug == "digimorph":
        m = re.search(r"Encope\s+[a-z]+", text)
        return (m.group(0) if m else "Encope michelini"), "irregular"
    m = re.search(r"Strongylocentrotus\s+purpuratus", text)
    return (m.group(0) if m else "sea urchin"), "regular"


def main():
    os.makedirs(DATA, exist_ok=True)
    files = []
    rows = []
    for slug, url in PAGES:
        meta = fetch(url, os.path.join(DATA, f"{slug}.html"), timeout=90)
        meta["label"] = slug
        files.append(meta)
        text = strip_html(open(os.path.join(DATA, f"{slug}.html"), encoding="utf-8", errors="replace").read())
        name, group = species_label(slug, text)
        counts = extract(text, drop_regular_urchin_asides=(slug == "mellita"))
        rows.append({
            "source": slug,
            "species": name,
            "group": group,
            "gonads": sorted(counts["gonads"]),
            "teeth": sorted(counts["teeth"]),
            "stomachs": sorted(counts["stomachs"]),
            "sentences": counts["sentences"][:8],
        })

    nonfive = []
    for row in rows:
        for structure in ("gonads", "teeth", "stomachs"):
            for number in row[structure]:
                if number != 5:
                    nonfive.append({"species": row["species"], "structure": structure, "count": number, "source": row["source"]})
    scored_structures = sum(1 for row in rows for structure in ("gonads", "teeth", "stomachs") if row[structure])
    all_five = scored_structures > 0 and not nonfive and all(
        row["gonads"] == [5] and row["teeth"] == [5] and row["stomachs"] == [5] for row in rows
    )
    groups = {row["group"] for row in rows}
    if nonfive:
        verdict, reason = "refutes", None
    elif all_five and "regular" in groups and "irregular" in groups:
        verdict, reason = "supports", None
    elif scored_structures:
        verdict, reason = "mixed", None
    else:
        verdict, reason = "inconclusive", "not-operationalizable"

    payload = {
        "datasets": [
            {
                "id": "lander-mellita-anatomy",
                "name": "Lander University invertebrate anatomy, Mellita",
                "landing_url": PAGES[0][1],
                "doi": None,
                "version": None,
                "license": None,
                "files": [files[0]],
                "role": "sand-dollar gonad and tooth counts",
            },
            {
                "id": "washington-sea-urchin-anatomy",
                "name": "University of Washington sea-urchin anatomy notes",
                "landing_url": PAGES[1][1],
                "doi": None,
                "version": None,
                "license": None,
                "files": [files[1]],
                "role": "regular urchin gonad, tooth, and stomach counts",
            },
            {
                "id": "digimorph-encope-michelini",
                "name": "DigiMorph Encope michelini",
                "landing_url": PAGES[2][1],
                "doi": None,
                "version": None,
                "license": None,
                "files": [files[2]],
                "role": "sand-dollar lantern tooth count",
            },
        ],
        "method": (
            "Explicit integer phrases were read from the full page text: a number word or digit, then "
            "the noun immediately or after up to six other words (gonad, tooth, teeth, or stomach). "
            "A phrase of the form 'two to five' was removed before matching. 'Not five' and a number "
            "in 'Fig. 5' are not counts. Sentences about regular urchins on the Mellita page are not "
            "assigned to the sand dollar. Any count other than five refutes the claim that every sea "
            "urchin has five of each."
        ),
        "measured": {
            "value": len(nonfive),
            "unit": "explicit structure counts other than five",
            "n": len(rows),
            "uncertainty": None,
            "extra": {"pages": rows, "nonfive": nonfive},
        },
        "verdict": verdict,
        "confidence": 0.86 if verdict == "refutes" else 0.5,
        "data_kind": "biological" if verdict != "inconclusive" else "none",
        "headline": (
            "Explicit counts other than five: "
            + "; ".join(f"{item['species']} {item['structure']} {item['count']}" for item in nonfive)
            + "."
            if nonfive
            else f"Non-five counts: {len(nonfive)}."
        ),
        "caveats": [
            "Aristotle's 'stomachs' are scored only where a modern page uses the word stomach. Five radial gut compartments under another name would not be counted.",
            "Sand dollars are irregular echinoids. The claim scope recorded for this id is Echinoidea, so they are included.",
            "Tooth counts of five in the same animals do not restore the conjunction once a gonad or stomach count differs.",
        ],
    }
    if reason:
        payload["reason"] = reason
    write_result(RESULT, load_result(RESULT), payload)
    print(verdict, nonfive)


if __name__ == "__main__":
    main()
