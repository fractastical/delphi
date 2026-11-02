#!/usr/bin/env python3
"""Test aristotle-pa04-34 against published fish testes masses.

Thresholds are locked to result.json. The CSV is downloaded at run time.
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

FILE_URL = "https://datadryad.org/api/v2/files/58157/download"
LANDING = "https://datadryad.org/dataset/doi:10.5061/dryad.fd3nq57"

EXPECTED_THRESHOLDS = {"refute_min_species_positive_mass": 10}

SPECIES_PRIORITY = ["species", "scientificname", "scientific_name", "binomial", "taxon", "latin"]
NONFISH = ("mammal", "bird", "reptile", "snake", "amphibian")

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
    req = urllib.request.Request(url, headers={"User-Agent": "delphi-claim-test/aristotle-pa04-34"})
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


def parse_number(value: str):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "" or text.lower() in {"na", "nan", "none", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def main() -> None:
    result = json.loads(RESULT.read_text())
    if result.get("thresholds") != EXPECTED_THRESHOLDS:
        sys.exit("thresholds in result.json do not match the locked constants in analysis.py")
    locked = {k: result.get(k) for k in LOCKED}
    original_caveats = list(result.get("caveats") or [])

    with tempfile.TemporaryDirectory(prefix="aristotle-pa04-34-") as tmp:
        dest = Path(tmp) / "MPdata2018.csv"
        meta = fetch(FILE_URL, dest)
        text = dest.read_text(encoding="utf-8-sig", errors="replace")
        rows = list(csv.DictReader(text.splitlines()))
        if not rows:
            conclude(result, locked, original_caveats, meta, "inconclusive", "data-unavailable", 0.35, None, ["The testes file has no data rows."], {"headers": []})
            return
        headers = list(rows[0].keys())

        def banned(name: str) -> bool:
            n = name.lower()
            return any(tok in n for tok in ("residual", "gsi", "relative", "ratio", "index"))

        mass_candidates = []
        for header in headers:
            if not header or banned(header):
                continue
            low = header.lower()
            if ("testis" in low or "testes" in low) and ("mass" in low or "weight" in low):
                mass_candidates.append(header)
        mass_col = None
        for header in mass_candidates:
            if "combined" in header.lower() or "total" in header.lower():
                mass_col = header
                break
        if mass_col is None and mass_candidates:
            mass_col = mass_candidates[0]

        by_squash = {squash(h): h for h in headers if h}
        species_col = None
        for token in SPECIES_PRIORITY:
            if squash(token) in by_squash:
                species_col = by_squash[squash(token)]
                break
        group_col = None
        for header in headers:
            if header and any(tok in header.lower() for tok in ("group", "clade", "shark", "chondrich", "class")):
                group_col = header
                break

        if mass_col is None:
            conclude(
                result,
                locked,
                original_caveats,
                meta,
                "inconclusive",
                "data-unavailable",
                0.35,
                None,
                ["No testes-mass column matched the pre-registered header rule.", "Headers: " + ", ".join(headers)],
                {"headers": headers},
            )
            return

        numeric_rows = 0
        positive_species = []
        zero_or_negative_species = set()
        nonfish_positive = []
        seen = set()
        per_species_max = {}
        for i, row in enumerate(rows):
            mass = parse_number(row.get(mass_col))
            if mass is None:
                continue
            numeric_rows += 1
            if species_col:
                species = " ".join((row.get(species_col) or "").split())
            else:
                species = f"row-{i+1}"
            if not species:
                species = f"row-{i+1}"
            group = (row.get(group_col) or "") if group_col else ""
            if any(tok in group.lower() for tok in NONFISH):
                if mass > 0:
                    nonfish_positive.append({"species": species, "group": group, "mass": mass})
                continue
            prev = per_species_max.get(species)
            if prev is None or mass > prev:
                per_species_max[species] = mass
            seen.add(species)

        for species, mass in per_species_max.items():
            if mass > 0:
                positive_species.append({"species": species, "max_testes_mass": mass})
            else:
                zero_or_negative_species.add(species)
        positive_species.sort(key=lambda r: r["species"])
        n_positive = len(positive_species)
        n_species_numeric = len(per_species_max)
        th = EXPECTED_THRESHOLDS["refute_min_species_positive_mass"]

        if numeric_rows == 0:
            verdict, reason, confidence = "inconclusive", "data-unavailable", 0.35
        elif n_positive >= th:
            verdict, reason, confidence = "refutes", None, 0.70
        elif n_positive >= 1:
            verdict, reason, confidence = "mixed", None, 0.40
        else:
            verdict, reason, confidence = "inconclusive", "other", 0.35

        measured = {
            "value": n_positive,
            "unit": "fish species with testes mass > 0",
            "n": n_species_numeric,
            "uncertainty": None,
            "extra": {
                "numeric_mass_rows": numeric_rows,
                "species_with_only_nonpositive_mass": len(zero_or_negative_species),
                "mass_column": mass_col,
                "species_column": species_col,
                "group_column": group_col,
                "headers": headers,
                "positive_species": positive_species,
                "nonfish_positive_rows": nonfish_positive,
                "min_positive_mass": min((r["max_testes_mass"] for r in positive_species), default=None),
                "max_positive_mass": max((r["max_testes_mass"] for r in positive_species), default=None),
            },
        }
        summary = [
            f"Fish species with a numeric testes mass: {n_species_numeric}. Species with mass > 0: {n_positive}. Numeric rows: {numeric_rows}.",
            f"Mass column: {mass_col}. Species column: {species_col or 'row index, because no species header matched'}.",
        ]
        conclude(result, locked, original_caveats, meta, verdict, reason, confidence, measured, summary, None)


def conclude(result, locked, original_caveats, meta, verdict, reason, confidence, measured, summary, extra):
    if measured is None:
        measured = {
            "value": None,
            "unit": "fish species with testes mass > 0",
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
            "id": "dryad-10.5061/dryad.fd3nq57-MPdata2018",
            "name": "Testes size, sperm competition and body mass in bony fish and sharks (MPdata2018.csv)",
            "landing_url": LANDING,
            "doi": "10.5061/dryad.fd3nq57",
            "version": "1",
            "license": "CC0-1.0",
            "files": [
                {
                    "name": "MPdata2018.csv",
                    "download_url": FILE_URL,
                    "final_url": meta["final_url"],
                    "retrieved_at": meta["retrieved_at"],
                    "byte_size": meta["byte_size"],
                    "sha256": meta["sha256"],
                }
            ],
            "role": "measured testes mass of fish species, used only as presence of a positive mass",
        }
    ]
    result["measured"] = measured
    result["method"] = (
        "Downloaded MPdata2018.csv from the Dryad API, hashed it, and selected the testes-mass column "
        "by the pre-registered header rule. Distinct fish species with a numeric mass strictly above zero "
        "were counted and compared with 10. No regression was fit, and the file's sperm-competition columns were not used."
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
