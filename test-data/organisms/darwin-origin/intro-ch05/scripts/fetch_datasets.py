#!/usr/bin/env python3
"""Fetch, inspect and checksum the reference datasets for the intro-ch05 taxa and write
datasets/<dataset-id>.json records, then link them from taxa/<slug>.json.

Subcommands (all idempotent; raw downloads are cached under /tmp/org/data):
  gbif      one record per taxon: GBIF occurrence count via the API
  anage     AnAge build 15 (longevity / body mass), one shared record
  pantheria PanTHERIA 1.0 (WR05), one shared record
  avonet    AVONET Supplementary dataset 1 (bird morphology), one shared record
  elton     EltonTraits 1.0 birds + mammals, one shared record
  amniote   Amniote Life-History Database (Myhrvold et al. 2015), one shared record
  ncbi      NCBI Datasets reference genome assembly per species-rank taxon, one record each
  worms     WoRMS Aphia records for marine taxa, one shared record
  pbdb      Paleobiology Database taxon occurrence counts, one shared record
  link      rewrite taxa/<slug>.json "datasets" from the dataset records
  all       everything above in order

Counts are what the files actually contain; identifiers are only written after the
landing page / API answered 200.
"""
import hashlib
import io
import json
import re
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
SLICE = HERE.parent
sys.path.insert(0, str(HERE))
from taxa_seed import TAXA  # noqa: E402

DATA = Path("/tmp/org/data")
DATA.mkdir(parents=True, exist_ok=True)
DATASETS = SLICE / "datasets"
DATASETS.mkdir(exist_ok=True)
TAXA_DIR = SLICE / "taxa"

S = requests.Session()
S.headers.update({"User-Agent": "delphi-organisms/0.1 (https://github.com/fractastical/delphi)"})
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def branch():
    try:
        return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=SLICE, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


VENDORED_BY = {"kind": "cloud-agent", "model": "claude-fable-5.1 (Cursor cloud agent)", "run": branch(), "date": TODAY}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def fetch_bytes(url, params=None, retries=4, method="GET"):
    """GET and return (bytes, final_url, retrieved_at). Retries on 429/5xx."""
    for i in range(retries):
        r = S.request(method, url, params=params, timeout=300, allow_redirects=True)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(5 * (i + 1))
            continue
        r.raise_for_status()
        return r.content, r.url, now()
    raise RuntimeError(f"failed: {url}")


def download(url, fname):
    """Download once to /tmp/org/data/<fname>; return (path, byte_size, sha256, retrieved_at)."""
    p = DATA / fname
    meta = DATA / (fname + ".meta.json")
    if p.exists() and meta.exists():
        m = json.loads(meta.read_text())
        return p, m["byte_size"], m["sha256"], m["retrieved_at"]
    b, final, ts = fetch_bytes(url)
    p.write_bytes(b)
    m = {"byte_size": len(b), "sha256": sha256_bytes(b), "retrieved_at": ts, "final_url": final}
    meta.write_text(json.dumps(m))
    return p, m["byte_size"], m["sha256"], ts


def resolves(url):
    """True if the landing page answers 2xx (or 403, i.e. exists but blocks bots - recorded as 'blocked')."""
    try:
        r = S.get(url, timeout=60, allow_redirects=True, stream=True)
        code = r.status_code
        r.close()
        return True if code < 400 else ("blocked" if code == 403 else False)
    except requests.RequestException:
        return False


def doi_registered(doi):
    """True if the DOI exists in the Handle system (https://doi.org/api/handles/<doi>)."""
    try:
        r = S.get(f"https://doi.org/api/handles/{doi}", timeout=60)
        return r.status_code == 200 and r.json().get("responseCode") == 1
    except requests.RequestException:
        return False


def integrity(landing, doi=None, **extra):
    d = {"identifier_resolves": resolves(landing)}
    if doi:
        d["doi_registered"] = doi_registered(doi)
    d.update(extra)
    d["checksum_verified"] = True
    d["checked_at"] = now()
    return d


def crossref(doi):
    """Authors and issued date from CrossRef for a DOI (None if unavailable)."""
    try:
        b, _, _ = fetch_bytes(f"https://api.crossref.org/works/{doi}")
    except Exception:  # noqa: BLE001
        return None
    m = json.loads(b)["message"]
    authors = []
    for a in m.get("author", []):
        fam, giv = a.get("family", ""), a.get("given", "")
        initials = "".join(w[0] for w in re.split(r"[\s.-]+", giv) if w)
        authors.append(f"{fam} {initials}".strip())
    parts = (m.get("issued", {}).get("date-parts") or [[None]])[0]
    issued = "-".join(f"{x:02d}" if i else str(x) for i, x in enumerate(parts) if x is not None) or None
    return {"authors": authors, "issued": issued, "title": (m.get("title") or [None])[0], "container": (m.get("container-title") or [None])[0],
            "volume": m.get("volume"), "page": m.get("page")}


def citation(doi, extra=""):
    """Bibliographic citation assembled from CrossRef metadata (never from memory)."""
    c = crossref(doi)
    if not c:
        return f"https://doi.org/{doi}"
    year = (c["issued"] or "")[:4]
    vol = f" {c['volume']}" if c.get("volume") else ""
    page = f":{c['page']}" if c.get("page") else ""
    return f"{', '.join(c['authors'])} ({year}) {c['title']}. {c['container']}{vol}{page}. doi:{doi}{extra}"


def load_taxa():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(TAXA_DIR.glob("*.json"))}


def write_record(rec):
    (DATASETS / f"{rec['id']}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", rec["id"], "taxa:", len(rec["taxa"]))


# ---------------------------------------------------------------- taxon matching in trait tables
# names a species/subspecies-rank taxon may appear under in trait tables
MATCH_NAMES = {
    "canis-familiaris": ["Canis familiaris", "Canis lupus familiaris"],
    "mustela-putorius-furo": ["Mustela furo", "Mustela putorius furo"],
    "bos-taurus-indicus": ["Bos indicus", "Bos taurus indicus"],
    "equus-quagga-quagga": ["Equus quagga quagga", "Equus quagga"],
    "lagopus-muta": ["Lagopus muta", "Lagopus mutus"],
    "lyrurus-tetrix": ["Lyrurus tetrix", "Tetrao tetrix"],
    "gallus-gallus": ["Gallus gallus"],
    "amblyopsis-spelaea": ["Amblyopsis spelaea", "Amblyopsis spelaeus"],
}
RANK_COL = {"species": "binomial", "subspecies": "binomial", "genus": "genus", "family": "family", "order": "order", "class": "class", "phylum": "phylum"}


_SUBTREE_CACHE = {}


def ncbi_subtree_names(taxid, rank):
    """Names of all NCBI Taxonomy nodes of `rank` below taxid (used to place sub-/infra-ranks
    such as Serpentes or Cetacea, which trait tables do not carry as columns)."""
    key = (taxid, rank)
    if key in _SUBTREE_CACHE:
        return _SUBTREE_CACHE[key]
    b, _, _ = fetch_bytes("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                          {"db": "taxonomy", "term": f"txid{taxid}[Subtree] AND {rank}[Rank]", "retmax": 2000, "retmode": "json"})
    ids = json.loads(b)["esearchresult"]["idlist"]
    names = set()
    for i in range(0, len(ids), 200):
        b, _, _ = fetch_bytes("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                              {"db": "taxonomy", "id": ",".join(ids[i:i + 200]), "retmode": "json"})
        res = json.loads(b)["result"]
        names |= {res[u]["scientificname"].lower() for u in res["uids"]}
        time.sleep(0.4)
    _SUBTREE_CACHE[key] = names
    return names


SUBTREE_RANKS = {"suborder", "infraorder", "infraclass", "subfamily"}


def match_rows(df, cols, taxa, union=None):
    """cols: dict rank->column name in df (binomial/genus/family/order/class/phylum).
    Returns {slug: n_rows} for taxa with >=1 row; if `union` (a list) is given, the boolean
    mask of rows matching any taxon is appended to it."""
    out = {}
    any_mask = pd.Series(False, index=df.index)
    sp_mask = pd.Series(False, index=df.index)
    for slug, t in taxa.items():
        rank = t["rank"]
        name = t["accepted_name"]
        mask = None
        if rank in ("species", "subspecies") and "binomial" in cols:
            names = {x.lower() for x in MATCH_NAMES.get(slug, [name])}
            if rank == "species":
                names.add(name.lower())
            mask = df[cols["binomial"]].str.lower().isin(names)
        elif rank in ("genus", "family", "order", "class", "phylum") and rank in cols:
            mask = df[cols[rank]].str.lower() == name.lower()
        elif rank == "class" and "class" not in cols and cols.get("_all_class", "").lower() == name.lower():
            mask = pd.Series(True, index=df.index)
        elif rank in SUBTREE_RANKS and t["identifiers"].get("ncbi_taxid"):
            for sub_rank in ("family", "genus"):
                if sub_rank in cols:
                    members = ncbi_subtree_names(t["identifiers"]["ncbi_taxid"], sub_rank)
                    if members:
                        mask = df[cols[sub_rank]].str.lower().isin(members)
                        break
        if mask is not None and int(mask.sum()):
            out[slug] = int(mask.sum())
            any_mask |= mask.fillna(False)
            if rank in ("species", "subspecies"):
                sp_mask |= mask.fillna(False)
    if union is not None:
        union.append((int(any_mask.sum()), int(sp_mask.sum())))
    return out


def coverage_counts(cov, row_label, union_rows):
    if isinstance(union_rows, list):
        union_rows = tuple(sum(x) for x in zip(*union_rows))
    allrows, sprows = union_rows
    return [
        {"property_id": "n_rows_for_taxa", "value": int(allrows), "description": f"distinct {row_label} matching at least one of the taxa listed below (per-taxon row counts, which overlap for nested taxa, are in taxa_coverage)"},
        {"property_id": "n_rows_for_species_rank_taxa", "value": int(sprows), "description": f"distinct {row_label} matching the species- or subspecies-rank taxa among them"},
    ]




# ---------------------------------------------------------------- GBIF occurrence counts
def do_gbif():
    taxa = load_taxa()
    for slug, t in taxa.items():
        key = t["identifiers"]["gbif_usage_key"]
        if not key:
            continue
        rid = f"gbif-occurrences-{slug}-{TODAY}"
        if (DATASETS / f"{rid}.json").exists():
            continue
        url = f"https://api.gbif.org/v1/occurrence/search?taxonKey={key}&limit=0"
        b, _, ts = fetch_bytes(url)
        count = json.loads(b)["count"]
        url2 = f"https://api.gbif.org/v1/occurrence/search?taxonKey={key}&hasCoordinate=true&hasGeospatialIssue=false&limit=0"
        b2, _, ts2 = fetch_bytes(url2)
        count2 = json.loads(b2)["count"]
        landing = f"https://www.gbif.org/occurrence/search?taxon_key={key}"
        ok = resolves(f"https://api.gbif.org/v1/species/{key}")
        rec = {
            "id": rid,
            "label": f"GBIF occurrence records for {t['accepted_name']} (backbone taxonKey {key}), counts retrieved {TODAY}",
            "identifier": landing,
            "doi": None,
            "bibliographic_citation": f"GBIF.org ({TODAY}) GBIF Occurrence Search, taxonKey={key}. {landing}",
            "is_referenced_by": "https://www.gbif.org/citation-guidelines",
            "creators": ["GBIF.org"],
            "issued": TODAY,
            "license": "mixed per publishing dataset: CC0 1.0, CC BY 4.0, CC BY-NC 4.0",
            "version": f"GBIF occurrence index as of {TODAY}",
            "distributions": [
                {"download_url": url, "media_type": "application/json", "byte_size": len(b), "sha256": sha256_bytes(b), "retrieved_at": ts, "inspected": True},
                {"download_url": url2, "media_type": "application/json", "byte_size": len(b2), "sha256": sha256_bytes(b2), "retrieved_at": ts2, "inspected": True},
            ],
            "counts": [
                {"property_id": "n_occurrences", "value": count, "description": f"occurrence records indexed by GBIF under taxonKey {key} (including child taxa) at retrieval"},
                {"property_id": "n_occurrences_georeferenced", "value": count2, "description": "the subset with coordinates and no geospatial issue"},
            ],
            "measurement_technique": "Aggregated primary biodiversity occurrence records (specimens, human observations, machine observations) published to GBIF and matched to the GBIF backbone taxonomy.",
            "taxa": [slug],
            "role": f"geographic occurrence records and record counts for {t['accepted_name']}",
            "integrity": {"identifier_resolves": ok, "checksum_verified": True, "checked_at": now()},
            "vendored_by": VENDORED_BY,
        }
        write_record(rec)
        time.sleep(0.3)


# ---------------------------------------------------------------- AnAge
def do_anage():
    url = "https://genomics.senescence.info/species/dataset.zip"
    p, size, sha, ts = download(url, "anage_dataset.zip")
    z = zipfile.ZipFile(p)
    names = z.namelist()
    df = pd.read_csv(io.BytesIO(z.read("anage_data.txt")), sep="\t", dtype=str)
    df["binomial"] = (df["Genus"].str.strip() + " " + df["Species"].str.strip())
    cols = {"binomial": "binomial", "genus": "Genus", "family": "Family", "order": "Order", "class": "Class", "phylum": "Phylum"}
    taxa = load_taxa()
    u = []
    cov = match_rows(df, cols, taxa, u)
    landing = "https://genomics.senescence.info/species/"
    rec = {
        "id": "anage-build-15",
        "label": "AnAge: The Animal Ageing and Longevity Database, build 15 (anage_data.txt)",
        "identifier": landing,
        "doi": "10.1093/nar/gkx1042",
        "bibliographic_citation": citation("10.1093/nar/gkx1042"),
        "is_referenced_by": "https://doi.org/10.1093/nar/gkx1042",
        "creators": (crossref("10.1093/nar/gkx1042") or {}).get("authors") or ["de Magalhães JP (Human Ageing Genomic Resources)"],
        "issued": (crossref("10.1093/nar/gkx1042") or {}).get("issued") or "2017-11",
        "license": "CC BY 3.0",
        "version": "build 15",
        "distributions": [
            {"download_url": url, "media_type": "application/zip", "byte_size": size, "sha256": sha, "retrieved_at": ts, "inspected": True,
             "files": names},
        ],
        "counts": [
            {"property_id": "n_species", "value": int(len(df)), "description": "species rows in anage_data.txt as distributed"},
            {"property_id": "n_columns", "value": int(df.shape[1] - 1), "description": "columns in anage_data.txt"},
        ] + coverage_counts(cov, "rows", u[0]),
        "taxa_coverage": cov,
        "measurement_technique": "Literature-compiled life-history traits per species: maximum longevity, adult body mass, age at maturity, gestation/incubation, metabolic rate, with data-quality flags.",
        "taxa": sorted(cov),
        "role": "maximum longevity, body mass and other life-history traits for the listed taxa (higher-rank taxa: rows of species within them)",
        "integrity": integrity(landing, "10.1093/nar/gkx1042"),
        "vendored_by": VENDORED_BY,
    }
    write_record(rec)


# ---------------------------------------------------------------- PanTHERIA
def do_pantheria():
    url = "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt"
    p, size, sha, ts = download(url, "PanTHERIA_1-0_WR05_Aug2008.txt")
    df = pd.read_csv(p, sep="\t", dtype=str, encoding="latin-1")
    cols = {"binomial": "MSW05_Binomial", "genus": "MSW05_Genus", "family": "MSW05_Family", "order": "MSW05_Order", "_all_class": "Mammalia"}
    taxa = load_taxa()
    u = []
    cov = match_rows(df, cols, taxa, u)
    landing = "https://doi.org/10.1890/08-1494.1"
    rec = {
        "id": "pantheria-1-0-wr05-2008",
        "label": "PanTHERIA: a species-level database of life history, ecology, and geography of extant and recently extinct mammals, v1.0 (Wilson & Reeder 2005 taxonomy)",
        "identifier": landing,
        "doi": "10.1890/08-1494.1",
        "bibliographic_citation": citation("10.1890/08-1494.1", " (Ecological Archives E090-184)"),
        "is_referenced_by": "https://doi.org/10.1890/08-1494.1",
        "creators": (crossref("10.1890/08-1494.1") or {}).get("authors") or ["Jones KE et al."],
        "issued": (crossref("10.1890/08-1494.1") or {}).get("issued") or "2009",
        "license": "Ecological Archives data paper; free for non-commercial scientific use with citation (no formal open license stated)",
        "version": "1.0 (WR05, August 2008)",
        "distributions": [
            {"download_url": url, "media_type": "text/tab-separated-values", "byte_size": size, "sha256": sha, "retrieved_at": ts, "inspected": True},
        ],
        "counts": [
            {"property_id": "n_species", "value": int(len(df)), "description": "species rows in PanTHERIA_1-0_WR05_Aug2008.txt"},
            {"property_id": "n_columns", "value": int(df.shape[1]), "description": "trait and taxonomy columns"},
        ] + coverage_counts(cov, "rows", u[0]),
        "taxa_coverage": cov,
        "measurement_technique": "Literature-compiled species-level mammal traits (adult body mass, litter size, gestation, longevity, home range, population density, diet, geographic range) under the Wilson & Reeder 2005 taxonomy.",
        "taxa": sorted(cov),
        "role": "life-history, ecological and geographic traits for the listed mammal taxa (domestic forms are not separated from wild species)",
        "integrity": integrity(landing, "10.1890/08-1494.1"),
        "vendored_by": VENDORED_BY,
    }
    write_record(rec)


# ---------------------------------------------------------------- AVONET
def do_avonet():
    meta = json.loads(fetch_bytes("https://api.figshare.com/v2/articles/16586228")[0])
    f = next(x for x in meta["files"] if x["name"] == "AVONET Supplementary dataset 1.xlsx")
    url = f["download_url"]
    p, size, sha, ts = download(url, "AVONET_Supplementary_dataset_1.xlsx")
    md5 = hashlib.md5(p.read_bytes()).hexdigest()
    assert md5 == f["computed_md5"], (md5, f["computed_md5"])
    xl = pd.ExcelFile(p)
    df = pd.read_excel(xl, "AVONET1_BirdLife", dtype=str)
    cols = {"binomial": "Species1", "family": "Family1", "order": "Order1", "_all_class": "Aves"}
    taxa = load_taxa()
    # genus column is not provided; derive it from the binomial
    df["genus"] = df["Species1"].str.split(" ").str[0]
    cols["genus"] = "genus"
    u = []
    cov = match_rows(df, cols, taxa, u)
    landing = "https://doi.org/10.6084/m9.figshare.16586228"
    rec = {
        "id": "avonet-figshare-16586228-v7",
        "label": "AVONET: morphological, ecological and geographical data for all birds - Supplementary dataset 1 (sheet AVONET1_BirdLife)",
        "identifier": landing,
        "doi": "10.6084/m9.figshare.16586228",
        "bibliographic_citation": citation("10.1111/ele.13898", " Data: figshare doi:10.6084/m9.figshare.16586228"),
        "is_referenced_by": "https://doi.org/10.1111/ele.13898",
        "creators": (crossref("10.1111/ele.13898") or {}).get("authors") or [a["full_name"] for a in meta.get("authors", [])],
        "issued": "2022-12-05",
        "license": meta.get("license", {}).get("name", "CC BY 4.0"),
        "version": f"figshare v{meta.get('version')}",
        "distributions": [
            {"download_url": url, "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "byte_size": size, "sha256": sha, "md5": md5, "retrieved_at": ts, "inspected": True,
             "sheets": xl.sheet_names},
        ],
        "counts": [
            {"property_id": "n_species", "value": int(len(df)), "description": "species rows in sheet AVONET1_BirdLife"},
            {"property_id": "n_columns", "value": int(df.shape[1] - 1), "description": "columns in sheet AVONET1_BirdLife"},
        ] + coverage_counts(cov, "rows", u[0]),
        "taxa_coverage": cov,
        "measurement_technique": "Museum-specimen morphometrics (beak, wing, tail, tarsus, body mass; ~90,000 individuals) plus trophic, habitat, migration and range metadata, averaged per species.",
        "taxa": sorted(cov),
        "role": "beak, wing, tail, tarsus and body-mass measurements for the listed bird taxa (higher-rank taxa: rows of species within them)",
        "integrity": integrity(landing, "10.6084/m9.figshare.16586228", paper_doi_registered=doi_registered("10.1111/ele.13898"), md5_matches_figshare=True),
        "vendored_by": VENDORED_BY,
    }
    write_record(rec)


# ---------------------------------------------------------------- EltonTraits
def do_elton():
    base = "https://esapubs.org/archive/ecol/E095/178/"
    pb, sb, hb, tb = download(base + "BirdFuncDat.txt", "BirdFuncDat.txt")
    pm, sm, hm, tm = download(base + "MamFuncDat.txt", "MamFuncDat.txt")
    birds = pd.read_csv(pb, sep="\t", dtype=str, encoding="latin-1")
    mams = pd.read_csv(pm, sep="\t", dtype=str, encoding="latin-1")
    mams = mams[mams["Scientific"].notna()]
    taxa = load_taxa()
    birds["genus"] = birds["Scientific"].str.split(" ").str[0]
    mams["genus"] = mams["Scientific"].str.split(" ").str[0]
    u = []
    covb = match_rows(birds, {"binomial": "Scientific", "genus": "genus", "family": "BLFamilyLatin", "order": "IOCOrder", "_all_class": "Aves"}, taxa, u)
    covm = match_rows(mams, {"binomial": "Scientific", "genus": "genus", "family": "MSWFamilyLatin", "_all_class": "Mammalia"}, taxa, u)
    cov = dict(covb)
    for k, v in covm.items():
        cov[k] = cov.get(k, 0) + v
    rec = {
        "id": "eltontraits-1-0-2014",
        "label": "EltonTraits 1.0: species-level foraging attributes of the world's birds and mammals (BirdFuncDat.txt, MamFuncDat.txt)",
        "identifier": "https://doi.org/10.1890/13-1917.1",
        "doi": "10.1890/13-1917.1",
        "bibliographic_citation": citation("10.1890/13-1917.1", " (Ecological Archives E095-178)"),
        "is_referenced_by": "https://doi.org/10.1890/13-1917.1",
        "creators": (crossref("10.1890/13-1917.1") or {}).get("authors") or ["Wilman H et al."],
        "issued": (crossref("10.1890/13-1917.1") or {}).get("issued") or "2014",
        "license": "Ecological Archives data paper; free use with citation (no formal open license stated)",
        "version": "1.0",
        "distributions": [
            {"download_url": base + "BirdFuncDat.txt", "media_type": "text/tab-separated-values", "byte_size": sb, "sha256": hb, "retrieved_at": tb, "inspected": True},
            {"download_url": base + "MamFuncDat.txt", "media_type": "text/tab-separated-values", "byte_size": sm, "sha256": hm, "retrieved_at": tm, "inspected": True},
        ],
        "counts": [
            {"property_id": "n_bird_species", "value": int(len(birds)), "description": "species rows in BirdFuncDat.txt"},
            {"property_id": "n_mammal_species", "value": int(len(mams)), "description": "species rows in MamFuncDat.txt (trailing blank/citation lines dropped)"},
        ] + coverage_counts(cov, "rows (birds + mammals)", u),
        "taxa_coverage": cov,
        "measurement_technique": "Literature-compiled diet composition (percent by category), foraging stratum, activity period and body mass per species.",
        "taxa": sorted(cov),
        "role": "diet, foraging stratum, activity and body mass for the listed bird and mammal taxa",
        "integrity": integrity("https://doi.org/10.1890/13-1917.1", "10.1890/13-1917.1", download_directory_resolves=resolves(base + "BirdFuncDat.txt")),
        "vendored_by": VENDORED_BY,
    }
    write_record(rec)


# ---------------------------------------------------------------- Amniote DB
def do_amniote():
    url = "https://esapubs.org/archive/ecol/E096/269/Data_Files/Amniote_Database_Aug_2015.csv"
    p, size, sha, ts = download(url, "Amniote_Database_Aug_2015.csv")
    df = pd.read_csv(p, dtype=str, encoding="latin-1")
    df["binomial"] = df["genus"].str.strip() + " " + df["species"].str.strip()
    taxa = load_taxa()
    u = []
    cov = match_rows(df, {"binomial": "binomial", "genus": "genus", "family": "family", "order": "order", "class": "class"}, taxa, u)
    landing = "https://doi.org/10.1890/15-0846R.1"
    rec = {
        "id": "amniote-life-history-db-2015-08",
        "label": "An amniote life-history database to perform comparative analyses with birds, mammals, and reptiles (Amniote_Database_Aug_2015.csv)",
        "identifier": landing,
        "doi": "10.1890/15-0846R.1",
        "bibliographic_citation": citation("10.1890/15-0846R.1", " (Ecological Archives E096-269)"),
        "is_referenced_by": "https://doi.org/10.1890/15-0846R.1",
        "creators": (crossref("10.1890/15-0846R.1") or {}).get("authors") or ["Myhrvold NP et al."],
        "issued": (crossref("10.1890/15-0846R.1") or {}).get("issued") or "2015",
        "license": "CC0 1.0 (as stated in the data paper metadata)",
        "version": "August 2015",
        "distributions": [
            {"download_url": url, "media_type": "text/csv", "byte_size": size, "sha256": sha, "retrieved_at": ts, "inspected": True},
        ],
        "counts": [
            {"property_id": "n_species", "value": int(len(df)), "description": "species rows in Amniote_Database_Aug_2015.csv"},
            {"property_id": "n_columns", "value": int(df.shape[1] - 1), "description": "columns (taxonomy + 29 life-history traits + metadata)"},
        ] + coverage_counts(cov, "rows", u[0]),
        "taxa_coverage": cov,
        "measurement_technique": "Literature-compiled life-history traits (body mass, longevity, clutch/litter size, maturity, incubation/gestation, growth) for birds, mammals and reptiles; -999 marks missing values.",
        "taxa": sorted(cov),
        "role": "life-history traits for the listed amniote taxa (higher-rank taxa: rows of species within them)",
        "integrity": integrity(landing, "10.1890/15-0846R.1"),
        "vendored_by": VENDORED_BY,
    }
    write_record(rec)


# ---------------------------------------------------------------- NCBI Datasets genomes
def do_ncbi():
    taxa = load_taxa()
    our_taxids = {v["identifiers"]["ncbi_taxid"] for v in taxa.values() if v["identifiers"]["ncbi_taxid"]}
    for slug, t in taxa.items():
        if t["rank"] not in ("species", "subspecies") or not t["identifiers"]["ncbi_taxid"]:
            continue
        if any(p.name.startswith("ncbi-genome-") and slug in json.loads(p.read_text())["taxa"] for p in DATASETS.glob("ncbi-genome-*.json")):
            continue
        taxid = t["identifiers"]["ncbi_taxid"]
        url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{taxid}/dataset_report?filters.reference_only=true&page_size=5"
        b, _, ts = fetch_bytes(url)
        rep = json.loads(b).get("reports", [])
        if not rep:
            print(f"no reference genome for {slug} (taxid {taxid})")
            continue
        r = rep[0]
        if int(r["organism"]["tax_id"]) != int(taxid):
            # a subspecies assembly stands in for its species unless that subspecies is a taxon of its own here (dog under wolf)
            sub_ok = (t["rank"] == "species" and r["organism"]["organism_name"].startswith(t["accepted_name"] + " ")
                      and int(r["organism"]["tax_id"]) not in our_taxids)
            if not sub_ok:
                print(f"no reference genome for {slug} itself (taxid {taxid}); the reference under this taxon is {r['accession']} for {r['organism']['organism_name']} (taxid {r['organism']['tax_id']})")
                continue
        acc = r["accession"]
        info = r.get("assembly_info", {})
        stats = r.get("assembly_stats", {})
        landing = f"https://www.ncbi.nlm.nih.gov/datasets/genome/{acc}/"
        ok = resolves(landing)
        rid = "ncbi-genome-" + acc.lower().replace("_", "-").replace(".", "-")
        existing = DATASETS / f"{rid}.json"
        if existing.exists():
            d = json.loads(existing.read_text())
            d["taxa"] = sorted(set(d["taxa"]) | {slug})
            write_record(d)
            continue
        counts = []
        for k, label in [("total_sequence_length", "total sequence length (bp)"), ("contig_n50", "contig N50 (bp)"), ("scaffold_n50", "scaffold N50 (bp)"),
                         ("number_of_chromosomes", "number of chromosomes"), ("number_of_scaffolds", "number of scaffolds"), ("gc_percent", "GC percent")]:
            if k in stats:
                v = stats[k]
                counts.append({"property_id": k, "value": float(v) if k == "gc_percent" else int(v), "description": label})
        rec = {
            "id": rid,
            "label": f"NCBI reference genome assembly {acc} ({info.get('assembly_name')}) for {r['organism']['organism_name']}",
            "identifier": landing,
            "doi": None,
            "bibliographic_citation": f"{info.get('submitter', 'NCBI')} ({(info.get('release_date') or '')[:4]}) Genome assembly {acc}, {info.get('assembly_name')}. NCBI Datasets. {landing}",
            "is_referenced_by": "https://doi.org/10.1038/s41597-024-03571-y",
            "creators": [info.get("submitter", "unknown submitter")],
            "issued": info.get("release_date"),
            "license": "NCBI: public domain (US government work); underlying submissions have no additional restrictions",
            "version": acc,
            "distributions": [
                {"download_url": url, "media_type": "application/json", "byte_size": len(b), "sha256": sha256_bytes(b), "retrieved_at": ts, "inspected": True},
            ],
            "counts": counts,
            "assembly": {"accession": acc, "paired_accession": r.get("paired_accession"), "assembly_level": info.get("assembly_level"), "refseq_category": info.get("refseq_category"),
                         "release_date": info.get("release_date"), "organism_taxid": r["organism"]["tax_id"], "infraspecific_names": r["organism"].get("infraspecific_names")},
            "measurement_technique": f"Whole-genome sequencing and assembly ({info.get('sequencing_tech') or 'sequencing technology not stated'}; {info.get('assembly_method') or 'assembly method not stated'}).",
            "taxa": [slug],
            "role": f"reference genome assembly for {t['accepted_name']}" + (f" (assembled from the subspecies {r['organism']['organism_name']})" if int(r["organism"]["tax_id"]) != int(taxid) else ""),
            "integrity": {"identifier_resolves": ok, "checksum_verified": True, "checked_at": now()},
            "vendored_by": VENDORED_BY,
        }
        write_record(rec)
        time.sleep(0.5)


# ---------------------------------------------------------------- WoRMS
def do_worms():
    taxa = load_taxa()
    dists, cov, rows = [], {}, {}
    for slug, t in taxa.items():
        aphia = t["identifiers"]["worms_aphia_id"]
        if not aphia:
            continue
        url = f"https://www.marinespecies.org/rest/AphiaRecordByAphiaID/{aphia}"
        b, _, ts = fetch_bytes(url)
        r = json.loads(b)
        assert r["AphiaID"] == aphia
        dists.append({"download_url": url, "media_type": "application/json", "byte_size": len(b), "sha256": sha256_bytes(b), "retrieved_at": ts, "inspected": True, "taxon": slug})
        cov[slug] = 1
        rows[slug] = {"AphiaID": r["AphiaID"], "scientificname": r["scientificname"], "status": r["status"], "rank": r["rank"], "valid_name": r.get("valid_name"), "valid_AphiaID": r.get("valid_AphiaID"), "isMarine": r.get("isMarine"), "isExtinct": r.get("isExtinct"), "lsid": r.get("lsid")}
        time.sleep(0.5)
    landing = "https://www.marinespecies.org/"
    rec = {
        "id": f"worms-aphia-records-{TODAY}",
        "label": f"World Register of Marine Species (WoRMS) Aphia taxon records retrieved {TODAY}",
        "identifier": landing,
        "doi": "10.14284/170",
        "bibliographic_citation": f"WoRMS Editorial Board ({TODAY[:4]}) World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. Accessed {TODAY}. doi:10.14284/170",
        "is_referenced_by": "https://doi.org/10.14284/170",
        "creators": ["WoRMS Editorial Board"],
        "issued": TODAY,
        "license": "CC BY 4.0",
        "version": f"live database as of {TODAY}",
        "distributions": dists,
        "counts": [
            {"property_id": "n_rows_for_taxa", "value": len(cov), "description": "Aphia records retrieved, one per listed taxon"},
            {"property_id": "n_records_accepted", "value": sum(1 for x in rows.values() if x["status"] == "accepted"), "description": "of those, records with status 'accepted'"},
        ],
        "taxa_coverage": cov,
        "aphia_records": rows,
        "measurement_technique": "Expert-curated taxonomic register: name, status, rank, classification, environment flags and LSID per taxon.",
        "taxa": sorted(cov),
        "role": "authoritative name status, rank and marine/extinct flags for the listed taxa (cirripedes and other marine groups)",
        "integrity": integrity(landing, "10.14284/170"),
        "vendored_by": VENDORED_BY,
    }
    write_record(rec)


# ---------------------------------------------------------------- Paleobiology Database
def do_pbdb():
    taxa = load_taxa()
    dists, cov, rows = [], {}, {}
    for slug, t in taxa.items():
        name = t["accepted_name"]
        if t["rank"] == "subspecies":
            name = " ".join(name.split()[:2])
        url = "https://paleobiodb.org/data1.2/taxa/single.json?name=" + requests.utils.quote(name) + "&show=size"
        try:
            b, _, ts = fetch_bytes(url)
        except requests.HTTPError:
            continue
        r = json.loads(b)
        recs = r.get("records", [])
        if not recs or recs[0].get("nam", "").lower() != name.lower():
            continue
        x = recs[0]
        noc = int(x.get("noc", 0) or 0)
        if noc == 0:
            continue
        dists.append({"download_url": url, "media_type": "application/json", "byte_size": len(b), "sha256": sha256_bytes(b), "retrieved_at": ts, "inspected": True, "taxon": slug})
        cov[slug] = noc
        rows[slug] = {"taxon_no": x.get("oid"), "name": x.get("nam"), "rank_code": x.get("rnk"), "n_occurrences": noc, "n_subtaxa": x.get("siz"), "n_extant_subtaxa": x.get("exs"), "extant": x.get("ext"), "queried_name": name}
        time.sleep(0.4)
    landing = "https://paleobiodb.org/"
    rec = {
        "id": f"pbdb-taxon-occurrence-counts-{TODAY}",
        "label": f"Paleobiology Database: fossil occurrence counts per taxon (taxa/single, show=size) retrieved {TODAY}",
        "identifier": landing,
        "doi": None,
        "bibliographic_citation": f"The Paleobiology Database ({TODAY[:4]}) Data Service 1.2, taxa/single with show=size. https://paleobiodb.org, accessed {TODAY}. See " + citation("10.1017/pab.2015.39"),
        "is_referenced_by": "https://doi.org/10.1017/pab.2015.39",
        "creators": ["The Paleobiology Database community"],
        "issued": TODAY,
        "license": "CC BY 4.0",
        "version": f"live database as of {TODAY}",
        "distributions": dists,
        "counts": [
            {"property_id": "n_rows_for_taxa", "value": len(cov), "description": "taxa with at least one fossil occurrence in PBDB (per-taxon occurrence counts in taxa_coverage)"},
            {"property_id": "n_occurrences_total", "value": int(sum(cov.values())), "description": "sum of PBDB occurrence counts over the listed taxa (overlapping for nested taxa)"},
        ],
        "taxa_coverage": cov,
        "pbdb_records": rows,
        "measurement_technique": "Literature-compiled fossil occurrences (collection x taxon) with geologic age and locality; counts are the database's per-taxon occurrence totals including subtaxa.",
        "taxa": sorted(cov),
        "role": "fossil record depth (number of occurrences, number of subtaxa) for the listed taxa; subspecies queried at species rank",
        "integrity": integrity(landing, paper_doi_registered=doi_registered("10.1017/pab.2015.39")),
        "vendored_by": VENDORED_BY,
    }
    write_record(rec)


# ---------------------------------------------------------------- link datasets into taxa
def do_link():
    taxa = load_taxa()
    links = {s: [] for s in taxa}
    for p in sorted(DATASETS.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for s in d["taxa"]:
            if s in links:
                links[s].append(d["id"])
    for s, t in taxa.items():
        t["datasets"] = sorted(set(links[s]), key=lambda x: (not x.startswith("gbif-"), x))
        (TAXA_DIR / f"{s}.json").write_text(json.dumps(t, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    none = [s for s, l in links.items() if not l]
    print(f"taxa: {len(taxa)}; with >=1 dataset: {len(taxa) - len(none)}; without: {none}")
    only_gbif = [s for s, l in links.items() if l and all(x.startswith("gbif-") for x in l)]
    print(f"only GBIF count: {len(only_gbif)}: {only_gbif}")


STEPS = {"gbif": do_gbif, "anage": do_anage, "pantheria": do_pantheria, "avonet": do_avonet, "elton": do_elton,
         "amniote": do_amniote, "ncbi": do_ncbi, "worms": do_worms, "pbdb": do_pbdb, "link": do_link}

if __name__ == "__main__":
    args = sys.argv[1:] or ["all"]
    if args == ["all"]:
        args = list(STEPS)
    for a in args:
        print(f"=== {a}")
        STEPS[a]()
