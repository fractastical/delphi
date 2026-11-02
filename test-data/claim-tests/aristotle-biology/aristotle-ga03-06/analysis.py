#!/usr/bin/env python3
"""Unfertilized eggs of hens and geese without a male (aristotle-ga03-06).
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
    ("psu", "https://extension.psu.edu/what-do-i-do-with-all-these-eggs"),
    ("msstate", "https://extension.msstate.edu/publications/choosing-the-right-breed-for-your-backyard-flock"),
    ("kstate", "https://www.asi.k-state.edu/extension/poultry/frequently-asked-questions/general-information.html"),
    ("gallus", "https://animaldiversity.org/accounts/Gallus_gallus/"),
    ("anser", "https://animaldiversity.org/accounts/Anser_anser/"),
]
CHICKEN_RE = re.compile(r"\b(hen|hens|chicken|chickens|rooster|roosters)\b", re.I)
GOOSE_RE = re.compile(r"\b(goose|geese|gander|ganders)\b", re.I)
AFFIRM_RE = re.compile(
    r"without a (?:rooster|male|gander)|"
    r"(?:not necessary|not needed|do not need|don't need|won.?t need)|"
    r"only needed.{0,40}fertil|"
    r"will not be fertile|will not hatch|non-fertile|unfertiliz",
    re.I,
)
DENY_RE = re.compile(r"(?:will not lay|cannot lay|do not lay|no eggs).{0,40}(?:without|unless).{0,20}(?:male|rooster|gander)", re.I)


def classify(sentence):
    chicken = bool(CHICKEN_RE.search(sentence))
    goose = bool(GOOSE_RE.search(sentence))
    affirm = bool(AFFIRM_RE.search(sentence))
    deny = bool(DENY_RE.search(sentence))
    return chicken, goose, affirm, deny


def main():
    os.makedirs(DATA, exist_ok=True)
    files = []
    hits = []
    chicken_affirm = goose_affirm = chicken_deny = goose_deny = False
    for slug, url in PAGES:
        meta = fetch(url, os.path.join(DATA, f"{slug}.html"), timeout=90)
        meta["label"] = slug
        files.append(meta)
        text = strip_html(open(os.path.join(DATA, f"{slug}.html"), encoding="utf-8", errors="replace").read())
        for sentence in sentences(text):
            chicken, goose, affirm, deny = classify(sentence)
            if not ((chicken or goose) and (affirm or deny)):
                continue
            # A poultry sentence that does not name a goose does not count for geese.
            if goose and not GOOSE_RE.search(sentence):
                goose = False
            hits.append({
                "source": slug,
                "chicken": chicken,
                "goose": goose,
                "affirm": affirm,
                "deny": deny,
                "sentence": sentence[:400],
            })
            if chicken and affirm:
                chicken_affirm = True
            if goose and affirm:
                goose_affirm = True
            if chicken and deny:
                chicken_deny = True
            if goose and deny:
                goose_deny = True

    if chicken_deny or goose_deny:
        verdict, reason = "refutes", None
    elif chicken_affirm and goose_affirm:
        verdict, reason = "supports", None
    elif chicken_affirm or goose_affirm:
        verdict, reason = "mixed", None
    else:
        verdict, reason = "inconclusive", "data-unavailable"

    payload = {
        "datasets": [{
            "id": "poultry-extension-and-adw",
            "name": "Extension pages and ADW accounts named in the pre-registration",
            "landing_url": "https://extension.msstate.edu/publications/choosing-the-right-breed-for-your-backyard-flock",
            "doi": None,
            "version": None,
            "license": None,
            "files": files,
            "role": "statements on laying without a male",
        }],
        "method": (
            "Each planned page was fetched and split into sentences. A chicken sentence names a hen, "
            "chicken, or rooster. A goose sentence names a goose or a gander. Affirmation is a statement "
            "that a male is not required, is needed only for fertile eggs, or that eggs laid without a "
            "male are infertile or will not hatch. Both species must be affirmed to support."
        ),
        "measured": {
            "value": int(chicken_affirm) + int(goose_affirm),
            "unit": "species (hen, goose) with an affirmation that females lay without a male",
            "n": 2,
            "uncertainty": None,
            "extra": {
                "chicken_affirm": chicken_affirm,
                "goose_affirm": goose_affirm,
                "chicken_deny": chicken_deny,
                "goose_deny": goose_deny,
                "sentences": hits,
            },
        },
        "verdict": verdict,
        "confidence": {"supports": 0.8, "mixed": 0.78, "refutes": 0.7, "inconclusive": 0.4}[verdict],
        "data_kind": "biological" if verdict != "inconclusive" else "none",
        "headline": (
            "Hens are described as laying infertile eggs without a rooster, and none of the fetched pages says this of geese."
            if verdict == "mixed" and chicken_affirm and not goose_affirm
            else f"Hen affirmation {chicken_affirm}, goose affirmation {goose_affirm}."
        ),
        "caveats": [
            "The Penn State URL returned a section index without the laying-without-a-rooster paragraph that search snippets had quoted. Only the fetched text was scored.",
            "A sentence that says roosters are unnecessary does not count for geese unless it names a goose or a gander.",
            "Sperm stored from an earlier mating can fertilize later eggs. It does not explain an egg the source calls infertile. The pages do not explicitly say the hens had never met a male.",
        ],
    }
    if reason:
        payload["reason"] = reason
    write_result(RESULT, load_result(RESULT), payload)
    print(verdict, chicken_affirm, goose_affirm, len(hits))


if __name__ == "__main__":
    main()
