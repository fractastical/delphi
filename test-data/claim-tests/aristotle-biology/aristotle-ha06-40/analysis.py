#!/usr/bin/env python3
"""Code the Animal Diversity Web account of Hyaena hyaena.

Rules are the ones committed in result.json before this page was downloaded.
"""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
URL = "https://animaldiversity.org/accounts/Hyaena_hyaena/"
UA = "delphisci-claim-test/aristotle-ha06-40"

DENIAL = re.compile(
    r"\b(not|n't|myth|false|incorrect|untrue|neither|misconception|mistaken|erroneous)\b",
    re.I,
)
HERM = re.compile(r"hermaphrodit", re.I)
SEPARATE = re.compile(r"gonochor|dioecious|separate sexes", re.I)
BLIND = re.compile(r"blind|pouch|pseudopenis|scent|\bsac\b", re.I)
BLIND_CTX = re.compile(r"tail|anal|genital|female|male|subcaudal", re.I)
REPRO_VOCAB = re.compile(
    r"gonad|penis|vagina|uterus|testis|testes|hermaphrodit|pouch|genital|ovary|vulva|scrotum",
    re.I,
)


def fetch(url, dest):
    DATA.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    raw = urllib.request.urlopen(req, timeout=60).read()
    dest.write_bytes(raw)
    return raw


def file_meta(raw, url):
    return {
        "download_url": url,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def html_to_text(raw):
    html = raw.decode("utf-8", "replace")
    html = re.sub(r"(?is)<script\b.*?</script>", " ", html)
    html = re.sub(r"(?is)<style\b.*?</style>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'")
    html = re.sub(r"&[a-z]+;", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def main():
    raw = fetch(URL, DATA / "hyaena-hyaena.html")
    text = html_to_text(raw)
    sents = sentences(text)
    is_species = bool(re.search(r"Hyaena hyaena", text))
    has_vocab = bool(REPRO_VOCAB.search(text))
    denial_sents = [s for s in sents if HERM.search(s) and DENIAL.search(s)]
    assert_sents = [s for s in sents if HERM.search(s) and not DENIAL.search(s)]
    separate_sents = [s for s in sents if SEPARATE.search(s)]
    male_and_female = bool(re.search(r"\bmales?\b", text, re.I) and re.search(r"\bfemales?\b", text, re.I))
    blind_sents = [s for s in sents if BLIND.search(s) and BLIND_CTX.search(s)]
    separate = bool(separate_sents) or (male_and_female and has_vocab)
    true_herm = bool(assert_sents) and not denial_sents
    blind = bool(blind_sents)

    if not is_species or not has_vocab:
        verdict, reason, confidence = "inconclusive", "not-operationalizable" if is_species else "data-unavailable", 0.4
        if not is_species:
            reason = "data-unavailable"
    elif true_herm:
        verdict, reason, confidence = "refutes", None, 0.7
    elif separate and not true_herm and blind:
        verdict, reason, confidence = "supports", None, 0.6
    elif separate and not true_herm:
        verdict, reason, confidence = "mixed", None, 0.55
    else:
        verdict, reason, confidence = "inconclusive", "not-operationalizable", 0.4

    DERIVED.mkdir(parents=True, exist_ok=True)
    excerpts = {
        "is_hyaena_hyaena": is_species,
        "has_reproductive_vocabulary": has_vocab,
        "separate_sexes": separate,
        "asserts_hermaphroditism": assert_sents,
        "denies_hermaphroditism": denial_sents,
        "separate_sentences": separate_sents,
        "blind_sentences": blind_sents,
        "male_and_female_both_present": male_and_female,
    }
    (DERIVED / "excerpts.json").write_text(json.dumps(excerpts, indent=2) + "\n")

    result = json.loads((HERE / "result.json").read_text())
    result.update({
        "status": "complete",
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological" if verdict != "inconclusive" or reason != "data-unavailable" else "none",
        "method": "Downloaded the Animal Diversity Web account of Hyaena hyaena, reduced the HTML to text, and coded sentences for separate sexes, an assertion or denial of hermaphroditism, and a blind or pouch-like structure in a genital or anal context. The pre-registered three-part rule set the verdict.",
        "measured": {
            "value": int(separate and not true_herm and blind),
            "unit": "1 if separate sexes, no hermaphrodite assertion, and a blind structure were all coded; else 0",
            "n": 1,
            "uncertainty": "one species account, not a specimen series",
            "extra": {
                "separate_sexes": separate,
                "true_hermaphrodite_asserted": true_herm,
                "blind_structure": blind,
                "n_denial_sentences": len(denial_sents),
                "n_assert_sentences": len(assert_sents),
                "n_blind_sentences": len(blind_sents),
            },
        },
        "datasets": [{
            "id": "adw-hyaena-hyaena",
            "name": "Animal Diversity Web account of Hyaena hyaena",
            "landing_url": URL,
            "doi": None,
            "version": "fetched " + dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
            "license": "Animal Diversity Web; page copyright University of Michigan Museum of Zoology. Text was coded, not redistributed.",
            "files": [file_meta(raw, URL)],
            "role": "anatomical and reproductive account of the striped hyena",
        }],
        "results_summary": [
            f"separate_sexes={separate}; hermaphrodite_asserted={true_herm}; blind_structure={blind}.",
            f"Denial sentences: {len(denial_sents)}. Asserting sentences: {len(assert_sents)}. Blind-context sentences: {len(blind_sents)}.",
        ],
    })
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        result.pop("reason", None)
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, reason, confidence)


if __name__ == "__main__":
    main()
