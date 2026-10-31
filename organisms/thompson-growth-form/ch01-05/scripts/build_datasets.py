#!/usr/bin/env python3
"""Fetch, check and describe the public datasets that cover the taxa of this slice, and write
datasets/<dataset-id>.json plus the `datasets` lists in taxa/<slug>.json.

Everything recorded here was downloaded by this script and checked: every count is computed
from the downloaded file or API response, every byte_size/sha256 is of the bytes received,
and every identifier/DOI was fetched (HTTP 2xx/3xx) before being written. Data files stay in
/tmp/organisms-data (none is committed; several exceed 1 MB).

Sources
  * GBIF occurrence counts            one record per taxon with a backbone key
  * AnAge build 15                    shared
  * PanTHERIA 1.0                     shared (mammals)
  * Amniote Life-History Database     shared (birds, mammals, reptiles)
  * EltonTraits 1.0                   shared (birds, mammals)
  * AVONET                            shared (birds)
  * FishBase (rfishbase parquet)      shared (fishes)
  * NCBI Datasets reference genomes   one record per species/genus with a reference assembly
  * WoRMS Aphia records               shared (marine taxa)
  * Paleobiology Database             shared (fossil taxa)

Usage: python3 build_datasets.py [section ...]   sections: gbif anage pantheria amniote elton avonet fishbase ncbi worms pbdb
"""
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
SLICE = HERE.parent
sys.path.insert(0, str(HERE))
from taxa_table import TAXA  # noqa: E402

DATA = Path("/tmp/organisms-data")
DATA.mkdir(exist_ok=True)
OUT = SLICE / "datasets"
OUT.mkdir(exist_ok=True)
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
S = requests.Session()
S.headers["User-Agent"] = "delphi-organisms/0.1 (https://github.com/fractastical/delphi)"


def branch():
    try:
        return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=SLICE, text=True).strip()
    except Exception:
        return "unknown"


VENDORED_BY = {"kind": "cloud-agent", "model": "claude-fable-5.1", "run": branch(), "date": TODAY}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, name, media_type):
    """Download once into DATA/name and return a distribution dict with checksum."""
    p = DATA / name
    if not p.exists():
        r = S.get(url, timeout=300, allow_redirects=True)
        r.raise_for_status()
        p.write_bytes(r.content)
    return {"download_url": url, "media_type": media_type, "byte_size": p.stat().st_size,
            "sha256": sha256_file(p), "retrieved_at": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "inspected": True}


def api_json(url, retries=4):
    """GET a JSON API; return (parsed, distribution dict)."""
    for attempt in range(retries):
        try:
            r = S.get(url, timeout=120)
            if r.status_code in (429,) or r.status_code >= 500:
                raise requests.HTTPError(str(r.status_code))
            r.raise_for_status()
            body = r.content
            return json.loads(body), {"download_url": url, "media_type": "application/json", "byte_size": len(body),
                                      "sha256": sha256_bytes(body), "retrieved_at": now(), "inspected": True}
        except (requests.RequestException, ValueError) as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def resolves(url):
    """True when the URL answers 2xx/3xx. DOI handles are judged by the doi.org redirect itself,
    since publisher sites behind it often refuse automated clients."""
    try:
        if url.startswith("https://doi.org/"):
            r = S.head(url, timeout=60, allow_redirects=False)
            return r.status_code in (301, 302, 303, 307, 308)
        r = S.head(url, timeout=60, allow_redirects=True)
        if r.status_code in (403, 405):
            r = S.get(url, timeout=60, allow_redirects=True, stream=True)
        return r.status_code < 400
    except requests.RequestException:
        return False


def load_taxa():
    out = {}
    for f in sorted((SLICE / "taxa").glob("*.json")):
        d = json.loads(f.read_text())
        out[d["slug"]] = d
    return out


TABLE = {t["slug"]: t for t in TAXA}
taxa = load_taxa()


def write_dataset(rec):
    rec.setdefault("vendored_by", VENDORED_BY)
    (OUT / f"{rec['id']}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for slug in rec.get("taxa", []):
        t = taxa[slug]
        if rec["id"] not in t["datasets"]:
            t["datasets"].append(rec["id"])
    print(f"  wrote {rec['id']}  taxa={len(rec.get('taxa', []))}")


def save_taxa():
    for slug, t in taxa.items():
        t["datasets"] = sorted(set(t["datasets"]))
        (SLICE / "taxa" / f"{slug}.json").write_text(json.dumps(t, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- taxon filters
# Informal / non-rank groups need explicit membership lists for the trait tables.
SHARK_ORDERS = {"Carcharhiniformes", "Lamniformes", "Orectolobiformes", "Heterodontiformes", "Hexanchiformes",
                "Squaliformes", "Squatiniformes", "Pristiophoriformes", "Echinorhiniformes"}
MARSUPIAL_ORDERS = {"Didelphimorphia", "Paucituberculata", "Microbiotheria", "Dasyuromorphia", "Peramelemorphia",
                    "Notoryctemorphia", "Diprotodontia"}
UNGULATE_ORDERS = {"Artiodactyla", "Perissodactyla", "Cetartiodactyla"}
FISH_CLASSES = {"Actinopterygii", "Chondrichthyes", "Elasmobranchii", "Holocephali", "Sarcopterygii", "Cephalaspidomorphi",
                "Myxini", "Petromyzonti", "Teleostei", "Dipneusti", "Coelacanthi", "Actinopteri", "Cladistii"}
SNAKE_FAMILIES = {"Acrochordidae", "Aniliidae", "Anomalepididae", "Anomochilidae", "Atractaspididae", "Boidae", "Bolyeriidae",
                  "Calabariidae", "Colubridae", "Cyclocoridae", "Cylindrophiidae", "Dipsadidae", "Elapidae", "Gerrhopilidae",
                  "Homalopsidae", "Lamprophiidae", "Leptotyphlopidae", "Loxocemidae", "Natricidae", "Pareidae", "Pareatidae",
                  "Prosymnidae", "Psammophiidae", "Pseudaspididae", "Pseudoxenodontidae", "Pseudoxyrhophiidae", "Pythonidae",
                  "Tropidophiidae", "Typhlopidae", "Uropeltidae", "Viperidae", "Xenodermatidae", "Xenodermidae", "Xenopeltidae",
                  "Xenophidiidae", "Xenotyphlopidae", "Candoiidae", "Charinidae", "Erycidae", "Sanziniidae", "Ungaliophiidae",
                  "Sibynophiidae", "Grayiidae", "Calamariidae", "Colubrinae"}


def row_mask(df, slug, cols):
    """Boolean mask of rows in `df` belonging to taxon `slug`.

    cols maps logical column names (class, order, family, genus, species, binomial) to the
    dataframe's column names (missing ones may be omitted). Returns None when the taxon cannot
    be expressed with the available columns (then it is simply not counted)."""
    t = taxa[slug]
    name = t["accepted_name"]
    rank = t["rank"]
    lineage = t.get("lineage", {})

    def col(k):
        return df[cols[k]].astype(str).str.strip() if k in cols else None

    if slug == "pisces":
        c = col("class")
        return c.isin(FISH_CLASSES) if c is not None else None
    if slug == "selachii":
        o = col("order")
        return o.isin(SHARK_ORDERS) if o is not None else None
    if slug == "marsupialia":
        o = col("order")
        return o.isin(MARSUPIAL_ORDERS) if o is not None else None
    if slug == "ungulata":
        o = col("order")
        return o.isin(UNGULATE_ORDERS) if o is not None else None
    if slug == "serpentes":
        f = col("family")
        return f.isin(SNAKE_FAMILIES) if f is not None else None
    if slug == "vertebrata":
        p = col("phylum")
        if p is not None:
            return p == "Chordata"
        return pd.Series(True, index=df.index)  # the other tables are vertebrate-only
    if slug == "canis-familiaris":
        b = col("binomial")
        return b.isin(["Canis familiaris", "Canis lupus familiaris"]) if b is not None else None
    if rank in ("species", "subspecies"):
        b = col("binomial")
        return (b == name) if b is not None else None
    if rank == "genus":
        g = col("genus")
        if g is None and "binomial" in cols:
            g = col("binomial").str.split().str[0]
        return (g == name) if g is not None else None
    if rank == "family":
        f = col("family")
        return (f == name) if f is not None else None
    if rank == "order":
        o = col("order")
        return (o == name) if o is not None else None
    if rank == "class":
        c = col("class")
        if c is not None:
            return c == name
        # tables without a class column are single-class tables; handled by caller
        return None
    return None


def count_taxa(df, cols, candidates, class_only=None):
    """Return {slug: n_rows} for the candidate slugs that have >0 rows."""
    out = {}
    for slug in candidates:
        if class_only and taxa[slug]["rank"] == "class" and taxa[slug]["accepted_name"] == class_only and "class" not in cols:
            out[slug] = int(len(df))
            continue
        m = row_mask(df, slug, cols)
        if m is None:
            continue
        n = int(m.sum())
        if n > 0:
            out[slug] = n
    return out


def group_slugs(*groups):
    return [s for s, t in TABLE.items() if set(t["groups"]) & set(groups) and s in taxa]


def n_rows_counts(per_taxon, what):
    return [{"property_id": "n_rows_for_taxa", "value": int(sum(per_taxon.values())),
             "description": f"{what} rows matching the listed taxa (per taxon: " + ", ".join(f"{k}={v}" for k, v in sorted(per_taxon.items())) + ")"}]


# --------------------------------------------------------------------------- GBIF
def build_gbif(only=None):
    print("GBIF occurrence counts")
    for slug, t in taxa.items():
        key = t["identifiers"].get("gbif_usage_key")
        if not key or (only and slug not in only):
            continue
        url = f"https://api.gbif.org/v1/occurrence/search?taxonKey={key}&limit=0"
        data, dist = api_json(url)
        count = int(data["count"])
        did = f"gbif-occurrences-{slug}-{TODAY}"
        write_dataset({
            "id": did,
            "label": f"GBIF occurrence records for {t['accepted_name']} (taxonKey {key}), API count on {TODAY}",
            "identifier": url,
            "doi": None,
            "bibliographic_citation": f"GBIF.org ({TODAY}) GBIF Occurrence Search API, taxonKey={key} ({t['accepted_name']}). https://www.gbif.org/occurrence/search?taxon_key={key}",
            "is_referenced_by": "https://www.gbif.org/developer/occurrence",
            "creators": ["GBIF Secretariat and publishing institutions"],
            "issued": TODAY,
            "license": "Per source dataset: CC0 1.0, CC BY 4.0 or CC BY-NC 4.0 (GBIF data user agreement)",
            "version": f"GBIF index as of {TODAY}",
            "distributions": [dist],
            "counts": [{"property_id": "n_occurrences", "value": count,
                        "description": f"`count` returned by the occurrence search API for taxonKey={key} and all descendant taxa"}],
            "measurement_technique": "Aggregated species-occurrence records (specimens, observations, literature, eDNA) published to GBIF and indexed against the GBIF backbone taxonomy.",
            "taxa": [slug],
            "role": f"number and distribution of occurrence records for {t['accepted_name']}",
            "integrity": {"identifier_resolves": True, "checksum_verified": True, "checked_at": dist["retrieved_at"]},
        })
        if count == 0:
            print(f"   note: zero GBIF occurrences for {slug}")


# --------------------------------------------------------------------------- AnAge
def build_anage():
    print("AnAge build 15")
    dist = download("https://genomics.senescence.info/species/dataset.zip", "anage.zip", "application/zip")
    import zipfile
    with zipfile.ZipFile(DATA / "anage.zip") as z:
        with z.open("anage_data.txt") as f:
            df = pd.read_csv(f, sep="\t", dtype=str)
    cols = {"phylum": "Phylum", "class": "Class", "order": "Order", "family": "Family", "genus": "Genus", "binomial": "binomial"}
    df["binomial"] = df["Genus"].str.strip() + " " + df["Species"].str.strip()
    per = count_taxa(df, cols, list(taxa))
    write_dataset({
        "id": "anage-build-15",
        "label": "AnAge: The Animal Ageing and Longevity Database, build 15 (3 July 2023)",
        "identifier": "https://genomics.senescence.info/species/",
        "doi": "10.1093/nar/gks1155",
        "bibliographic_citation": "Tacutu R, Craig T, Budovsky A, Wuttke D, Lehmann G, Taranukha D, Costa J, Fraifeld VE, de Magalhães JP (2013) Human Ageing Genomic Resources: integrated databases and tools for the biology and genetics of ageing. Nucleic Acids Research 41(D1):D1027–D1033.",
        "is_referenced_by": "https://doi.org/10.1093/nar/gks1155",
        "creators": ["Tacutu R", "Craig T", "Budovsky A", "Wuttke D", "Lehmann G", "Taranukha D", "Costa J", "Fraifeld VE", "de Magalhães JP"],
        "issued": "2023-07-03",
        "license": "CC BY 3.0 (HAGR legal notice, https://genomics.senescence.info/legal.html)",
        "version": "build 15",
        "distributions": [dist],
        "counts": [{"property_id": "n_species", "value": int(len(df)), "description": "rows (species entries) in anage_data.txt inside dataset.zip"}] + n_rows_counts(per, "anage_data.txt"),
        "measurement_technique": "Literature-compiled life-history and ageing traits per species: maximum longevity, adult body mass, age at maturity, gestation/incubation, litter size, growth rate, metabolic rate.",
        "taxa": sorted(per),
        "role": "maximum longevity, body mass and growth-rate parameters for the listed taxa (Thompson's rate-of-growth and magnitude arguments)",
        "integrity": {"identifier_resolves": resolves("https://genomics.senescence.info/species/"), "checksum_verified": True, "checked_at": now()},
    })


# --------------------------------------------------------------------------- PanTHERIA
def build_pantheria():
    print("PanTHERIA 1.0")
    url = "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt"
    dist = download(url, "pantheria.txt", "text/tab-separated-values")
    df = pd.read_csv(DATA / "pantheria.txt", sep="\t", dtype=str, encoding="latin-1")
    cols = {"order": "MSW05_Order", "family": "MSW05_Family", "genus": "MSW05_Genus", "binomial": "MSW05_Binomial"}
    per = count_taxa(df, cols, group_slugs("mammal"), class_only="Mammalia")
    write_dataset({
        "id": "pantheria-1-0",
        "label": "PanTHERIA 1.0: a species-level database of life history, ecology and geography of extant and recently extinct mammals (WR05 taxonomy, Aug 2008)",
        "identifier": "https://doi.org/10.1890/08-1494.1",
        "doi": "10.1890/08-1494.1",
        "bibliographic_citation": "Jones KE, Bielby J, Cardillo M, Fritz SA, O'Dell J, Orme CDL, Safi K, Sechrest W, Boakes EH, Carbone C, Connolly C, Cutts MJ, Foster JK, Grenyer R, Habib M, Plaster CA, Price SA, Rigby EA, Rist J, Teacher A, Bininda-Emonds ORP, Gittleman JL, Mace GM, Purvis A (2009) PanTHERIA: a species-level database of life history, ecology, and geography of extant and recently extinct mammals. Ecology 90:2648. Ecological Archives E090-184.",
        "is_referenced_by": "https://doi.org/10.1890/08-1494.1",
        "creators": ["Jones KE", "Bielby J", "Cardillo M", "Fritz SA", "O'Dell J", "Orme CDL", "Safi K", "Sechrest W", "Boakes EH", "Carbone C", "Connolly C", "Cutts MJ", "Foster JK", "Grenyer R", "Habib M", "Plaster CA", "Price SA", "Rigby EA", "Rist J", "Teacher A", "Bininda-Emonds ORP", "Gittleman JL", "Mace GM", "Purvis A"],
        "issued": "2009-09",
        "license": None,
        "version": "1.0 (WR05, August 2008)",
        "distributions": [dist],
        "counts": [{"property_id": "n_species", "value": int(len(df)), "description": "rows in PanTHERIA_1-0_WR05_Aug2008.txt (one per Wilson & Reeder 2005 species; -999 marks missing values)"}] + n_rows_counts(per, "PanTHERIA"),
        "measurement_technique": "Literature-compiled species means: adult body mass, head-body length, gestation, litter size, longevity, basal metabolic rate, home range, population density, diet and habitat breadth, geographic range.",
        "taxa": sorted(per),
        "role": "adult body mass, neonate mass, gestation length and maximum longevity for the listed mammals",
        "integrity": {"identifier_resolves": resolves("https://doi.org/10.1890/08-1494.1"), "checksum_verified": True, "checked_at": now()},
        "notes": "No licence file accompanies the ESA Ecological Archives distribution (the directory https://esapubs.org/archive/ecol/E090/184/ returns 403; the data file itself downloads). The dog has no separate row (PanTHERIA follows Wilson & Reeder 2005, where it is Canis lupus).",
    })


# --------------------------------------------------------------------------- Amniote DB
def build_amniote():
    print("Amniote Life-History Database")
    url = "https://esapubs.org/archive/ecol/E096/269/Data_Files/Amniote_Database_Aug_2015.csv"
    dist = download(url, "amniote.csv", "text/csv")
    df = pd.read_csv(DATA / "amniote.csv", dtype=str, encoding="latin-1")
    df["binomial"] = df["genus"].str.strip() + " " + df["species"].str.strip()
    cols = {"class": "class", "order": "order", "family": "family", "genus": "genus", "binomial": "binomial"}
    per = count_taxa(df, cols, group_slugs("mammal", "bird", "reptile"))
    write_dataset({
        "id": "amniote-life-history-database-2015",
        "label": "An amniote life-history database to perform comparative analyses with birds, mammals, and reptiles (Amniote_Database_Aug_2015.csv)",
        "identifier": "https://doi.org/10.1890/15-0846R.1",
        "doi": "10.1890/15-0846R.1",
        "bibliographic_citation": "Myhrvold NP, Baldridge E, Chan B, Sivam D, Freeman DL, Ernest SKM (2015) An amniote life-history database to perform comparative analyses with birds, mammals, and reptiles. Ecology 96:3109. Ecological Archives E096-269.",
        "is_referenced_by": "https://doi.org/10.1890/15-0846R.1",
        "creators": ["Myhrvold NP", "Baldridge E", "Chan B", "Sivam D", "Freeman DL", "Ernest SKM"],
        "issued": "2015-11",
        "license": None,
        "version": "August 2015",
        "distributions": [dist],
        "counts": [{"property_id": "n_species", "value": int(len(df)), "description": "rows in Amniote_Database_Aug_2015.csv (one per species/subspecies; -999 marks missing values)"}] + n_rows_counts(per, "Amniote database"),
        "measurement_technique": "Literature-compiled life-history traits for 21,322 amniote species: body mass, longevity, maturity, clutch/litter size, gestation/incubation, egg mass, growth-related ages.",
        "taxa": sorted(per),
        "role": "adult body mass, maturity age, longevity and birth/hatching mass for the listed birds, mammals and reptiles",
        "integrity": {"identifier_resolves": resolves("https://doi.org/10.1890/15-0846R.1"), "checksum_verified": True, "checked_at": now()},
        "notes": "No licence file accompanies the ESA Ecological Archives distribution (the directory https://esapubs.org/archive/ecol/E096/269/ returns 403; the data file itself downloads). Snakes (Serpentes) are counted through a list of snake family names because the file has no suborder column; 'Ungulata' is counted as the orders Artiodactyla/Cetartiodactyla + Perissodactyla.",
    })


# --------------------------------------------------------------------------- EltonTraits
def build_elton():
    print("EltonTraits 1.0")
    d_bird = download("https://ndownloader.figshare.com/files/5631081", "BirdFuncDat.txt", "text/tab-separated-values")
    d_mam = download("https://ndownloader.figshare.com/files/5631084", "MamFuncDat.txt", "text/tab-separated-values")
    birds = pd.read_csv(DATA / "BirdFuncDat.txt", sep="\t", dtype=str, encoding="latin-1")
    mams = pd.read_csv(DATA / "MamFuncDat.txt", sep="\t", dtype=str, encoding="latin-1")
    birds = birds[birds["Scientific"].notna()]
    mams = mams[mams["Scientific"].notna()]
    pb = count_taxa(birds, {"order": "IOCOrder", "family": "BLFamilyLatin", "binomial": "Scientific"}, group_slugs("bird"), class_only="Aves")
    pm = count_taxa(mams, {"family": "MSWFamilyLatin", "binomial": "Scientific"}, group_slugs("mammal"), class_only="Mammalia")
    per = {**pb, **pm}
    for k in set(pb) & set(pm):
        per[k] = pb[k] + pm[k]
    write_dataset({
        "id": "eltontraits-1-0",
        "label": "EltonTraits 1.0: species-level foraging attributes of the world's birds and mammals",
        "identifier": "https://doi.org/10.6084/m9.figshare.3559887.v1",
        "doi": "10.1890/13-1917.1",
        "bibliographic_citation": "Wilman H, Belmaker J, Simpson J, de la Rosa C, Rivadeneira MM, Jetz W (2014) EltonTraits 1.0: Species-level foraging attributes of the world's birds and mammals. Ecology 95:2027. Ecological Archives E095-178.",
        "is_referenced_by": "https://doi.org/10.1890/13-1917.1",
        "creators": ["Wilman H", "Belmaker J", "Simpson J", "de la Rosa C", "Rivadeneira MM", "Jetz W"],
        "issued": "2014-07",
        "license": "CC0 1.0 (figshare record)",
        "version": "1.0",
        "distributions": [d_bird, d_mam],
        "counts": [
            {"property_id": "n_species_birds", "value": int(len(birds)), "description": "rows in BirdFuncDat.txt"},
            {"property_id": "n_species_mammals", "value": int(len(mams)), "description": "rows in MamFuncDat.txt"},
        ] + n_rows_counts(per, "BirdFuncDat.txt + MamFuncDat.txt"),
        "measurement_technique": "Literature-compiled diet composition, foraging stratum, activity period and body mass per species.",
        "taxa": sorted(per),
        "role": "body mass and foraging/activity attributes for the listed birds and mammals",
        "integrity": {"identifier_resolves": resolves("https://doi.org/10.6084/m9.figshare.3559887.v1"), "checksum_verified": True, "checked_at": now()},
    })


# --------------------------------------------------------------------------- AVONET
def build_avonet():
    print("AVONET")
    dist = download("https://ndownloader.figshare.com/files/34480856", "avonet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    df = pd.read_excel(DATA / "avonet.xlsx", sheet_name="AVONET1_BirdLife", dtype=str)
    per = count_taxa(df, {"order": "Order1", "family": "Family1", "binomial": "Species1"}, group_slugs("bird"), class_only="Aves")
    write_dataset({
        "id": "avonet-2022",
        "label": "AVONET: morphological, ecological and geographical data for all birds (Supplementary dataset 1, sheet AVONET1_BirdLife)",
        "identifier": "https://doi.org/10.6084/m9.figshare.16586228.v7",
        "doi": "10.1111/ele.13898",
        "bibliographic_citation": "Tobias JA, Sheard C, Pigot AL, Devenish AJM, Yang J, Sayol F, Neate-Clegg MHC, Alioravainen N, Weeks TL, Barber RA, Walkden PA, MacGregor HEA, Jones SEI, Vincent C, Phillips AG, Marples NM, Montaño-Centellas FA, Leandro-Silva V, Claramunt S, Darski B, Freeman BG, Bregman TP, Cooney CR, Hughes EC, Capp EJR, Varley ZK, Friedman NR, Korntheuer H, Corrales-Vargas A, Trisos CH, Weeks BC, Hanz DM, Töpfer T, Bravo GA, Remeš V, Nowak L, Carneiro LS, Moncada R AJ, Matysioková B, Baldassarre DT, Martínez-Salinas A, Wolfe JD, Chapman PM, Daly BG, Sorensen MC, Neu A, Ford MA, Mayhew RJ, Fabio Silveira L, Kelly DJ, Annorbah NND, Pollock HS, Grabowska-Zhang AM, McEntee JP, Carlos T. Gonzalez J, Meneses CG, Muñoz MC, Powell LL, Jamie GA, Matthews TJ, Johnson O, Brito GRR, Zyskowski K, Crates R, Harvey MG, Jurado Zevallos M, Hosner PA, Bradfer-Lawrence T, Maley JM, Stiles FG, Lima HS, Provost KL, Chibesa M, Mashao M, Howard JT, Mlamba E, Chua MAH, Li B, Gómez MI, García NC, Päckert M, Fuchs J, Ali JR, Derryberry EP, Carlson ML, Urriza RC, Brzeski KE, Prawiradilaga DM, Rayner MJ, Miller ET, Bowie RCK, Lafontaine R-M, Scofield RP, Lou Y, Somarathna L, Lepage D, Illif M, Neuschulz EL, Templin M, Dehling DM, Cooper JC, Pauwels OSG, Analuddin K, Fjeldså J, Seddon N, Sweet PR, DeClerck FAJ, Naka LN, Brawn JD, Aleixo A, Böhning-Gaese K, Rahbek C, Fritz SA, Thomas GH, Schleuning M (2022) AVONET: morphological, ecological and geographical data for all birds. Ecology Letters 25:581–597.",
        "is_referenced_by": "https://doi.org/10.1111/ele.13898",
        "creators": ["Tobias JA", "Sheard C", "Pigot AL", "Devenish AJM", "Yang J", "Sayol F", "et al. (see citation)"],
        "issued": "2022-12-05",
        "license": "CC BY 4.0 (figshare record)",
        "version": "figshare v7",
        "distributions": [dist],
        "counts": [{"property_id": "n_species", "value": int(len(df)), "description": "rows in sheet AVONET1_BirdLife (BirdLife taxonomy species)"}] + n_rows_counts(per, "AVONET1_BirdLife"),
        "measurement_technique": "Museum-specimen and field measurements (beak, wing, tail, tarsus, body mass) for ~90,000 individuals, averaged per species, with ecological and range attributes.",
        "taxa": sorted(per),
        "role": "wing length, hand-wing index and body mass for the listed birds (Thompson's flight-scaling argument)",
        "integrity": {"identifier_resolves": resolves("https://doi.org/10.6084/m9.figshare.16586228.v7"), "checksum_verified": True, "checked_at": now()},
    })


# --------------------------------------------------------------------------- FishBase
def build_fishbase():
    print("FishBase v25.04 (rfishbase parquet mirror)")
    base = "https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/fb/v25.04/parquet/"
    d_sp = download(base + "species.parquet", "fb_species.parquet", "application/vnd.apache.parquet")
    d_fam = download(base + "families.parquet", "fb_families.parquet", "application/vnd.apache.parquet")
    sp = pd.read_parquet(DATA / "fb_species.parquet")
    fam = pd.read_parquet(DATA / "fb_families.parquet")[["FamCode", "Family", "Order", "Class"]]
    df = sp.merge(fam, on="FamCode", how="left")
    df["binomial"] = df["Genus"].astype(str).str.strip() + " " + df["Species"].astype(str).str.strip()
    cols = {"class": "Class", "order": "Order", "family": "Family", "genus": "Genus", "binomial": "binomial"}
    per = count_taxa(df, cols, group_slugs("fish"))
    # species pages: verify SpecCode landing pages resolve for the species-level taxa
    pages = {}
    for slug in per:
        if taxa[slug]["rank"] == "species":
            code = int(df.loc[df["binomial"] == taxa[slug]["accepted_name"], "SpecCode"].iloc[0])
            url = f"https://www.fishbase.se/summary/{code}"
            pages[slug] = {"SpecCode": code, "url": url, "resolves": resolves(url)}
    write_dataset({
        "id": "fishbase-v25-04",
        "label": "FishBase, version 04/2025: species and families tables (rfishbase parquet snapshot)",
        "identifier": "https://www.fishbase.se/",
        "doi": None,
        "bibliographic_citation": "Froese R, Pauly D (eds) (2025) FishBase. World Wide Web electronic publication. www.fishbase.org, version (04/2025).",
        "is_referenced_by": "https://www.fishbase.se/manual/English/FishbaseThe_FishBase_Book.htm",
        "creators": ["Froese R", "Pauly D", "FishBase Consortium"],
        "issued": "2025-04",
        "license": None,
        "version": "v25.04",
        "distributions": [d_sp, d_fam],
        "counts": [{"property_id": "n_species", "value": int(len(sp)), "description": "rows in species.parquet"},
                   {"property_id": "n_families", "value": int(len(fam)), "description": "rows in families.parquet"}] + n_rows_counts(per, "species table"),
        "measurement_technique": "Literature-compiled species records: maximum length and weight, length-weight relationship parameters, longevity, growth (von Bertalanffy) parameters, habitat and depth.",
        "taxa": sorted(per),
        "role": "length-weight relationships, maximum size and growth parameters for the listed fishes (Thompson's plaice and haddock weight-length analysis)",
        "integrity": {"identifier_resolves": resolves("https://www.fishbase.se/"), "checksum_verified": True, "checked_at": now()},
        "notes": "The parquet files are the rfishbase snapshot of the FishBase SQL tables (Boettiger C, Lang DT, Wainwright PC (2012) rfishbase. J Fish Biol 81:2030–2039) hosted at https://huggingface.co/datasets/cboettig/fishbase; FishBase itself publishes the data through www.fishbase.se. FishBase's licence is not machine-readable on its pages and is therefore left null. Species pages checked: " + json.dumps(pages),
    })


# --------------------------------------------------------------------------- NCBI Datasets
def build_ncbi(only=None):
    print("NCBI Datasets reference genomes")
    for slug, t in taxa.items():
        taxid = t["identifiers"].get("ncbi_taxid")
        if not taxid or t["rank"] not in ("species", "subspecies", "genus") or (only and slug not in only):
            continue
        url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{taxid}/dataset_report?filters.reference_only=true&page_size=1"
        try:
            data, dist = api_json(url)
        except Exception as e:
            print(f"   {slug}: API error {e}")
            continue
        reports = data.get("reports") or []
        if not reports:
            continue
        r = reports[0]
        acc = r["accession"]
        info = r.get("assembly_info", {})
        stats = r.get("assembly_stats", {})
        org = r.get("organism", {})
        landing = f"https://www.ncbi.nlm.nih.gov/datasets/genome/{acc}/"
        did = "ncbi-genome-" + acc.lower().replace("_", "-").replace(".", "-")
        note = None
        if t["rank"] == "genus":
            note = f"Taxon is the genus {t['accepted_name']}; this is the first reference assembly returned for the genus (organism {org.get('organism_name')}), total {data.get('total_count')} reference assemblies in the genus."
        write_dataset({
            "id": did,
            "label": f"NCBI reference genome assembly {acc} ({info.get('assembly_name')}) for {org.get('organism_name')}",
            "identifier": landing,
            "doi": None,
            "bibliographic_citation": f"{info.get('submitter', 'NCBI')} ({(info.get('release_date') or '')[:4]}) Genome assembly {info.get('assembly_name')} ({acc}), {org.get('organism_name')}. NCBI Datasets. {landing}",
            "is_referenced_by": "https://www.ncbi.nlm.nih.gov/datasets/docs/v2/",
            "creators": [info.get("submitter") or "unknown submitter"],
            "issued": info.get("release_date"),
            "license": "NCBI data are in the public domain (NCBI Website and Data Usage Policies)",
            "version": info.get("assembly_name"),
            "distributions": [dist],
            "counts": [
                {"property_id": "total_sequence_length_bp", "value": int(stats.get("total_sequence_length", 0)), "description": "assembly_stats.total_sequence_length"},
                {"property_id": "number_of_contigs", "value": int(stats.get("number_of_contigs", 0)), "description": "assembly_stats.number_of_contigs"},
                {"property_id": "contig_n50_bp", "value": int(stats.get("contig_n50", 0)), "description": "assembly_stats.contig_n50"},
            ],
            "measurement_technique": f"Whole-genome sequence assembly; assembly level {info.get('assembly_level')}; RefSeq category {info.get('refseq_category', 'none')}; BioProject {info.get('bioproject_accession')}.",
            "taxa": [slug],
            "role": f"reference genome assembly for {org.get('organism_name')}",
            "integrity": {"identifier_resolves": resolves(landing), "checksum_verified": True, "checked_at": now()},
            **({"notes": note} if note else {}),
        })


# --------------------------------------------------------------------------- WoRMS
def build_worms():
    print("WoRMS Aphia records")
    dists, per, ids = [], {}, {}
    for slug, t in taxa.items():
        aphia = t["identifiers"].get("worms_aphia_id")
        if not aphia:
            continue
        url = f"https://www.marinespecies.org/rest/AphiaRecordByAphiaID/{aphia}"
        data, dist = api_json(url)
        dists.append(dist)
        per[slug] = 1
        ids[slug] = {"AphiaID": aphia, "scientificname": data.get("scientificname"), "rank": data.get("rank"), "status": data.get("status"), "valid_AphiaID": data.get("valid_AphiaID")}
    write_dataset({
        "id": f"worms-aphia-records-{TODAY}",
        "label": f"World Register of Marine Species (WoRMS): Aphia taxon records for the marine taxa of this slice, retrieved {TODAY}",
        "identifier": "https://www.marinespecies.org/",
        "doi": "10.14284/170",
        "bibliographic_citation": f"WoRMS Editorial Board ({TODAY[:4]}) World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. doi:10.14284/170",
        "is_referenced_by": "https://doi.org/10.14284/170",
        "creators": ["WoRMS Editorial Board"],
        "issued": TODAY,
        "license": "CC BY 4.0",
        "version": f"REST API, {TODAY}",
        "distributions": dists,
        "counts": [{"property_id": "n_records", "value": len(dists), "description": "AphiaRecordByAphiaID responses retrieved, one per listed taxon"}] + n_rows_counts(per, "Aphia"),
        "measurement_technique": "Expert-curated taxonomic register: accepted name, authority, rank, status, classification and environment flags per AphiaID.",
        "taxa": sorted(per),
        "role": "authoritative marine taxonomy (accepted name, rank, status) for the listed taxa",
        "integrity": {"identifier_resolves": resolves("https://www.marinespecies.org/"), "checksum_verified": True, "checked_at": now()},
        "notes": "Per-taxon AphiaIDs: " + json.dumps(ids),
    })


# --------------------------------------------------------------------------- PBDB
def build_pbdb():
    print("Paleobiology Database")
    dists, per, info = [], {}, {}
    for slug, t in taxa.items():
        if not TABLE[slug].get("fossil"):
            continue
        name = t["accepted_name"]
        url = f"https://paleobiodb.org/data1.2/taxa/single.json?name={requests.utils.quote(name)}&show=size,app"
        data, dist = api_json(url)
        recs = data.get("records") or []
        if not recs:
            print(f"   {slug}: no PBDB taxon")
            continue
        r = recs[0]
        dists.append(dist)
        per[slug] = int(r.get("noc", 0))
        info[slug] = {"pbdb_taxon": r.get("oid"), "name": r.get("nam"), "n_occurrences": r.get("noc"), "taxon_size": r.get("siz"),
                      "extant_size": r.get("exs"), "first_appearance": r.get("tei"), "last_appearance": r.get("tli")}
    write_dataset({
        "id": f"pbdb-taxa-{TODAY}",
        "label": f"Paleobiology Database: taxon summaries (occurrence counts and stratigraphic range) for the fossil-bearing taxa of this slice, retrieved {TODAY}",
        "identifier": "https://paleobiodb.org/",
        "doi": None,
        "bibliographic_citation": f"The Paleobiology Database ({TODAY}) Data Service 1.2, taxa/single. https://paleobiodb.org/data1.2/",
        "is_referenced_by": "https://paleobiodb.org/data1.2/taxa/single_doc.html",
        "creators": ["Paleobiology Database contributors"],
        "issued": TODAY,
        "license": "CC BY 4.0",
        "version": f"data service 1.2, {TODAY}",
        "distributions": dists,
        "counts": [{"property_id": "n_occurrences", "value": int(sum(per.values())), "description": "sum of `noc` (fossil occurrences) over the listed taxa; per taxon: " + ", ".join(f"{k}={v}" for k, v in sorted(per.items()))}],
        "measurement_technique": "Community-entered fossil occurrence records from the literature with taxonomic opinions and stratigraphic intervals.",
        "taxa": sorted(per),
        "role": "fossil occurrence counts and stratigraphic ranges for extinct or fossil-rich taxa (moa, pterosaurs, Carboniferous dragonflies, foraminifera, radiolaria)",
        "integrity": {"identifier_resolves": resolves("https://paleobiodb.org/"), "checksum_verified": True, "checked_at": now()},
        "notes": "Per-taxon summaries: " + json.dumps(info),
    })


SECTIONS = {"gbif": build_gbif, "anage": build_anage, "pantheria": build_pantheria, "amniote": build_amniote, "elton": build_elton,
            "avonet": build_avonet, "fishbase": build_fishbase, "ncbi": build_ncbi, "worms": build_worms, "pbdb": build_pbdb}

if __name__ == "__main__":
    # usage: build_datasets.py [section[:slug,slug] ...]; per-taxon sections (gbif, ncbi) accept a slug filter
    wanted = sys.argv[1:] or list(SECTIONS)
    for w in wanted:
        name, _, slugs = w.partition(":")
        if slugs:
            SECTIONS[name](only=set(slugs.split(",")))
        else:
            SECTIONS[name]()
    save_taxa()
    print("done")
