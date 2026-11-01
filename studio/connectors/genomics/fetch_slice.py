"""Fetch the bounded raw slice and its receipts. Writes under data/genomics/artifacts/ and data/genomics/receipts.json.

  PYTHONPATH=. python3 -m connectors.genomics.fetch_slice
Network: zfin.org (about 200 MB streamed in all, nothing kept but the selected rows), NCBI E-utilities, UCSC, Europe PMC, Daniocell.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.parse
from pathlib import Path

from . import sources as S
from .genes import GENES

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "genomics"
ART = OUT / "artifacts"
SET = set(GENES)


def _write(name: str, data: bytes | str) -> dict:
    b = data.encode() if isinstance(data, str) else data
    (ART / name).write_bytes(b)
    import hashlib
    return {"path": f"data/genomics/artifacts/{name}", "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    rec: dict[str, dict] = {}

    def keep_cols(idx, symbols=SET):
        return lambda line: len(line.split("\t")) > idx and line.split("\t")[idx] in symbols

    # 1. identifiers (ZFIN download files; whole-file hashes, selected rows kept)
    for key, fname, idx in (("zfin_gene", "gene.txt", 2), ("zfin_ensembl", "ensembl_1_to_1.txt", 2)):
        body, r = S.fetch(f"https://zfin.org/downloads/{fname}", 5_000_000)
        rows = [l for l in body.decode().splitlines() if l.split("\t")[idx:idx + 1] and l.split("\t")[idx] in SET]
        rec[key] = {"receipt": r.to_dict(), "kept_rows": len(rows), "artifact": _write(f"zfin_{fname.split('.')[0]}_selected.tsv", "\n".join(rows) + "\n")}
    # ZFIN gene ids of the set, to filter the id-keyed files
    zdb = {l.split("\t")[0]: l.split("\t")[2] for l in (ART / "zfin_gene_selected.tsv").read_text().splitlines()}
    # 2. aliases: which ZFIN names carry 'lat4' (the Daane symbol), plus the selected genes' aliases
    kept, _, r = S.stream_lines("https://zfin.org/downloads/aliases.txt", lambda l: l.split("\t")[0] in zdb or re.search(r"\blat4", l, re.I) is not None, 50_000_000)
    rec["zfin_aliases"] = {"receipt": r.to_dict(), "kept_rows": len(kept), "artifact": _write("zfin_aliases_selected.tsv", "\n".join(kept) + "\n")}
    # 3. wildtype expression (literature-curated), phenotype (genotype/phenotype)
    for key, fname, idx in (("zfin_expression", "wildtype-expression_fish.txt", 1), ("zfin_phenotype", "phenoGeneCleanData_fish.txt", 1)):
        kept, _, r = S.stream_lines(f"https://zfin.org/downloads/{fname}", keep_cols(idx))
        rec[key] = {"receipt": r.to_dict(), "kept_rows": len(kept), "artifact": _write(f"zfin_{key.split('_')[1]}_selected.tsv", "\n".join(kept) + "\n")}
    # 4. ZFIN gene models (GFF3): keep every line that mentions a selected ZFIN gene id
    ids = set(zdb)
    kept, comments, r = S.stream_lines("https://zfin.org/downloads/zfin_genes.gff3", lambda l: any(i in l for i in ids))
    rec["zfin_gff"] = {"receipt": r.to_dict(), "kept_rows": len(kept), "header_comments": comments[:12],
                       "artifact": _write("zfin_genes_selected.gff3", "##gff-version 3\n" + "\n".join(kept) + "\n")}
    # 5. NCBI Gene summaries (current NCBI assembly, NOT necessarily GRCz11) and a UCSC danRer11 position check
    ncbi_ids = ",".join(l.split("\t")[3] for l in (ART / "zfin_gene_selected.tsv").read_text().splitlines())
    body, r = S.fetch(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=gene&id={ncbi_ids}&retmode=json", 5_000_000)
    rec["ncbi_gene"] = {"receipt": r.to_dict(), "artifact": _write("ncbi_gene_summaries.json", body)}
    ucsc = {}
    for g in ("kcnh2a", "kcnk5b", "fgf20a", "piezo1", "slc43a2a"):
        body, r = S.fetch(f"https://api.genome.ucsc.edu/search?search={g}&genome=danRer11", 2_000_000)
        ucsc[g] = {"receipt": r.to_dict(), "response": json.loads(body)}
    rec["ucsc_danrer11"] = {"artifact": _write("ucsc_danrer11_search.json", json.dumps(ucsc, indent=1, sort_keys=True))}
    # 6. flying fish: NCBI assembly + BioProject, Europe PMC metadata and the CC BY full text
    body, r = S.fetch("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=assembly&id=10071681&retmode=json", 2_000_000)
    rec["ncbi_assembly_flyingfish"] = {"receipt": r.to_dict(), "artifact": _write("ncbi_assembly_GCA_018398805.1.json", body)}
    body, r = S.fetch("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=bioproject&id=714815&retmode=json", 2_000_000)
    rec["ncbi_bioproject"] = {"receipt": r.to_dict(), "artifact": _write("ncbi_bioproject_PRJNA714815.json", body)}
    for key, pmc in (("epmc_mirrorwing", "PMC8294118"), ("epmc_daane", "PMC9172250"), ("epmc_daniocell", "PMC11181902")):
        body, r = S.fetch(f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=PMCID:{pmc}&format=json&resultType=core", 2_000_000)
        rec[key] = {"receipt": r.to_dict(), "artifact": _write(f"europepmc_{pmc}.json", body)}
    body, r = S.fetch("https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8294118/fullTextXML", 5_000_000)
    rec["pmc_mirrorwing_xml"] = {"receipt": r.to_dict(), "artifact": _write("PMC8294118_fulltext.xml", body)}
    # 7. Daniocell: cluster annotations (whole) and the gene pages of the set
    body, r = S.fetch("https://daniocell.nichd.nih.gov/assets/obj-download/cluster_annotations.csv", 2_000_000)
    rec["daniocell_clusters"] = {"receipt": r.to_dict(), "artifact": _write("daniocell_cluster_annotations.csv", body)}
    body, r = S.fetch("https://daniocell.nichd.nih.gov/assets/data/data.json", 5_000_000)
    index = {x["name"]: x["url"] for x in json.loads(body)}
    rec["daniocell_gene_index"] = {"receipt": r.to_dict(), "genes_in_index": {g: g in index for g in GENES}, "total_entries": len(index)}
    pages = {}
    for g in GENES:
        if g not in index:
            pages[g] = {"status": "not in Daniocell gene index"}
            continue
        url = "https://daniocell.nichd.nih.gov/" + index[g]
        try:
            body, r = S.fetch(url, 2_000_000)
        except S.FetchRefused as exc:
            pages[g] = {"status": f"refused: {exc}"}
            continue
        pages[g] = {"status": "ok", "receipt": r.to_dict(), "artifact": _write(f"daniocell_page_{g}.html", body)}
    rec["daniocell_pages"] = pages
    svgs = {}
    for g in ("kcnh2a", "kcnk5b", "fgf20a", "piezo1"):
        if pages.get(g, {}).get("status") == "ok":
            url = "https://daniocell.nichd.nih.gov/" + index[g].rsplit("/", 1)[0] + f"/{g}_dotplot_all.svg"
            try:
                body, r = S.fetch(url, 5_000_000)
                svgs[g] = {"receipt": r.to_dict(), "artifact": _write(f"daniocell_dotplot_{g}.svg", body)}
            except S.FetchRefused as exc:
                svgs[g] = {"status": f"refused: {exc}"}
    rec["daniocell_dotplots"] = svgs
    (OUT / "receipts.json").write_text(json.dumps(rec, indent=1, sort_keys=True))
    print("fetched", sum(1 for v in rec.values() if v), "groups;", sum(len(list(ART.glob('*'))) for _ in [0]), "artifact files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
