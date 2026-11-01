"""Sourced Claim / Evidence / Problem drafts for the Daane 2021 layer. Separate file from records.py so the earlier 24 records keep their versions.

  PYTHONPATH=. python3 -m connectors.genomics.daane2021_records
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "genomics"
NS, ISSUER = "node-a", "genomics-worker"
CREATED_AT = "2026-10-31T21:30:00+00:00"


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from frontier import models, store

    J = lambda n: json.loads((OUT / n).read_text())
    pins, chain, res, card = J("daane2021_pins.json"), J("daane2021_chain.json"), J("lat4a_resolution_v2.json"), J("daane2021_source.json")
    Qs = pins["quotes"]
    pdf = pins["pdf"]
    F = pins["figures"]

    def src(locator):
        return {"uri": card["uri"], "locator": locator, "source_version": card["version"], "content_sha256": pdf["sha256"], "content_available": False,
                "access": f"{card['access']}; read level: {card['read_level']}; licence: none stated in the bytes read; PDF not stored here", "license": None}

    def pg(*ids):
        return "; ".join(f"[{i}] p.{Qs[i]['pdf_page']}: \"{Qs[i]['quote']}\"" for i in ids)

    def aref(path, title, media, role):
        b = (ROOT / path).read_bytes()
        h = hashlib.sha256(b).hexdigest()
        return {"title": f"{role}: {path} - {title}"[:3000], "uri": "urn:sha256:" + h, "sha256": h, "byte_size": len(b), "media_type": media, "role": role, "availability": "referenced", "license": None}

    def claim(id_, title, statement, context, limitations, locator, origin, assumptions=None):
        return {"namespace": NS, "kind": "Claim", "id": id_, "issuer": ISSUER, "source_uri": "urn:frontier:connector:genomics", "visibility": "public", "predecessor": None,
                "payload": {"title": title, "statement": statement, "context": context, "assumptions": assumptions or [], "limitations": limitations, "source": src(locator), "origin": origin}}

    def problem(id_, title, known, question, kind, capabilities, uses, locator, scales, tags, original=None):
        return {"namespace": NS, "kind": "Problem", "id": id_, "issuer": ISSUER, "source_uri": "urn:frontier:connector:genomics", "visibility": "public",
                "predecessor": None, "payload": {"title": title, "known_state": known, "question": question, "problem_kind": kind, "novelty_status": "Not searched beyond the paper and the stored sources.", "data_access": "The 19-page PDF was read in full; the supplement was not retrieved.",
                                                 "completeness": "recorded", "required_capabilities": capabilities, "downstream_uses": uses, "dependencies": [], "source": src(locator), "original": original or {}, "approach": "unknown", "scales": scales, "context_tags": tags}}

    tag = lambda cls, sp="Danio rerio": f"[species: {sp}; evidence_class: {cls}; source card: daane2021-pdf] "
    D = [
        claim("gx-daane-nr21-lat4a-gof", "Source statement (full text): the zebrafish dominant mutant nr21 carries T200K in lat4a and acts by gain of function",
              "Daane et al. report a dominant ENU mutant, nr21, with small adult fins and no statistically decreased body size; they mapped it to chromosome 15, found a nonsynonymous T200K change in a conserved domain of the L-type amino-acid transporter lat4a, and "
              "show by cis frameshift revertants that the effect is a gain of function. Zebrafish lacking lat4a have no fin phenotype.",
              tag("causal_intervention (as reported)") + "Read in the paper's own text and legends. " + pg("lat4a_map", "nr21_gof", "lat4a_null"), ["Figures were read from legends only; mutant data were not examined.", "The allele names are lat4 nr21 (dmh26) and lat4a del (mh152); the paper prints no ZFIN or Ensembl id."],
              "Results: Identification of leucine transporter lat4a as a regulator of fin size; Figure 3 (pdf p.%s)" % F["Figure 3"]["pdf_page"], "source_statement"),
        claim("gx-daane-kcnh2a-lof-gof", "Source statement (full text): longfin (lof) is a kcnh2a gain of function from cis-ectopic expression; an inversion breakpoint lies between kcc4a and kcnh2a",
              "The paper states that loss-of-function kcnh2a alleles in cis revert the longfin phenotype, so lof imparts a gain of function; long-read mapping found breakpoints at 23.174 Mb (upstream of prrx1a) and 24.075 Mb (between kcc4a and kcnh2a) in Zv11; "
              "and that ectopic kcnh2a expression is sufficient to drive fin overgrowth.", tag("causal_intervention (as reported)") + pg("lof_gof", "lof_breakpoints", "lof_ectopic"),
              ["Breakpoint positions are given to 0.001 Mb: the 24.075 Mb breakpoint is consistent with, not proof of, the position about 5.6 kb upstream of the ZFIN GRCz11 kcnh2a start (24,080,694).", "lof^dt2 and its revertants are not maintained, per the methods."],
              "STAR Methods: Mapping and mutational analysis of lof (dt2); Figure 3", "source_statement"),
        claim("gx-daane-fig4-fin-proportion-phenocopy", "Source statement (Figure 4, pdf p.%s): the lat4a x kcnh2a trans-heterozygote reproduces flying-fish fin proportions in zebrafish, not flight" % F["Figure 4"]["pdf_page"],
              "In nr21/lof trans-heterozygotes the paper reports elongated paired fins and a hypocercal caudal fin, with lat4a suppressing the overgrowth caused by increased potassium-channel function in the median fins; kcnh2a expression does not change with nr21, and the authors conclude the suppression acts downstream of bioelectric signalling.",
              tag("genotype_phenotype (as reported)") + "The phenocopy concerns relative fin proportions only. " + pg("fig4_title", "fig4_suppressor", "fig4_transhet", "fig4_phenocopy", "fig4_mechanism", "fig4_qrt"),
              ["No flight, gliding or aerodynamic measurement in zebrafish appears in the text read.", "The mechanism is not identified.", "The zebrafish alleles are not the flying-fish variants."], "Figure 4 (pdf p.%s) and Results" % F["Figure 4"]["pdf_page"], "source_statement"),
        claim("gx-daane-35species-lat4a-f326l", "Source statement (full text): a lat4a F326L substitution is shared across lineages with enlarged pectoral fins in a 35-species capture",
              "The authors pooled DNA of several individuals from each of 35 beloniform species and captured an average of 78.3% of targeted regions at 38.3-fold depth; they report a shared lat4a F326L substitution across lineages with enlarged pectoral fins, accelerated lat4a evolution in gliding lineages "
              "(phyloP p = 0.008 at the flying-fish ancestor), and one flying fish (P. brachypterus, elongated dorsal fin) lacking the convergent allele.", tag("sequence_annotation", "Beloniformes (35 species)") + pg("cap_species", "cap_coverage", "f326l", "f326l_caveat", "lat4a_phyloP", "sailfin"),
              ["Targeted capture of conserved regions from pooled individuals, not whole genomes.", "The authors cannot exclude incomplete lineage sorting or introgression.", "No functional test of F326L is reported in the text read; F326L (natural) is a different residue from T200K (laboratory)."],
              "Results: Convergent genetic signatures; Figure 2 (pdf p.%s); Table S1, S2, S3; Data S1B, S1G, S1J" % F["Figure 2"]["pdf_page"], "source_statement"),
        claim("gx-daane-data-s1a-fin-body-allometry", "Source statement: Data S1A holds paired fin and standard-length measurements of museum beloniform specimens (Figure 1B)",
              "The paper says paired fin and standard fish lengths were measured from beloniform specimens in the Harvard Museum of Comparative Zoology (Data S1A), that flying-fish pectoral fin length increases rapidly with body size, and that the allometric relationship was identical across two- and four-wing flying fishes.",
              tag("source_assessment", "Beloniformes") + "Data S1A is in the publisher's supplement, which is not part of the PDF and was not retrieved here (dx-submit is extracting it). " + pg("allometry_s1a", "allometry_rapid", "allometry_identical"),
              ["The measurements themselves were not read.", "'Identical' is the authors' description of Figure 1B."], "STAR Methods: Specimen tissue collection; Figure 1B (pdf p.%s)" % F["Figure 1"]["pdf_page"], "source_statement"),
        claim("gx-lat4a-is-probably-slc43a2a", "Inference (probable, not confirmed): the paper's lat4a is zebrafish slc43a2a (ZDB-GENE-040426-964)",
              "The paper maps nr21 to chromosome 15 and calls lat4a the zebrafish counterpart of mammalian Lat4 (Slc43a2). In ZFIN's GRCz11 gene models slc43a2a is on chromosome 15 and its paralog slc43a2b on chromosome 10. This is the working identification; the paper prints no accession for lat4a in the text read.",
              tag("source_assessment") + "Conflicting evidence kept: UniProt names the slc43a2b product 'Large neutral amino acids transporter small subunit 4'. A residue check could not test slc43a2a (its RefSeq protein is 153 residues, too short to contain residues 200 or 326) and is negative for slc43a2b (M200, D326 in NP_001008585.1).",
              ["Inferred from position, orthology naming and the suffix; not confirmed by an identifier, alignment or the supplement's mapping interval.", "Numbering across isoforms may differ."], "data/genomics/lat4a_resolution_v2.json", "derived"),
        claim("gx-daane-chain-gene-to-fin-shape", "Chain as reported: gene -> ion channel / amino-acid transporter -> fin outgrowth -> fin shape, in zebrafish, with context",
              "kcnh2a (potassium channel; lof gain of function, cis-ectopic expression) drives fin overgrowth; lat4a (L-type amino-acid transporter; nr21 T200K gain of function) shortens fins and suppresses the lof overgrowth in the median fins; "
              "together they give elongated paired fins and a hypocercal caudal fin. The intermediate mechanism is not identified, lat4a is not required for normal fin length, and the 35-species genomic data are correlational.",
              tag("causal_intervention, genotype_phenotype (as reported)") + "A map of what the paper reports, not a validated mechanism and not a prescription. Candidate perturbations are listed in daane2021_chain.json with their unknowns.",
              ["Genomes available is not a proven mutation map: no flying-fish variant is shown to change fin length.", "Nothing here transfers to another species or to a constructed organism."], "data/genomics/daane2021_chain.json", "derived"),
        problem("gx-problem-lat4a-accession", "Confirm lat4a = slc43a2a: the paper's mapping interval, its Lat4a alignment (Figure 3C) or an accession",
                "The working identification is slc43a2a by chromosome 15, orthology naming and suffix. Figure S2D-S2F (the mapping) is in the supplement; Figure 3C labels T200K; slc43a2a's RefSeq protein is too short to test residues 200 and 326.",
                "Is the paper's lat4a ZFIN slc43a2a (ZDB-GENE-040426-964), and what is its transcript?", "project_gap", ["the supplement's Figure S2", "a full-length slc43a2a protein", "the authors' accession"], ["Removes the 'inferred' label on lat4a."], "data/genomics/lat4a_resolution_v2.json", ["molecular"],
                ["species:Danio rerio", "evidence_class:source_assessment"], {"supersedes_for_status": "gx-problem-lat4a-identity (kept unchanged; records are append-only)"}),
        problem("gx-problem-daane-supplement", "Not retrieved: Tables S1-S3, Data S1A-S1N and Figures S1-S4 of Daane et al. 2021",
                "The supplement is on the publisher's site (doi 10.1016/j.cub.2021.08.054) and is not in the 19-page PDF. Data S1A holds the fin and body measurements (Figure 1B); dx-submit is extracting the empirical fit data.",
                "What do Data S1A-S1N and Tables S1-S3 contain in detail?", "project_gap", ["access to the supplement"], ["Empirical fin/body fits for the browser"], "daane2021_pins.json: supplement", ["organism", "evolutionary"], ["species:Beloniformes", "evidence_class:source_assessment"]),
        problem("gx-problem-f326l-function", "Untested: does the flying-fish lat4a F326L change transport or fin size, and in which direction?",
                "F326L is shared across lineages with enlarged pectoral fins; nr21 (T200K) shortens zebrafish fins. The paper does not, in the text read, test F326L or state its direction.",
                "What does F326L do in a transporter assay or in zebrafish?", "computational_open_question", ["a transporter assay or a zebrafish knock-in", "a longer slc43a2a model"], ["Would turn a correlation into a tested variant."], "daane2021_pins.json: f326l", ["molecular", "evolutionary"], ["species:Danio rerio", "evidence_class:causal_intervention"]),
    ]

    def evid(id_, target, kind, rel, locator, method, context, arts, lim):
        return {"namespace": NS, "kind": "Evidence", "id": id_, "issuer": ISSUER, "source_uri": "urn:frontier:connector:genomics", "visibility": "public", "predecessor": None,
                "payload": {"target": target, "evidence_kind": kind, "relation": rel, "source": src(locator), "created_time": {"value": card["retrieved_at"], "basis": "witnessed"}, "retrieved_time": {"value": card["retrieved_at"], "basis": "witnessed"},
                            "method": method, "context": context, "assumptions": [], "provenance": {"source_card": "daane2021-pdf", "pdf_sha256": pdf["sha256"], "pdf_pages": 19, "quotes_verified_verbatim": len(Qs)}, "source_dependence": {"declared": True, "independent_of_author": False, "note": "one operator read the paper and wrote the records; no independent review"},
                            "uncertainty": "Not quantified.", "limitations": lim, "artifacts": [aref(p, t, m, r) for p, t, m, r in arts]}}
    A = lambda p, t, m="application/json", r="output": (p, t, m, r)
    common = [A("data/genomics/daane2021_pins.json", "figure and table pins, verified quotes with pdf pages, accessions"), A("data/genomics/daane2021_source.json", "source card with the pdf hash", r="log")]
    E = [evid("gx-ev-daane-nr21", "gx-daane-nr21-lat4a-gof", "source_assessment", "supports", "Results and Figure 3", "Fetched the author-hosted PDF, extracted its text and checked every quoted sentence verbatim against it.", "The paper's own statements.", common, ["Legends and text only; no data examined."]),
         evid("gx-ev-daane-lof", "gx-daane-kcnh2a-lof-gof", "source_assessment", "supports", "STAR Methods; Figure 3", "Same, for the lof statements and breakpoints.", "The paper's own statements.", common + [A("data/genomics/genes.csv", "ZFIN GRCz11 spans used for the breakpoint consistency note", "text/csv", "input")], ["The 5.6 kb figure compares a three-decimal Mb breakpoint with a ZFIN GFF3 start."]),
         evid("gx-ev-daane-fig4", "gx-daane-fig4-fin-proportion-phenocopy", "source_assessment", "supports", "Figure 4, pdf page %s" % F["Figure 4"]["pdf_page"], "Same, for the Figure 4 legend and the Results sentences.", "The paper's own statements; the figure panels were not examined.", common + [A("data/genomics/daane2021_chain.json", "the chain and the candidate perturbations with unknowns", r="output")], ["Legend and text only."]),
         evid("gx-ev-daane-35species", "gx-daane-35species-lat4a-f326l", "source_assessment", "supports", "Results; Figure 2; STAR Methods", "Same, for the capture and F326L statements.", "The paper's own statements, including its own caveat.", common, ["Table S1-S3 and Data S1 were not read."]),
         evid("gx-ev-daane-s1a", "gx-daane-data-s1a-fin-body-allometry", "source_assessment", "context_only", "STAR Methods; Figure 1B", "Located the sentence that names Data S1A and the statements about Figure 1B.", "Pins where the empirical data are; the data were not read.", common, ["The supplement was not retrieved."]),
         evid("gx-ev-lat4a-mapping", "gx-lat4a-is-probably-slc43a2a", "source_assessment", "supports", "lat4a_resolution_v2.json", "Compared the paper's chromosome statement with ZFIN GRCz11 positions of slc43a2a and slc43a2b; fetched NCBI RefSeq proteins and a UCSC RefSeq model and tested residues 200 and 326.", "A positional and orthology inference with a negative and an inconclusive residue check.",
              [A("data/genomics/lat4a_resolution_v2.json", "the resolution with evidence for and against"), A("data/genomics/artifacts/ncbi_NP_956545.1_slc43a2a.faa", "NCBI RefSeq protein for slc43a2a (153 residues)", "text/plain", "input"), A("data/genomics/artifacts/ncbi_NP_001008585.1_slc43a2b.faa", "NCBI RefSeq protein for slc43a2b (592 residues)", "text/plain", "input"),
               A("data/genomics/artifacts/ucsc_slc43a2a_refseq_model.json", "UCSC danRer11 RefSeq model and the translation length", "application/json", "input")], ["Not confirmed by an accession.", "The residue check is inconclusive for slc43a2a and numbering across isoforms may differ for slc43a2b."])]
    made = {d["id"]: models.make_record(models.Draft.model_validate(d), created_at=CREATED_AT) for d in D}
    for e in E:
        e["payload"]["target"] = models.ref(made[e["payload"]["target"]])
        made[e["id"]] = models.make_record(models.Draft.model_validate(e), created_at=CREATED_AT)
    recs = list(made.values())
    bad = store._unlicensed_available_content(recs)
    if bad:
        raise SystemExit(f"licence gate: {bad}")
    (OUT / "daane2021_records.json").write_text(json.dumps({"records_schema": "genomics-records-0.1 (connector-local; frontier.models records)", "status": "proposed drafts; nothing submitted, reviewed or accepted", "namespace": NS, "issuer": ISSUER,
                                                            "append_only_note": "adds records; the 24 in records/records.json keep their versions. gx-problem-lat4a-identity there is superseded in status by gx-problem-lat4a-accession and the inference claim here, not edited.", "records": recs}, indent=1, sort_keys=True))
    import collections
    print(dict(collections.Counter(r["kind"] for r in recs)), "records; licence offenders:", len(bad))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
