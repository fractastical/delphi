#!/usr/bin/env python3
"""Find and (attempt to) download public 3D scans of bovid crania with both horn
cores, for claim ch13-02.  Writes derived/candidate_media.csv (the MorphoSource
media that would serve) and derived/source_probe.json (the access log).

Outcome in this run: the catalogue search works, but every download route tested
is blocked (MorphoSource serves an Anubis 'Access Denied' page to this host, and
its downloads require an account and acceptance of a use agreement), so no mesh
was obtained and the claim is recorded inconclusive / data-unavailable.
"""
import csv, hashlib, json, os, time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
API = "https://www.morphosource.org/api/media"
SEARCHES = ["horn", "horncore", "Bovidae", "Capra", "Ovis", "Bos", "Oryx", "Gazella", "Ammotragus", "Bison"]
BOVID = ("Ovis", "Capra", "Bos", "Bison", "Oryx", "Gazella", "Ammotragus", "Bubalus", "Antidorcas", "Aepyceros",
         "Tragelaphus", "Taurotragus", "Syncerus", "Budorcas", "Hemitragus", "Rupicapra", "Pantholops",
         "Saiga", "Redunca", "Qurliqnoria", "Gazellospira", "Caprovis", "Caprotragoides", "Leptobos")
PAIRED = ("cranium", "skull")  # a single horn or horn core cannot test left-vs-right


def main():
    os.makedirs(DERIVED, exist_ok=True)
    probe, found = [], {}
    for q in SEARCHES:
        entry = {"source": "morphosource-api", "url": f"{API}?q={q}&per_page=50",
                 "queried_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        try:
            r = requests.get(API, params={"q": q, "per_page": 50}, headers={"Accept": "application/json"}, timeout=90)
            entry.update({"http_status": r.status_code, "byte_size": len(r.content),
                          "sha256": hashlib.sha256(r.content).hexdigest()})
            d = r.json()["response"]
            entry["hits"] = d["pages"]["total_count"]
            for m in d["media"]:
                tax = (m.get("physical_object_taxonomy_name") or [""])[0]
                title = (m.get("title") or [""])[0]
                if not tax.startswith(BOVID):
                    continue
                found[m["id"][0]] = {
                    "media_id": m["id"][0], "taxon": tax, "title": title,
                    "part": (m.get("part") or [""])[0], "media_type": (m.get("media_type") or [""])[0],
                    "visibility": (m.get("visibility") or [""])[0] if m.get("visibility") else "",
                    "file_size_all": (m.get("file_size_all") or [None])[0],
                    "use_agreement": (m.get("morphosource_use_agreement_type") or [""])[0] if m.get("morphosource_use_agreement_type") else "",
                    "shows_both_horns": any(w in title.lower() or w in (m.get("part") or [""])[0].lower() for w in PAIRED),
                }
        except Exception as e:  # noqa: BLE001
            entry["error"] = f"{type(e).__name__}: {e}"
        probe.append(entry)
    with open(os.path.join(DERIVED, "candidate_media.csv"), "w", newline="") as f:
        cols = ["media_id", "taxon", "title", "part", "media_type", "visibility", "file_size_all", "use_agreement", "shows_both_horns"]
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for v in sorted(found.values(), key=lambda v: (v["taxon"], v["media_id"])):
            w.writerow(v)
    # Attempt to download one open-visibility cranium mesh.
    for mid in [v["media_id"] for v in found.values() if v["visibility"] == "open" and v["shows_both_horns"]][:2]:
        for url in (f"https://www.morphosource.org/api/media/{mid}/download",
                    f"https://www.morphosource.org/media_downloads/{mid}",
                    f"https://www.morphosource.org/concern/media/{mid}"):
            entry = {"source": "morphosource-download", "url": url,
                     "queried_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            try:
                r = requests.get(url, timeout=120, allow_redirects=True)
                entry.update({"http_status": r.status_code, "byte_size": len(r.content),
                              "content_type": r.headers.get("Content-Type", ""),
                              "sha256": hashlib.sha256(r.content).hexdigest()})
                if "not a bot" in r.text[:3000] or "Anubis" in r.text[:3000] or "Access Denied" in r.text[:3000]:
                    entry["blocked"] = "bot challenge / access denied page instead of content"
            except Exception as e:  # noqa: BLE001
                entry["error"] = f"{type(e).__name__}: {e}"
            probe.append(entry)
    json.dump(probe, open(os.path.join(DERIVED, "source_probe.json"), "w"), indent=1)
    n_pair = sum(v["shows_both_horns"] for v in found.values())
    n_open_pair = sum(v["shows_both_horns"] and v["visibility"] == "open" for v in found.values())
    print(json.dumps({"bovid_media": len(found), "cranium_or_skull": n_pair, "open_cranium_or_skull": n_open_pair,
                      "downloads_blocked": sum("blocked" in p or "error" in p or p.get("http_status") == 404
                                               for p in probe if p["source"] == "morphosource-download")}, indent=1))


if __name__ == "__main__":
    main()
