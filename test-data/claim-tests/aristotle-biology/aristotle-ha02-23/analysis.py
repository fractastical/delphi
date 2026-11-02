#!/usr/bin/env python3
"""Kidneys and urinary bladders of fishes and birds."""
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
FISH_TERMS = {"kidney", "urinary bladder"}
ITEM_URL = "https://zfin.org/downloads/anatomy_item.txt"
SYN_URL = "https://zfin.org/downloads/anatomy_synonyms.txt"
STAGE_URL = "https://zfin.org/downloads/stage_ontology.txt"
RENAL_URL = "http://purl.obolibrary.org/obo/uberon/subsets/renal-minimal.obo"


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


def adult_stage_id(path):
    adults = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        try:
            end_hour = float(parts[4])
        except ValueError:
            end_hour = -1
        if "adult" in parts[2].strip().lower():
            adults.append((end_hour, parts[0].strip(), parts[2].strip()))
    if not adults:
        return None, None
    adults.sort()
    return adults[-1][1], adults[-1][2]


def load_items(path):
    items = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip() or line.lower().startswith("anatomy id"):
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        name = parts[1].strip() if len(parts) == 4 else " ".join(p.strip() for p in parts[1:-2])
        items.append({"id": parts[0].strip(), "name": name, "end": parts[-1].strip()})
    return items


def load_synonyms(path):
    by_id = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3 or parts[0].lower().startswith("anatomy"):
            continue
        by_id.setdefault(parts[0].strip(), []).append(parts[-1].strip())
    return by_id


def fish_hits(items, synonyms, adult_id):
    found = []
    for item in items:
        names = {item["name"].lower()}
        names.update(s.lower() for s in synonyms.get(item["id"], []))
        # Exact match only. "swim bladder" must not match "urinary bladder".
        hit = sorted(names & FISH_TERMS)
        if not hit:
            continue
        found.append(
            {
                "id": item["id"],
                "name": item["name"],
                "end": item["end"],
                "matched": hit,
                "adult": adult_id is None or item["end"] == adult_id,
            }
        )
    return found


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


def bird_axioms(typedefs, terms):
    """Positive presence or positive absence of kidney / urinary bladder in Aves or Gallus."""
    wanted = {}
    for term in terms:
        names = {term["name"].lower(), *(s.lower() for s in term["synonyms"])}
        if "kidney" in names or "urinary bladder" in names:
            wanted[term["id"]] = term
    notes = []
    present = set()
    absent = set()
    for term in wanted.values():
        names = {term["name"].lower(), *(s.lower() for s in term["synonyms"])}
        if "urinary bladder" in names:
            label = "urinary bladder"
        elif "kidney" in names:
            label = "kidney"
        else:
            continue
        for rel in term["rels"]:
            rel_name = typedefs.get(rel["rel"], rel["rel"]).lower().replace("_", " ")
            comment = rel["comment"].lower()
            if "taxon" not in rel_name:
                continue
            bird = "aves" in comment or "gallus" in comment or comment.strip() in {"bird", "birds"}
            note = {
                "organ": label,
                "relation": rel_name,
                "target": rel["target"],
                "comment": rel["comment"],
                "scored": bird,
            }
            if not bird:
                note["why"] = "the taxon id is not named Aves or Gallus in this file"
                notes.append(note)
                continue
            notes.append(note)
            if "never" in rel_name:
                absent.add(label)
            elif any(token in rel_name for token in ("present", "only", "in taxon")):
                present.add(label)
    return {"present": sorted(present), "absent": sorted(absent), "notes": notes}


def decide(fish, bird):
    adult = [row for row in fish if row["adult"]]
    fish_present = {name for row in adult for name in row["matched"]}
    if fish_present or bird["present"]:
        return "refutes", None
    if not fish_present and {"kidney", "urinary bladder"} <= set(bird["absent"]):
        return "supports", None
    return "inconclusive", "not-operationalizable"


def self_test():
    fish = [{"id": "ZFA:1", "name": "kidney", "end": "ADULT", "matched": ["kidney"], "adult": True}]
    assert decide(fish, {"present": [], "absent": []})[0] == "refutes"
    assert decide([], {"present": [], "absent": ["kidney", "urinary bladder"]})[0] == "supports"
    assert decide([], {"present": [], "absent": ["kidney"]})[0] == "inconclusive"
    assert "swim bladder" not in FISH_TERMS
    assert "urinary bladder" in FISH_TERMS
    print("self-test ok")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    result = json.loads((ROOT / "result.json").read_text())
    try:
        item_meta = fetch(ITEM_URL, CACHE / "anatomy_item.txt")
        syn_meta = fetch(SYN_URL, CACHE / "anatomy_synonyms.txt")
        stage_meta = fetch(STAGE_URL, CACHE / "stage_ontology.txt")
        renal_meta = fetch(RENAL_URL, CACHE / "renal-minimal.obo")
    except Exception as exc:
        result.update(
            {
                "status": "complete",
                "verdict": "inconclusive",
                "reason": "data-unavailable",
                "confidence": 0.8,
                "data_kind": "none",
                "method": f"An anatomy file could not be downloaded ({exc}).",
                "measured": {"value": None, "unit": "organs present", "n": 0, "uncertainty": None, "extra": {}},
            }
        )
        (ROOT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print("inconclusive", exc)
        return
    adult_id, adult_name = adult_stage_id(CACHE / "stage_ontology.txt")
    items = load_items(CACHE / "anatomy_item.txt")
    synonyms = load_synonyms(CACHE / "anatomy_synonyms.txt")
    hits = []
    for item in items:
        names = {item["name"].lower()}
        names.update(s.lower() for s in synonyms.get(item["id"], []))
        hit = sorted(name for name in names if name in FISH_TERMS)
        if hit:
            hits.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "end": item["end"],
                    "matched": hit,
                    "adult": adult_id is None or item["end"] == adult_id,
                }
            )
    typedefs, terms = parse_obo((CACHE / "renal-minimal.obo").read_text(encoding="utf-8", errors="replace"))
    bird = bird_axioms(typedefs, terms)
    verdict, reason = decide(hits, bird)
    adult_hits = [row for row in hits if row["adult"]]
    measured = {
        "value": len(adult_hits) + len(bird["present"]),
        "unit": "positive kidney or urinary-bladder records in fish or birds",
        "n": len(items),
        "uncertainty": "exact term match plus taxon axioms",
        "extra": {
            "adult_stage_id": adult_id,
            "adult_stage_name": adult_name,
            "fish_adult_hits": adult_hits,
            "fish_other_hits": [row for row in hits if not row["adult"]],
            "bird": bird,
        },
    }
    result.update(
        {
            "status": "complete",
            "verdict": verdict,
            "confidence": 0.84 if verdict == "refutes" else 0.6,
            "data_kind": "biological",
            "method": (
                "Counted exact adult zebrafish terms named kidney or urinary bladder, ignoring the swim bladder, "
                "and read Uberon renal-minimal taxon axioms for Aves or Gallus. Any positive presence refutes the "
                "universal. Support would require positive absence axioms for both organs and no fish term. "
                "A missing string is not absence."
            ),
            "datasets": [
                {
                    "id": "zfin-zebrafish-anatomy",
                    "name": "ZFIN zebrafish anatomy terms, synonyms and stages",
                    "landing_url": "https://zfin.org/downloads",
                    "doi": None,
                    "version": "live download",
                    "license": "CC BY 4.0",
                    "files": [
                        {**item_meta, "name": "anatomy_item.txt"},
                        {**syn_meta, "name": "anatomy_synonyms.txt"},
                        {**stage_meta, "name": "stage_ontology.txt"},
                    ],
                    "role": "adult kidney and urinary bladder terms in Danio rerio",
                },
                {
                    "id": "uberon-renal-minimal",
                    "name": "Uberon renal-minimal subset",
                    "landing_url": "https://obophenotype.github.io/uberon/current_release/",
                    "doi": None,
                    "version": "current purl subset",
                    "license": "CC BY 3.0",
                    "files": [{**renal_meta, "name": "renal-minimal.obo"}],
                    "role": "taxon axioms for kidney and urinary bladder in birds",
                },
            ],
            "measured": measured,
            "results_summary": [
                f"fish adult hits {len(adult_hits)}; bird present {bird['present']}; bird absent {bird['absent']}."
            ],
        }
    )
    if reason:
        result["reason"] = reason
    (ROOT / "derived").mkdir(exist_ok=True)
    (ROOT / "derived" / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, adult_hits, bird["present"], bird["absent"])


if __name__ == "__main__":
    main()
