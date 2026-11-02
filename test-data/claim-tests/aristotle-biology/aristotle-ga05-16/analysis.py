#!/usr/bin/env python3
"""iNaturalist search for white individuals of four groups named by Aristotle."""
import datetime as dt
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test/aristotle-ga05-16 (research)"}


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        return json.loads(raw), raw, r.geturl()


def taxon_ok(taxon, species):
    name = ((taxon or {}).get("name") or "")
    return name == species or name.startswith(species + " ")


def text_blob(obs):
    parts = [obs.get("description") or ""]
    parts.extend(obs.get("tags") or [])
    for field in obs.get("ofvs") or []:
        parts.append(str(field.get("name") or ""))
        parts.append(str(field.get("value") or ""))
    return "\n".join(parts)


def term_hits(blob, terms, negation):
    hits = []
    low = blob.lower()
    for term in terms:
        start = 0
        t = term.lower()
        while True:
            i = low.find(t, start)
            if i < 0:
                break
            before = low[max(0, i - 40):i]
            if not negation.search(before):
                snippet = blob[max(0, i - 60):i + len(term) + 80].replace("\n", " ")
                hits.append({"term": term, "snippet": snippet[:180]})
                break
            start = i + len(t)
    return hits


def main():
    result = json.loads(RESULT.read_text())
    rules = result["rules"]
    negation = re.compile(rules["negation"])
    calls = []
    matches = {group: [] for group in rules["groups"]}
    errors = []
    for group, species_list in rules["groups"].items():
        if matches[group]:
            continue
        for species in species_list:
            if matches[group]:
                break
            for term in rules["terms"][group]:
                if matches[group]:
                    break
                for page in range(1, rules["max_pages"] + 1):
                    params = {
                        "taxon_name": species,
                        "quality_grade": rules["quality_grade"],
                        "q": term,
                        "per_page": rules["per_page"],
                        "page": page,
                        "order": "desc",
                        "order_by": "votes",
                    }
                    url = rules["endpoint"] + "?" + urllib.parse.urlencode(params)
                    time.sleep(0.4)
                    try:
                        payload, raw, final = get_json(url)
                    except Exception as exc:
                        errors.append({"url": url, "error": str(exc)})
                        break
                    calls.append({
                        "url": final,
                        "byte_size": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "n_results": len(payload.get("results") or []),
                    })
                    for obs in payload.get("results") or []:
                        if not taxon_ok(obs.get("taxon"), species):
                            continue
                        if not obs.get("photos"):
                            continue
                        hits = term_hits(text_blob(obs), [term], negation)
                        if not hits:
                            continue
                        matches[group].append({
                            "id": obs.get("id"),
                            "uri": obs.get("uri"),
                            "species": (obs.get("taxon") or {}).get("name"),
                            "license_code": obs.get("license_code"),
                            "quality_grade": obs.get("quality_grade"),
                            "term": hits[0]["term"],
                            "snippet": hits[0]["snippet"],
                        })
                        break
                    if matches[group] or len(payload.get("results") or []) < rules["per_page"]:
                        break
    found = {g: len(v) for g, v in matches.items()}
    n_groups = sum(1 for n in found.values() if n > 0)
    if errors and n_groups == 0:
        verdict, reason, conf = "inconclusive", "data-unavailable", rules["confidence_inconclusive"]
    elif n_groups == 4:
        verdict, reason, conf = "supports", None, rules["confidence_supports"]
    elif n_groups == 0:
        verdict, reason, conf = "inconclusive", "underpowered", rules["confidence_inconclusive"]
    else:
        verdict, reason, conf = "mixed", None, rules["confidence_mixed"]
    kept = {g: v[:5] for g, v in matches.items()}
    measured = {
        "value": n_groups,
        "unit": "named groups with at least one qualifying observation",
        "n": sum(found.values()),
        "extra": {"groups_with_match": found, "api_errors": errors, "observations": kept},
    }
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2, ensure_ascii=False) + "\n")
    (DERIVED / "api_calls.json").write_text(json.dumps(calls, indent=2) + "\n")
    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = conf
    result["data_kind"] = "biological" if calls else "none"
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["measured"] = measured
    result["method"] = (
        "Queried the iNaturalist observations API for each pre-registered species and colour term, "
        "kept research-grade observations with a photo whose community taxon matched the species, "
        "and required the term in the description, tags, or observation fields without a negation in the preceding window."
    )
    result["results_summary"] = [
        f"Groups with a qualifying observation: {n_groups} of 4 ({found}).",
        f"API calls: {len(calls)}. Errors: {len(errors)}.",
        f"Verdict {verdict}.",
    ]
    result["datasets"] = [{
        "id": "inaturalist-observations-api",
        "name": "iNaturalist observations API, research-grade text search",
        "landing_url": "https://www.inaturalist.org/",
        "doi": None,
        "version": "api v1",
        "license": "per-observation license_code in derived/measured.json",
        "files": calls,
        "role": "photographed observations scored for white, albino, or leucistic wording",
    }]
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, found)


if __name__ == "__main__":
    main()
