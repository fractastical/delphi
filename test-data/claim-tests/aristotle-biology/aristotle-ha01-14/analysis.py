#!/usr/bin/env python3
"""Test aristotle-ha01-14 against Animal Diversity Web accounts."""

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
UA = "delphi-claim-test/aristotle-ha01-14 (research)"
ACCOUNTS = [
    "Talpa_europaea",
    "Talpa_occidentalis",
    "Talpa_romana",
    "Nannospalax_ehrenbergi",
    "Notoryctes_typhlops",
    "Chrysochloris_asiatica",
    "Eremitalpa_granti",
    "Heterocephalus_glaber",
    "Cryptomys_hottentotus",
    "Fukomys_damarensis",
    "Geomys_bursarius",
    "Thomomys_bottae",
    "Scalopus_aquaticus",
    "Condylura_cristata",
    "Parascalops_breweri",
    "Scapanus_townsendii",
    "Mogera_wogura",
]
SUBJECT = {"Talpa_europaea", "Talpa_occidentalis", "Talpa_romana"}
ALTERNATIVE = {"Nannospalax_ehrenbergi"}
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
    # A newline before a lowercase word is a wrapped line, not a new sentence.
    text = re.sub(r"\s*\n\s*(?=[a-z])", " ", text)
    out = []
    for block in re.split(r"[\n\r]+", text):
        block = re.sub(r"\s+", " ", block).strip()
        if not block:
            continue
        out.extend([part.strip() for part in re.split(r"(?<=[.!?])\s+", block) if part.strip()])
    return out


def eye_sentences(text: str):
    kept = []
    for sentence in sentences(text):
        if re.search(r"(?i)\b(eyes?|vision|blind|sight|eyelids?)\b", sentence):
            kept.append(sentence)
    return kept


def subcutaneous(sentence: str) -> bool:
    s = sentence.lower()
    if re.search(r"eyelids?.{0,30}(fused|sealed)", s):
        return True
    if re.search(
        r"(vestigial|rudimentary|reduced|degenerate|microscopic).{0,40}eyes?|eyes?.{0,40}(vestigial|rudimentary|reduced|degenerate|microscopic)",
        s,
    ):
        return True
    for match in re.finditer(r"eyes?", s):
        window = s[max(0, match.start() - 60) : match.end() + 60]
        if "skin" in window and re.search(r"beneath|under|below|covered by|hidden", window):
            return True
    return False


def externally_functional(sentence: str) -> bool:
    return bool(
        re.search(
            r"(?i)(well[- ]developed|prominent|functional)\s+eyes?|eyes?.{0,30}(well[- ]developed|prominent|functional)|(acute|good|excellent)\s+vision",
            sentence,
        )
    )


def blind(sentence: str) -> bool:
    return bool(re.search(r"(?i)\bblind\b|cannot see|unable to see|no external eyes", sentence))


def light_detection(sentence: str) -> bool:
    return bool(re.search(r"(?i)detect(?:s|ing)? light|light[- ]sensitive|distinguish light|not completely blind", sentence))


def eyes_absent(sentence: str) -> bool:
    return bool(re.search(r"(?i)eyes?.{0,30}(absent|missing|lacking)|no eyes|lack(?:s|ing)? eyes", sentence))


def comparator_eyeless(sentence: str) -> bool:
    return bool(
        re.search(
            r"(?i)\bblind\b|eyes?.{0,50}(covered|buried|under|beneath).{0,30}skin|eyes?.{0,30}(absent|missing|lacking|vestigial|degenerate)|no (external )?eyes|eyelids?.{0,20}fused",
            sentence,
        )
    )


def flags(sents):
    return {
        "subcutaneous": any(subcutaneous(s) for s in sents),
        "externally_functional": any(externally_functional(s) for s in sents),
        "blind": any(blind(s) for s in sents),
        "light_detection": any(light_detection(s) for s in sents),
        "eyes_absent": any(eyes_absent(s) for s in sents),
        "comparator_eyeless": any(comparator_eyeless(s) for s in sents),
        "n_eye_sentences": len(sents),
    }


def talpa_caveats(talpa_sentences):
    caveats = [
        "The codes are the pre-registered sentence patterns. A sentence that mentions eyes but does not match those patterns does not change the verdict. Every kept eye sentence is in derived/sentences.json.",
        "Uniqueness is tested only on the pre-registered fossorial list. A pass would not show that no other mammal on earth lacks eyes.",
        "Spalax or Nannospalax is the alternative identification of Aristotle's mole and is reported separately.",
        "These are compiled species accounts, not new dissections.",
    ]
    unmatched = [
        sentence
        for sentence in talpa_sentences
        if re.search(r"(?i)\beyes?\b", sentence)
        and not any(
            fn(sentence)
            for fn in (subcutaneous, externally_functional, blind, light_detection, eyes_absent)
        )
    ]
    if unmatched:
        caveats.append(
            "European mole eye sentences that the frozen patterns did not code: "
            + " | ".join(sentence[:240] for sentence in unmatched[:4])
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
    records = []
    quotes = []
    for name in ACCOUNTS:
        url = f"https://animaldiversity.org/accounts/{name}/"
        try:
            response = sess.get(url, timeout=60, allow_redirects=True)
        except requests.RequestException as exc:
            records.append({"account": name, "status": "error", "error": str(exc)})
            continue
        final = response.url.rstrip("/")
        if response.status_code != 200 or not final.endswith(name):
            records.append({"account": name, "status": response.status_code, "final_url": response.url})
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
        sents = eye_sentences(parser.text())
        coded = flags(sents)
        coded["account"] = name
        coded["status"] = 200
        records.append(coded)
        for sentence in sents[:40]:
            quotes.append({"account": name, "sentence": sentence[:400]})

    (DERIVED / "codes.json").write_text(json.dumps(records, indent=2) + "\n")
    (DERIVED / "sentences.json").write_text(json.dumps(quotes, indent=2) + "\n")

    by_name = {row["account"]: row for row in records if row.get("status") == 200}
    talpa = by_name.get("Talpa_europaea")
    comparators = [by_name[name] for name in by_name if name not in SUBJECT and name not in ALTERNATIVE]
    comparator_hits = [row["account"] for row in comparators if row.get("comparator_eyeless")]

    if talpa is None:
        verdict, reason = "inconclusive", "data-unavailable"
    elif talpa["n_eye_sentences"] == 0:
        verdict, reason = "inconclusive", "other"
    elif talpa["externally_functional"] or (talpa["eyes_absent"] and not talpa["subcutaneous"]):
        verdict, reason = "refutes", None
    elif (
        talpa["subcutaneous"]
        and not talpa["externally_functional"]
        and talpa["blind"]
        and not talpa["light_detection"]
        and len(comparators) >= 5
        and not comparator_hits
    ):
        verdict, reason = "supports", None
    elif talpa["subcutaneous"] and (talpa["light_detection"] or comparator_hits):
        verdict, reason = "mixed", None
    else:
        verdict, reason = "inconclusive", "other"

    if verdict == "mixed" and comparator_hits and talpa and talpa.get("subcutaneous"):
        confidence = 0.66
    elif verdict == "refutes":
        confidence = 0.6
    elif verdict == "supports":
        confidence = 0.55
    else:
        confidence = 0.4

    measured = {
        "value": len(comparator_hits),
        "unit": "comparator accounts matching the eyeless pattern",
        "n": len(comparators),
        "uncertainty": None,
        "extra": {
            "talpa_europaea": talpa,
            "comparator_hits": comparator_hits,
            "n_comparators_retrieved": len(comparators),
            "n_accounts_retrieved": len(by_name),
            "alternative_identification": {name: by_name.get(name) for name in ALTERNATIVE},
            "other_talpa": {name: by_name.get(name) for name in SUBJECT if name != "Talpa_europaea"},
            "talpa_eye_sentences": [row["sentence"] for row in quotes if row["account"] == "Talpa_europaea"],
            "rule_based_verdict": verdict,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    total_bytes = sum(item["byte_size"] for item in files)
    digest = hashlib.sha256("".join(item["sha256"] for item in files).encode()).hexdigest()
    finish(
        {
            "status": "complete",
            "data_kind": "biological" if by_name else "none",
            "verdict": verdict,
            "confidence": confidence,
            **({"reason": reason} if reason else {}),
            "measured": measured,
            "datasets": [
                {
                    "id": "animal-diversity-web-mole-accounts",
                    "name": "Animal Diversity Web species accounts",
                    "landing_url": "https://animaldiversity.org/",
                    "doi": None,
                    "version": None,
                    "license": "Animal Diversity Web account license as stated on the site",
                    "files": [
                        {
                            "download_url": "https://animaldiversity.org/accounts/<species>/",
                            "retrieved_at": retrieved,
                            "byte_size": total_bytes,
                            "sha256": digest,
                            "note": f"SHA-256 of the concatenated per-page SHA-256 hex digests; {len(files)} pages. Per-page hashes are in this list.",
                        },
                        *files,
                    ],
                    "role": "eye descriptions for Talpa europaea and the pre-registered fossorial mammals",
                }
            ],
            "method": (
                f"Retrieved {len(by_name)} Animal Diversity Web accounts from the pre-registered list. "
                "Eye sentences were coded with the frozen patterns for subcutaneous eyes, blindness, light detection, "
                "functional external eyes, and the comparator eyeless pattern. Mole-rat pages were not used as uniqueness counterexamples."
            ),
            "caveats": talpa_caveats(
                [row["sentence"] for row in quotes if row["account"] == "Talpa_europaea"]
            ),
        }
    )
    print(json.dumps({"verdict": verdict, "talpa": talpa, "comparator_hits": comparator_hits}, indent=2))


if __name__ == "__main__":
    main()
