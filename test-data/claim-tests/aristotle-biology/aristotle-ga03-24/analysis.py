#!/usr/bin/env python3
"""aristotle-ga03-24: few shelled molluscs live on land, many in the sea.

GBIF backbone habitat counts for four classes, plus MolluscaBase statistics
if the page exposes marine / terrestrial / freshwater accepted-species counts.
Thresholds are fixed in result.json.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
DERIVED = HERE / "derived"
DATA = HERE / "data"
RESULT = HERE / "result.json"
UA = "delphisci-claim-test/aristotle-biology"
GBIF = "https://api.gbif.org/v1"
CLASSES = ["Gastropoda", "Bivalvia", "Polyplacophora", "Scaphopoda"]
STATS_URL = "https://www.molluscabase.org/aphia.php?p=stats"


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_bytes(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read(), datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False
        if tag in ("tr", "p", "li", "div", "br", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def parse_molluscabase(html: str) -> dict | None:
    parser = TextExtractor()
    parser.feed(html)
    text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
    # Look for an environment word and a nearby integer of accepted species.
    # Prefer a line that also says "accepted".
    found = {}
    for label, key in (("terrestrial", "terrestrial"), ("marine", "marine"), ("freshwater", "freshwater"), ("fresh water", "freshwater")):
        for match in re.finditer(label, text, flags=re.I):
            window = text[max(0, match.start() - 80): match.end() + 80]
            if key in found and "accepted" not in window.lower():
                continue
            numbers = [int(n.replace(",", "")) for n in re.findall(r"\d{1,3}(?:,\d{3})+|\d{2,7}", window)]
            numbers = [n for n in numbers if n >= 50]
            if not numbers:
                continue
            # The count nearest the label, preferring a window that says accepted.
            if key not in found or "accepted" in window.lower():
                found[key] = numbers[0]
                found[key + "_window"] = " ".join(window.split())
    if not all(k in found for k in ("marine", "terrestrial", "freshwater")):
        return None
    return {
        "marine": found["marine"],
        "terrestrial": found["terrestrial"],
        "freshwater": found["freshwater"],
        "windows": {k: found.get(k + "_window") for k in ("marine", "terrestrial", "freshwater")},
    }


def ratio_class(marine: int, terrestrial: int) -> str:
    if marine < 500:
        return "unqualified"
    r = terrestrial / marine
    if r < 0.10:
        return "supports"
    if r >= 0.25:
        return "refutes"
    return "mixed"


def backbone_key() -> tuple[str, str]:
    url = f"{GBIF}/dataset/search?q={urllib.parse.quote('GBIF Backbone Taxonomy')}&type=CHECKLIST&limit=20"
    payload = get_json(url)
    for item in payload.get("results", []):
        title = item.get("title") or ""
        if title.strip().lower() == "gbif backbone taxonomy":
            return item["key"], title
    for item in payload.get("results", []):
        title = (item.get("title") or "").lower()
        if "gbif backbone" in title:
            return item["key"], item.get("title")
    raise RuntimeError("GBIF backbone dataset was not found")


def class_key(name: str) -> dict:
    url = f"{GBIF}/species/match?name={urllib.parse.quote(name)}&kingdom=Animalia&verbose=false"
    payload = get_json(url)
    return {
        "name": name,
        "usageKey": payload.get("usageKey"),
        "rank": payload.get("rank"),
        "status": payload.get("status"),
        "scientificName": payload.get("scientificName"),
        "matchType": payload.get("matchType"),
    }


def species_count(dataset_key: str, taxon_key: int, habitat: str | None) -> int:
    q = {
        "datasetKey": dataset_key,
        "highertaxonKey": str(taxon_key),
        "rank": "SPECIES",
        "status": "ACCEPTED",
        "limit": "0",
    }
    if habitat:
        q["habitat"] = habitat
    url = f"{GBIF}/species/search?{urllib.parse.urlencode(q)}"
    payload = get_json(url)
    time.sleep(0.05)
    return int(payload.get("count", 0))


def decide(sources: dict) -> tuple[str, str | None]:
    qualifying = {name: src for name, src in sources.items() if src.get("qualifies")}
    if not qualifying:
        return "inconclusive", "data-unavailable"
    labels = {src["band"] for src in qualifying.values()}
    if labels == {"supports"}:
        return "supports", None
    if labels == {"refutes"}:
        return "refutes", None
    return "mixed", None


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    dataset_key, dataset_title = backbone_key()
    gbif_classes = []
    totals = {"total": 0, "TERRESTRIAL": 0, "MARINE": 0, "FRESHWATER": 0}
    for name in CLASSES:
        info = class_key(name)
        if info.get("rank") != "CLASS" or not info.get("usageKey"):
            info["error"] = "match was not a class"
            gbif_classes.append(info)
            continue
        counts = {"total": species_count(dataset_key, info["usageKey"], None)}
        for habitat in ("TERRESTRIAL", "MARINE", "FRESHWATER"):
            counts[habitat] = species_count(dataset_key, info["usageKey"], habitat)
        info["counts"] = counts
        gbif_classes.append(info)
        for key, value in counts.items():
            totals[key] += value

    marine = totals["MARINE"]
    terrestrial = totals["TERRESTRIAL"]
    freshwater = totals["FRESHWATER"]
    total = totals["total"]
    classified = terrestrial + marine + freshwater
    coverage = (classified / total) if total else 0.0
    filter_ignored = total > 0 and (terrestrial == total or marine == total)
    overlap = classified > total * 1.05
    gbif_qualifies = (
        marine >= 500
        and total > 0
        and coverage >= 0.40
        and not filter_ignored
        and not overlap
    )
    gbif_band = ratio_class(marine, terrestrial) if gbif_qualifies else "unqualified"
    gbif = {
        "dataset_key": dataset_key,
        "dataset_title": dataset_title,
        "classes": gbif_classes,
        "totals": totals,
        "coverage": coverage,
        "filter_ignored": filter_ignored,
        "overlap": overlap,
        "ratio_terrestrial_over_marine": (terrestrial / marine) if marine else None,
        "qualifies": gbif_qualifies,
        "band": gbif_band,
    }

    stats_bytes, stats_time = get_bytes(STATS_URL)
    stats_path = DATA / "molluscabase-stats.html"
    stats_path.write_bytes(stats_bytes)
    parsed = parse_molluscabase(stats_bytes.decode("utf-8", errors="replace"))
    if parsed:
        m_band = ratio_class(parsed["marine"], parsed["terrestrial"])
        moll = {
            "qualifies": m_band != "unqualified",
            "band": m_band,
            "marine": parsed["marine"],
            "terrestrial": parsed["terrestrial"],
            "freshwater": parsed["freshwater"],
            "ratio_terrestrial_over_marine": parsed["terrestrial"] / parsed["marine"] if parsed["marine"] else None,
            "windows": parsed["windows"],
            "retrieved_at": stats_time,
        }
    else:
        moll = {"qualifies": False, "band": "unqualified", "parsed": False, "retrieved_at": stats_time}

    sources = {}
    if gbif["qualifies"]:
        sources["gbif"] = gbif
    if moll["qualifies"]:
        sources["molluscabase"] = moll
    verdict, reason = decide(sources)
    if verdict == "inconclusive":
        conf = 0.35
    elif verdict == "mixed":
        conf = 0.6
    else:
        # Single-source decisions are less sure than agreement of both registers.
        conf = 0.75 if len(sources) == 2 else 0.55

    used = []
    if gbif["qualifies"]:
        used.append(gbif["ratio_terrestrial_over_marine"])
    if moll["qualifies"]:
        used.append(moll["ratio_terrestrial_over_marine"])
    value = used[0] if used else gbif["ratio_terrestrial_over_marine"]
    measured = {
        "value": value,
        "unit": "terrestrial accepted species / marine accepted species (first qualifying source; both are in extra)",
        "n": marine,
        "uncertainty": None,
        "extra": {"gbif": gbif, "molluscabase": moll, "qualifying_sources": list(sources)},
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")

    stats_hash = hashlib.sha256(stats_bytes).hexdigest()
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological" if (gbif["qualifies"] or moll["qualifies"]) else "none"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = conf
    result["method"] = (
        "Counted accepted species in the GBIF backbone for Gastropoda, Bivalvia, Polyplacophora and Scaphopoda, "
        "with and without the habitat filters TERRESTRIAL, MARINE and FRESHWATER. "
        "Also fetched the MolluscaBase statistics page and kept it only if marine, terrestrial and freshwater counts could be read from the text. "
        "The verdict follows the pre-registered agreement rule. Cephalopods are not in the sum."
    )
    result["measured"] = measured
    result["results_summary"] = [
        f"GBIF {dataset_title}: terrestrial {terrestrial}, marine {marine}, freshwater {freshwater}, total {total}, coverage {coverage:.3f}, qualifies {gbif_qualifies}, band {gbif_band}.",
        f"MolluscaBase qualifies {moll['qualifies']}, band {moll['band']}, ratio {moll.get('ratio_terrestrial_over_marine')}.",
        f"Verdict {verdict}.",
    ]
    result["datasets"] = [
        {
            "id": "gbif-backbone-species-habitat",
            "name": dataset_title,
            "landing_url": "https://www.gbif.org/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c",
            "doi": None,
            "version": dataset_key,
            "license": "CC BY 4.0 (GBIF backbone)",
            "files": [{
                "download_url": f"{GBIF}/species/search",
                "retrieved_at": retrieved,
                "byte_size": len(json.dumps(gbif["totals"]).encode()),
                "sha256": hashlib.sha256(json.dumps(gbif, sort_keys=True).encode()).hexdigest(),
                "name": "gbif species/search counts recorded in derived/measured.json",
            }],
            "role": "accepted species counts by habitat for four shelled-mollusc classes",
        },
        {
            "id": "molluscabase-stats",
            "name": "MolluscaBase statistics page",
            "landing_url": "https://www.molluscabase.org/",
            "doi": None,
            "version": stats_time[:10],
            "license": "CC BY 4.0",
            "files": [{
                "download_url": STATS_URL,
                "retrieved_at": stats_time,
                "byte_size": len(stats_bytes),
                "sha256": stats_hash,
            }],
            "role": "accepted mollusc counts by environment, used only if the page text exposes them",
        },
    ]
    # The stats HTML can be large. Record the checksum; do not commit the HTML (data/ is gitignored).
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "gbif_ratio": gbif["ratio_terrestrial_over_marine"], "gbif_qualifies": gbif_qualifies, "moll_qualifies": moll["qualifies"], "moll_ratio": moll.get("ratio_terrestrial_over_marine")}, indent=2))


if __name__ == "__main__":
    main()
