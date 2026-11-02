#!/usr/bin/env python3
"""Test aristotle-ha09-26 against honey-bee pollen loads.

Thresholds are locked to result.json. The CSV is downloaded at run time
and is not committed.
"""

from __future__ import annotations

import csv
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

FILE_URL = "https://datadryad.org/api/v2/files/3848538/download"
LANDING = "https://datadryad.org/dataset/doi:10.5061/dryad.tdz08kq88"

EXPECTED_THRESHOLDS = {"min_loads": 30, "refute_min_mixed_fraction": 0.1}

POLLEN_PRIORITY = [
    "morphotype",
    "pollenmorphotype",
    "pollen_morphotype",
    "pollentype",
    "pollen_type",
    "plantspecies",
    "plant_species",
    "floralspecies",
    "floral_species",
    "family",
    "genus",
    "taxon",
    "pollen",
]

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
    req = urllib.request.Request(url, headers={"User-Agent": "delphi-claim-test/aristotle-ha09-26"})
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


def squash(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def is_honey(value: str) -> bool:
    v = (value or "").strip().lower()
    return v == "hb" or "mellifera" in v or "honey" in v


def main() -> None:
    result = json.loads(RESULT.read_text())
    if result.get("thresholds") != EXPECTED_THRESHOLDS:
        sys.exit("thresholds in result.json do not match the locked constants in analysis.py")
    locked = {k: result.get(k) for k in LOCKED}
    original_caveats = list(result.get("caveats") or [])

    with tempfile.TemporaryDirectory(prefix="aristotle-ha09-26-") as tmp:
        dest = Path(tmp) / "dataset_pollen_raw.csv"
        meta = fetch(FILE_URL, dest)
        text = dest.read_text(encoding="utf-8-sig", errors="replace")
        rows = list(csv.DictReader(text.splitlines()))
        if not rows:
            conclude(result, locked, original_caveats, meta, "inconclusive", "data-unavailable", 0.30, None, ["The pollen file has no data rows."], {"headers": []})
            return
        headers = list(rows[0].keys())
        by_squash = {squash(h): h for h in headers if h}

        def need(*candidates):
            for c in candidates:
                if squash(c) in by_squash:
                    return by_squash[squash(c)]
            return None

        species_col = need("species")
        site_col = need("site")
        period_col = need("period")
        day_col = need("day")
        bee_col = need("bee")
        pollen_col = None
        for token in POLLEN_PRIORITY:
            key = squash(token)
            if key in by_squash and by_squash[key] != species_col:
                pollen_col = by_squash[key]
                break
        missing = [
            name
            for name, col in (
                ("species", species_col),
                ("site", site_col),
                ("period", period_col),
                ("day", day_col),
                ("bee", bee_col),
                ("pollen_kind", pollen_col),
            )
            if col is None
        ]
        if missing:
            conclude(
                result,
                locked,
                original_caveats,
                meta,
                "inconclusive",
                "data-unavailable",
                0.30,
                None,
                ["Required columns were not found: " + ", ".join(missing) + ".", "Headers: " + ", ".join(headers)],
                {"headers": headers, "missing": missing},
            )
            return

        loads = {}
        honey_rows = 0
        for row in rows:
            if not is_honey(row.get(species_col) or ""):
                continue
            honey_rows += 1
            key = (
                (row.get(site_col) or "").strip(),
                (row.get(period_col) or "").strip(),
                (row.get(day_col) or "").strip(),
                (row.get(bee_col) or "").strip(),
            )
            kind = " ".join((row.get(pollen_col) or "").split())
            loads.setdefault(key, set())
            if kind:
                loads[key].add(kind)

        single = 0
        mixed = 0
        excluded = 0
        mixed_examples = []
        kind_counts = {}
        for key, kinds in loads.items():
            if len(kinds) == 0:
                excluded += 1
            elif len(kinds) == 1:
                single += 1
                only = next(iter(kinds))
                kind_counts[only] = kind_counts.get(only, 0) + 1
            else:
                mixed += 1
                if len(mixed_examples) < 12:
                    mixed_examples.append({"site": key[0], "period": key[1], "day": key[2], "bee": key[3], "kinds": sorted(kinds)})
        scored = single + mixed
        fraction = (mixed / scored) if scored else None
        th = EXPECTED_THRESHOLDS
        if scored < th["min_loads"]:
            verdict, reason, confidence = "inconclusive", "underpowered", 0.30
        elif mixed == 0:
            verdict, reason, confidence = "supports", None, 0.55
        elif fraction >= th["refute_min_mixed_fraction"]:
            verdict, reason, confidence = "refutes", None, 0.75
        else:
            verdict, reason, confidence = "mixed", None, 0.60

        measured = {
            "value": None if fraction is None else round(fraction, 6),
            "unit": "fraction of scored honey-bee pollen loads with two or more pollen kinds",
            "n": scored,
            "uncertainty": None,
            "extra": {
                "mixed_loads": mixed,
                "single_kind_loads": single,
                "excluded_loads_no_pollen_kind": excluded,
                "honey_bee_rows": honey_rows,
                "load_keys": len(loads),
                "pollen_column": pollen_col,
                "species_column": species_col,
                "grouping_columns": [site_col, period_col, day_col, bee_col],
                "headers": headers,
                "mixed_load_examples": mixed_examples,
                "single_kind_counts_top": dict(sorted(kind_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:15]),
            },
        }
        fraction_text = "none" if fraction is None else f"{fraction:.4f}"
        summary = [
            f"Honey-bee rows: {honey_rows}. Load keys: {len(loads)}. Scored loads: {scored}. Single-kind: {single}. Mixed: {mixed}. Excluded with no pollen kind: {excluded}.",
            f"Mixed fraction: {fraction_text}. Pollen-kind column: {pollen_col}.",
        ]
        conclude(result, locked, original_caveats, meta, verdict, reason, confidence, measured, summary, None)


def conclude(result, locked, original_caveats, meta, verdict, reason, confidence, measured, summary, extra):
    if measured is None:
        measured = {
            "value": None,
            "unit": "fraction of scored honey-bee pollen loads with two or more pollen kinds",
            "n": 0,
            "uncertainty": None,
            "extra": extra or {},
        }
    elif extra:
        measured["extra"].update(extra)
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
            "id": "dryad-10.5061/dryad.tdz08kq88-dataset_pollen_raw",
            "name": "Pollen collection by the western honey bee and common eastern bumble bee (dataset_pollen_raw.csv)",
            "landing_url": LANDING,
            "doi": "10.5061/dryad.tdz08kq88",
            "version": "4",
            "license": "CC0-1.0",
            "files": [
                {
                    "name": "dataset_pollen_raw.csv",
                    "download_url": FILE_URL,
                    "final_url": meta["final_url"],
                    "retrieved_at": meta["retrieved_at"],
                    "byte_size": meta["byte_size"],
                    "sha256": meta["sha256"],
                }
            ],
            "role": "individual corbicular pollen loads of honey bees and bumble bees; only honey bees are scored",
        }
    ]
    result["measured"] = measured
    result["method"] = (
        "Downloaded dataset_pollen_raw.csv from the Dryad API, hashed it, and grouped honey-bee rows "
        "by site, period, day and bee. The pollen-kind column was chosen by the pre-registered header priority. "
        "A load with two or more distinct pollen-kind values was mixed. The fraction was compared with 0 and 0.10."
    )
    result["results_summary"] = summary
    result["caveats"] = original_caveats
    for key, value in locked.items():
        if result.get(key) != value:
            sys.exit(f"locked field changed: {key}")
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    DERIVED.parent.mkdir(parents=True, exist_ok=True)
    DERIVED.write_text(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured, "results_summary": summary}, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "value": measured.get("value"), "n": measured.get("n")}, indent=2))


if __name__ == "__main__":
    main()
