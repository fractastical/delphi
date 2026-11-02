#!/usr/bin/env python3
"""aristotle-ha01-22: does the heart of humans and large mammals have three cavities?

Re-run: python3 analysis.py
Fetches the pre-registered open texts into ./data (gitignored).
"""
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphi-claim-tests/1.0 (aristotle-ha01-22)"}
GROUPS = {
    "openstax_tradition": [
        "https://openstax.org/books/anatomy-and-physiology-2e/pages/19-1-heart-anatomy",
        "https://opentext.uoregon.edu/animalphysiology/chapter/6-3-mammalian-heart-and-blood-vessels/",
        "https://organismalbio.biosci.gatech.edu/nutrition-transport-and-homeostasis/the-mammalian-cardiac-cycle/",
    ],
    "wikibooks_animal_heart": [
        "https://en.wikibooks.org/wiki/Anatomy_and_Physiology_of_Animals/Cardiovascular_System/The_Heart",
    ],
    "umn_ungulate_dissection": [
        "https://pressbooks.umn.edu/ungulateanatomylabguide/chapter/part-5-heart-and-major-vessels/",
    ],
    "mgccc_cow_heart_chambers": [
        "https://mgccc.edu/learning_lab/science/heart2/tsld026.htm",
    ],
}
CHAMBERS = ("right atrium", "left atrium", "right ventricle", "left ventricle")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url):
    DATA.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-")[:80]
    dest = DATA / f"{slug}.html"
    meta_path = dest.with_suffix(".meta.json")
    if dest.exists() and dest.stat().st_size > 0 and meta_path.exists():
        return json.loads(meta_path.read_text()), dest.read_text(errors="replace")
    try:
        r = requests.get(url, timeout=90, headers=UA)
        r.raise_for_status()
    except requests.RequestException as exc:
        meta = {
            "download_url": None,
            "requested_url": url,
            "retrieved_at": now(),
            "byte_size": 0,
            "sha256": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
        # Do not cache a failed fetch as an empty page. The next run retries it.
        return meta, ""
    meta = {
        "download_url": r.url,
        "requested_url": url,
        "retrieved_at": now(),
        "byte_size": len(r.content),
        "sha256": hashlib.sha256(r.content).hexdigest(),
    }
    dest.write_bytes(r.content)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return meta, r.text


def html_text(raw):
    raw = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style.*?>.*?</style>", " ", raw)
    raw = re.sub(r"(?i)</(p|div|li|h[1-6]|tr)>", "\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    return re.sub(r"\n{2,}", "\n", raw)


def sentence_votes(text):
    """Return stated counts whose sentence is about a mammal, human, horse, or cow, not only a fish, amphibian, or reptile."""
    votes = []
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    for s in chunks:
        low = s.lower()
        if not re.search(r"chamber|cavit", low):
            continue
        nonmammal = bool(re.search(r"\b(fish|fishes|amphibian|reptile|shark)\b", low))
        mammal = bool(re.search(r"\b(mammal|mammals|mammalian|human|humans|horse|horses|pony|cow|cows|calf|cattle|ungulate|ox)\b", low))
        if nonmammal and not mammal:
            continue
        found = set()
        if re.search(r"\bfour[-\s]chamber|\b4[-\s]chamber|\bfour chambers\b|\b4 chambers\b", low):
            found.add(4)
        if re.search(r"\bthree[-\s]chamber|\b3[-\s]chamber|\bthree chambers\b|\b3 chambers\b|\bthree cavities\b", low):
            found.add(3)
        if found:
            votes.append({"sentence": s.strip()[:400], "counts": sorted(found), "mammal_word": mammal})
    return votes


def named_chambers(text):
    low = text.lower()
    found = []
    if re.search(r"right atrium|right auricle", low):
        found.append("right atrium")
    if re.search(r"left atrium|left auricle", low):
        found.append("left atrium")
    if "right ventricle" in low:
        found.append("right ventricle")
    if "left ventricle" in low:
        found.append("left ventricle")
    if re.search(r"two atria|both atria|left and right atria|right and left atria", low):
        for name in ("right atrium", "left atrium"):
            if name not in found:
                found.append(name)
    return found


def code_page(text, url):
    votes = sentence_votes(text)
    stated = sorted({c for v in votes for c in v["counts"]})
    # A page whose subject is the mammalian, human, ungulate, or cow heart can supply a
    # four-count from the page even when the sentence that states it omitted the taxon word.
    # A three-count is never taken from the raw page: amphibian hearts are often on the same
    # page, and only a mammal sentence (above) may vote for three.
    page_subject = bool(re.search(r"mammal|human|ungulate|cow heart|pony|heart anatomy", text[:1500], re.I)) or any(
        k in url for k in ("mammalian", "ungulate", "heart2", "19-1-heart", "The_Heart")
    )
    if page_subject and 4 not in stated and re.search(r"\bfour[-\s]chamber|\bfour chambers\b|\b4 chambers\b", text, re.I):
        stated = sorted(set(stated) | {4})
    names = named_chambers(text)
    named_count = len(names) if len(names) >= 3 else None
    clean = None
    discordant = False
    if len(stated) == 1:
        clean = stated[0]
        if named_count is not None and named_count != clean:
            discordant = True
            clean = None
    elif len(stated) > 1:
        discordant = True
    elif named_count is not None:
        clean = named_count
    size_sentence = None
    for s in re.split(r"(?<=[.!?])\s+", text):
        low = s.lower()
        if re.search(r"right", low) and re.search(r"largest|larger", low) and re.search(r"left", low) and re.search(r"smallest|smaller", low) and re.search(r"cavit|chamber", low):
            size_sentence = s.strip()[:400]
            break
    return {
        "url": url,
        "stated_counts": stated,
        "named_chambers": names,
        "clean_count": clean,
        "discordant": discordant,
        "size_sentence": size_sentence,
        "vote_sentences": votes[:8],
        "text_chars": len(text),
    }


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    pages = []
    files = []
    for group, urls in GROUPS.items():
        for url in urls:
            meta, raw = fetch(url)
            if meta.get("error"):
                files.append(meta)
                pages.append({
                    "url": url,
                    "group": group,
                    "error": meta["error"],
                    "clean_count": None,
                    "discordant": False,
                    "stated_counts": [],
                    "named_chambers": [],
                    "text_chars": 0,
                    "size_sentence": None,
                    "openstax_adapted": False,
                    "file": {k: meta[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256", "error")},
                })
                continue
            text = html_text(raw)
            coded = code_page(text, url)
            coded["openstax_adapted"] = "adapted from openstax" in text.lower()
            coded["group"] = group
            coded["file"] = {k: meta[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}
            pages.append(coded)
            files.append(meta)

    # Wikibooks joins OpenStax if it says so.
    group_of = {}
    for p in pages:
        g = p["group"]
        if g == "wikibooks_animal_heart" and p.get("openstax_adapted"):
            g = "openstax_tradition"
        group_of.setdefault(g, []).append(p)

    group_votes = {}
    for g, plist in group_of.items():
        counts = sorted({p["clean_count"] for p in plist if p["clean_count"] is not None and not p["discordant"]})
        # A discordant page does not vote. If the remaining pages agree, that is the group vote.
        if len(counts) == 1:
            group_votes[g] = counts[0]
        elif len(counts) > 1:
            group_votes[g] = "discordant"
        else:
            group_votes[g] = None

    enumerating = {g: v for g, v in group_votes.items() if isinstance(v, int)}
    discordant_groups = [g for g, v in group_votes.items() if v == "discordant"]
    size_hits = [p["size_sentence"] for p in pages if p["size_sentence"]]
    values = set(enumerating.values())
    if len(enumerating) >= 2 and values == {3} and size_hits:
        verdict, confidence = "supports", 0.60
        reason = None
    elif len(enumerating) >= 2 and values and 3 not in values:
        verdict, confidence = "refutes", 0.80
        reason = None
    elif len(enumerating) >= 2 and values == {3} and not size_hits:
        verdict, confidence = "mixed", 0.45
        reason = None
    elif discordant_groups or (values and len(values) > 1):
        verdict, confidence = "mixed", 0.45
        reason = None
    elif len(enumerating) == 1:
        verdict, confidence = "mixed", 0.45
        reason = None
    else:
        verdict, confidence = "inconclusive", 0.55
        reason = "data-unavailable"

    # The pre-registered refutation is "a count other than 3". A mix of 4 and something else
    # that is still not 3 is already handled. If some groups say 4 and none say 3, refutes.
    measured = {
        "value": (enumerating.get("openstax_tradition") if isinstance(enumerating.get("openstax_tradition"), int) else (next(iter(values)) if len(values) == 1 else None)),
        "unit": "blood-filled chambers (atria and ventricles) enumerated for the mammalian heart",
        "n": len(enumerating),
        "uncertainty": "one vote per independent text group; OpenStax-derived pages count once",
        "extra": {
            "group_votes": group_votes,
            "enumerating_groups": enumerating,
            "pages": [
                {k: p[k] for k in ("group", "url", "clean_count", "discordant", "stated_counts", "named_chambers", "text_chars")}
                for p in pages
            ],
            "size_order_sentences": size_hits[:4],
        },
    }
    (DERIVED / "votes.json").write_text(json.dumps({"pages": pages, "group_votes": group_votes, "measured": measured}, indent=2) + "\n")
    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = confidence
    result["data_kind"] = "biological" if any(p["text_chars"] > 500 for p in pages) else "none"
    if reason:
        result["reason"] = reason
    result["datasets"] = [{
        "id": "open-mammal-heart-anatomy-texts",
        "name": "Open texts on the mammalian, human, and ungulate heart",
        "landing_url": "https://opentext.uoregon.edu/animalphysiology/chapter/6-3-mammalian-heart-and-blood-vessels/",
        "doi": None,
        "version": "pages retrieved " + now()[:10],
        "license": "mixed open educational texts (OpenStax CC BY, university pressbooks, Wikibooks)",
        "files": [
            {k: m[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256") if m.get(k) is not None}
            | {"requested_url": m["requested_url"]}
            | ({"error": m["error"]} if m.get("error") else {})
            for m in files
        ],
        "role": "enumeration of adult heart chambers in humans and large mammals",
    }]
    result["method"] = (
        "Fetched each pre-registered page, stripped the markup, and recorded stated chamber counts in sentences "
        "about mammals, humans, horses, or cattle, ignoring sentences that assign a count only to fish, amphibians, "
        "or reptiles. Named right and left atria and ventricles, mapping auricle to the atrium of the same side. "
        "Pages adapted from OpenStax vote as one group. A group vote is the agreed clean count. The claim's size "
        "order is recorded when a sentence ranks cavities, and is required only for a support."
    )
    result["measured"] = measured
    if verdict == "refutes":
        headline = "The adult mammalian heart is described with four chambers, not the three cavities in the claim."
    elif verdict == "supports":
        headline = "The texts enumerate three heart cavities and rank the right one largest and the left one smallest."
    elif verdict == "mixed":
        headline = "The texts do not agree on a count of three cavities with the claimed size order."
    else:
        headline = "The fetched pages do not enumerate the chambers of the mammalian heart."
    result["results_summary"] = [headline]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "votes": group_votes, "confidence": confidence}, indent=2))


if __name__ == "__main__":
    main()
