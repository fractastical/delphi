#!/usr/bin/env python3
"""Recompute the pre-registered test of aristotle-pa02-29.

Thresholds are the ones in result.json. This script does not edit
pass_criterion, fail_criterion, hypothesis, planned_datasets,
test_contract, or interpretation.

Wikipedia HTML and OLS JSON stay in /tmp and are not committed.
Requires python3 package: requests.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
RESULT_PATH = ROOT / "result.json"
DERIVED = ROOT / "derived"
CACHE = Path("/tmp/delphi-claim-tests/aristotle-pa02-29")

UA = {"User-Agent": "delphi-claim-test/aristotle-pa02-29 (scientific reproducibility; python-requests)"}

PAGES = {
    "bird": "Bird",
    "lizard": "Lizard",
    "crocodile": "Crocodile",
    "turtle": "Turtle",
    "mammal": "Mammal",
}
TARGETS = ("bird", "lizard", "crocodile", "turtle")
REPTILES = ("lizard", "crocodile", "turtle")
TAXA = {
    "bird": "Aves",
    "lizard": "Squamata",
    "crocodile": "Crocodilia",
    "turtle": "Testudines",
    "mammal": "Mammalia",
}

BAD_HEAD = (
    "reference",
    "see also",
    "external link",
    "bibliograph",
    "gallery",
    "further reading",
    "etymolog",
    "taxonomy",
    "classification",
    "evolution",
    "fossil",
    "mytholog",
    "in culture",
    "cultural",
    "as food",
    "as pet",
    "conservation status",
    "relationship with human",
)
GOOD_HEAD = (
    "anatom",
    "morpholog",
    "sense",
    "head",
    "ear",
    "skin",
    "feather",
    "scale",
    "description",
    "appearance",
    "physical",
    "skull",
    "integument",
    "characteristic",
    "external",
)

PRESENCE_RE = re.compile(
    r"\b(pinnae|pinna|auricles|auricle|external ears|external ear|"
    r"projecting ears|ears that stand out)\b",
    re.I,
)
ABSENCE_RE = re.compile(
    r"\b(?:no|without|lack(?:s|ing)?|do not have|don't have)\s+"
    r"(?:an?\s+|any\s+)?(?:external\s+ears?|pinnae?|auricles?)\b"
    r"|"
    r"\bears?\s+(?:are|is)\s+(?:absent|lacking)\b"
    r"|"
    r"\bno ears?,\s+only\b"
    r"|"
    r"\black(?:s|ing)?\s+(?:external\s+)?ears?\b",
    re.I,
)
PASSAGE_RE = re.compile(
    r"\b(ear openings?|auditory canals?|auditory meatus|auditory passages?|"
    r"external acoustic meatus|tympanum|tympanic membranes?|ear canals?|"
    r"ear flaps?|earlids?)\b",
    re.I,
)
TUFT_RE = re.compile(r"\bear[- ]tufts?\b", re.I)
OTHER_TAXA_RE = re.compile(r"\b(mammals?|mammalian|dogs?|cats?|humans?|horses?)\b", re.I)
HEDGE_RE = re.compile(
    r"\b(few|some|exception|exceptions|rarely|one species|a single species)\b",
    re.I,
)
NEG_RE = re.compile(r"\b(no|not|without|lack|lacks|lacking|never)\b", re.I)
LABELS = (
    "pinna",
    "external acoustic meatus",
    "external ear",
    "feather",
    "hair",
    "scale",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def section_included(title: str) -> bool:
    text = title.strip().lower()
    if text in {"", "lead"}:
        return True
    if any(bad in text for bad in BAD_HEAD):
        return False
    return any(good in text for good in GOOD_HEAD)


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.section = "LEAD"
        self.include = True
        self.skip_depth = 0
        self.in_heading = None
        self.heading_buf: list[str] = []
        self.chunks: list[str] = []
        self.buf: list[str] = []

    def _flush(self):
        if self.include and self.buf:
            self.chunks.append("".join(self.buf))
        self.buf = []

    def handle_starttag(self, tag, attrs):
        classes = " ".join(value for key, value in attrs if key == "class")
        if tag in {"script", "style", "sup"} or "reference" in classes or "mw-editsection" in classes:
            self.skip_depth += 1
            return
        if tag in {"h2", "h3"} and self.skip_depth == 0:
            self._flush()
            self.in_heading = tag
            self.heading_buf = []

    def handle_endtag(self, tag):
        if tag in {"script", "style", "sup"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if tag == self.in_heading and self.skip_depth == 0:
            title = re.sub(r"\s+", " ", re.sub(r"\bedit\b", "", "".join(self.heading_buf), flags=re.I)).strip()
            if tag == "h2" or not self.include:
                self.section = title
                self.include = section_included(title)
            elif section_included(title):
                self.include = True
            self.in_heading = None

    def handle_data(self, data):
        if self.skip_depth or self.in_heading:
            if self.in_heading and not self.skip_depth:
                self.heading_buf.append(data)
            return
        if self.include:
            self.buf.append(data)

    def text(self) -> str:
        self._flush()
        return "\n".join(self.chunks)


def sentences_of(html: str) -> list[str]:
    parser = ArticleParser()
    parser.feed(html)
    text = re.sub(r"\s+", " ", re.sub(r"\[\d+\]", " ", parser.text()))
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if len(part.strip()) > 30]


def negated(sentence: str, match: re.Match) -> bool:
    window = sentence[max(0, match.start() - 48) : match.start()]
    words = re.findall(r"[A-Za-z']+", window)
    return bool(NEG_RE.search(" ".join(words[-6:])))


def score_page(sentences: list[str], control: bool) -> dict:
    presence, absence, passage = [], [], []
    for sentence in sentences:
        presence_match = PRESENCE_RE.search(sentence)
        if (
            presence_match
            and not negated(sentence, presence_match)
            and not TUFT_RE.search(sentence)
        ):
            if control or not OTHER_TAXA_RE.search(sentence):
                presence.append(sentence)
        if ABSENCE_RE.search(sentence) and not HEDGE_RE.search(sentence):
            absence.append(sentence)
        if PASSAGE_RE.search(sentence):
            passage.append(sentence)
    if presence and not absence:
        state = "present"
    elif absence and not presence:
        state = "absent"
    elif presence and absence:
        state = "mixed"
    elif passage:
        state = "passage_only"
    else:
        state = "unscored"
    def samples(rows):
        return [row[:300] for row in rows[:4]]
    return {
        "state": state,
        "passage": bool(passage),
        "evidence": {
            "presence": samples(presence),
            "absence": samples(absence),
            "passage": samples(passage),
        },
    }


def fetch_wiki(title: str) -> dict:
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "parse",
            "page": title,
            "prop": "text|revid",
            "format": "json",
            "formatversion": "2",
            "redirects": "1",
            "disableeditsection": "1",
        },
        headers=UA,
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(payload["error"])
    parse = payload["parse"]
    html = parse["text"]
    if isinstance(html, dict):
        html = html.get("*") or ""
    return {
        "title": parse.get("title", title),
        "revid": parse.get("revid"),
        "html": html,
        "byte_size": len(response.content),
        "sha256": sha256(response.content),
        "retrieved_at": utc_now(),
        "download_url": response.url,
    }


def ols_search(label: str) -> dict:
    response = requests.get(
        "https://www.ebi.ac.uk/ols4/api/search",
        params={
            "q": label,
            "ontology": "uberon",
            "type": "class",
            "exact": "true",
            "rows": 5,
        },
        headers=UA,
        timeout=60,
    )
    response.raise_for_status()
    return {
        "label": label,
        "byte_size": len(response.content),
        "sha256": sha256(response.content),
        "retrieved_at": utc_now(),
        "download_url": response.url,
        "payload": response.json(),
    }


def term_found(payload, label: str) -> bool:
    docs = payload.get("response", {}).get("docs", [])
    if not docs:
        docs = (payload.get("_embedded") or {}).get("terms", [])
    for doc in docs:
        if str(doc.get("label", "")).strip().lower() == label.lower():
            return True
    return False


def collect_axioms(payload) -> list[dict]:
    found = []
    text = json.dumps(payload)
    for relation in ("only_in_taxon", "present_in_taxon", "never_in_taxon"):
        for match in re.finditer(relation + r".{0,80}?NCBITaxon[_:](\d+)", text):
            found.append({"relation": relation, "taxon_id": match.group(1), "context": match.group(0)[:120]})
        for match in re.finditer(r"NCBITaxon[_:](\d+).{0,80}?" + relation, text):
            found.append({"relation": relation, "taxon_id": match.group(1), "context": match.group(0)[:120]})
    return found


def taxon_ids() -> dict[str, str]:
    resolved = {}
    for name in sorted(set(TAXA.values())):
        response = requests.get(
            "https://www.ebi.ac.uk/ols4/api/search",
            params={"q": name, "ontology": "ncbitaxon", "type": "class", "exact": "true", "rows": 3},
            headers=UA,
            timeout=60,
        )
        response.raise_for_status()
        docs = response.json().get("response", {}).get("docs", [])
        obo = docs[0].get("obo_id") if docs else None
        if obo and "NCBITaxon:" in obo:
            resolved[name] = obo.split(":")[-1]
        time.sleep(0.2)
    return resolved


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    result = json.loads(RESULT_PATH.read_text())
    frozen = {
        key: result.get(key)
        for key in (
            "hypothesis",
            "pass_criterion",
            "fail_criterion",
            "planned_datasets",
            "test_contract",
            "interpretation",
        )
    }
    problems = []
    wiki_files = []
    pages = {}
    for key, title in PAGES.items():
        try:
            page = fetch_wiki(title)
        except Exception as exc:  # noqa: BLE001 — an unavailable page is a recorded result
            problems.append(f"wikipedia {title}: {exc}")
            pages[key] = {"state": "unscored", "passage": False, "evidence": {}, "title": title, "revid": None}
            continue
        time.sleep(0.4)
        wiki_files.append(
            {
                "name": page["title"],
                "download_url": page["download_url"],
                "retrieved_at": page["retrieved_at"],
                "byte_size": page["byte_size"],
                "sha256": page["sha256"],
                "revid": page["revid"],
            }
        )
        scored = score_page(sentences_of(page["html"]), control=(key == "mammal"))
        scored["title"] = page["title"]
        scored["revid"] = page["revid"]
        pages[key] = scored

    ols_files = []
    axioms = {}
    found_labels = {}
    for label in LABELS:
        try:
            record = ols_search(label)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"ols {label}: {exc}")
            axioms[label] = []
            found_labels[label] = False
            continue
        time.sleep(0.3)
        ols_files.append(
            {
                "name": label,
                "download_url": record["download_url"],
                "retrieved_at": record["retrieved_at"],
                "byte_size": record["byte_size"],
                "sha256": record["sha256"],
            }
        )
        axioms[label] = collect_axioms(record["payload"])
        found_labels[label] = term_found(record["payload"], label)
        (CACHE / f"ols-{label.replace(' ', '_')}.json").write_bytes(
            json.dumps(record["payload"]).encode()
        )

    try:
        ids = taxon_ids()
    except Exception as exc:  # noqa: BLE001
        problems.append(f"ncbitaxon: {exc}")
        ids = {}

    def mentions(label: str, relation: str, taxon_name: str) -> bool:
        taxon_id = ids.get(taxon_name)
        if not taxon_id:
            return False
        return any(item["relation"] == relation and item["taxon_id"] == taxon_id for item in axioms.get(label, []))

    meatus_never = {key: mentions("external acoustic meatus", "never_in_taxon", taxa) for key, taxa in TAXA.items()}
    meatus_known = found_labels.get("external acoustic meatus", False)
    uberon_passage = {key: meatus_known and not meatus_never.get(key, False) for key in TARGETS}
    for key in TARGETS:
        if pages[key]["state"] in {"absent", "passage_only", "unscored"} and not pages[key]["passage"]:
            if uberon_passage.get(key):
                pages[key]["passage"] = True
                pages[key]["passage_source"] = "uberon"
                if pages[key]["state"] == "unscored":
                    pages[key]["state"] = "passage_only"
            else:
                pages[key]["passage_source"] = "wikipedia" if pages[key]["passage"] else None
        else:
            pages[key]["passage_source"] = "wikipedia" if pages[key]["passage"] else None

    control = pages["mammal"]["state"]
    no_pinna = {"absent", "passage_only"}
    bird_ok = pages["bird"]["state"] in no_pinna and pages["bird"]["passage"]
    reptile_no_pinna = [key for key in REPTILES if pages[key]["state"] in no_pinna]
    reptile_present = [key for key in REPTILES if pages[key]["state"] == "present"]
    reptile_with_passage = [key for key in reptile_no_pinna if pages[key]["passage"]]
    targets_present = [key for key in TARGETS if pages[key]["state"] == "present"]
    scored_targets = [key for key in TARGETS if pages[key]["state"] != "unscored"]

    wiki_down = any(pages[key].get("revid") is None for key in PAGES)
    if control != "present":
        verdict = "inconclusive"
        reason = "other" if not wiki_down else "data-unavailable"
    elif wiki_down and len(scored_targets) < 3:
        verdict = "inconclusive"
        reason = "data-unavailable"
    elif pages["bird"]["state"] == "present" or len(reptile_present) >= 2:
        verdict = "refutes"
        reason = None
    elif bird_ok and len(reptile_no_pinna) >= 2 and not targets_present and len(reptile_with_passage) >= 1:
        verdict = "supports"
        reason = None
    elif len(scored_targets) >= 3:
        verdict = "mixed"
        reason = None
    else:
        verdict = "inconclusive"
        reason = "data-unavailable" if wiki_down else "underpowered"

    pinna_mammal = mentions("pinna", "only_in_taxon", "Mammalia") or mentions("pinna", "present_in_taxon", "Mammalia")
    pinna_never_aves = mentions("pinna", "never_in_taxon", "Aves")
    feather_aves = mentions("feather", "only_in_taxon", "Aves") or mentions("feather", "present_in_taxon", "Aves")
    hair_mammal = mentions("hair", "only_in_taxon", "Mammalia") or mentions("hair", "present_in_taxon", "Mammalia")
    uberon_agrees = bool(pinna_mammal or pinna_never_aves) and pages["bird"]["state"] != "present"
    uberon_contradicts = pages["bird"]["state"] in no_pinna and (
        mentions("pinna", "present_in_taxon", "Aves") or mentions("pinna", "only_in_taxon", "Aves")
    )

    absent_n = sum(pages[key]["state"] in no_pinna for key in TARGETS)
    confidence = 0.45
    if control == "present":
        confidence += 0.10
    if bird_ok:
        confidence += 0.10
    confidence += 0.05 * len(reptile_no_pinna)
    if uberon_agrees:
        confidence += 0.10
    if any(pages[key]["state"] == "mixed" for key in TARGETS):
        confidence -= 0.15
    if uberon_contradicts:
        confidence -= 0.20
    confidence = round(min(0.85, max(0.3, confidence)), 2)

    summary = [
        f"{key}: {pages[key]['state']}; passage={pages[key]['passage']}"
        for key in ("mammal",) + TARGETS
    ]
    summary.append(
        f"target groups without a pinna code: {absent_n}; mammal control: {control}"
    )

    measured = {
        "value": absent_n,
        "unit": "target groups coded without an external pinna",
        "n": len(TARGETS),
        "uncertainty": None,
        "extra": {
            "mammal_control": control,
            "reptile_groups_without_pinna": reptile_no_pinna,
            "reptile_groups_with_pinna": reptile_present,
            "confidence_formula": confidence,
            "groups": {
                key: {
                    "state": pages[key]["state"],
                    "passage": pages[key]["passage"],
                    "passage_source": pages[key].get("passage_source"),
                    "title": pages[key].get("title"),
                    "revid": pages[key].get("revid"),
                }
                for key in pages
            },
            "uberon_taxon_ids": ids,
            "uberon_axiom_counts": {label: len(rows) for label, rows in axioms.items()},
            "uberon_material_association": {
                "pinna_restricted_toward_mammalia": pinna_mammal,
                "pinna_never_in_aves": pinna_never_aves,
                "feather_toward_aves": feather_aves,
                "hair_toward_mammalia": hair_mammal,
                "used_in_verdict": False,
            },
            "problems": problems,
        },
    }
    outcome = {
        "verdict": verdict,
        "reason": reason,
        "confidence": confidence,
        "data_kind": "biological" if any(item.get("revid") for item in pages.values()) else "none",
        "measured": measured,
        "results_summary": summary,
        "method": (
            "Fetched the English Wikipedia articles Bird, Lizard, Crocodile, Turtle, and Mammal, "
            "kept the lead and anatomy-related sections, and coded pinna presence, pinna absence, "
            "and auditory openings with the pre-registered sentence patterns. Mammal is only a check "
            "that the same patterns detect a pinna. Queried Uberon class records by label through the "
            "OLS 4 API and used a meatus term not marked never_in_taxon to fill a missing passage hit. "
            "The material explanation is stored from taxon axioms and is not part of the decision."
        ),
        "provenance_wiki": wiki_files,
        "provenance_ols": ols_files,
        "evidence": {key: pages[key].get("evidence") for key in pages},
        "axioms": axioms,
    }
    (DERIVED / "outcome.json").write_text(json.dumps(outcome, indent=2) + "\n")
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")

    if "--apply" in sys.argv:
        current = json.loads(RESULT_PATH.read_text())
        for key, value in frozen.items():
            if current.get(key) != value:
                raise SystemExit(f"refusing to apply: pre-registered field changed: {key}")
        current["status"] = "complete"
        current["verdict"] = verdict
        if reason:
            current["reason"] = reason
        else:
            current.pop("reason", None)
        current["confidence"] = confidence
        current["data_kind"] = outcome["data_kind"]
        current["measured"] = measured
        current["results_summary"] = summary
        current["method"] = outcome["method"]
        current["datasets"] = [
            {
                "id": "wikipedia-en-anatomy-bird-lizard-crocodile-turtle-mammal",
                "name": "English Wikipedia anatomy text for Bird, Lizard, Crocodile, Turtle, and Mammal",
                "landing_url": "https://en.wikipedia.org/wiki/Bird",
                "doi": None,
                "version": "revision ids on each file",
                "license": "CC BY-SA 4.0",
                "files": wiki_files,
                "role": "sentence coding of external pinna versus auditory opening; Mammal is the parser control",
            },
            {
                "id": "uberon-via-ols4",
                "name": "Uberon class records via the EMBL-EBI OLS 4 API",
                "landing_url": "https://www.ebi.ac.uk/ols4/ontologies/uberon",
                "doi": None,
                "version": "OLS 4 response at retrieval",
                "license": None,
                "files": ols_files,
                "role": "optional passage axiom and the untested feather, hair, and pinna taxon association",
            },
        ]
        RESULT_PATH.write_text(json.dumps(current, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
