#!/usr/bin/env python3
"""Recompute the pre-registered test of aristotle-ha03-09.

Downloads the Human Protein Atlas v25.1 normal-tissue immunohistochemistry
table and the standard cell-type codebook. Scores only endothelial cells in
brain tissues named in that codebook, for PECAM1, VWF and CD34.

Requires Python 3, pandas, and a network connection on a cold cache.
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
CACHE = Path(os.environ.get("CLAIM_TEST_CACHE", "/tmp/aristotle-ha03-09"))
USER_AGENT = "delphi-claim-test/1.0 (research; +https://github.com/fractastical/delphi)"

DATA_URL = "https://www.proteinatlas.org/download/tsv/normal_ihc_data.tsv.zip"
CODEBOOK_URL = "https://www.proteinatlas.org/download/tsv/normal_ihc_cell_types.tsv.zip"

EXPECTED = {
    "normal_ihc_data.tsv.zip": {
        "url": DATA_URL,
        "byte_size": 5732831,
        "sha256": "fa2315e5a53ecffd9427a5bfe219c8cc41b54089ef6f6be7b5d79b5455e0677f",
    },
    "normal_ihc_cell_types.tsv.zip": {
        "url": CODEBOOK_URL,
        "byte_size": 1115,
        "sha256": "04fc18dacc29c3bf5ad6440e46990a97e8cb3ed2b4b96d62102d5062c9edd011",
    },
}

MARKERS = {
    "ENSG00000261371": "PECAM1",
    "ENSG00000110799": "VWF",
    "ENSG00000174059": "CD34",
}
RELIABLE = {"Enhanced", "Supported", "Approved"}
DETECTED = {"Low", "Medium", "High"}
EXCLUDED_SUBSTRINGS = (
    "pituitary",
    "choroid",
    "meninges",
    "pia",
    "dura",
    "arachnoid",
    "spinal cord",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, dest: Path) -> bytes:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return data


def read_zip_tsv(blob: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        name = archive.namelist()[0]
        return pd.read_csv(archive.open(name), sep="\t", dtype=str)


def excluded_tissue(name: str) -> bool:
    text = name.casefold()
    return any(piece in text for piece in EXCLUDED_SUBSTRINGS)


def main() -> None:
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = json.loads(RESULT_PATH.read_text())
    CACHE.mkdir(parents=True, exist_ok=True)
    blobs = {}
    mismatch = False
    for name, meta in EXPECTED.items():
        blob = fetch(meta["url"], CACHE / name)
        blobs[name] = blob
        if len(blob) != meta["byte_size"] or sha256_bytes(blob) != meta["sha256"]:
            mismatch = True

    if mismatch:
        result["status"] = "complete"
        result["verdict"] = "inconclusive"
        result["reason"] = "data-unavailable"
        result["data_kind"] = "none"
        result["confidence"] = 0.35
        result["method"] = (
            "The Human Protein Atlas download did not match the SHA-256 recorded "
            "at first retrieval, so the pre-registered rule stops the test."
        )
        result["measured"] = {
            "value": None,
            "unit": "endothelial marker genes detected inside a brain tissue",
            "n": 0,
            "uncertainty": "checksum mismatch",
            "extra": {},
        }
        RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print("inconclusive: checksum mismatch")
        return

    codebook = read_zip_tsv(blobs["normal_ihc_cell_types.tsv.zip"])
    data = read_zip_tsv(blobs["normal_ihc_data.tsv.zip"])
    brain = codebook[codebook["Organ"].str.casefold() == "brain"].copy()
    brain = brain[~brain["Tissue"].map(excluded_tissue)]
    included_tissues = sorted(brain["Tissue"].unique())

    marker_rows = data[data["Gene"].isin(MARKERS)].copy()
    in_brain = marker_rows[marker_rows["Tissue"].isin(included_tissues)].copy()
    endothelial = in_brain[
        in_brain["Cell type"].str.contains("endothelial", case=False, na=False)
    ].copy()
    counted = endothelial[endothelial["Reliability"].isin(RELIABLE)].copy()
    refuting = counted[counted["Level"].isin(DETECTED)].copy()

    genes_hit = sorted(refuting["Gene"].map(MARKERS).unique())
    levels_by_gene = {}
    for gene_id, symbol in MARKERS.items():
        rows = counted[counted["Gene"] == gene_id]
        levels_by_gene[symbol] = sorted(rows["Level"].unique()) if len(rows) else []

    strong = []
    low_only = []
    for symbol in genes_hit:
        gene_levels = set(refuting.loc[refuting["Gene"].map(MARKERS) == symbol, "Level"])
        if gene_levels & {"Medium", "High"}:
            strong.append(symbol)
        elif "Low" in gene_levels:
            low_only.append(symbol)

    if len(counted) == 0:
        verdict = "inconclusive"
        reason = "underpowered"
        confidence = 0.4
        value = 0
    elif len(refuting) == 0:
        verdict = "inconclusive"
        reason = "underpowered"
        confidence = 0.4
        value = 0
    else:
        verdict = "refutes"
        reason = None
        value = len(genes_hit)
        if len(strong) >= 2:
            confidence = 0.8
        elif len(strong) == 1:
            confidence = 0.7
        else:
            confidence = 0.55

    def records(frame: pd.DataFrame) -> list[dict]:
        keep = ["Gene", "Gene name", "Tissue", "Cell type", "Level", "Reliability"]
        return frame[keep].sort_values(["Gene name", "Tissue", "Cell type"]).to_dict(orient="records")

    measured = {
        "value": value,
        "unit": "endothelial marker genes detected inside a brain tissue, of 3",
        "n": int(len(counted)),
        "uncertainty": (
            "no counted endothelial rows"
            if len(counted) == 0
            else "; ".join(
                f"{symbol}={','.join(levels_by_gene[symbol]) or 'no counted row'}"
                for symbol in ("PECAM1", "VWF", "CD34")
            )
        ),
        "extra": {
            "included_tissues": included_tissues,
            "genes_detected": genes_hit,
            "genes_medium_or_high": strong,
            "genes_low_only": low_only,
            "counted_endothelial_rows": records(counted),
            "other_marker_rows_in_included_tissues": records(in_brain),
        },
    }

    DERIVED.mkdir(parents=True, exist_ok=True)
    in_brain.sort_values(["Gene name", "Tissue", "Cell type"]).to_csv(
        DERIVED / "brain-marker-rows.csv", index=False
    )
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")

    prior = result.get("datasets") or []
    if prior:
        retrieved_at = prior[0]["files"][0].get("retrieved_at", retrieved_at)

    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = confidence
    result["data_kind"] = "biological" if verdict != "inconclusive" else "none"
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["measured"] = measured
    result["method"] = (
        "Downloaded Human Protein Atlas normal_ihc_data.tsv.zip (version 25.1) and the "
        "standard cell-type codebook, and checked both SHA-256 values. Brain tissues are "
        "those with Organ = Brain in the codebook, minus pituitary, choroid plexus, "
        "meninges and spinal cord. Rows for the three pre-registered Ensembl genes were "
        "kept when the cell type contained 'endothelial' and reliability was Enhanced, "
        "Supported or Approved. Any Low, Medium or High level refutes the universal; "
        "Not detected does not support it."
    )
    if verdict == "refutes":
        bits = ", ".join(
            f"{row['Gene name']} {row['Level']} in {row['Tissue']} {row['Cell type']} ({row['Reliability']})"
            for row in records(refuting)
        )
        summary = [
            f"Refuting rows: {bits}.",
            f"{len(strong)} of the three markers are Medium or High in cerebral-cortex endothelial cells.",
            "Other cell types in the included brain tissues are Not detected for these three proteins, so the positive stain is the endothelial row.",
        ]
    else:
        summary = [
            f"Counted endothelial rows: {len(counted)}. Detected rows: {len(refuting)}.",
            "The pre-registered rule does not treat a negative or missing stain as support for a universal claim.",
        ]
    result["results_summary"] = summary
    caveats = list(result.get("caveats") or [])
    added = (
        "The standard codebook annotates endothelial cells for the brain only in the "
        "cerebral cortex. Cerebellum, caudate and hippocampus are in the codebook but "
        "have no endothelial row. Staining of glial cells, neurons, neuropil and "
        "Purkinje cells for these three genes is Not detected and is not used as the verdict."
    )
    if verdict == "refutes" and added not in caveats:
        caveats.append(added)
    result["caveats"] = caveats
    result["datasets"] = [
        {
            "id": "human-protein-atlas-v25.1-normal-ihc",
            "name": "Human Protein Atlas normal tissue immunohistochemistry, version 25.1",
            "landing_url": "https://www.proteinatlas.org/humanproteome/tissue/data",
            "doi": None,
            "version": "25.1",
            "license": "CC BY 4.0",
            "files": [
                {
                    "name": name,
                    "download_url": meta["url"],
                    "retrieved_at": retrieved_at,
                    "byte_size": len(blobs[name]),
                    "sha256": sha256_bytes(blobs[name]),
                }
                for name, meta in EXPECTED.items()
            ],
            "role": "cell-type-resolved staining levels of PECAM1, VWF and CD34 in normal human brain tissues",
        }
    ]
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "verdict": verdict,
        "confidence": confidence,
        "reason": reason,
        "value": value,
        "n": int(len(counted)),
        "genes_medium_or_high": strong,
        "uncertainty": measured["uncertainty"],
    }, indent=2))


if __name__ == "__main__":
    main()
