#!/usr/bin/env python3
"""Try to retrieve the caprification fruit-set article for aristotle-ha05-46.

If the article cannot be downloaded, the pre-registered verdict is data-unavailable.
No fruit-set number is taken from memory.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
URLS = [
    "https://www.mdpi.com/2311-7524/9/1/78/pdf?version=1674006898",
    "https://www.mdpi.com/2311-7524/9/1/78/htm",
    "https://doi.org/10.3390/horticulturae9010078",
]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def attempt(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/pdf,text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read(200_000)
            return {
                "url": url,
                "status": resp.status,
                "content_type": resp.headers.get("content-type"),
                "final_url": resp.geturl(),
                "bytes_read": len(body),
                "sha256_prefix": hashlib.sha256(body).hexdigest(),
                "looks_like_pdf": body.startswith(b"%PDF"),
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        snippet = exc.read(500)
        return {
            "url": url,
            "status": exc.code,
            "content_type": exc.headers.get("content-type") if exc.headers else None,
            "final_url": url,
            "bytes_read": len(snippet),
            "sha256_prefix": hashlib.sha256(snippet).hexdigest() if snippet else None,
            "looks_like_pdf": snippet.startswith(b"%PDF"),
            "error": "HTTPError",
        }
    except Exception as exc:
        return {"url": url, "status": None, "error": f"{type(exc).__name__}: {exc}", "looks_like_pdf": False}


def main() -> None:
    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tries = [attempt(url) for url in URLS]
    got_pdf = next((row for row in tries if row.get("looks_like_pdf") and row.get("status") == 200), None)
    if got_pdf:
        verdict, reason, confidence = "inconclusive", "other", 0.4
        note = "A PDF was retrieved but this run has no fruit-set parser for it, so the pre-registered comparison was not computed."
        data_kind = "none"
    else:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.8
        note = "None of the planned URLs returned the article. Fruit set was not read from anywhere else."
        data_kind = "none"
    measured = {
        "value": None,
        "unit": "percentage-point difference in fruit set, wasp treatment minus zero-wasp treatment",
        "n": 0,
        "uncertainty": None,
        "extra": {"attempts": tries, "retrieved_at": retrieved},
    }
    doc = json.loads(RESULT.read_text())
    doc["status"] = "complete"
    doc["datasets"] = [{
        "id": "mdpi-horticulturae-2023-caprifig-storage-10.3390-horticulturae9010078",
        "name": "Effects of caprifig storage on fruit productivity of Bursa Siyahi figs",
        "landing_url": "https://doi.org/10.3390/horticulturae9010078",
        "doi": "10.3390/horticulturae9010078",
        "version": None,
        "license": "open access; the file was not retrieved, so the licence text was not read from the PDF",
        "files": [],
        "role": "fruit set under caprification; not obtained",
    }]
    doc["method"] = (
        "Requested the MDPI PDF, the MDPI HTML and the DOI landing page. "
        "Each response status and content type was recorded. No article body was parsed, and no fruit-set percentage was supplied from any other source."
    )
    doc["measured"] = measured
    doc["verdict"] = verdict
    doc["reason"] = reason
    doc["confidence"] = confidence
    doc["data_kind"] = data_kind
    doc["results_summary"] = [note, "HTTP statuses: " + ", ".join(f"{row['status']} {row['url']}" for row in tries)]
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "statuses": [(row["status"], row["url"]) for row in tries]}))


if __name__ == "__main__":
    main()
