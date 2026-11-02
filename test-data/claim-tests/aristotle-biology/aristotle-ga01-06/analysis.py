#!/usr/bin/env python3
"""Testis position in birds and oviparous quadrupeds (aristotle-ga01-06).

The species panel and the regular expressions are fixed in result.json.
Mus musculus is a method check: if it does not code as external, the test stops.

Run from this directory: python3 analysis.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test/1.0 (aristotle-ga01-06)"}
BIRDS = [
    "Struthio_camelus",
    "Gallus_gallus",
    "Anas_platyrhynchos",
    "Columba_livia",
    "Bubo_bubo",
    "Apus_apus",
    "Spheniscus_demersus",
    "Passer_domesticus",
]
QUADRUPEDS = [
    "Crocodylus_niloticus",
    "Testudo_graeca",
    "Podarcis_muralis",
    "Varanus_niloticus",
    "Sphenodon_punctatus",
    "Chelydra_serpentina",
]
MOUSE = "Mus_musculus"
INTERNAL = re.compile(
    r"(testes?.{0,40}(internal|abdominal|intra-abdominal|within the body|body cavity)"
    r"|(internal|abdominal|intra-abdominal).{0,40}testes?"
    r"|testes?.{0,30}(kidney|loin|lumbar))",
    re.I | re.S,
)
EXTERNAL = re.compile(
    r"(scrotum|testes?.{0,40}(external|scrotal|descended))",
    re.I | re.S,
)
NEAR = re.compile(r"kidney|loin|lumbar|dorsal body wall|retroperitoneal", re.I)


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        if tag in {"p", "div", "br", "h1", "h2", "h3", "h4", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def visible_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
    return re.sub(r"\n{2,}", "\n", text)


def reproduction_section(text: str) -> str | None:
    match = re.search(r"\bReproduction\b", text)
    if not match:
        return None
    slice_ = text[match.start():]
    end = re.search(
        r"\n\s*(Lifespan/Longevity|Behavior|Behaviour|Food Habits|Predation|Ecosystem Roles|"
        r"Economic Importance|Conservation|Other Comments|Contributors)\b",
        slice_[30:],
    )
    if end:
        slice_ = slice_[: 30 + end.start()]
    return slice_[:8000]


def code_section(section: str) -> dict:
    internal = bool(INTERNAL.search(section))
    external = bool(EXTERNAL.search(section))
    near = bool(NEAR.search(section))
    if internal and external:
        label = "conflict"
    elif internal:
        label = "internal"
    elif external:
        label = "external"
    else:
        label = "unknown"
    snippet = None
    found = INTERNAL.search(section) or EXTERNAL.search(section)
    if found:
        start = max(0, found.start() - 80)
        snippet = re.sub(r"\s+", " ", section[start:found.end() + 80])[:240]
    return {"label": label, "near_kidney": near, "snippet": snippet}


def fetch_account(slug: str) -> dict:
    url = f"https://animaldiversity.org/accounts/{slug}/"
    dest = DATA / f"{slug}.html"
    DATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size == 0:
        response = requests.get(url, headers=UA, timeout=60)
        if response.status_code != 200:
            return {"slug": slug, "fetched": False, "status": response.status_code, "url": url}
        dest.write_bytes(response.content)
    raw = dest.read_bytes()
    stamp = dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc)
    text = visible_text(raw.decode("utf-8", errors="replace"))
    section = reproduction_section(text)
    record = {
        "slug": slug,
        "url": url,
        "fetched": True,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "has_reproduction_section": section is not None,
    }
    if section is None:
        record["label"] = "unknown"
        record["near_kidney"] = False
    else:
        record.update(code_section(section))
    return record


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    panel = []
    mouse = fetch_account(MOUSE)
    time.sleep(0.5)
    for slug in BIRDS + QUADRUPEDS:
        panel.append(fetch_account(slug))
        time.sleep(0.5)
    birds = [row for row in panel if row["slug"] in BIRDS]
    quads = [row for row in panel if row["slug"] in QUADRUPEDS]
    birds_ok = [row for row in birds if row.get("has_reproduction_section")]
    quads_ok = [row for row in quads if row.get("has_reproduction_section")]
    n_birds_internal = sum(1 for row in birds if row.get("label") == "internal")
    n_quads_internal = sum(1 for row in quads if row.get("label") == "internal")
    n_quads_near = sum(1 for row in quads if row.get("near_kidney"))
    n_external = sum(1 for row in panel if row.get("label") == "external")
    mouse_external = mouse.get("label") == "external"
    if not mouse_external:
        verdict, reason = "inconclusive", "other"
        confidence = 0.3
    elif len(birds_ok) < 6 or len(quads_ok) < 4:
        verdict, reason = "inconclusive", "data-unavailable"
        confidence = 0.3
    elif n_external >= 1:
        verdict, reason = "refutes", None
        confidence = 0.7
    elif n_birds_internal >= 7 and n_quads_internal >= 5 and n_quads_near >= 5:
        verdict, reason = "supports", None
        confidence = 0.6
    else:
        verdict, reason = "mixed", None
        confidence = 0.45
    measured = {
        "value": n_birds_internal + n_quads_internal,
        "unit": "panel species coded internal (8 birds + 6 oviparous quadrupeds)",
        "n": len(birds_ok) + len(quads_ok),
        "uncertainty": None,
        "extra": {
            "mouse": mouse,
            "n_birds_internal": n_birds_internal,
            "n_quadrupeds_internal": n_quads_internal,
            "n_quadrupeds_near_kidney": n_quads_near,
            "n_external_in_scope": n_external,
            "panel": panel,
        },
    }
    summary = [
        f"Mouse coded {mouse.get('label')}.",
        f"Birds internal {n_birds_internal}/8 (sections found {len(birds_ok)}). "
        f"Quadrupeds internal {n_quads_internal}/6, near-kidney {n_quads_near}/6, "
        f"external in scope {n_external}.",
        f"Verdict {verdict}.",
    ]
    (DERIVED / "measured.json").write_text(json.dumps({"measured": measured, "summary": summary}, indent=2) + "\n")
    files = []
    for row in [mouse, *panel]:
        if row.get("fetched"):
            files.append({
                "name": f"{row['slug']}.html",
                "download_url": row["url"],
                "retrieved_at": row.get("retrieved_at"),
                "byte_size": row.get("byte_size"),
                "sha256": row.get("sha256"),
            })
    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological" if birds_ok or quads_ok else "none"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    result["method"] = (
        "Fetched the pre-registered Animal Diversity Web accounts, cut the Reproduction section, "
        "and applied the registered internal, external and near-kidney expressions. The mouse had to "
        "code as external or the test was inconclusive. Counts were compared with the registered minima."
    )
    result["measured"] = measured
    result["results_summary"] = summary
    result["datasets"] = [
        {
            "id": "animal-diversity-web-accounts-2026-11",
            "name": "Animal Diversity Web species accounts for the pre-registered panel",
            "landing_url": "https://animaldiversity.org/",
            "doi": None,
            "version": "pages retrieved 2026-11-01",
            "license": "accounts are published by the University of Michigan Museum of Zoology; see each page",
            "files": files,
            "role": "reproduction-section statements of testis position",
        }
    ]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "summary": summary, "mouse": mouse.get("label")}, indent=2))


if __name__ == "__main__":
    main()
