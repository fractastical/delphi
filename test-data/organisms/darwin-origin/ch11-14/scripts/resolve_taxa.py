#!/usr/bin/env python3
"""Resolve every seed taxon against GBIF, NCBI Taxonomy, Wikidata, ITIS, WoRMS and the
Paleobiology Database and write taxa/<slug>.json.

Only identifiers returned by the services are recorded; a failed lookup yields null.
Responses are cached under /tmp/delphi-organisms-cache so re-runs are cheap.

Usage: python3 resolve_taxa.py [slug ...]
"""
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

HERE = Path(__file__).resolve().parent
SLICE = HERE.parent
sys.path.insert(0, str(HERE))
import seed  # noqa: E402

CACHE = Path("/tmp/delphi-organisms-cache")
CACHE.mkdir(exist_ok=True)
UA = {"User-Agent": "delphi-organisms/0.1 (https://github.com/fractastical/delphi)"}
GBIF_BACKBONE = "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"
# taxon, monotypic taxon, fossil taxon, monotypic fossil taxon, ichnotaxon, clade, extinct taxon, parataxon
WD_TAXON_CLASSES = {"Q16521", "Q310890", "Q23038290", "Q47487597", "Q2568288", "Q713623", "Q98961713", "Q55983715"}


def get_json(url, params=None, sleep=0.34):
    key = hashlib.sha256((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    f = CACHE / (key + ".json")
    if f.exists():
        return json.loads(f.read_text())
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=60)
            if r.status_code == 200:
                data = r.json()
                f.write_text(json.dumps(data))
                time.sleep(sleep)
                return data
            if r.status_code == 204:
                f.write_text("null")
                return None
            if r.status_code == 404:
                f.write_text("null")
                return None
        except (requests.RequestException, ValueError) as e:  # noqa: PERF203
            print(f"  retry {attempt} {url}: {e}", file=sys.stderr)
        time.sleep(2 * (attempt + 1))
    return None


LINNEAN = {"species": "SPECIES", "genus": "GENUS", "family": "FAMILY", "order": "ORDER", "class": "CLASS", "phylum": "PHYLUM"}


def rank_compatible(seed_rank, gbif_rank):
    """The GBIF backbone contains stray usages such as a 'family' Marsupialia or a doubtful 'genus'
    Crustacea; a usage is only accepted when its rank is compatible with Darwin's taxon."""
    if seed_rank in LINNEAN:
        return gbif_rank == LINNEAN[seed_rank]
    # intermediate ranks GBIF does not use (subphylum, infraclass, suborder, infraorder, superorder, superfamily)
    return gbif_rank in ("ORDER", "CLASS", "PHYLUM", "UNRANKED", "SUBORDER", "INFRAORDER", "SUPERFAMILY", "SUBCLASS",
                         "INFRACLASS", "SUPERORDER", "SUBPHYLUM")


def gbif_usage_ok(key, rank):
    """Reject usages that are not accepted or (for higher taxa) have no descendants (orphans such as
    Actinopterygii 204 and Reptilia 358 in the current backbone)."""
    u = get_json(f"https://api.gbif.org/v1/species/{key}")
    if not u or u.get("taxonomicStatus") != "ACCEPTED":
        return False, u
    if rank != "species" and not u.get("numDescendants"):
        return False, u
    return True, u


def gbif(name, rank):
    m = get_json("https://api.gbif.org/v1/species/match", {"name": name, "kingdom": "Animalia", "strict": "false"})
    rejected = []
    ok = (m and m.get("matchType") in ("EXACT", "FUZZY") and (m.get("canonicalName") or "").lower() == name.lower()
          and rank_compatible(rank, m.get("rank")))
    if ok:
        key = m.get("acceptedUsageKey") or m.get("usageKey")
        good, u = gbif_usage_ok(key, rank)
        if good:
            out = {"usage_key": key, "scientific_name": u.get("scientificName"), "rank": u.get("rank"),
                   "status": u.get("taxonomicStatus"), "match_type": m.get("matchType"), "confidence": m.get("confidence"),
                   "num_descendants": u.get("numDescendants"),
                   "lineage": {k: u.get(k) for k in ("phylum", "class", "order", "family")}}
            return out
        rejected.append({"key": key, "rank": m.get("rank"), "status": (u or {}).get("taxonomicStatus"), "why": "not accepted or no descendants"})
    elif m and m.get("matchType") in ("EXACT", "FUZZY"):
        rejected.append({"key": m.get("usageKey"), "rank": m.get("rank"), "status": m.get("status"), "why": "name or rank mismatch"})
    # higher taxa that the match service does not rank: look the name up in the backbone directly
    s = get_json("https://api.gbif.org/v1/species", {"name": name, "datasetKey": GBIF_BACKBONE, "limit": 20})
    cands = [u for u in (s or {}).get("results", [])
             if (u.get("canonicalName") or u.get("scientificName", "").split(" ")[0]).lower() == name.lower()
             and u.get("kingdom") == "Animalia" and u.get("taxonomicStatus") == "ACCEPTED" and rank_compatible(rank, u.get("rank"))]
    for u in cands:
        good, full = gbif_usage_ok(u["key"], rank)
        if good:
            return {"usage_key": u["key"], "scientific_name": full.get("scientificName"), "rank": full.get("rank"),
                    "status": full.get("taxonomicStatus"), "match_type": "BACKBONE_LOOKUP",
                    "num_descendants": full.get("numDescendants"),
                    "lineage": {k: full.get(k) for k in ("phylum", "class", "order", "family")}}
        rejected.append({"key": u["key"], "rank": u.get("rank"), "status": u.get("taxonomicStatus"), "why": "not accepted or no descendants"})
    return {"usage_key": None, "rejected_usages": rejected}


def ncbi(name, rank):
    for term in (f'"{name}"[Scientific Name] AND Metazoa[Subtree]', f'"{name}"[All Names] AND Metazoa[Subtree]'):
        d = get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                     {"db": "taxonomy", "term": term, "retmode": "json"}, sleep=0.4)
        ids = (d or {}).get("esearchresult", {}).get("idlist", [])
        if not ids or len(ids) > 10:
            continue
        s = get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                     {"db": "taxonomy", "id": ",".join(ids), "retmode": "json"}, sleep=0.4)
        recs = [(i, (s or {}).get("result", {}).get(i, {})) for i in ids]
        if len(recs) > 1:
            # e.g. genus Mus vs subgenus Mus: keep the record with the exact name and Darwin's rank.
            # ("Reptilia" is only an NCBI synonym of Lepidosauria/Testudines, so it yields nothing.)
            recs = [r for r in recs if (r[1].get("scientificname") or "").lower() == name.lower()]
            if len(recs) > 1:
                recs = [r for r in recs if (r[1].get("rank") or "").lower() == rank]
        if len(recs) == 1:
            i, rec = recs[0]
            return {"taxid": int(i), "scientific_name": rec.get("scientificname"), "rank": rec.get("rank")}
    return {"taxid": None}


def wikidata(name):
    s = get_json("https://www.wikidata.org/w/api.php",
                 {"action": "wbsearchentities", "search": name, "language": "en", "format": "json", "limit": 10, "type": "item"})
    ids = [h["id"] for h in (s or {}).get("search", [])]
    # label search misses items whose English label is a vernacular (e.g. 'amphibian' for Amphibia):
    # also search by the taxon-name statement itself
    q = get_json("https://www.wikidata.org/w/api.php",
                 {"action": "query", "list": "search", "srsearch": f'haswbstatement:"P225={name}"', "format": "json", "srlimit": 10})
    ids += [h["title"] for h in (q or {}).get("query", {}).get("search", []) if h["title"] not in ids]
    if not ids:
        return {"qid": None}
    e = get_json("https://www.wikidata.org/w/api.php",
                 {"action": "wbgetentities", "ids": "|".join(ids), "props": "claims|labels", "format": "json"})
    for qid in ids:
        ent = (e or {}).get("entities", {}).get(qid, {})
        claims = ent.get("claims", {})
        p225 = [c["mainsnak"]["datavalue"]["value"] for c in claims.get("P225", []) if "datavalue" in c["mainsnak"]]
        p31 = [c["mainsnak"]["datavalue"]["value"]["id"] for c in claims.get("P31", []) if "datavalue" in c["mainsnak"]]
        if any(v.lower() == name.lower() for v in p225) and (set(p31) & WD_TAXON_CLASSES):
            label = ent.get("labels", {}).get("en", {}).get("value")
            return {"qid": qid, "label": label, "taxon_name": p225[0]}
    return {"qid": None}


def itis(name):
    d = get_json("https://www.itis.gov/ITISWebService/jsonservice/searchByScientificName", {"srchKey": name}, sleep=0.5)
    for r in (d or {}).get("scientificNames") or []:
        if r and (r.get("combinedName") or "").lower() == name.lower() and r.get("kingdom") == "Animalia":
            return {"tsn": int(r["tsn"])}
    return {"tsn": None}


def worms(name):
    d = get_json(f"https://www.marinespecies.org/rest/AphiaRecordsByName/{quote(name)}", {"like": "false", "marine_only": "false"}, sleep=0.5)
    recs = [r for r in (d or []) if (r.get("scientificname") or "").lower() == name.lower() and r.get("kingdom") == "Animalia"]
    acc = [r for r in recs if r.get("status") == "accepted"] or recs
    if acc:
        r = acc[0]
        return {"aphia_id": r["AphiaID"], "status": r.get("status"), "valid_aphia_id": r.get("valid_AphiaID"),
                "is_marine": r.get("isMarine")}
    return {"aphia_id": None}


def pbdb(name):
    d = get_json("https://paleobiodb.org/data1.2/taxa/single.json", {"name": name}, sleep=0.3)
    recs = (d or {}).get("records", [])
    if recs:
        r = recs[0]
        # PBDB field `ext` is the *extant* flag ("1" = extant); recently extinct species are often "1".
        return {"taxon_id": r.get("oid"), "name": r.get("nam"), "extant_flag": r.get("ext"), "n_occurrences": r.get("noc")}
    return {"taxon_id": None}


def main(only=None):
    mentions = json.load(open(SLICE / "mentions.json", encoding="utf-8"))
    by_slug = {}
    for m in mentions:
        by_slug.setdefault(m["taxon_slug"], []).append(m)
    (SLICE / "taxa").mkdir(exist_ok=True)
    for t in seed.TAXA:
        slug = t["slug"]
        if only and slug not in only:
            continue
        print(slug, flush=True)
        g = gbif(t["name"], t["rank"])
        n = ncbi(t["name"], t["rank"])
        w = wikidata(t["name"])
        i = itis(t["name"])
        wo = worms(t["name"])
        p = pbdb(t["name"])
        ms = by_slug.get(slug, [])
        names = sorted({m["name_as_written"] for m in ms}, key=str.lower)
        claim_ids = sorted({m["source"]["claim_id"] for m in ms if "claim_id" in m["source"]})
        existing = {}
        f = SLICE / "taxa" / f"{slug}.json"
        if f.exists():
            existing = json.loads(f.read_text(encoding="utf-8"))
        rec = {
            "slug": slug,
            "accepted_name": t["name"],
            "rank": t["rank"],
            "vernacular": t.get("vernacular", []),
            "names_as_written": names,
            "identifiers": {
                "gbif_usage_key": g.get("usage_key"),
                "ncbi_taxid": n.get("taxid"),
                "wikidata_qid": w.get("qid"),
                "itis_tsn": i.get("tsn"),
                "worms_aphia_id": wo.get("aphia_id"),
                "pbdb_taxon_id": p.get("taxon_id"),
            },
            "lineage": g.get("lineage") or {},
            "extinct": bool(t.get("extinct")),
            "mentioned_in": claim_ids,
            "n_text_mentions": sum(1 for m in ms if "file" in m["source"]),
            "datasets": existing.get("datasets", []),
            "notes": t["notes"],
            "resolution": {
                "gbif": {k: v for k, v in g.items() if k not in ("lineage", "match")},
                "ncbi": n, "wikidata": w, "worms": wo, "pbdb": p,
                "queried_name": t["name"],
            },
        }
        f.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
