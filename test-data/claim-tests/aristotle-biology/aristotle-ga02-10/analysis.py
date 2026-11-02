#!/usr/bin/env python3
"""ZFIN start stages of named organs against aristotle-ga02-10.

Rules are those committed in result.json. Standard library only.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
ANATOMY_URL = "https://zfin.org/downloads/anatomy_item.txt"
STAGE_URL = "https://zfin.org/downloads/stage_ontology.txt"
ORGANS = [
    "heart", "liver", "eye", "intestine", "pectoral fin",
    "kidney", "pancreas", "swim bladder", "brain", "notochord",
]
UA = "delphisci-claim-test"


def fetch(url: str, dest: Path) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            dest.write_bytes(resp.read())
    raw = dest.read_bytes()
    return {
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def rows(path: Path) -> list[list[str]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        out.append(line.split("\t"))
    return out


def main() -> None:
    anatomy_info = fetch(ANATOMY_URL, DATA / "anatomy_item.txt")
    stage_info = fetch(STAGE_URL, DATA / "stage_ontology.txt")
    stages = {}
    for cols in rows(DATA / "stage_ontology.txt"):
        if len(cols) < 5 or not cols[0].startswith("ZDB-STAGE"):
            continue
        begin, end = float(cols[3]), float(cols[4])
        stages[cols[0]] = {"obo": cols[1], "name": cols[2], "begin_hours": begin, "end_hours": end}
    by_name: dict[str, list[list[str]]] = {}
    for cols in rows(DATA / "anatomy_item.txt"):
        if len(cols) < 4:
            continue
        by_name.setdefault(cols[1].strip().lower(), []).append(cols)

    name_hits = []
    scored = []
    join_fail = 0
    for organ in ORGANS:
        hits = by_name.get(organ, [])
        if not hits:
            name_hits.append({"organ": organ, "found": False})
            continue
        # Exact name can still occur on more than one row. Score each and keep the earliest specific stage.
        parsed = []
        for cols in hits:
            stage_id = cols[2].strip()
            stage = stages.get(stage_id)
            if stage is None:
                join_fail += 1
                parsed.append({"organ": organ, "anatomy_id": cols[0], "start_stage_id": stage_id, "joined": False})
                continue
            placeholder = stage["name"].strip().lower() == "unknown" or (stage["end_hours"] - stage["begin_hours"]) > 1000
            parsed.append({
                "organ": organ,
                "anatomy_id": cols[0],
                "start_stage_id": stage_id,
                "joined": True,
                "placeholder": placeholder,
                "stage_name": stage["name"],
                "begin_hours": stage["begin_hours"],
                "end_hours": stage["end_hours"],
            })
        name_hits.append({"organ": organ, "found": True, "rows": parsed})
        usable = [row for row in parsed if row.get("joined") and not row.get("placeholder")]
        if usable:
            scored.append(min(usable, key=lambda row: row["begin_hours"]))

    n_found = sum(1 for row in name_hits if row["found"])
    n = len(scored)
    stage_ids = {row["start_stage_id"] for row in scored}
    s = len(stage_ids)
    joined = sum(1 for row in name_hits if row["found"] for item in row["rows"] if item.get("joined"))
    found_rows = sum(len(row["rows"]) for row in name_hits if row["found"])
    if n_found == 0 or (found_rows and joined * 2 < found_rows):
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.8
    elif n >= 5 and s >= 2:
        verdict, reason, confidence = "supports", None, 0.7
    elif n >= 5 and s == 1:
        verdict, reason, confidence = "refutes", None, 0.65
    else:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.6

    begins = [row["begin_hours"] for row in scored]
    measured = {
        "value": s,
        "unit": "distinct ZFIN start stages among scored named organs",
        "n": n,
        "uncertainty": "exact count of stage identifiers",
        "extra": {
            "organs_requested": ORGANS,
            "organs_found": n_found,
            "organs_scored": n,
            "join_failures": join_fail,
            "begin_hours_min": min(begins) if begins else None,
            "begin_hours_max": max(begins) if begins else None,
            "span_hours": (max(begins) - min(begins)) if begins else None,
            "scored": scored,
            "lookup": name_hits,
        },
    }
    doc = json.loads(RESULT.read_text())
    doc["status"] = "complete"
    doc["datasets"] = [{
        "id": "zfin-anatomy-item-and-stage-series",
        "name": "ZFIN zebrafish anatomy terms and stage series",
        "landing_url": "https://zfin.org/downloads",
        "doi": None,
        "version": "downloaded at analysis time; ZFIN rebuilds these files daily",
        "license": "ZFIN public download; the downloads page asks for attribution and does not name an SPDX licence",
        "files": [
            {"name": "anatomy_item.txt", **anatomy_info},
            {"name": "stage_ontology.txt", **stage_info},
        ],
        "role": "start stage of named zebrafish anatomical structures, with hour bounds of each stage",
    }]
    doc["method"] = (
        "Downloaded the ZFIN anatomy-item and stage-series files and hashed them. "
        "Ten organ names were matched exactly, placeholders named Unknown or spanning more than 1000 hours were dropped, "
        "and the number of distinct start stages among the remaining organs was compared with the pre-registered thresholds. "
        "Where one name had several rows, the earliest specific start stage was kept."
    )
    doc["measured"] = measured
    doc["verdict"] = verdict
    doc["confidence"] = confidence
    doc["data_kind"] = "none" if reason == "data-unavailable" else "biological"
    doc["results_summary"] = [
        f"Named organs found: {n_found} of {len(ORGANS)}. Scored after dropping placeholders: {n}. Distinct start stages: {s}.",
        "Span of start times, in hours from fertilization, is in measured.extra. The verdict uses the count of stages, not the span.",
    ]
    if reason:
        doc["reason"] = reason
    else:
        doc.pop("reason", None)
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "n": n, "s": s, "found": n_found}))


if __name__ == "__main__":
    main()
