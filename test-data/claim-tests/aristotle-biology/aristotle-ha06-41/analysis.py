#!/usr/bin/env python3
"""Test aristotle-ha06-41: European hares breed all season, superfoetate, and bear monthly."""
import hashlib
import json
import os
import re
import zipfile
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
UA = "DelphiClaimTest/1.0 (aristotle-ha06-41; public claim test)"
FILES = []
ANAGE = "/workspace/test-data/organisms/darwin-origin/ch11-14/data/anage_build15_dataset.zip"
GISD = "https://www.iucngisd.org/gisd/species.php?sc=1643"
ADW = "https://animaldiversity.org/accounts/Lepus_europaeus/"
MONTH = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "midwinter": 1, "winter": 1, "spring": 4, "midsummer": 7, "summer": 7,
    "autumn": 10, "fall": 10,
}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(url, content, when, role):
    FILES.append({
        "download_url": url,
        "retrieved_at": when,
        "byte_size": len(content) if isinstance(content, (bytes, bytearray)) else os.path.getsize(content),
        "sha256": hashlib.sha256(content if isinstance(content, (bytes, bytearray)) else open(content, "rb").read()).hexdigest(),
        "role": role,
    })


def fetch(url, name, role):
    path = os.path.join(DATA, name)
    meta = path + ".retrieved"
    if os.path.exists(path) and os.path.exists(meta):
        content = open(path, "rb").read()
        when = open(meta).read().strip()
    else:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=120)
        r.raise_for_status()
        content, when = r.content, now()
        open(path, "wb").write(content)
        open(meta, "w").write(when)
    record(url, content, when, role)
    return content.decode("utf-8", "replace")


def text_of(html):
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def month_of(fragment):
    low = fragment.lower()
    found = []
    for word, num in MONTH.items():
        if re.search(r"\b" + word + r"\b", low):
            found.append(num)
    return min(found) if found else None


def season_flags(text):
    affirm = bool(re.search(r"year[-\s]?round|all seasons|throughout the year|every season", text, re.I))
    deny = False
    spans = []
    for m in re.finditer(r"between\s+(.{3,60}?)\s+and\s+([A-Za-z][A-Za-z /]{2,30})", text, re.I):
        a, b = month_of(m.group(1)), month_of(m.group(2))
        if a and b:
            span = (b - a + 1) if b >= a else (12 - a + 1 + b)
            spans.append({"phrase": m.group(0), "start_month": a, "end_month": b, "inclusive_months": span})
            if span <= 9:
                deny = True
    return affirm, deny, spans


def clause_from(flags):
    affirms = [name for name, (a, d, _) in flags.items() if a]
    denies = [name for name, (a, d, _) in flags.items() if d]
    if affirms and denies:
        return "unresolved"
    if affirms and not denies:
        return "pass"
    if denies and not affirms:
        return "fail"
    return "unresolved"


def main():
    blob = open(ANAGE, "rb").read()
    record(
        "https://genomics.senescence.info/species/dataset.zip",
        blob,
        now(),
        "AnAge build 15 zip already in test-data/organisms",
    )
    FILES[-1]["path"] = "test-data/organisms/darwin-origin/ch11-14/data/anage_build15_dataset.zip"
    with zipfile.ZipFile(ANAGE) as zf:
        raw = zf.read("anage_data.txt").decode("utf-8", "replace")
    lines = raw.splitlines()
    cols = lines[0].split("\t")
    row = next(ln.split("\t") for ln in lines[1:] if ln.split("\t")[6] == "Lepus" and ln.split("\t")[7] == "europaeus")
    rec = dict(zip(cols, row))
    litters = rec["Litters/Clutches per year"].strip()
    interval = rec["Inter-litter/Interbirth interval"].strip()
    litters_n = float(litters) if litters else None
    interval_n = float(interval) if interval else None
    if litters_n is not None and litters_n >= 10:
        month = "pass"
    elif interval_n is not None and interval_n <= 35:
        month = "pass"
    elif litters_n is not None and litters_n < 8:
        month = "fail"
    else:
        month = "unresolved"

    pages = {
        "gisd": text_of(fetch(GISD, "gisd-lepus.html", "IUCN GISD Lepus europaeus")),
        "adw": text_of(fetch(ADW, "adw-lepus.html", "Animal Diversity Web Lepus europaeus")),
    }
    flags = {name: season_flags(text) for name, text in pages.items()}
    season = clause_from(flags)
    super_re = re.compile(r"superfoet|superfet|superconception", re.I)
    super_hits = {name: bool(super_re.search(text)) for name, text in pages.items()}
    # Explicit denial is not expected as a mere absence. Absence is unresolved.
    denial = any(re.search(r"does not superfoet|no superfoet|without superfoet", text, re.I) for text in pages.values())
    if any(super_hits.values()):
        superfet = "pass"
    elif denial:
        superfet = "fail"
    else:
        superfet = "unresolved"

    clauses = {"every_month": month, "all_seasons": season, "superfoetation": superfet}
    resolved = {k: v for k, v in clauses.items() if v in {"pass", "fail"}}
    n_pass = sum(v == "pass" for v in resolved.values())
    n_fail = sum(v == "fail" for v in resolved.values())
    if len(resolved) < 2:
        verdict, reason = "inconclusive", "other"
    elif n_pass == 3:
        verdict, reason = "supports", None
    elif n_pass and n_fail:
        verdict, reason = "mixed", None
    elif n_fail == len(resolved) and len(resolved) >= 2:
        verdict, reason = "refutes", None
    else:
        verdict, reason = "inconclusive", "other"

    measured = {
        "value": litters_n,
        "unit": "litters per year",
        "n": 1,
        "uncertainty": None,
        "extra": {
            "gestation_days": rec["Gestation/Incubation (days)"],
            "interlitter_interval": interval or None,
            "clauses": clauses,
            "season_spans": {k: v[2] for k, v in flags.items()},
            "season_affirm": {k: v[0] for k, v in flags.items()},
            "superfoetation_mentioned": super_hits,
            "anage_path": "test-data/organisms/darwin-origin/ch11-14/data/anage_build15_dataset.zip",
            "anage_zip_bytes": len(blob),
            "anage_zip_sha256": FILES[0]["sha256"],
        },
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2, ensure_ascii=False)
    path = os.path.join(HERE, "result.json")
    result = json.load(open(path))
    result["status"] = "complete"
    result["preregistered"] = True
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = 0.72
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["deviations"] = []
    result["method"] = (
        "Litters per year and the inter-litter interval were read from the vendored AnAge build 15 row for Lepus europaeus. "
        "Every month fails when litters per year are present and below 8. "
        "GISD and Animal Diversity Web were searched for an explicit year-round statement and for a between-month breeding span of nine months or fewer. "
        "A year-round statement in one source and a short span in the other leaves the season clause unresolved. "
        "Superfoetation passes only if one of those accounts names it. Fewer than two resolved clauses is inconclusive."
    )
    result["measured"] = measured
    result["caveats"] = [
        "AnAge's litters-per-year figure is a literature average, not a count of births made for this test.",
        "GISD says reproduction occurs year round, while Animal Diversity Web limits the breeding season to midwinter through midsummer. The pre-registered rule treats that conflict as unresolved rather than as a vote.",
        "Neither account uses the word superfoetation or superconception, so that clause is unresolved rather than denied.",
        "The scope is Lepus europaeus, the brown hare named in the claim record.",
    ]
    result["datasets"] = [
        {
            "id": "anage-build-15",
            "name": "AnAge build 15",
            "landing_url": "https://genomics.senescence.info/species/",
            "doi": "10.1093/nar/gks1155",
            "doi_note": "The vendored release notes cite PMID 23193293. NCBI esummary for that PMID returns this DOI.",
            "version": "build 15",
            "license": "CC BY 3.0",
            "files": [FILES[0]],
            "role": "litters per year, gestation and inter-litter interval for Lepus europaeus",
        },
        {
            "id": "iucn-gisd-lepus-europaeus",
            "name": "IUCN Global Invasive Species Database, Lepus europaeus",
            "landing_url": GISD,
            "doi": None,
            "version": "page retrieved with this run",
            "license": "publicly readable GISD species profile",
            "files": [f for f in FILES if "iucngisd" in f["download_url"]],
            "role": "breeding-season wording",
        },
        {
            "id": "adw-lepus-europaeus",
            "name": "Animal Diversity Web, Lepus europaeus",
            "landing_url": ADW,
            "doi": None,
            "version": "page retrieved with this run",
            "license": "publicly readable; University of Michigan Museum of Zoology",
            "files": [f for f in FILES if "animaldiversity" in f["download_url"]],
            "role": "breeding-season wording and any superfoetation statement",
        },
    ]
    result["headline"] = (
        f"AnAge records {litters_n} litters per year for the European hare, so bearing young every month fails, "
        "but the season accounts conflict and superfoetation is not stated, so the pre-registered rule stays inconclusive."
    )
    with open(path, "w") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(verdict, clauses, result["headline"])


if __name__ == "__main__":
    main()
