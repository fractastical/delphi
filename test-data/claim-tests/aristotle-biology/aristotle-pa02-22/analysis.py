#!/usr/bin/env python3
"""Test aristotle-pa02-22 against species accounts, DigiMorph and Uberon."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "result.json"
DERIVED = ROOT / "derived"
UA = "delphi-claim-test/aristotle-pa02-22 (research)"
ACCOUNTS = [
    "Alligator_mississippiensis",
    "Crocodylus_niloticus",
    "Crocodylus_porosus",
    "Sphenodon_punctatus",
    "Chelydra_serpentina",
    "Homo_sapiens",
    "Gallus_gallus",
]
DIGIMORPH = "https://digimorph.org/specimens/Alligator_mississippiensis/"
UBERON = "https://www.ebi.ac.uk/ols4/api/search"
POS = re.compile(r"(?i)\bgastralia\b|\bgastralium\b|abdominal ribs|ventral ribs")
NEG = re.compile(
    r"(?i)\b(no|without|lack|lacks|lacking|absent|devoid|not)\b.{0,40}(gastralia|gastralium|abdominal ribs|ventral ribs)"
)
DENIAL = re.compile(
    r"(?i)(abdominal|belly).{0,40}wall.{0,50}(no bones|without bones|boneless|devoid of bones)|"
    r"(no|without|devoid of) bones.{0,40}(abdominal|belly)"
)
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

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        if tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "td"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        return "".join(self.parts)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sentences(text: str):
    out = []
    for block in re.split(r"[\n\r]+", text):
        block = re.sub(r"\s+", " ", block).strip()
        if not block:
            continue
        out.extend([part.strip() for part in re.split(r"(?<=[.!?])\s+", block) if part.strip()])
    return out


def positive_sentences(text: str):
    hits = []
    denials = []
    for sentence in sentences(text):
        if POS.search(sentence) and not NEG.search(sentence):
            hits.append(sentence[:500])
        if DENIAL.search(sentence):
            denials.append(sentence[:500])
    return hits, denials


def belly_caveats(positive_sources, account_hits, digimorph_hits, uberon_quote):
    caveats = [
        "A turtle shell mentioned only as a shell was not scored. The positive pattern is gastralia or abdominal or ventral ribs.",
        "Silence in an account is not evidence that the belly wall lacks bones. Support required eight explicit denials.",
        "The human account is a coding check. A positive hit there would have made the verdict inconclusive.",
    ]
    if positive_sources == ["uberon"] and not account_hits and not digimorph_hits:
        caveats.insert(
            0,
            "No pre-registered species account and not the DigiMorph alligator page named gastralia, a gastralium, abdominal ribs or ventral ribs. The only affirmative hit is the Uberon search record: "
            + re.sub(r"\s+", " ", uberon_quote)[:360],
        )
    else:
        caveats.insert(
            0,
            "Species-account hits and the Uberon hit are listed separately in measured.extra.",
        )
    return caveats


def finish(payload):
    data = json.loads(RESULT.read_text())
    snapshot = {k: data[k] for k in FROZEN}
    data.update(payload)
    for key, value in snapshot.items():
        if data[key] != value:
            raise SystemExit(f"frozen field changed: {key}")
    RESULT.write_text(json.dumps(data, indent=2) + "\n")


def main():
    DERIVED.mkdir(exist_ok=True)
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    retrieved = now()
    files = []
    per_source = []
    human_hit = False

    for name in ACCOUNTS:
        url = f"https://animaldiversity.org/accounts/{name}/"
        try:
            response = sess.get(url, timeout=60, allow_redirects=True)
        except requests.RequestException as exc:
            per_source.append({"source": name, "error": str(exc)})
            continue
        if response.status_code != 200 or not response.url.rstrip("/").endswith(name):
            per_source.append({"source": name, "status": response.status_code, "final_url": response.url})
            continue
        files.append(
            {
                "download_url": response.url,
                "retrieved_at": now(),
                "byte_size": len(response.content),
                "sha256": hashlib.sha256(response.content).hexdigest(),
            }
        )
        parser = TextExtractor()
        parser.feed(response.text)
        hits, denials = positive_sentences(parser.text())
        if name == "Homo_sapiens" and hits:
            human_hit = True
        per_source.append({"source": name, "positive": hits, "denials": denials})

    digimorph_hits = []
    try:
        digi = sess.get(DIGIMORPH, timeout=60)
        digi.raise_for_status()
        files.append(
            {
                "download_url": digi.url,
                "retrieved_at": now(),
                "byte_size": len(digi.content),
                "sha256": hashlib.sha256(digi.content).hexdigest(),
            }
        )
        parser = TextExtractor()
        parser.feed(digi.text)
        digimorph_hits, _ = positive_sentences(parser.text())
        per_source.append({"source": "digimorph", "positive": digimorph_hits})
    except requests.RequestException as exc:
        per_source.append({"source": "digimorph", "error": str(exc)})

    uberon_quote = ""
    uberon_hits = []
    uberon_iri = None
    try:
        search = sess.get(UBERON, params={"q": "gastralia", "ontology": "uberon", "rows": 5}, timeout=60)
        search.raise_for_status()
        files.append(
            {
                "download_url": search.url,
                "retrieved_at": now(),
                "byte_size": len(search.content),
                "sha256": hashlib.sha256(search.content).hexdigest(),
            }
        )
        docs = ((search.json().get("response") or {}).get("docs")) or []
        if docs:
            uberon_iri = docs[0].get("iri") or docs[0].get("obo_id")
            description = " ".join(docs[0].get("description") or [])
            label = docs[0].get("label") or ""
            uberon_quote = f"{label}. {description}".strip()
            uberon_hits, _ = positive_sentences(uberon_quote)
            if not uberon_hits and POS.search(uberon_quote) and not NEG.search(uberon_quote):
                uberon_hits = [uberon_quote[:500]]
        per_source.append({"source": "uberon", "iri": uberon_iri, "quote": uberon_quote[:800], "positive": uberon_hits})
    except (requests.RequestException, ValueError) as exc:
        per_source.append({"source": "uberon", "error": str(exc)})

    (DERIVED / "hits.json").write_text(json.dumps(per_source, indent=2) + "\n")

    account_hits = []
    denial_accounts = []
    retrieved_accounts = 0
    for row in per_source:
        if row["source"] in ACCOUNTS and "positive" in row:
            retrieved_accounts += 1
            if row["positive"]:
                account_hits.append(row["source"])
            if row.get("denials"):
                denial_accounts.append(row["source"])

    positive_sources = list(account_hits)
    if digimorph_hits:
        positive_sources.append("digimorph")
    if uberon_hits:
        positive_sources.append("uberon")

    pages_retrieved = any("positive" in row or row.get("quote") for row in per_source)
    if not pages_retrieved:
        verdict, reason = "inconclusive", "data-unavailable"
    elif human_hit:
        verdict, reason = "inconclusive", "other"
    elif positive_sources:
        verdict, reason = "refutes", None
    elif len(denial_accounts) >= 8 and not positive_sources:
        verdict, reason = "supports", None
    else:
        verdict, reason = "inconclusive", "other"

    specimen_or_account = bool(account_hits or digimorph_hits)
    if verdict == "refutes" and specimen_or_account:
        confidence = 0.76
    elif verdict == "refutes":
        confidence = 0.58
    elif verdict == "supports":
        confidence = 0.45
    else:
        confidence = 0.4

    measured = {
        "value": len(positive_sources),
        "unit": "sources with an unnegated gastralia or abdominal-rib statement",
        "n": retrieved_accounts,
        "uncertainty": None,
        "extra": {
            "positive_sources": positive_sources,
            "account_hits": account_hits,
            "digimorph_hits": digimorph_hits,
            "uberon_iri": uberon_iri,
            "uberon_quote": uberon_quote[:800],
            "denial_accounts": denial_accounts,
            "human_false_positive": human_hit,
            "rule_based_verdict": verdict,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    total_bytes = sum(item["byte_size"] for item in files)
    digest = hashlib.sha256("".join(item["sha256"] for item in files).encode()).hexdigest()
    finish(
        {
            "status": "complete",
            "data_kind": "biological" if positive_sources or retrieved_accounts else "none",
            "verdict": verdict,
            "confidence": confidence,
            **({"reason": reason} if reason else {}),
            "measured": measured,
            "datasets": [
                {
                    "id": "animal-diversity-web-accounts",
                    "name": "Animal Diversity Web species accounts",
                    "landing_url": "https://animaldiversity.org/",
                    "doi": None,
                    "version": None,
                    "license": "Animal Diversity Web account license as stated on the site",
                    "files": [item for item in files if "animaldiversity.org" in item["download_url"]]
                    or [
                        {
                            "download_url": "https://animaldiversity.org/accounts/",
                            "retrieved_at": retrieved,
                            "byte_size": 0,
                            "sha256": hashlib.sha256(b"").hexdigest(),
                            "note": "no account page resolved",
                        }
                    ],
                    "role": "statements about gastralia or abdominal ribs",
                },
                {
                    "id": "digimorph-alligator-mississippiensis",
                    "name": "DigiMorph Alligator mississippiensis specimen page",
                    "landing_url": DIGIMORPH,
                    "doi": None,
                    "version": None,
                    "license": "as stated on the DigiMorph specimen page",
                    "files": [item for item in files if "digimorph.org" in item["download_url"]],
                    "role": "specimen-page text for ventral skeletal elements",
                },
                {
                    "id": "uberon-ols-gastralia",
                    "name": "Uberon term for gastralia via OLS",
                    "landing_url": "https://www.ebi.ac.uk/ols4/ontologies/uberon",
                    "doi": None,
                    "version": None,
                    "license": "not stated in the OLS search response",
                    "files": [item for item in files if "ebi.ac.uk" in item["download_url"]],
                    "role": "definition of gastralia",
                },
            ],
            "method": (
                "Retrieved the pre-registered Animal Diversity Web accounts, the DigiMorph alligator specimen page, "
                "and the Uberon search result for gastralia. A sentence is a hit when it names gastralia, a gastralium, "
                "abdominal ribs or ventral ribs and does not negate that phrase within 40 characters. "
                f"Combined response bytes {total_bytes}, digest of page hashes {digest}."
            ),
            "caveats": belly_caveats(positive_sources, account_hits, digimorph_hits, uberon_quote),
        }
    )
    print(json.dumps({"verdict": verdict, "positive_sources": positive_sources, "uberon": uberon_quote[:240]}, indent=2))


if __name__ == "__main__":
    main()
