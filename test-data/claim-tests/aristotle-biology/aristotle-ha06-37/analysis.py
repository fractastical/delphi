#!/usr/bin/env python3
"""Test aristotle-ha06-37 against Europe PMC title-and-abstract records.

Re-run from this directory: python3 analysis.py
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

QUERY = (
    '("female mule" OR "fertile mule" OR "mule mare" OR "she-mule" OR "female hinny" OR "fertile hinny" '
    'OR "offspring of a female mule" OR "offspring of a hinny" OR "hinny and her offspring" '
    'OR "recipient mule" OR "recipient mules") '
    'AND (foal OR pregnan* OR parturition OR abort* OR impregnat* OR conception OR offspring OR birth OR foaled OR foaling) '
    'NOT (duck* OR "mule deer" OR Odocoileus OR Cairina OR Anas OR Muscovy)'
)
SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
DAM_MULE = re.compile(r"female mules?|fertile mules?|mule mares?|she-mules?|pregnant mules?|offspring of a female mule|recipient mules?|mule dams?", re.I)
DAM_HINNY = re.compile(r"female hinn(?:y|ies)|fertile hinn(?:y|ies)|offspring of a hinny|hinny and her", re.I)
BIRTH = re.compile(r"\b(?:foals?|foaled|foaling|offspring|parturition|gave birth|live births?|born)\b", re.I)
BIRTH_NEG = re.compile(r"did not|failed to|without (?:giving )?birth|no (?:live )?(?:foal|offspring)|unable to|infertil|usually infertile|steril", re.I)
PREG = re.compile(r"pregnan|conception|conceived|impregnat|ovulat|estrous|oestrus", re.I)
FAIL = re.compile(r"abort|resorb|failed to give birth|did not give birth|without giving birth|not followed by|embryonic loss|pregnancy loss|embryonic death", re.I)
NOISE = re.compile(r"mule deer|odocoileus|mule duck|cairina|anas platyrhynchos|muscovy", re.I)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def clean(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


def sentences(text):
    return re.split(r"(?<=[.])\s+", text)


def classify(title, abstract):
    text = f"{title}. {abstract}".strip()
    if NOISE.search(text):
        return None
    mule = bool(DAM_MULE.search(text))
    hinny = bool(DAM_HINNY.search(text))
    if not mule and not hinny:
        return None
    live = []
    nonbirth = []
    for sentence in sentences(text):
        if BIRTH.search(sentence) and not BIRTH_NEG.search(sentence):
            live.append(sentence)
        if PREG.search(sentence) and FAIL.search(sentence):
            nonbirth.append(sentence)
    if not live and not nonbirth:
        return None
    return {
        "female_mule_dam": mule,
        "female_hinny_dam": hinny,
        "live_birth": bool(live),
        "nonbirth_pregnancy": bool(nonbirth),
        "live_sentence": live[0][:400] if live else None,
        "nonbirth_sentence": nonbirth[0][:400] if nonbirth else None,
    }


def main():
    records = []
    blobs = []
    cursor = "*"
    seen = set()
    while cursor and cursor not in seen:
        seen.add(cursor)
        r = requests.get(SEARCH, params={"query": QUERY, "format": "json", "pageSize": 100, "resultType": "core", "cursorMark": cursor}, timeout=120, headers={"User-Agent": "DelphiClaimTest/1.0"})
        r.raise_for_status()
        blobs.append(r.content)
        data = r.json()
        records.extend(data.get("resultList", {}).get("result", []))
        nxt = data.get("nextCursorMark")
        if not nxt or nxt == cursor:
            break
        cursor = nxt
        if len(blobs) > 10:
            break
    payload = b"".join(blobs)
    file_rec = {
        "download_url": SEARCH + "?query=" + requests.utils.quote(QUERY) + "&format=json&resultType=core",
        "retrieved_at": now(),
        "byte_size": len(payload),
        "sha256": sha256(payload),
        "content_type": "application/json",
        "pages": len(blobs),
        "hit_count": None,
    }
    if blobs:
        file_rec["hit_count"] = json.loads(blobs[0]).get("hitCount")

    dedup = {}
    for rec in records:
        key = rec.get("pmid") or rec.get("id")
        if key and key not in dedup:
            dedup[key] = rec
    classified = []
    for key, rec in dedup.items():
        title = clean(rec.get("title"))
        abstract = clean(rec.get("abstractText"))
        label = classify(title, abstract)
        if not label:
            continue
        label.update({
            "id": rec.get("id"),
            "pmid": rec.get("pmid"),
            "year": rec.get("pubYear"),
            "title": title[:300],
            "doi": rec.get("doi"),
        })
        classified.append(label)
    live = [row for row in classified if row["live_birth"]]
    nonbirth = [row for row in classified if row["nonbirth_pregnancy"]]
    reason = None
    if not blobs:
        verdict, reason = "inconclusive", "data-unavailable"
    elif live and not nonbirth:
        verdict = "refutes"
    elif nonbirth and not live:
        verdict = "supports"
    elif live and nonbirth:
        verdict = "mixed"
    else:
        verdict, reason = "inconclusive", "other"

    confidence = 0.72 if verdict in {"refutes", "supports", "mixed"} else 0.4
    measured = {
        "value": len(live),
        "unit": "deduplicated Europe PMC records classified as a live birth to a female mule or female hinny",
        "n": len(classified),
        "uncertainty": "title and abstract only; one paper may be in both classes",
        "extra": {
            "query": QUERY,
            "records_returned": len(records),
            "records_deduplicated": len(dedup),
            "n_live_birth": len(live),
            "n_nonbirth_pregnancy": len(nonbirth),
            "n_female_mule_live": sum(1 for row in live if row["female_mule_dam"]),
            "n_female_hinny_live": sum(1 for row in live if row["female_hinny_dam"]),
            "n_female_mule_nonbirth": sum(1 for row in nonbirth if row["female_mule_dam"]),
            "n_female_hinny_nonbirth": sum(1 for row in nonbirth if row["female_hinny_dam"]),
            "live_records": [{k: row[k] for k in ("id", "pmid", "year", "title", "live_sentence")} for row in live],
            "nonbirth_records": [{k: row[k] for k in ("id", "pmid", "year", "title", "nonbirth_sentence")} for row in nonbirth],
            "verdict_by_rule": verdict,
        },
    }
    json.dump(classified, open(os.path.join(DERIVED, "classified.json"), "w"), indent=2)
    result = json.load(open(os.path.join(HERE, "result.json")))
    result["status"] = "complete"
    result["data_kind"] = "none" if reason == "data-unavailable" else "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    result["confidence"] = confidence
    result["datasets"] = [{
        "id": "europepmc-female-mule-pregnancy",
        "name": "Europe PMC search for female-mule and female-hinny reproductive outcomes",
        "landing_url": "https://europepmc.org/search?query=" + requests.utils.quote(QUERY),
        "doi": None,
        "version": "REST search resultType=core",
        "license": "Europe PMC metadata and abstracts, retrieved from the public API",
        "files": [file_rec],
        "role": "titles and abstracts returned by the pre-registered query",
    }]
    result["method"] = (
        "Europe PMC was searched with a query that requires a female mule, fertile mule, female hinny, or recipient mule, and a reproductive-outcome word, and that excludes mule deer and ducks. "
        "Records were deduplicated by PMID or Europe PMC id. "
        "A live birth is a sentence with foal, offspring, parturition, or birth and without a negation. "
        "A non-birth pregnancy is a sentence that has both a conception or pregnancy term and an abortion, resorption, or failure-to-give-birth term. "
        "The word sterile alone is not a non-birth pregnancy."
    )
    result["measured"] = measured
    result["caveats"] = [
        "Classification uses titles and abstracts, not full texts. A birth reported only in the paper body is missed.",
        "Embryo-transfer foals born to a recipient mule match the pre-registered live-birth pattern and are counted.",
        "Female hinnies are counted, as the pre-registration requires, and are also reported separately.",
        "Papers that only restate sterility, without a pregnancy that failed, are not in the non-birth class.",
    ]
    with open(os.path.join(HERE, "result.json"), "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    json.dump({"verdict": verdict, "n_live": len(live), "n_nonbirth": len(nonbirth)}, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps({"verdict": verdict, "reason": reason, "hit": file_rec["hit_count"], "live": len(live), "nonbirth": len(nonbirth), "titles": [row["title"] for row in classified]}, indent=2))


if __name__ == "__main__":
    main()
