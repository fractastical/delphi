#!/usr/bin/env python3
"""Larva versus pupa feeding. Stop if the planned files lack the variables."""
import hashlib
import json
import re
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
UA = "delphi-claim-test/1.0 (research; aristotle-biology)"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
LANDING = {
    "dryad-10.5061/dryad.crjdfn3f9": "https://datadryad.org/dataset/doi:10.5061/dryad.crjdfn3f9",
    "dryad-10.5061/dryad.v41ns1rz4": "https://datadryad.org/dataset/doi:10.5061/dryad.v41ns1rz4",
}
STAGE_RE = re.compile(r"larva|caterpillar|grub|instar|pupa|chrysalis|pupal", re.I)
FEED_RE = re.compile(r"feed|intake|frass|feces|faeces|excret|defecat", re.I)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
        final = resp.geturl()
    dest.write_bytes(data)
    return data, {
        "download_url": url if "X-Amz-" not in final else url,
        "retrieved_at": now(),
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def header_cells(data):
    """First non-empty row of the first sheet. Values below the header are not returned."""
    with zipfile.ZipFile(__import__("io").BytesIO(data)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", NS):
                shared.append("".join(node.text or "" for node in item.findall(".//m:t", NS)))
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    for row in root.findall("m:sheetData/m:row", NS):
        cells = []
        for cell in row.findall("m:c", NS):
            kind = cell.get("t")
            value = cell.find("m:v", NS)
            inline = cell.find("m:is", NS)
            if kind == "s" and value is not None and value.text:
                text = shared[int(value.text)]
            elif inline is not None:
                text = "".join(node.text or "" for node in inline.findall(".//m:t", NS))
            elif value is not None and value.text is not None:
                text = value.text
            else:
                text = ""
            cells.append(text)
        if any(cells):
            return cells
    return []


def qualifies(headers):
    text = " | ".join(headers)
    return bool(STAGE_RE.search(text) and FEED_RE.search(text))


def file_links(html):
    pairs = re.findall(r'href="(/downloads/file_stream/\d+)"[^>]*>\s*([^<]+\.(?:xlsx|csv|txt))', html, re.I)
    if pairs:
        return [(f"https://datadryad.org{href}", name.strip()) for href, name in pairs]
    hrefs = re.findall(r'href="(/downloads/file_stream/\d+)"', html)
    names = re.findall(r"[\w.\-]+\.(?:xlsx|csv|txt)", html)
    # Fall back to pairing in order when the markup separates them.
    out = []
    data_names = [name for name in names if not name.lower().startswith("doi_")]
    for href, name in zip(hrefs, data_names):
        out.append((f"https://datadryad.org{href}", name))
    return out


def self_test():
    assert qualifies(["Instar", "Intake", "WetFrass"])
    assert not qualifies(["Pupal Mass", "Development Time", "Diet"])
    assert not qualifies(["ID", "Red Mean", "Luminance Mean"])
    assert qualifies(["Pupa", "frass_mg"])
    assert not qualifies(["Stage", "Mass"])
    print("self-test ok")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    result = json.loads((ROOT / "result.json").read_text())
    datasets = []
    inspected = []
    qualifying = []
    for dataset_id, landing in LANDING.items():
        try:
            html, page_meta = fetch(landing, CACHE / f"{dataset_id}.html")
        except Exception as exc:
            inspected.append({"id": dataset_id, "error": str(exc)})
            continue
        page = html.decode("utf-8", errors="replace")
        links = file_links(page)
        files = []
        for url, name in links:
            if name.lower().endswith(".txt") and "readme" in name.lower():
                continue
            try:
                data, meta = fetch(url, CACHE / name)
            except Exception as exc:
                inspected.append({"id": dataset_id, "file": name, "error": str(exc)})
                continue
            headers = header_cells(data) if name.lower().endswith(".xlsx") else []
            record = {"file": name, "headers": headers, "qualifies": qualifies(headers), **meta}
            inspected.append({"id": dataset_id, **record})
            files.append({k: v for k, v in record.items() if k != "qualifies"})
            if record["qualifies"]:
                qualifying.append(record)
        datasets.append(
            {
                "id": dataset_id,
                "name": dataset_id,
                "landing_url": landing,
                "doi": dataset_id.replace("dryad-", ""),
                "version": None,
                "license": None,
                "files": [{**page_meta, "name": "landing.html"}] + files,
                "role": "checked for a larval-versus-pupal feeding or excretion column",
            }
        )
    if not qualifying:
        verdict = "inconclusive"
        reason = "data-unavailable"
        measured = {
            "value": 0,
            "unit": "planned files with both a stage contrast and a feeding or excretion variable",
            "n": len(inspected),
            "uncertainty": "header screen only; body values were not used",
            "extra": {"inspected": [{k: v for k, v in row.items() if k != "sha256"} for row in inspected]},
        }
        # keep checksums in datasets, not duplicated in extra
        result.update(
            {
                "status": "complete",
                "verdict": verdict,
                "reason": reason,
                "confidence": 0.85,
                "data_kind": "none",
                "method": (
                    "Downloaded the two pre-registered Dryad packages and read only the header row of each spreadsheet. "
                    "A file qualifies only if the header names both a larval or pupal stage and feeding or excretion. "
                    "None did, so body values were not analysed and the verdict is data-unavailable."
                ),
                "datasets": datasets,
                "measured": measured,
                "results_summary": ["No planned file contains both a stage contrast and a feeding or excretion variable."],
            }
        )
    else:
        result.update(
            {
                "status": "complete",
                "verdict": "inconclusive",
                "reason": "other",
                "confidence": 0.4,
                "data_kind": "biological",
                "method": "A qualifying file was found after registration. The value comparison was not implemented because the pre-registered screen was expected to stop.",
                "datasets": datasets,
                "measured": {
                    "value": len(qualifying),
                    "unit": "qualifying files",
                    "n": len(qualifying),
                    "uncertainty": None,
                    "extra": {"qualifying_headers": [row["headers"] for row in qualifying]},
                },
                "results_summary": ["Qualifying headers were found; this run does not score body values."],
            }
        )
    (ROOT / "derived").mkdir(exist_ok=True)
    (ROOT / "derived" / "measured.json").write_text(json.dumps(result["measured"], indent=2) + "\n")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(result["verdict"], result["measured"]["value"])


if __name__ == "__main__":
    main()
