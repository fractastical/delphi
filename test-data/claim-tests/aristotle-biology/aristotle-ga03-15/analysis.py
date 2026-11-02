#!/usr/bin/env python3
"""Fish fertilization codes and zebrafish mouth-to-gut anatomy.

Rules are those committed in result.json before these files were read.
"""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test/1.0 (aristotle-ga03-15; research)"
PARQUET_URL = "https://data.source.coop/cboettig/fishbase/fb/v26.06/parquet/reproduc.parquet"
ZFIN_REL = "https://zfin.org/downloads/anatomy_relationship.txt"
ZFIN_ITEM = "https://zfin.org/downloads/anatomy_item.txt"
REFUTING = re.compile(r"intestin|gut|swallow|ingest|uterus", re.I)


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read()
    dest.write_bytes(body)
    return body


def norm(value):
    return re.sub(r"\s+", " ", value.strip().casefold())


def classify(value):
    """Closed list from pass_criterion, plus the inflection deviation for articles.

    The deviation (recorded in result.json) treats three stored strings as the
    pre-registered phrases with the articles removed. 'other' stays unclassified.
    """
    v = norm(value)
    if REFUTING.search(v):
        return "refuting"
    exact = {
        "external",
        "internal",
        "internal (in the oviduct)",
        "internal (oviduct)",
        "in the mouth",
        "in mouth",
        "in a brood pouch",
        "in a brood pouch or similar structure",
        "in brood pouch or similar structure",
        "elsewhere",
    }
    if v in exact or v.startswith("external") or v.startswith("internal") or v.startswith("in a brood pouch"):
        return "compatible"
    return "unclassified"


def ancestors(start, parents):
    seen = set()
    stack = [start]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(parents.get(cur, []))
    return seen


def anatomy(item_text, rel_text):
    names = {}
    for line in item_text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            names[parts[0]] = parts[1]
    # File columns are parent, child, relation: the child stands in that relation to the parent.
    parents = defaultdict(list)
    edges = []
    rel_counts = Counter()
    for line in rel_text.splitlines():
        if not line.strip():
            continue
        a, b, rel = line.split("\t")
        rel_counts[rel] += 1
        if rel in ("part of", "is_a"):
            parents[b].append(a)
        edges.append((a, b, rel))
    def ids_named(pred):
        return [i for i, n in names.items() if pred(n.casefold())]
    mouth_ids = ids_named(lambda n: n in ("mouth", "oral cavity"))
    gut_ids = ids_named(lambda n: "intestine" in n)
    gonad_ids = ids_named(lambda n: n in ("ovary", "uterus", "gonad") or n.endswith(" ovary"))
    digestive_ids = set(ids_named(lambda n: "digestive" in n or "alimentary" in n or n == "gut"))
    mouth_anc = set()
    gut_anc = set()
    for i in mouth_ids:
        mouth_anc |= ancestors(i, parents)
    for i in gut_ids:
        gut_anc |= ancestors(i, parents)
    shared = mouth_anc & gut_anc & (digestive_ids | {i for i in mouth_anc & gut_anc if "digestive" in names.get(i, "").casefold() or "alimentary" in names.get(i, "").casefold() or names.get(i, "").casefold() == "gut"})
    # also count a digestive-system node reached by both
    shared_digestive = []
    for i in mouth_anc & gut_anc:
        label = names.get(i, "")
        if "digestive" in label.casefold() or "alimentary" in label.casefold() or label.casefold() == "gut":
            shared_digestive.append(label)
    mouth_set = set(mouth_ids)
    gonad_set = set(gonad_ids)
    bad = []
    for a, b, rel in edges:
        if rel not in ("continuous with", "connected_to", "connected to"):
            continue
        ends = {a, b}
        if ends & mouth_set and ends & gonad_set:
            bad.append({"relation": rel, "a": names.get(a), "b": names.get(b)})
    affirmed = bool(shared_digestive) and not bad and bool(mouth_ids) and bool(gut_ids)
    return {
        "affirmed": affirmed,
        "mouth_terms": [names[i] for i in mouth_ids],
        "intestine_terms": [names[i] for i in gut_ids],
        "shared_digestive_ancestors": sorted(set(shared_digestive)),
        "gonad_terms": [names[i] for i in gonad_ids],
        "mouth_gonad_bridges": bad,
        "relation_counts": dict(rel_counts),
        "has_mouth_and_intestine": bool(mouth_ids) and bool(gut_ids),
    }


def main():
    DATA.mkdir(exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files = {
        "reproduc.parquet": PARQUET_URL,
        "anatomy_relationship.txt": ZFIN_REL,
        "anatomy_item.txt": ZFIN_ITEM,
    }
    meta = []
    blobs = {}
    for name, url in files.items():
        raw = fetch(url, DATA / name)
        blobs[name] = raw
        meta.append({
            "name": name,
            "download_url": url,
            "retrieved_at": now,
            "byte_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    table = pq.read_table(DATA / "reproduc.parquet", columns=["SpecCode", "Fertilization", "AddInfos"])
    specs = table.column("SpecCode").to_pylist()
    ferts = table.column("Fertilization").to_pylist()
    infos = table.column("AddInfos").to_pylist()
    by_species = defaultdict(set)
    other_notes = []
    for spec, fert, info in zip(specs, ferts, infos):
        if fert is None or str(fert).strip() == "":
            continue
        value = str(fert).strip()
        by_species[spec].add(value)
        if norm(value) == "other":
            other_notes.append({"SpecCode": spec, "AddInfos": (info or "")[:400]})
    value_counts = Counter()
    class_species = Counter()
    for spec, values in by_species.items():
        kinds = set()
        for value in values:
            value_counts[value] += 1
            kinds.add(classify(value))
        if "refuting" in kinds:
            class_species["refuting"] += 1
        elif "unclassified" in kinds:
            class_species["unclassified"] += 1
        else:
            class_species["compatible"] += 1
    n = len(by_species)
    n_ref = class_species["refuting"]
    n_unc = class_species["unclassified"]
    anat = anatomy(
        blobs["anatomy_item.txt"].decode("utf-8", "replace"),
        blobs["anatomy_relationship.txt"].decode("utf-8", "replace"),
    )
    if n == 0:
        verdict, reason = "inconclusive", "data-unavailable"
    elif n_ref >= 1 or anat["mouth_gonad_bridges"]:
        verdict, reason = "refutes", None
    elif 0 < n < 200:
        verdict, reason = "inconclusive", "underpowered"
    elif n_unc > 0 and n_ref == 0:
        verdict, reason = "mixed", None
    elif n_ref == 0 and n_unc == 0 and n >= 200 and anat["affirmed"]:
        verdict, reason = "supports", None
    elif n_ref == 0 and n_unc == 0 and n >= 200 and not anat["has_mouth_and_intestine"]:
        verdict, reason = "mixed", None
    else:
        verdict, reason = "mixed", None
    measured = {
        "value": n_ref,
        "unit": "species whose Fertilization code describes a gut-to-uterus route",
        "n": n,
        "uncertainty": None,
        "extra": {
            "compatible_species": class_species["compatible"],
            "unclassified_species": n_unc,
            "fertilization_value_counts": dict(value_counts),
            "in_mouth_species": value_counts.get("in mouth", 0),
            "other_code_notes": other_notes,
            "anatomy": anat,
        },
    }
    confidence = 0.78 if verdict == "mixed" and n_ref == 0 and anat["affirmed"] else 0.55
    result = json.loads((HERE / "result.json").read_text())
    result["deviations"] = [{
        "change": "Three stored Fertilization strings were accepted as the pre-registered compatible phrases with the articles removed: 'in mouth' for 'in the mouth', 'in brood pouch or similar structure' for 'in a brood pouch or similar structure', and 'internal (oviduct)' (already covered by the prefix 'internal', listed here for the record).",
        "why": "FishBase stores those strings rather than the manual's wording, which was what the closed list quoted. The code 'other' was not mapped onto 'elsewhere' and remains unclassified. Thresholds were not changed. The four 'other' notes are copied into measured.extra and are not used to reclassify those species.",
    }]
    result.update({
        "status": "complete",
        "data_kind": "biological",
        "datasets": [
            {
                "id": "fishbase-v26.06-reproduc",
                "name": "FishBase reproduction table, rfishbase snapshot v26.06",
                "landing_url": "https://www.fishbase.se/",
                "doi": None,
                "version": "v26.06",
                "license": None,
                "files": [m for m in meta if m["name"] == "reproduc.parquet"],
                "role": "where egg and sperm meet, one row set per species",
            },
            {
                "id": "zfin-anatomy-relationship",
                "name": "ZFIN anatomy item and relationship tables",
                "landing_url": "https://zfin.org/downloads",
                "doi": None,
                "version": None,
                "license": None,
                "files": [m for m in meta if m["name"] != "reproduc.parquet"],
                "role": "zebrafish graph of mouth, intestine and gonad",
            },
        ],
        "measured": measured,
        "verdict": verdict,
        "confidence": confidence,
        "method": (
            "Read Fertilization for every non-empty FishBase reproduc row in snapshot v26.06, "
            "counted distinct SpecCode values, and classed each code with the pre-registered list "
            "plus the article-dropping deviation. Walked ZFIN part-of and is-a links from mouth and "
            "intestine toward a shared digestive ancestor, and checked continuous-with edges between "
            "mouth and gonad terms."
        ),
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["results_summary"] = [
        f"{n} species have a fertilization code; {n_ref} refuting; {n_unc} unclassified; {class_species['compatible']} compatible.",
        "Value counts: " + ", ".join(f"{k}={v}" for k, v in value_counts.most_common()),
        f"Zebrafish anatomy affirmed={anat['affirmed']}; shared ancestors={anat['shared_digestive_ancestors']}; mouth-gonad bridges={len(anat['mouth_gonad_bridges'])}.",
    ]
    (DERIVED / "measured.json").write_text(json.dumps({"measured": measured, "verdict": verdict}, indent=2) + "\n")
    (HERE / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, measured["value"], "n", n, "unc", n_unc, "anat", anat["affirmed"])


if __name__ == "__main__":
    main()
