#!/usr/bin/env python3
"""aristotle-ha03-07: aorta and vena cava continuity with the heart in Uberon.

Rules are those in result.json. Run: python3 analysis.py
"""
import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
DERIVED = HERE / "derived"
DATA = HERE / "data"
URL = "https://github.com/obophenotype/uberon/releases/download/v2026-10-01/uberon-basic.obo"
CONTINUITY = {
    "continuous_with", "connected_to", "connects", "adjacent_to", "supplies", "drains",
    "branches_from", "tributary_of", "ro:0002150", "ro:0002170", "ro:0002176",
}
DEVELOPS = {"develops_from", "ro:0002202"}
VEIN_NAMES = {
    "posterior vena cava", "caudal vena cava", "vena cava",
    "anterior vena cava", "cranial vena cava",
}


def fetch():
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / "uberon-basic.obo"
    if not path.exists():
        req = urllib.request.Request(URL, headers={"User-Agent": "delphisci-claim-test"})
        path.write_bytes(urllib.request.urlopen(req, timeout=180).read())
    raw = path.read_bytes()
    return raw, {
        "name": "uberon-basic.obo",
        "download_url": URL,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def parse_obo(text):
    terms = {}
    current = None
    rel_count = 0
    for line in text.splitlines():
        if line == "[Term]":
            current = {"id": None, "name": None, "rels": []}
            continue
        if line.startswith("[") and line.endswith("]"):
            current = None
            continue
        if current is None or not line or line.startswith("!"):
            continue
        if line.startswith("id:"):
            current["id"] = line.split(":", 1)[1].strip()
            terms[current["id"]] = current
        elif line.startswith("name:"):
            current["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("relationship:"):
            rest = line.split(":", 1)[1].strip()
            # "continuous_with UBERON:0001234 ! label" or "RO:0002150 UBERON:0001234"
            parts = rest.split()
            if len(parts) < 2:
                continue
            pred, obj = parts[0], parts[1]
            current["rels"].append((pred, obj))
            rel_count += 1
    return terms, rel_count


def is_heart(name):
    n = (name or "").casefold()
    return n == "heart" or any(tok in n for tok in ("heart", "ventricle", "atrium", "cardiac", "bulbus arteriosus", "conus arteriosus"))


def is_brain_or_head(name):
    n = (name or "").casefold()
    return n in {"brain", "head"} or "brain" in n


def describe(term, terms):
    heart, brain, develops_brain = [], [], []
    for pred, obj in term["rels"]:
        pred_l = pred.casefold()
        target = terms.get(obj)
        tname = target["name"] if target else obj
        if pred_l in CONTINUITY and is_heart(tname):
            heart.append({"predicate": pred, "id": obj, "name": tname})
        if pred_l in CONTINUITY and is_brain_or_head(tname):
            brain.append({"predicate": pred, "id": obj, "name": tname})
        if pred_l in DEVELOPS and is_brain_or_head(tname):
            develops_brain.append({"predicate": pred, "id": obj, "name": tname})
    return {"id": term["id"], "name": term["name"], "heart": heart, "brain_continuity": brain, "develops_from_brain_or_head": develops_brain}


def main():
    result = json.loads(RESULT.read_text())
    DERIVED.mkdir(parents=True, exist_ok=True)
    raw, info = fetch()
    text = raw.decode("utf-8", errors="replace")
    license_line = None
for ln in text.splitlines()[:80]:
    low = ln.lower()
    if "creativecommons.org" in low or "dcterms:license" in low or low.startswith("remark: license"):
        license_line = ln.strip()
        break
    terms, rel_count = parse_obo(text)
    by_name = {}
    for t in terms.values():
        if t.get("name"):
            by_name.setdefault(t["name"].casefold(), t)

    aorta = by_name.get("aorta")
    veins = []
    for name in sorted(VEIN_NAMES):
        term = by_name.get(name)
        if term:
            veins.append(describe(term, terms))
    if rel_count == 0 or aorta is None:
        reason = "data-unavailable" if rel_count == 0 or aorta is None else "not-operationalizable"
        measured = {"value": 0, "unit": "great vessels continuous with the heart", "n": 0, "extra": {"relation_rows": rel_count, "aorta_found": aorta is not None, "n_terms": len(terms)}}
        verdict, conf, data_kind = "inconclusive", 0.3, "none"
    else:
        aorta_d = describe(aorta, terms)
        vein_heart = [v for v in veins if v["heart"]]
        develops = aorta_d["develops_from_brain_or_head"] + [d for v in veins for d in v["develops_from_brain_or_head"]]
        aorta_brain_only = bool(aorta_d["brain_continuity"]) and not aorta_d["heart"]
        n_vessels = int(bool(aorta_d["heart"])) + int(bool(vein_heart))
        measured = {
            "value": n_vessels,
            "unit": "great-vessel groups (aorta, vena cava) with a heart-continuity relation",
            "n": 1 + len(veins),
            "extra": {
                "relation_rows_parsed": rel_count,
                "aorta": {k: aorta_d[k] for k in ("id", "name", "heart", "brain_continuity", "develops_from_brain_or_head")},
                "vena_cava_terms": veins,
                "n_vena_cava_terms_found": len(veins),
            },
        }
        if develops or aorta_brain_only:
            verdict, reason, conf, data_kind = "refutes", None, 0.7, "biological"
        elif aorta_d["heart"] and vein_heart and not develops:
            verdict, reason, conf, data_kind = "supports", None, 0.55, "biological"
        elif not aorta_d["heart"] and not aorta_d["brain_continuity"]:
            verdict, reason, conf, data_kind = "inconclusive", "not-operationalizable", 0.35, "none"
        else:
            verdict, reason, conf, data_kind = "mixed", None, 0.5, "biological"

    result.update({
        "status": "complete",
        "verdict": verdict,
        "confidence": conf,
        "data_kind": data_kind,
        "measured": measured,
        "method": "Parsed Uberon basic v2026-10-01 term blocks, matched the aorta and the listed vena-cava names, and scored continuity with heart structures against develops_from brain or head, using the predicates fixed in the pre-registration.",
        "datasets": [{
            "id": "uberon-basic-v2026-10-01",
            "name": "Uberon basic anatomy ontology, release v2026-10-01",
            "landing_url": "https://obophenotype.github.io/uberon/",
            "doi": None,
            "version": "v2026-10-01",
            "license": license_line,
            "files": [info],
            "role": "cross-species relations of the aorta and the vena cava to the heart and the brain",
        }],
    })
    if reason:
        result["reason"] = reason
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, measured.get("value"), rel_count if "rel_count" in dir() else "")


if __name__ == "__main__":
    main()
