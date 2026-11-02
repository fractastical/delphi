#!/usr/bin/env python3
"""Test aristotle-ha02-16 against the Zebrafish Anatomy Ontology and Uberon."""

import hashlib
import json
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ZFA_URL = "https://purl.obolibrary.org/obo/zfa.obo"
UBERON_URL = "https://github.com/obophenotype/uberon/releases/download/v2026-10-01/uberon.obo"
HERE = Path(__file__).resolve().parent

LABELS = {
    "neck": {"neck"},
    "limb": {"limb", "forelimb", "hindlimb"},
    "testis": {"testis", "testicle", "testicles"},
    "mammary": {"mammary gland", "breast"},
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "DelphiClaimTest/1.0"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=180, context=ctx) as resp:
        data = resp.read()
        retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        final = resp.geturl()
    return data, retrieved, final


def terms(obo_text):
    blocks = []
    current = []
    for line in obo_text.splitlines():
        if line.startswith("[Term]"):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append(current)
    parsed = []
    for block in blocks:
        term = {"id": None, "name": None, "synonyms": [], "relations": []}
        for line in block:
            if line.startswith("id:"):
                term["id"] = line.split(":", 1)[1].strip()
            elif line.startswith("name:"):
                term["name"] = line.split(":", 1)[1].strip()
            elif line.startswith("synonym:"):
                # synonym: "label" SCOPE
                try:
                    label = line.split('"', 2)[1]
                except IndexError:
                    continue
                term["synonyms"].append(label)
            elif line.startswith("relationship:"):
                term["relations"].append(line.split(":", 1)[1].strip())
        if term["id"] and term["name"]:
            parsed.append(term)
    return parsed


def labels_of(term):
    names = {term["name"].lower()}
    names.update(s.lower() for s in term["synonyms"])
    return names


def zfa_hits(zfa_terms):
    found = {key: [] for key in LABELS}
    for term in zfa_terms:
        names = labels_of(term)
        for key, wanted in LABELS.items():
            if names & wanted:
                found[key].append({"id": term["id"], "name": term["name"], "synonyms": term["synonyms"]})
    return found


def relation_taxon(rel):
    # relationship: in_taxon NCBITaxon:40674 ! Mammalia
    parts = rel.split()
    if len(parts) < 2:
        return None, None, None
    kind = parts[0]
    taxon = next((p for p in parts[1:] if p.startswith("NCBITaxon:")), None)
    label = rel.split("!", 1)[1].strip() if "!" in rel else None
    return kind, taxon, label


def uberon_axioms(uberon_terms):
    wanted_ids = {}
    for term in uberon_terms:
        names = labels_of(term)
        for key, wanted in LABELS.items():
            if term["name"] and term["name"].lower() in wanted:
                wanted_ids.setdefault(key, []).append(term)
    axioms = {}
    for key, terms_ in wanted_ids.items():
        rows = []
        for term in terms_:
            for rel in term["relations"]:
                if "taxon" not in rel.lower() and "NCBITaxon:" not in rel:
                    continue
                kind, taxon, label = relation_taxon(rel)
                rows.append(
                    {
                        "id": term["id"],
                        "name": term["name"],
                        "relation": kind,
                        "taxon": taxon,
                        "taxon_label": label,
                        "raw": rel[:300],
                    }
                )
        axioms[key] = rows
    return axioms


def restricts_to_nonfish(axioms):
    """in_taxon or only_in_taxon naming a clade that is not itself a fish clade."""
    fish_labels = {"teleostei", "actinopterygii", "chondrichthyes", "sarcopterygii"}
    nonfish = {"mammalia", "tetrapoda", "amniota"}
    for row in axioms:
        rel = (row.get("relation") or "").lower()
        label = (row.get("taxon_label") or "").lower()
        if rel in ("in_taxon", "only_in_taxon") and label in nonfish:
            return True
        if rel == "never_in_taxon" and label in fish_labels:
            return True
    return False


def dubious_for_fish(axioms):
    for row in axioms:
        rel = (row.get("relation") or "").lower()
        label = (row.get("taxon_label") or "").lower()
        if rel == "dubious_for_taxon" and label in {"teleostei", "actinopterygii", "chondrichthyes"}:
            return True
    return False


def main():
    zfa_raw, zfa_at, zfa_final = fetch(ZFA_URL)
    uberon_raw, uberon_at, uberon_final = fetch(UBERON_URL)
    zfa_text = zfa_raw.decode("utf-8", errors="replace")
    uberon_text = uberon_raw.decode("utf-8", errors="replace")
    zfa = zfa_hits(terms(zfa_text))
    axioms = uberon_axioms(terms(uberon_text))

    # A clause is contradicted by a zebrafish anatomy term with that label,
    # which is a structure of Danio rerio. It is supported by absence of that
    # label from ZFA, or by an Uberon restriction to a non-fish clade.
    clauses = {}
    for key in LABELS:
        present_in_zebrafish = bool(zfa[key])
        restricted = restricts_to_nonfish(axioms.get(key, []))
        dubious = dubious_for_fish(axioms.get(key, []))
        if present_in_zebrafish:
            state = "contradicted"
        elif restricted or not present_in_zebrafish:
            # Label absence in the zebrafish anatomy ontology supports the
            # clause for that fish, per the pre-registered rule. An Uberon
            # restriction is additional support when present.
            state = "supported"
        else:
            state = "unrecorded"
        clauses[key] = {
            "state": state,
            "zebrafish_terms": zfa[key],
            "uberon_restriction_to_nonfish": restricted,
            "uberon_dubious_for_a_fish_clade": dubious,
            "uberon_taxon_axioms": axioms.get(key, []),
        }

    contradicted = [k for k, v in clauses.items() if v["state"] == "contradicted"]
    supported = [k for k, v in clauses.items() if v["state"] == "supported"]
    if not contradicted and len(supported) == 4:
        verdict, reason = "supports", None
    elif "testis" in contradicted and not supported:
        verdict, reason = "refutes", None
    elif contradicted and supported:
        verdict, reason = "mixed", None
    elif not contradicted and not supported:
        verdict, reason = "inconclusive", "not-operationalizable"
    else:
        verdict, reason = "refutes" if "testis" in contradicted else "mixed", None

    measured = {
        "value": len(contradicted),
        "unit": "clauses contradicted, of neck, limb, testis and mammary gland",
        "n": 4,
        "uncertainty": None,
        "extra": {
            "clauses": {
                k: {
                    "state": v["state"],
                    "zebrafish_terms": v["zebrafish_terms"],
                    "uberon_restriction_to_nonfish": v["uberon_restriction_to_nonfish"],
                    "uberon_dubious_for_a_fish_clade": v["uberon_dubious_for_a_fish_clade"],
                    "uberon_taxon_axioms": v["uberon_taxon_axioms"],
                }
                for k, v in clauses.items()
            },
            "contradicted": contradicted,
            "supported": supported,
            "verdict_from_criteria": verdict,
            "reason": reason,
        },
    }
    out = {
        "zfa": {
            "retrieved_at": zfa_at,
            "download_url": ZFA_URL,
            "byte_size": len(zfa_raw),
            "sha256": hashlib.sha256(zfa_raw).hexdigest(),
        },
        "uberon": {
            "retrieved_at": uberon_at,
            "download_url": UBERON_URL,
            "byte_size": len(uberon_raw),
            "sha256": hashlib.sha256(uberon_raw).hexdigest(),
        },
        "measured": measured,
    }
    derived = HERE / "derived"
    derived.mkdir(exist_ok=True)
    (derived / "measured.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "contradicted": contradicted, "supported": supported, "zfa_sha": out["zfa"]["sha256"], "uberon_sha": out["uberon"]["sha256"]}, indent=2))


if __name__ == "__main__":
    main()
