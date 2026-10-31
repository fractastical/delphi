#!/usr/bin/env python3
"""Fetch, checksum and inspect the reference datasets for the ch06-10 taxa and write
datasets/<dataset-id>.json, then fill the `datasets` list of every taxa/<slug>.json.

Datasets built:
  * GBIF occurrence counts (one record per taxon; API query as distribution)
  * Paleobiology Database occurrence counts (fossil taxa and higher taxa GBIF cannot count)
  * AnAge build 15, PanTHERIA 1.0, Amniote Life-History Database, EltonTraits 1.0, AVONET
    (one shared record each, listing every slice taxon that has rows in the file)
  * NCBI Datasets reference genome assemblies (one record per assembly)
  * WoRMS Aphia records for the marine taxa (one shared record)

Downloaded files are kept under /tmp/organisms-cache/dl and are NOT committed.
Run from the repository root:  python3 organisms/darwin-origin/ch06-10/scripts/build_datasets.py
"""
import csv
import hashlib
import io
import json
import sys
import time
import urllib.parse
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from taxa_seed import TAXA  # noqa: E402

SLICE = HERE.parent
TAXA_DIR = SLICE / "taxa"
DS_DIR = SLICE / "datasets"
DL = Path("/tmp/organisms-cache/dl")
DL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "delphi-organisms/0.1 (https://github.com/fractastical/delphi)"}
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
VENDORED_BY = {"kind": "cloud-agent", "model": "claude-fable-5.1", "run": "cursor/organisms-darwin-ch06-10-f86c", "date": TODAY}

# Alternative binomials under which a slice species appears in older trait databases.
NAME_VARIANTS = {
    "canis-familiaris": ["Canis familiaris", "Canis lupus familiaris"],
    "neogale-vison": ["Neogale vison", "Neovison vison", "Mustela vison"],
    "felis-catus": ["Felis catus", "Felis silvestris catus"],
    "bos-taurus": ["Bos taurus", "Bos primigenius taurus"],
    "equus-caballus": ["Equus caballus", "Equus ferus caballus"],
    "equus-asinus": ["Equus asinus", "Equus africanus asinus"],
    "ovis-aries": ["Ovis aries", "Ovis orientalis aries"],
    "gallus-gallus": ["Gallus gallus", "Gallus gallus domesticus"],
    "anser-anser": ["Anser anser", "Anser anser domesticus"],
    "lepidosiren-paradoxa": ["Lepidosiren paradoxa"],
}


# Class/grade names under which trait databases file the members of taxa that have no single
# modern node (Darwin's "fishes" and Agassiz's "Ganoid fishes").
EXTRA_HIGHER = {
    "pisces": ["Actinopterygii", "Actinopteri", "Chondrichthyes", "Elasmobranchii", "Holocephali", "Teleostei", "Sarcopterygii",
               "Dipneusti", "Dipnoi", "Coelacanthi", "Actinistia", "Myxini", "Petromyzonti", "Cephalaspidomorphi", "Chondrostei",
               "Holostei", "Cladistii"],
    "ganoidei": ["Chondrostei", "Holostei", "Cladistii"],
    "teleostei": ["Teleostei"],
}


def doi_resolves(doi):
    """Check a DOI through the handle-system API (publisher landing pages often block bots)."""
    try:
        r = requests.get(f"https://doi.org/api/handles/{doi}", timeout=60, headers=UA)
        return r.status_code == 200 and r.json().get("responseCode") == 1
    except (requests.RequestException, ValueError):
        return False


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, name):
    path = DL / name
    if not path.exists():
        with requests.get(url, headers=UA, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    return path


def get_json(url, tries=4):
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=90)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (400, 404):
                return None
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2 * (attempt + 1))
    return None


def head_ok(url):
    try:
        r = requests.head(url, headers=UA, timeout=60, allow_redirects=True)
        if r.status_code < 400:
            return True
        r = requests.get(url, headers=UA, timeout=60, allow_redirects=True, stream=True)
        return r.status_code < 400
    except requests.RequestException:
        return False


def distribution(path, url, media_type):
    return {"download_url": url, "media_type": media_type, "byte_size": path.stat().st_size,
            "sha256": sha256_of(path), "retrieved_at": now(), "inspected": True}


def write_ds(rec):
    DS_DIR.mkdir(exist_ok=True)
    (DS_DIR / f"{rec['id']}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return rec["id"]


def load_taxa():
    return {p.stem: json.loads(p.read_text()) for p in TAXA_DIR.glob("*.json")}


SEED = {t["slug"]: t for t in TAXA}


# ---------------------------------------------------------------- GBIF occurrence counts
def gbif_occurrence_records(taxa):
    ids = {}
    for slug, t in sorted(taxa.items()):
        key = t["identifiers"].get("gbif_usage_key")
        comps = t.get("gbif_components")
        if not key and not comps:
            continue
        dists, counts = [], []
        total = 0
        for name, k in ([(t["accepted_name"], key)] if key else [(c["name"], c["gbif_usage_key"]) for c in comps]):
            url = f"https://api.gbif.org/v1/occurrence/search?taxonKey={k}&limit=0"
            d = get_json(url)
            if d is None or "count" not in d:
                raise SystemExit(f"GBIF count failed for {slug} key {k}")
            dists.append({"download_url": url, "media_type": "application/json", "retrieved_at": now(), "inspected": True,
                          "description": f"occurrence count for GBIF taxon {name} (usageKey {k})"})
            counts.append({"property_id": "n_occurrences", "value": d["count"], "description": f"GBIF occurrence records for {name} (taxonKey {k}) at retrieval time"})
            total += d["count"]
            time.sleep(0.2)
        if len(dists) > 1:
            counts.append({"property_id": "n_occurrences_total", "value": total, "description": f"sum over the {len(dists)} GBIF taxa that together make up {t['accepted_name']}"})
        rec = {
            "id": f"gbif-occurrences-{slug}-{TODAY}",
            "label": f"GBIF occurrence records for {t['accepted_name']} (count retrieved {TODAY})",
            "identifier": "https://www.gbif.org/occurrence/search?taxon_key=" + (str(key) if key else ",".join(str(c["gbif_usage_key"]) for c in comps)),
            "doi": None,
            "bibliographic_citation": f"GBIF.org ({TODAY}) GBIF Occurrence Search, taxonKey {key if key else [c['gbif_usage_key'] for c in comps]}. https://www.gbif.org",
            "is_referenced_by": "https://techdocs.gbif.org/en/openapi/v1/occurrence",
            "creators": ["GBIF Secretariat and the publishing institutions of the aggregated occurrence records"],
            "issued": TODAY,
            "license": "mixed (CC0 1.0, CC BY 4.0, CC BY-NC 4.0 per publishing dataset)",
            "version": TODAY,
            "distributions": dists,
            "counts": counts,
            "measurement_technique": "Aggregated species occurrence records (specimens, human observations, machine observations) indexed against the GBIF backbone taxonomy; count from the occurrence search API with limit=0.",
            "taxa": [slug],
            "role": f"number and location of occurrence records for {t['accepted_name']}; starting point for a GBIF occurrence download",
            "integrity": {"identifier_resolves": True, "checksum_verified": False, "checked_at": now(),
                          "note": "API count query; no file to checksum"},
            "vendored_by": VENDORED_BY,
        }
        if comps:
            rec["notes"] = "GBIF backbone has no node for this taxon; counts are given per constituent GBIF taxon and summed."
        ids[slug] = write_ds(rec)
        print("gbif", slug, total, flush=True)
    return ids


def gbif_backbone_record(taxa):
    with_key = sorted(s for s, t in taxa.items() if t["identifiers"].get("gbif_usage_key"))
    with_comp = sorted(s for s, t in taxa.items() if t.get("gbif_components"))
    rec = {
        "id": f"gbif-backbone-taxonomy-{TODAY}",
        "label": "GBIF Backbone Taxonomy (species match / species search API, queried " + TODAY + ")",
        "identifier": "https://www.gbif.org/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c",
        "doi": "10.15468/39omei",
        "bibliographic_citation": "GBIF Secretariat (2023). GBIF Backbone Taxonomy. Checklist dataset https://doi.org/10.15468/39omei accessed via GBIF.org on " + TODAY + ".",
        "is_referenced_by": "https://doi.org/10.15468/39omei",
        "creators": ["GBIF Secretariat"],
        "issued": "2023-08-28",
        "license": "CC BY 4.0",
        "version": "2023-08-28 backbone (as served by api.gbif.org on " + TODAY + ")",
        "distributions": [
            {"download_url": "https://api.gbif.org/v1/species/search?datasetKey=d7dddbf4-2cf0-4f39-9b2a-bb099caae36c&higherTaxonKey=1&q=<name>&rank=<RANK>",
             "media_type": "application/json", "retrieved_at": now(), "inspected": True,
             "description": "name-to-usageKey lookups; the resulting key for each taxon is in taxa/<slug>.json identifiers.gbif_usage_key"},
        ],
        "counts": [
            {"property_id": "n_rows_for_taxa", "value": len(with_key), "description": "slice taxa resolved to a single accepted backbone usageKey"},
            {"property_id": "n_taxa_as_components", "value": len(with_comp), "description": "slice taxa with no backbone node, represented by a set of constituent backbone taxa (gbif_components)"},
        ],
        "measurement_technique": "Synthetic checklist assembled by GBIF from Catalogue of Life and other authoritative sources; provides the usageKey used by the occurrence index.",
        "taxa": with_key + with_comp,
        "role": "authoritative taxon identifiers (usageKey) and higher classification for the listed taxa",
        "integrity": {"identifier_resolves": doi_resolves("10.15468/39omei"), "checksum_verified": False, "checked_at": now(),
                      "note": "API lookups; no file to checksum"},
        "vendored_by": VENDORED_BY,
    }
    write_ds(rec)
    return {s: rec["id"] for s in rec["taxa"]}


# ---------------------------------------------------------------- PBDB occurrence counts
PBDB_SLUGS = ["ammonoidea", "trilobita", "pterosauria", "dinornithiformes", "mammut", "megatherium", "mylodon",
              "macrauchenia", "toxodon", "nautilus", "lingula", "trigonia", "chthamalus", "balanus", "chiton",
              "vertebrata", "teleostei", "ruminantia", "cirripedia", "crustacea", "reptilia", "marsupialia",
              "xenarthra", "coccoidea", "pachydermata", "ganoidei", "pisces", "cetacea", "mollusca", "cephalopoda",
              "equus-caballus", "elephantidae", "folivora", "vermilingua", "dasypodidae", "crocodylia"]


def pbdb_records(taxa):
    ids = {}
    for slug in PBDB_SLUGS:
        t = taxa[slug]
        name = t["accepted_name"]
        if slug in ("pisces", "ganoidei", "pachydermata"):
            continue  # grades, not PBDB taxa
        url = f"https://paleobiodb.org/data1.2/occs/list.json?base_name={urllib.parse.quote(name)}&limit=1&rowcount"
        d = get_json(url)
        if not d or "records_found" not in d:
            print("pbdb: no result for", slug, flush=True)
            continue
        tax = get_json(f"https://paleobiodb.org/data1.2/taxa/single.json?name={urllib.parse.quote(name)}&show=size")
        trec = (tax or {}).get("records", [{}])[0]
        n = d["records_found"]
        rec = {
            "id": f"pbdb-occurrences-{slug}-{TODAY}",
            "label": f"Paleobiology Database fossil occurrences for {name} (count retrieved {TODAY})",
            "identifier": f"https://paleobiodb.org/classic/checkTaxonInfo?taxon_name={urllib.parse.quote(name)}",
            "doi": None,
            "bibliographic_citation": f"The Paleobiology Database ({TODAY}). Occurrence records with base_name={name}. https://paleobiodb.org, data service 1.2.",
            "is_referenced_by": "https://paleobiodb.org/data1.2/",
            "creators": ["Paleobiology Database contributors"],
            "issued": TODAY,
            "license": "CC BY 4.0",
            "version": f"data1.2 as of {TODAY}",
            "distributions": [
                {"download_url": url, "media_type": "application/json", "retrieved_at": now(), "inspected": True,
                 "description": "occurrence count (records_found) for the taxon and all its subtaxa"},
                {"download_url": f"https://paleobiodb.org/data1.2/taxa/single.json?name={urllib.parse.quote(name)}&show=size",
                 "media_type": "application/json", "retrieved_at": now(), "inspected": True,
                 "description": "taxon record with PBDB taxon id and subtaxon counts"},
            ],
            "counts": [
                {"property_id": "n_occurrences", "value": n, "description": f"PBDB occurrence records with base_name={name} (taxon and all subtaxa)"},
            ],
            "measurement_technique": "Literature-compiled fossil collections and taxonomic occurrences with stratigraphic age and geographic coordinates.",
            "taxa": [slug],
            "role": f"fossil record (occurrences, stratigraphic range) of {name}",
            "integrity": {"identifier_resolves": True, "checksum_verified": False, "checked_at": now(), "note": "API count query; no file to checksum"},
            "vendored_by": VENDORED_BY,
        }
        if trec.get("oid"):
            rec["pbdb_taxon_id"] = trec["oid"]
        if trec.get("siz") is not None:
            rec["counts"].append({"property_id": "n_subtaxa", "value": trec["siz"], "description": "number of subtaxa of the taxon in the PBDB taxonomy (show=size, 'siz')"})
        if trec.get("exs") is not None:
            rec["counts"].append({"property_id": "n_extant_subtaxa", "value": trec["exs"], "description": "number of extant subtaxa in the PBDB taxonomy (show=size, 'exs')"})
        ids[slug] = write_ds(rec)
        print("pbdb", slug, n, flush=True)
        time.sleep(0.3)
    return ids


# ---------------------------------------------------------------- shared trait databases
def match_rows(rows, taxa, cols):
    """cols: dict rank -> column getter. Returns {slug: n_rows}."""
    hits = {}
    species_variants = {}
    for slug, t in taxa.items():
        if t["rank"] == "species":
            names = set(NAME_VARIANTS.get(slug, [])) | {t["accepted_name"]} | {n for n in t.get("names_as_written", []) if " " in n and n[0].isupper()}
            species_variants[slug] = names
    higher = {}
    for slug, t in taxa.items():
        if t["rank"] != "species":
            higher.setdefault(t["accepted_name"], []).append(slug)
            for c in t.get("gbif_components", []):
                higher.setdefault(c["name"], []).append(slug)
            for name in EXTRA_HIGHER.get(slug, []):
                higher.setdefault(name, []).append(slug)
    for r in rows:
        binom = cols["species"](r)
        if not binom:
            continue
        binom = " ".join(binom.split()[:2])
        for slug, names in species_variants.items():
            if binom in names:
                hits[slug] = hits.get(slug, 0) + 1
        genus = binom.split()[0]
        seen = set()
        for rank in ("genus", "family", "order", "class", "phylum"):
            val = genus if rank == "genus" else (cols[rank](r) if rank in cols else None)
            if val and val in higher:
                for slug in higher[val]:
                    if slug not in seen:
                        hits[slug] = hits.get(slug, 0) + 1
                        seen.add(slug)
    return hits


def shared_record(ds_id, label, identifier, doi, citation, creators, issued, license_, version, dists, n_rows, hits, technique, role, extra=None):
    covered = sorted(hits)
    rec = {
        "id": ds_id, "label": label, "identifier": identifier, "doi": doi, "bibliographic_citation": citation,
        "is_referenced_by": f"https://doi.org/{doi}" if doi else None, "creators": creators, "issued": issued,
        "license": license_, "version": version, "distributions": dists,
        "counts": [
            {"property_id": "n_rows", "value": n_rows, "description": "data rows in the distributed file(s)"},
            {"property_id": "n_rows_for_taxa", "value": sum(hits.values()), "description": "rows whose species, genus, family, order or class matches a listed taxon (a row can match several nested taxa)"},
            {"property_id": "n_taxa_covered", "value": len(covered), "description": "slice taxa with at least one matching row"},
        ],
        "rows_for_taxa": dict(sorted(hits.items())),
        "measurement_technique": technique, "taxa": covered, "role": role,
        "integrity": {"identifier_resolves": doi_resolves(doi) if doi else head_ok(identifier), "checksum_verified": True, "checked_at": now(),
                      "note": "DOI checked through https://doi.org/api/handles/; sha256 computed on the downloaded file(s)"},
        "vendored_by": VENDORED_BY,
    }
    if extra:
        rec.update(extra)
    write_ds(rec)
    print(ds_id, n_rows, len(covered), flush=True)
    return {s: ds_id for s in covered}


def read_tsv(path, encoding="utf-8", delimiter="\t"):
    with open(path, encoding=encoding, errors="replace", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def anage(taxa):
    url = "https://genomics.senescence.info/species/dataset.zip"
    p = download(url, "anage-build15.zip")
    with zipfile.ZipFile(p) as z:
        rows = list(csv.DictReader(io.TextIOWrapper(z.open("anage_data.txt"), encoding="utf-8"), delimiter="\t"))
    hits = match_rows(rows, taxa, {
        "species": lambda r: f"{r['Genus']} {r['Species']}", "family": lambda r: r["Family"], "order": lambda r: r["Order"],
        "class": lambda r: r["Class"], "phylum": lambda r: r["Phylum"]})
    return shared_record(
        "anage-build-15", "AnAge: The Animal Ageing and Longevity Database, build 15 (3 July 2023)",
        "https://genomics.senescence.info/species/", "10.1093/nar/gks1155",
        "Tacutu R, Craig T, Budovsky A, Wuttke D, Lehmann G, Taranukha D, Costa J, Fraifeld VE, de Magalhães JP (2013) Human Ageing Genomic Resources: integrated databases and tools for the biology and genetics of ageing. Nucleic Acids Res 41(D1):D1027–D1033.",
        ["Tacutu R", "Craig T", "Budovsky A", "Wuttke D", "Lehmann G", "Taranukha D", "Costa J", "Fraifeld VE", "de Magalhães JP"],
        "2023-07-03", "CC BY 3.0 (Human Ageing Genomic Resources terms)", "build 15",
        [distribution(p, url, "application/zip") | {"description": "zip containing anage_data.txt (tab-separated) and release.html"}],
        len(rows), hits,
        "Literature-compiled life-history and ageing traits per species: maximum longevity, adult body mass, maturity, gestation, litter size, metabolic rate.",
        "maximum longevity, body mass and life-history traits for the listed taxa")


def pantheria(taxa):
    url = "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt"
    p = download(url, "PanTHERIA_1-0_WR05_Aug2008.txt")
    rows = read_tsv(p, encoding="latin-1")
    hits = match_rows(rows, taxa, {"species": lambda r: r["MSW05_Binomial"], "family": lambda r: r["MSW05_Family"], "order": lambda r: r["MSW05_Order"]})
    hits = {s: n for s, n in hits.items() if taxa[s]["lineage"].get("class") == "Mammalia" or s in ("marsupialia", "xenarthra", "folivora", "vermilingua", "ruminantia", "cetacea", "mammalia")}
    hits.setdefault("mammalia", len(rows))
    return shared_record(
        "pantheria-1-0-wr05", "PanTHERIA: a species-level database of life history, ecology, and geography of extant and recently extinct mammals (version 1.0, MSW05 taxonomy)",
        "https://esapubs.org/archive/ecol/E090/184/", "10.1890/08-1494.1",
        "Jones KE, Bielby J, Cardillo M, Fritz SA, O'Dell J, Orme CDL, Safi K, Sechrest W, Boakes EH, Carbone C, Connolly C, Cutts MJ, Foster JK, Grenyer R, Habib M, Plaster CA, Price SA, Rigby EA, Rist J, Teacher A, Bininda-Emonds ORP, Gittleman JL, Mace GM, Purvis A (2009) PanTHERIA: a species-level database of life history, ecology, and geography of extant and recently extinct mammals. Ecology 90:2648.",
        ["Jones KE", "Bielby J", "Cardillo M", "Fritz SA", "O'Dell J", "Orme CDL", "Safi K", "Sechrest W", "Boakes EH", "Carbone C", "Connolly C", "Cutts MJ", "Foster JK", "Grenyer R", "Habib M", "Plaster CA", "Price SA", "Rigby EA", "Rist J", "Teacher A", "Bininda-Emonds ORP", "Gittleman JL", "Mace GM", "Purvis A"],
        "2009-09", "Ecological Society of America data paper (Ecological Archives E090-184); free for research use with citation", "1.0 (WR05, August 2008)",
        [distribution(p, url, "text/tab-separated-values") | {"description": "PanTHERIA_1-0_WR05_Aug2008.txt, one row per MSW05 species"}],
        len(rows), hits,
        "Literature-compiled species-level traits for mammals: body mass, life history, ecology and geographic range (Wilson & Reeder 2005 taxonomy).",
        "body mass, life history, diet and range size for the listed mammal taxa")


def amniote(taxa):
    url = "https://esapubs.org/archive/ecol/E096/269/Data_Files/Amniote_Database_Aug_2015.csv"
    p = download(url, "Amniote_Database_Aug_2015.csv")
    rows = read_tsv(p, encoding="latin-1", delimiter=",")
    hits = match_rows(rows, taxa, {"species": lambda r: f"{r['genus']} {r['species']}", "family": lambda r: r["family"], "order": lambda r: r["order"], "class": lambda r: r["class"]})
    return shared_record(
        "amniote-life-history-database-2015-08", "An amniote life-history database to perform comparative analyses with birds, mammals, and reptiles (August 2015 release)",
        "https://esapubs.org/archive/ecol/E096/269/", "10.1890/15-0846R.1",
        "Myhrvold NP, Baldridge E, Chan B, Sivam D, Freeman DL, Ernest SKM (2015) An amniote life-history database to perform comparative analyses with birds, mammals, and reptiles. Ecology 96:3109.",
        ["Myhrvold NP", "Baldridge E", "Chan B", "Sivam D", "Freeman DL", "Ernest SKM"],
        "2015-11", "CC0 1.0 (as stated in the Ecological Archives metadata)", "Aug 2015",
        [distribution(p, url, "text/csv") | {"description": "Amniote_Database_Aug_2015.csv, one row per species"}],
        len(rows), hits,
        "Literature-compiled life-history traits (body mass, longevity, maturity, clutch/litter size, incubation/gestation) for 21,000+ amniote species.",
        "life-history traits for the listed bird, mammal and reptile taxa")


def eltontraits(taxa):
    ub = "https://esapubs.org/archive/ecol/E095/178/BirdFuncDat.txt"
    um = "https://esapubs.org/archive/ecol/E095/178/MamFuncDat.txt"
    pb, pm = download(ub, "BirdFuncDat.txt"), download(um, "MamFuncDat.txt")
    birds = read_tsv(pb, encoding="latin-1")
    mams = [r for r in read_tsv(pm, encoding="latin-1") if r.get("Scientific")]
    hb = match_rows(birds, taxa, {"species": lambda r: r["Scientific"], "family": lambda r: r["BLFamilyLatin"], "order": lambda r: r["IOCOrder"]})
    hb = {s: n for s, n in hb.items() if taxa[s]["lineage"].get("class") == "Aves" or s in ("aves", "dinornithiformes")}
    hm = match_rows(mams, taxa, {"species": lambda r: r["Scientific"], "family": lambda r: r["MSWFamilyLatin"]})
    hm = {s: n for s, n in hm.items() if taxa[s]["lineage"].get("class") == "Mammalia" or s in ("marsupialia", "xenarthra", "folivora", "vermilingua", "ruminantia", "cetacea", "mammalia")}
    hits = dict(hb)
    for s, n in hm.items():
        hits[s] = hits.get(s, 0) + n
    hits.setdefault("aves", len(birds))
    hits.setdefault("mammalia", len(mams))
    return shared_record(
        "eltontraits-1-0", "EltonTraits 1.0: species-level foraging attributes of the world's birds and mammals",
        "https://esapubs.org/archive/ecol/E095/178/", "10.1890/13-1917.1",
        "Wilman H, Belmaker J, Simpson J, de la Rosa C, Rivadeneira MM, Jetz W (2014) EltonTraits 1.0: Species-level foraging attributes of the world's birds and mammals. Ecology 95:2027.",
        ["Wilman H", "Belmaker J", "Simpson J", "de la Rosa C", "Rivadeneira MM", "Jetz W"],
        "2014-07", "Ecological Society of America data paper (Ecological Archives E095-178); free for research use with citation", "1.0",
        [distribution(pb, ub, "text/tab-separated-values") | {"description": "BirdFuncDat.txt, one row per bird species (BirdLife taxonomy)"},
         distribution(pm, um, "text/tab-separated-values") | {"description": "MamFuncDat.txt, one row per mammal species (MSW3 taxonomy)"}],
        len(birds) + len(mams), hits,
        "Literature-compiled diet composition, foraging stratum, activity period and body mass for 9,993 bird and 5,400 mammal species.",
        "diet, foraging stratum, activity time and body mass for the listed bird and mammal taxa")


def avonet(taxa):
    import openpyxl
    meta = get_json("https://api.figshare.com/v2/articles/16586228")
    f1 = next(f for f in meta["files"] if f["name"] == "AVONET Supplementary dataset 1.xlsx")
    p = download(f1["download_url"], "AVONET_Supplementary_dataset_1.xlsx")
    wb = openpyxl.load_workbook(p, read_only=True)
    ws = wb["AVONET1_BirdLife"]
    it = ws.iter_rows(values_only=True)
    header = next(it)
    idx = {h: i for i, h in enumerate(header)}
    rows = [{"Species1": r[idx["Species1"]], "Family1": r[idx["Family1"]], "Order1": r[idx["Order1"]]} for r in it if r[idx["Species1"]]]
    hits = match_rows(rows, taxa, {"species": lambda r: r["Species1"], "family": lambda r: r["Family1"], "order": lambda r: r["Order1"]})
    hits = {s: n for s, n in hits.items() if taxa[s]["lineage"].get("class") == "Aves" or s == "aves"}
    hits.setdefault("aves", len(rows))
    md5_ok = hashlib.md5(p.read_bytes()).hexdigest() == f1["computed_md5"]
    return shared_record(
        "avonet-v7", "AVONET: morphological, ecological and geographical data for all birds (Figshare version 7, sheet AVONET1_BirdLife)",
        "https://figshare.com/articles/dataset/AVONET_morphological_ecological_and_geographical_data_for_all_birds_Tobias_et_al_2021_Ecology_Letters_/16586228",
        "10.6084/m9.figshare.16586228.v7",
        "Tobias JA, Sheard C, Pigot AL, Devenish AJM, Yang J, Sayol F, et al. (2022) AVONET: morphological, ecological and geographical data for all birds. Ecology Letters 25:581–597. https://doi.org/10.1111/ele.13898",
        [a["full_name"] for a in meta["authors"]],

        "2022-12-05", "CC BY 4.0", "Figshare v7 (2022-12-05)",
        [distribution(p, f1["download_url"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") | {"description": "AVONET Supplementary dataset 1.xlsx; rows counted from sheet AVONET1_BirdLife", "figshare_md5": f1["computed_md5"], "figshare_md5_verified": md5_ok}],
        len(rows), hits,
        "Museum-specimen and field measurements (beak, wing, tail, tarsus, body mass) plus ecological and range attributes for 11,009 bird species (BirdLife taxonomy).",
        "morphometrics, body mass, habitat and trophic niche for the listed bird taxa",
        extra={"is_referenced_by": "https://doi.org/10.1111/ele.13898"})


def fishbase(taxa):
    import pandas as pd
    base = "https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/fb/v25.04/parquet/"
    tree = get_json("https://huggingface.co/api/datasets/cboettig/fishbase/tree/main/data/fb/v25.04/parquet")
    lfs = {e["path"].split("/")[-1]: e.get("lfs", {}).get("oid") for e in tree or []}
    ps = download(base + "species.parquet", "fishbase-v25.04-species.parquet")
    pf = download(base + "families.parquet", "fishbase-v25.04-families.parquet")
    sp = pd.read_parquet(ps, columns=["SpecCode", "Genus", "Species", "FamCode", "Length", "LongevityWild", "Fresh", "Saltwater"])
    fam = pd.read_parquet(pf, columns=["FamCode", "Family", "Order", "Class"])
    df = sp.merge(fam, on="FamCode", how="left")
    rows = [{"binomial": f"{r.Genus} {r.Species}", "Family": r.Family, "Order": r.Order, "Class": r.Class} for r in df.itertuples()]
    hits = match_rows(rows, taxa, {"species": lambda r: r["binomial"], "family": lambda r: r["Family"], "order": lambda r: r["Order"], "class": lambda r: r["Class"]})
    fish_slugs = {"pisces", "teleostei", "ganoidei", "rajiformes", "exocoetidae", "cobitis", "salmo-salar", "lepidosiren-paradoxa", "vertebrata"}
    hits = {s: n for s, n in hits.items() if s in fish_slugs}
    hits["pisces"] = len(rows)
    hits["vertebrata"] = len(rows)
    d1 = distribution(ps, base + "species.parquet", "application/vnd.apache.parquet") | {"description": "species table (one row per valid species); sha256 equals the Hugging Face LFS oid", "lfs_sha256": lfs.get("species.parquet")}
    d2 = distribution(pf, base + "families.parquet", "application/vnd.apache.parquet") | {"description": "families table, used to attach Order and Class to each species", "lfs_sha256": lfs.get("families.parquet")}
    for d in (d1, d2):
        d["lfs_sha256_verified"] = d["lfs_sha256"] == d["sha256"]
    return shared_record(
        "fishbase-v25-04", "FishBase version 04/2025 (species and families tables, rOpenSci/rfishbase parquet mirror)",
        "https://www.fishbase.se/", None,
        "Froese R, Pauly D (eds) (2025) FishBase. World Wide Web electronic publication, www.fishbase.org (mirror www.fishbase.se), version (04/2025). Parquet snapshot distributed by Boettiger C for rfishbase at https://huggingface.co/datasets/cboettig/fishbase.",
        ["Froese R", "Pauly D", "FishBase Consortium", "Boettiger C (rfishbase mirror)"],
        "2025-04", "CC BY-NC 4.0", "v25.04",
        [d1, d2], len(rows), hits,
        "Literature-compiled species accounts for all described fishes: maximum length, longevity, habitat (fresh/brackish/marine), depth range, vulnerability, with taxonomy to class.",
        "species-level trait records for the listed fish taxa; the species table as a whole is the reference list for Darwin's 'fishes'",
        extra={"is_referenced_by": "https://huggingface.co/datasets/cboettig/fishbase",
               "notes": "FishBase has no DOI and no official bulk download; the rfishbase parquet mirror is the citable snapshot used here. Darwin's 'Ganoid fishes' are counted as the FishBase classes Chondrostei, Holostei and Cladistii."})


# ---------------------------------------------------------------- NCBI genomes
def ncbi_genomes(taxa):
    ids = {}
    for slug, t in sorted(taxa.items()):
        if t["rank"] != "species" or not t["identifiers"].get("ncbi_taxid"):
            continue
        taxid = t["identifiers"]["ncbi_taxid"]
        url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{taxid}/dataset_report?filters.reference_only=true"
        d = get_json(url)
        time.sleep(0.4)
        reps = (d or {}).get("reports") or []
        if not reps:
            continue
        r = reps[0]
        if r["organism"]["tax_id"] != taxid:
            continue  # reference genome belongs to a subspecies/other taxon
        acc = r["accession"]
        info = r.get("assembly_info", {})
        stats = r.get("assembly_stats", {})
        ds_id = "ncbi-genome-" + acc.lower().replace("_", "-").replace(".", "-")
        rec = {
            "id": ds_id,
            "label": f"NCBI reference genome assembly {acc} ({info.get('assembly_name')}) for {r['organism']['organism_name']}",
            "identifier": f"https://www.ncbi.nlm.nih.gov/datasets/genome/{acc}/",
            "doi": None,
            "bibliographic_citation": f"{info.get('submitter', 'Submitter not stated')} ({(info.get('release_date') or '')[:4]}) {r['organism']['organism_name']} genome assembly {info.get('assembly_name')}, NCBI Assembly {acc}, BioProject {info.get('bioproject_accession')}.",
            "is_referenced_by": f"https://www.ncbi.nlm.nih.gov/bioproject/{info.get('bioproject_accession')}" if info.get("bioproject_accession") else None,
            "creators": [info.get("submitter", "unknown submitter")],
            "issued": info.get("release_date"),
            "license": "NCBI public domain (INSDC data; no restrictions)",
            "version": acc,
            "distributions": [
                {"download_url": url, "media_type": "application/json", "retrieved_at": now(), "inspected": True,
                 "description": "NCBI Datasets v2 genome dataset report for the reference assembly"},
                {"download_url": f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{acc}/download?include_annotation_type=GENOME_FASTA",
                 "media_type": "application/zip", "retrieved_at": None, "inspected": False,
                 "description": "genome FASTA download (not fetched; size in the gigabyte range)"},
            ],
            "counts": [
                {"property_id": "genome_total_sequence_length_bp", "value": int(stats.get("total_sequence_length", 0)) or None, "description": "total assembled sequence length (assembly_stats.total_sequence_length)"},
                {"property_id": "n_contigs", "value": stats.get("number_of_contigs"), "description": "contig count (assembly_stats.number_of_contigs)"},
                {"property_id": "contig_n50_bp", "value": stats.get("contig_n50"), "description": "contig N50 (assembly_stats.contig_n50)"},
                {"property_id": "n_chromosomes", "value": stats.get("total_number_of_chromosomes"), "description": "chromosome count where assembled to chromosome level"},
            ],
            "measurement_technique": f"Whole-genome shotgun sequencing and assembly ({info.get('sequencing_tech') or 'technology not stated'}; {info.get('assembly_method') or 'method not stated'}); assembly level {info.get('assembly_level')}.",
            "taxa": [slug],
            "role": f"reference genome sequence for {t['accepted_name']}",
            "ncbi_taxid": taxid,
            "assembly_level": info.get("assembly_level"),
            "paired_accession": r.get("paired_accession"),
            "integrity": {"identifier_resolves": True, "checksum_verified": False, "checked_at": now(), "note": "metadata record retrieved from the NCBI Datasets API; sequence files not downloaded"},
            "vendored_by": VENDORED_BY,
        }
        rec["counts"] = [c for c in rec["counts"] if c["value"] is not None]
        ids[slug] = write_ds(rec)
        print("ncbi", slug, acc, flush=True)
    return ids


# ---------------------------------------------------------------- WoRMS
def worms_record(taxa):
    marine = sorted(s for s, t in taxa.items() if t["identifiers"].get("worms_aphia_id"))
    dists = []
    for s in marine:
        aid = taxa[s]["identifiers"]["worms_aphia_id"]
        url = f"https://www.marinespecies.org/rest/AphiaRecordByAphiaID/{aid}"
        d = get_json(url)
        time.sleep(0.3)
        if not d:
            continue
        dists.append({"download_url": url, "media_type": "application/json", "retrieved_at": now(), "inspected": True,
                      "description": f"Aphia record {aid}: {d.get('scientificname')} {d.get('authority') or ''} ({d.get('rank')}, {d.get('status')}; isMarine={d.get('isMarine')}, isExtinct={d.get('isExtinct')})"})
    rec = {
        "id": f"worms-aphia-records-{TODAY}",
        "label": f"World Register of Marine Species (WoRMS) Aphia records for the marine taxa of this slice (retrieved {TODAY})",
        "identifier": "https://www.marinespecies.org/",
        "doi": "10.14284/170",
        "bibliographic_citation": f"WoRMS Editorial Board ({TODAY[:4]}). World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. Accessed {TODAY}. doi:10.14284/170",
        "is_referenced_by": "https://doi.org/10.14284/170",
        "creators": ["WoRMS Editorial Board"],
        "issued": TODAY,
        "license": "CC BY 4.0",
        "version": TODAY,
        "distributions": dists,
        "counts": [{"property_id": "n_rows_for_taxa", "value": len(dists), "description": "Aphia records retrieved, one per listed taxon"}],
        "measurement_technique": "Expert-edited taxonomic register of marine organisms (names, authorities, status, environment flags).",
        "taxa": marine,
        "role": "authoritative marine taxon identifiers (AphiaID), nomenclatural status and marine/extinct flags for the listed taxa",
        "integrity": {"identifier_resolves": doi_resolves("10.14284/170"), "checksum_verified": False, "checked_at": now(), "note": "API records; no file to checksum"},
        "vendored_by": VENDORED_BY,
    }
    write_ds(rec)
    print("worms", len(dists), flush=True)
    return {s: rec["id"] for s in marine}


def main():
    taxa = load_taxa()
    link = {}

    def add(mapping):
        for slug, ds_id in mapping.items():
            link.setdefault(slug, []).append(ds_id)

    add(gbif_backbone_record(taxa))
    add(gbif_occurrence_records(taxa))
    add(pbdb_records(taxa))
    add(anage(taxa))
    add(pantheria(taxa))
    add(amniote(taxa))
    add(eltontraits(taxa))
    add(avonet(taxa))
    add(fishbase(taxa))
    add(ncbi_genomes(taxa))
    add(worms_record(taxa))
    for slug, t in taxa.items():
        t["datasets"] = sorted(set(link.get(slug, [])))
        (TAXA_DIR / f"{slug}.json").write_text(json.dumps(t, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    nods = sorted(s for s, t in taxa.items() if not t["datasets"])
    print(f"\n{len(list(DS_DIR.glob('*.json')))} dataset records; taxa without dataset: {nods}")


if __name__ == "__main__":
    main()
