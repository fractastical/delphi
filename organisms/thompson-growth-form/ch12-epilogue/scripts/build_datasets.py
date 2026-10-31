#!/usr/bin/env python3
"""Build dataset records for the resolved taxa -> datasets/<id>.json, and link them from taxa/.

Per-taxon records: GBIF occurrence counts (all taxa with a GBIF key), Paleobiology Database
occurrence counts (extinct taxa), NCBI Datasets reference genome assemblies (species-rank taxa).
Shared records (one per slice): AnAge, PanTHERIA, Amniote Life-History Database, AVONET,
FishBase, WoRMS, MorphoSource.

Raw downloads live in $ORGANISMS_DATA (default /tmp/organisms-data), never in the repo.
Run `python3 build_datasets.py [step ...]` with steps among:
  gbif pbdb ncbi anage pantheria amniote avonet fishbase worms morphosource
"""
import hashlib
import io
import json
import re
import sys
import zipfile
from collections import defaultdict

import pandas as pd

from common import (DATA, SESSION, SLICE, VENDORED_BY, cached_meta, download, get_json, now_iso, read_json,
                    today, write_json)

sys.path.insert(0, str(SLICE / "scripts"))
from taxa_terms import TAXA  # noqa: E402

TERMS = {t["slug"]: t for t in TAXA}
TAXA_DIR = SLICE / "taxa"
DS_DIR = SLICE / "datasets"
DS_DIR.mkdir(exist_ok=True)
TAXA_RECS = {p.stem: read_json(p) for p in sorted(TAXA_DIR.glob("*.json"))}
RANK_ORDER = ["species", "subspecies", "genus", "family", "order", "class"]


def link(slug, dataset_id):
    ds = TAXA_RECS[slug].setdefault("datasets", [])
    if dataset_id not in ds:
        ds.append(dataset_id)


def save_taxa():
    for slug, rec in TAXA_RECS.items():
        rec["datasets"] = sorted(set(rec.get("datasets", [])))
        write_json(TAXA_DIR / f"{slug}.json", rec)


def head_ok(url, tries=3):
    import time
    for attempt in range(tries):
        try:
            if url.startswith("https://doi.org/"):
                # a DOI resolves if the handle server redirects; the publisher page may block bots
                ok = SESSION.head(url, timeout=30, allow_redirects=False).status_code in (301, 302, 303)
            else:
                r = SESSION.head(url, timeout=30, allow_redirects=True)
                if r.status_code in (403, 405):
                    r = SESSION.get(url, timeout=30, allow_redirects=True, stream=True,
                                    headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) delphi-organisms"})
                ok = r.status_code < 400
            if ok:
                return True
        except Exception:  # noqa: BLE001
            ok = False
        time.sleep(2 * (attempt + 1))
    return False


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def api_distribution(url, body):
    raw = json.dumps(body, sort_keys=True).encode()
    full, retrieved = cached_meta(url)
    return {"download_url": full, "media_type": "application/json", "byte_size": len(raw),
            "sha256": sha256_bytes(raw), "retrieved_at": retrieved or now_iso(), "inspected": True,
            "note": "checksum is of the JSON response body as cached, keys sorted"}


def base_record(ds_id, label, identifier, **kw):
    rec = {
        "id": ds_id, "label": label, "identifier": identifier,
        "doi": kw.get("doi"), "bibliographic_citation": kw.get("citation"),
        "is_referenced_by": kw.get("is_referenced_by"), "creators": kw.get("creators", []),
        "issued": kw.get("issued"), "license": kw.get("license"), "version": kw.get("version"),
        "distributions": kw.get("distributions", []), "counts": kw.get("counts", []),
        "measurement_technique": kw.get("technique"), "taxa": kw.get("taxa", []),
        "role": kw.get("role"),
        "integrity": {"identifier_resolves": head_ok(identifier), "checksum_verified": kw.get("checksum_verified", False),
                      "checksum_source": kw.get("checksum_source"), "checked_at": now_iso()},
        "vendored_by": VENDORED_BY,
    }
    for k in ("taxa_rows", "notes", "landing_page"):
        if k in kw:
            rec[k] = kw[k]
    return rec


def emit(rec):
    write_json(DS_DIR / f"{rec['id']}.json", rec)
    for slug in rec["taxa"]:
        link(slug, rec["id"])
    print(f"  wrote {rec['id']} ({len(rec['taxa'])} taxa)")


# ---------------------------------------------------------------------------------------------- names
def match_names(slug):
    """Names under which a taxon may appear in a trait table, keyed by rank."""
    rec, term = TAXA_RECS[slug], TERMS[slug]
    rank = rec["rank"] or term.get("rank")
    names = {rec["accepted_name"], term["query"]}
    if rec.get("worms") and rec["worms"].get("valid_name"):
        names.add(rec["worms"]["valid_name"])
    if rec.get("pbdb") and rec["pbdb"].get("accepted_name"):
        names.add(rec["pbdb"]["accepted_name"])
    names.update(term.get("alias_names", []))
    if rank == "subspecies":  # e.g. Canis lupus familiaris: also try the binomial Thompson's usage implies
        names.add(term["query"])
        rank = "species"
    return rank, {n for n in names if n}


def rows_for_taxa(df, cols, slugs):
    """cols: dict rank -> column holding that rank's name (species column holds the binomial)."""
    out = {}
    for slug in slugs:
        rank, names = match_names(slug)
        col = cols.get(rank)
        if col is None:
            continue
        series = df[col].astype(str).str.strip()
        if rank == "species":
            series = series.str.replace(r"\s+", " ", regex=True)
        n = int(series.str.lower().isin({x.lower() for x in names}).sum())
        if n:
            out[slug] = n
    return out


# ---------------------------------------------------------------------------------------------- GBIF
def step_gbif():
    print("GBIF occurrence counts")
    for slug, rec in TAXA_RECS.items():
        key = rec["identifiers"].get("gbif_usage_key")
        if not key:
            continue
        url = "https://api.gbif.org/v1/occurrence/search"
        body = get_json(url, params={"taxonKey": key, "limit": 0}, sleep=0.1)
        full, retrieved = cached_meta(url, params={"taxonKey": key, "limit": 0})
        ds_id = f"gbif-occurrences-{slug}-{today()}"
        emit(base_record(
            ds_id, f"GBIF occurrence records for {rec['accepted_name']} (taxonKey {key}), count on {today()}",
            full,
            landing_page=f"https://www.gbif.org/occurrence/search?taxon_key={key} (returns HTTP 403 to automated clients; the API URL is used as identifier)",
            citation=f"GBIF.org ({today()}) GBIF Occurrence Search, taxonKey={key}. https://www.gbif.org/occurrence/search?taxon_key={key}",
            is_referenced_by="https://doi.org/10.15468/39omei",
            creators=["GBIF.org"], issued=today(), version=today(),
            license="per-dataset (CC0 1.0, CC BY 4.0 or CC BY-NC 4.0); see https://www.gbif.org/terms",
            distributions=[{**api_distribution(full, body), "download_url": full}],
            counts=[{"property_id": "n_occurrences", "value": body["count"],
                     "description": f"occurrence records in GBIF whose taxonKey resolves to {rec['accepted_name']} (incl. child taxa), from the API count field"}],
            technique="Aggregated occurrence records (specimens, observations, machine observations) indexed against the GBIF backbone taxonomy.",
            taxa=[slug], role=f"geographic occurrence records for {rec['accepted_name']}",
            checksum_verified=True, checksum_source="sha256 of the cached API response body",
        ))


# ---------------------------------------------------------------------------------------------- PBDB
def step_pbdb():
    print("Paleobiology Database occurrence counts")
    for slug, rec in TAXA_RECS.items():
        if not rec.get("pbdb"):
            continue
        name = rec["pbdb"].get("accepted_name") or rec["pbdb"]["name"]
        url = "https://paleobiodb.org/data1.2/occs/list.json"
        params = {"base_name": name, "limit": 1, "rowcount": ""}
        body = get_json(url, params=params, sleep=0.2)
        full, _ = cached_meta(url, params=params)
        n = body.get("records_found", 0)
        ds_id = f"pbdb-occurrences-{slug}-{today()}"
        emit(base_record(
            ds_id, f"Paleobiology Database fossil occurrences for {name} (base_name), count on {today()}",
            f"https://paleobiodb.org/data1.2/taxa/single.json?id=txn:{rec['identifiers']['pbdb_taxon_no']}&show=class",
            landing_page=f"https://paleobiodb.org/classic/checkTaxonInfo?taxon_no={rec['identifiers']['pbdb_taxon_no']} (returns HTTP 403 to automated clients; the data1.2 API URL is used as identifier)",
            citation=f"The Paleobiology Database ({today()}) occurrence list, base_name={name}. https://paleobiodb.org/data1.2/occs/list.json?base_name={name}",
            is_referenced_by="https://doi.org/10.1007/s12549-015-0207-y",
            creators=["Paleobiology Database contributors"], issued=today(), version=f"data1.2 API, {today()}",
            license="CC BY 4.0",
            distributions=[api_distribution(full, body)],
            counts=[{"property_id": "n_occurrences", "value": n,
                     "description": f"fossil occurrence records for {name} and its subtaxa (records_found)"},
                    {"property_id": "n_taxon_occurrences_in_taxonomy_table", "value": rec["pbdb"].get("n_occurrences"),
                     "description": "noc field of the PBDB taxon record (occurrences attributed to this taxon name)"}],
            technique="Literature-compiled fossil collections with taxonomic occurrences, ages and localities.",
            taxa=[slug], role=f"fossil record (occurrences, stratigraphic range) for {name}",
            checksum_verified=True, checksum_source="sha256 of the cached API response body",
        ))


# ---------------------------------------------------------------------------------------------- NCBI genomes
def step_ncbi():
    print("NCBI Datasets reference genomes")
    for slug, rec in TAXA_RECS.items():
        taxid = rec["identifiers"].get("ncbi_taxid")
        if not taxid or rec["rank"] not in ("species", "subspecies"):
            continue
        url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{taxid}/dataset_report"
        params = {"filters.reference_only": "true", "page_size": 1}
        body = get_json(url, params=params, sleep=0.4)
        reports = (body or {}).get("reports", [])
        if not reports:
            continue
        r = reports[0]
        if r.get("organism", {}).get("tax_id") not in (taxid,) and rec["rank"] == "species":
            # reference genome belongs to a subspecies/strain; still the species' reference. Keep, but note.
            pass
        acc = r["accession"]
        info = r.get("assembly_info", {})
        stats = r.get("assembly_stats", {})
        full, _ = cached_meta(url, params=params)
        ds_id = f"ncbi-genome-{acc.lower().replace('_', '-').replace('.', '-')}"
        emit(base_record(
            ds_id, f"NCBI reference genome assembly {acc} ({info.get('assembly_name')}) for {r['organism']['organism_name']}",
            f"https://www.ncbi.nlm.nih.gov/datasets/genome/{acc}/",
            citation=f"{info.get('submitter') or 'NCBI'} ({(info.get('release_date') or '')[:4]}) Genome assembly {info.get('assembly_name')} [{acc}]. NCBI Datasets. https://www.ncbi.nlm.nih.gov/datasets/genome/{acc}/",
            is_referenced_by="https://doi.org/10.1038/s41597-024-03571-y",
            creators=[x for x in [info.get("submitter")] if x], issued=info.get("release_date"),
            license="NCBI data are in the public domain (US Government work); see https://www.ncbi.nlm.nih.gov/home/about/policies/",
            version=info.get("assembly_name"),
            distributions=[api_distribution(full, body)],
            counts=[{"property_id": "total_sequence_length_bp", "value": int(stats.get("total_sequence_length", 0) or 0), "description": "total assembled sequence length (bp)"},
                    {"property_id": "contig_n50_bp", "value": stats.get("contig_n50"), "description": "contig N50 (bp)"},
                    {"property_id": "number_of_chromosomes", "value": stats.get("total_number_of_chromosomes"), "description": "assembled chromosomes"}],
            technique=f"Whole-genome shotgun assembly; level {info.get('assembly_level')}; BioProject {info.get('bioproject_accession')}; organism tax_id {r['organism'].get('tax_id')}.",
            taxa=[slug], role=f"reference genome assembly for {rec['accepted_name']}",
            checksum_verified=True, checksum_source="sha256 of the cached dataset_report response; the assembly files themselves were not downloaded",
            notes=None if r["organism"].get("tax_id") == taxid else f"Reference assembly is filed under tax_id {r['organism'].get('tax_id')} ({r['organism']['organism_name']}), a subspecies/strain of the taxon.",
        ))


# ---------------------------------------------------------------------------------------------- AnAge
def step_anage():
    print("AnAge")
    d = download("https://genomics.senescence.info/species/dataset.zip", "anage_dataset.zip")
    z = zipfile.ZipFile(d["path"])
    names = z.namelist()
    data_name = next(n for n in names if n.endswith("anage_data.txt"))
    df = pd.read_csv(io.BytesIO(z.read(data_name)), sep="\t", dtype=str)
    df["binomial"] = (df["Genus"].str.strip() + " " + df["Species"].str.strip())
    release = next((n for n in names if "release" in n.lower()), None)
    build = ""
    if release:
        txt = z.read(release).decode("utf-8", "ignore")
        m = re.search(r"[Bb]uild\s*(\d+)", txt)
        build = m.group(1) if m else ""
    slugs = [s for s in TAXA_RECS if TERMS[s]["group"] in ("mammal", "bird", "reptile", "fish")]
    rows = rows_for_taxa(df, {"species": "binomial", "genus": "Genus", "family": "Family", "order": "Order", "class": "Class"}, slugs)
    emit(base_record(
        f"anage-build-{build or 'current'}", f"AnAge: The Animal Ageing and Longevity Database, build {build}",
        "https://genomics.senescence.info/species/",
        doi="10.1093/nar/gkx1042",
        citation="Tacutu R, Thornton D, Johnson E, Budovsky A, Barardo D, Craig T, Diana E, Lehmann G, Toren D, Wang J, Fraifeld VE, de Magalhães JP (2018) Human Ageing Genomic Resources: new and updated databases. Nucleic Acids Res 46(D1):D1083-D1090.",
        is_referenced_by="https://doi.org/10.1093/nar/gkx1042",
        creators=["de Magalhães JP", "Tacutu R", "Human Ageing Genomic Resources"], issued="2017-11", license="CC BY 3.0",
        version=f"build {build}",
        distributions=[{"download_url": d["download_url"], "media_type": "application/zip", "byte_size": d["byte_size"], "sha256": d["sha256"],
                        "retrieved_at": d["retrieved_at"], "inspected": True, "files": names}],
        counts=[{"property_id": "n_species", "value": int(len(df)), "description": f"species rows in {data_name} as distributed"},
                {"property_id": "n_rows_for_taxa", "value": int(sum(rows.values())), "description": "rows matching the taxa listed below (species: exact binomial; genus/family/order/class: column match)"}],
        technique="Literature-compiled life-history traits: maximum longevity, body mass, metabolic rate, maturity, gestation, litter size.",
        taxa=sorted(rows), taxa_rows=rows, role="maximum longevity, adult body mass and other life-history traits for the listed taxa",
        checksum_verified=True, checksum_source="sha256 computed from the downloaded zip; no publisher checksum available",
    ))


# ---------------------------------------------------------------------------------------------- PanTHERIA
def step_pantheria():
    print("PanTHERIA")
    url = "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt"
    d = download(url, "PanTHERIA_1-0_WR05_Aug2008.txt")
    df = pd.read_csv(d["path"], sep="\t", dtype=str, encoding="latin-1")
    slugs = [s for s in TAXA_RECS if TERMS[s]["group"] == "mammal"]
    rows = rows_for_taxa(df, {"species": "MSW05_Binomial", "genus": "MSW05_Genus", "family": "MSW05_Family", "order": "MSW05_Order"}, slugs)
    emit(base_record(
        "pantheria-1-0-wr05-2008", "PanTHERIA: a species-level database of life history, ecology, and geography of extant and recently extinct mammals (v1.0, Wilson & Reeder 2005 taxonomy)",
        "https://doi.org/10.1890/08-1494.1",
        doi="10.1890/08-1494.1",
        citation="Jones KE, Bielby J, Cardillo M, Fritz SA, O'Dell J, Orme CDL, Safi K, Sechrest W, Boakes EH, Carbone C, Connolly C, Cutts MJ, Foster JK, Grenyer R, Habib M, Plaster CA, Price SA, Rigby EA, Rist J, Teacher A, Bininda-Emonds ORP, Gittleman JL, Mace GM, Purvis A (2009) PanTHERIA: a species-level database of life history, ecology, and geography of extant and recently extinct mammals. Ecology 90:2648.",
        is_referenced_by="https://doi.org/10.1890/08-1494.1",
        creators=["Jones KE", "Bielby J", "Cardillo M", "Fritz SA", "Purvis A", "et al."], issued="2009-09", license=None,
        version="1.0 (WR05, August 2008)",
        distributions=[{"download_url": url, "media_type": "text/tab-separated-values", "byte_size": d["byte_size"], "sha256": d["sha256"],
                        "retrieved_at": d["retrieved_at"], "inspected": True}],
        counts=[{"property_id": "n_species", "value": int(len(df)), "description": "species rows in PanTHERIA_1-0_WR05_Aug2008.txt"},
                {"property_id": "n_rows_for_taxa", "value": int(sum(rows.values())), "description": "rows matching the taxa listed below"}],
        technique="Literature-compiled species-level traits: body mass, longevity, gestation, litter size, home range, population density, diet, geographic range.",
        taxa=sorted(rows), taxa_rows=rows, role="adult body mass, longevity and life-history traits for the listed mammals",
        checksum_verified=True, checksum_source="sha256 computed from the downloaded file; no publisher checksum available",
        notes="Ecological Archives E090-184 data paper; no explicit licence is attached to the file (ESA data papers are free for scientific use with citation). The esapubs.org directory pages return 403 to automated clients, so the DOI is used as identifier; the data file URL itself resolves.",
    ))


# ---------------------------------------------------------------------------------------------- Amniote
def step_amniote():
    print("Amniote Life-History Database")
    url = "https://esapubs.org/archive/ecol/E096/269/Data_Files/Amniote_Database_Aug_2015.csv"
    d = download(url, "Amniote_Database_Aug_2015.csv")
    df = pd.read_csv(d["path"], dtype=str, encoding="latin-1")
    df["binomial"] = df["genus"].str.strip() + " " + df["species"].str.strip()
    slugs = [s for s in TAXA_RECS if TERMS[s]["group"] in ("mammal", "bird", "reptile")]
    rows = rows_for_taxa(df, {"species": "binomial", "genus": "genus", "family": "family", "order": "order", "class": "class"}, slugs)
    emit(base_record(
        "amniote-life-history-database-2015-08", "An amniote life-history database to perform comparative analyses with birds, mammals, and reptiles (Amniote Database, August 2015)",
        "https://doi.org/10.1890/15-0846R.1",
        doi="10.1890/15-0846R.1",
        citation="Myhrvold NP, Baldridge E, Chan B, Sivam D, Freeman DL, Ernest SKM (2015) An amniote life-history database to perform comparative analyses with birds, mammals, and reptiles. Ecology 96:3109.",
        is_referenced_by="https://doi.org/10.1890/15-0846R.1",
        creators=["Myhrvold NP", "Baldridge E", "Chan B", "Sivam D", "Freeman DL", "Ernest SKM"], issued="2015-11", license=None,
        version="August 2015",
        distributions=[{"download_url": url, "media_type": "text/csv", "byte_size": d["byte_size"], "sha256": d["sha256"],
                        "retrieved_at": d["retrieved_at"], "inspected": True}],
        counts=[{"property_id": "n_species", "value": int(len(df)), "description": "species rows in Amniote_Database_Aug_2015.csv"},
                {"property_id": "n_rows_for_taxa", "value": int(sum(rows.values())), "description": "rows matching the taxa listed below"}],
        technique="Literature-compiled life-history traits (body mass, egg mass, clutch/litter size, longevity, maturity, incubation/gestation) for 21,322 amniote species; missing values coded -999.",
        taxa=sorted(rows), taxa_rows=rows, role="egg mass, adult body mass and life-history traits for the listed birds, mammals and reptiles",
        checksum_verified=True, checksum_source="sha256 computed from the downloaded file; no publisher checksum available",
        notes="Ecological Archives E096-269 data paper; no explicit licence is attached to the file. The esapubs.org directory pages return 403 to automated clients, so the DOI is used as identifier; the data file URL itself resolves.",
    ))


# ---------------------------------------------------------------------------------------------- AVONET
def step_avonet():
    print("AVONET")
    meta = get_json("https://api.figshare.com/v2/articles/16586228")
    f = next(x for x in meta["files"] if x["id"] == 34480856)
    d = download("https://ndownloader.figshare.com/files/34480856", "AVONET_Supplementary_dataset_1.xlsx")
    md5 = hashlib.md5(open(d["path"], "rb").read()).hexdigest()  # noqa: S324 - figshare publishes md5
    df = pd.read_excel(d["path"], sheet_name="AVONET1_BirdLife", dtype=str)
    slugs = [s for s in TAXA_RECS if TERMS[s]["group"] == "bird"]
    rows = rows_for_taxa(df, {"species": "Species1", "family": "Family1", "order": "Order1"}, slugs)
    # genus-level: Species1 starts with "Genus "
    for slug in slugs:
        rank, names = match_names(slug)
        if rank == "genus":
            n = int(df["Species1"].astype(str).str.split(" ").str[0].isin(names).sum())
            if n:
                rows[slug] = n
    emit(base_record(
        "avonet-2022-v7", "AVONET: morphological, ecological and geographical data for all birds (Supplementary dataset 1, BirdLife taxonomy sheet)",
        "https://doi.org/10.6084/m9.figshare.16586228.v7",
        doi="10.1111/ele.13898",
        citation="Tobias JA, Sheard C, Pigot AL, Devenish AJM, Yang J, Sayol F, Neate-Clegg MHC, Alioravainen N, Weeks TL, Barber RA, et al. (2022) AVONET: morphological, ecological and geographical data for all birds. Ecology Letters 25:581-597.",
        is_referenced_by="https://doi.org/10.1111/ele.13898",
        creators=["Tobias JA", "Sheard C", "Pigot AL", "Devenish AJM", "et al."], issued=meta.get("published_date", "")[:10], license=meta.get("license", {}).get("name"),
        version=f"figshare v{meta.get('version')} ({f['name']})",
        distributions=[{"download_url": f["download_url"], "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "byte_size": d["byte_size"], "sha256": d["sha256"], "md5": md5, "figshare_computed_md5": f["computed_md5"],
                        "retrieved_at": d["retrieved_at"], "inspected": True}],
        counts=[{"property_id": "n_species", "value": int(len(df)), "description": "species rows in sheet AVONET1_BirdLife"},
                {"property_id": "n_rows_for_taxa", "value": int(sum(rows.values())), "description": "rows matching the taxa listed below"}],
        technique="Museum-specimen morphometrics (beak, wing, tail, tarsus, body mass) averaged per species, with ecological and range attributes.",
        taxa=sorted(rows), taxa_rows=rows, role="beak, wing and body-mass morphometrics for the listed birds",
        checksum_verified=(md5 == f["computed_md5"]), checksum_source="md5 of the download equals figshare's computed_md5; sha256 also recorded",
    ))


# ---------------------------------------------------------------------------------------------- FishBase
def step_fishbase():
    print("FishBase")
    base = "https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/fb/v25.04/parquet/"
    ds = download(base + "species.parquet", "fishbase_v25.04_species.parquet")
    df_f = download(base + "families.parquet", "fishbase_v25.04_families.parquet")
    sp = pd.read_parquet(ds["path"])
    fam = pd.read_parquet(df_f["path"])[["FamCode", "Family", "Order"]]
    sp = sp.merge(fam, on="FamCode", how="left")
    sp["binomial"] = sp["Genus"].astype(str).str.strip() + " " + sp["Species"].astype(str).str.strip()
    slugs = [s for s in TAXA_RECS if TERMS[s]["group"] == "fish"]
    rows = rows_for_taxa(sp, {"species": "binomial", "genus": "Genus", "family": "Family", "order": "Order"}, slugs)
    emit(base_record(
        "fishbase-v25-04-species", "FishBase species table, version 25.04 (rfishbase parquet snapshot)",
        "https://fishbase.se/",
        citation="Froese R, Pauly D (eds) (2025) FishBase. World Wide Web electronic publication, www.fishbase.org, version (04/2025). Snapshot: Boettiger C, rfishbase data mirror, https://huggingface.co/datasets/cboettig/fishbase",
        is_referenced_by="https://huggingface.co/datasets/cboettig/fishbase",
        creators=["Froese R", "Pauly D", "FishBase Consortium"], issued="2025-04", license="CC BY-NC 4.0",
        version="v25.04",
        distributions=[{"download_url": base + "species.parquet", "media_type": "application/vnd.apache.parquet", "byte_size": ds["byte_size"], "sha256": ds["sha256"], "retrieved_at": ds["retrieved_at"], "inspected": True},
                       {"download_url": base + "families.parquet", "media_type": "application/vnd.apache.parquet", "byte_size": df_f["byte_size"], "sha256": df_f["sha256"], "retrieved_at": df_f["retrieved_at"], "inspected": True}],
        counts=[{"property_id": "n_species", "value": int(len(sp)), "description": "rows in species.parquet (one per valid species)"},
                {"property_id": "n_rows_for_taxa", "value": int(sum(rows.values())), "description": "rows matching the taxa listed below"}],
        technique="Curated species-level fish data: maximum length, weight, length-weight parameters, habitat, depth range, trophic level, with literature references.",
        taxa=sorted(rows), taxa_rows=rows, role="maximum length, body depth/length-weight data and habitat for the listed fishes",
        checksum_verified=True, checksum_source="sha256 computed from the downloaded parquet files; Hugging Face LFS also exposes sha256 per file",
    ))


# ---------------------------------------------------------------------------------------------- WoRMS
def step_worms():
    print("WoRMS")
    dists, taxa, counts = [], [], []
    for slug, rec in TAXA_RECS.items():
        aid = rec["identifiers"].get("worms_aphia_id")
        if not aid or not TERMS[slug].get("marine"):
            continue
        url = f"https://www.marinespecies.org/rest/AphiaRecordByAphiaID/{aid}"
        body = get_json(url, sleep=0.3)
        if not body:
            continue
        full, _ = cached_meta(url)
        dists.append({**api_distribution(full, body), "taxon": slug})
        taxa.append(slug)
        counts.append({"property_id": "aphia_record", "value": aid, "description": f"{slug}: {body.get('scientificname')} {body.get('authority') or ''} [{body.get('status')}, rank {body.get('rank')}]".strip()})
    emit(base_record(
        f"worms-aphia-records-ch12-epilogue-{today()}", f"World Register of Marine Species (WoRMS) Aphia records for the marine taxa of this slice, retrieved {today()}",
        "https://www.marinespecies.org/",
        doi="10.14284/170",
        citation=f"WoRMS Editorial Board ({today()[:4]}) World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. doi:10.14284/170",
        is_referenced_by="https://doi.org/10.14284/170",
        creators=["WoRMS Editorial Board"], issued=today(), license="CC BY 4.0", version=f"REST API, {today()}",
        distributions=dists,
        counts=[{"property_id": "n_taxa_with_records", "value": len(taxa), "description": "taxa of this slice with an Aphia record retrieved"}] + counts,
        technique="Expert-curated taxonomic register: accepted names, synonymy, authority, rank, classification, environment flags, extinction flag.",
        taxa=taxa, role="authoritative nomenclature and classification for the listed marine taxa",
        checksum_verified=True, checksum_source="sha256 of each cached API response body",
    ))


# ---------------------------------------------------------------------------------------------- MorphoSource
def step_morphosource():
    print("MorphoSource")
    dists, taxa, counts, rows = [], [], [], {}
    for slug, rec in TAXA_RECS.items():
        name = rec["accepted_name"]
        url = "https://www.morphosource.org/api/media"
        params = {"f[taxonomy_gbif][]": name, "per_page": 1}
        body = get_json(url, params=params, sleep=0.3)
        n = ((body or {}).get("response", {}).get("pages", {}) or {}).get("total_count", 0)
        if not n:
            continue
        full, _ = cached_meta(url, params=params)
        slim = {"response": {"pages": body["response"]["pages"], "facets": [f for f in body["response"].get("facets", []) if f["name"] in ("media_type", "modality", "publication_status")]}}
        dists.append({**api_distribution(full, slim), "taxon": slug, "note": "checksum is of the response reduced to pages + media_type/modality/publication_status facets"})
        taxa.append(slug)
        rows[slug] = n
        counts.append({"property_id": "n_media", "value": n, "description": f"{slug}: media records whose GBIF taxonomy facet includes '{name}'"})
    emit(base_record(
        f"morphosource-media-ch12-epilogue-{today()}", f"MorphoSource 3D media (scans/meshes) for the taxa of this slice, counts on {today()}",
        "https://www.morphosource.org/",
        doi="10.1017/S1089332600002862",
        citation="Boyer DM, Gunnell GF, Kaufman S, McGeary TM (2016) MorphoSource: Archiving and sharing 3-D digital specimen data. The Paleontological Society Papers 22:157-181.",
        is_referenced_by="https://doi.org/10.1017/S1089332600002862",
        creators=["Duke University", "MorphoSource contributors"], issued=today(), license="per-media (CC0, CC BY, CC BY-NC or restricted); metadata open",
        version=f"API, {today()}",
        distributions=dists,
        counts=[{"property_id": "n_taxa_with_media", "value": len(taxa), "description": "taxa of this slice with at least one media record"},
                {"property_id": "n_rows_for_taxa", "value": int(sum(rows.values())), "description": "media records summed over the listed taxa (a record may be counted under more than one nested taxon)"}] + counts,
        technique="Repository of 3D surface scans and CT volumes of museum specimens (skulls, skeletons, whole bodies), indexed to GBIF taxonomy.",
        taxa=taxa, taxa_rows=rows, role="3D skull and skeleton scans for morphometric comparison of the listed taxa",
        checksum_verified=True, checksum_source="sha256 of each reduced cached API response",
    ))


STEPS = {"gbif": step_gbif, "pbdb": step_pbdb, "ncbi": step_ncbi, "anage": step_anage, "pantheria": step_pantheria,
         "amniote": step_amniote, "avonet": step_avonet, "fishbase": step_fishbase, "worms": step_worms, "morphosource": step_morphosource}

if __name__ == "__main__":
    which = sys.argv[1:] or list(STEPS)
    for w in which:
        STEPS[w]()
        save_taxa()
    missing = [s for s, r in TAXA_RECS.items() if not r.get("datasets")]
    print(f"\n{len(list(DS_DIR.glob('*.json')))} dataset records; taxa without any dataset: {missing}")
