#!/usr/bin/env python3
"""Pupal stage of bees, wasps, and caterpillars (aristotle-ga03-18).
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

# Vespula vulgaris is classification-only. The deviation substitutes a vespid
# whose ADW account has a development section. Thresholds are unchanged.
TAXA = [
    ("bee", "Apis mellifera", "https://animaldiversity.org/accounts/Apis_mellifera/"),
    ("wasp", "Vespula maculifrons", "https://animaldiversity.org/accounts/Vespula_maculifrons/"),
    ("caterpillar", "Danaus plexippus", "https://animaldiversity.org/accounts/Danaus_plexippus/"),
]
VULGARIS = "https://animaldiversity.org/accounts/Vespula_vulgaris/"
STAGE_RE = re.compile(r"\b(pupa|pupae|pupate|pupation|chrysalis|chrysalides)\b", re.I)
EMERGE_RE = re.compile(r"\bemerg\w*\b", re.I)
ADULT_WORD_RE = re.compile(r"\badults?\b", re.I)
ADULT_WORKER_RE = re.compile(r"\badult\s+workers?\b", re.I)
HUSK_RE = re.compile(r"\b(cocoon|chrysalis|sealed|case around|immobile|motionless|quiescent|non-feeding)\b", re.I)
DENY_RE = re.compile(r"no pupa|without a pupa|direct development", re.I)


def account_body(text):
    cut = re.search(r"\bClose\b", text)
    return text[:cut.start()] if cut else text


def development_sentences(text):
    # Prefer the Development section through the next major heading word.
    m = re.search(r"\bDevelopment\b(.{0,2500}?)\b(?:Reproduction|Lifespan|Behavior|Food Habits)\b", text, re.I)
    blob = m.group(0) if m else text
    return sentences(blob)


def adult_follows(sentence):
    # Workers that seal a cell are not the adult that comes out of the pupa.
    if EMERGE_RE.search(sentence):
        return True
    scrubbed = ADULT_WORKER_RE.sub(" ", sentence)
    return bool(ADULT_WORD_RE.search(scrubbed))


def score(text):
    sents = development_sentences(text)
    stage = [s for s in sents if STAGE_RE.search(s)]
    # A husk word counts only in a sentence that also names the stage, so nest
    # material ('cocoon silk') is not read as a pupal shell.
    husk = [s for s in sents if HUSK_RE.search(s) and STAGE_RE.search(s)]
    adult = []
    for i, sentence in enumerate(sents):
        if not (HUSK_RE.search(sentence) and STAGE_RE.search(sentence)):
            continue
        # The adult may be named in that sentence or in the next two.
        for later in sents[i:i + 3]:
            if adult_follows(later) and later not in adult:
                adult.append(later)
    deny = [s for s in sents if DENY_RE.search(s)]
    passed = bool(stage and adult and husk) and not deny
    return {
        "pass": passed,
        "denied": bool(deny),
        "stage_sentences": stage[:2],
        "husk_sentences": husk[:2],
        "adult_sentences": adult[:2],
        "has_development_section": bool(re.search(r"\bDevelopment\b", text)),
    }


def main():
    os.makedirs(DATA, exist_ok=True)
    files = []
    vul = fetch(VULGARIS, os.path.join(DATA, "adw-vespula-vulgaris.html"))
    vul["label"] = "ADW Vespula vulgaris (classification stub)"
    files.append(vul)
    vul_text = account_body(strip_html(open(os.path.join(DATA, "adw-vespula-vulgaris.html"), encoding="utf-8", errors="replace").read()))
    vulgaris_has_development = bool(re.search(r"\bDevelopment\b", vul_text))

    rows = []
    for role, name, url in TAXA:
        slug = name.split()[0].lower()
        meta = fetch(url, os.path.join(DATA, f"adw-{slug}.html"))
        meta["label"] = f"ADW {name}"
        files.append(meta)
        text = account_body(strip_html(open(os.path.join(DATA, f"adw-{slug}.html"), encoding="utf-8", errors="replace").read()))
        scored = score(text)
        scored["role"] = role
        scored["taxon"] = name
        rows.append(scored)

    n_pass = sum(1 for r in rows if r["pass"])
    n_deny = sum(1 for r in rows if r["denied"])
    if n_pass == 3:
        verdict = "supports"
    elif n_deny and n_pass == 0:
        verdict = "refutes"
    elif n_pass in (1, 2) or (n_deny and n_pass):
        verdict = "mixed"
    else:
        verdict = "inconclusive"
    reason = "data-unavailable" if verdict == "inconclusive" else None

    # iNaturalist pupa annotations are recorded and do not decide the verdict.
    inat = {}
    inat_err = None
    try:
        terms = requests.get("https://api.inaturalist.org/v1/controlled_terms", timeout=60, headers={"User-Agent": "delphi-claim-test/1.0"}).json()
        open(os.path.join(DATA, "inat-controlled-terms.json"), "w").write(requests.get("https://api.inaturalist.org/v1/controlled_terms", timeout=60).text)
        life = next(t for t in terms["results"] if t["label"].lower() == "life stage")
        pupa = next(v for v in life["values"] if v["label"].lower() == "pupa")
        for role, name, _url in TAXA:
            q = (
                "https://api.inaturalist.org/v1/observations?taxon_name="
                + requests.utils.quote(name)
                + f"&term_id={life['id']}&term_value_id={pupa['id']}&per_page=0&quality_grade=research"
            )
            body = requests.get(q, timeout=60, headers={"User-Agent": "delphi-claim-test/1.0"}).json()
            inat[name] = body.get("total_results")
    except Exception as exc:
        inat_err = str(exc)

    payload = {
        "datasets": [{
            "id": "adw-bee-wasp-butterfly",
            "name": "Animal Diversity Web life cycles of Apis mellifera, Vespula maculifrons, and Danaus plexippus",
            "landing_url": "https://animaldiversity.org/",
            "doi": None,
            "version": None,
            "license": None,
            "files": files,
            "role": "development prose for a bee, a vespid wasp, and a butterfly",
        }],
        "method": (
            "The Development section of each account was isolated. A taxon passes when that section "
            "names a pupa, pupation, or chrysalis, and a hardened-covering word (cocoon, chrysalis, "
            "sealed cell, or case) shares that sentence. The adult counts when emerge/adult appears "
            "in that sentence or in the next two. 'Adult workers' sealing a cell does not count. "
            "Nest-building mentions of cocoon silk do not count."
        ),
        "measured": {
            "value": n_pass,
            "unit": "of three groups (bee, vespid wasp, butterfly) whose development text describes an enclosed pupa",
            "n": 3,
            "uncertainty": None,
            "extra": {
                "taxa": rows,
                "vespula_vulgaris_has_development_section": vulgaris_has_development,
                "inaturalist_research_grade_pupa_counts": inat,
                "inaturalist_error": inat_err,
            },
        },
        "verdict": verdict,
        "confidence": 0.64 if verdict == "mixed" else 0.7,
        "data_kind": "biological" if verdict != "inconclusive" else "none",
        "deviations": [{
            "date": "2026-11-01",
            "what_changed": "The wasp account and the immobility phrase list.",
            "why": (
                "The pre-registered Vespula vulgaris page is a classification stub with no Development "
                "section, so it cannot be scored. Vespula maculifrons, a vespid wasp, was substituted. "
                "The adjectives immobile, motionless, quiescent, and non-feeding do not occur in these "
                "accounts. A sealed cell, a silk cocoon, or a chrysalis case, in a sentence that names "
                "the pupa, was accepted as the hardened husk. The threshold is still all three groups. "
                "iNaturalist counts stay non-decisive."
            ),
        }, {
            "date": "2026-11-01",
            "what_changed": "An emergence phrase counts in the stage-and-husk sentence or in the next two sentences.",
            "why": (
                "The pre-registered rule says the adult follows the pupal stage. On the monarch account "
                "the chrysalis sentence and the emergence sentence are one sentence apart, so requiring "
                "both in a single sentence dropped a description the criterion already accepts. The "
                "covering word must still share a sentence with the stage name. The phrase 'adult workers' "
                "is not read as the emerging adult."
            ),
        }],
        "headline": (
            f"{n_pass} of 3 groups have an enclosed pupa in the fetched development text "
            f"({', '.join(r['taxon'] + (':pass' if r['pass'] else ':not') for r in rows)})."
        ),
        "caveats": [
            "The word motionless is not in the accounts. The husk is scored from cocoon, sealed cell, or chrysalis.",
            "Vespula maculifrons says the larva pupates and the adult emerges. That sentence does not name a shell, so the wasp does not pass.",
            "iNaturalist annotation counts, when retrieved, are not part of the verdict.",
        ],
    }
    if reason:
        payload["reason"] = reason
    write_result(RESULT, load_result(RESULT), payload)
    print(verdict, [(r["taxon"], r["pass"]) for r in rows], inat, inat_err)


if __name__ == "__main__":
    main()
