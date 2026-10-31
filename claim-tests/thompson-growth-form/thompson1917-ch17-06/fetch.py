#!/usr/bin/env python3
"""Search the public sources pre-registered for claim ch17-06 (ox, sheep and giraffe
cannon-bones) and record, for each query, the HTTP status, the number of hits and a
SHA-256 of the response body.  Writes derived/source_probe.json.

This is a search log, not a data download: no source was found that gives metacarpal
greatest length and breadth for all three species without authentication (see
result.json).  Re-running it reproduces the log; hit counts may change as catalogues grow.
"""
import hashlib, json, os, time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
UA = {"Accept": "application/json"}

QUERIES = [
    ("morphosource", "https://www.morphosource.org/api/media?q=Giraffa&per_page=5", "3D media of giraffe"),
    ("morphosource", "https://www.morphosource.org/api/media?q=Giraffa+metacarpal&per_page=5", "3D media of giraffe metacarpal"),
    ("morphosource", "https://www.morphosource.org/api/media?q=Giraffa+metatarsal&per_page=5", "3D media of giraffe metatarsal"),
    ("morphosource", "https://www.morphosource.org/api/media?q=Bos+taurus+metacarpal&per_page=5", "3D media of ox metacarpal"),
    ("morphosource", "https://www.morphosource.org/api/media?q=Ovis+aries+metacarpal&per_page=5", "3D media of sheep metacarpal"),
    ("zenodo", "https://zenodo.org/api/records?q=%28metacarpal%20OR%20metapodial%20OR%20%22cannon%20bone%22%29%20AND%20%28measurements%20OR%20osteometric%29&size=15&type=dataset", "osteometric metapodial datasets"),
    ("zenodo", "https://zenodo.org/api/records?q=giraffe%20metacarpal&size=10&type=dataset", "giraffe metacarpal datasets"),
    ("dryad", "https://datadryad.org/api/v2/search?q=giraffe%20limb%20bone&per_page=15", "giraffe limb bone datasets"),
    ("dryad", "https://datadryad.org/api/v2/search?q=metapodial%20measurements&per_page=15", "metapodial measurement datasets"),
    ("geome-futres", "https://api.geome-db.org/records/Sample/json?q=genus%3DGiraffa&limit=5", "FuTRES/GEOME trait records for Giraffa"),
    ("ads-abmap", "https://archaeologydataservice.ac.uk/archives/view/abmap/", "Animal Bone Metrical Archive Project (ox, sheep)"),
    ("opencontext", "https://opencontext.org/query/?q=metacarpal&response=metadata", "Open Context zooarchaeological measurements"),
]


def hits(source, body):
    try:
        j = json.loads(body)
    except Exception:  # noqa: BLE001
        return None
    if source == "morphosource":
        return j.get("response", {}).get("pages", {}).get("total_count")
    if source == "zenodo":
        t = j.get("hits", {}).get("total")
        return t.get("value") if isinstance(t, dict) else t
    if source == "dryad":
        return j.get("total")
    if source == "geome-futres":
        return sum(len(v) for v in j.get("content", {}).values())
    return None


def main():
    os.makedirs(DERIVED, exist_ok=True)
    log = []
    for source, url, what in QUERIES:
        entry = {"source": source, "url": url, "looking_for": what,
                 "queried_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        try:
            r = requests.get(url, headers=UA, timeout=90)
            entry.update({"http_status": r.status_code, "byte_size": len(r.content),
                          "sha256": hashlib.sha256(r.content).hexdigest(),
                          "content_type": r.headers.get("Content-Type", ""), "hits": hits(source, r.text)})
            if "not a bot" in r.text[:2000] or "Just a moment" in r.text[:2000]:
                entry["blocked"] = "bot challenge served instead of content"
        except Exception as e:  # noqa: BLE001
            entry["error"] = f"{type(e).__name__}: {e}"
        log.append(entry)
        print(json.dumps(entry))
    json.dump(log, open(os.path.join(DERIVED, "source_probe.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
