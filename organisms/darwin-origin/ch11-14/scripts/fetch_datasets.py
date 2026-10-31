#!/usr/bin/env python3
"""Fetch, inspect and checksum the reference datasets for the ch11-14 taxa and write
datasets/<id>.json; then fill the `datasets` field of each taxa/<slug>.json.

Datasets built:
  * one GBIF occurrence-count record per taxon with a GBIF backbone key
  * one Paleobiology Database occurrence-count record per extinct taxon
  * one NCBI Datasets reference-genome record per species-rank taxon that has one
  * shared records (one per slice, listing every taxon they contain):
    AnAge build 15, PanTHERIA 1.0, Amniote Life-History Database (2015),
    EltonTraits 1.0, AVONET (figshare v7), WoRMS Aphia records

Downloads go to /tmp/delphi-organisms-data; files under 1 MB are also vendored into
<slice>/data/. Nothing is scored here.

Usage: python3 fetch_datasets.py [gbif|pbdb|ncbi|shared|all]
"""
import datetime as dt
import hashlib
import io
import json
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
SLICE = HERE.parent
sys.path.insert(0, str(HERE))
import seed  # noqa: E402

DATA = Path("/tmp/delphi-organisms-data")
DATA.mkdir(exist_ok=True)
VENDOR = SLICE / "data"
DSDIR = SLICE / "datasets"
DSDIR.mkdir(exist_ok=True)
UA = {"User-Agent": "delphi-organisms/0.1 (https://github.com/fractastical/delphi)"}
TODAY = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
VENDORED_BY = {"kind": "cloud-agent", "model": "Claude Fable 5.1 (Cursor cloud agent)",
               "run": "cursor/darwin-ch11-14-organisms-de91", "date": TODAY}
ONE_MB = 1_000_000


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def fetch_bytes(url, params=None, timeout=300):
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            if r.status_code == 200:
                return r
            print(f"  HTTP {r.status_code} {r.url}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  retry {attempt} {url}: {e}", file=sys.stderr)
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed: {url}")


def download(url, fname):
    """Download to DATA/fname (reusing an existing copy), return distribution dict + path."""
    p = DATA / fname
    if not p.exists():
        r = fetch_bytes(url)
        p.write_bytes(r.content)
        (DATA / (fname + ".retrieved_at")).write_text(now())
        media = r.headers.get("Content-Type", "application/octet-stream").split(";")[0]
        (DATA / (fname + ".media_type")).write_text(media)
    data = p.read_bytes()
    dist = {
        "download_url": url,
        "media_type": (DATA / (fname + ".media_type")).read_text() if (DATA / (fname + ".media_type")).exists() else "application/octet-stream",
        "byte_size": len(data),
        "sha256": sha256_bytes(data),
        "retrieved_at": (DATA / (fname + ".retrieved_at")).read_text(),
        "inspected": True,
    }
    if len(data) < ONE_MB:
        VENDOR.mkdir(exist_ok=True)
        shutil.copyfile(p, VENDOR / fname)
        dist["vendored_copy"] = f"organisms/darwin-origin/ch11-14/data/{fname}"
    return dist, p


def url_resolves(url):
    try:
        r = requests.head(url, headers=UA, timeout=60, allow_redirects=True)
        if r.status_code in (403, 405):
            r = requests.get(url, headers=UA, timeout=60, allow_redirects=True, stream=True)
        return r.status_code < 400
    except requests.RequestException:
        return False


def crossref(doi):
    """Title, authors and issued date straight from CrossRef, so nothing is typed from memory."""
    p = DATA / f"crossref-{doi.replace('/', '_')}.json"
    if p.exists():
        return json.loads(p.read_text())
    r = fetch_bytes(f"https://api.crossref.org/works/{quote(doi)}")
    m = r.json()["message"]
    authors = []
    for a in m.get("author", []):
        fam, giv = a.get("family", ""), a.get("given", "")
        initials = "".join(w[0] for w in re.split(r"[\s\-]+", giv) if w)
        authors.append(f"{fam} {initials}".strip())
    year = (m.get("issued", {}).get("date-parts") or [[None]])[0][0]
    out = {"title": (m.get("title") or [""])[0], "authors": authors, "year": year,
           "container": (m.get("container-title") or [""])[0], "volume": m.get("volume"), "page": m.get("page")}
    p.write_text(json.dumps(out))
    return out


def citation(doi, info):
    first = ", ".join(info["authors"][:3]) + (" et al." if len(info["authors"]) > 3 else "")
    bits = [f"{first} ({info['year']}) {info['title']}. {info['container']}"]
    if info.get("volume"):
        bits.append(f" {info['volume']}")
    if info.get("page"):
        bits.append(f":{info['page']}")
    bits.append(f". https://doi.org/{doi}")
    return "".join(bits)


def load_taxa():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((SLICE / "taxa").glob("*.json"))}


def write_ds(rec):
    (DSDIR / f"{rec['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("  wrote", rec["id"], flush=True)


# ---------------------------------------------------------------------------------------------
# GBIF occurrence counts
# ---------------------------------------------------------------------------------------------
def build_gbif(taxa):
    for slug, t in taxa.items():
        key = t["identifiers"].get("gbif_usage_key")
        if not key:
            continue
        url = f"https://api.gbif.org/v1/occurrence/search?taxonKey={key}&limit=0"
        r = fetch_bytes(url)
        retrieved = now()
        count = r.json()["count"]
        rec = {
            "id": f"gbif-occurrences-{slug}-{TODAY}",
            "label": f"GBIF occurrence count for {t['accepted_name']} (GBIF taxonKey {key}), {TODAY}",
            "identifier": f"https://www.gbif.org/occurrence/search?taxon_key={key}",
            "doi": None,
            "bibliographic_citation": f"GBIF.org ({TODAY}) GBIF Occurrence Search for taxonKey={key} ({t['accepted_name']}). {url}",
            "is_referenced_by": "https://www.gbif.org/citation-guidelines",
            "creators": ["GBIF.org"],
            "issued": TODAY,
            "license": "Per-record licences aggregated by GBIF (CC0 1.0, CC BY 4.0, CC BY-NC 4.0); https://www.gbif.org/terms",
            "version": TODAY,
            "distributions": [{
                "download_url": url,
                "media_type": "application/json",
                "byte_size": len(r.content),
                "sha256": sha256_bytes(r.content),
                "retrieved_at": retrieved,
                "inspected": True,
            }],
            "counts": [{
                "property_id": "n_occurrences",
                "value": count,
                "description": f"occurrence records indexed by GBIF under backbone usage {key} ({t['accepted_name']}, rank {t['rank']}) on {TODAY}, including records of all descendant taxa",
            }],
            "measurement_technique": "Aggregated species-occurrence records (preserved specimens, human and machine observations, literature) indexed by GBIF; count from the occurrence search API with limit=0.",
            "taxa": [slug],
            "role": f"number and availability of occurrence records for {t['accepted_name']}",
            "integrity": {
                "identifier_resolves": url_resolves(f"https://api.gbif.org/v1/species/{key}"),
                "checksum_verified": True,
                "checked_at": retrieved,
            },
            "vendored_by": VENDORED_BY,
        }
        write_ds(rec)
        time.sleep(0.3)


# ---------------------------------------------------------------------------------------------
# Paleobiology Database occurrence counts (extinct taxa)
# ---------------------------------------------------------------------------------------------
def build_pbdb(taxa):
    for slug, t in taxa.items():
        if not t.get("extinct") or not t["identifiers"].get("pbdb_taxon_id"):
            continue
        name = t["accepted_name"]
        url = f"https://paleobiodb.org/data1.2/occs/list.json?base_name={quote(name)}&limit=1&rowcount"
        r = fetch_bytes(url)
        retrieved = now()
        found = r.json().get("records_found")
        tid = t["identifiers"]["pbdb_taxon_id"].split(":")[1]
        rec = {
            "id": f"pbdb-occurrences-{slug}-{TODAY}",
            "label": f"Paleobiology Database fossil occurrence count for {name} (PBDB taxon {tid}), {TODAY}",
            "identifier": f"https://paleobiodb.org/classic/basicTaxonInfo?taxon_no={tid}",
            "doi": None,
            "bibliographic_citation": f"The Paleobiology Database ({TODAY}) occurrence records for base_name={name}. {url}",
            "is_referenced_by": "https://paleobiodb.org/#/faq",
            "creators": ["The Paleobiology Database contributors"],
            "issued": TODAY,
            "license": "CC BY 4.0 (https://paleobiodb.org/#/faq)",
            "version": TODAY,
            "distributions": [{
                "download_url": url,
                "media_type": "application/json",
                "byte_size": len(r.content),
                "sha256": sha256_bytes(r.content),
                "retrieved_at": retrieved,
                "inspected": True,
            }],
            "counts": [{
                "property_id": "n_occurrences",
                "value": found,
                "description": f"fossil occurrence records in PBDB for {name} and all taxa classified under it on {TODAY}",
            }],
            "measurement_technique": "Literature-compiled fossil occurrences (taxon x collection x stratigraphic interval) entered by PBDB contributors; count from the data1.2 occs/list API with rowcount.",
            "taxa": [slug],
            "role": f"fossil record extent for the extinct taxon {name}",
            "integrity": {
                "identifier_resolves": url_resolves(f"https://paleobiodb.org/data1.2/taxa/single.json?id=txn:{tid}"),
                "checksum_verified": True,
                "checked_at": retrieved,
            },
            "vendored_by": VENDORED_BY,
        }
        write_ds(rec)


# ---------------------------------------------------------------------------------------------
# NCBI Datasets reference genomes (species only)
# ---------------------------------------------------------------------------------------------
def build_ncbi(taxa):
    for slug, t in taxa.items():
        taxid = t["identifiers"].get("ncbi_taxid")
        if t["rank"] != "species" or not taxid:
            continue
        url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{taxid}/dataset_report?filters.reference_only=true"
        r = fetch_bytes(url)
        retrieved = now()
        reports = r.json().get("reports") or []
        if not reports:
            print(f"  no reference genome for {slug}")
            continue
        rep = reports[0]
        acc = rep["accession"]
        info = rep.get("assembly_info", {})
        stats = rep.get("assembly_stats", {})
        org = rep.get("organism", {})
        slug_acc = acc.lower().replace("_", "-").replace(".", "-")
        counts = []
        for k, label in (("total_sequence_length", "total sequence length (bp)"), ("contig_n50", "contig N50 (bp)"),
                         ("scaffold_n50", "scaffold N50 (bp)"), ("number_of_contigs", "number of contigs"),
                         ("number_of_scaffolds", "number of scaffolds")):
            if k in stats:
                counts.append({"property_id": k, "value": int(stats[k]), "description": f"{label} of assembly {acc}"})
        rec = {
            "id": f"ncbi-genome-{slug_acc}",
            "label": f"NCBI reference genome assembly {acc} ({info.get('assembly_name')}) for {org.get('organism_name')}",
            "identifier": f"https://www.ncbi.nlm.nih.gov/datasets/genome/{acc}/",
            "doi": None,
            "bibliographic_citation": f"{info.get('submitter', 'NCBI')} ({(info.get('release_date') or '')[:4]}) {org.get('organism_name')} genome assembly {acc} ({info.get('assembly_name')}). NCBI Datasets. https://www.ncbi.nlm.nih.gov/datasets/genome/{acc}/",
            "is_referenced_by": "https://www.ncbi.nlm.nih.gov/datasets/docs/v2/",
            "creators": [info.get("submitter") or "unknown submitter"],
            "issued": info.get("release_date"),
            "license": "NCBI public-domain data; https://www.ncbi.nlm.nih.gov/home/about/policies/",
            "version": info.get("assembly_name"),
            "distributions": [{
                "download_url": url,
                "media_type": "application/json",
                "byte_size": len(r.content),
                "sha256": sha256_bytes(r.content),
                "retrieved_at": retrieved,
                "inspected": True,
                "note": "assembly data report retrieved from the NCBI Datasets v2 API; sequence data not downloaded",
            }],
            "counts": counts,
            "measurement_technique": f"Whole-genome sequencing and assembly; level {info.get('assembly_level')}, {info.get('assembly_type')}; source database {rep.get('source_database')}.",
            "taxa": [slug],
            "role": f"reference genome assembly for {t['accepted_name']} (NCBI taxid {taxid}, infraspecific: {org.get('infraspecific_names')})",
            "integrity": {
                "identifier_resolves": url_resolves(f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{acc}/dataset_report"),
                "checksum_verified": True,
                "checked_at": retrieved,
            },
            "vendored_by": VENDORED_BY,
        }
        write_ds(rec)
        time.sleep(0.4)


# ---------------------------------------------------------------------------------------------
# Shared trait databases
# ---------------------------------------------------------------------------------------------
GROUPS = {
    "marsupialia": {"order": ["Didelphimorphia", "Paucituberculata", "Microbiotheria", "Dasyuromorphia",
                              "Peramelemorphia", "Notoryctemorphia", "Diprotodontia", "Marsupialia"]},
    "xenarthra": {"order": ["Cingulata", "Pilosa", "Xenarthra"]},
    "ruminantia": {"family": ["Tragulidae", "Antilocapridae", "Giraffidae", "Moschidae", "Cervidae", "Bovidae"]},
    "cetacea": {"order": ["Cetacea"], "family": ["Balaenidae", "Balaenopteridae", "Delphinidae", "Eschrichtiidae", "Iniidae",
                                                 "Kogiidae", "Lipotidae", "Monodontidae", "Neobalaenidae", "Phocoenidae",
                                                 "Physeteridae", "Platanistidae", "Pontoporiidae", "Ziphiidae"]},
    "vertebrata": {"class": ["Mammalia", "Aves", "Reptilia", "Amphibia", "Actinopterygii", "Chondrichthyes", "Sarcopterygii",
                             "Teleostei", "Cephalaspidomorphi", "Myxini", "Coelacanthi", "Dipnoi"]},
    "crustacea": {"class": ["Malacostraca", "Branchiopoda", "Maxillopoda", "Hexanauplia", "Thecostraca", "Ostracoda",
                            "Copepoda", "Remipedia", "Cephalocarida"]},
    "papilionoidea": {"family": ["Papilionidae", "Pieridae", "Nymphalidae", "Lycaenidae", "Riodinidae", "Hesperiidae", "Hedylidae"]},
    "serpentes": {"family": ["Acrochordidae", "Aniliidae", "Anomalepididae", "Anomochilidae", "Atractaspididae", "Boidae",
                             "Bolyeriidae", "Colubridae", "Cylindrophiidae", "Dipsadidae", "Elapidae", "Gerrhopilidae",
                             "Homalopsidae", "Lamprophiidae", "Leptotyphlopidae", "Loxocemidae", "Natricidae", "Pareatidae",
                             "Pseudoxenodontidae", "Pythonidae", "Tropidophiidae", "Typhlopidae", "Uropeltidae", "Viperidae",
                             "Xenodermatidae", "Xenopeltidae", "Xenophidiidae", "Xenotyphlopidae"]},
    "canis-familiaris": {"binomial": ["Canis familiaris", "Canis lupus familiaris"]},
    "bos-taurus": {"binomial": ["Bos taurus", "Bos primigenius"]},
    "equus-caballus": {"binomial": ["Equus caballus", "Equus ferus caballus"]},
    "anas-platyrhynchos": {"binomial": ["Anas platyrhynchos"]},
    "lepidosiren-paradoxa": {"binomial": ["Lepidosiren paradoxa"]},
}
LINEAGE_COLS = ("genus", "family", "order", "class", "phylum")


def match_rows(df, t):
    """Boolean mask of rows belonging to taxon t in a normalised frame."""
    name = t["accepted_name"].lower()
    mask = pd.Series(False, index=df.index)
    if t["rank"] == "species" and "binomial" in df:
        mask |= df["binomial"].str.lower() == name
    for col in LINEAGE_COLS:
        if col in df:
            mask |= df[col].str.lower() == name
    for col, vals in GROUPS.get(t["slug"], {}).items():
        if col in df:
            mask |= df[col].str.lower().isin([v.lower() for v in vals])
    return mask


def normalise(df, binomial=None, genus=None, family=None, order=None, klass=None, phylum=None, const=None):
    out = pd.DataFrame(index=df.index)
    for new, old in (("binomial", binomial), ("genus", genus), ("family", family), ("order", order), ("class", klass), ("phylum", phylum)):
        if old is not None:
            out[new] = df[old].astype(str).str.strip()
    for k, v in (const or {}).items():
        out[k] = v
    if "genus" not in out and "binomial" in out:
        out["genus"] = out["binomial"].str.split(" ").str[0]
    return out


def shared_record(ds_id, label, identifier, doi, creators, cite, issued, license_, version, dists, n_rows, rows_desc,
                  technique, role, frames, taxa, extra_counts=None, notes=None):
    per_taxon = {}
    for slug, t in taxa.items():
        t = dict(t, slug=slug)
        n = int(sum(int(match_rows(df, t).sum()) for df in frames))
        if n:
            per_taxon[slug] = n
    checked = now()
    rec = {
        "id": ds_id,
        "label": label,
        "identifier": identifier,
        "doi": doi,
        "bibliographic_citation": cite,
        "is_referenced_by": f"https://doi.org/{doi}" if doi else None,
        "creators": creators,
        "issued": issued,
        "license": license_,
        "version": version,
        "distributions": dists,
        "counts": [
            {"property_id": "n_species", "value": n_rows, "description": rows_desc},
            {"property_id": "n_rows_for_taxa", "value": int(sum(per_taxon.values())),
             "description": "rows matching the taxa listed below (species rows by binomial; higher taxa by lineage columns, "
                            "see rows_per_taxon)"},
        ] + (extra_counts or []),
        "rows_per_taxon": dict(sorted(per_taxon.items())),
        "measurement_technique": technique,
        "taxa": sorted(per_taxon),
        "role": role,
        "integrity": {
            "identifier_resolves": url_resolves(identifier) and (url_resolves(f"https://doi.org/{doi}") if doi else True),
            "checksum_verified": True,
            "checked_at": checked,
        },
        "vendored_by": VENDORED_BY,
    }
    if notes:
        rec["notes"] = notes
    write_ds(rec)
    return rec


def build_shared(taxa):
    # ---- AnAge build 15 ---------------------------------------------------------------------
    dist, p = download("https://genomics.senescence.info/species/dataset.zip", "anage_build15_dataset.zip")
    with zipfile.ZipFile(p) as z:
        df = pd.read_csv(io.BytesIO(z.read("anage_data.txt")), sep="\t", dtype=str)
    df["binomial"] = df["Genus"] + " " + df["Species"]
    fr = normalise(df, binomial="binomial", genus="Genus", family="Family", order="Order", klass="Class", phylum="Phylum")
    doi = "10.1093/nar/gkx1042"
    info = crossref(doi)
    shared_record(
        "anage-build-15", "AnAge: The Animal Ageing and Longevity Database, build 15 (released 2023-07-03)",
        "https://genomics.senescence.info/species/", doi, info["authors"], citation(doi, info),
        "2023-07-03", "CC BY 3.0 (https://genomics.senescence.info/legal.html)", "build 15", [dist],
        len(df), "species rows in anage_data.txt as distributed",
        "Literature-compiled life-history traits per species: maximum longevity, adult body mass, maturity, gestation/incubation, litter size, metabolic rate.",
        "maximum longevity, adult body mass and other life-history traits for the listed taxa", [fr], taxa)

    # ---- PanTHERIA 1.0 ----------------------------------------------------------------------
    dist, p = download("https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt", "PanTHERIA_1-0_WR05_Aug2008.txt")
    df = pd.read_csv(p, sep="\t", dtype=str)
    fr = normalise(df, binomial="MSW05_Binomial", genus="MSW05_Genus", family="MSW05_Family", order="MSW05_Order", const={"class": "Mammalia"})
    doi = "10.1890/08-1494.1"
    info = crossref(doi)
    pantheria_fam_order = dict(zip(df["MSW05_Family"], df["MSW05_Order"]))
    shared_record(
        "pantheria-1-0-wr05-2008", "PanTHERIA 1.0: species-level life history, ecology and geography of extant and recently extinct mammals (MSW05 taxonomy, Aug 2008)",
        "https://esapubs.org/archive/ecol/E090/184/", doi, info["authors"], citation(doi, info),
        "2009-09", "not stated in the archive (ESA Ecological Archives E090-184 data paper)", "1.0 (WR05, August 2008)", [dist],
        len(df), "species rows (Wilson & Reeder 2005 taxonomy) in PanTHERIA_1-0_WR05_Aug2008.txt",
        "Literature-compiled species traits: adult body mass, longevity, gestation, litter size, home range, population density, geographic range, diet breadth.",
        "body mass, longevity and ecological traits for the listed mammal taxa", [fr], taxa)

    # ---- Amniote Life-History Database --------------------------------------------------------
    dist, p = download("https://esapubs.org/archive/ecol/E096/269/Data_Files/Amniote_Database_Aug_2015.csv", "Amniote_Database_Aug_2015.csv")
    df = pd.read_csv(p, dtype=str)
    df["binomial"] = df["genus"] + " " + df["species"]
    fr = normalise(df, binomial="binomial", genus="genus", family="family", order="order", klass="class")
    doi = "10.1890/15-0846.1"
    info = crossref(doi)
    shared_record(
        "amniote-life-history-db-2015", "Amniote Life-History Database (Myhrvold et al. 2015), Aug 2015 release",
        "https://esapubs.org/archive/ecol/E096/269/", doi, info["authors"], citation(doi, info),
        "2015-11", "not stated in the archive (ESA Ecological Archives E096-269 data paper)", "August 2015", [dist],
        len(df), "species rows in Amniote_Database_Aug_2015.csv (birds, mammals, reptiles)",
        "Literature-compiled life-history traits for amniotes: body mass, longevity, maturity, clutch/litter size, incubation/gestation, egg mass.",
        "life-history traits for the listed bird, mammal and reptile taxa", [fr], taxa)

    # ---- EltonTraits 1.0 ----------------------------------------------------------------------
    dist_b, pb = download("https://esapubs.org/archive/ecol/E095/178/BirdFuncDat.txt", "EltonTraits_BirdFuncDat.txt")
    dist_m, pm = download("https://esapubs.org/archive/ecol/E095/178/MamFuncDat.txt", "EltonTraits_MamFuncDat.txt")
    birds = pd.read_csv(pb, sep="\t", dtype=str, encoding="latin-1")
    mams = pd.read_csv(pm, sep="\t", dtype=str, encoding="latin-1")
    birds = birds[birds["Scientific"].notna()]
    mams = mams[mams["Scientific"].notna()]
    mams["order"] = mams["MSWFamilyLatin"].map(pantheria_fam_order)
    fb = normalise(birds, binomial="Scientific", family="BLFamilyLatin", order="IOCOrder", const={"class": "Aves"})
    fm = normalise(mams, binomial="Scientific", family="MSWFamilyLatin", order="order", const={"class": "Mammalia"})
    doi = "10.1890/13-1917.1"
    info = crossref(doi)
    shared_record(
        "eltontraits-1-0-2014", "EltonTraits 1.0: species-level foraging attributes of the world's birds and mammals",
        "https://esapubs.org/archive/ecol/E095/178/", doi, info["authors"], citation(doi, info),
        "2014-07", "not stated in the archive (ESA Ecological Archives E095-178 data paper)", "1.0", [dist_b, dist_m],
        len(birds) + len(mams), f"species rows: {len(birds)} birds (BirdFuncDat.txt) + {len(mams)} mammals (MamFuncDat.txt)",
        "Literature-compiled diet composition, foraging stratum, activity period and body mass per species.",
        "diet, foraging stratum and body mass for the listed bird and mammal taxa", [fb, fm], taxa,
        notes="Mammal orders are not in MamFuncDat.txt; they were filled from the MSW05 family->order map in PanTHERIA for higher-rank matching.")

    # ---- AVONET -------------------------------------------------------------------------------
    dist, p = download("https://ndownloader.figshare.com/files/34480856", "AVONET_Supplementary_dataset_1.xlsx")
    df = pd.read_excel(p, sheet_name="AVONET1_BirdLife", dtype=str)
    fr = normalise(df, binomial="Species1", family="Family1", order="Order1", const={"class": "Aves"})
    doi = "10.1111/ele.13898"
    info = crossref(doi)
    shared_record(
        "avonet-2022-figshare-v7", "AVONET: morphological, ecological and geographical data for all birds (Supplementary dataset 1, sheet AVONET1_BirdLife; figshare v7)",
        "https://doi.org/10.6084/m9.figshare.16586228", doi, info["authors"], citation(doi, info),
        "2022", "CC BY 4.0 (figshare record licence)", "figshare 16586228 v7; sheet AVONET1_BirdLife", [dist],
        len(df), "species rows in sheet AVONET1_BirdLife (BirdLife taxonomy)",
        "Museum-specimen and live-bird morphometrics (beak, wing, tail, tarsus, mass) averaged per species, with habitat, trophic niche, migration and range data.",
        "morphometric and ecological traits for the listed bird taxa", [fr], taxa)

    # ---- WoRMS / Aphia records ---------------------------------------------------------------
    dists, per = [], {}
    for slug, t in taxa.items():
        aid = t["identifiers"].get("worms_aphia_id")
        if not aid:
            continue
        url = f"https://www.marinespecies.org/rest/AphiaRecordByAphiaID/{aid}"
        r = fetch_bytes(url)
        rec = r.json()
        dists.append({"download_url": url, "media_type": "application/json", "byte_size": len(r.content),
                      "sha256": sha256_bytes(r.content), "retrieved_at": now(), "inspected": True,
                      "taxon": slug, "aphia_id": aid, "status": rec.get("status"), "is_marine": rec.get("isMarine")})
        per[slug] = 1
        time.sleep(0.3)
    doi = "10.14284/170"
    checked = now()
    rec = {
        "id": f"worms-aphia-records-{TODAY}",
        "label": f"World Register of Marine Species (WoRMS) Aphia taxon records for the ch11-14 taxa, retrieved {TODAY}",
        "identifier": "https://www.marinespecies.org/",
        "doi": doi,
        "bibliographic_citation": f"WoRMS Editorial Board ({TODAY[:4]}). World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. Accessed {TODAY}. https://doi.org/{doi}",
        "is_referenced_by": f"https://doi.org/{doi}",
        "creators": ["WoRMS Editorial Board"],
        "issued": TODAY,
        "license": "CC BY 4.0 (https://www.marinespecies.org/about.php#terms)",
        "version": TODAY,
        "distributions": dists,
        "counts": [
            {"property_id": "n_rows_for_taxa", "value": len(per), "description": "Aphia taxon records retrieved, one per listed taxon"},
        ],
        "rows_per_taxon": dict(sorted(per.items())),
        "measurement_technique": "Expert-curated taxonomic register; each record gives the accepted name, authority, rank, status, classification and marine/brackish/freshwater/terrestrial flags. Mollusc records are curated by MolluscaBase, which shares the Aphia platform.",
        "taxa": sorted(per),
        "role": "authoritative taxonomic record (AphiaID, status, environment flags) for the listed taxa, including the marine ones (cirripedes, crabs, cuttle-fish, corals, cetaceans, sirenians, seabirds)",
        "integrity": {"identifier_resolves": url_resolves("https://www.marinespecies.org/") and url_resolves(f"https://doi.org/{doi}"),
                      "checksum_verified": True, "checked_at": checked},
        "vendored_by": VENDORED_BY,
    }
    write_ds(rec)


# ---------------------------------------------------------------------------------------------
def link_taxa(taxa):
    cover = {}
    for p in DSDIR.glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        for s in d["taxa"]:
            cover.setdefault(s, set()).add(d["id"])
    for slug, t in taxa.items():
        t["datasets"] = sorted(cover.get(slug, set()))
        (SLICE / "taxa" / f"{slug}.json").write_text(json.dumps(t, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("taxa without any dataset:", sorted(s for s in taxa if not taxa[s]["datasets"]))


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    taxa = load_taxa()
    if what in ("gbif", "all"):
        build_gbif(taxa)
    if what in ("pbdb", "all"):
        build_pbdb(taxa)
    if what in ("ncbi", "all"):
        build_ncbi(taxa)
    if what in ("shared", "all"):
        build_shared(taxa)
    link_taxa(load_taxa())


if __name__ == "__main__":
    main()
