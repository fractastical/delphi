#!/usr/bin/env python3
"""Test aristotle-ga02-10 against ZFIN anatomy start stages.

Thresholds are locked to result.json. Files are downloaded at run time.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
DERIVED = HERE / "derived" / "measured.json"

ANATOMY_URL = "https://zfin.org/downloads/anatomy_item.txt"
STAGE_URL = "https://zfin.org/downloads/stage_ontology.txt"

EXPECTED_THRESHOLDS = {
    "min_items": 50,
    "min_distinct_stages": 5,
    "min_span_hours": 24,
    "early_begin_hours_max": 1,
    "modal_fraction_for_early": 0.95,
}

LOCKED = [
    "claim_id",
    "claim_iri",
    "project",
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "thresholds",
    "test_contract",
    "interpretation",
    "preregistered_at",
    "created",
    "agent",
]


def fetch(url: str, dest: Path) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "delphi-claim-test/aristotle-ga02-10"})
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    h = hashlib.sha256()
    nbytes = 0
    with urllib.request.urlopen(req, timeout=180) as resp, dest.open("wb") as out:
        final = resp.geturl()
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            h.update(chunk)
            nbytes += len(chunk)
    return {
        "download_url": url,
        "final_url": final,
        "retrieved_at": retrieved,
        "byte_size": nbytes,
        "sha256": h.hexdigest(),
    }


def rows_from(path: Path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        out.append(line.split("\t"))
    return out


def looks_header(cells, tokens) -> bool:
    blob = " ".join(cells).lower()
    return any(tok in blob for tok in tokens)


def fold_name(cells, start, end):
    return " ".join(c.strip() for c in cells[start:end] if c.strip())


def parse_anatomy(rows):
    start = 0
    header = None
    if rows and looks_header(rows[0], ["anatomy", "start stage", "start_stage"]):
        header = [c.strip().lower() for c in rows[0]]
        start = 1
    items = []
    for cells in rows[start:]:
        if len(cells) < 4:
            continue
        if header:
            def col(*needles):
                for i, name in enumerate(header):
                    if all(n in name for n in needles):
                        return cells[i].strip() if i < len(cells) else ""
                return ""
            ident = col("anatomy", "id") or cells[0].strip()
            name = col("anatomy", "name") or fold_name(cells, 1, -2)
            start_id = col("start") 
            end_id = col("end")
            if not start_id:
                start_id = cells[-2].strip()
                end_id = cells[-1].strip()
        else:
            ident = cells[0].strip()
            name = fold_name(cells, 1, -2)
            start_id = cells[-2].strip()
            end_id = cells[-1].strip()
        if not start_id:
            continue
        items.append({"id": ident, "name": name, "start": start_id, "end": end_id})
    return items


def parse_stages(rows):
    start = 0
    if rows and looks_header(rows[0], ["hour", "begin", "stage name"]):
        start = 1
    stages = []
    for cells in rows[start:]:
        if len(cells) < 5:
            continue
        ident = cells[0].strip()
        obo = cells[1].strip()
        name = fold_name(cells, 2, -2)
        try:
            begin = float(cells[-2].strip())
            end = float(cells[-1].strip())
        except ValueError:
            continue
        stages.append({"id": ident, "obo": obo, "name": name, "begin": begin, "end": end})
    return stages


def main() -> None:
    result = json.loads(RESULT.read_text())
    if result.get("thresholds") != EXPECTED_THRESHOLDS:
        sys.exit("thresholds in result.json do not match the locked constants in analysis.py")
    locked = {k: result.get(k) for k in LOCKED}
    original_caveats = list(result.get("caveats") or [])
    th = EXPECTED_THRESHOLDS

    with tempfile.TemporaryDirectory(prefix="aristotle-ga02-10-") as tmp:
        tmp = Path(tmp)
        anatomy_path = tmp / "anatomy_item.txt"
        stage_path = tmp / "stage_ontology.txt"
        anatomy_meta = fetch(ANATOMY_URL, anatomy_path)
        stage_meta = fetch(STAGE_URL, stage_path)
        items = parse_anatomy(rows_from(anatomy_path))
        stages = parse_stages(rows_from(stage_path))
        by_id = {s["id"]: s for s in stages}
        by_obo = {s["obo"]: s for s in stages}

        def match(items_in, use_obo: bool):
            matched = []
            unmatched = 0
            for item in items_in:
                stage = by_obo.get(item["start"]) if use_obo else by_id.get(item["start"])
                if stage is None and use_obo:
                    stage = by_id.get(item["start"])
                if stage is None:
                    unmatched += 1
                    continue
                matched.append({**item, "begin": stage["begin"], "stage_name": stage["name"], "stage_id": stage["id"]})
            return matched, unmatched

        matched, unmatched = match(items, False)
        match_mode = "stage-id"
        if len(matched) < th["min_items"]:
            matched, unmatched = match(items, True)
            match_mode = "obo-id-fallback"

        if len(matched) < th["min_items"]:
            conclude(
                result,
                locked,
                original_caveats,
                anatomy_meta,
                stage_meta,
                "inconclusive",
                "underpowered" if items and stages else "data-unavailable",
                0.30,
                {
                    "value": None,
                    "unit": "hours between earliest and latest anatomy start stage",
                    "n": len(matched),
                    "uncertainty": None,
                    "extra": {
                        "anatomy_rows_parsed": len(items),
                        "stage_rows_parsed": len(stages),
                        "unmatched": unmatched,
                        "match_mode": match_mode,
                    },
                },
                [
                    f"Matched items: {len(matched)}. Anatomy rows parsed: {len(items)}. Stage rows parsed: {len(stages)}.",
                ],
            )
            return

        begins = [m["begin"] for m in matched]
        span = max(begins) - min(begins)
        stage_counts = {}
        for m in matched:
            stage_counts[m["stage_id"]] = stage_counts.get(m["stage_id"], 0) + 1
        modal_id, modal_n = max(stage_counts.items(), key=lambda kv: (kv[1], kv[0]))
        modal_fraction = modal_n / len(matched)
        modal_begin = by_id[modal_id]["begin"]
        distinct = len(stage_counts)
        early_n = sum(1 for b in begins if b <= th["early_begin_hours_max"])
        early_cluster = modal_fraction >= th["modal_fraction_for_early"] and modal_begin <= th["early_begin_hours_max"]
        spread = distinct >= th["min_distinct_stages"] and span >= th["min_span_hours"]

        if spread and not early_cluster:
            verdict, reason, confidence = "supports", None, 0.60
        elif early_cluster and not spread:
            verdict, reason, confidence = "refutes", None, 0.55
        else:
            verdict, reason, confidence = "mixed", None, 0.40

        # Stage onset histogram, limited to stages that occur.
        histogram = []
        for sid, count in sorted(stage_counts.items(), key=lambda kv: (by_id[kv[0]]["begin"], kv[0])):
            histogram.append(
                {
                    "stage_id": sid,
                    "stage_name": by_id[sid]["name"],
                    "begin_hours": by_id[sid]["begin"],
                    "items": count,
                }
            )
        measured = {
            "value": round(span, 4),
            "unit": "hours between earliest and latest anatomy start stage",
            "n": len(matched),
            "uncertainty": None,
            "extra": {
                "distinct_start_stages": distinct,
                "earliest_begin_hours": min(begins),
                "latest_begin_hours": max(begins),
                "modal_stage_id": modal_id,
                "modal_stage_name": by_id[modal_id]["name"],
                "modal_begin_hours": modal_begin,
                "modal_fraction": round(modal_fraction, 6),
                "items_with_begin_hours_at_most_1": early_n,
                "unmatched": unmatched,
                "match_mode": match_mode,
                "anatomy_rows_parsed": len(items),
                "stage_rows_parsed": len(stages),
                "stage_histogram": histogram,
            },
        }
        summary = [
            f"Matched anatomical items: {len(matched)} of {len(items)} parsed. Distinct start stages: {distinct}. Begin-hour span: {span:.4f} (from {min(begins)} to {max(begins)}).",
            f"Modal start stage: {by_id[modal_id]['name']} at {modal_begin} h, fraction {modal_fraction:.4f}. Items with begin hours <= 1: {early_n}.",
        ]
        conclude(result, locked, original_caveats, anatomy_meta, stage_meta, verdict, reason, confidence, measured, summary)


def conclude(result, locked, original_caveats, anatomy_meta, stage_meta, verdict, reason, confidence, measured, summary):
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["datasets"] = [
        {
            "id": "zfin-anatomy-and-stages",
            "name": "ZFIN zebrafish anatomy terms and stage series",
            "landing_url": "https://zfin.org/downloads",
            "doi": None,
            "version": "daily report current on the retrieval date; index page was labelled 31 Oct 2026 when the test was registered",
            "license": None,
            "files": [
                {
                    "name": "anatomy_item.txt",
                    "download_url": anatomy_meta["download_url"],
                    "final_url": anatomy_meta["final_url"],
                    "retrieved_at": anatomy_meta["retrieved_at"],
                    "byte_size": anatomy_meta["byte_size"],
                    "sha256": anatomy_meta["sha256"],
                },
                {
                    "name": "stage_ontology.txt",
                    "download_url": stage_meta["download_url"],
                    "final_url": stage_meta["final_url"],
                    "retrieved_at": stage_meta["retrieved_at"],
                    "byte_size": stage_meta["byte_size"],
                    "sha256": stage_meta["sha256"],
                },
            ],
            "role": "start stage of each zebrafish anatomical structure, joined to begin hours of the staging series",
        }
    ]
    result["measured"] = measured
    result["method"] = (
        "Downloaded the ZFIN anatomy-item and stage-series files, hashed them, and joined each "
        "structure's start stage to the stage series. The span of begin hours, the number of distinct "
        "start stages, and the modal-stage fraction were compared with the pre-registered thresholds. "
        "No expression file was used."
    )
    result["results_summary"] = summary
    result["caveats"] = original_caveats + [
        "No SPDX licence is stated on https://zfin.org/downloads. The files are public daily reports."
    ]
    for key, value in locked.items():
        if result.get(key) != value:
            sys.exit(f"locked field changed: {key}")
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    DERIVED.parent.mkdir(parents=True, exist_ok=True)
    payload = {"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured, "results_summary": summary}
    DERIVED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "value": measured.get("value"), "n": measured.get("n")}, indent=2))


if __name__ == "__main__":
    main()
