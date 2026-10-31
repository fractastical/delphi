#!/usr/bin/env python3
"""Resolve every taxon in taxa_seed.TAXA to GBIF, NCBI Taxonomy, Wikidata (and ITIS /
WoRMS when Wikidata or WoRMS know the name) and write taxa/<slug>.json.

Nothing is invented: every identifier written is read back from the authority's API
(GBIF species/match + species/{key}; NCBI esearch + esummary; Wikidata
wbsearchentities + wbgetentities with P31/P225 checks; WoRMS AphiaRecordsByName;
ITIS getFullRecordFromTSN).  Where an authority has no node for a name the field is
null and the reason is in `resolution_notes`.

Usage: python3 resolve_taxa.py [slug ...]
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
SLICE = HERE.parent
sys.path.insert(0, str(HERE))
from taxa_seed import TAXA  # noqa: E402

UA = {"User-Agent": "delphi-organisms/0.1 (https://github.com/fractastical/delphi)"}
S = requests.Session()
S.headers.update(UA)

# GBIF backbone keys fixed by hand where species/match is ambiguous or the backbone
# has no node (verified by scripts/probe runs; see REPORT.md "Ambiguities").
GBIF_OVERRIDE = {
    "apodemus": 2437754, "columba": 2495404, "coccus": 2049629, "diptera": 811,
    "serpentes": 11205692, "onitis": 1093671, "equus": 8652950, "canis": 5219142,
    "camelus": 2441236, "lepus": 2436691, "bombus": 1340278, "pyrgoma": 4335560,
    "edentata": 11034550, "sessilia": 1426, "bos-taurus-indicus": 4262587,
    "mustela-putorius-furo": 5218913, "canis-familiaris": 6164210,
    "proteolepas-bivincta": 2203054, "amblyopsis-spelaea": 5212776,
    "marsupialia": 9712517, "brachyura": 11132538,
    # no node in the GBIF backbone
    "cirripedia": None, "actinopterygii": None, "reptilia": None, "ruminantia": None,
    "tetraoninae": None, "phthiraptera": None,
}
NCBI_NO_NODE_NOTE = {
    "sessilia": "NCBI Taxonomy has no Sessilia; the rock barnacles are its suborder Balanomorpha (taxid 2899670).",
    "reptilia": "NCBI Taxonomy has no Reptilia node (it uses Sauropsida and its subgroups).",
    "edentata": "NCBI Taxonomy has no Edentata (obsolete grouping).",
    "proteolepas-bivincta": "No NCBI Taxonomy entry; the name is a nomen dubium.",
}
# lineage for taxa with no GBIF node (standard placement)
LINEAGE_FALLBACK = {
    "cirripedia": {"phylum": "Arthropoda", "class": "Thecostraca"},
    "actinopterygii": {"phylum": "Chordata", "class": "Actinopterygii"},
    "reptilia": {"phylum": "Chordata", "class": "Reptilia"},
    "ruminantia": {"phylum": "Chordata", "class": "Mammalia", "order": "Artiodactyla"},
    "tetraoninae": {"phylum": "Chordata", "class": "Aves", "order": "Galliformes", "family": "Phasianidae"},
    "phthiraptera": {"phylum": "Arthropoda", "class": "Insecta", "order": "Phthiraptera"},
}
GBIF_NO_NODE_NOTE = {
    "cirripedia": "GBIF backbone has no Cirripedia node (barnacles sit under class Maxillopoda, orders Sessilia/Pedunculata/Scalpelliformes).",
    "actinopterygii": "GBIF backbone has no Actinopterygii class node.",
    "reptilia": "GBIF backbone has no Reptilia node (Squamata, Testudines, Crocodylia are placed directly under Chordata).",
    "ruminantia": "GBIF backbone has no Ruminantia node.",
    "tetraoninae": "GBIF backbone has no Tetraoninae; Tetraonidae (key 4847862) is only a synonym usage of Phasianidae.",
    "phthiraptera": "GBIF backbone places lice inside Psocodea and has no Phthiraptera node.",
}
# NCBI names that differ from the accepted name used here
NCBI_QUERY = {
    "bos-taurus-indicus": "Bos indicus",
    "proteolepas-bivincta": "Proteolepas bivincta",
}
# alternative spellings accepted for Wikidata P225 / ITIS names
ALT_NAMES = {
    "canis-familiaris": ["Canis familiaris"],
    "mustela-putorius-furo": ["Mustela furo"],
    "bos-taurus-indicus": ["Bos indicus"],
    "equus-quagga-quagga": ["Equus quagga quagga"],
}
TAXON_CLASSES = {"Q16521", "Q310890", "Q23038290", "Q713623", "Q47487597", "Q2752661", "Q98961713"}
MARINE = {"cirripedia", "sessilia", "ibla", "pyrgoma", "proteolepas-bivincta", "brachyura", "mollusca",
          "gastropoda", "brachiopoda", "cetacea", "fulmarus-glacialis", "actinopterygii", "salmo-salar",
          "vultur-gryphus", "tachyeres"}

CACHE = Path("/tmp/org/cache")
CACHE.mkdir(parents=True, exist_ok=True)


def get(url, params=None, retries=3):
    key = CACHE / (str(abs(hash((url, json.dumps(params, sort_keys=True))))) + ".json")
    if key.exists():
        return json.loads(key.read_text())
    for i in range(retries + 2):
        try:
            r = S.get(url, params=params, timeout=60)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", "0") or 0) or 20 * (i + 1)
                print(f"   429 from {url.split('/')[2]}, sleeping {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            if r.status_code == 204:
                data = None
            else:
                r.raise_for_status()
                data = r.json()
            key.write_text(json.dumps(data))
            time.sleep(1.0 if "wikidata" in url else 0.34)
            return data
        except requests.RequestException:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"gave up on {url}")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- GBIF
def gbif(slug, seed):
    notes = []
    if slug in GBIF_OVERRIDE:
        key = GBIF_OVERRIDE[slug]
        if key is None:
            notes.append(GBIF_NO_NODE_NOTE[slug])
            return None, None, notes
    else:
        m = get("https://api.gbif.org/v1/species/match", {"name": seed["name"], "kingdom": "Animalia", "strict": "true"})
        if not m or (m.get("canonicalName") or "").lower() != seed["name"].lower():
            raise RuntimeError(f"GBIF: no exact match for {slug} {seed['name']}: {m}")
        key = m["usageKey"]
    rec = get(f"https://api.gbif.org/v1/species/{key}")
    canon = rec.get("canonicalName") or rec.get("scientificName")
    if canon.lower() != seed["name"].lower():
        raise RuntimeError(f"GBIF {slug}: key {key} is {canon!r}, expected {seed['name']!r}")
    if rec.get("taxonomicStatus") != "ACCEPTED":
        notes.append(f"GBIF usage {key} has taxonomicStatus {rec.get('taxonomicStatus')}"
                     + (f" (accepted: {rec.get('accepted')}, key {rec.get('acceptedKey')})" if rec.get("acceptedKey") else "") + ".")
    lineage = {k: rec.get(k) for k in ("phylum", "class", "order", "family") if rec.get(k)}
    return key, {"gbif_rank": rec.get("rank"), "gbif_status": rec.get("taxonomicStatus"), "lineage": lineage,
                 "scientific_name": rec.get("scientificName")}, notes


# ---------------------------------------------------------------- NCBI
def ncbi(slug, seed):
    name = NCBI_QUERY.get(slug, seed["name"])
    r = get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {"db": "taxonomy", "term": f"{name}[Scientific Name] OR {name}[Synonym] OR {name}[All Names]", "retmode": "json"})
    ids = r["esearchresult"]["idlist"]
    if not ids:
        return None, None, [NCBI_NO_NODE_NOTE.get(slug, f"NCBI Taxonomy has no entry named {name!r}.")]
    s = get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi", {"db": "taxonomy", "id": ",".join(ids[:10]), "retmode": "json"})
    res = s["result"]
    cands = [res[i] for i in res["uids"]]
    exact = [c for c in cands if c.get("scientificname", "").lower() == name.lower()]
    same_rank = [c for c in exact if c.get("rank") == seed["rank"]]
    pick = (same_rank or exact or [None])[0]
    if pick is None:
        # accept a synonym hit if a single candidate
        if len(cands) == 1:
            pick = cands[0]
        else:
            return None, None, [NCBI_NO_NODE_NOTE.get(slug, f"NCBI: ambiguous candidates for {name!r}: " + "; ".join(f"{c['uid']} {c.get('scientificname')}" for c in cands))]
    notes = []
    if pick.get("scientificname", "").lower() != name.lower():
        notes.append(f"NCBI taxid {pick['uid']} is named {pick.get('scientificname')!r} (matched {name!r} as a synonym).")
    if name != seed["name"]:
        notes.append(f"NCBI queried as {name!r}.")
    return int(pick["uid"]), {"ncbi_scientific_name": pick.get("scientificname"), "ncbi_rank": pick.get("rank")}, notes


# ---------------------------------------------------------------- Wikidata
def wd_claim_values(ent, prop):
    out = []
    for c in ent.get("claims", {}).get(prop, []):
        dv = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(dv, dict) and "id" in dv:
            out.append(dv["id"])
        elif isinstance(dv, str):
            out.append(dv)
    return out


def wikidata(slug, seed):
    last = None
    for name in [seed["name"]] + ALT_NAMES.get(slug, []):
        res = wikidata_one(slug, seed, name)
        if res[0]:
            return res
        last = res
    return last


def wikidata_one(slug, seed, name):
    r = get("https://www.wikidata.org/w/api.php",
            {"action": "wbsearchentities", "search": name, "language": "en", "format": "json", "limit": 20, "type": "item"})
    ids = [x["id"] for x in r.get("search", [])]
    if not ids:
        return None, None, [f"Wikidata search found nothing for {name!r}."]
    e = get("https://www.wikidata.org/w/api.php", {"action": "wbgetentities", "ids": "|".join(ids), "props": "claims|labels", "format": "json"})
    good = []
    for qid in ids:
        ent = e["entities"].get(qid, {})
        p31 = set(wd_claim_values(ent, "P31"))
        p225 = [v.lower() for v in wd_claim_values(ent, "P225")]
        if p31 & TAXON_CLASSES and name.lower() in p225:
            good.append((qid, ent))
    if not good:
        return None, None, [f"Wikidata: no item with P31 taxon and P225 == {name!r} among {ids[:8]}."]
    qid, ent = good[0]
    ext = {
        "wd_gbif": wd_claim_values(ent, "P846"),
        "wd_ncbi": wd_claim_values(ent, "P685"),
        "wd_itis": wd_claim_values(ent, "P815"),
        "wd_worms": wd_claim_values(ent, "P850"),
        "wd_label": ent.get("labels", {}).get("en", {}).get("value"),
    }
    notes = []
    if len(good) > 1:
        notes.append("Wikidata: several taxon items carry this name: " + ", ".join(q for q, _ in good) + f"; {qid} used.")
    if name != seed["name"]:
        notes.append(f"Wikidata queried as {name!r}.")
    return qid, ext, notes


# ---------------------------------------------------------------- WoRMS / ITIS
def worms(seed):
    try:
        r = get(f"https://www.marinespecies.org/rest/AphiaRecordsByName/{requests.utils.quote(seed['name'])}",
                {"like": "false", "marineonly": "false"})
    except requests.HTTPError:
        return None, None
    if not r:
        return None, None
    exact = [x for x in r if x.get("scientificname", "").lower() == seed["name"].lower()]
    if not exact:
        return None, None
    acc = [x for x in exact if x.get("status") == "accepted"] or exact
    x = acc[0]
    return x["AphiaID"], {"worms_status": x.get("status"), "worms_rank": x.get("rank"), "worms_valid_name": x.get("valid_name"), "worms_valid_aphia_id": x.get("valid_AphiaID")}


def itis(tsn, slug, seed):
    r = get("https://www.itis.gov/ITISWebService/jsonservice/getFullRecordFromTSN", {"tsn": tsn})
    if not r or not r.get("scientificName"):
        return None
    name = r["scientificName"].get("combinedName", "")
    ok = [seed["name"].lower()] + [a.lower() for a in ALT_NAMES.get(slug, [])]
    if name.lower() not in ok:
        return None
    return {"itis_name": name, "itis_usage": (r.get("coreMetadata") or {}).get("taxonUsageRating")}


# ---------------------------------------------------------------- main
def main(slugs):
    mentions = json.loads((SLICE / "mentions.json").read_text(encoding="utf-8"))
    (SLICE / "taxa").mkdir(exist_ok=True)
    problems = []
    for slug in slugs:
        seed = TAXA[slug]
        notes = []
        gkey, ginfo, n = gbif(slug, seed); notes += n
        nkey, ninfo, n = ncbi(slug, seed); notes += n
        qid, winfo, n = wikidata(slug, seed); notes += n
        aphia = None
        if slug in MARINE or (winfo and winfo["wd_worms"]):
            aphia, wminfo = worms(seed)
            if aphia and wminfo["worms_status"] != "accepted":
                notes.append(f"WoRMS AphiaID {aphia} status {wminfo['worms_status']} (valid: {wminfo['worms_valid_name']}, {wminfo['worms_valid_aphia_id']}).")
        tsn = None
        if winfo and winfo["wd_itis"]:
            cand = winfo["wd_itis"][0]
            it = itis(cand, slug, seed)
            if it:
                tsn = int(cand)
                if it["itis_name"].lower() != seed["name"].lower():
                    notes.append(f"ITIS TSN {tsn} is named {it['itis_name']!r}.")
            else:
                notes.append(f"ITIS TSN {cand} from Wikidata did not verify against the ITIS API for this name; dropped.")
        # cross-checks between authorities
        if winfo:
            if gkey and winfo["wd_gbif"] and str(gkey) not in winfo["wd_gbif"]:
                notes.append(f"Wikidata P846 GBIF id {winfo['wd_gbif']} differs from the backbone key used ({gkey}).")
            if nkey and winfo["wd_ncbi"] and str(nkey) not in winfo["wd_ncbi"]:
                notes.append(f"Wikidata P685 NCBI id {winfo['wd_ncbi']} differs from NCBI taxid used ({nkey}).")
            if aphia and winfo["wd_worms"] and str(aphia) not in winfo["wd_worms"]:
                notes.append(f"Wikidata P850 WoRMS id {winfo['wd_worms']} differs from AphiaID used ({aphia}).")
        ms = [m for m in mentions if m["taxon_slug"] == slug]
        claim_ids = sorted({m["source"]["claim_id"] for m in ms if "claim_id" in m["source"]},
                           key=lambda c: (c.split("-")[1], c))
        lines = sorted({m["source"]["line_start"] for m in ms if "file" in m["source"]})
        names = sorted({m["name_as_written"] for m in ms}, key=str.lower)
        rec = {
            "slug": slug,
            "accepted_name": seed["name"],
            "rank": seed["rank"],
            "vernacular": seed.get("vernacular", []),
            "names_as_written": names,
            "identifiers": {
                "gbif_usage_key": gkey,
                "ncbi_taxid": nkey,
                "wikidata_qid": qid,
                "itis_tsn": tsn,
                "worms_aphia_id": aphia,
            },
            "lineage": (ginfo or {}).get("lineage", {}),
            "mentioned_in": claim_ids,
            "text_mentions": {"file": "books/darwin-origin/inputs/pg1228.txt", "n": len(lines), "lines": lines},
            "datasets": [],
            "notes": seed.get("notes", ""),
            "resolution_notes": notes,
            "resolved_at": now(),
        }
        if not rec["lineage"]:
            rec["lineage"] = LINEAGE_FALLBACK.get(slug, {})
        (SLICE / "taxa" / f"{slug}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        flag = "" if (gkey and nkey and qid) else "  <-- incomplete"
        print(f"{slug:26} gbif={gkey} ncbi={nkey} wd={qid} itis={tsn} worms={aphia}{flag}")
        for x in notes:
            print("     -", x)
        if not qid or not (gkey or nkey):
            problems.append(slug)
    if problems:
        print("\nUnresolved or partial:", problems)


if __name__ == "__main__":
    main(sys.argv[1:] or list(TAXA))
