#!/usr/bin/env python3
"""Spinneret-atlas deposit against aristotle-ha09-25.

The pre-registered measurement is a species-by-origin table. Image stacks are not downloaded.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
API = "https://ckan.fdm.uni-greifswald.de/api/3/action/package_show?id=anatomical-atlas-spider-spinnerets"
UA = "delphisci-claim-test"


def fetch_bytes(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read(), resp.headers.get("content-type", "")


def main() -> None:
    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw, _ctype = fetch_bytes(API)
    manifest = json.loads(raw)
    resources = (manifest.get("result") or {}).get("resources") or []
    inventory = []
    for res in resources:
        inventory.append({
            "name": res.get("name"),
            "format": res.get("format"),
            "size": res.get("size"),
            "url": res.get("url"),
            "mimetype": res.get("mimetype"),
        })
    small = [row for row in inventory if isinstance(row["size"], int) and row["size"] < 200_000]
    pdf_info = None
    pdf_text = ""
    for row in small:
        url = row.get("url")
        if not url:
            continue
        dest = DATA / "CT-Settings.pdf"
        DATA.mkdir(parents=True, exist_ok=True)
        blob, _ = fetch_bytes(url)
        dest.write_bytes(blob)
        pdf_info = {
            "name": row["name"],
            "download_url": url,
            "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
        }
        reader = PdfReader(str(dest))
        pdf_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        break
    low = pdf_text.lower()
    origin_terms = ("silk gland", "internal gland", "surface slough", "bark")
    origin_present = {term: term in low for term in origin_terms}
    # Scanner settings name species but do not code where silk comes from.
    has_origin_table = origin_present["silk gland"] or origin_present["surface slough"]
    n_zip = sum(1 for row in inventory if (row["format"] or "").upper() == "ZIP")
    if has_origin_table:
        verdict, reason, confidence, data_kind = "inconclusive", "other", 0.4, "biological"
        note = (
            "The small PDF mentions silk origin. This script does not score a coding it was not built to tabulate. See deviations."
        )
    else:
        verdict, reason, confidence, data_kind = "inconclusive", "data-unavailable", 0.85, "none"
        small_word = "is" if len(small) == 1 else "are"
        note = (
            f"The deposit lists {len(inventory)} resources, of which {n_zip} are ZIP image stacks "
            f"and {len(small)} {small_word} under 200 KB. The small file does not code silk as an internal gland versus a surface slough for five species."
        )
    measured = {
        "value": None,
        "unit": "species coded for silk origin",
        "n": 0,
        "uncertainty": None,
        "extra": {
            "n_resources": len(inventory),
            "n_zip": sum(1 for row in inventory if (row["format"] or "").upper() == "ZIP"),
            "formats": sorted({(row["format"] or "").upper() for row in inventory}),
            "small_resources": [{k: row[k] for k in ("name", "format", "size")} for row in small],
            "pdf_text_chars": len(pdf_text),
            "pdf_origin_terms_present": origin_present,
            "pdf_mentions_spinneret": "spinneret" in low,
            "pdf_is_scanner_settings": "voltage" in low and "pixel size" in low,
        },
    }
    doc = json.loads(RESULT.read_text())
    doc["status"] = "complete"
    files = [{
        "name": "package_show.json",
        "download_url": API,
        "retrieved_at": retrieved,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }]
    if pdf_info:
        files.append(pdf_info)
    doc["datasets"] = [{
        "id": "greifswald-ckan-anatomical-atlas-spider-spinnerets",
        "name": "Anatomical atlas of the spider spinneret muscle system",
        "landing_url": "https://ckan.fdm.uni-greifswald.de/dataset/anatomical-atlas-spider-spinnerets",
        "doi": (manifest.get("result") or {}).get("doi"),
        "version": (manifest.get("result") or {}).get("metadata_modified"),
        "license": (manifest.get("result") or {}).get("license_title"),
        "files": files,
        "role": "public deposit checked for a table of silk origin; image stacks were not measured",
    }]
    doc["method"] = (
        "Read the CKAN package manifest and hashed it. Resources of 200 KB or more were not downloaded; the ZIP resources are microCT stacks above 5 MB. "
        "The one resource under 200 KB was downloaded, hashed, and its text extracted. "
        "It was accepted as a measurement only if it coded silk origin for at least five species. It did not, so the pre-registered data-unavailable rule applies."
    )
    doc["measured"] = measured
    doc["verdict"] = verdict
    doc["reason"] = reason
    doc["confidence"] = confidence
    doc["data_kind"] = data_kind
    doc["results_summary"] = [note]
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({"measured": measured, "inventory": inventory}, indent=2) + "\n")
    # inventory can be large; keep the derived file, but drop urls from a size check later
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "n_resources": len(inventory), "pdf_chars": len(pdf_text), "silk_gland": "silk gland" in low}))


if __name__ == "__main__":
    main()
