"""One card per source: URI, accession, version, locator, licence, access, retrieval time, artifact hashes, read level, limits.

Built only from the receipts the fetchers wrote. A licence is recorded only where a source's own bytes state one; otherwise it is null
and `license_read` says so. Nothing here is a legal conclusion.

  PYTHONPATH=. python3 -m connectors.genomics.source_cards
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "genomics"


def main() -> int:
    r = json.loads((OUT / "receipts.json").read_text())
    f = json.loads((OUT / "flyingfish_receipts.json").read_text())
    x = json.loads((OUT / "extra_receipts.json").read_text())
    cards = []

    def card(id_, name, uri, accession, locator, license_, license_read, access, receipt, artifacts, read_level, limits, version=None):
        cards.append({"id": id_, "name": name, "uri": uri, "accession": accession, "version": version or receipt.get("last_modified") or receipt.get("etag") or f"retrieved {receipt['retrieved_at']}",
                      "locator": locator, "license": license_, "license_read": license_read, "access": access, "retrieved_at": receipt["retrieved_at"], "http_status": receipt["http_status"],
                      "source_stream_sha256": receipt["sha256"], "source_stream_bytes": receipt["bytes"], "artifacts": artifacts, "read_level": read_level, "limits": limits})

    NOLIC = "no licence statement was read; ZFIN's terms page was not fetched"
    for key, fname, loc, lim in (
            ("zfin_gene", "gene.txt", "rows for the 22 selected symbols", "symbol/ID table only"),
            ("zfin_ensembl", "ensembl_1_to_1.txt", "rows for the 22 selected symbols", "1:1 ZFIN-Ensembl map only; genes without a 1:1 mapping are absent from this file"),
            ("zfin_aliases", "aliases.txt", "rows for the selected genes plus every row containing 'lat4'", "alias table; zero rows contained lat4"),
            ("zfin_expression", "wildtype-expression_fish.txt", "rows whose gene symbol is in the set", "no header row in the file (columns inferred from layout and sample rows); literature-curated, sparse, presence annotations not levels"),
            ("zfin_phenotype", "phenoGeneCleanData_fish.txt", "rows whose gene symbol is in the set", "no header row in the file; curated annotations of mutants and morphants, not a measurement by this connector"),
            ("zfin_gff", "zfin_genes.gff3", "lines mentioning a selected ZFIN gene id", "assembly is not stated in the file header; checked against UCSC danRer11 (see assembly_check.json)")):
        card(f"zfin-{fname.split('.')[0].lower().replace('_', '-')}", f"ZFIN download {fname}", f"https://zfin.org/downloads/{fname}", fname, loc, None, NOLIC, "public download, no login",
             r[key]["receipt"], [r[key]["artifact"]], "full-file stream (whole file hashed; selected rows kept)", lim)
    card("ncbi-gene-esummary", "NCBI Gene esummary (22 ids)", r["ncbi_gene"]["receipt"]["url"], "NCBI Gene ids from ZFIN gene.txt", "esummary JSON", None, "NCBI's data-use policy was not fetched", "public E-utilities", r["ncbi_gene"]["receipt"], [r["ncbi_gene"]["artifact"]],
         "full response", "coordinates are on NCBI's CURRENT assembly (e.g. NC_141022.1), not GRCz11")
    card("ucsc-danrer11-search", "UCSC genome search, danRer11 (5 genes)", "https://api.genome.ucsc.edu/search?genome=danRer11", "danRer11 = GRCz11 (GCA_000002035.4)", "positionMatches, ncbiRefSeq tracks", None, "UCSC terms not fetched", "public API",
         r["zfin_gff"]["receipt"] | {"retrieved_at": r["ncbi_gene"]["receipt"]["retrieved_at"], "sha256": r["ucsc_danrer11"]["artifact"]["sha256"], "bytes": r["ucsc_danrer11"]["artifact"]["bytes"], "last_modified": None, "http_status": 200},
         [r["ucsc_danrer11"]["artifact"]], "full responses", "5 genes only; search positions, 0-based start in the display")
    card("ncbi-assembly-gca-018398805", "NCBI Assembly record, Hirundichthys_speculiger_1.0", "https://www.ncbi.nlm.nih.gov/assembly/GCA_018398805.1", "GCA_018398805.1", "esummary uid 10071681", None, "NCBI policy not fetched", "public E-utilities",
         r["ncbi_assembly_flyingfish"]["receipt"], [r["ncbi_assembly_flyingfish"]["artifact"]], "full response", "GenBank only; no RefSeq; scaffold level")
    card("ncbi-bioproject-prjna714815", "NCBI BioProject PRJNA714815", "https://www.ncbi.nlm.nih.gov/bioproject/714815", "PRJNA714815", "esummary uid 714815", None, "NCBI policy not fetched", "public E-utilities",
         r["ncbi_bioproject"]["receipt"], [r["ncbi_bioproject"]["artifact"]], "full response", "record metadata only")
    card("pmc8294118-fulltext", "Draft Genome of the Mirrorwing Flyingfish, Front Genet 2021 (full text)", "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8294118/", "PMC8294118; doi:10.3389/fgene.2021.695700", "article body sections", "CC BY",
         "read from the article's own license statement and Europe PMC metadata ('cc by'); version not stated", "open access", r["pmc_mirrorwing_xml"]["receipt"], [r["pmc_mirrorwing_xml"]["artifact"], r["epmc_mirrorwing"]["artifact"]],
         "full-text", "figure and supplementary-table content not read")
    fa = f["article"]
    card("figshare-14600634-article", "figshare dataset 14600634 metadata (flyingfish genome and annotation)", "https://doi.org/10.6084/m9.figshare.14600634.v1", "figshare 14600634 (doi 10.6084/m9.figshare.14600634.v1)", "article JSON incl. file list, sizes, MD5",
         "CC BY 4.0", "read from the figshare API record's license field", "public API", fa["receipt"], [fa["artifact"]], "full response", "metadata only")
    for fname, key in (("Hirundichthys_speculiger.gene.gff", "gff"), ("Hirundichthys_speculiger.pep.fa", "pep"), ("Hirundichthys_speculiger.pep.fa.blast.swissprot.xls", "swissprot")):
        fr = f["files"][fname]
        arts = {"gff": [f["gff_selected"]], "pep": [f["peptides_selected"]], "swissprot": [f["swissprot_best_hits_selected"]["artifact"]]}[key]
        card(f"figshare-14600634-{key}", f"figshare 14600634 file {fname}", "https://ndownloader.figshare.com/files/" + {"gff": "28029993", "pep": "28029996", "swissprot": "28030008"}[key], fname,
             "selected rows / records", "CC BY 4.0", "from the dataset's figshare license field", "public download (302 to a signed S3 URL)", fr["receipt"], arts, "full-file stream; md5 and size match figshare's declaration",
             "predicted gene models; HsScaf/GHS id mapping is an inference tested on lengths (flyingfish_receipts.json id_mapping_test)", version=f"figshare md5 {fr['figshare_md5']}")
    for key, pmc, what in (("epmc_daane", "PMC9172250", "Daane et al. 2021, Current Biology (abstract only)"), ("epmc_daniocell", "PMC11181902", "Daniocell paper, Dev Cell 2023 (abstract only)")):
        card(f"europepmc-{pmc.lower()}", f"Europe PMC record for {what}", f"https://europepmc.org/article/PMC/{pmc}", pmc, "Europe PMC core record (title, abstract, license field)", None, "Europe PMC reports no open licence; article not open access",
             "metadata public; full text not accessible", r[key]["receipt"], [r[key]["artifact"]], "abstract", "full text could-not-access: Europe PMC fullTextXML returned HTTP 500")
    dc = r["daniocell_clusters"]
    card("daniocell-cluster-annotations", "Daniocell cluster_annotations.csv", "https://daniocell.nichd.nih.gov/assets/obj-download/cluster_annotations.csv", "Daniocell2023 (GEO GSE223922)", "all 521 rows", None,
         "no licence statement found on the pages read", "public download", dc["receipt"], [dc["artifact"]], "full file", "cluster-level table; no cell counts or per-gene values")
    pages = r["daniocell_pages"]
    card("daniocell-gene-pages", "Daniocell gene pages (22 genes)", "https://daniocell.nichd.nih.gov/gene/", "Daniocell gene pages", "correlation table and tissue-group thumbnails per page", None, "no licence statement found on the pages read", "public pages",
         pages["kcnh2a"]["receipt"], [v["artifact"] for k, v in sorted(pages.items()) if v.get("status") == "ok"] + [v["artifact"] for v in r["daniocell_dotplots"].values() if "artifact" in v], "full pages",
         "the dot-plot SVGs are glyph paths and were stored but not parsed; the 'noexp' placeholder's meaning is not stated in the bytes read", version="retrieved " + pages["kcnh2a"]["receipt"]["retrieved_at"])
    card("daniocell-landing", "Daniocell landing page", "https://daniocell.nichd.nih.gov/", "Daniocell", "'62 stages', '19 broad tissue types', GEO accession", None, "no licence statement found", "public page", x["daniocell_landing"]["receipt"],
         [x["daniocell_landing"]["artifact"]], "full page", "site statements, not verified against the data")
    card("uniprot-slc43a2-zebrafish", "UniProt search gene:slc43a2* organism 7955", x["uniprot_slc43a2"]["receipt"]["url"], "UniProt (5 entries)", "recommended and synonym names", None, "UniProt terms not fetched", "public REST API",
         x["uniprot_slc43a2"]["receipt"], [x["uniprot_slc43a2"]["artifact"]], "full response", "names only")
    zh = x["zebrahub"]
    card("zebrahub-pages", "Zebrahub landing pages and public file listing", "https://zebrahub.sf.czbiohub.org/", "Zebrahub", "/transcriptomics, /epigenomics, /data and the public listing", None, "no licence read; the Data page states a release policy (not parsed here)", "public pages",
         zh["transcriptomics"]["receipt"], [v["artifact"] for v in zh.values()], "landing pages and directory listings only", "no gene-level or cell-level data was fetched; atlas objects were not located")
    (OUT / "sources.json").write_text(json.dumps({"sources_schema": "genomics-sources-0.1 (connector-local)", "retrieved": "2026-10-31", "cards": cards}, indent=1, sort_keys=True))
    print(len(cards), "cards;", sum(len(c["artifacts"]) for c in cards), "artifact refs;", sum(1 for c in cards if c["license"]), "with a stated licence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
