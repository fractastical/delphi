#!/usr/bin/env python3
"""aristotle-ha04-04: ten feet, claws included, on the crawfish and the crab.

Pre-registered parser: an explicit count of pereopods, walking legs, legs, or
feet. Five pairs means 10. 'On each side' doubles the number. The order name
Decapoda, carapace teeth, and 'the first pair' alone do not count.

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
    {"id": "marlin-palinurus-elephas-1145", "species": "Palinurus elephas", "group": "crawfish",
     "name": "MarLIN account of the European spiny lobster",
     "url": "https://www.marlin.ac.uk/species/detail/1145"},
    {"id": "marlin-carcinus-maenas-1497", "species": "Carcinus maenas", "group": "crab",
     "name": "MarLIN account of the common shore crab",
     "url": "https://www.marlin.ac.uk/species/detail/1497"},
    {"id": "adw-carcinus-maenas", "species": "Carcinus maenas", "group": "crab",
     "name": "Animal Diversity Web account of Carcinus maenas",
     "url": "https://animaldiversity.org/accounts/Carcinus_maenas/"},
    {"id": "adw-palinuridae", "species": "Palinuridae", "group": "crawfish",
     "name": "Animal Diversity Web classification page for Palinuridae",
     "url": "https://animaldiversity.org/accounts/Palinuridae/"},
]

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10}
PAIR = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+pairs?\s+of\s+"
    r"(pereopods|walking legs|legs|feet)\b", re.I)
EACH = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(pereopods|walking legs|legs|feet)\s+on\s+(each|either)\s+side\b", re.I)
TOTAL = re.compile(
    r"\b(ten|10|five|5)\s+(pereopods|walking legs|legs|feet)\b", re.I)
NEAR = re.compile(r".{60}(pereopod|walking leg|pair of legs|pairs of legs).{60}", re.I)


def fetch(url, name):
    DATA.mkdir(exist_ok=True)
    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read()
        final = resp.geturl()
    (DATA / name).write_bytes(raw)
    return {
        "download_url": url, "final_url": final, "retrieved_at": retrieved,
        "byte_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "raw": raw,
    }


def plain_text(raw):
    text = raw.decode("utf-8", "replace")
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def as_int(token):
    token = token.lower()
    if token.isdigit():
        return int(token)
    return WORDS[token]


def counts_in(text):
    found = []
    for match in PAIR.finditer(text):
        found.append({"pattern": "pairs", "count": 2 * as_int(match.group(1)), "text": match.group(0)})
    for match in EACH.finditer(text):
        found.append({"pattern": "each-side", "count": 2 * as_int(match.group(1)), "text": match.group(0)})
    for match in TOTAL.finditer(text):
        # "five legs" is not "five pairs"; it is an absolute count only for ten/10.
        # "five legs" would under-count a pair phrase already caught above.
        token = match.group(1).lower()
        if token in ("ten", "10"):
            found.append({"pattern": "total", "count": 10, "text": match.group(0)})
    # de-duplicate identical spans
    unique = []
    seen = set()
    for item in found:
        key = (item["count"], item["text"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def main():
    scored = []
    fetched = {}
    for page in PAGES:
        got = fetch(page["url"], page["id"] + ".html")
        fetched[page["id"]] = got
        text = plain_text(got["raw"])
        found = counts_in(text)
        scored.append({
            **{k: page[k] for k in ("id", "species", "group", "name")},
            "counts": found,
            "near": [m.group(0) for m in NEAR.finditer(text)][:6],
        })

    by_group = {"crawfish": [], "crab": []}
    for row in scored:
        for item in row["counts"]:
            by_group[row["group"]].append(item["count"])

    def group_vote(values):
        if not values:
            return "silent"
        if any(v != 10 for v in values) and any(v == 10 for v in values):
            return "disagree"
        if all(v == 10 for v in values):
            return "ten"
        return "other"

    crawfish = group_vote(by_group["crawfish"])
    crab = group_vote(by_group["crab"])
    if crawfish == "silent" and crab == "silent":
        verdict, reason = "inconclusive", "data-unavailable"
    elif crawfish == "ten" and crab == "ten":
        verdict, reason = "supports", None
    elif crawfish == "other" or crab == "other":
        if (crawfish == "ten" and crab == "other") or (crab == "ten" and crawfish == "other"):
            verdict, reason = "mixed", None
        elif crawfish == "silent" or crab == "silent":
            # one species has a non-ten count; the claim names both, and a non-ten count refutes that species
            verdict, reason = "refutes", None
        else:
            verdict, reason = "refutes", None
    elif crawfish == "disagree" or crab == "disagree":
        verdict, reason = "mixed", None
    elif crawfish == "silent" or crab == "silent":
        verdict, reason = "inconclusive", "underpowered"
    else:
        verdict, reason = "inconclusive", "other"

    confidence = 0.72 if verdict == "inconclusive" else 0.7
    measured = {
        "value": len(by_group["crawfish"]) + len(by_group["crab"]),
        "unit": "explicit pereopod or walking-leg counts parsed from the four accounts",
        "n": 4,
        "uncertainty": f"crawfish vote {crawfish}; crab vote {crab}",
        "extra": {"crawfish_counts": by_group["crawfish"], "crab_counts": by_group["crab"], "pages": [
            {"id": s["id"], "species": s["species"], "counts": s["counts"], "near": s["near"]} for s in scored
        ]},
    }

    datasets = []
    for page in PAGES:
        got = fetched[page["id"]]
        datasets.append({
            "id": page["id"], "name": page["name"], "landing_url": page["url"],
            "doi": None, "version": None, "license": "not stated on the fetched page",
            "files": [{
                "name": page["id"] + ".html",
                "download_url": got["download_url"], "final_url": got["final_url"],
                "retrieved_at": got["retrieved_at"], "byte_size": got["byte_size"],
                "sha256": got["sha256"],
            }],
            "role": f"leg-count account for {page['species']}",
        })

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "none" if reason == "data-unavailable" else "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = confidence
    result["datasets"] = datasets
    result["measured"] = measured
    result["deviations"] = []
    result["method"] = (
        "Fetched the four pre-registered accounts and parsed explicit pereopod or walking-leg counts "
        "with the pre-registered patterns. The order name Decapoda, carapace teeth, and a bare mention "
        f"of the first pair were ignored. Crawfish vote: {crawfish}. Crab vote: {crab}."
    )
    result["results_summary"] = [
        f"Parsed counts: crawfish {by_group['crawfish'] or 'none'}, crab {by_group['crab'] or 'none'}.",
        f"Verdict {verdict}" + (f" ({reason})" if reason else "") + ".",
    ]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({
        "verdict": verdict, "reason": reason, "pages": measured["extra"]["pages"],
    }, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "crawfish": crawfish, "crab": crab,
                      "pages": measured["extra"]["pages"]}, indent=2))


if __name__ == "__main__":
    main()
