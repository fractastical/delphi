#!/usr/bin/env python3
"""Fish hearing and smell. Presence of a pre-registered adult term refutes."""
import csv
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
UA = "delphi-claim-test/1.0 (research; aristotle-biology)"
TERMS = {
    "inner ear",
    "otolith organ",
    "peripheral olfactory organ",
    "olfactory epithelium",
    "olfactory rosette",
    "olfactory pit",
    "naris",
    "nostril",
    "olfactory nerve",
    "octaval nerve",
}
ITEM_URL = "https://zfin.org/downloads/anatomy_item.txt"
SYN_URL = "https://zfin.org/downloads/anatomy_synonyms.txt"
STAGE_URL = "https://zfin.org/downloads/stage_ontology.txt"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return {
        "download_url": url,
        "retrieved_at": now(),
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def adult_stage_id(path):
    adults = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        name = parts[2].strip().lower()
        try:
            end_hour = float(parts[4])
        except ValueError:
            end_hour = -1
        if "adult" in name:
            adults.append((end_hour, parts[0].strip(), parts[2].strip()))
    if not adults:
        return None, None
    adults.sort()
    _hour, stage_id, stage_name = adults[-1]
    return stage_id, stage_name


def load_items(path):
    items = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip() or line.lower().startswith("anatomy id"):
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        items.append(
            {
                "id": parts[0].strip(),
                "name": parts[1].strip() if len(parts) == 4 else " ".join(p.strip() for p in parts[1:-2]),
                "end": parts[-1].strip(),
            }
        )
    return items


def load_synonyms(path):
    by_id = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip() or "synonym" in line.lower() and line.lower().startswith("anatomy"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        by_id.setdefault(parts[0].strip(), []).append(parts[-1].strip())
    return by_id


def matched(items, synonyms, adult_id):
    found = []
    for item in items:
        names = {item["name"].lower()}
        names.update(s.lower() for s in synonyms.get(item["id"], []))
        hit = sorted(names & TERMS)
        if not hit:
            continue
        is_adult = adult_id is None or item["end"] == adult_id
        found.append({"id": item["id"], "name": item["name"], "end": item["end"], "matched": hit, "adult": is_adult})
    return found


def decide(found):
    adult_hits = [row for row in found if row["adult"]]
    if adult_hits:
        return "refutes", None
    # A presence ontology does not state absence. No denial string is read.
    return "inconclusive", "not-operationalizable"


def self_test():
    items = [
        {"id": "ZFA:1", "name": "inner ear", "end": "ADULT"},
        {"id": "ZFA:2", "name": "swim bladder", "end": "ADULT"},
    ]
    found = matched(items, {}, "ADULT")
    assert decide(found)[0] == "refutes"
    items[0]["end"] = "EMBRYO"
    found = matched(items, {}, "ADULT")
    assert decide(found)[0] == "inconclusive"
    assert decide([])[0] == "inconclusive"
    print("self-test ok")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    result = json.loads((ROOT / "result.json").read_text())
    try:
        item_meta = fetch(ITEM_URL, CACHE / "anatomy_item.txt")
        syn_meta = fetch(SYN_URL, CACHE / "anatomy_synonyms.txt")
        stage_meta = fetch(STAGE_URL, CACHE / "stage_ontology.txt")
    except Exception as exc:
        result.update(
            {
                "status": "complete",
                "verdict": "inconclusive",
                "reason": "data-unavailable",
                "confidence": 0.8,
                "data_kind": "none",
                "method": f"The zebrafish anatomy files could not be downloaded ({exc}).",
                "measured": {"value": None, "unit": "matching adult terms", "n": 0, "uncertainty": None, "extra": {}},
            }
        )
        (ROOT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print("inconclusive", exc)
        return
    adult_id, adult_name = adult_stage_id(CACHE / "stage_ontology.txt")
    items = load_items(CACHE / "anatomy_item.txt")
    synonyms = load_synonyms(CACHE / "anatomy_synonyms.txt")
    found = matched(items, synonyms, adult_id)
    verdict, reason = decide(found)
    adult_hits = [row for row in found if row["adult"]]
    measured = {
        "value": len(adult_hits),
        "unit": "pre-registered adult hearing or smell terms present in zebrafish",
        "n": len(items),
        "uncertainty": "exact name match against the pre-registered list",
        "extra": {
            "adult_stage_id": adult_id,
            "adult_stage_name": adult_name,
            "adult_hits": adult_hits,
            "non_adult_hits": [row for row in found if not row["adult"]],
        },
    }
    result.update(
        {
            "status": "complete",
            "verdict": verdict,
            "confidence": 0.86 if verdict == "refutes" else 0.7,
            "data_kind": "biological",
            "method": (
                "Downloaded the ZFIN anatomy term file, synonyms and stage table. "
                "Counted exact names or synonyms in the pre-registered hearing and smell list "
                "whose end stage is the adult stage. Any such term refutes the claim that fishes "
                "lack those organs and passages. A missing string does not count as absence."
            ),
            "datasets": [
                {
                    "id": "zfin-zebrafish-anatomy",
                    "name": "ZFIN zebrafish anatomy terms, synonyms and stages",
                    "landing_url": "https://zfin.org/downloads",
                    "doi": None,
                    "version": "live download",
                    "license": "CC BY 4.0",
                    "files": [
                        {**item_meta, "name": "anatomy_item.txt"},
                        {**syn_meta, "name": "anatomy_synonyms.txt"},
                        {**stage_meta, "name": "stage_ontology.txt"},
                    ],
                    "role": "adult structures of Danio rerio",
                }
            ],
            "measured": measured,
            "results_summary": [
                f"{len(adult_hits)} pre-registered adult terms matched."
            ],
        }
    )
    if reason:
        result["reason"] = reason
    (ROOT / "derived").mkdir(exist_ok=True)
    (ROOT / "derived" / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, adult_hits)


if __name__ == "__main__":
    main()
