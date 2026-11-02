#!/usr/bin/env python3
"""Recompute the pre-registered test of aristotle-ha08-13.

Reads Anguilla anguilla maximum longevity from FishBase species snapshot
v26.06 and from AnAge build 15. A source supports the claim when its maximum
is at least 7 years.

Requires Python 3, pandas and pyarrow. Downloads are not committed.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RESULT_PATH = HERE / "result.json"
DERIVED = HERE / "derived"
CACHE = Path(os.environ.get("CLAIM_TEST_CACHE", "/tmp/aristotle-ha08-13"))
USER_AGENT = "delphi-claim-test/1.0 (research; +https://github.com/fractastical/delphi)"

FISHBASE_URL = "https://data.source.coop/cboettig/fishbase/fb/v26.06/parquet/species.parquet"
FISHBASE_SHA = "87c99bc57f368c6102ea4042e7e6c8019c7405d5a352ead840f06244609ab101"
FISHBASE_SIZE = 3469911
ANAGE_URL = "https://genomics.senescence.info/species/dataset.zip"
ANAGE_SHA = "e3ddb66e32e973a79932859ba53013e8f60d957c6ec01c6eb573e3ea3018d630"
ANAGE_SIZE = 169150


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, dest: Path) -> bytes:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        data = dest.read_bytes()
        return data
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return data


def source_verdict(value):
    if value is None:
        return "missing"
    if value >= 7:
        return "supports"
    return "refutes"


def main() -> None:
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = json.loads(RESULT_PATH.read_text())
    CACHE.mkdir(parents=True, exist_ok=True)
    fish_path = CACHE / "species.parquet"
    # Reuse the snapshot already fetched for the migration test when the hash matches.
    shared = Path("/tmp/aristotle-ha06-26/species.parquet")
    if not fish_path.exists() and shared.exists() and sha256_bytes(shared.read_bytes()) == FISHBASE_SHA:
        fish_path.write_bytes(shared.read_bytes())
    fish_bytes = fetch(FISHBASE_URL, fish_path)
    anage_bytes = fetch(ANAGE_URL, CACHE / "anage.zip")
    fish_ok = len(fish_bytes) == FISHBASE_SIZE and sha256_bytes(fish_bytes) == FISHBASE_SHA
    anage_ok = len(anage_bytes) == ANAGE_SIZE and sha256_bytes(anage_bytes) == ANAGE_SHA
    if not fish_ok and not anage_ok:
        result.update({
            "status": "complete",
            "verdict": "inconclusive",
            "reason": "data-unavailable",
            "data_kind": "none",
            "confidence": 0.35,
            "method": "Neither longevity file matched the SHA-256 of the first retrieval.",
            "measured": {"value": None, "unit": "years", "n": 0, "uncertainty": "checksum mismatch", "extra": {}},
        })
        RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print("inconclusive: both checksums failed")
        return

    fish_value = None
    fish_detail = None
    if fish_ok:
        frame = pd.read_parquet(
            BytesIO(fish_bytes),
            columns=["Genus", "Species", "LongevityWild", "LongevityCaptive", "LongevityWildRef", "LongevityCapRef"],
        )
        hit = frame[(frame["Genus"] == "Anguilla") & (frame["Species"] == "anguilla")]
        if len(hit) == 1:
            row = hit.iloc[0]
            wild = None if pd.isna(row["LongevityWild"]) else float(row["LongevityWild"])
            captive = None if pd.isna(row["LongevityCaptive"]) else float(row["LongevityCaptive"])
            present = [value for value in (wild, captive) if value is not None]
            fish_value = max(present) if present else None
            fish_detail = {
                "wild_years": wild,
                "captive_years": captive,
                "wild_ref": None if pd.isna(row["LongevityWildRef"]) else int(row["LongevityWildRef"]),
                "captive_ref": None if pd.isna(row["LongevityCapRef"]) else int(row["LongevityCapRef"]),
                "maximum_years": fish_value,
            }
    anage_value = None
    anage_detail = None
    if anage_ok:
        with zipfile.ZipFile(BytesIO(anage_bytes)) as archive:
            table = pd.read_csv(archive.open("anage_data.txt"), sep="\t", dtype=str)
        longevity_col = "Maximum longevity (yrs)"
        if longevity_col not in table.columns:
            matches = [col for col in table.columns if "longevity" in col.lower() and "yr" in col.lower()]
            longevity_col = matches[0] if len(matches) == 1 else None
        if longevity_col:
            hit = table[(table["Genus"] == "Anguilla") & (table["Species"] == "anguilla")]
            if len(hit) == 1:
                row = hit.iloc[0]
                raw = row[longevity_col]
                anage_value = None if pd.isna(raw) or str(raw).strip() == "" else float(raw)
                anage_detail = {
                    "maximum_years": anage_value,
                    "column": longevity_col,
                    "common_name": row.get("Common name"),
                    "specimen_origin": row.get("Specimen origin"),
                    "sample_size": row.get("Sample size"),
                    "data_quality": row.get("Data quality"),
                    "references": row.get("References"),
                    "hagrid": row.get("HAGRID"),
                }

    fish_component = source_verdict(fish_value) if fish_ok else "missing"
    anage_component = source_verdict(anage_value) if anage_ok else "missing"
    present = [(name, component, value) for name, component, value in (
        ("fishbase", fish_component, fish_value),
        ("anage", anage_component, anage_value),
    ) if component != "missing"]
    if not present:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.35
    elif len(present) == 1:
        verdict = present[0][1]
        reason = None
        confidence = 0.6
    elif present[0][1] == present[1][1] == "supports":
        verdict, reason, confidence = "supports", None, 0.75
    elif present[0][1] == present[1][1] == "refutes":
        verdict, reason, confidence = "refutes", None, 0.75
    else:
        verdict, reason, confidence = "mixed", None, 0.5

    source_values = [value for _, _, value in present]
    measured = {
        "value": None if not source_values else min(source_values),
        "unit": "years, lower of the source maxima that could be read",
        "n": len(present),
        "uncertainty": (
            f"FishBase maximum {fish_value} (wild {None if not fish_detail else fish_detail['wild_years']}, "
            f"captive {None if not fish_detail else fish_detail['captive_years']}); AnAge {anage_value}"
        ),
        "extra": {
            "fishbase": fish_detail,
            "fishbase_component": fish_component,
            "anage": anage_detail,
            "anage_component": anage_component,
        },
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    prior = result.get("datasets") or []
    if prior:
        retrieved_at = prior[0]["files"][0].get("retrieved_at", retrieved_at)
    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = confidence
    result["data_kind"] = "none" if verdict == "inconclusive" else "biological"
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["measured"] = measured
    result["method"] = (
        "Downloaded the FishBase v26.06 species parquet and the AnAge build-15 zip and "
        "checked both SHA-256 values. For the single Anguilla anguilla row, the FishBase "
        "maximum is the greater of LongevityWild and LongevityCaptive. The AnAge maximum "
        "is Maximum longevity (yrs). A source supports the claim at 7 years or more and "
        "refutes it below 7. The two sources are combined as pre-registered."
    )
    result["results_summary"] = [
        f"FishBase: wild {None if not fish_detail else fish_detail['wild_years']} years "
        f"(ref {None if not fish_detail else fish_detail['wild_ref']}), "
        f"captive {None if not fish_detail else fish_detail['captive_years']} years "
        f"(ref {None if not fish_detail else fish_detail['captive_ref']}), "
        f"maximum {fish_value}, component {fish_component}.",
        f"AnAge build 15: maximum {anage_value} years, origin "
        f"{None if not anage_detail else anage_detail['specimen_origin']}, "
        f"quality {None if not anage_detail else anage_detail['data_quality']}, "
        f"component {anage_component}.",
        f"Verdict {verdict}. The lower of the two maxima is {measured['value']} years.",
    ]
    caveats = list(result.get("caveats") or [])
    added = (
        "AnAge build 15 (3 July 2023) records the European eel maximum as a captivity "
        "record with sample size 'small' and data quality 'acceptable'. FishBase records "
        "separate wild and captive maxima. Neither database is an age-at-death distribution. "
        "Reference titles were not resolved beyond the id numbers stored in each file."
    )
    if added not in caveats and verdict != "inconclusive":
        caveats.append(added)
    result["caveats"] = caveats
    datasets = []
    if fish_ok:
        datasets.append({
            "id": "fishbase-rfishbase-parquet-v26.06-species",
            "name": "FishBase backend snapshot v26.06, species table",
            "landing_url": "https://source.coop/cboettig/fishbase",
            "doi": None,
            "version": "fb/v26.06",
            "license": "CC BY-NC 4.0",
            "files": [{
                "name": "species.parquet",
                "download_url": FISHBASE_URL,
                "retrieved_at": retrieved_at,
                "byte_size": len(fish_bytes),
                "sha256": sha256_bytes(fish_bytes),
            }],
            "role": "wild and captive maximum longevity, in years, for Anguilla anguilla",
        })
    if anage_ok:
        datasets.append({
            "id": "anage-build-dataset-zip",
            "name": "AnAge build 15 species dataset",
            "landing_url": "https://genomics.senescence.info/species/dataset.zip",
            "doi": None,
            "version": "build 15 (2023-07-03)",
            "license": "free to use under Human Ageing Genomic Resources conditions",
            "files": [{
                "name": "dataset.zip",
                "download_url": ANAGE_URL,
                "retrieved_at": retrieved_at,
                "byte_size": len(anage_bytes),
                "sha256": sha256_bytes(anage_bytes),
            }],
            "role": "maximum longevity in years for Anguilla anguilla",
        })
    result["datasets"] = datasets
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "verdict": verdict,
        "confidence": confidence,
        "value": measured["value"],
        "fish": fish_value,
        "anage": anage_value,
    }, indent=2))


if __name__ == "__main__":
    main()
