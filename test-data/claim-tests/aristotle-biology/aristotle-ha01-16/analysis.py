#!/usr/bin/env python3
"""Test aristotle-ha01-16: the ear opens on the palate and not on the brain."""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import quote

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

SEARCH = "https://www.ebi.ac.uk/ols4/api/search"


def save(name, payload):
    path = os.path.join(DATA, name)
    raw = json.dumps(payload).encode()
    open(path, "wb").write(raw)
    return {
        "download_url": payload.get("_download_url", ""),
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "label": name,
    }


def get(url):
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    return r.json(), r.url


def search(ontology, query):
    data, url = get(SEARCH + f"?q={quote(query)}&ontology={ontology}&rows=15")
    data["_download_url"] = url
    return data


def term(ontology, iri):
    url = f"https://www.ebi.ac.uk/ols4/api/ontologies/{ontology}/terms/" + quote(quote(iri, safe=""), safe="")
    data, final = get(url)
    data["_download_url"] = final
    return data


def defs(doc):
    desc = doc.get("description") or []
    if isinstance(desc, str):
        desc = [desc]
    return [d for d in desc if not str(d).startswith("EDITOR_NOTE")]


def mentions_link(text):
    ear = bool(re.search(r"middle ear|tympanic", text, re.I))
    pharynx = bool(re.search(r"pharynx|nasopharynx|palate", text, re.I))
    return ear and pharynx


def mentions_brain_passage(text):
    return bool(re.search(r"brain|cranial cavity", text, re.I)) and bool(
        re.search(r"connect|passage|open|lumen|continu", text, re.I)
    )


def pick(docs, label):
    label = label.lower()
    for doc in docs:
        if (doc.get("label") or "").lower() == label:
            return doc
    return None


def ontology_report(ontology, queries):
    files = []
    found = {}
    for q in queries:
        data = search(ontology, q)
        files.append(save(f"{ontology}-search-{q.replace(' ', '_')}.json", data))
        docs = data.get("response", {}).get("docs", [])
        for label in ("pharyngotympanic tube", "auditory tube", "tympanic cavity"):
            hit = pick(docs, label)
            if hit and label not in found:
                found[label] = hit
    reports = {}
    for label, hit in found.items():
        full = term(ontology, hit["iri"])
        files.append(save(f"{ontology}-term-{hit.get('short_form') or label}.json", full))
        text = " ".join(defs(full) or defs(hit))
        reports[label] = {
            "iri": hit.get("iri"),
            "obo_id": hit.get("obo_id"),
            "definition": text[:800],
            "links_ear_and_pharynx": mentions_link(text),
            "states_brain_passage": mentions_brain_passage(text),
        }
    tube = reports.get("pharyngotympanic tube") or reports.get("auditory tube")
    cavity = reports.get("tympanic cavity")
    return {
        "tube": tube,
        "cavity": cavity,
        "supports": bool(tube and tube["links_ear_and_pharynx"] and not tube["states_brain_passage"]
                         and (cavity is None or not cavity["states_brain_passage"])),
        "brain_passage": bool((tube and tube["states_brain_passage"]) or (cavity and cavity["states_brain_passage"])),
        "files": files,
    }


def main():
    uberon = ontology_report("uberon", ["pharyngotympanic tube", "tympanic cavity"])
    fma = ontology_report("fma", ["pharyngotympanic tube", "tympanic cavity"])
    json.dump({"uberon": {k: v for k, v in uberon.items() if k != "files"},
               "fma": {k: v for k, v in fma.items() if k != "files"}},
              open(os.path.join(DERIVED, "anatomy.json"), "w"), indent=2)

    if uberon["brain_passage"] or fma["brain_passage"]:
        verdict, reason = "refutes", None
    elif uberon["supports"] and fma["supports"]:
        verdict, reason = "supports", None
    elif uberon["supports"] ^ fma["supports"]:
        verdict, reason = "mixed", None
    elif not uberon["tube"] or not fma["tube"]:
        # One missing tube cannot refute. Refutation requires both tubes and no pharyngeal link.
        verdict, reason = "inconclusive", "data-unavailable"
    else:
        verdict, reason = "refutes", None

    def core_sentence(text):
        text = re.sub(r"^Old definition:\s*", "", (text or "").strip(), flags=re.I)
        text = text.replace("[FMA].", "").replace("[FMA]", "")
        return re.sub(r"\s+", " ", text).strip()

    same = False
    if uberon["tube"] and fma["tube"]:
        u = core_sentence(uberon["tube"]["definition"])
        f = core_sentence(fma["tube"]["definition"])
        same = bool(u and f and (u == f or u in f or f in u))
    if verdict == "supports":
        confidence = 0.6 if same else 0.7
    elif verdict == "refutes":
        confidence = 0.65
    elif verdict == "mixed":
        confidence = 0.5
    else:
        confidence = 0.35

    measured = {
        "value": int(bool(uberon["supports"]) + int(bool(fma["supports"]))),
        "unit": "ontologies whose auditory-tube definition links middle ear and pharynx and states no brain passage",
        "n": 2,
        "uncertainty": "two curated ontologies, not a sample of heads",
        "extra": {
            "uberon_supports": uberon["supports"],
            "fma_supports": fma["supports"],
            "uberon_tube_definition": None if not uberon["tube"] else uberon["tube"]["definition"],
            "fma_tube_definition": None if not fma["tube"] else fma["tube"]["definition"],
            "definitions_are_the_same_sentence": same,
            "uberon_brain_passage": uberon["brain_passage"],
            "fma_brain_passage": fma["brain_passage"],
        },
    }
    if "--write-result" in sys.argv:
        result = json.load(open(os.path.join(HERE, "result.json")))
        result["status"] = "complete"
        result["data_kind"] = "biological" if verdict != "inconclusive" else "none"
        result["verdict"] = verdict
        if reason:
            result["reason"] = reason
        result["confidence"] = confidence
        result["measured"] = measured
        result["datasets"] = [
            {
                "id": "ebi-ols-uberon",
                "name": "Uberon auditory-tube and tympanic-cavity terms from the EBI Ontology Lookup Service",
                "landing_url": "https://www.ebi.ac.uk/ols4/ontologies/uberon",
                "doi": None,
                "version": "OLS4 live terms",
                "license": "CC BY 4.0",
                "role": "definition of the pharyngotympanic tube",
                "files": uberon["files"],
            },
            {
                "id": "ebi-ols-fma",
                "name": "Foundational Model of Anatomy terms from the EBI Ontology Lookup Service",
                "landing_url": "https://www.ebi.ac.uk/ols4/ontologies/fma",
                "doi": None,
                "version": "OLS4 live terms",
                "license": "CC BY 4.0",
                "role": "definition of the pharyngotympanic tube",
                "files": fma["files"],
            },
        ]
        result["method"] = (
            "analysis.py searches OLS for the pharyngotympanic tube and the tympanic cavity in Uberon and FMA, "
            "then reads each term's definition, skipping EDITOR_NOTE lines. "
            "A source supports the claim when the tube definition names both the middle ear or tympanic cavity and the pharynx, "
            "and neither definition states a passage into the brain or cranial cavity. "
            "Both sources must agree for support. Confidence is capped at 0.7 because these are curated relations, not dissected heads."
        )
        result["caveats"] = [
            "The ontologies compile anatomical descriptions. They do not count how often the tube is patent in living people.",
            "Uberon's tube definition is the FMA sentence, so the two sources are not independent.",
            "FMA's tympanic-cavity term returned no definition text, so that term does not state a brain passage because it states nothing. Uberon's tympanic-cavity definition does not mention the brain.",
            "Aristotle's palate is read as the nasopharynx, where the auditory tube opens. The definitions say pharynx.",
            "No imaging or dissection series was measured.",
        ]
        json.dump(result, open(os.path.join(HERE, "result.json"), "w"), indent=2)
        open(os.path.join(HERE, "result.json"), "a").write("\n")
    print(json.dumps({"verdict": verdict, "confidence": confidence, "same": same,
                      "uberon": uberon["supports"], "fma": fma["supports"]}))


if __name__ == "__main__":
    main()
