"""Sourced Claim / Evidence / Problem drafts (Frontier shapes), validated by frontier.models and the store's licence gate.

Every number in a statement is computed from the committed data files. Species is explicit; evidence class is one of
expression_correlation, genotype_phenotype, causal_intervention, sequence_annotation, source_assessment. Cross-species
statements are hypotheses, never evidence. Drafts are proposed: nothing is submitted, reviewed or accepted.

  PYTHONPATH=. python3 -m connectors.genomics.records
"""

from __future__ import annotations

import collections
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "genomics"
NS, ISSUER = "node-a", "genomics-worker"
CREATED_AT = "2026-10-31T20:30:00+00:00"        # declared when the drafts were written; not a claim about when the data were fetched
FIN = re.compile(r"\bfins?\b|fin fold|fin bud|fin ray|pectoral|actinotrichia|lepidotrichia|apical ectodermal", re.I)
EV_KIND = {"expression_correlation", "genotype_phenotype", "causal_intervention", "sequence_annotation", "source_assessment"}


def J(name):
    return json.loads((OUT / name).read_text())


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from frontier import models, store

    cards = {c["id"]: c for c in J("sources.json")["cards"]}
    index, fly, ffacts, assembly, lat4 = J("index.json"), J("flyingfish_receipts.json"), J("flyingfish_genome_facts.json"), J("assembly_check.json"), J("lat4a_resolution.json")
    ex = list(csv.DictReader(open(OUT / "zfin_expression_selected.csv")))
    ph = list(csv.DictReader(open(OUT / "zfin_phenotype_selected.csv")))
    corr = [r for r in csv.DictReader(open(OUT / "daniocell_correlations.csv")) if r["gene"] == "kcnh2a"]
    plots = {p["file"].split("/")[-1]: p for p in J("plots/plot_manifest.json")["plots"]}
    ncl = index["datasets"][2]
    kex = [r for r in ex if r["symbol"] == "kcnh2a"]
    fin_ph = collections.Counter(r["symbol"] for r in ph if FIN.search(r["affected_structure"]))
    all_ph = collections.Counter(r["symbol"] for r in ph)
    good = [g for g in fly["selected_genes"] if g["usable"]]
    bad = [g for g in fly["selected_genes"] if not g["usable"]]
    present = sorted({g["symbol_hit"] for g in good})
    absent = fly["swissprot_best_hits_selected"]["symbols_absent"]
    best = max(corr, key=lambda r: abs(float(r["r_all_cells"])))

    def src(card_id, locator, art=0, version=None):
        c = cards[card_id]
        a = c["artifacts"][art]
        return {"uri": c["uri"], "locator": locator, "source_version": version or c["version"], "content_sha256": a["sha256"], "content_available": c["license"] is not None,
                "access": f"{c['access']}; read level: {c['read_level']}; licence: {c['license'] or 'none stated in the bytes read'}", "license": c["license"]}

    def aref(path, title, media, role, lic=None):
        import hashlib
        b = (ROOT / path).read_bytes()
        h = hashlib.sha256(b).hexdigest()
        return {"title": f"{role}: {path} - {title}"[:3000], "uri": "urn:sha256:" + h, "sha256": h, "byte_size": len(b), "media_type": media, "role": role, "availability": "referenced", "license": lic}

    def claim(id_, title, statement, context, assumptions, limitations, source, origin):
        return {"namespace": NS, "kind": "Claim", "id": id_, "issuer": ISSUER, "source_uri": "urn:frontier:connector:genomics", "visibility": "public", "predecessor": None,
                "payload": {"title": title, "statement": statement, "context": context, "assumptions": assumptions, "limitations": limitations, "source": source, "origin": origin}}

    def problem(id_, title, known, question, kind, novelty, access, caps, uses, source, scales, tags, original=None):
        return {"namespace": NS, "kind": "Problem", "id": id_, "issuer": ISSUER, "source_uri": "urn:frontier:connector:genomics", "visibility": "public", "predecessor": None,
                "payload": {"title": title, "known_state": known, "question": question, "problem_kind": kind, "novelty_status": novelty, "data_access": access, "completeness": "recorded",
                            "required_capabilities": caps, "downstream_uses": uses, "dependencies": [], "source": source, "original": original or {}, "approach": "unknown", "scales": scales, "context_tags": tags}}

    drafts = []
    tag = lambda sp, cls, card: f"[species: {sp}; evidence_class: {cls}; source card: {card}] "
    # ---- claims
    drafts.append(claim("gx-daane-lat4a-kcnh2a-source", "Source assertion: a lat4a x kcnh2a interaction in zebrafish phenocopies flying-fish fin proportions",
        "The abstract of Daane et al. 2021 reports a phylogenomic analysis of genome-wide variation in 35 species of flying fishes and relatives, intersected with zebrafish fin-size mutants, and states that an L-type amino acid transporter, lat4a, "
        "and the potassium channel kcnh2a regulate fin proportion and that their interaction in zebrafish closely phenocopies the observed fin proportions of flying fishes.",
        tag("Danio rerio (experiment); 35 species incl. flying fishes (phylogenomics)", "genotype_phenotype, causal_intervention (as claimed by the source)", "europepmc-pmc9172250") +
        "A source statement at abstract level. The paper is not open access and its full text, figures and supplement were not read.", ["Abstract only."],
        ["No causal_intervention data was fetched: no figure-level or genotype-level data was read.", "'lat4a' is not a current ZFIN symbol (see gx-problem-lat4a-identity).", "Whether the result transfers to flying fish is the paper's proposal, not evidence here."],
        src("europepmc-pmc9172250", "Europe PMC core record, abstractText"), "source_statement"))
    drafts.append(claim("gx-mirrorwing-assembly-annotation", "Source assertion: mirrorwing flyingfish draft genome of 1.04 Gb with 23,611 predicted protein-coding genes",
        "Xu et al. (first author Xu P; author list from Europe PMC) state a 1.04 Gb assembly (contig N50 992.83 kb, scaffold N50 1,152.47 kb), 23,611 predicted protein-coding genes (99.5% functionally annotated), BUSCO completeness 94.2% (genome) and 95.7% (gene set, actinopterygii_odb9 4,584), "
        "with the assembly under BioProject PRJNA714815 and the annotation in figshare 10.6084/m9.figshare.14600634.v1.",
        tag("Hirundichthys speculiger", "sequence_annotation", "pmc8294118-fulltext") + "Read in the article's full text (CC BY). The statements are the authors' own numbers.",
        ["The article text is quoted by locator only; supplementary tables were not read."], ["One species.", "Gene models are predictions.", "Nothing here says another flying-fish species is annotated."],
        src("pmc8294118-fulltext", "Summary; Value of the Data; Summary of the Genome Assembly and Annotation; Data Availability Statement"), "source_statement"))
    drafts.append(claim("gx-mirrorwing-contig-n50-disagreement", "Source disagreement preserved: contig N50 of the mirrorwing assembly, paper versus NCBI record",
        "The paper states a contig N50 of 992.83 kb; the NCBI Assembly record GCA_018398805.1 reports 1,092,820 bp. The scaffold N50 agrees (1,152.47 kb versus 1,152,470 bp). This connector does not reconcile them.",
        tag("Hirundichthys speculiger", "source_assessment", "ncbi-assembly-gca-018398805") + "Two sources disagree on one number; both are kept.", [],
        ["Which figure describes the released scaffolds was not determined (no assembly sequence was downloaded).", "A 10% difference may reflect different contig definitions; that is a guess, not a finding."],
        src("ncbi-assembly-gca-018398805", "contign50 in esummary"), "derived"))
    drafts.append(claim("gx-mirrorwing-fin-set-best-hits", f"Annotation-derived: {len(good)} mirrorwing flyingfish gene models have a best SwissProt hit in the fin / mechanosensation gene set",
        f"In the authors' annotation (23,611 gene models), {len(good)} models whose inferred gene-model id passed a per-gene protein-length check and whose best-hit paralog is compatible with the set have a best SwissProt BLASTP hit named for one of the set's genes: {', '.join(present)}. "
        f"{len(bad)} further hits are not used (failed the length check, are a different zebrafish paralog, or are the fgf8 control). Each is a best-hit similarity (identity {min(g['identity_pct'] for g in good):.1f} to {max(g['identity_pct'] for g in good):.1f}%), not an orthology call, and paralogs (a/b) are not resolved.",
        tag("Hirundichthys speculiger", "sequence_annotation", "figshare-14600634-swissprot") + "BLAST tables and gene models use different ids; a position-rank mapping was tested against protein lengths "
        f"({fly['id_mapping_test']['strict_hypothesis']['rate']:.1%} agreement against {fly['id_mapping_test']['control_offset_plus1']['rate']:.1%} and {fly['id_mapping_test']['control_offset_minus1']['rate']:.1%} for one-gene shifts).",
        ["The id mapping is an inference, passed per gene by protein length only."], ["No synteny or reciprocal-best-hit check.", "Absence of a symbol among best hits is not absence from the genome."],
        src("figshare-14600634-swissprot", "flyingfish_swissprot_best_hits_selected.tsv, flyingfish_selected_gene_models.gff3, flyingfish_selected_proteins.faa"), "derived"))
    drafts.append(claim("gx-mirrorwing-kcnh2-not-best-hit", f"Annotation-derived: {', '.join(absent)} are not best SwissProt hits of any mirrorwing gene model",
        f"No mirrorwing gene model has a best SwissProt hit named {', '.join(absent)}. {fly['absent_symbols_any_hit']['KCNH2']['hits']} hits to KCNH2 exist (on {fly['absent_symbols_any_hit']['KCNH2']['distinct_queries']} distinct gene models) but those models' best hits are other genes (for example KCNH7); "
        "HOXD13 and FGF24 have no hit at all in the table. This describes this annotation of one assembly, not the genome.",
        tag("Hirundichthys speculiger", "sequence_annotation", "figshare-14600634-swissprot") + "Relevant because kcnh2a is half of the Daane fin-proportion story; it is NOT evidence that kcnh2 is missing from the species.", [],
        ["A missing best hit can mean an incomplete or fragmented annotation, a divergent sequence or a naming difference.", "A direct search of the scaffold sequence was not done."],
        src("figshare-14600634-swissprot", "absent_symbols_any_hit in flyingfish_receipts.json"), "derived"))
    drafts.append(claim("gx-zfin-kcnh2a-expression-annotations", f"Curated database content: ZFIN holds {len(kex)} wildtype expression annotations for kcnh2a, all by RT-PCR",
        f"ZFIN's wildtype-expression table has {len(kex)} rows for kcnh2a (zebrafish): {sum(1 for r in kex if r['start_stage']=='Adult')} adult tissue rows including 'fin' and 'regenerating fin' (publication {next(r['publication'] for r in kex if r['structure']=='fin')}) and "
        f"{sum(1 for r in kex if r['structure']=='whole organism')} whole-organism rows across embryonic and larval stages. Assay: {', '.join(sorted({r['assay'] for r in kex}))} only; no in situ annotation.",
        tag("Danio rerio", "expression_correlation", "zfin-wildtype-expression-fish") + "Literature-curated presence annotations, not levels, not an experiment by this connector.", [],
        ["Absent annotations mean not curated, not not expressed.", "RT-PCR on whole tissue does not localise expression to cell types.", "The ZFIN publication id was not resolved to a citation here."],
        src("zfin-wildtype-expression-fish", "rows with gene symbol kcnh2a"), "derived"))
    drafts.append(claim("gx-zfin-kcnh2a-no-phenotype-rows", "Curated database content: ZFIN's phenotype table has no rows for kcnh2a",
        f"ZFIN's gene phenotype file (phenoGeneCleanData_fish.txt) has {all_ph.get('kcnh2a', 0)} rows for kcnh2a at retrieval, while kcnk5b has {all_ph['kcnk5b']} and kcnj13 has {all_ph['kcnj13']}.",
        tag("Danio rerio", "genotype_phenotype", "zfin-phenogenecleandata-fish") + "A statement about ZFIN's curation at one retrieval time.", [],
        ["It does not say kcnh2a mutants have no phenotype; the Daane experiments may not be curated yet.", "Only this one file was read."],
        src("zfin-phenogenecleandata-fish", "rows with gene symbol kcnh2a (none)"), "derived"))
    top = ", ".join(f"{g} {fin_ph[g]}/{all_ph[g]}" for g, _ in fin_ph.most_common(6))
    drafts.append(claim("gx-zfin-fin-phenotype-annotations", f"Curated database content: ZFIN fin-related phenotype annotations for the gene set ({sum(fin_ph.values())} rows)",
        f"Of {sum(all_ph.values())} ZFIN phenotype rows for the 22 selected genes, {sum(fin_ph.values())} have an affected structure naming a fin, fin fold, fin bud or pectoral structure. Largest counts (fin rows/all rows): {top}.",
        tag("Danio rerio", "genotype_phenotype", "zfin-phenogenecleandata-fish") + "Curated mutant and morphant annotations; association of a genotype with a phenotype, not a mechanism.", [],
        ["Counts reflect curation effort as much as biology.", "A row can describe a morphant or a multi-gene genotype.", "Fin-term matching is by word, not by ontology closure."],
        src("zfin-phenogenecleandata-fish", "affected structure terms matching fin"), "derived"))
    clt = ncl["clusters_by_tissue"]
    drafts.append(claim("gx-daniocell-coverage", f"Source coverage: Daniocell annotates {ncl['clusters_in_annotation_file']} clusters over {ncl['stages']} stages; {ncl['fin_labelled_clusters']} carry a fin label ({ncl['fin_cluster_share_pct']}%)",
        f"The Daniocell landing page states whole-animal wild-type zebrafish data across 62 stages (3.3-120 hpf) in 19 broad tissue types (GEO GSE223922). The cluster annotation file has {ncl['clusters_in_annotation_file']} clusters; "
        f"{ncl['fin_labelled_clusters']} ({ncl['fin_cluster_share_pct']}%) have a fin label ('fin epithelia' {clt.get('fin epithelia')}, 'fin mesenchyme' {clt.get('fin mesenchyme')}, others by identity), against 'neural' {clt.get('neural')} and 'eye' {clt.get('eye')}. "
        "Embryos and larvae only: adult and regenerating fin are not covered.",
        tag("Danio rerio", "source_assessment", "daniocell-cluster-annotations") + "Cluster counts, not cell counts.", [],
        ["The Daniocell paper (PMC11181902) is not open access and was not read; no per-stage cell counts were obtained.", "Cluster number reflects annotation granularity, not tissue size."],
        src("daniocell-cluster-annotations", "all 521 rows; landing-page statements in daniocell-landing"), "derived"))
    drafts.append(claim("gx-daniocell-kcnh2a-correlations", f"Expression correlation (weak): the genes most correlated with kcnh2a across all Daniocell cells have |r| at most {abs(float(best['r_all_cells'])):.3f}",
        f"On the Daniocell kcnh2a all-cells page the top positive correlation is {best['partner_gene']} (r = {best['r_all_cells']}) and the listed correlations are all small; the page lists {sum(1 for r in corr if r['direction']=='positive')} positive and {sum(1 for r in corr if r['direction']=='negative')} negative partners.",
        tag("Danio rerio", "expression_correlation", "daniocell-gene-pages") + "Co-variation of expression across whole-animal cells. It shows neither interaction nor regulation nor function.", [],
        ["All-cells correlation mixes tissues and stages.", "kcnh2a pages for individual tissues were not read."],
        src("daniocell-gene-pages", "kcnh2a page, correlation table (data/genomics/daniocell_correlations.csv)"), "derived"))
    ck = assembly["genes_checked_against_ucsc"]["kcnh2a"]
    drafts.append(claim("gx-ncbi-gene-coordinates-are-not-grcz11", "Coordinate convention: NCBI Gene's current coordinates for the gene set are not GRCz11",
        f"For kcnh2a, NCBI Gene returns chr2 accession {ck['ncbi_gene_current']['chraccver']}, {ck['ncbi_gene_current']['start']:,}-{ck['ncbi_gene_current']['stop']:,}; ZFIN's GRCz11 span is chr{ck['zfin_gff']['chr']}:{ck['zfin_gff']['start']:,}-{ck['zfin_gff']['end']:,}, "
        f"which UCSC danRer11's RefSeq match ({ck['ucsc_danrer11_refseq_matches'][0]['ucsc_position']}) overlaps. The same holds for all 5 genes checked: danRer11 overlaps ZFIN, NCBI's current record overlaps none. Boundaries are not identical: {assembly['reading'].split('Boundaries are NOT identical:')[1].split('(different')[0].strip(' .')}.",
        tag("Danio rerio", "source_assessment", "ucsc-danrer11-search") + "Coordinates from NCBI Gene must carry their accession and never be joined to GRCz11 rows.", [],
        ["Five genes were checked against UCSC, not all 22.", "The ZFIN GFF3 header does not state its assembly; GRCz11 is inferred from the overlap with danRer11 and the Ensembl ids."],
        src("ncbi-gene-esummary", "genomicinfo for the selected Gene ids; assembly_check.json"), "derived"))
    drafts.append(claim("gx-transfer-hypothesis-zebrafish-to-flyingfish", "Hypothesis (proposed, not evidence): the zebrafish lat4a x kcnh2a fin-proportion result may carry over to flying fishes",
        "Daane et al. propose that bioelectric cues and amino-acid transport also shape relative fin size in flying fishes. Here that is a hypothesis that needs, at minimum, the paper's gene identifiers, expression of both genes in flying-fish fin tissue and a test in a flying fish or a closer proxy.",
        tag("Danio rerio -> flying fishes", "proposed_transfer (not an evidence class)", "europepmc-pmc9172250") + "Kept separate from every species-specific statement.", ["The paper's reading of its own phylogenomic result."],
        ["No flying-fish expression or perturbation data was fetched.", "The mirrorwing annotation has no gene model whose best hit is KCNH2 (annotation-level only)."],
        src("europepmc-pmc9172250", "abstractText, last sentence"), "hypothesis"))
    # ---- problems
    drafts.append(problem("gx-problem-lat4a-identity", "UNRESOLVED: which ZFIN gene is the 'lat4a' of Daane et al. 2021?",
        "The abstract calls lat4a 'an L-type amino acid transporter'. It is not a ZFIN symbol or alias, and gets 0 hits in NCBI Gene and UniProt. slc43a2a and slc43a2b are candidates by name (UniProt names the slc43a2b product 'Large neutral amino acids transporter small subunit 4'); neither is confirmed.",
        "Which zebrafish gene(s) did the authors mean, and what are the flying-fish counterparts?", "project_gap", "Not assessed against the paper's methods (not open access).", "Paper full text and supplement could-not-access; ZFIN, NCBI and UniProt checked.",
        ["access to the paper's methods or supplement, or the authors' gene identifiers", "synteny check of slc43a2a/b"], ["Any record keyed on lat4a must wait for this."], src("europepmc-pmc9172250", "abstractText"), ["molecular"], ["species:Danio rerio", "evidence_class:source_assessment"],
        {"status": "unresolved", "file": "data/genomics/lat4a_resolution.json", "candidates": ["slc43a2a ZDB-GENE-040426-964", "slc43a2b ZDB-GENE-041212-6"]}))
    drafts.append(problem("gx-problem-causal-intervention-data", "No causal_intervention data fetched: the lat4a x kcnh2a double-mutant phenocopy is a claim read at abstract level only",
        "The only causal evidence for the fin-proportion story is the paper's zebrafish mutant experiments. The paper is not open access; no figure, genotype table or measurement was read. ZFIN has no phenotype row for kcnh2a.",
        "What genotypes, measurements and controls support the phenocopy claim, and are they in a public dataset?", "project_gap", "Not searched beyond ZFIN and Europe PMC.", "Paper not open access; no data repository was identified.",
        ["full-text access", "ZFIN curation status check", "contact route to the authors is NOT proposed here (no outreach)"], ["Separates expression correlation from causal evidence in the browser."], src("europepmc-pmc9172250", "abstractText"),
        ["organism", "developmental"], ["species:Danio rerio", "evidence_class:causal_intervention"]))
    drafts.append(problem("gx-problem-zebrahub-and-danio-code", "Not fetched: Zebrahub gene-level data and DANIO-CODE regulatory tracks",
        "Zebrahub's landing pages state a 10-stage, 40-embryo, ~120,000-cell transcriptome and a 6-stage, 420-embryo, ~94,000-cell multiome with ~640,000 ATAC peaks; its public file server lists imaging and a 3D-UMAP folder. No precomputed gene-level subset or API was located. "
        "DANIO-CODE and UCSC regulatory tracks were not fetched.",
        "Where can bounded gene-level expression or accessibility for the fin set be obtained without a whole-atlas download?", "project_gap", "Not assessed.", "Landing pages and listings read; atlas objects (cellxgene viewer) not queried.",
        ["identify a gene-level endpoint or a small per-gene export", "disk and memory caps for any atlas object"], ["Adds regenerating-fin and epigenomic coverage beyond ZFIN curation and Daniocell."], src("zebrahub-pages", "landing pages and public listing"),
        ["cellular", "tissue"], ["species:Danio rerio", "evidence_class:expression_correlation"]))
    drafts.append(problem("gx-problem-flyingfish-kcnh2-and-others", "Is there a kcnh2 gene in the mirrorwing genome that the annotation did not name as such?",
        "No gene model has KCNH2 as its best SwissProt hit; KCNH7 is the best hit for the nearest queries. HOXD13 and FGF24 have no hit. The annotation is a prediction on a scaffold-level assembly.",
        "Do kcnh2, hoxd13 and msx1 sequences exist in the assembly, and are they annotated under other names?", "computational_open_question", "Not searched.", "Assembly sequence (311 MB figshare file) not downloaded.",
        ["bounded sequence search of the scaffolds with caps", "synteny against zebrafish and medaka"], ["Tests the transfer hypothesis against the species it concerns."], src("figshare-14600634-swissprot", "absent_symbols_any_hit"),
        ["molecular", "evolutionary"], ["species:Hirundichthys speculiger", "evidence_class:sequence_annotation"]))
    # ---- evidence (targets are filled after the claims are made)
    def evid(id_, target_id, kind, rel, card_id, locator, method, context, art_paths, lim, prov=None, art=0, assumptions=None):
        c = cards[card_id]
        return {"namespace": NS, "kind": "Evidence", "id": id_, "issuer": ISSUER, "source_uri": "urn:frontier:connector:genomics", "visibility": "public", "predecessor": None,
                "payload": {"target": target_id, "evidence_kind": kind, "relation": rel, "source": src(card_id, locator, art), "created_time": {"value": c["retrieved_at"], "basis": "witnessed"},
                            "retrieved_time": {"value": c["retrieved_at"], "basis": "witnessed"}, "method": method, "context": context, "assumptions": assumptions or [],
                            "provenance": {"source_card": card_id, "retrieval_receipt": {"sha256": c["source_stream_sha256"], "bytes": c["source_stream_bytes"], "http_status": c["http_status"]}} | (prov or {}),
                            "source_dependence": {"declared": True, "independent_of_author": False, "note": "one operator fetched, parsed and wrote the claims; no independent review"},
                            "uncertainty": "Not quantified; counts are of annotations or table rows.", "limitations": lim, "artifacts": [aref(p, t, m, r, l) for p, t, m, r, l in art_paths]}}
    A = lambda p, t, m="text/plain", r="output", l=None: (p, t, m, r, l)
    ev = [
        evid("gx-ev-zfin-kcnh2a-expression", "gx-zfin-kcnh2a-expression-annotations", "source_assessment", "supports", "zfin-wildtype-expression-fish", "rows with gene symbol kcnh2a",
             "Streamed ZFIN wildtype-expression_fish.txt once (hash of the whole stream recorded) and kept the rows of the selected symbols; plotted the kcnh2a rows.", "Curated database rows, read by this connector.",
             [A("data/genomics/zfin_expression_selected.csv", "selected ZFIN expression rows", "text/csv"), A("data/genomics/plots/kcnh2a_zfin_expression.svg", "plotted view drawn only from those rows", "image/svg+xml"),
              A("data/genomics/artifacts/zfin_expression_selected.tsv", "raw selected rows as streamed")],
             ["No header row in the source file; column names inferred from the layout and sample rows.", "A square in the plot is an annotation, not a level."], {"plot_sha256": plots["kcnh2a_zfin_expression.svg"]["sha256"]}),
        evid("gx-ev-zfin-fin-phenotypes", "gx-zfin-fin-phenotype-annotations", "source_assessment", "supports", "zfin-phenogenecleandata-fish", "rows whose affected structure names a fin",
             "Streamed ZFIN phenoGeneCleanData_fish.txt once and kept rows of the selected symbols; counted rows whose affected-structure term names a fin by word.", "Curated annotations, read not re-measured.",
             [A("data/genomics/zfin_phenotype_selected.csv", "selected ZFIN phenotype rows", "text/csv"), A("data/genomics/artifacts/zfin_phenotype_selected.tsv", "raw selected rows as streamed")],
             ["No header row in the source file; fields located by the PATO term.", "kcnh2a has no rows."]),
        evid("gx-ev-mirrorwing-hits", "gx-mirrorwing-fin-set-best-hits", "predicted", "supports", "figshare-14600634-swissprot", "best hit per query, length-checked inferred models",
             "Streamed the authors' SwissProt BLASTP table, gene GFF and peptide FASTA from figshare (MD5 and size matched figshare's declaration); took the best-scoring hit per query; tested an id mapping against protein lengths with one-gene-shift controls.",
             "Homology is the authors' pipeline output (BLASTP best hit), not our computation of orthology.",
             [A("data/genomics/artifacts/flyingfish_swissprot_best_hits_selected.tsv", "best hits for the selected symbols", "text/tab-separated-values", "output", "CC BY 4.0"),
              A("data/genomics/artifacts/flyingfish_selected_gene_models.gff3", "gene models of the length-consistent hits (authors' GFF subset)", "text/plain", "output", "CC BY 4.0"),
              A("data/genomics/artifacts/flyingfish_selected_proteins.faa", "authors' predicted proteins for those models (not generated here)", "text/plain", "output", "CC BY 4.0"),
              A("data/genomics/flyingfish_receipts.json", "receipts, MD5 checks, id-mapping test and per-gene table", "application/json", "log"),
              A("data/genomics/plots/flyingfish_best_hits.svg", "plotted view drawn from the best-hit table", "image/svg+xml")],
             ["Id mapping is an inference (position rank), checked per gene by length only.", "Best hit is not orthology; paralogs unresolved."], {"id_mapping_test": fly["id_mapping_test"]}),
        evid("gx-ev-mirrorwing-paper", "gx-mirrorwing-assembly-annotation", "source_assessment", "supports", "pmc8294118-fulltext", "Summary; Summary of the Genome Assembly and Annotation; Data Availability Statement",
             "Read the open-access full text (Europe PMC JATS XML, CC BY) and located each stated number in its section.", "The numbers are the authors'; none was recomputed.",
             [A("data/genomics/flyingfish_genome_facts.json", "extracted statements with section locators and the NCBI comparison", "application/json", "log"), A("data/genomics/artifacts/PMC8294118_fulltext.xml", "the article XML as retrieved", "application/xml", "input", "CC BY")],
             ["Figures and supplementary tables not read."]),
        evid("gx-ev-daniocell-coverage", "gx-daniocell-coverage", "source_assessment", "supports", "daniocell-cluster-annotations", "cluster_annotations.csv and the landing-page statements",
             "Downloaded the cluster annotation CSV and the landing page; counted clusters per tissue label and by a word-bounded fin pattern.", "Counts of annotation clusters.",
             [A("data/genomics/artifacts/daniocell_cluster_annotations.csv", "the cluster annotation file as retrieved", "text/csv", "input"), A("data/genomics/artifacts/daniocell_index.html", "landing page with the 62-stage and 19-tissue statements", "text/html", "input"),
              A("data/genomics/index.json", "index with the computed counts", "application/json", "log")],
             ["Cluster counts, not cell counts.", "Embryo and larva only."]),
        evid("gx-ev-daniocell-kcnh2a-correlations", "gx-daniocell-kcnh2a-correlations", "source_assessment", "supports", "daniocell-gene-pages", "kcnh2a page, correlation table",
             "Parsed the correlation table of the stored kcnh2a gene page and plotted the top partners.", "Values are as the page lists them.",
             [A("data/genomics/daniocell_correlations.csv", "parsed correlation tables for the gene set", "text/csv"), A("data/genomics/artifacts/daniocell_page_kcnh2a.html", "the kcnh2a page as retrieved", "text/html", "input"),
              A("data/genomics/plots/kcnh2a_daniocell_correlations.svg", "plotted view drawn from the parsed table", "image/svg+xml")],
             ["The page does not state how r was computed beyond the label.", "All-cells view only."], {"plot_sha256": plots["kcnh2a_daniocell_correlations.svg"]["sha256"]}),
        evid("gx-ev-coordinates", "gx-ncbi-gene-coordinates-are-not-grcz11", "source_assessment", "supports", "ncbi-gene-esummary", "genomicinfo versus ZFIN GFF3 versus UCSC danRer11",
             "Compared NCBI Gene's genomicinfo, ZFIN GFF3 gene spans and UCSC danRer11 RefSeq matches for five genes and reported overlaps and offsets.", "A comparison of three sources' coordinates.",
             [A("data/genomics/assembly_check.json", "per-gene overlaps, offsets and conventions", "application/json", "log"), A("data/genomics/artifacts/ucsc_danrer11_search.json", "UCSC search responses", "application/json", "input"),
              A("data/genomics/artifacts/ncbi_gene_summaries.json", "NCBI Gene esummary", "application/json", "input"), A("data/genomics/artifacts/zfin_genes_selected.gff3", "ZFIN GFF3 gene lines", "text/plain", "input")],
             ["Five genes of 22 checked.", "No Ensembl REST coordinates (its lookup endpoint timed out)."]),
        evid("gx-ev-daane-abstract", "gx-daane-lat4a-kcnh2a-source", "source_assessment", "context_only", "europepmc-pmc9172250", "abstractText",
             "Read the Europe PMC core record; the full text could not be fetched (HTTP 500, not open access).", "Establishes only what the abstract says.",
             [A("data/genomics/artifacts/europepmc_PMC9172250.json", "Europe PMC record with abstract", "application/json", "input")], ["Abstract only; no data, figure or method read."]),
    ]
    ids = {d["id"]: d for d in drafts}
    made = {}
    for d in drafts:                                              # claims and problems first so evidence can pin exact versions
        made[d["id"]] = models.make_record(models.Draft.model_validate(d), created_at=CREATED_AT)
    for e in ev:
        t = made[e["payload"]["target"]]
        e["payload"]["target"] = models.ref(t)
        made[e["id"]] = models.make_record(models.Draft.model_validate(e), created_at=CREATED_AT)
    records = list(made.values())
    offenders = store._unlicensed_available_content(records)
    if offenders:
        raise SystemExit(f"licence gate refused: {offenders}")
    kinds = collections.Counter(r["kind"] for r in records)
    (OUT / "records").mkdir(exist_ok=True)
    (OUT / "records" / "records.json").write_text(json.dumps({"records_schema": "genomics-records-0.1 (connector-local; frontier.models records)", "status": "proposed drafts; nothing submitted, reviewed or accepted",
                                                              "namespace": NS, "issuer": ISSUER, "evidence_classes": sorted(EV_KIND), "records": records}, indent=1, sort_keys=True))
    print(dict(kinds), "records; licence-gate offenders:", len(offenders))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
