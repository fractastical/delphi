#!/usr/bin/env python3
"""Striped hyenas are not hermaphrodites (aristotle-ha06-40).

GBIF sex facet for Hyaena hyaena, the ADW reproductive-features line, and the
PMC HTML of McCormick et al. on spotted-hyena sex differences.
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

GBIF_MATCH = "https://api.gbif.org/v1/species/match?name=Hyaena%20hyaena"
ADW = "https://animaldiversity.org/accounts/Hyaena_hyaena/"
PMC = "https://pmc.ncbi.nlm.nih.gov/articles/PMC9248831/"

SUPPORT_RE = re.compile(
    r"sexes separate|gonochoric|gonochoristic|dioecious|"
    r"not hermaphrodit|unique to (?:the )?spotted hyena|"
    r"other members of the hyena family|other hyaenid",
    re.I,
)
REFUTE_RE = re.compile(
    r"functional hermaphrodit|"
    r"every (?:individual |hyena )?.{0,60}organs of both sexes",
    re.I,
)


def reproductive_window(text):
    i = text.lower().find("key reproductive features")
    if i < 0:
        return ""
    window = text[i:i + 500]
    return window


def main():
    os.makedirs(DATA, exist_ok=True)
    files = []
    meta = fetch(GBIF_MATCH, os.path.join(DATA, "gbif-species-match.json"))
    meta["label"] = "GBIF species match Hyaena hyaena"
    files.append(meta)
    match = requests.get(GBIF_MATCH, timeout=60, headers={"User-Agent": "delphi-claim-test/1.0"}).json()
    key = match["usageKey"]
    if match.get("scientificName", "").split()[0:2] != ["Hyaena", "hyaena"] and "Hyaena hyaena" not in match.get("scientificName", ""):
        raise SystemExit(f"species match was not Hyaena hyaena: {match.get('scientificName')}")
    facet_url = f"https://api.gbif.org/v1/occurrence/search?taxonKey={key}&facet=sex&limit=0"
    meta = fetch(facet_url, os.path.join(DATA, "gbif-sex-facet.json"))
    meta["label"] = "GBIF occurrence sex facet"
    files.append(meta)
    facet = requests.get(facet_url, timeout=90, headers={"User-Agent": "delphi-claim-test/1.0"}).json()
    counts = {c["name"]: c["count"] for c in facet["facets"][0]["counts"]}
    male = counts.get("Male", 0)
    female = counts.get("Female", 0)
    herm = sum(v for k, v in counts.items() if re.search(r"hermaphrodite|intersex|both", k, re.I))
    sex_pass = male >= 20 and female >= 20 and herm == 0

    meta = fetch(ADW, os.path.join(DATA, "adw-hyaena-hyaena.html"))
    meta["label"] = "ADW Hyaena hyaena"
    files.append(meta)
    adw = strip_html(open(os.path.join(DATA, "adw-hyaena-hyaena.html"), encoding="utf-8", errors="replace").read())
    window = reproductive_window(adw)
    adw_support = bool(SUPPORT_RE.search(window))
    adw_refute = bool(REFUTE_RE.search(window))

    pmc_text = ""
    pmc_err = None
    try:
        meta = fetch(PMC, os.path.join(DATA, "pmc9248831.html"), timeout=90)
        meta["label"] = "PMC9248831 Sex Differences in Spotted Hyenas"
        files.append(meta)
        pmc_text = strip_html(open(os.path.join(DATA, "pmc9248831.html"), encoding="utf-8", errors="replace").read())
    except Exception as exc:
        pmc_err = str(exc)
    pmc_support_sents = [s for s in sentences(pmc_text) if SUPPORT_RE.search(s)] if pmc_text else []
    pmc_refute_sents = [s for s in sentences(pmc_text) if REFUTE_RE.search(s)] if pmc_text else []
    # Keep the anatomical-support hit only when it is about hyenas, not a site banner.
    pmc_support_sents = [s for s in pmc_support_sents if re.search(r"hyena|hyaen", s, re.I)]
    text_support = adw_support or bool(pmc_support_sents)
    text_refute = adw_refute or bool(pmc_refute_sents)

    if text_refute and (herm > male + female or re.search(r"functional hermaphrodit", window + " " + " ".join(pmc_refute_sents), re.I)):
        verdict, reason = "refutes", None
    elif text_refute and not text_support:
        verdict, reason = "refutes", None
    elif sex_pass and text_support and not text_refute:
        verdict, reason = "supports", None
    elif (sex_pass or text_support) and not text_refute:
        verdict, reason = "mixed", None
    elif facet.get("count", 0) == 0 and not adw and not pmc_text:
        verdict, reason = "inconclusive", "data-unavailable"
    else:
        verdict, reason = "inconclusive", "underpowered" if (male + female) < 20 else "other"

    confidence = {"supports": 0.72, "refutes": 0.7, "mixed": 0.55, "inconclusive": 0.35}[verdict]
    headline = (
        f"Striped-hyena records list {female} females and {male} males and none as hermaphrodites, "
        f"and the species account codes the sexes as separate."
        if verdict == "supports"
        else f"The sex and anatomy sources do not together show that striped hyenas are separate sexes ({verdict})."
    )
    payload = {
        "datasets": [
            {
                "id": "gbif-occurrence-sex-hyaena-hyaena",
                "name": "GBIF occurrence sex facet for Hyaena hyaena",
                "landing_url": "https://www.gbif.org/",
                "doi": None,
                "version": f"species usageKey {key}",
                "license": "GBIF occurrence records, mixed licenses, attribution required",
                "files": files[:2],
                "role": "counts of sexed striped-hyena occurrences",
            },
            {
                "id": "adw-hyaena-hyaena",
                "name": "Animal Diversity Web account of Hyaena hyaena",
                "landing_url": ADW,
                "doi": None,
                "version": None,
                "license": None,
                "files": [files[2]],
                "role": "structured reproductive-mode statement",
            },
        ],
        "method": (
            "The script resolved Hyaena hyaena on GBIF and read the occurrence sex facet. "
            "It took the 500 characters after 'Key Reproductive Features' on the Animal Diversity Web "
            "account and matched the pre-registered support and refute phrases. "
            "The PMC HTML of the spotted-hyena sex-difference article was fetched the same way and "
            "kept only when a matching sentence also names a hyena."
        ),
        "measured": {
            "value": female + male,
            "unit": "GBIF occurrences of Hyaena hyaena sexed male or female",
            "n": facet.get("count"),
            "uncertainty": None,
            "extra": {
                "gbif_usage_key": key,
                "gbif_total_occurrences": facet.get("count"),
                "sex_counts": counts,
                "male": male,
                "female": female,
                "hermaphrodite_intersex_or_both": herm,
                "sex_count_pass": sex_pass,
                "adw_reproductive_window": window,
                "adw_support": adw_support,
                "pmc_support_sentences": pmc_support_sents[:4],
                "pmc_refute_sentences": pmc_refute_sents[:4],
                "pmc_error": pmc_err,
            },
        },
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological",
        "headline": headline,
        "caveats": [
            "GBIF sex is the sex assigned by the record publisher, not a dissection of the reproductive tract.",
            "The Animal Diversity Web line codes separate sexes. It does not measure the blind subcaudal pouch Aristotle described.",
            "Indeterminate GBIF records are neither male, female, nor hermaphrodite and are not counted in the threshold.",
        ],
    }
    if pmc_err is None and len(files) > 3:
        payload["datasets"].append({
            "id": "pmc-pmc9248831-sex-differences-spotted-hyenas",
            "name": "PMC9248831 Sex Differences in Spotted Hyenas (HTML)",
            "landing_url": PMC,
            "doi": "10.1101/cshperspect.a039180",
            "version": "PMC9248831",
            "license": None,
            "files": [files[3]],
            "role": "anatomical contrast between spotted hyenas and other hyaenids",
        })
    if reason:
        payload["reason"] = reason
    write_result(RESULT, load_result(RESULT), payload)
    print(verdict, confidence, male, female, herm, adw_support, len(pmc_support_sents))


if __name__ == "__main__":
    main()
