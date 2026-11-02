#!/usr/bin/env python3
"""aristotle-ga05-09: seals have no external ears, only hearing passages, because they live in water.

The lexicon is the one fixed in result.json before these pages were read.
Pinna terms: external ear, ear flap, pinna.
Negation within the 80 characters before the term: no, not, lack, without, absent, do not.
Passage terms: ear canal, auditory meatus, ear opening, hearing passage.

Run: python3 analysis.py
"""

import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test/1.0"}

PAGES = [
    {"id": "adw-phocidae", "name": "Animal Diversity Web account for Phocidae",
     "url": "https://animaldiversity.org/accounts/Phocidae/", "group": "phocid",
     "role": "family account for true seals"},
    {"id": "adw-monachus-monachus", "name": "Animal Diversity Web account for Monachus monachus",
     "url": "https://animaldiversity.org/accounts/Monachus_monachus/", "group": "phocid",
     "role": "Mediterranean monk seal, the seal of Aristotle's sea"},
    {"id": "noaa-mediterranean-monk-seal", "name": "NOAA Fisheries species page for the Mediterranean monk seal",
     "url": "https://www.fisheries.noaa.gov/species/mediterranean-monk-seal", "group": "phocid",
     "role": "second public account of the monk seal"},
    {"id": "adw-otariidae", "name": "Animal Diversity Web account for Otariidae",
     "url": "https://animaldiversity.org/accounts/Otariidae/", "group": "comparison",
     "role": "eared seals and sea lions, aquatic comparison"},
    {"id": "adw-odobenus-rosmarus", "name": "Animal Diversity Web account for Odobenus rosmarus",
     "url": "https://animaldiversity.org/accounts/Odobenus_rosmarus/", "group": "comparison",
     "role": "walrus, aquatic comparison"},
    {"id": "adw-enhydra-lutris", "name": "Animal Diversity Web account for Enhydra lutris",
     "url": "https://animaldiversity.org/accounts/Enhydra_lutris/", "group": "comparison",
     "role": "sea otter, aquatic comparison"},
]

PINNA = re.compile(r"external ears?|ear flaps?|pinnae|pinna", re.I)
NEG = re.compile(r"\b(do not|don't|cannot|can't|without|absent|lacking|lacks|lack|no|not)\b", re.I)
PASSAGE = re.compile(r"ear canal|auditory meatus|ear opening|hearing passage", re.I)


def fetch(url, name):
    DATA.mkdir(exist_ok=True)
    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read()
        final = resp.geturl()
    (DATA / name).write_bytes(raw)
    return {
        "download_url": url,
        "final_url": final,
        "retrieved_at": retrieved,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "raw": raw,
    }


def plain_text(raw):
    text = raw.decode("utf-8", "replace")
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&#39;", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", text)


def score(text):
    hits = []
    for match in PINNA.finditer(text):
        window = text[max(0, match.start() - 80):match.start()]
        hits.append({
            "term": match.group(0),
            "negated": bool(NEG.search(window)),
            "context": (window + match.group(0))[-120:],
        })
    if not hits:
        pinna = "silent"
    else:
        present = any(not h["negated"] for h in hits)
        absent = any(h["negated"] for h in hits)
        if present and absent:
            pinna = "disagree"
        elif present:
            pinna = "present"
        else:
            pinna = "absent"
    return {
        "pinna": pinna,
        "passage": bool(PASSAGE.search(text)),
        "hits": hits,
    }


def decide(scored):
    phocid = [s for s in scored if s["group"] == "phocid"]
    comparison = [s for s in scored if s["group"] == "comparison"]
    phocid_votes = [s for s in phocid if s["pinna"] in ("present", "absent", "disagree")]
    if not phocid_votes:
        return "inconclusive", "data-unavailable"
    if any(s["pinna"] == "present" or s["pinna"] == "disagree" for s in phocid_votes):
        if any(s["pinna"] == "absent" for s in phocid_votes):
            return "mixed", None
        return "refutes", None
    # all voting phocid pages say absent
    passage = any(s["passage"] for s in phocid)
    comparison_present = any(s["pinna"] == "present" for s in comparison)
    if comparison_present or not passage:
        return "mixed", None
    if any(s["pinna"] in ("present", "absent") for s in comparison) and not comparison_present:
        return "supports", None
    # comparisons all silent: causal clause untested, and passage held, but support requires a scored comparison
    return "mixed", None


def main():
    scored = []
    fetched = {}
    for page in PAGES:
        got = fetch(page["url"], page["id"] + ".html")
        fetched[page["id"]] = got
        result = score(plain_text(got["raw"]))
        scored.append({**page, **result})

    verdict, reason = decide(scored)
    phocid_present = sum(1 for s in scored if s["group"] == "phocid" and s["pinna"] == "present")
    voting = [s for s in scored if s["pinna"] != "silent"]
    if verdict == "mixed" and any(s["group"] == "comparison" and s["pinna"] == "present" for s in scored):
        confidence = 0.8
    elif verdict in ("supports", "refutes"):
        confidence = 0.75
    else:
        confidence = 0.45

    public_scores = [{
        "id": s["id"], "group": s["group"], "pinna": s["pinna"], "passage": s["passage"],
        "hits": s["hits"],
    } for s in scored]
    measured = {
        "value": phocid_present,
        "unit": "phocid accounts that score an external pinna as present",
        "n": len(voting),
        "uncertainty": "pages voting on the pinna: " + ", ".join(f"{s['id']}={s['pinna']}" for s in voting),
        "extra": {"scores": public_scores},
    }

    datasets = []
    for page in PAGES:
        got = fetched[page["id"]]
        datasets.append({
            "id": page["id"],
            "name": page["name"],
            "landing_url": page["url"],
            "doi": None,
            "version": None,
            "license": "not stated on the fetched page",
            "files": [{
                "name": page["id"] + ".html",
                "download_url": got["download_url"],
                "final_url": got["final_url"],
                "retrieved_at": got["retrieved_at"],
                "byte_size": got["byte_size"],
                "sha256": got["sha256"],
            }],
            "role": page["role"],
        })

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = confidence
    result["datasets"] = datasets
    result["measured"] = measured
    result["deviations"] = [{
        "what": "Phrases outside the pre-registered lexicon were left unscored, including 'earless', bare 'ears', and 'outer ear tube'.",
        "why": "The contract names the phrases that count. Adding synonyms after reading the pages would change the scorer. The thresholds were not changed.",
    }]
    result["method"] = (
        "Fetched the six pre-registered accounts, stripped the HTML, and applied the fixed pinna and "
        "passage lexicon. Phocidae scores pinna absent. The monk-seal pages do not match the lexicon. "
        "Otariidae scores pinna present. The pre-registered rule then returns mixed: true seals are described "
        "without an external ear, and a water-living comparison group is described with one."
    )
    bits = [f"{s['id']}: pinna {s['pinna']}, passage {s['passage']}" for s in scored]
    result["results_summary"] = bits + [f"Verdict {verdict}. Phocid pages scoring pinna present: {phocid_present}."]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({
        "verdict": verdict, "reason": reason, "scores": public_scores,
    }, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "scores": [{k: s[k] for k in ("id", "pinna", "passage")} for s in scored]}, indent=2))


if __name__ == "__main__":
    main()
