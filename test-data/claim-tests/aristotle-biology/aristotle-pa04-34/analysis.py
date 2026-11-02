#!/usr/bin/env python3
"""ZFIN anatomy term 'testis' against aristotle-pa04-34.

Rules are those committed in result.json. Standard library only.
The dataset can refute the claim. It cannot support it.
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
SYNONYM_URL = "https://zfin.org/downloads/anatomy_synonyms.txt"
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


def table(path: Path) -> list[list[str]]:
    return [line.split("\t") for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    try:
        anatomy_info = fetch(ANATOMY_URL, DATA / "anatomy_item.txt")
    except Exception as exc:
        write_unavailable(str(exc), None, None)
        return
    synonym_info = None
    synonym_error = None
    try:
        synonym_info = fetch(SYNONYM_URL, DATA / "anatomy_synonyms.txt")
    except Exception as exc:
        synonym_error = str(exc)

    exact = []
    for cols in table(DATA / "anatomy_item.txt"):
        if len(cols) >= 2 and cols[1].strip().lower() == "testis":
            exact.append({
                "anatomy_id": cols[0],
                "anatomy_name": cols[1],
                "start_stage_id": cols[2] if len(cols) > 2 else None,
                "end_stage_id": cols[3] if len(cols) > 3 else None,
            })
    synonyms = []
    if synonym_info:
        for cols in table(DATA / "anatomy_synonyms.txt"):
            if any(col.strip().lower() == "testis" for col in cols):
                synonyms.append({"columns": cols})

    if exact or synonyms:
        verdict, reason, confidence = "refutes", None, 0.8 if exact else 0.7
        data_kind = "biological"
    else:
        verdict, reason, confidence = "inconclusive", "other", 0.55
        data_kind = "biological"

    measured = {
        "value": len(exact) + len(synonyms),
        "unit": "ZFIN anatomy rows whose name or synonym is exactly testis",
        "n": 1,
        "uncertainty": "exact string match; one species, Danio rerio",
        "extra": {
            "exact_name_rows": exact,
            "synonym_rows": synonyms[:20],
            "n_synonym_rows": len(synonyms),
            "synonym_file_error": synonym_error,
        },
    }
    files = [{"name": "anatomy_item.txt", **anatomy_info}]
    if synonym_info:
        files.append({"name": "anatomy_synonyms.txt", **synonym_info})
    doc = json.loads(RESULT.read_text())
    doc["status"] = "complete"
    doc["datasets"] = [{
        "id": "zfin-anatomy-item-testis",
        "name": "ZFIN zebrafish anatomy terms and synonyms",
        "landing_url": "https://zfin.org/downloads",
        "doi": None,
        "version": "downloaded at analysis time; ZFIN rebuilds these files daily",
        "license": "ZFIN public download; the downloads page asks for attribution and does not name an SPDX licence",
        "files": files,
        "role": "whether the zebrafish anatomical record contains a testis",
    }]
    doc["method"] = (
        "Downloaded the ZFIN anatomy-item file and the synonym file, hashed them, and searched for the exact "
        "string testis. An exact anatomy name refutes the claim that no fish has testicles internally. "
        "A missing term would be inconclusive, because the file does not record absences. Snakes were not in the file and were not scored."
    )
    doc["measured"] = measured
    doc["verdict"] = verdict
    doc["confidence"] = confidence
    doc["data_kind"] = data_kind
    doc["results_summary"] = [
        f"Exact anatomy-name rows equal to testis: {len(exact)}. Synonym rows containing that exact string: {len(synonyms)}.",
        "One fish with a testis refutes 'no fish has testicles, either externally or internally'. The serpents clause was not tested.",
    ]
    if reason:
        doc["reason"] = reason
    else:
        doc.pop("reason", None)
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "exact": len(exact), "synonyms": len(synonyms)}))


def write_unavailable(message: str, anatomy_info, synonym_info) -> None:
    doc = json.loads(RESULT.read_text())
    doc["status"] = "complete"
    doc["verdict"] = "inconclusive"
    doc["reason"] = "data-unavailable"
    doc["confidence"] = 0.8
    doc["data_kind"] = "none"
    doc["method"] = "The anatomy file could not be downloaded. No term was scored."
    doc["measured"] = {"value": None, "unit": "ZFIN testis rows", "n": 0, "uncertainty": None, "extra": {"error": message}}
    doc["results_summary"] = [message]
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps({"verdict": "inconclusive", "reason": "data-unavailable"}))


if __name__ == "__main__":
    main()
