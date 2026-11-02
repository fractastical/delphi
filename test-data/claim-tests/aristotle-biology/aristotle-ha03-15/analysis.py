#!/usr/bin/env python3
"""Elephant toenail donors in an open-access paper against aristotle-ha03-15.

Rules are those committed in result.json. Standard library only.
This dataset can refute the claim. It cannot support it.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11295213/fullTextXML"
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


def local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def text_of(el) -> str:
    # Footnote markers live in xref/sup. They are not part of the donor's name.
    skip = {"xref", "sup", "fn"}
    parts = []

    def walk(node, at_root: bool) -> None:
        if not at_root and local(node.tag) in skip:
            return
        if node.text:
            parts.append(node.text)
        for child in list(node):
            walk(child, False)
            if child.tail:
                parts.append(child.tail)

    walk(el, True)
    return " ".join(" ".join(parts).split())


def elephant_genus(cell: str) -> str | None:
    low = cell.lower()
    if "loxodonta" in low or "l. africana" in low:
        return "Loxodonta"
    if "elephas" in low or "e. maximus" in low:
        return "Elephas"
    return None


def main() -> None:
    info = fetch(URL, DATA / "PMC11295213.fullTextXML")
    root = ET.parse(DATA / "PMC11295213.fullTextXML").getroot()
    donors = []
    for wrap in (el for el in root.iter() if local(el.tag) == "table-wrap"):
        caption = " ".join(text_of(el) for el in wrap.iter() if local(el.tag) in {"caption", "title", "label"})
        if "toenail" not in caption.lower() and "toe nail" not in caption.lower():
            continue
        table = next((el for el in wrap.iter() if local(el.tag) == "table"), None)
        if table is None:
            continue
        for tr in (el for el in table.iter() if local(el.tag) == "tr"):
            cells = [text_of(td) for td in list(tr) if local(td.tag) in {"td", "th"}]
            genera = [elephant_genus(cell) for cell in cells]
            genera = [g for g in genera if g]
            if not genera:
                continue
            donors.append({
                "individual": cells[0] if cells else None,
                "genus": genera[0],
                "species_cell": next(cell for cell in cells if elephant_genus(cell)),
            })
        if donors:
            break
    n = len(donors)
    genera = sorted({row["genus"] for row in donors})
    if n >= 1:
        verdict, reason = "refutes", None
        confidence = 0.8 if n >= 4 and len(genera) == 2 else 0.6
        data_kind = "biological"
    else:
        verdict, reason, confidence, data_kind = "inconclusive", "data-unavailable", 0.75, "none"
    measured = {
        "value": n,
        "unit": "elephants recorded as sources of toenail tissue",
        "n": n,
        "uncertainty": "count of table rows; not a nail-count per foot",
        "extra": {
            "genera": genera,
            "n_loxodonta": sum(1 for row in donors if row["genus"] == "Loxodonta"),
            "n_elephas": sum(1 for row in donors if row["genus"] == "Elephas"),
            "donors": donors,
        },
    }
    doc = json.loads(RESULT.read_text())
    doc["status"] = "complete"
    doc["datasets"] = [{
        "id": "europepmc-PMC11295213-elephant-toenail",
        "name": "Nailing it: elephant toenails for hormone analysis, Europe PMC full text",
        "landing_url": "https://europepmc.org/article/PMC/PMC11295213",
        "doi": "10.1093/conphys/coae048",
        "version": "PMC11295213",
        "license": "CC BY",
        "files": [{"name": "PMC11295213.fullTextXML", **info}],
        "role": "sample table of elephants from which toenail trimmings were collected",
    }]
    doc["method"] = (
        "Downloaded the Europe PMC JATS XML for PMC11295213 and hashed it. "
        "A table whose caption says the samples were toenail trimmings was parsed, and each row naming "
        "Loxodonta or Elephas was counted as a donor. One donor refutes the claim that the elephant has no nails at all. "
        "The clause about all other toed animals was not in this file and was not scored."
    )
    doc["measured"] = measured
    doc["verdict"] = verdict
    doc["confidence"] = confidence
    doc["data_kind"] = data_kind
    doc["results_summary"] = [
        f"Toenail donors parsed from the sample table: {n}. Genera: {genera}.",
        "Keratinous toenail tissue taken from an elephant refutes 'has no nails whatsoever'. Other toed animals were not tested.",
    ]
    if reason:
        doc["reason"] = reason
    else:
        doc.pop("reason", None)
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "n": n, "genera": genera, "confidence": confidence}))


if __name__ == "__main__":
    main()
