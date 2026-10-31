"""Daane et al. 2021 (Curr Biol) read in full: the lat4a mapping, the gene -> ion/amino-acid -> outgrowth -> fin-shape chain, and pins.

The PDF (19 pages, author-hosted, no licence stated) is fetched into a scratch directory and NOT stored in the repo. Every quote below must occur
verbatim in the PDF's text (pdftotext, whitespace-normalised, line-break hyphens joined), is at most 25 words, and gets the PDF page it was found on.
A quote that is not found stops the run.

  PYTHONPATH=. python3 -m connectors.genomics.daane2021 --workdir <scratch dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from . import sources as S

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "genomics"
ART = OUT / "artifacts"
PDF_URL = "https://www.daanelab.org/pdfs/papers/Daane-CurrBio-2021.pdf"
DOI = "10.1016/j.cub.2021.08.054"
CREATED_AT = "2026-10-31T21:30:00+00:00"       # declared when the drafts were written
NS, ISSUER = "node-a", "genomics-worker"


def norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)          # the PDF text carries stray control characters before some numbers
    s = re.sub(r"-\n(?=[a-z])", "", s)
    return re.sub(r"\s+", " ", s).strip()


class Paper:
    def __init__(self, pdf: Path):
        self.pages = [norm(subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), str(pdf), "-"], capture_output=True, text=True, check=True).stdout) for i in range(1, 20)]
        self.full = norm(subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True).stdout)

    def q(self, key: str, quote: str, what: str) -> dict:
        n = norm(quote)
        if len(n.split()) > 25:
            raise SystemExit(f"quote {key} over 25 words")
        if n not in self.full:
            raise SystemExit(f"QUOTE NOT FOUND ({key}): {n!r}")
        pages = [i + 1 for i, p in enumerate(self.pages) if n in p]
        return {"id": key, "quote": n, "pdf_page": pages[0] if pages else None, "page_note": None if pages else "spans a page break", "what": what, "verified_verbatim": True}


def translate(dna: str) -> str:
    aas = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
    table = {a + b + c: aas[i] for i, (a, b, c) in enumerate((a, b, c) for a in "TCAG" for b in "TCAG" for c in "TCAG")}
    return "".join(table.get(dna[i:i + 3], "X") for i in range(0, len(dna) - 2, 3))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", type=Path, required=True)
    a = ap.parse_args()
    a.workdir.mkdir(parents=True, exist_ok=True)
    body, receipt = S.fetch(PDF_URL, 20_000_000)
    pdf = a.workdir / "daane2021.pdf"
    pdf.write_bytes(body)
    P = Paper(pdf)
    Q = P.q
    quotes = {q["id"]: q for q in [
        Q("lat4a_map", "we mapped nr21 to chromosome 15 and identified a nonsynonymous mutation (T200K) in a conserved domain of the L-type amino acid transporter, lat4a", "nr21 mapped to chromosome 15; T200K in lat4a"),
        Q("lat4_function", "Mammalian Lat4 shuttles isoleucine, leucine, methionine, and phenylalanine into the cell in an ion- and pH-independent manner", "what Lat4 transports (citing mammalian work)"),
        Q("lat4_slc43a2_ref", "Essential amino acid transporter Lat4 (Slc43a2) is required for mouse development", "reference 17 title: Lat4 = Slc43a2"),
        Q("nr21_small_fins", "We identified a dominant mutant, nr21, as having small adult fins compared to wild-type siblings", "nr21 phenotype"),
        Q("nr21_body", "The nr21 mutant, however, does not have a statistically decreased body size", "fin effect without a body-size effect"),
        Q("nr21_gof", "indicating that the mutation in lat4anr21 results from a gain-of-function effect", "cis frameshift reverts nr21: gain of function"),
        Q("lat4a_null", "zebrafish lacking lat4a have no fin phenotype", "lat4a loss of function has no fin phenotype"),
        Q("lat4a_alleles", "Lat4a alleles identified and used in this work are lat4nr21 (dmh26), and lat4adel (mh152).", "allele names"),
        Q("lat4a_grna", "CRISPR guide RNAs (gRNAs) were designed against the third coding exon of lat4a", "frameshift design"),
        Q("lof_gof", "The ability to revert the mutant phenotype by loss-of-function kcnh2a alleles in cis to lof indicates the mutant imparts a gain-of-function effect", "kcnh2a lof is a gain of function"),
        Q("lof_ectopic", "As ectopic expression of kcnh2a is sufficient to drive fin overgrowth (Figure 3)", "ectopic kcnh2a drives overgrowth"),
        Q("lof_breakpoints", "identified a breakpoint upstream of the transcription start site of prrx1a (23.174 Mb in Zv11) and one between kcc4a and kcnh2a (24.075 Mb)", "lof^dt2 breakpoints in Zv11 (GRCz11)"),
        Q("lof_cis_ref", "longfin causes cis-ectopic expression of the kcnh2a ether-a-go-go K+ channel to autonomously prolong fin outgrowth", "reference 21 title (Stewart et al. 2021)"),
        Q("lof_alleles", "Longfin alleles used in this work are lofdt2, the revertants lof (lfr1(Y669N), lfr2(L739Q), and WL7 (Y418X).", "lof alleles and revertants"),
        Q("lof_not_maintained", "These lines are no longer maintained nor frozen, thus are used for confirmation of mapping only.", "lof^dt2 and revertants are not maintained"),
        Q("lof_deletion_line", "The deletion line lofj6e1 (lofDf(Chr02:csnk1g2a,rnf2,kifap3b)j6g1/j6g1) is present at ZIRC repository (ZL1494).", "the maintained deletion line"),
        Q("fig4_title", "Intersection of bioelectric and Lat4a-mediated growth pathways is sufficient to phenocopy the evolved flying fish fin allometry", "Figure 4 title"),
        Q("fig4_suppressor", "lat4a is a fin suppressor of overgrowth caused by increased potassium channel function", "Figure 4A legend"),
        Q("fig4_transhet", "the nr21/lof trans-heterozygotes exhibit elongated paired fins and a hypocercal caudal fin", "Figure 4A legend"),
        Q("fig4_phenocopy", "suggesting the interaction between these two genes is sufficient to phenocopy this key innovation and organismal bauplan of flying fishes", "Results"),
        Q("fig4_mechanism", "the mechanism of fin-specific suppression of lof by lat4a mutations is occurring downstream of bioelectric signaling signals", "Results"),
        Q("fig4_qrt", "kcnh2a expression does not vary significantly in pectoral or dorsal fins containing the nr21 mutation", "Results; Figures 4D and 4E"),
        Q("cap_species", "35 different beloniform species, including two- and four-winged flying fishes, halfbeaks, sauries, and needlefishes", "sampling (Table S1; Data S1B)"),
        Q("cap_coverage", "We obtained coverage from an average of 78.3% of the targeted genomic regions at an average 38.3-fold depth", "capture recovery (Tables S2 and S3)"),
        Q("f326l", "we detected a shared amino acid substitution in lat4a that is found across multiple lineages having enlarged pectoral fins", "F326L"),
        Q("f326l_caveat", "we cannot exclude incomplete lineage sorting or introgression of ancestral F326L haplotypes specifically within gliding lineages", "authors' own caveat"),
        Q("lat4a_phyloP", "Lat4a also has a phyloP acceleration p = 0.008 on the common ancestral node of flying fishes", "Figure 2 legend (Data S1J)"),
        Q("sailfin", "only one flying fish species in our dataset lacks the convergent lat4a allele, the sailfin flying fish Parexocoetus brachypterus", "exception with an elongated dorsal fin"),
        Q("allometry_s1a", "Paired fin and standard fish lengths were measured from beloniform specimens in the Harvard Museum of Comparative Zoology (Data S1A)", "source of the fin/body data"),
        Q("allometry_identical", "The allometric relationship between body size and pectoral fin length was identical across the two- and four-wing flying fishes", "Figure 1B; Data S1A"),
        Q("allometry_rapid", "the length of flying fish pectoral fins increases rapidly", "Figure 1B; Data S1A"),
        Q("data_sra", "Raw targeted sequencing reads have been deposited in the NCBI Sequence Read Archive", "data availability"),
        Q("supp_location", "Supplemental information can be found online at https://doi.org/10.1016/j. cub.2021.08.054.", "where the supplement is"),
        Q("published", "Published: September 16, 2021", "publication date as printed"),
    ]}
    # accessions printed in the Key resources table (checked in the text, not typed from memory)
    for acc in ("PRJNA743939", "10.5281/zenodo.5082978", "ERX1428166", "Zebrafish reference genome (Zv11)"):
        if acc not in P.full:
            raise SystemExit(f"accession not in the PDF text: {acc}")
    for tag in ("Figure 1. ", "Figure 2. ", "Figure 3. ", "Figure 4. "):
        if tag not in P.full:
            raise SystemExit(f"{tag} legend not found")
    fig_pages = {t.strip(" ."): next(i + 1 for i, p in enumerate(P.pages) if re.search(re.escape(t) + r"[A-Z]", p)) for t in ("Figure 1. ", "Figure 2. ", "Figure 3. ", "Figure 4. ")}
    krt_pages = [i + 1 for i, p in enumerate(P.pages) if "REAGENT or RESOURCE" in p]
    # ---- chromosome / residue evidence for the lat4a mapping
    gcsv = {r.split(",")[0]: r.split(",") for r in (OUT / "genes.csv").read_text().splitlines()[1:]}
    chr_a, chr_b = gcsv["slc43a2a"][5], gcsv["slc43a2b"][5]
    def fasta(p):
        L = p.read_text().splitlines()
        return L[0], "".join(L[1:])
    ha, sa = fasta(ART / "ncbi_NP_956545.1_slc43a2a.faa")
    hb, sb = fasta(ART / "ncbi_NP_001008585.1_slc43a2b.faa")
    track, tr_r = S.fetch("https://api.genome.ucsc.edu/getData/track?genome=danRer11;track=ncbiRefSeq;chrom=chr15;start=28360000;end=28410000", 2_000_000)
    item = next(x for x in json.loads(track)["ncbiRefSeq"] if x["name2"] == "slc43a2a")
    seqb, sq_r = S.fetch(f"https://api.genome.ucsc.edu/getData/sequence?genome=danRer11;chrom=chr15;start={item['txStart']};end={item['txEnd']}", 2_000_000)
    dna = json.loads(seqb)["dna"].upper()
    es, ee = [int(x) for x in item["exonStarts"].strip(",").split(",")], [int(x) for x in item["exonEnds"].strip(",").split(",")]
    cds = "".join(dna[max(s, item["cdsStart"]) - item["txStart"]: min(e, item["cdsEnd"]) - item["txStart"]] for s, e in zip(es, ee) if max(s, item["cdsStart"]) < min(e, item["cdsEnd"]))
    prot = translate(cds).rstrip("*")
    assert prot == sa or len(prot) == len(sa), (len(prot), len(sa))
    at = lambda s, n: s[n - 1] if len(s) >= n else None
    residue = {"paper_positions": {"nr21": "T200K (zebrafish lab mutation)", "natural": "F326L (flying fishes, Figure 2D)"},
               "slc43a2a": {"zfin_chr": chr_a, "refseq_protein": "NP_956545.1", "length": len(sa), "aa200": at(sa, 200), "aa326": at(sa, 326), "ucsc_refseq_model": f"{item['name']} chr15:{item['txStart']}-{item['txEnd']} CDS {item['cdsStart']}-{item['cdsEnd']}, {item['exonCount']} exons, CDS {len(cds)} nt",
                         "translation_from_danrer11_matches_ncbi_protein_length": len(prot) == len(sa), "verdict": "INCONCLUSIVE: the RefSeq model is 153 residues, too short to contain residues 200 or 326"},
               "slc43a2b": {"zfin_chr": chr_b, "refseq_protein": "NP_001008585.1", "length": len(sb), "aa200": at(sb, 200), "aa326": at(sb, 326), "verdict": "does NOT have T at 200 or F at 326 in this RefSeq numbering (numbering across isoforms may differ)"}}
    res = {
        "schema": "lat4a-resolution-0.2 (connector-local)", "supersedes": "data/genomics/lat4a_resolution.json (kept unchanged; records are append-only)", "question": "Which ZFIN gene is Daane et al. 2021's lat4a?",
        "status": "PROBABLE slc43a2a (ZDB-GENE-040426-964, ENSDARG00000036848); NOT confirmed by an accession",
        "evidence_for": [{"what": "the paper maps nr21 to chromosome 15", "quote": quotes["lat4a_map"]["id"]}, {"what": f"ZFIN (GRCz11) puts slc43a2a on chromosome {chr_a} and its paralog slc43a2b on chromosome {chr_b}", "source": "genes.csv from ZFIN GFF3"},
                         {"what": "the paper's lat4a is the zebrafish counterpart of mammalian Lat4, whose gene name is Slc43a2", "quote": quotes["lat4_slc43a2_ref"]["id"]}, {"what": "the 'a' suffix matches", "weight": "weak"}],
        "evidence_against_or_unresolved": [{"what": "UniProt names the slc43a2b product 'Large neutral amino acids transporter small subunit 4' (the LAT4 name), while slc43a2a carries only 'Solute carrier family 43 member 2a'", "source": "lat4a_resolution.json (UniProt, 2026-10-31)", "weight": "protein-name annotation, weaker than the authors' mapping"},
                                           {"what": "the paper prints no ZFIN or Ensembl identifier for lat4a in the text read; its mapping interval is in Figures S2D-S2F, which are in the supplement and were not retrieved"},
                                           {"what": "the residue check could not test slc43a2a (RefSeq model too short) and is negative for slc43a2b"}],
        "residue_check": residue, "paper_accessions": {"BioProject": "PRJNA743939", "Zenodo": "10.5281/zenodo.5082978", "SRA (longfin PacBio reads)": "ERX1428166", "reference genome": "Zv11 (= GRCz11)"},
        "what_would_confirm": ["Figure S2D-S2F mapping interval and the Lat4a alignment (Figure 3C, which labels T200K) against the slc43a2a gene model", "the authors' transcript or protein accession", "a longer slc43a2a protein (Ensembl transcript) in which residue 200 is T"],
        "reading": "Use slc43a2a as the working zebrafish gene for 'lat4a' and label it inferred; do not present it as the paper's stated identifier."}
    (OUT / "lat4a_resolution_v2.json").write_text(json.dumps(res, indent=1, sort_keys=True))
    (ART / "ucsc_slc43a2a_refseq_model.json").write_text(json.dumps({"item": {k: item[k] for k in ("name", "name2", "chrom", "strand", "txStart", "txEnd", "cdsStart", "cdsEnd", "exonCount", "exonStarts", "exonEnds")}, "genomic_dna_sha256": hashlib.sha256(dna.encode()).hexdigest(),
                                                                       "cds_nt": len(cds), "protein_len": len(prot), "protein_first12": prot[:12]}, indent=1, sort_keys=True))
    def pin(fig, page, what, quote_ids, locator=None):
        return {"pin": fig, "pdf_page": page, "what": what, "quotes": quote_ids, **({"locator": locator} if locator else {})}
    pins = {
        "schema": "daane2021-pins-0.1 (connector-local)", "paper": {"citation": "Daane JM, Blum N, Lanni J, Boldt H, Iovine MK, Higdon CW, Johnson SL, Lovejoy NR, Harris MP. Modulation of bioelectric cues in the evolution of flying fishes. Curr Biol 31 (2021). doi:" + DOI, "author_list_source": "Europe PMC record PMC9172250 (stored)"},
        "pdf": {"url": PDF_URL, "sha256": receipt.sha256, "bytes": receipt.bytes, "pages": 19, "retrieved_at": receipt.retrieved_at, "stored_in_repo": False, "license": None, "state": "'Corrected proof' (PDF metadata); the text prints 'Published: September 16, 2021'"},
        "figures": {"Figure 1": pin("Figure 1", fig_pages["Figure 1"], "static allometry of pectoral fins in Exocoetidae, sauries, needlefish and halfbeaks; data in Data S1A", ["allometry_rapid", "allometry_identical"]),
                    "Figure 2": pin("Figure 2", fig_pages["Figure 2"], "convergent and ancestral genetic signatures; lat4a relative evolutionary rate and the F326L substitution (panels C, D)", ["f326l", "lat4a_phyloP", "sailfin"]),
                    "Figure 3": pin("Figure 3", fig_pages["Figure 3"], "zebrafish nr21 (lat4a) short fins, the cis frameshift revertant L106Rfs39, and kcnh2a/kcnk5b/kcnj13 overexpression (panels H-J)", ["lat4a_map", "nr21_gof", "lat4a_null", "lof_ectopic"]),
                    "Figure 4": pin("Figure 4", fig_pages["Figure 4"], "THE PIN: nr21/lof trans-heterozygotes (lat4a x kcnh2a) phenocopy flying-fish fin proportions; B, C pectoral and caudal fin length / SL; D, E qRT-PCR", ["fig4_title", "fig4_suppressor", "fig4_transhet", "fig4_phenocopy", "fig4_mechanism", "fig4_qrt"])},
        "supplement": {"where": "publisher's online Supplemental information, https://doi.org/" + DOI, "in_the_19_page_pdf": False, "retrieved": False, "quote": "supp_location",
                       "items": {"Table S1": {"what": "species and specimens sampled for targeted capture (35 beloniform species)", "cited_with": "Data S1B", "quote": "cap_species", "description_basis": "how the main text cites it"},
                                 "Table S2": {"what": "recovery by target category (CNEs, microRNAs, coding sequence) in the capture", "quote": "cap_coverage", "description_basis": "how the main text cites it"},
                                 "Table S3": {"what": "coverage at multiple read depths", "quote": "cap_coverage", "description_basis": "how the main text cites it"},
                                 "Data S1A": {"what": "paired fin and standard-length measurements of Harvard MCZ beloniform specimens: THE EMPIRICAL FIN/BODY DATA (Figure 1B)", "quote": "allometry_s1a", "description_basis": "STAR Methods sentence", "status": "dx-submit is extracting this; not retrieved here"},
                                 "Data S1B": {"what": "specimen and tissue sources for sequencing", "description_basis": "how the main text cites it"},
                                 "Data S1C-S1N": {"what": "coverage by gene group (C); variation (D); contigs (E); relative evolutionary rate by GO term (F); parallel amino-acid substitutions incl. lat4a F326L (G); fin and limb candidate genes (H); convergent rate shifts (I); accelerated and constrained elements incl. lat4a (J); GO enrichment (K-N)", "description_basis": "how the main text cites each letter; not read in the files"}}},
        "accessions": {"PRJNA743939": "BioProject: Beloniformes targeted sequencing reads (this paper)", "10.5281/zenodo.5082978": "Zenodo: Beloniformes assembled contigs (this paper)", "ERX1428166": "SRA: longfin PacBio sequencing reads", "reference genome": "Zebrafish Zv11 (= GRCz11)",
                       "key_resources_pdf_pages": krt_pages, "quote": "data_sra"}}
    (OUT / "daane2021_pins.json").write_text(json.dumps({**pins, "quotes": quotes}, indent=1, sort_keys=True))
    # ---- the chain (every statement is tied to a verified quote id)
    Z = lambda s: {"symbol": s, "zfin_id": gcsv[s][2], "ensembl_gene_grcz11": gcsv[s][3], "zfin_gff_grcz11": f"chr{gcsv[s][5]}:{int(gcsv[s][6]):,}-{int(gcsv[s][7]):,} ({gcsv[s][8]})"}
    chain = {
        "schema": "daane2021-chain-0.1 (connector-local)", "status": "a map of what the paper reports, NOT a validated mechanism and NOT a prescription", "organism_of_experiments": "Danio rerio (zebrafish)", "organism_of_motivation": "flying fishes and relatives (Beloniformes), 35 species by targeted capture",
        "chain": [
            {"step": 1, "from": "gene", "to": "ion channel / amino-acid transporter", "nodes": [
                {"paper_name": "kcnh2a", "gene": Z("kcnh2a"), "function_class": "potassium channel (ether-a-go-go)", "functional_class_quote": "lof_cis_ref", "mapping": "stated by the paper and ZFIN agree"},
                {"paper_name": "lat4a", "gene": {**Z("slc43a2a"), "mapping": "INFERRED (probable), see lat4a_resolution_v2.json"}, "function_class": "L-type amino-acid transporter; mammalian Lat4 moves isoleucine, leucine, methionine, phenylalanine", "functional_class_quote": "lat4_function",
                 "caution": "the function is that of the mammalian protein per the paper; transport was not measured in the zebrafish mutants in the text read"}]},
            {"step": 2, "from": "ion channel / amino-acid transporter", "to": "fin outgrowth (zebrafish)", "edges": [
                {"gene": "kcnh2a", "allele": "lof^dt2: gain of function; inversion with breakpoints at 23.174 Mb (upstream of prrx1a) and 24.075 Mb (between kcc4a and kcnh2a) in Zv11", "effect": "ectopic kcnh2a expression drives fin overgrowth", "evidence_class": "causal_intervention (as reported: mutants, cis revertants, overexpression)", "quotes": ["lof_gof", "lof_ectopic", "lof_breakpoints", "lof_cis_ref"],
                 "consistency_check": "the 24.075 Mb breakpoint lies about 5.6 kb upstream of the ZFIN GRCz11 start of kcnh2a (24,080,694), as 'between kcc4a and kcnh2a' implies; the paper gives Mb to three decimals"},
                {"gene": "lat4a", "allele": "nr21 (dmh26), T200K, dominant; cis frameshift revertant L106Rfs39; lat4a^del (mh152)", "effect": "nr21 shortens all fins without a statistically decreased body size; the revertants show nr21 acts by gain of function; lat4a null has no fin phenotype", "evidence_class": "causal_intervention (as reported)", "quotes": ["nr21_small_fins", "nr21_body", "nr21_gof", "lat4a_null", "lat4a_map"],
                 "consequence": "lat4a is not shown to be REQUIRED for normal fin length; only the gain-of-function allele has an effect"}]},
            {"step": 3, "from": "fin outgrowth", "to": "fin shape / proportion (zebrafish)", "edges": [
                {"cross": "nr21/+ x lof/+ (trans-heterozygote)", "effect": "lat4a nr21 suppresses the overgrowth caused by lof in the median fins and leaves elongated paired fins plus a hypocercal caudal fin: a fin-proportion pattern like flying fishes", "evidence_class": "genotype_phenotype (as reported; Figure 4A-C)",
                 "quotes": ["fig4_title", "fig4_suppressor", "fig4_transhet", "fig4_phenocopy"], "mechanism": "kcnh2a expression does not change with nr21 (qRT-PCR) and the paper concludes the suppression acts downstream of bioelectric signalling; the mechanism is not identified", "mechanism_quotes": ["fig4_qrt", "fig4_mechanism"],
                 "pin": "Figure 4, PDF page " + str(fig_pages["Figure 4"])}]}],
        "context": {"what_is_reproduced": "relative fin proportions (paired fins elongated, hypocercal caudal fin) in a zebrafish double mutant", "what_is_not": ["flight or gliding performance (no aerodynamic or locomotion measurement in zebrafish appears in the text read)", "the flying-fish genotype: the zebrafish alleles (lat4a T200K, kcnh2a lof inversion) are not the flying-fish variants", "that flying fishes use these two genes: the genomic data are correlational"],
                    "phylogenomic_links": [{"observation": "a shared lat4a F326L substitution across lineages with enlarged pectoral fins", "quotes": ["f326l", "f326l_caveat"]}, {"observation": "lat4a elevated evolutionary rate in gliding lineages and phyloP acceleration at the flying-fish ancestor", "quotes": ["lat4a_phyloP"]}, {"observation": "one flying fish lacks the convergent lat4a allele and has an elongated dorsal fin", "quotes": ["sailfin"]}],
                    "genomes_available_is_not_a_mutation_map": {"why": "the 35-species data are pooled targeted capture of conserved regions (average 78.3% of targeted regions at 38.3-fold), the F326L link is a correlation the authors themselves caveat, and F326L (natural, flying fishes) is a different residue from T200K (laboratory, zebrafish); no flying-fish variant is shown to change fin length", "quotes": ["cap_coverage", "f326l_caveat"]}}}
    cand = {
        "schema": "daane2021-candidate-perturbations-0.1", "status": "CANDIDATES ONLY. Not prescriptions, not validated designs, no effect size is claimed.",
        "zebrafish_alleles_in_the_paper": [
            {"allele": "lat4a nr21 (dmh26), T200K", "effect": "short fins, dominant, gain of function", "availability_stated": "Key resources table: 'This paper'; ZIRC id not given", "quotes": ["lat4a_alleles", "nr21_gof"]},
            {"allele": "lat4a del (mh152), CRISPR frameshift", "effect": "no fin phenotype alone; the cis frameshift L106Rfs39 reverts nr21", "quotes": ["lat4a_alleles", "lat4a_null", "lat4a_grna"]},
            {"allele": "kcnh2a lof^dt2 (inversion, cis-ectopic expression)", "effect": "long fins, gain of function", "availability_stated": "Key resources table lists ZIRC ZL86, but the methods say lof^dt2 and its revertants are no longer maintained or frozen: the two statements disagree and both are kept", "quotes": ["lof_alleles", "lof_not_maintained"]},
            {"allele": "kcnh2a lof revertants lfr1 (Y669N), lfr2 (L739Q), WL7 (Y418X)", "effect": "revert the long-fin phenotype in cis", "availability_stated": "not maintained", "quotes": ["lof_alleles", "lof_not_maintained"]},
            {"allele": "lof^j6e1 deletion line Df(Chr02:csnk1g2a,rnf2,kifap3b)", "effect": "deletion on chromosome 2 (Iovine and Johnson); maintained", "availability_stated": "ZIRC ZL1494", "quotes": ["lof_deletion_line"]}],
        "candidate_perturbations": [
            {"id": "cp1", "what": "the paper's own cross: lat4a nr21/+ x kcnh2a lof/+", "why": "reported to give elongated paired fins and a hypocercal caudal fin (Figure 4)", "unknown": ["strain and husbandry dependence", "whether the lof^dt2 allele can still be obtained", "effect on anything but fin proportions"], "quotes": ["fig4_transhet"]},
            {"id": "cp2", "what": "introduce the flying-fish F326L change into zebrafish lat4a", "why": "it is the natural lat4a variant shared by lineages with enlarged pectoral fins", "unknown": ["whether it changes transport or fin size at all", "its direction (nr21 shortens fins; the paper does not say F326L lengthens them)", "that the zebrafish gene is slc43a2a (inferred)"], "quotes": ["f326l", "f326l_caveat"], "status": "not tested in the text read"},
            {"id": "cp3", "what": "dose series of other potassium channels already reported to drive fin overgrowth (kcnk5b, kcnj13)", "why": "the paper cites overexpression of kcnj13, kcnk5b and kcnh2a as sufficient to induce overgrowth", "unknown": ["whether any of them interacts with lat4a", "dose-response"], "quotes": ["lof_ectopic"]},
            {"id": "cp4", "what": "lat4a null alone", "why": "a control, not an expected effect: the paper reports no fin phenotype", "unknown": [], "quotes": ["lat4a_null"]}],
        "not_a_prescription": "each entry is a question the paper's data motivate. None is a recommended experiment, a design for a printed or living construct, or a claim that the effect would transfer to any other species."}
    (OUT / "daane2021_chain.json").write_text(json.dumps({"chain": chain, "perturbations": cand}, indent=1, sort_keys=True))
    # ---- source card
    card = {"id": "daane2021-pdf", "name": "Daane et al. 2021, Current Biology: full text (author-hosted PDF)", "uri": PDF_URL, "accession": "doi:" + DOI, "version": "Corrected proof; the text prints 'Published: September 16, 2021'", "locator": "19 pages; figures at pdf pages " + ", ".join(f"{k} p.{v}" for k, v in fig_pages.items()),
            "license": None, "license_read": "no licence stated on the PDF; the publisher's terms were not read; the PDF is not stored here", "access": "public download from a laboratory website", "retrieved_at": receipt.retrieved_at, "http_status": receipt.http_status, "source_stream_sha256": receipt.sha256, "source_stream_bytes": receipt.bytes,
            "artifacts": [{"path": "data/genomics/daane2021_pins.json", "sha256": hashlib.sha256((OUT / "daane2021_pins.json").read_bytes()).hexdigest(), "bytes": (OUT / "daane2021_pins.json").stat().st_size}], "read_level": "full-text (all 19 pages; the supplement is not part of the PDF and was not read)",
            "limits": ["Tables S1-S3, Data S1 and Figures S1-S4 are in the publisher's supplement, not in this PDF", "the PDF is a corrected proof, not the final typeset version", "quotes verified against pdftotext output, not against page images; figure content was read from legends only"]}
    (OUT / "daane2021_source.json").write_text(json.dumps(card, indent=1, sort_keys=True))
    print("quotes verified:", len(quotes), "| figure pages:", fig_pages, "| KRT pages:", krt_pages, "| slc43a2a aa200/326:", at(sa, 200), at(sa, 326), "| slc43a2b aa200/326:", at(sb, 200), at(sb, 326))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
