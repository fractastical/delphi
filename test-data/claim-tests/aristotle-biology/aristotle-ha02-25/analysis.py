#!/usr/bin/env python3
"""Recompute the pre-registered test of aristotle-ha02-25.

Downloads the open-access PDF of Szyndlar and Georgalis (Vertebrate Zoology
73, e101372) and reads trunk-vertebra counts from the authors' own
trunk+cloacal+caudal notation. One mean per species is compared with the
band 28-32.

Requires Python 3 and pypdf. The PDF is about 100 MB and is not committed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
RESULT_PATH = HERE / "result.json"
DERIVED = HERE / "derived"
CACHE = Path(os.environ.get("CLAIM_TEST_CACHE", "/tmp/aristotle-ha02-25"))
USER_AGENT = "Mozilla/5.0 (compatible; delphi-claim-test/1.0; +https://github.com/fractastical/delphi)"
PDF_URL = "https://vertebrate-zoology.arphahub.com/article/101372/download/pdf/913073"
EXPECTED_SHA = "012892cf3b2eb7bbb30852439c28fbee01eb50cff8c51d9e49881fd30bd2b8a7"
EXPECTED_SIZE = 97641788

STOP_GENERA = {
    "The", "This", "That", "These", "Those", "For", "From", "With", "Within",
    "Number", "Data", "Figure", "Table", "See", "Both", "After", "Before",
    "However", "Although", "Among", "Between", "Under", "Over", "During",
    "Total", "Trunk", "Caudal", "Cloacal", "General", "More", "Most", "Some",
    "Such", "Each", "Other", "Only", "Also", "Into", "About", "Above", "Below",
    "Their", "There", "Here", "When", "Where", "While", "Which", "What",
    "Copyright", "Creative", "Vertebrate", "Zoology", "Abstract",
}
BINOMIAL = re.compile(r"\b([A-Z][a-z]{3,})\s+([a-z]{4,})\b")
TRIPLE = re.compile(r"(\d{2,4})\+(\d{1,2})\+(\d{1,3}\+?)")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_pdf(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == EXPECTED_SIZE and sha256_file(dest) == EXPECTED_SHA:
        return
    req = urllib.request.Request(PDF_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as resp, dest.open("wb") as out:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)


def pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        text = text.replace("\u00ad", "")
        text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
        text = re.sub(r"\s+", " ", text)
        parts.append(text)
    return " ".join(parts)


def parse_counts(text: str) -> tuple[dict, list]:
    by_species: dict[tuple[str, str], list[int]] = {}
    skipped = []
    for match in TRIPLE.finditer(text):
        trunk = int(match.group(1))
        before = text[max(0, match.start() - 80):match.start()]
        if "?" in before[-15:]:
            skipped.append({"trunk": trunk, "reason": "author marked the count uncertain"})
            continue
        if "for instance" in before.lower():
            skipped.append({"trunk": trunk, "reason": "instructional example"})
            continue
        window = text[max(0, match.start() - 220):match.start()]
        found = [m for m in BINOMIAL.finditer(window) if m.group(1) not in STOP_GENERA]
        if not found:
            skipped.append({"trunk": trunk, "reason": "no binomial in the preceding window"})
            continue
        genus, epithet = found[-1].group(1), found[-1].group(2)
        by_species.setdefault((genus, epithet), []).append(trunk)
    return by_species, skipped


def main() -> None:
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = json.loads(RESULT_PATH.read_text())
    dest = CACHE / "atlas.pdf"
    fetch_pdf(dest)
    size = dest.stat().st_size
    digest = sha256_file(dest)
    if size != EXPECTED_SIZE or digest != EXPECTED_SHA:
        result["status"] = "complete"
        result["verdict"] = "inconclusive"
        result["reason"] = "data-unavailable"
        result["data_kind"] = "none"
        result["confidence"] = 0.35
        result["method"] = "The PDF download did not match the SHA-256 of the first retrieval."
        result["measured"] = {
            "value": None,
            "unit": "median trunk vertebrae per species",
            "n": 0,
            "uncertainty": "checksum mismatch",
            "extra": {"byte_size": size, "sha256": digest},
        }
        RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print("inconclusive: checksum mismatch")
        return

    by_species, skipped = parse_counts(pdf_text(dest))
    rows = []
    for (genus, epithet), trunks in sorted(by_species.items()):
        rows.append({
            "genus": genus,
            "species": epithet,
            "n_skeletons": len(trunks),
            "mean_trunk": sum(trunks) / len(trunks),
            "min_trunk": min(trunks),
            "max_trunk": max(trunks),
        })
    means = [row["mean_trunk"] for row in rows]
    n = len(means)
    if n == 0:
        median = None
        in_band = 0
        fraction = None
    else:
        median = float(statistics.median(means))
        in_band = sum(1 for value in means if 28 <= value <= 32)
        fraction = in_band / n
    if n < 10:
        verdict = "inconclusive"
        reason = "underpowered"
        confidence = 0.4
    elif median is not None and 28 <= median <= 32 and fraction >= 0.80:
        verdict = "supports"
        reason = None
        confidence = 0.8 if n >= 30 else 0.6
    elif median is not None and (median < 28 or median > 32 or fraction < 0.50):
        verdict = "refutes"
        reason = None
        confidence = 0.8 if n >= 30 else 0.6
    else:
        verdict = "mixed"
        reason = None
        confidence = 0.5

    # Sensitivity stated in the interpretation: atlas and axis may lack ribs.
    minus_two_in_band = sum(1 for value in means if 28 <= (value - 2) <= 32)
    measured = {
        "value": None if median is None else round(median, 2),
        "unit": "median of species-mean trunk vertebral counts",
        "n": n,
        "uncertainty": None if not means else f"species means {min(means):.0f} to {max(means):.0f}; {in_band}/{n} inside 28-32",
        "extra": {
            "fraction_inside_28_32": None if fraction is None else round(fraction, 4),
            "n_inside_28_32": in_band,
            "n_skeletons": sum(row["n_skeletons"] for row in rows),
            "n_skipped": len(skipped),
            "skip_reasons": {
                reason_name: sum(1 for item in skipped if item["reason"] == reason_name)
                for reason_name in sorted({item["reason"] for item in skipped})
            },
            "species_means_minus_2_inside_28_32": minus_two_in_band,
            "smallest_species_means": sorted(rows, key=lambda row: row["mean_trunk"])[:8],
        },
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    import csv
    with (DERIVED / "species-trunk-counts.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["genus", "species", "n_skeletons", "mean_trunk", "min_trunk", "max_trunk"])
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item["mean_trunk"]):
            writer.writerow({**row, "mean_trunk": round(row["mean_trunk"], 2)})
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
        "Downloaded the PDF and checked its SHA-256. Text was extracted with pypdf. "
        "Counts use the paper's notation trunk+cloacal+caudal. A count was dropped if "
        "a question mark in the preceding 15 characters marked it uncertain, or if it "
        "sat in an instructional 'for instance' sentence. The binomial in the preceding "
        "220 characters, ignoring ordinary English capitals, received the count. "
        "Species means were compared with the pre-registered band 28-32."
    )
    result["results_summary"] = [
        f"{n} species, {measured['extra']['n_skeletons']} skeleton counts, median species-mean trunk count {measured['value']}.",
        f"Species inside 28-32: {in_band} of {n}. Smallest species mean: "
        + (
            f"{measured['extra']['smallest_species_means'][0]['genus']} "
            f"{measured['extra']['smallest_species_means'][0]['species']} "
            f"{measured['extra']['smallest_species_means'][0]['mean_trunk']:.0f}."
            if rows else "none."
        ),
        f"Subtracting 2 for an atlas and axis without ribs still leaves {minus_two_in_band} species inside 28-32.",
        f"Skipped triples: {measured['extra']['skip_reasons']}.",
    ]
    caveats = list(result.get("caveats") or [])
    added = (
        "The atlas counts non-caenophidian snakes, not every snake. Trunk counts "
        "include the atlas and axis. Uncertain counts marked with a question mark "
        "were not used. Literature ranges written as prose ('155-162 trunk vertebrae') "
        "were not parsed; only the plus-notation skeleton counts were."
    )
    if added not in caveats:
        caveats.append(added)
    result["caveats"] = caveats
    result["datasets"] = [
        {
            "id": "szyndlar-georgalis-2023-vz-73-e101372-pdf",
            "name": "An illustrated atlas of the vertebral morphology of extant non-caenophidian snakes",
            "landing_url": "https://doi.org/10.3897/vz.73.e101372",
            "doi": "10.3897/vz.73.e101372",
            "version": "Vertebrate Zoology 73: 717-886 (2023)",
            "license": "CC BY 4.0",
            "files": [
                {
                    "name": "vz.73.e101372.pdf",
                    "download_url": PDF_URL,
                    "retrieved_at": retrieved_at,
                    "byte_size": size,
                    "sha256": digest,
                }
            ],
            "role": "per-skeleton trunk, cloacal and caudal vertebral counts for non-caenophidian snakes",
        }
    ]
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "verdict": verdict,
        "confidence": confidence,
        "n": n,
        "median": measured["value"],
        "in_band": in_band,
        "smallest": measured["extra"]["smallest_species_means"][:3],
    }, indent=2))


if __name__ == "__main__":
    main()
