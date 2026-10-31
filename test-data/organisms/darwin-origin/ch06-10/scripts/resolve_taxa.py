#!/usr/bin/env python3
"""Resolve every seed taxon against GBIF, NCBI Taxonomy, Wikidata, ITIS, WoRMS and PBDB and
write taxa/<slug>.json. Raw API responses are cached under /tmp so the run can be repeated.

Run from the repository root:  python3 test-data/organisms/darwin-origin/ch06-10/scripts/resolve_taxa.py
"""
import json
import sys
import time
import urllib.parse
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from taxa_seed import TAXA  # noqa: E402

SLICE = HERE.parent
TAXA_DIR = SLICE / "taxa"
CACHE = Path("/tmp/organisms-cache/resolve")
CACHE.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "delphi-organisms/0.1 (https://github.com/fractastical/delphi)"}
BACKBONE = "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"
ANIMALIA_KEY = 1

GBIF_RANKS = {"species": "SPECIES", "genus": "GENUS", "family": "FAMILY", "order": "ORDER",
              "class": "CLASS", "phylum": "PHYLUM"}

# GBIF backbone only carries kingdom/phylum/class/order/family/genus/species. For taxa at other
# ranks (or that GBIF splits), list the accepted GBIF taxa whose union is Darwin's taxon.
GBIF_HINTS = {
    "neogale-vison": {"name": "Neovison vison"},
    "canis-familiaris": {"name": "Canis familiaris"},
    "hydra": {"parent": "Cnidaria"},
    "lingula": {"parent": "Brachiopoda"},
    "trigonia": {"parent": "Mollusca"},
    "nautilus": {"parent": "Mollusca"},
    "balanus": {"parent": "Arthropoda"},
    "chthamalus": {"parent": "Arthropoda"},
    "chiton": {"parent": "Mollusca"},
    "cephalotes": {"parent": "Hymenoptera"},
    "troglodytes": {"parent": "Aves"},
    "mustela": {"parent": "Mammalia"},
    "pieris": {"parent": "Lepidoptera"},
    "turdus": {"parent": "Aves"},
    "sitta": {"parent": "Aves"},
    "crotalus": {"parent": "Squamata"},
    "felis": {"parent": "Mammalia"},
    "canis": {"parent": "Mammalia"},
    "lepus": {"parent": "Mammalia"},
    "camelus": {"parent": "Mammalia"},
    "bombus": {"parent": "Hymenoptera"},
    "melipona": {"parent": "Hymenoptera"},
    "xenarthra": {"components": ["Cingulata|Mammalia", "Pilosa|Mammalia"]},
    "folivora": {"components": ["Bradypodidae|Mammalia", "Megalonychidae|Mammalia"]},
    "vermilingua": {"components": ["Myrmecophagidae|Mammalia", "Cyclopedidae|Mammalia"]},
    "marsupialia": {"components": ["Didelphimorphia|Mammalia", "Paucituberculata|Mammalia", "Microbiotheria|Mammalia", "Dasyuromorphia|Mammalia",
                                   "Peramelemorphia|Mammalia", "Notoryctemorphia|Mammalia", "Diprotodontia|Mammalia"]},
    "reptilia": {"components": ["Squamata|Chordata", "Testudines|Chordata", "Crocodylia|Chordata", "Sphenodontia|Chordata"]},
    "vertebrata": {"components": []}, "pisces": {"components": []}, "ganoidei": {"components": []},
    "pachydermata": {"components": []}, "crustacea": {"components": []}, "cirripedia": {"components": []},
    "teleostei": {"components": []}, "ruminantia": {"components": []}, "ammonoidea": {"components": []},
    "coccoidea": {"components": []}, "pterosauria": {"components": []}, "dinornithiformes": {"components": []},
    "cetacea": {"name": "Cetacea", "rank": "ORDER"},
    "crocodylia": {"rank": None},
    "phocidae": {"rank": "FAMILY"},
}

# Lineage for taxa that have no GBIF backbone node (GBIF-derived lineage is used otherwise).
LINEAGE_FALLBACK = {
    "crustacea": {"phylum": "Arthropoda"},
    "vertebrata": {"phylum": "Chordata"},
    "pisces": {"phylum": "Chordata"},
    "ammonoidea": {"phylum": "Mollusca", "class": "Cephalopoda"},
    "marsupialia": {"phylum": "Chordata", "class": "Mammalia"},
    "xenarthra": {"phylum": "Chordata", "class": "Mammalia"},
    "reptilia": {"phylum": "Chordata"},
    "pterosauria": {"phylum": "Chordata", "class": "Reptilia"},
    "cirripedia": {"phylum": "Arthropoda", "class": "Thecostraca"},
    "coccoidea": {"phylum": "Arthropoda", "class": "Insecta", "order": "Hemiptera"},
    "teleostei": {"phylum": "Chordata", "class": "Actinopterygii"},
    "ganoidei": {"phylum": "Chordata", "class": "Actinopterygii"},
    "ruminantia": {"phylum": "Chordata", "class": "Mammalia", "order": "Artiodactyla"},
    "pachydermata": {"phylum": "Chordata", "class": "Mammalia"},
    "folivora": {"phylum": "Chordata", "class": "Mammalia", "order": "Pilosa"},
    "vermilingua": {"phylum": "Chordata", "class": "Mammalia", "order": "Pilosa"},
    "dinornithiformes": {"phylum": "Chordata", "class": "Aves"},
}

WD_RANK = {"species": "Q7432", "genus": "Q34740", "family": "Q35409", "order": "Q36602",
           "class": "Q37517", "phylum": "Q38348"}
WD_TAXON_CLASSES = {"Q16521", "Q310890", "Q23038290", "Q713623", "Q2449730", "Q47487597", "Q2568288", "Q42621", "Q98961713", "Q217743"}
WD_NAME_ALIASES = {"Crocodylia": ["Crocodilia"]}
WD_SKIP = {"Ganoidei"}
WD_ANIMAL_ANCESTORS = {"Q729", "Q5173", "Q4863", "Q10915", "Q7377", "Q5113", "Q1360", "Q25326", "Q1390", "Q25364", "Q10811", "Q25522", "Q127282", "Q25241", "Q7380", "Q10850", "Q25306", "Q4867740", "Q128257", "Q25375", "Q28319", "Q7386", "Q25312", "Q21659", "Q1137342", "Q1273371", "Q8514"}


def get(url, kind):
    key = CACHE / (kind + "-" + urllib.parse.quote(url, safe="")[-180:] + ".json")
    if key.exists():
        return json.loads(key.read_text())
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=60, headers=UA)
            if r.status_code == 200:
                try:
                    data = r.json()
                except ValueError:
                    data = {"_text": r.text}
                key.write_text(json.dumps(data))
                return data
            if r.status_code == 404:
                key.write_text("null")
                return None
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    return None


# ---------------- GBIF ----------------
def gbif_backbone_search(name, rank, parent=None):
    """Search the backbone for an accepted taxon with this canonical name (and rank)."""
    q = {"datasetKey": BACKBONE, "q": name, "limit": 50, "higherTaxonKey": ANIMALIA_KEY}
    if rank:
        q["rank"] = rank
    url = "https://api.gbif.org/v1/species/search?" + urllib.parse.urlencode(q)
    d = get(url, "gbifsearch") or {}
    hits = [r for r in d.get("results", []) if r.get("canonicalName") == name and r.get("kingdom") == "Animalia"]
    acc = [r for r in hits if r.get("taxonomicStatus") == "ACCEPTED"]
    if parent:
        acc = [r for r in acc if parent in (r.get("phylum"), r.get("class"), r.get("order"), r.get("family"))]
    if len(acc) == 1:
        return acc[0], None
    if len(acc) > 1:
        return None, f"ambiguous GBIF backbone hits for {name}: " + ", ".join(f"{r['key']} ({r.get('phylum')}/{r.get('class')}/{r.get('order')})" for r in acc)
    syn = [r for r in hits if r.get("acceptedKey")]
    if parent:
        syn = [r for r in syn if parent in (r.get("phylum"), r.get("class"), r.get("order"), r.get("family"))]
    if len(syn) >= 1:
        u = get(f"https://api.gbif.org/v1/species/{syn[0]['acceptedKey']}", "gbifusage")
        return u, f"'{name}' is a GBIF synonym of {u.get('scientificName')} (key {u.get('key')})"
    return None, f"no accepted GBIF backbone taxon named {name}" + (f" at rank {rank}" if rank else "")


def gbif_component_keys(names):
    out = []
    for spec in names:
        n, _, parent = spec.partition("|")
        hit, note = gbif_backbone_search(n, None, parent or None)
        if hit is None:
            raise SystemExit(f"GBIF component {n} not found: {note}")
        out.append({"name": n, "gbif_usage_key": hit["key"], "rank": hit.get("rank", "").lower()})
    return out


def lineage(u):
    return {k: u.get(k) for k in ("phylum", "class", "order", "family", "genus") if u.get(k)}


# ---------------- NCBI ----------------
def ncbi(name):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    d = get(base + "esearch.fcgi?db=taxonomy&retmode=json&term=" + urllib.parse.quote(name), "ncbi")
    time.sleep(0.35)
    ids = (d or {}).get("esearchresult", {}).get("idlist", [])
    if not ids:
        return None, None
    summ = get(base + "esummary.fcgi?db=taxonomy&retmode=json&id=" + ",".join(ids[:20]), "ncbisum")
    time.sleep(0.35)
    recs = [summ["result"][i] for i in ids[:20] if i in summ.get("result", {})]
    def bad(r):
        d = (r.get("division") or "").lower()
        return any(w in d for w in ("alga", "plant", "bacteria", "virus", "fung", "environmental", "synthetic", "phage", "unassigned"))
    exact = [r for r in recs if r.get("scientificname") == name and not bad(r)]
    if exact:
        return int(exact[0]["taxid"]), exact[0]["scientificname"]
    # name is an NCBI synonym (e.g. Canis familiaris -> Canis lupus familiaris); keep when unique
    good = [r for r in recs if not bad(r)]
    if len(good) == 1:
        return int(good[0]["taxid"]), good[0]["scientificname"]
    return None, None


# ---------------- Wikidata ----------------
def wd_entities(ids):
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), 40):
        chunk = ids[i:i + 40]
        d = get("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=claims|descriptions&ids=" + "|".join(chunk), "wdent")
        out.update((d or {}).get("entities", {}))
    return out


def wd_claim_ids(ent, prop):
    return [c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in ent.get("claims", {}).get(prop, []) if c["mainsnak"].get("datavalue")]


def wd_is_animal(qid, limit=150):
    """Breadth-first walk up P171 (parent taxon) until a known animal clade is reached."""
    seen, queue = set(), [qid]
    while queue and len(seen) < limit:
        cur = queue.pop(0)
        if not cur or cur in seen:
            continue
        seen.add(cur)
        if cur in WD_ANIMAL_ANCESTORS:
            return True
        ent = wd_entities([cur]).get(cur, {})
        queue.extend(p for p in wd_claim_ids(ent, "P171") if p not in seen)
    return False


def wikidata(name, rank, qid_hint=None):
    if qid_hint:
        return qid_hint
    if name in WD_SKIP:
        return None
    names = [name] + WD_NAME_ALIASES.get(name, [])
    d = get("https://www.wikidata.org/w/api.php?action=wbsearchentities&language=en&format=json&limit=20&search=" + urllib.parse.quote(name), "wd")
    cands = [c["id"] for c in (d or {}).get("search", [])]
    if not cands:
        return None
    ents = wd_entities(cands)
    ok = []
    for q in cands:
        ent = ents.get(q, {})
        p31 = set(wd_claim_ids(ent, "P31"))
        p225 = [c["mainsnak"].get("datavalue", {}).get("value") for c in ent.get("claims", {}).get("P225", []) if c["mainsnak"].get("datavalue")]
        if not (p31 & WD_TAXON_CLASSES) or not (set(names) & set(p225)):
            continue
        if rank in WD_RANK and wd_claim_ids(ent, "P105") and WD_RANK[rank] not in wd_claim_ids(ent, "P105"):
            continue
        ok.append(q)
    for q in ok:
        if wd_is_animal(q):
            return q
    return None


# ---------------- ITIS / WoRMS / PBDB ----------------
def itis(name):
    d = get("https://www.itis.gov/ITISWebService/jsonservice/searchByScientificName?srchKey=" + urllib.parse.quote(name), "itis")
    for rec in (d or {}).get("scientificNames") or []:
        if rec and rec.get("combinedName") == name and rec.get("kingdom") == "Animalia":
            return int(rec["tsn"])
    return None


def worms(name):
    d = get("https://www.marinespecies.org/rest/AphiaRecordsByName/" + urllib.parse.quote(name) + "?like=false&marine_only=false", "worms")
    for rec in d or []:
        if rec.get("scientificname") == name and rec.get("kingdom") == "Animalia":
            return rec.get("valid_AphiaID") or rec.get("AphiaID")
    return None


def pbdb(name):
    d = get("https://paleobiodb.org/data1.2/taxa/single.json?name=" + urllib.parse.quote(name), "pbdb")
    recs = (d or {}).get("records") or []
    if recs and recs[0].get("nam") == name:
        return recs[0]["oid"]
    return None


def main():
    TAXA_DIR.mkdir(exist_ok=True)
    mentions = json.loads((SLICE / "mentions.json").read_text())
    by_slug = {}
    for m in mentions:
        by_slug.setdefault(m["taxon_slug"], []).append(m)
    rows = []
    for t in TAXA:
        slug, name = t["slug"], t["query"]
        hint = GBIF_HINTS.get(slug, {})
        ms = by_slug.get(slug, [])
        rec = {
            "slug": slug,
            "accepted_name": name,
            "rank": t["rank"],
            "vernacular": t["vernacular"],
            "names_as_written": sorted({m["name_as_written"] for m in ms}, key=str.lower),
            "identifiers": {"gbif_usage_key": None, "ncbi_taxid": None, "wikidata_qid": None, "itis_tsn": None, "worms_aphia_id": None},
            "lineage": {},
            "mentioned_in": sorted({m["source"]["claim_id"] for m in ms if "claim_id" in m["source"]}),
            "text_mentions": sum(1 for m in ms if "file" in m["source"]),
            "datasets": [],
            "notes": t["notes"],
        }
        notes = []
        # GBIF
        if "components" in hint:
            if hint["components"]:
                rec["gbif_components"] = gbif_component_keys(hint["components"])
                notes.append("GBIF backbone has no node for this taxon; gbif_components lists the accepted GBIF taxa whose union it is.")
            else:
                notes.append("GBIF backbone has no node for this taxon (it only carries kingdom to species ranks, or treats the name as a synonym/doubtful).")
        else:
            gname = hint.get("name", name)
            grank = hint.get("rank", GBIF_RANKS.get(t["rank"]))
            u, note = gbif_backbone_search(gname, grank, hint.get("parent"))
            if u is None:
                notes.append(note)
            else:
                rec["identifiers"]["gbif_usage_key"] = u["key"]
                rec["gbif_scientific_name"] = u.get("scientificName")
                rec["lineage"] = lineage(u)
                if note:
                    notes.append(note)
        # NCBI
        if not t["rank"].startswith("grade"):
            tid, nname = ncbi(name)
            rec["identifiers"]["ncbi_taxid"] = tid
            if tid and nname != name:
                rec["ncbi_scientific_name"] = nname
            rec["identifiers"]["itis_tsn"] = itis(name)
        # Wikidata
        rec["identifiers"]["wikidata_qid"] = wikidata(name, t["rank"], t.get("wikidata"))
        if t["marine"]:
            rec["identifiers"]["worms_aphia_id"] = worms(name)
        if t["fossil"]:
            rec["identifiers"]["pbdb_taxon_id"] = pbdb(name)
        if not rec["lineage"] and slug in LINEAGE_FALLBACK:
            rec["lineage"] = LINEAGE_FALLBACK[slug]
        if notes:
            rec["resolution_notes"] = notes
        (TAXA_DIR / f"{slug}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ids = rec["identifiers"]
        row = (slug, ids["gbif_usage_key"], ids["ncbi_taxid"], ids["wikidata_qid"], ids["itis_tsn"], ids.get("worms_aphia_id"), ids.get("pbdb_taxon_id"), "; ".join(notes)[:100])
        rows.append(row)
        print(*row, sep="\t", flush=True)
    n = len(rows)
    print(f"\n{n} taxa: GBIF {sum(1 for r in rows if r[1])}, NCBI {sum(1 for r in rows if r[2])}, Wikidata {sum(1 for r in rows if r[3])}, ITIS {sum(1 for r in rows if r[4])}, WoRMS {sum(1 for r in rows if r[5])}, PBDB {sum(1 for r in rows if r[6])}")


if __name__ == "__main__":
    main()
