#!/usr/bin/env python3
"""Test aristotle-ha06-29 against FishBase reproduction text and OBIS occurrences."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "result.json"
DERIVED = ROOT / "derived"
SUMMARY = "https://www.fishbase.se/summary/Anguilla-anguilla.html"
OBIS = "https://api.obis.org/v3/occurrence"
UA = "delphi-claim-test/aristotle-ha06-29 (research)"
SARGASSO = "POLYGON((-80 20,-40 20,-40 35,-80 35,-80 20))"
FROZEN = [
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "test_contract",
    "interpretation",
    "claim_id",
    "claim_iri",
    "project",
    "agent",
]


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag in {"script", "style"}:
            self.skip += 1
        if tag == "a" and attr.get("href"):
            self.hrefs.append(attr["href"])
        if tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "td", "th"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1
        if tag in {"p", "div", "li", "tr", "td", "th"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        return "".join(self.parts)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def finish(payload):
    data = json.loads(RESULT.read_text())
    snapshot = {k: data[k] for k in FROZEN}
    data.update(payload)
    for key, value in snapshot.items():
        if data[key] != value:
            raise SystemExit(f"frozen field changed: {key}")
    RESULT.write_text(json.dumps(data, indent=2) + "\n")


def section_after(text: str, label: str, stop_prefixes: tuple[str, ...]) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    for i, line in enumerate(lines):
        if line.lower().startswith(label.lower()):
            chunk = []
            for nxt in lines[i + 1 : i + 8]:
                if nxt.lower().startswith(stop_prefixes):
                    break
                chunk.append(nxt)
            return " ".join(chunk).strip()
    return ""


def field_after(text: str, label: str) -> str:
    pattern = re.compile(rf"(?im)^\s*{re.escape(label)}\s*$")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    for i, line in enumerate(lines):
        if line.lower() == label.lower() and i + 1 < len(lines):
            return lines[i + 1]
    match = re.search(rf"(?i){re.escape(label)}\s+([A-Za-z][A-Za-z ;,/()-]{{0,80}})", text)
    return match.group(1).strip() if match else ""


def main():
    DERIVED.mkdir(exist_ok=True)
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    files = []
    retrieved = now()

    try:
        summary = sess.get(SUMMARY, timeout=60)
        summary.raise_for_status()
    except requests.RequestException as exc:
        finish(
            {
                "status": "complete",
                "data_kind": "none",
                "verdict": "inconclusive",
                "reason": "data-unavailable",
                "confidence": 0.35,
                "measured": {"value": None, "unit": "disconfirming observations", "n": 0, "uncertainty": None, "extra": {"error": str(exc)}},
                "datasets": [],
                "method": "The FishBase species page could not be retrieved, so OBIS was not used as a substitute identity source.",
                "caveats": ["No reproduction text or occurrence count was measured."],
            }
        )
        print(str(exc))
        return

    files.append(
        {
            "download_url": summary.url,
            "retrieved_at": retrieved,
            "byte_size": len(summary.content),
            "sha256": sha256(summary.content),
            "note": "species summary page",
        }
    )
    parser = TextExtractor()
    parser.feed(summary.text)
    summary_text = parser.text()
    if not re.search(r"Anguilla\s+anguilla", summary_text):
        raise SystemExit("summary page did not name Anguilla anguilla")

    repro_url = None
    # The species page links MaturityList.php before FishReproSummary.php. The reproduction
    # record is the summary page, not the maturity list.
    for href in parser.hrefs:
        if "FishReproSummary" in href:
            repro_url = urljoin(summary.url, href)
            break
    if repro_url is None:
        for href in parser.hrefs:
            if re.search(r"(?i)reprosummary", href) and not re.search(r"(?i)maturity", href):
                repro_url = urljoin(summary.url, href)
                break
    repro_text = ""
    repro_bytes = b""
    if repro_url:
        repro = sess.get(repro_url, timeout=60)
        repro.raise_for_status()
        repro_bytes = repro.content
        files.append(
            {
                "download_url": repro.url,
                "retrieved_at": now(),
                "byte_size": len(repro.content),
                "sha256": sha256(repro.content),
                "note": "reproduction summary",
            }
        )
        extractor = TextExtractor()
        extractor.feed(repro.text)
        repro_text = extractor.text()
    else:
        repro_text = summary_text
        repro_url = summary.url

    mode = field_after(repro_text, "Mode")
    fertilization = field_after(repro_text, "Fertilization")
    guild = field_after(repro_text, "Reproductive guild")
    description = section_after(
        repro_text,
        "Description of life cycle and mating behavior",
        ("search for more", "used for aquaculture", "main ref", "references", "scored as"),
    )
    if not description:
        match = re.search(
            r"(?is)Description of life cycle and mating behavior\s*(.{40,1200}?)\s*(?:Search for more|Used for aquaculture|Main Ref\.|$)",
            repro_text,
        )
        if match:
            description = re.sub(r"\s+", " ", match.group(1)).strip()
    if not description:
        match = re.search(r"(?i).{0,200}(spawn|larva|leptocephalus|sargasso|egg).{0,400}", repro_text)
        description = re.sub(r"\s+", " ", match.group(0)).strip() if match else ""

    life = " ".join([mode, fertilization, guild, description])
    sexual_mode = bool(re.search(r"(?i)\bdioec(?:ism|ious)\b", mode)) or bool(
        re.search(r"(?i)\b(external|internal)\b", fertilization)
    )
    mentions_egg_larva_or_sea = bool(
        re.search(r"(?i)\beggs?\b|\blarva[el]?\b|\bleptocephal", life)
    ) or bool(re.search(r"(?i)spawn\w*[^.]*\bsea\b|\bsea\b[^.]*spawn", description))
    spontaneous = bool(re.search(r"(?i)spontaneous generation|earth'?s guts|worms? (?:in|from) (?:the )?mud|generat\w+ from mud", life))

    obis_error = None
    sargasso_total = None
    global_total = None
    larval_count = None
    facet_status = None
    try:
        sargasso = sess.get(
            OBIS,
            params={"scientificname": "Anguilla anguilla", "geometry": SARGASSO, "size": 0},
            timeout=60,
        )
        sargasso.raise_for_status()
        files.append(
            {
                "download_url": sargasso.url,
                "retrieved_at": now(),
                "byte_size": len(sargasso.content),
                "sha256": sha256(sargasso.content),
                "note": "Sargasso box occurrence count",
            }
        )
        sargasso_total = int(sargasso.json().get("total"))
        overall = sess.get(OBIS, params={"scientificname": "Anguilla anguilla", "size": 0}, timeout=60)
        overall.raise_for_status()
        files.append(
            {
                "download_url": overall.url,
                "retrieved_at": now(),
                "byte_size": len(overall.content),
                "sha256": sha256(overall.content),
                "note": "global occurrence count",
            }
        )
        global_total = int(overall.json().get("total"))
    except (requests.RequestException, ValueError, TypeError) as exc:
        obis_error = str(exc)

    facet_url = "https://api.obis.org/v3/occurrence/facet"
    try:
        facet = sess.get(
            facet_url,
            params={"scientificname": "Anguilla anguilla", "facets": "lifestage"},
            timeout=60,
        )
        facet_status = facet.status_code
        files.append(
            {
                "download_url": facet.url,
                "retrieved_at": now(),
                "byte_size": len(facet.content),
                "sha256": sha256(facet.content),
                "note": f"life-stage facet HTTP {facet.status_code}",
            }
        )
        if facet.ok:
            payload = facet.json()
            blob = json.dumps(payload).lower()
            # Count only structured facet records whose name is larva or leptocephalus.
            records = []
            if isinstance(payload, dict):
                for key in ("results", "facets", "lifestage"):
                    if isinstance(payload.get(key), list):
                        records.extend(payload[key])
            larval_count = 0
            found_stage = False
            for record in records:
                if not isinstance(record, dict):
                    continue
                label = str(record.get("name") or record.get("term") or record.get("lifestage") or "").lower()
                count = record.get("count") or record.get("records") or 0
                if "larva" in label or "leptocephal" in label:
                    found_stage = True
                    larval_count += int(count)
            if not found_stage:
                larval_count = None
                if "leptocephal" not in blob and "larva" not in blob:
                    larval_count = 0 if records else None
    except requests.RequestException as exc:
        facet_status = str(exc)

    fishbase_refutes = sexual_mode and mentions_egg_larva_or_sea
    sargasso_refutes = sargasso_total is not None and sargasso_total >= 1
    larva_refutes = larval_count is not None and larval_count >= 1
    disconfirming = int(fishbase_refutes) + int(sargasso_refutes) + int(larva_refutes)

    fishbase_ok = bool(repro_text.strip())
    if fishbase_refutes or sargasso_refutes or larva_refutes:
        verdict, reason = "refutes", None
    elif (
        spontaneous
        and not sexual_mode
        and sargasso_total == 0
        and larval_count == 0
    ):
        verdict, reason = "supports", None
    elif (not fishbase_ok) and sargasso_total is None and larval_count is None:
        verdict, reason = "inconclusive", "data-unavailable"
    else:
        verdict, reason = "inconclusive", "other"

    if fishbase_refutes and sargasso_refutes:
        confidence = 0.9
    elif verdict == "refutes":
        confidence = 0.78
    elif verdict == "supports":
        confidence = 0.55
    else:
        confidence = 0.4

    quote = description[:500]
    (DERIVED / "reproduction_fields.txt").write_text(
        f"mode: {mode}\nfertilization: {fertilization}\nguild: {guild}\ndescription: {description}\n"
    )
    measured = {
        "value": disconfirming,
        "unit": "independent disconfirming observations among the three pre-registered checks",
        "n": 3,
        "uncertainty": None,
        "extra": {
            "mode": mode,
            "fertilization": fertilization,
            "reproductive_guild": guild,
            "life_cycle_quote": quote,
            "sexual_mode": sexual_mode,
            "mentions_egg_larva_or_sea": mentions_egg_larva_or_sea,
            "spontaneous_language": spontaneous,
            "sargasso_occurrences": sargasso_total,
            "global_occurrences": global_total,
            "larval_facet_count": larval_count,
            "facet_status": facet_status,
            "obis_error": obis_error,
            "reproduction_url": repro_url,
            "rule_based_verdict": verdict,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    finish(
        {
            "status": "complete",
            "data_kind": "biological",
            "verdict": verdict,
            "confidence": confidence,
            **({"reason": reason} if reason else {}),
            "measured": measured,
            "datasets": [
                {
                    "id": "fishbase-anguilla-anguilla-reproduction",
                    "name": "FishBase reproduction summary for Anguilla anguilla",
                    "landing_url": "https://www.fishbase.se/summary/Anguilla-anguilla.html",
                    "doi": None,
                    "version": None,
                    "license": "FishBase terms of use",
                    "files": [item for item in files if "fishbase" in item["download_url"]],
                    "role": "reproductive mode and life-cycle description",
                },
                {
                    "id": "obis-anguilla-anguilla",
                    "name": "OBIS occurrences of Anguilla anguilla",
                    "landing_url": "https://obis.org/",
                    "doi": None,
                    "version": "api v3",
                    "license": "mixed; occurrence records keep the license of each contributing dataset",
                    "files": [item for item in files if "obis.org" in item["download_url"]],
                    "role": "count of occurrences inside the pre-registered Sargasso box and life-stage facet",
                },
            ],
            "method": (
                "Opened the FishBase species page for Anguilla anguilla, followed the reproduction link on that page, "
                "and read mode, fertilization, guild and the life-cycle description. Counted OBIS occurrences of the "
                "same scientific name inside latitude 20–35 N and longitude 80–40 W, and requested a life-stage facet."
            ),
            "caveats": [
                "FishBase is a compiled species account, not a new observation of spawning.",
                "An OBIS point inside the Sargasso box is a recorded occurrence of the species, not by itself a witnessed spawning event.",
                "The life-stage facet is used only when the API returns structured stage counts. A missing facet is not a count of zero unless the response lists stages and none is larval.",
                "The test does not identify the animal Aristotle called the earth's guts.",
            ],
        }
    )
    print(json.dumps({"verdict": verdict, "mode": mode, "sargasso": sargasso_total, "disconfirming": disconfirming}, indent=2))


if __name__ == "__main__":
    main()
