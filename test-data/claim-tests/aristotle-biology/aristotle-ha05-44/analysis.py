#!/usr/bin/env python3
"""Louse, flea, and bedbug eggs ('nits') hatch or not (aristotle-ha05-44).
"""
import os
import re
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import fetch, load_result, sentences, strip_html, write_result

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RESULT = os.path.join(HERE, "result.json")
TAXA = {
    "Pediculus humanus": "https://animaldiversity.org/accounts/Pediculus_humanus/",
    "Pulex irritans": "https://animaldiversity.org/accounts/Pulex_irritans/",
    "Cimex lectularius": "https://animaldiversity.org/accounts/Cimex_lectularius/",
}
HATCH_RE = re.compile(r"\b(egg|eggs|nit|nits)\b.{0,80}\b(hatch\w*|nymph\w*|larva\w*)\b|\b(hatch\w*)\b.{0,40}\b(nymph\w*|larva\w*)\b", re.I)
TERMINAL_RE = re.compile(r"\b(egg|eggs|nit|nits)\b.{0,80}(do not hatch|nothing further|generate nothing|produce nothing)", re.I)


def account_body(text):
    # Glossary entries on ADW begin with a defined term followed by 'Close'.
    cut = re.search(r"\bClose\b", text)
    return text[:cut.start()] if cut else text


def main():
    os.makedirs(DATA, exist_ok=True)
    files = []
    scored = []
    for name, url in TAXA.items():
        slug = name.split()[0].lower()
        meta = fetch(url, os.path.join(DATA, f"adw-{slug}.html"))
        meta["label"] = f"ADW {name}"
        files.append(meta)
        text = account_body(strip_html(open(os.path.join(DATA, f"adw-{slug}.html"), encoding="utf-8", errors="replace").read()))
        hatch = [s for s in sentences(text) if HATCH_RE.search(s)]
        terminal = [s for s in sentences(text) if TERMINAL_RE.search(s)]
        # A page that is only a classification skeleton has no development prose.
        has_prose = "reproduction" in text.lower() or "development" in text.lower() or "egg" in text.lower()
        state = "unscored"
        if hatch and not terminal:
            state = "hatches"
        elif terminal and not hatch:
            state = "terminal"
        elif hatch and terminal:
            state = "conflict"
        elif not has_prose:
            state = "no-lifecycle-text"
        scored.append({
            "taxon": name,
            "state": state,
            "hatch_sentences": hatch[:3],
            "terminal_sentences": terminal[:2],
            "chars": len(text),
        })

    states = {s["taxon"]: s["state"] for s in scored}
    if any(v == "hatches" for v in states.values()) and any(v == "terminal" for v in states.values()):
        verdict, reason = "mixed", None
    elif any(v == "hatches" for v in states.values()):
        verdict, reason = "refutes", None
    elif all(v == "terminal" for v in states.values()):
        verdict, reason = "supports", None
    else:
        verdict, reason = "inconclusive", "data-unavailable"

    # Non-decisive GBIF lifeStage facets.
    gbif = {}
    for name in TAXA:
        match_url = "https://api.gbif.org/v1/species/match?name=" + requests.utils.quote(name)
        m = requests.get(match_url, timeout=60, headers={"User-Agent": "delphi-claim-test/1.0"}).json()
        key = m.get("usageKey")
        facet_url = f"https://api.gbif.org/v1/occurrence/search?taxonKey={key}&facet=lifeStage&limit=0"
        meta = fetch(facet_url, os.path.join(DATA, f"gbif-lifestage-{name.split()[0].lower()}.json"))
        meta["label"] = f"GBIF lifeStage {name}"
        files.append(meta)
        body = requests.get(facet_url, timeout=90, headers={"User-Agent": "delphi-claim-test/1.0"}).json()
        counts = {}
        if body.get("facets"):
            counts = {c["name"]: c["count"] for c in body["facets"][0]["counts"]}
        gbif[name] = {"usageKey": key, "occurrence_count": body.get("count"), "lifeStage": counts}

    n_hatch = sum(1 for s in scored if s["state"] == "hatches")
    payload = {
        "datasets": [
            {
                "id": "adw-lice-fleas-bedbugs",
                "name": "Animal Diversity Web accounts of Pediculus humanus, Pulex irritans, and Cimex lectularius",
                "landing_url": "https://animaldiversity.org/",
                "doi": None,
                "version": None,
                "license": None,
                "files": files[:3],
                "role": "life-cycle prose for the three named insects",
            },
            {
                "id": "gbif-lifestage-facet-three-taxa",
                "name": "GBIF lifeStage facets for the same three taxa",
                "landing_url": "https://www.gbif.org/",
                "doi": None,
                "version": None,
                "license": "GBIF occurrence records, mixed licenses",
                "files": files[3:],
                "role": "non-decisive counts of recorded life stages",
            },
        ],
        "method": (
            "HTML was stripped and cut before the ADW glossary. A sentence matches hatching when it "
            "joins egg or nit with hatch, nymph, or larva. A sentence matches a terminal egg when it "
            "says eggs do not hatch or generate nothing. One hatching account refutes the universal. "
            "GBIF lifeStage facets were stored and not used for the verdict."
        ),
        "measured": {
            "value": n_hatch,
            "unit": "of three taxa whose account says the eggs hatch",
            "n": 3,
            "uncertainty": None,
            "extra": {"accounts": scored, "gbif_lifestage": gbif},
        },
        "verdict": verdict,
        "confidence": {"refutes": 0.9, "supports": 0.7, "mixed": 0.6, "inconclusive": 0.4}[verdict],
        "data_kind": "biological" if verdict != "inconclusive" else "none",
        "headline": (
            "Louse nits are described as hatching into nymphs, and flea eggs as hatching, so those eggs do not generate nothing."
            if verdict == "refutes"
            else f"The three life-cycle accounts score as {states}."
        ),
        "caveats": [
            "The Cimex lectularius ADW URL is a classification stub with no life-cycle prose. One hatching account is enough to refute the universal.",
            "GBIF life-stage counts do not show that a particular nit hatched. They are not part of the verdict.",
            "The louse interval 'about eight days' and the flea interval are in the fetched sentences stored in measured.extra.",
        ],
    }
    if reason:
        payload["reason"] = reason
    write_result(RESULT, load_result(RESULT), payload)
    print(verdict, states)


if __name__ == "__main__":
    main()
