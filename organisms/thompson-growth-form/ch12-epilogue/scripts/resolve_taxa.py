#!/usr/bin/env python3
"""Resolve every taxon in taxa_terms.TAXA against GBIF, NCBI Taxonomy, Wikidata, WoRMS
(marine) and the Paleobiology Database (extinct) -> taxa/<slug>.json.

Existing taxon files keep their `datasets` list (filled in by build_datasets.py).
"""
import sys
from collections import defaultdict

from common import HERE, SLICE, get_json, read_json, write_json

sys.path.insert(0, str(HERE))
from taxa_terms import TAXA  # noqa: E402

GBIF = "https://api.gbif.org/v1"
NCBI = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
WD = "https://www.wikidata.org/w/api.php"
PBDB = "https://paleobiodb.org/data1.2"
WORMS = "https://www.marinespecies.org/rest"

def gbif_match(name, rank=None):
    params = {"name": name, "strict": "true"}
    if rank and rank not in ("clade", "infraorder", "superorder", "subphylum", "subclass", "superfamily", "subfamily"):
        params["rank"] = rank.upper()
    m = get_json(f"{GBIF}/species/match", params=params)
    if not m or m.get("matchType") in ("NONE", "HIGHERRANK"):
        # fall back to a backbone name search
        s = get_json(f"{GBIF}/species/search", params={"q": name, "datasetKey": "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c", "limit": 20})
        hits = [r for r in (s or {}).get("results", []) if r.get("canonicalName", "").lower() == name.lower()]
        hits.sort(key=lambda r: (r.get("taxonomicStatus") != "ACCEPTED", r.get("kingdom") != "Animalia"))
        if not hits:
            return None
        r = hits[0]
        m = {"usageKey": r["key"], "scientificName": r.get("scientificName"), "canonicalName": r.get("canonicalName"),
             "rank": r.get("rank"), "status": r.get("taxonomicStatus"), "matchType": "SEARCH",
             "acceptedUsageKey": r.get("acceptedKey"), **{k: r.get(k) for k in ("kingdom", "phylum", "class", "order", "family", "genus")}}
    key = m.get("usageKey")
    if m.get("status") == "SYNONYM" and m.get("acceptedUsageKey"):
        key = m["acceptedUsageKey"]
    usage = get_json(f"{GBIF}/species/{key}")
    return {"match": m, "usage": usage}


def ncbi_taxid(name):
    d = get_json(f"{NCBI}/esearch.fcgi", params={"db": "taxonomy", "term": f"{name}[Scientific Name]", "retmode": "json"}, sleep=0.4)
    ids = (d or {}).get("esearchresult", {}).get("idlist", [])
    if len(ids) == 1:
        return int(ids[0])
    if len(ids) > 1:
        # choose the one whose scientific name equals the query
        s = get_json(f"{NCBI}/esummary.fcgi", params={"db": "taxonomy", "id": ",".join(ids[:20]), "retmode": "json"}, sleep=0.4)
        for uid in ids[:20]:
            rec = s["result"].get(uid, {})
            if rec.get("scientificname", "").lower() == name.lower():
                return int(uid)
        return int(ids[0])
    return None


def wikidata_qid(names):
    for name in names:
        s = get_json(WD, params={"action": "wbsearchentities", "search": name, "language": "en", "format": "json", "limit": 50, "type": "item"}, sleep=1.0)
        ids = [h["id"] for h in (s or {}).get("search", [])]
        if not ids:
            continue
        e = get_json(WD, params={"action": "wbgetentities", "ids": "|".join(ids), "props": "claims|labels", "format": "json"}, sleep=1.0)
        for qid in ids:
            ent = e["entities"].get(qid, {})
            claims = ent.get("claims", {})
            p225 = [c["mainsnak"].get("datavalue", {}).get("value") for c in claims.get("P225", [])]
            if any(isinstance(v, str) and v.lower() == name.lower() for v in p225):
                return qid, name
    return None, None


def pbdb_taxon(name):
    d = get_json(f"{PBDB}/taxa/single.json", params={"name": name, "show": "class,attr"})
    recs = (d or {}).get("records", [])
    if not recs:
        return None
    r = recs[0]
    def val(k):
        v = r.get(k)
        return None if (v is None or str(v).startswith("NO_")) else v
    out = {"taxon_no": int(r["oid"].split(":")[1]), "name": r["nam"], "rank": r.get("rnk"), "n_occurrences": r.get("noc"),
           "is_extant": r.get("ext"), "phylum": val("phl"), "class": val("cll"), "order": val("odl"), "family": val("fml")}
    if r.get("acc") and r["acc"] != r["oid"]:
        out["accepted_taxon_no"] = int(r["acc"].split(":")[1])
        out["accepted_name"] = r.get("acn")
    return out


def worms_aphia(name):
    d = get_json(f"{WORMS}/AphiaRecordsByName/{name}", params={"like": "false", "marine_only": "false"})
    if not d:
        return None
    exact = [r for r in d if r.get("scientificname", "").lower() == name.lower()]
    if not exact:
        return None
    exact.sort(key=lambda r: r.get("status") != "accepted")
    r = exact[0]
    return {"aphia_id": r["AphiaID"], "status": r.get("status"), "valid_aphia_id": r.get("valid_AphiaID"), "valid_name": r.get("valid_name"),
            "rank": r.get("rank"), "is_extinct": r.get("isExtinct")}


def main():
    mentions = read_json(SLICE / "mentions.json")
    by_slug = defaultdict(list)
    for m in mentions:
        by_slug[m["taxon_slug"]].append(m)
    problems = []
    for t in TAXA:
        slug = t["slug"]
        ms = by_slug.get(slug, [])
        if not ms:
            continue
        if t.get("gbif_key"):
            g = {"match": {"matchType": "MANUAL"}, "usage": get_json(f"{GBIF}/species/{t['gbif_key']}")}
        else:
            g = gbif_match(t["query"], t.get("rank"))
        usage = (g or {}).get("usage") or {}
        accepted = usage.get("canonicalName") or t["query"]
        if usage.get("kingdom") not in (None, "Animalia"):
            problems.append(f"{slug}: GBIF kingdom {usage.get('kingdom')}")
        if usage.get("canonicalName") and usage["canonicalName"].lower() != t["query"].lower():
            problems.append(f"{slug}: GBIF accepted name '{usage['canonicalName']}' differs from query '{t['query']}'")
        names = [t["query"]] + ([accepted] if accepted != t["query"] else []) + t.get("wd_names", [])
        qid, _ = wikidata_qid(names)
        taxid = ncbi_taxid(t["query"]) or (ncbi_taxid(accepted) if accepted != t["query"] else None)
        # PBDB for extinct taxa, and for extant higher taxa the GBIF backbone lacks (their fossil record is still a dataset)
        pb = pbdb_taxon(t["query"]) if (t.get("extinct") or not usage.get("key")) else None
        wo = worms_aphia(t["query"]) if t.get("marine") else None

        lineage = {k: usage.get(k) for k in ("phylum", "class", "order", "family")}
        if pb:
            for k in lineage:
                lineage[k] = lineage[k] or pb.get(k)
        rank = (usage.get("rank") or t.get("rank") or "").lower()
        if not usage and pb and pb.get("rank"):
            rank = t.get("rank")
        claim_ids = sorted({m["source"]["claim_id"] for m in ms if "claim_id" in m["source"]})
        written = []
        for m in ms:
            w = m["name_as_written"]
            if w.lower() not in [x.lower() for x in written]:
                written.append(w)
        ident = {
            "gbif_usage_key": usage.get("key"),
            "ncbi_taxid": taxid,
            "wikidata_qid": qid,
            "itis_tsn": None,
            "worms_aphia_id": (wo or {}).get("valid_aphia_id") or (wo or {}).get("aphia_id"),
        }
        if pb:
            ident["pbdb_taxon_no"] = pb["taxon_no"]
        rec = {
            "slug": slug,
            "accepted_name": accepted,
            "rank": rank,
            "vernacular": t.get("vernacular", []),
            "names_as_written": written,
            "identifiers": ident,
            "lineage": lineage,
            "gbif": {"scientific_name": usage.get("scientificName"), "status": usage.get("taxonomicStatus"),
                     "match_type": (g or {}).get("match", {}).get("matchType"), "kingdom": usage.get("kingdom")} if usage else None,
            "pbdb": pb,
            "worms": wo,
            "extinct": bool(t.get("extinct")),
            "mentioned_in": claim_ids,
            "n_text_mentions": sum(1 for m in ms if "file" in m["source"]),
            "datasets": [],
            "notes": t.get("notes", ""),
        }
        path = SLICE / "taxa" / f"{slug}.json"
        if path.exists():
            rec["datasets"] = read_json(path).get("datasets", [])
        write_json(path, rec)
        flag = "" if ident["gbif_usage_key"] else "  <-- no GBIF"
        print(f"{slug:36s} gbif={ident['gbif_usage_key']!s:9s} ncbi={taxid!s:8s} wd={qid!s:10s} worms={ident['worms_aphia_id']!s:7s} pbdb={ident.get('pbdb_taxon_no')!s:7s} {accepted}{flag}")
    print("\nPROBLEMS:")
    print("\n".join(problems) or "none")


if __name__ == "__main__":
    main()
