"""Derive the typed, bounded index from the fetched artifacts. Deterministic: the same artifacts give the same files.

Reads data/genomics/artifacts/ (written by fetch_slice and fetch_flyingfish); fetches only the Zebrahub landing pages and the
UniProt synonym check, which are small and recorded in data/genomics/extra_receipts.json.

  PYTHONPATH=. python3 -m connectors.genomics.build_index
"""

from __future__ import annotations

import collections
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from . import sources as S
from .genes import GENES

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "genomics"
ART = OUT / "artifacts"
FIN = re.compile(r"\bfins?\b|fin fold|fin bud|fin ray|pectoral|actinotrichia|lepidotrichia|apical ectodermal", re.I)   # word-bounded: a bare "fin" would match "definitive"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rows(name: str):
    return [l.rstrip("\n").split("\t") for l in (ART / name).read_text().splitlines() if l.strip()]


def write_csv(name: str, header: list[str], data: list[list]) -> None:
    with open(OUT / name, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(data)


def main() -> int:
    (OUT / "plots").mkdir(exist_ok=True)
    zfin = {r[2]: r[0] for r in rows("zfin_gene_selected.tsv")}
    ncbi_id = {r[2]: r[3] for r in rows("zfin_gene_selected.tsv")}
    ens = {r[2]: r[3] for r in rows("zfin_ensembl_1_to_1_selected.tsv")}
    # --- ZFIN GRCz11 gene models (gene rows only)
    loc = {}
    for l in (ART / "zfin_genes_selected.gff3").read_text().splitlines():
        c = l.split("\t")
        if len(c) > 8 and c[2] == "gene":
            gid = re.search(r"ID=(ZDB-GENE-[^;]+)", c[8])
            if gid:
                loc[gid.group(1)] = (c[0], int(c[3]), int(c[4]), c[6])
    # --- NCBI Gene (current NCBI assembly; may not be GRCz11)
    ng = json.loads((ART / "ncbi_gene_summaries.json").read_text())["result"]
    ncbi_loc = {}
    for sym, gid in ncbi_id.items():
        gi = (ng.get(gid, {}).get("genomicinfo") or [{}])[0]
        ncbi_loc[sym] = (gi.get("chraccver"), gi.get("chrstart"), gi.get("chrstop"))
    # --- ZFIN expression / phenotype
    exp, ph = rows("zfin_expression_selected.tsv"), rows("zfin_phenotype_selected.tsv")
    exp_by, ph_by = collections.defaultdict(list), collections.defaultdict(list)
    for r in exp:
        exp_by[r[1]].append(r)
    for r in ph:
        ph_by[r[1]].append(r)

    def ph_fields(r):
        k = next(i for i, x in enumerate(r) if x.startswith("PATO:"))      # anchor on the quality term; the structure term before it may be ZFA or GO
        return {"structure": r[k - 1], "pato_id": r[k], "quality": r[k + 1], "tag": r[k + 2], "fish": r[-7], "genotype": re.sub(r"<[^>]+>", "", r[-6]), "pub": r[-3]}

    fly = json.loads((OUT / "flyingfish_receipts.json").read_text())
    ff_by = collections.defaultdict(list)
    for g in fly["selected_genes"]:
        for z in g["zebrafish_gene"].split("/"):
            ff_by[z.replace("slc43a2", "slc43a2")].append(g)
    ff_by["slc43a2a"] = ff_by.pop("slc43a2a", []) + [g for g in fly["selected_genes"] if g["symbol_hit"] == "SLC43A2"]
    ff_by["slc43a2b"] = list(ff_by["slc43a2a"])

    genes_out = []
    for sym, role in GENES.items():
        z = zfin[sym]
        c, st, en, strand = loc.get(z, (None, None, None, None))
        nl = ncbi_loc[sym]
        e, p = exp_by[sym], [ph_fields(r) for r in ph_by[sym]]
        ffg = [g for g in ff_by.get(sym, []) if g["usable"]]
        genes_out.append([sym, role, z, ens.get(sym, ""), ncbi_id[sym], c or "", st or "", en or "", strand or "", len(e), sum(1 for r in e if FIN.search(r[4] + r[6])),
                          len(p), sum(1 for x in p if FIN.search(x["structure"])), nl[0] or "", nl[1] or "", nl[2] or "", len(ffg)])
    write_csv("genes.csv", ["symbol", "role", "zfin_id", "ensembl_gene", "ncbi_gene_id", "zfin_gff_chr", "zfin_gff_start", "zfin_gff_end", "zfin_gff_strand", "zfin_expression_rows",
                            "zfin_fin_expression_rows", "zfin_phenotype_rows", "zfin_fin_phenotype_rows", "ncbi_current_chr_accession", "ncbi_current_start", "ncbi_current_stop",
                            "flyingfish_length_consistent_best_hit_models"], genes_out)
    # --- assembly / coordinate check
    ucsc = json.loads((ART / "ucsc_danrer11_search.json").read_text())
    chk = {}
    for g, v in ucsc.items():
        z = loc.get(zfin[g])
        pos = [m["position"] for t in v["response"].get("positionMatches", []) for m in t.get("matches", []) if t["name"].startswith("ncbiRefSeq")]
        hits = []
        for ptxt in pos:
            m = re.fullmatch(r"chr(\w+):(\d+)-(\d+)", ptxt)
            if m and z:
                a, b = int(m.group(2)) + 1, int(m.group(3))     # UCSC display: start shown 0-based
                ov = max(0, min(b, z[2]) - max(a, z[1]) + 1) if m.group(1) == z[0] else 0
                hits.append({"ucsc_position": ptxt, "same_chromosome": m.group(1) == z[0], "overlap_bp": ov, "ucsc_length": b - a + 1, "start_diff_bp": a - z[1], "end_diff_bp": b - z[2]})
        nl = ncbi_loc[g]
        overlap_ncbi = bool(z and nl[0] and nl[1] and z[0] == str(ng[ncbi_id[g]]["chromosome"]) and nl[1] <= z[2] and z[1] <= nl[2])
        chk[g] = {"zfin_gff": {"chr": z[0], "start": z[1], "end": z[2], "strand": z[3]} if z else None, "ucsc_danrer11_refseq_matches": hits,
                  "ncbi_gene_current": {"chraccver": nl[0], "start": nl[1], "stop": nl[2]}, "ncbi_current_overlaps_zfin_span": overlap_ncbi}
    best_hits = [max(v["ucsc_danrer11_refseq_matches"], key=lambda h: h["overlap_bp"]) for v in chk.values() if v["ucsc_danrer11_refseq_matches"]]
    READING = (f"For all {len(best_hits)} genes checked, UCSC danRer11's RefSeq match overlaps ZFIN's GRCz11 gene span on the same chromosome (best overlaps {min(h['overlap_bp'] for h in best_hits):,} to {max(h['overlap_bp'] for h in best_hits):,} bp). "
               f"Boundaries are NOT identical: start offsets {min(h['start_diff_bp'] for h in best_hits):,} to {max(h['start_diff_bp'] for h in best_hits):,} bp, end offsets {min(h['end_diff_bp'] for h in best_hits):,} to {max(h['end_diff_bp'] for h in best_hits):,} bp "
               "(different annotations draw gene ends differently). NCBI Gene's current record is on a different assembly: it overlaps the ZFIN span for none of the genes (offsets of megabases), so its coordinates are carried only with their accession and never joined to GRCz11 rows.")
    (OUT / "assembly_check.json").write_text(json.dumps({
        "grcz11": {"genbank": "GCA_000002035.4", "source": "Ensembl REST /info/assembly/danio_rerio (read 2026-10-31); UCSC danRer11 sourceName 'GRCz11 (GCA_000002035.4)'"},
        "conventions": {"zfin_gff3": "1-based inclusive, strand as stated, chromosome names without 'chr'", "ucsc_search_position": "chr-prefixed; the displayed start is 0-based",
                        "ncbi_gene": "accession.version contigs of NCBI's CURRENT annotation; NC_141022.1 is not a GRCz11 chromosome accession"},
        "reading": READING,
        "genes_checked_against_ucsc": chk}, indent=1, sort_keys=True))
    # --- lat4a resolution
    aliases = [r for r in rows("zfin_aliases_selected.tsv") if re.search(r"lat4", " ".join(r), re.I)]
    body, r = S.fetch("https://rest.uniprot.org/uniprotkb/search?query=gene:slc43a2*+AND+organism_id:7955&fields=accession,gene_names,protein_name,length,reviewed&format=json&size=10", 1_000_000)
    up = json.loads(body)["results"]
    (ART / "uniprot_slc43a2_zebrafish.json").write_bytes(body)
    extra = {"uniprot_slc43a2": {"receipt": r.to_dict(), "artifact": {"path": "data/genomics/artifacts/uniprot_slc43a2_zebrafish.json", "sha256": sha(ART / "uniprot_slc43a2_zebrafish.json")}}}
    names = [{"accession": u["primaryAccession"], "gene": u["genes"][0]["geneName"]["value"], "synonyms": [s["value"] for s in u["genes"][0].get("synonyms", [])],
              "protein_name": (u["proteinDescription"].get("recommendedName") or u["proteinDescription"].get("submissionNames", [{}])[0]).get("fullName", {}).get("value"), "reviewed": u["entryType"]} for u in up]
    (OUT / "lat4a_resolution.json").write_text(json.dumps({
        "question": "Which ZFIN gene is the 'lat4a' of Daane et al. 2021 (named in the abstract as 'an L-type amino acid transporter, lat4a')?",
        "status": "UNRESOLVED",
        "checked": {"zfin_gene_txt_symbol_lat4a": "absent (ZFIN gene.txt, retrieved 2026-10-31)", "zfin_aliases_rows_containing_lat4": len(aliases), "ncbi_gene_esearch_lat4a_danio": "0 hits (esearch 'lat4a', 2026-10-31)",
                    "uniprot_zebrafish_gene_lat4_or_protein_name_lat4": "0 results (2026-10-31)", "paper_full_text": "could-not-access: PMC9172250 is not open access; Europe PMC fullTextXML returned HTTP 500"},
        "candidates": {"slc43a2a": {"zfin": zfin["slc43a2a"], "note": "ZFIN name 'solute carrier family 43 member 2a'; no lat4 alias"},
                       "slc43a2b": {"zfin": zfin["slc43a2b"], "note": "UniProt names the product 'Large neutral amino acids transporter small subunit 4', which matches 'LAT4' in the L-type amino acid transporter naming"}},
        "uniprot_entries_read": names,
        "reading": "The abstract's 'lat4a' is not a current ZFIN symbol or alias. slc43a2a and slc43a2b are candidates by name only; neither is confirmed, and the 'a' suffix does not establish which paralog. Do not key any record on lat4a.",
        "limits": "No sequence, synteny or paper-figure evidence was read. Resolving it needs the paper's methods or supplement (not open access) or the authors' gene identifiers."}, indent=1, sort_keys=True))
    # --- Daniocell: coverage counts, correlations, tissue-group signal
    cl = list(csv.DictReader(open(ART / "daniocell_cluster_annotations.csv", encoding="utf-8-sig")))
    tissue_counts = collections.Counter(x["tissue"] or "(blank)" for x in cl)
    subsets = collections.Counter(x["tissue.subsets"] or "(blank)" for x in cl)
    fin_clusters = [x for x in cl if FIN.search(x["tissue"] + " " + x["identity.super"] + " " + x["identity.sub"])]
    corr, thumbs = [], []
    for sym in GENES:
        pth = ART / f"daniocell_page_{sym}.html"
        if not pth.exists():
            continue
        t = pth.read_text(errors="ignore")
        for m in re.finditer(r'<tr><td><a href="[^"]*">([^<]+)</a></td><td>(-?[\d.]+)</td><td><a href="[^"]*">([^<]+)</a></td><td>(-?[\d.]+)</td></tr>', t):
            corr.append([sym, "positive", m.group(1), m.group(2)])
            corr.append([sym, "negative", m.group(3), m.group(4)])
        for m in re.finditer(r'<img src="(?:\.\./\.\./noexp/noexp_thumb_(\w+)\.png|' + re.escape(sym) + r'_thumb_(\w+)\.png)"', t):
            thumbs.append([sym, m.group(1) or m.group(2), "placeholder_noexp" if m.group(1) else "gene_thumbnail"])
    write_csv("daniocell_correlations.csv", ["gene", "direction", "partner_gene", "r_all_cells"], corr)
    write_csv("daniocell_tissue_group_thumbnails.csv", ["gene", "tissue_group_code", "thumbnail_kind"], thumbs)
    fin_thumb = {g: next((k for gg, code, k in thumbs if gg == g and code == "fin"), "no_page_thumbnail") for g in GENES}
    # --- Zebrahub landing facts (small pages; counts are the site's own statements)
    zh = {}
    for key, url in (("transcriptomics", "https://zebrahub.sf.czbiohub.org/transcriptomics"), ("epigenomics", "https://zebrahub.sf.czbiohub.org/epigenomics"), ("data", "https://zebrahub.sf.czbiohub.org/data"),
                     ("public_listing_root", "https://public.czbiohub.org/royerlab/zebrahub/"), ("public_listing_sequencing", "https://public.czbiohub.org/royerlab/zebrahub/sequencing/"),
                     ("public_listing_imaging", "https://public.czbiohub.org/royerlab/zebrahub/imaging/")):
        body, r = S.fetch(url, 2_000_000)
        (ART / f"zebrahub_{key}.html").write_bytes(body)
        zh[key] = {"receipt": r.to_dict(), "artifact": {"path": f"data/genomics/artifacts/zebrahub_{key}.html", "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}}
    extra["zebrahub"] = zh
    body, r = S.fetch("https://daniocell.nichd.nih.gov/", 2_000_000)
    (ART / "daniocell_index.html").write_bytes(body)
    extra["daniocell_landing"] = {"receipt": r.to_dict(), "artifact": {"path": "data/genomics/artifacts/daniocell_index.html", "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}}
    landing = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", "", body.decode(errors="ignore"), flags=re.S)))
    for need in ("62 stages of development, spanning 3.3&ndash;120 hours post-fertilization", "19 broad tissue types", "GSE223922"):
        if need not in landing and need.replace("&ndash;", "–") not in landing:
            raise SystemExit(f"Daniocell landing page no longer states: {need}")
    (OUT / "extra_receipts.json").write_text(json.dumps(extra, indent=1, sort_keys=True))
    # --- ZFIN summaries
    ex_rows = []
    for sym in GENES:
        for r in exp_by[sym]:
            ex_rows.append([sym, r[0], r[4], r[6], r[7], r[8], r[9], r[11]])
    write_csv("zfin_expression_selected.csv", ["symbol", "zfin_id", "structure", "sub_structure", "start_stage", "end_stage", "assay", "publication"], ex_rows)
    ph_rows = []
    for sym in GENES:
        for x in (ph_fields(r) for r in ph_by[sym]):
            ph_rows.append([sym, zfin[sym], x["structure"], x["quality"], x["tag"], x["genotype"], x["fish"], x["pub"]])
    write_csv("zfin_phenotype_selected.csv", ["symbol", "zfin_id", "affected_structure", "quality", "tag", "genotype_display", "fish_id", "publication"], ph_rows)
    # --- flying fish paper + assembly facts (read from the committed bytes)
    root = ET.parse(ART / "PMC8294118_fulltext.xml").getroot()
    txt = lambda e: re.sub(r"\s+", " ", "".join(e.itertext())).strip()
    facts = []
    for sec in root.iter("sec"):
        t = sec.find("title")
        title = txt(t) if t is not None else ""
        for p in sec.findall("p"):
            s = txt(p)
            for key, rx in (("assembly_size", r"1\.04-Gb genome assembly"), ("contig_n50_paper", r"contig N50 of 992\.83 kb"), ("scaffold_n50_paper", r"scaffold N50 of 1,152\.47 kb"),
                            ("protein_coding_genes", r"predicted 23,611 protein-coding genes"), ("busco_genome", r"94\.2% of the Actinopterygii"), ("busco_genes", r"95\.7% of the Actinopterygii"),
                            ("data_availability", r"PRJNA714815")):
                m = re.search(rx, s)
                if m and not any(f["key"] == key for f in facts):
                    facts.append({"key": key, "section": title, "excerpt": s[max(0, m.start() - 60): m.end() + 120]})
    asm = json.loads((ART / "ncbi_assembly_GCA_018398805.1.json").read_text())["result"]["10071681"]
    (OUT / "flyingfish_genome_facts.json").write_text(json.dumps({
        "species": "Hirundichthys speculiger (mirrorwing flyingfish)", "paper": {"pmcid": "PMC8294118", "doi": "10.3389/fgene.2021.695700", "license": "CC BY (Europe PMC metadata and the article's license statement)", "read_level": "full-text"},
        "paper_statements": facts,
        "ncbi_assembly": {"accession": asm["assemblyaccession"], "name": asm["assemblyname"], "status": asm["assemblystatus"], "released": asm["seqreleasedate"], "contig_n50": asm["contign50"], "scaffold_n50": asm["scaffoldn50"],
                          "refseq": asm["synonym"]["refseq"] or None, "bioproject_in_ncbi": "PRJNA714815 resolves (uid 714815)"},
        "disagreements": [{"quantity": "contig N50", "paper": "992.83 kb", "ncbi_assembly_record": f"{asm['contign50']:,} bp", "note": "scaffold N50 agrees (1,152.47 kb vs 1,152,470 bp); not reconciled here"}],
        "annotation": {"where": "figshare 10.6084/m9.figshare.14600634.v1 (CC BY 4.0), not in the GenBank assembly record", "gene_models": fly["annotation_totals"]["mRNA_in_gff"], "note": "the paper states 23,611 predicted protein-coding genes; the GFF has 23,611 mRNAs"},
        "limits": ["One species. No other flying-fish species is assumed annotated.", "Gene models are predictions (GeneWise and others), functional names are BLAST best hits, not orthology."]}, indent=1, sort_keys=True))
    # --- the index
    zh_t = (ART / "zebrahub_transcriptomics.html").read_text(errors="ignore")
    index = {
        "index_schema": "genomics-index-0.1 (connector-local; no root schema changed)", "retrieved": "2026-10-31", "namespace_note": "records use namespace node-a; corpus remaps",
        "assemblies": [{"species": "Danio rerio", "assembly": "GRCz11", "genbank": "GCA_000002035.4", "coordinate_source": "ZFIN GFF3 (checked against UCSC danRer11)", "annotation": "ZFIN genes"},
                       {"species": "Hirundichthys speculiger", "assembly": "Hirundichthys_speculiger_1.0", "genbank": "GCA_018398805.1", "refseq": None, "annotation": "figshare 14600634 (CC BY 4.0), predicted gene models"}],
        "datasets": [
            {"id": "zfin-wildtype-expression", "species": "Danio rerio", "evidence_class": "expression_correlation", "rows_selected": len(exp), "artifact": "data/genomics/zfin_expression_selected.csv", "nature": "literature-curated; sparse for most of these genes"},
            {"id": "zfin-phenotype", "species": "Danio rerio", "evidence_class": "genotype_phenotype", "rows_selected": len(ph), "artifact": "data/genomics/zfin_phenotype_selected.csv", "nature": "literature-curated mutant/morphant annotations"},
            {"id": "daniocell", "species": "Danio rerio", "evidence_class": "expression_correlation", "stages": 62, "hpf_range": [3.3, 120], "broad_tissue_types": 19, "clusters_in_annotation_file": len(cl),
             "clusters_by_tissue": dict(tissue_counts.most_common()), "fin_labelled_clusters": len(fin_clusters), "fin_cluster_share_pct": round(100 * len(fin_clusters) / len(cl), 2), "geo": "GSE223922",
             "artifact": "data/genomics/daniocell_correlations.csv", "limits": "cluster counts, not cell counts; the paper (PMC11181902) is not open access and was not read"},
            {"id": "zebrahub", "species": "Danio rerio", "evidence_class": "expression_correlation", "access": "landing pages and public listing read only; no gene-level subset fetched",
             "transcriptomics_site_statement": "10 stages, 40 embryos, ~120000 cells (the site's own statement on /transcriptomics)",
             "epigenomics_site_statement": "6 stages, 420 embryos, ~94000 cells, ~640000 ATAC peaks (site statement)"},
            {"id": "mirrorwing-annotation", "species": "Hirundichthys speculiger", "evidence_class": "sequence_annotation", "models": fly["annotation_totals"]["mRNA_in_gff"], "selected_length_consistent": fly["length_consistent_selected_genes"],
             "artifact": "data/genomics/artifacts/flyingfish_swissprot_best_hits_selected.tsv"}],
        "cell_states": [{"source": "daniocell", "cluster": x["clust"], "tissue": x["tissue"], "identity_super": x["identity.super"], "identity_sub": x["identity.sub"], "marker_genes": [x["ident.gene.1"], x["ident.gene.2"], x["ident.gene.3"]]} for x in fin_clusters],
        "genes": [dict(zip(["symbol", "role", "zfin_id", "ensembl_gene", "ncbi_gene_id", "zfin_gff_chr", "zfin_gff_start", "zfin_gff_end", "zfin_gff_strand", "zfin_expression_rows", "zfin_fin_expression_rows",
                            "zfin_phenotype_rows", "zfin_fin_phenotype_rows", "ncbi_current_chr_accession", "ncbi_current_start", "ncbi_current_stop", "flyingfish_models"], g)) | {"daniocell_fin_thumbnail": fin_thumb[g[0]], "species": "Danio rerio"} for g in genes_out],
        "unresolved": [{"symbol": "lat4a", "file": "data/genomics/lat4a_resolution.json", "status": "UNRESOLVED"}],
        "evidence_classes": ["expression_correlation", "genotype_phenotype", "causal_intervention", "sequence_annotation", "source_assessment"],
        "note": "cross-species statements are proposed_transfer and are never evidence; no causal_intervention data was fetched at figure level"}
    (OUT / "index.json").write_text(json.dumps(index, indent=1, sort_keys=True))
    print("genes", len(genes_out), "| expression rows", len(exp), "| phenotype rows", len(ph), "| daniocell clusters", len(cl), "fin-labelled", len(fin_clusters), "| correlations", len(corr), "| thumbs", len(thumbs))
    print("tissue counts", dict(tissue_counts.most_common(6)), "| fin thumbs:", collections.Counter(fin_thumb.values()))
    print({g: (v["ucsc_danrer11_refseq_matches"][:1], v["ncbi_current_overlaps_zfin_span"]) for g, v in chk.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
