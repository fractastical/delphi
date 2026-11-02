#!/usr/bin/env python3
"""aristotle-ha07-12: is five the largest number of children at one birth?

The decision rule is the one committed in result.json. One human delivery of
six or more, as stated in a Europe PMC title or abstract, refutes it. The
search cannot support the maximum.

    python3 analysis.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html as html_lib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
UA = "delphisci-claim-test/aristotle-ha07-12"
EBI = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
QUERY = (
    "TITLE_ABS:(sextuplets OR septuplets OR octuplets OR nonuplets "
    "OR sextuplet OR septuplet OR octuplet OR nonuplet) "
    "AND (birth OR born OR delivery OR deliveries)"
)
PLURAL = re.compile(r"\b(sextuplets?|septuplets?|octuplets?|nonuplets?)\b", re.I)
HUMAN = re.compile(r"\b(birth|born|delivery|deliveries|infant|infants|baby|babies|mother|mothers|woman|women)\b", re.I)
NEGATION = re.compile(
    r"\b(no|not a|not an|without|never)\s+(sextuplets?|septuplets?|octuplets?|nonuplets?)\b",
    re.I,
)
RANK = {"sextuplet": 6, "septuplet": 7, "octuplet": 8, "nonuplet": 9}


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def plain(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment or "")
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def plurality_of(text: str) -> int | None:
    if not text or NEGATION.search(text) or not HUMAN.search(text):
        return None
    found = [RANK[m.group(1).lower().rstrip("s")] for m in PLURAL.finditer(text)]
    return max(found) if found else None


def sentence_with(text: str) -> str | None:
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if plurality_of(sentence):
            return sentence[:500]
    if plurality_of(text):
        return text[:500]
    return None


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    retrieved = now_utc()
    params = {"query": QUERY, "format": "json", "resultType": "core", "pageSize": "25"}
    url = EBI + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read()
        status = resp.status
    (DATA / "europepmc.json").write_bytes(raw)
    payload = json.loads(raw.decode("utf-8"))
    results = (payload.get("resultList") or {}).get("result") or []
    hits = []
    for row in results:
        title = plain(row.get("title") or "")
        abstract = plain(row.get("abstractText") or "")
        blob = f"{title} {abstract}".strip()
        n = plurality_of(blob)
        if n is None:
            continue
        hits.append({
            "pmid": row.get("pmid"),
            "doi": row.get("doi"),
            "year": row.get("pubYear"),
            "plurality": n,
            "title": title[:300],
            "sentence": sentence_with(abstract or title),
        })
    hits.sort(key=lambda h: (-h["plurality"], h.get("year") or ""))
    if status != 200:
        verdict, reason = "inconclusive", "data-unavailable"
    elif hits:
        verdict, reason = "refutes", None
    else:
        verdict, reason = "inconclusive", "underpowered"
    maximum = max((h["plurality"] for h in hits), default=None)
    confidence = 0.8 if verdict == "refutes" and maximum and maximum >= 6 else (0.35 if reason == "underpowered" else 0.2)
    measured = {
        "value": maximum,
        "unit": "infants at one delivery; the highest plurality named in a matching title or abstract",
        "n": len(hits),
        "uncertainty": "count of matching abstracts in the first 25 search results, not a census of births",
        "extra": {
            "query": QUERY,
            "http_status": status,
            "hit_count_reported": payload.get("hitCount"),
            "results_returned": len(results),
            "matching_hits": hits,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured}, indent=2) + "\n")
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological" if status == 200 else "none"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = confidence
    result["measured"] = measured
    result["datasets"] = [{
        "id": "europepmc-higher-order-human-births",
        "name": "Europe PMC title and abstract search for higher-order human births",
        "landing_url": "https://europepmc.org/",
        "doi": None,
        "version": "query retrieved " + retrieved,
        "license": "Public Europe PMC REST API; each abstract remains under its source article's terms",
        "files": [{
            "download_url": url,
            "retrieved_at": retrieved,
            "byte_size": len(raw),
            "sha256": sha256(raw),
        }],
        "role": "titles and abstracts that name a human sextuplet, septuplet, octuplet or nonuplet birth",
    }]
    result["method"] = (
        "Ran the pre-registered Europe PMC title-and-abstract query with resultType=core and pageSize=25. "
        "A result counts only when its own title or abstract names sextuplets, septuplets, octuplets or nonuplets, "
        "also refers to a human birth, and does not negate that word. The highest such plurality is the measured value. "
        "One hit refutes five as the maximum. The search was not used to support the maximum."
    )
    if hits:
        top = next(
            (h for h in hits if h.get("sentence") and re.search(r"octuplets were born|octuplet birth", h["sentence"], re.I)),
            hits[0],
        )
        result["results_summary"] = [
            f"Highest plurality in the matching abstracts is {maximum}.",
            f"Example: PMID {top.get('pmid')} ({top.get('year')}): {top.get('sentence')}",
            f"{len(hits)} of {len(results)} returned records matched; Europe PMC reported {payload.get('hitCount')} hits for the query.",
        ]
    else:
        result["results_summary"] = [
            f"No returned title or abstract matched. Europe PMC reported {payload.get('hitCount')} hits and the response contained {len(results)} records."
        ]
    caveats = list(result.get("caveats") or [])
    for caveat in [
        "Only the first 25 results were read. The verdict uses those abstracts, not the unrecovered remainder of the hit list.",
        "The test does not estimate how often births above five occur. It asks whether the stated maximum of five still holds.",
    ]:
        if caveat not in caveats:
            caveats.append(caveat)
    result["caveats"] = caveats
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "maximum": maximum, "n": len(hits), "hitCount": payload.get("hitCount"), "top": hits[:3]}, indent=2))


if __name__ == "__main__":
    main()
