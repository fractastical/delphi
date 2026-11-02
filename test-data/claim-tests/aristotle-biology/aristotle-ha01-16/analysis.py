#!/usr/bin/env python3
"""Middle-ear passage to the palate, and none to the brain, in Uberon."""
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
UA = "delphi-claim-test/1.0 (research; aristotle-biology)"
URLS = {
    "uberon-sensory-minimal": "http://purl.obolibrary.org/obo/uberon/subsets/sensory-minimal.obo",
    "uberon-cranial-minimal": "http://purl.obolibrary.org/obo/uberon/subsets/cranial-minimal.obo",
}
PASSAGE_TOKENS = ("connect", "continuous", "opens")
PALATE_NAMES = {"nasopharynx", "pharynx", "palate", "soft palate"}
EAR_NAMES = {"tympanic cavity", "middle ear"}
BRAIN_NAMES = {"cranial cavity", "brain"}
TUBE_NAMES = {"pharyngotympanic tube", "eustachian tube", "auditory tube"}
IGNORE_PARTS = ("nerve", "vein", "artery")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return {
        "download_url": url,
        "retrieved_at": now(),
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def parse_obo(text):
    typedefs = {}
    terms = []
    stanza = None
    current = None
    for line in text.splitlines():
        if line.startswith("[") and line.endswith("]"):
            if current and stanza == "Typedef" and current.get("id"):
                typedefs[current["id"]] = current.get("name", current["id"])
            if current and stanza == "Term" and current.get("id"):
                terms.append(current)
            stanza = line[1:-1]
            current = {"id": None, "name": "", "rels": [], "synonyms": []}
            continue
        if current is None or not line or line.startswith("!"):
            continue
        if line.startswith("id: "):
            current["id"] = line[4:].strip()
        elif line.startswith("name: "):
            current["name"] = line[6:].strip()
        elif line.startswith("synonym: "):
            match = re.search(r'"([^"]+)"', line)
            if match:
                current["synonyms"].append(match.group(1))
        elif line.startswith("relationship: "):
            rest = line[len("relationship: ") :]
            bits = rest.split(" ! ", 1)
            left = bits[0].strip().split()
            if len(left) >= 2:
                current["rels"].append(
                    {"rel": left[0], "target": left[1], "comment": bits[1].strip() if len(bits) > 1 else ""}
                )
    if current and stanza == "Typedef" and current.get("id"):
        typedefs[current["id"]] = current.get("name", current["id"])
    if current and stanza == "Term" and current.get("id"):
        terms.append(current)
    return typedefs, terms


def names_of(term):
    return {term["name"].lower(), *(syn.lower() for syn in term["synonyms"])}


def is_passage(rel_name):
    lowered = rel_name.lower().replace("_", " ")
    return any(token in lowered for token in PASSAGE_TOKENS)


def decide(typedefs, terms):
    by_id = {term["id"]: term for term in terms}
    def label(target, comment):
        if comment:
            return comment.lower()
        term = by_id.get(target)
        return term["name"].lower() if term else ""

    def find_terms(wanted):
        found = []
        for term in terms:
            if names_of(term) & wanted:
                found.append(term)
        return found

    tubes = find_terms(TUBE_NAMES)
    ears = find_terms(EAR_NAMES)
    passages = []
    palate = False
    brain = False
    for term in tubes + ears:
        for rel in term["rels"]:
            rel_name = typedefs.get(rel["rel"], rel["rel"])
            if not is_passage(rel_name):
                continue
            target_name = label(rel["target"], rel["comment"])
            if any(part in target_name for part in IGNORE_PARTS):
                continue
            record = {
                "from": term["name"],
                "relation": rel_name,
                "to": target_name or rel["target"],
            }
            passages.append(record)
            if any(name in target_name for name in PALATE_NAMES) or any(
                name in names_of(term) for name in TUBE_NAMES
            ) and any(name in target_name for name in PALATE_NAMES | {"tympanic cavity", "middle ear"}):
                palate = True
            # A tube whose other end is the tympanic cavity is only half the path.
            if names_of(term) & TUBE_NAMES and any(name in target_name for name in PALATE_NAMES):
                palate = True
            if names_of(term) & EAR_NAMES and any(name in target_name for name in PALATE_NAMES | TUBE_NAMES):
                # ear connected to the tube counts only together with the tube's pharyngeal end
                pass
            if names_of(term) & EAR_NAMES and any(name in target_name for name in BRAIN_NAMES):
                brain = True
    # Palate passage: tube connects to a pharyngeal/palate term, or ear connects to tube AND tube connects to pharynx.
    tube_to_pharynx = False
    ear_to_tube = False
    tube_to_ear = False
    for record in passages:
        source = record["from"].lower()
        target = record["to"]
        if any(name in source for name in TUBE_NAMES) and any(name in target for name in PALATE_NAMES):
            tube_to_pharynx = True
        if any(name in source for name in TUBE_NAMES) and any(name in target for name in EAR_NAMES):
            tube_to_ear = True
        if any(name in source for name in EAR_NAMES) and any(name in target for name in TUBE_NAMES | PALATE_NAMES):
            if any(name in target for name in PALATE_NAMES):
                tube_to_pharynx = True
            if any(name in target for name in TUBE_NAMES):
                ear_to_tube = True
    palate_ok = tube_to_pharynx or (ear_to_tube and tube_to_pharynx) or (tube_to_ear and tube_to_pharynx)
    # tube_to_pharynx alone is the pass condition for the positive clause
    palate_ok = tube_to_pharynx
    if not tubes and not ears:
        return "inconclusive", "not-operationalizable", passages, palate_ok, brain
    if not any(is_passage(typedefs.get(rel["rel"], rel["rel"])) for term in tubes + ears for rel in term["rels"]):
        if not passages:
            return "inconclusive", "not-operationalizable", passages, palate_ok, brain
    if brain or not palate_ok:
        return "refutes", None, passages, palate_ok, brain
    return "supports", None, passages, palate_ok, brain


def self_test():
    typedefs = {"RO:1": "connects"}
    terms = [
        {
            "id": "T",
            "name": "pharyngotympanic tube",
            "synonyms": ["Eustachian tube"],
            "rels": [
                {"rel": "RO:1", "target": "N", "comment": "nasopharynx"},
                {"rel": "RO:1", "target": "E", "comment": "tympanic cavity"},
            ],
        },
        {"id": "E", "name": "tympanic cavity", "synonyms": [], "rels": []},
        {"id": "N", "name": "nasopharynx", "synonyms": [], "rels": []},
    ]
    verdict, reason, _passages, palate, brain = decide(typedefs, terms)
    assert verdict == "supports" and palate and not brain and reason is None
    terms[1]["rels"].append({"rel": "RO:1", "target": "C", "comment": "cranial cavity"})
    verdict, reason, _p, palate, brain = decide(typedefs, terms)
    assert verdict == "refutes" and brain
    typedefs = {"RO:2": "part_of"}
    terms[0]["rels"] = [{"rel": "RO:2", "target": "N", "comment": "nasopharynx"}]
    terms[1]["rels"] = []
    verdict, reason, passages, _palate, _brain = decide(typedefs, terms)
    assert verdict == "inconclusive" and reason == "not-operationalizable"
    assert not passages
    print("self-test ok")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    result = json.loads((ROOT / "result.json").read_text())
    files = []
    typedefs = {}
    terms = []
    try:
        for key, url in URLS.items():
            meta = fetch(url, CACHE / f"{key}.obo")
            files.append({**meta, "name": f"{key}.obo", "id": key})
            part_types, part_terms = parse_obo(
                (CACHE / f"{key}.obo").read_text(encoding="utf-8", errors="replace")
            )
            typedefs.update(part_types)
            terms.extend(part_terms)
    except Exception as exc:
        result.update(
            {
                "status": "complete",
                "verdict": "inconclusive",
                "reason": "data-unavailable",
                "confidence": 0.8,
                "data_kind": "none",
                "method": f"An Uberon subset could not be downloaded ({exc}).",
                "measured": {"value": None, "unit": "passage relations", "n": 0, "uncertainty": None, "extra": {}},
            }
        )
        (ROOT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print("inconclusive", exc)
        return
    verdict, reason, passages, palate_ok, brain = decide(typedefs, terms)
    measured = {
        "value": len(passages),
        "unit": "passage relations from the tube or middle ear",
        "n": len(terms),
        "uncertainty": "OBO relationship lines with typedef names",
        "extra": {
            "palate_passage": palate_ok,
            "brain_passage": brain,
            "passages": passages,
        },
    }
    result.update(
        {
            "status": "complete",
            "verdict": verdict,
            "confidence": 0.72 if verdict in {"supports", "refutes"} else 0.65,
            "data_kind": "biological",
            "method": (
                "Parsed the Uberon sensory-minimal and cranial-minimal OBO subsets. Passage relations are typedefs "
                "whose names contain connect, continuous or opens. part_of does not count, and nerves and veins are "
                "ignored. The palate clause needs the pharyngotympanic tube linked to the nasopharynx, pharynx or "
                "palate. A passage from the tympanic cavity or middle ear to the cranial cavity or brain refutes "
                "the denial. Inner-ear channels do not vote."
            ),
            "datasets": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "landing_url": "https://obophenotype.github.io/uberon/current_release/",
                    "doi": None,
                    "version": "current purl subset",
                    "license": "CC BY 3.0",
                    "files": [{k: v for k, v in item.items() if k != "id"}],
                    "role": "ear, tube and cranial anatomy relations",
                }
                for item in files
            ],
            "measured": measured,
            "results_summary": [
                f"palate passage {palate_ok}; brain passage {brain}; passage lines {len(passages)}."
            ],
        }
    )
    if reason:
        result["reason"] = reason
    (ROOT / "derived").mkdir(exist_ok=True)
    (ROOT / "derived" / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, palate_ok, brain, passages)


if __name__ == "__main__":
    main()
