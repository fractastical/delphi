#!/usr/bin/env python3
"""Resolve every taxon in taxa_table.py to GBIF, NCBI Taxonomy, Wikidata (and WoRMS / ITIS
where they apply) and write taxa/<slug>.json.

Every identifier written here was returned by the authority's own API for the name in the
table (or is an explicit override in the table, verified by fetching it). Nothing is guessed.
Raw API responses are cached under /tmp/organisms-cache so the run can be repeated.

Usage: python3 resolve_taxa.py [slug ...]
"""
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
SLICE = HERE.parent
sys.path.insert(0, str(HERE))
from taxa_table import TAXA  # noqa: E402

CACHE = Path("/tmp/organisms-cache")
CACHE.mkdir(exist_ok=True)
S = requests.Session()
S.headers["User-Agent"] = "delphi-organisms/0.1 (https://github.com/fractastical/delphi)"

GBIF_KINGDOM_KEY = {"Animalia": 1, "Chromista": 4, "Protozoa": 7}
WD_TAXON_CLASSES = {"Q16521", "Q310890", "Q23038290", "Q713623", "Q58051350", "Q47487597", "Q2111790", "Q17487588"}
_last_ncbi = 0.0


def get(url, params=None, ttl_ok=True, **kw):
    key = hashlib.sha1((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    f = CACHE / (key + ".json")
    if f.exists():
        return json.loads(f.read_text())
    global _last_ncbi
    if "ncbi.nlm.nih.gov" in url:
        dt = time.time() - _last_ncbi
        if dt < 0.4:
            time.sleep(0.4 - dt)
        _last_ncbi = time.time()
    for attempt in range(4):
        try:
            r = S.get(url, params=params, timeout=60, **kw)
            if r.status_code == 204:
                data = None
                break
            if r.status_code >= 500 or r.status_code == 429:
                raise requests.HTTPError(f"{r.status_code}")
            if r.status_code == 404:
                data = None
                break
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "error" in data:
                raise requests.HTTPError(str(data["error"])[:120])
            break
        except (requests.RequestException, ValueError) as e:
            if attempt == 3:
                print("   !! failed", url, params, e)
                return None
            time.sleep(2 ** attempt)
    f.write_text(json.dumps(data))
    return data


def canonical(sci):
    """Strip authorship from a GBIF scientificName."""
    if not sci:
        return ""
    m = re.match(r"^([A-Z][a-z]+(?: [a-z]+){0,2})", sci)
    return m.group(1) if m else sci


# ----------------------------------------------------------------------------- GBIF
def gbif_lookup(t):
    name, rank, kingdom = t["name"], t["rank"], t["kingdom"]
    if "gbif_key" in t:
        return t["gbif_key"], "override" if t["gbif_key"] else "none (no backbone taxon)"
    if rank == "informal group":
        return None, "informal"
    parent = t.get("gbif_parent_key")
    if not parent:
        r = get("https://api.gbif.org/v1/species/match", {"name": name, "rank": rank, "kingdom": kingdom, "strict": "false"})
        if r and r.get("matchType") == "EXACT" and canonical(r.get("scientificName")) == name and r.get("kingdom") == kingdom:
            return r["usageKey"], "match"
    hk = parent or GBIF_KINGDOM_KEY[kingdom]
    for status in ("ACCEPTED", "DOUBTFUL", "SYNONYM"):
        r = get("https://api.gbif.org/v1/species/search",
                {"q": name, "highertaxonKey": hk, "status": status, "limit": 50, "datasetKey": "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"})
        if not r:
            continue
        hits = [x for x in r.get("results", []) if x.get("canonicalName") == name]
        same_rank = [x for x in hits if x.get("rank") == rank]
        pick = (same_rank or hits)
        if pick:
            return pick[0]["key"], f"search:{status}"
    return None, "none"


def gbif_detail(key):
    d = get(f"https://api.gbif.org/v1/species/{key}")
    return d or {}


# ----------------------------------------------------------------------------- NCBI
NCBI_BAD_LINEAGE = ("Viridiplantae", "Fungi", "Bacteria", "Oomyc", "Archaea", "Viruses")


def ncbi_lineage(taxid):
    f = CACHE / f"ncbi-lineage-{taxid}.txt"
    if f.exists():
        return f.read_text()
    for attempt in range(4):
        time.sleep(0.5)
        r = S.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                  params={"db": "taxonomy", "id": taxid, "retmode": "xml"}, timeout=60)
        m = re.search(r"<Lineage>(.*?)</Lineage>", r.text, re.S)
        if r.status_code == 200 and m:
            f.write_text(m.group(1))
            return m.group(1)
        time.sleep(2 ** attempt)
    raise RuntimeError(f"NCBI efetch failed for taxid {taxid}")


def ncbi_lineage_ok(taxid, kingdom):
    """Reject homonyms: animals must be Metazoa; protists must not be plants, fungi, bacteria or oomycetes."""
    lineage = ncbi_lineage(taxid)
    if kingdom == "Animalia":
        return "Metazoa" in lineage
    return not any(b in lineage for b in NCBI_BAD_LINEAGE) and "Metazoa" not in lineage


def ncbi_lookup(name, kingdom="Animalia"):
    for field in ("Scientific Name", "All Names"):
        r = get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                {"db": "taxonomy", "term": f'"{name}"[{field}]', "retmode": "json"})
        ids = (r or {}).get("esearchresult", {}).get("idlist", [])
        if not ids:
            continue
        s = get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                {"db": "taxonomy", "id": ",".join(ids[:20]), "retmode": "json"})
        res = (s or {}).get("result", {})
        for i in ids[:20]:
            rec = res.get(i, {})
            if rec.get("scientificname", "").lower() == name.lower() and ncbi_lineage_ok(i, kingdom):
                return int(i), rec.get("rank"), rec.get("scientificname")
        # accept a unique hit by other name (e.g. synonym) only if a single id was returned
        if len(ids) == 1 and ncbi_lineage_ok(ids[0], kingdom):
            rec = res.get(ids[0], {})
            return int(ids[0]), rec.get("rank"), rec.get("scientificname")
    return None, None, None


# ----------------------------------------------------------------------------- Wikidata
def wd_entities(ids):
    r = get("https://www.wikidata.org/w/api.php",
            {"action": "wbgetentities", "ids": "|".join(ids), "props": "claims|labels|descriptions", "languages": "en", "format": "json"})
    return (r or {}).get("entities", {})


def wd_claim_values(ent, prop):
    out = []
    for c in ent.get("claims", {}).get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and "id" in v:
            out.append(v["id"])
        elif isinstance(v, str):
            out.append(v)
    return out


def wikidata_lookup(t):
    name = t["name"]
    if "wikidata" in t:
        qid = t["wikidata"]
        if qid is None:
            return None, None
        ent = wd_entities([qid]).get(qid, {})
        return qid, ent.get("labels", {}).get("en", {}).get("value")
    r = get("https://www.wikidata.org/w/api.php",
            {"action": "wbsearchentities", "search": name, "language": "en", "type": "item", "limit": 15, "format": "json"})
    ids = [x["id"] for x in (r or {}).get("search", [])]
    if not ids:
        return None, None
    ents = wd_entities(ids)
    best = None
    for qid in ids:
        e = ents.get(qid, {})
        p31 = set(wd_claim_values(e, "P31"))
        p225 = [v.lower() for v in wd_claim_values(e, "P225")]
        if name.lower() in p225 and p31 & WD_TAXON_CLASSES:
            return qid, e.get("labels", {}).get("en", {}).get("value")
        if name.lower() in p225 and best is None:
            best = (qid, e.get("labels", {}).get("en", {}).get("value"))
    return best if best else (None, None)


# ----------------------------------------------------------------------------- WoRMS
def worms_lookup(name, rank):
    r = get(f"https://www.marinespecies.org/rest/AphiaRecordsByName/{requests.utils.quote(name)}",
            {"like": "false", "marine_only": "false"})
    if not r:
        return None, None
    recs = [x for x in r if x.get("scientificname") == name]
    acc = [x for x in recs if x.get("status") == "accepted"]
    pick = None
    for pool in (acc, recs):
        same = [x for x in pool if (x.get("rank") or "").upper() == rank.upper()]
        if same:
            pick = same[0]
            break
        if pool:
            pick = pool[0]
            break
    if not pick:
        return None, None
    return pick["AphiaID"], pick.get("valid_AphiaID")


# ----------------------------------------------------------------------------- ITIS
def itis_lookup(name):
    r = get("https://www.itis.gov/ITISWebService/jsonservice/getITISTermsFromScientificName", {"srchKey": name})
    terms = (r or {}).get("itisTerms") or []
    for term in terms:
        if term and term.get("scientificName") == name and term.get("nameUsage") in ("valid", "accepted"):
            return int(term["tsn"])
    return None


# ----------------------------------------------------------------------------- main
def main(only=None):
    mentions = json.loads((SLICE / "mentions.json").read_text())
    by_slug = {}
    for m in mentions:
        by_slug.setdefault(m["taxon_slug"], []).append(m)
    (SLICE / "taxa").mkdir(exist_ok=True)
    summary = {"gbif": 0, "ncbi": 0, "wikidata": 0, "worms": 0, "itis": 0}
    for t in TAXA:
        if only and t["slug"] not in only:
            continue
        slug = t["slug"]
        ms = by_slug.get(slug, [])
        print(f"{slug}: {t['name']}")
        out_path = SLICE / "taxa" / f"{slug}.json"
        existing = json.loads(out_path.read_text()) if out_path.exists() else {}

        gkey, how = gbif_lookup(t)
        gdet = gbif_detail(gkey) if gkey else {}
        accepted_key = gdet.get("acceptedKey") if gdet.get("taxonomicStatus") not in (None, "ACCEPTED", "DOUBTFUL") else None
        if accepted_key:
            gdet_acc = gbif_detail(accepted_key)
        else:
            gdet_acc = gdet
        lineage = {k: gdet_acc.get(k) for k in ("phylum", "class", "order", "family") if gdet_acc.get(k)}
        if gdet_acc.get("kingdom"):
            lineage = {"kingdom": gdet_acc["kingdom"], **lineage}
        if t.get("lineage"):  # hand-set when the backbone usage is unplaced (e.g. a doubtful genus with no classification)
            lineage = dict(t["lineage"])

        ncbi_name = t.get("ncbi_name", t["name"]) if "ncbi_name" in t else t["name"]
        if ncbi_name is None or t["rank"] == "informal group":
            ncbi = (None, None, None)
        else:
            ncbi = ncbi_lookup(ncbi_name, t["kingdom"])

        qid, qlabel = wikidata_lookup(t)
        aphia, aphia_valid = worms_lookup(t["name"], t["rank"]) if t.get("marine") else (None, None)
        tsn = itis_lookup(t["name"]) if t["kingdom"] == "Animalia" and t["rank"] != "informal group" else None

        for k, v in (("gbif", gkey), ("ncbi", ncbi[0]), ("wikidata", qid), ("worms", aphia), ("itis", tsn)):
            summary[k] += bool(v)

        notes = [t.get("notes", "")] if t.get("notes") else []
        if gkey and gdet.get("taxonomicStatus") == "SYNONYM" and accepted_key:
            notes.append(f"GBIF usage {gkey} ({gdet.get('scientificName')}) is a synonym of {accepted_key} ({gdet_acc.get('scientificName')}); the accepted key is recorded.")
        if gkey and gdet.get("rank") and gdet.get("rank") != t["rank"] and t["rank"] != "informal group":
            notes.append(f"GBIF backbone ranks this taxon as {gdet.get('rank')}.")
        if gkey and gdet.get("taxonomicStatus") == "DOUBTFUL":
            notes.append("GBIF backbone marks this name DOUBTFUL.")
        if ncbi[0] and ncbi[2] and ncbi[2].lower() != (ncbi_name or "").lower():
            notes.append(f"NCBI Taxonomy returns this name under '{ncbi[2]}'.")
        if aphia and aphia_valid and aphia_valid != aphia:
            notes.append(f"WoRMS AphiaID {aphia} is unaccepted; valid AphiaID {aphia_valid}.")
        if t.get("protist"):
            notes.append("Treated as an animal by Thompson; not Metazoa in modern taxonomy (see lineage).")

        rec = {
            "slug": slug,
            "accepted_name": gdet_acc.get("canonicalName") or t["name"],
            "rank": (gdet_acc.get("rank") or t["rank"]).lower() if t["rank"] != "informal group" else "informal group",
            "vernacular": t.get("vernacular", []),
            "names_as_written": sorted({m["name_as_written"] for m in ms}),
            "identifiers": {
                "gbif_usage_key": accepted_key or gkey,
                "gbif_matched_key": gkey if accepted_key else None,
                "ncbi_taxid": ncbi[0],
                "wikidata_qid": qid,
                "itis_tsn": tsn,
                "worms_aphia_id": aphia,
            },
            "lineage": lineage,
            "mentioned_in": sorted({m["source"]["claim_id"] for m in ms if "claim_id" in m["source"]}),
            "text_mentions": sum(1 for m in ms if "file" in m["source"]),
            "datasets": existing.get("datasets", []),
            "notes": " ".join(n.strip() for n in notes if n.strip()),
            "resolved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "resolution": {"gbif": how, "ncbi_rank": ncbi[1], "wikidata_label": qlabel},
        }
        if not rec["identifiers"]["gbif_matched_key"]:
            del rec["identifiers"]["gbif_matched_key"]
        out_path.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"   gbif={gkey} ({how}) acc={accepted_key} ncbi={ncbi[0]} wd={qid} ({qlabel}) worms={aphia} itis={tsn}")
    print(summary)


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
