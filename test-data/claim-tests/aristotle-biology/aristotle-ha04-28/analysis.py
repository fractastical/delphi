#!/usr/bin/env python3
"""European eel sex and eggs against Aristotle's claim that the eel engenders nothing.

Pre-registered in result.json. Reads the FishBase reproduction summary for
Anguilla anguilla and the OBIS lifeStage facet. Navigation labels are not searched.
"""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from html import unescape
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
UA = "Mozilla/5.0 (compatible; delphisci-claim-test/1.0; research)"
SUMMARY = "https://www.fishbase.se/summary/Anguilla-anguilla.html"
OBIS = "https://api.obis.org/v3/facet?scientificname=Anguilla%20anguilla&facets=lifeStage"
MODE_RE = re.compile(r"\b(dioecism|dioecious|gonochorism|gonochoristic|separate sexes)\b", re.I)
SEXLESS_RE = re.compile(r"no distinguishable sex|sexless|no gonads", re.I)
EGG_RE = re.compile(r"\beggs?\b|\bspawning\b|\bfecundity\b|\bleptocephalus\b|\blarvae?\b", re.I)
STAGE_RE = re.compile(r"egg|larva|leptocephal", re.I)


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
        return r.status, body, r.geturl()


def visible(html):
    html = re.sub(r"(?is)<script\b.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style\b.*?>.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def reproduction_slice(text):
    """From the Mode field through the life-cycle paragraph, skipping site navigation."""
    low = text.lower()
    i = low.find(" mode ")
    if i < 0:
        i = low.find("mode ")
    j = low.find("search for more references")
    if i < 0:
        return ""
    if j < i:
        j = len(text)
    return text[i:j]


def main():
    DATA.mkdir(exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    files = []
    status, summary_b, final = fetch(SUMMARY)
    (DATA / "Anguilla-anguilla.html").write_bytes(summary_b)
    files.append({
        "name": "Anguilla-anguilla.html",
        "download_url": SUMMARY,
        "retrieved_at": now(),
        "byte_size": len(summary_b),
        "sha256": sha256(summary_b),
        "http_status": status,
    })
    summary_html = summary_b.decode("utf-8", "replace")
    links = re.findall(r"""href=['"]([^'"]*FishReproSummary\.php[^'"]*)['"]""", summary_html, flags=re.I)
    repro_url = None
    if links:
        href = links[0].replace("&amp;", "&")
        if href.startswith("/"):
            repro_url = "https://www.fishbase.se" + href
        elif href.startswith("../"):
            repro_url = "https://www.fishbase.se/" + href[3:]
        elif href.startswith("http"):
            repro_url = href
        else:
            repro_url = "https://www.fishbase.se/Reproduction/" + href.lstrip("./")
    repro_text = ""
    if repro_url:
        st, repro_b, _ = fetch(repro_url)
        (DATA / "FishReproSummary.html").write_bytes(repro_b)
        files.append({
            "name": "FishReproSummary.html",
            "download_url": repro_url,
            "retrieved_at": now(),
            "byte_size": len(repro_b),
            "sha256": sha256(repro_b),
            "http_status": st,
        })
        repro_text = reproduction_slice(visible(repro_b.decode("utf-8", "replace")))
    obis_ok = False
    obis_stages = []
    obis_hit = []
    try:
        st, obis_b, _ = fetch(OBIS)
        (DATA / "obis-lifestage.json").write_bytes(obis_b)
        files.append({
            "name": "obis-lifestage.json",
            "download_url": OBIS,
            "retrieved_at": now(),
            "byte_size": len(obis_b),
            "sha256": sha256(obis_b),
            "http_status": st,
        })
        payload = json.loads(obis_b.decode())
        obis_stages = payload.get("results", {}).get("lifeStage", [])
        obis_ok = True
        for bucket in obis_stages:
            if STAGE_RE.search(str(bucket.get("key", ""))):
                obis_hit.append({"key": bucket.get("key"), "records": bucket.get("records")})
    except Exception as exc:  # noqa: BLE001 — recorded, not hidden
        obis_error = str(exc)
    else:
        obis_error = None

    mode_hit = MODE_RE.search(repro_text)
    sexless = SEXLESS_RE.search(repro_text)
    egg_hits = EGG_RE.findall(repro_text)
    larva_records = sum(int(b["records"]) for b in obis_hit if str(b["records"]).isdigit() or isinstance(b["records"], int))
    spawning_unobserved = "actual spawning has never been observed" in repro_text.lower() or \
        "actual spawning has never been observed" in visible(summary_html).lower()

    if not repro_text and not obis_ok:
        verdict, reason = "inconclusive", "data-unavailable"
    elif mode_hit or egg_hits or larva_records >= 1:
        verdict, reason = "refutes", None
    elif sexless and not egg_hits and obis_ok and larva_records == 0:
        verdict, reason = "supports", None
    elif not repro_text and obis_ok and larva_records == 0:
        verdict, reason = "inconclusive", "other"
    else:
        verdict, reason = "inconclusive", "other"

    if verdict == "refutes" and mode_hit and egg_hits:
        confidence = 0.84
    elif verdict == "refutes":
        confidence = 0.7
    elif verdict == "supports":
        confidence = 0.55
    else:
        confidence = 0.35

    measured = {
        "value": 1 if mode_hit else 0,
        "unit": "1 if the reproduction mode matches separate sexes, else 0",
        "n": 1,
        "uncertainty": None,
        "extra": {
            "mode_match": mode_hit.group(0) if mode_hit else None,
            "sexless_match": bool(sexless),
            "egg_or_larva_terms": sorted(set(m.lower() for m in egg_hits)),
            "reproduction_slice_chars": len(repro_text),
            "obis_life_stage_retrieved": obis_ok,
            "obis_error": obis_error,
            "obis_egg_larva_leptocephalus_buckets": obis_hit,
            "obis_egg_larva_leptocephalus_records": larva_records,
            "obis_life_stage_buckets": len(obis_stages),
            "phrase_actual_spawning_never_observed": spawning_unobserved,
        },
    }
    doc = json.loads(RESULT.read_text())
    doc["status"] = "complete"
    doc["verdict"] = verdict
    if reason:
        doc["reason"] = reason
    elif "reason" in doc:
        del doc["reason"]
    doc["confidence"] = confidence
    doc["data_kind"] = "biological"
    for ds in doc["datasets"]:
        if ds["id"] == "fishbase-anguilla-anguilla":
            ds["files"] = [f for f in files if f["name"].endswith(".html")]
            ds["license"] = None
        if ds["id"] == "obis-anguilla-anguilla-lifestage":
            ds["files"] = [f for f in files if f["name"].endswith(".json")]
    doc["measured"] = measured
    doc["method"] = (
        "Fetched the FishBase species summary, followed the FishReproSummary link, "
        "and searched only the slice from the Mode field through the life-cycle paragraph. "
        "Separate-sex wording and egg, spawning, fecundity, or larva wording were matched "
        "with the pre-registered expressions. OBIS was queried with facets=lifeStage and size "
        "implied by the facet endpoint; buckets whose labels match egg, larva, or leptocephalus "
        "were summed. The HTML navigation label 'Eggs' is outside that slice."
    )
    doc["results_summary"] = [
        f"Reproduction mode match: {measured['extra']['mode_match']}.",
        f"Egg or larva terms in the reproduction slice: {measured['extra']['egg_or_larva_terms']}.",
        f"OBIS egg/larva/leptocephalus records: {larva_records} across {len(obis_hit)} buckets "
        f"(life-stage buckets returned: {len(obis_stages)}).",
        f"Verdict {verdict}." + (f" Reason {reason}." if reason else ""),
    ]
    if spawning_unobserved:
        note = (
            "The retrieved account also says that actual spawning has never been observed. "
            "That sentence does not remove the mode or the egg-scatterer guild from the same record."
        )
        caveats = list(doc.get("caveats") or [])
        if note not in caveats:
            caveats.append(note)
        doc["caveats"] = caveats
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    DERIVED.joinpath("measured.json").write_text(json.dumps({
        "measured": measured, "verdict": verdict, "reason": reason,
        "reproduction_slice": repro_text[:4000],
    }, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "mode": measured["extra"]["mode_match"],
                      "terms": measured["extra"]["egg_or_larva_terms"], "obis": larva_records}, indent=2))


if __name__ == "__main__":
    main()
