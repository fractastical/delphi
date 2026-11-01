#!/usr/bin/env python3
"""Produce zrs-analysis.json from the fetched sequences and the core alignment."""
import hashlib
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/tmp/claude-1000/-home-ubuntu-git-morphoswarm/507442cb-0fa9-4ade-b46c-d7b940105d10/scratchpad/limbless/zrs")
import zrs_lib as Z  # noqa: E402
from core_trim import read_fasta  # noqa: E402

ORDER = ["mouse", "human", "chicken", "lizard", "coelacanth", "elephant_shark",
         "eryx", "python", "king_cobra", "rattlesnake", "garter_snake"]
SNAKES = {"eryx", "python", "king_cobra", "rattlesnake", "garter_snake", "corn_snake"}
P_THRESH = 0.0032
E1_BLOCK = (1002, 1019)    # alignment columns of the 17 bp lizard-referenced deletion


def main():
    rec = json.load(open("seqs/final_set.json"))
    core_def = json.load(open("seqs/core_def.json"))
    aln = read_fasta("alignment.fasta.core")
    keys = [k for k in ORDER if k in aln]
    L = len(aln[keys[0]])
    rows = [aln[k] for k in keys]
    cons, depth, major = Z.column_conservation(rows)

    # mouse position for each alignment column (None inside insertions)
    mp, c = [], core_def["mouse_core"][0] - 1
    for i in range(L):
        if aln["mouse"][i] != "-":
            c += 1
            mp.append(c)
        else:
            mp.append(None)

    # ---- identity matrix -------------------------------------------------
    idm = {}
    for a in keys:
        idm[a] = {}
        for b in keys:
            pid, ident, nc = Z.pct_identity(aln[a], aln[b])
            idm[a][b] = round(pid, 2)

    # ---- ETS1 scan -------------------------------------------------------
    pfm = json.load(open("motifs/MA0098.3.json"))["pfm"]
    pwm = Z.PWM(pfm, "ETS1_MA0098.3")
    thr, dist = pwm.pvalue_threshold(P_THRESH)
    consensus = "".join(max("ACGT", key=lambda b: pfm[b][i]) for i in range(pwm.length))

    ets, col_of = {}, {}
    for k in keys:
        m = [i for i in range(L) if aln[k][i] != "-"]
        col_of[k] = m
        core_seq = aln[k].replace("-", "")
        hits = []
        for h in Z.scan(core_seq, pwm, thr):
            c0 = m[h["start"]]
            c1 = m[min(h["end"] - 1, len(m) - 1)]
            hits.append(dict(start=h["start"], end=h["end"], motif=h["motif"],
                             strand=h["strand"], score=h["score"],
                             pvalue=round(pwm.pvalue_of(h["score"], dist), 6),
                             aln_start=c0, aln_end=c1,
                             mouse_pos=mp[c0], inferred=True))
        ets[k] = sorted(hits, key=lambda x: x["aln_start"])

    # ---- the E1 deletion -------------------------------------------------
    s, e = E1_BLOCK
    liz_cols = [i for i in range(s, e) if aln["lizard"][i] != "-"]
    e1 = dict(
        aln_columns=[s, e],
        lizard_sequence="".join(aln["lizard"][i] for i in liz_cols),
        lizard_length=len(liz_cols),
        mouse_positions=[mp[i] for i in range(s, e) if mp[i] is not None],
        mm10=[29314497 + mp[s] - 1,
              29314497 + max(x for x in (mp[i] for i in range(s, e)) if x is not None) - 1],
        absent_in={k: (len([i for i in range(s, e)
                            if aln["lizard"][i] != "-" and aln[k][i] == "-"]))
                   for k in keys},
        ets1_hit_in_block={k: any(h["aln_start"] < e and h["aln_end"] >= s for h in ets[k])
                           for k in keys},
        inferred=True,
        note="Independently recovered, not taken from the paper. Columns gapped in a species "
             "relative to lizard; the paper's 17 bp figure is also lizard-referenced "
             "('a 17 bp sequence from the lizard ZRS ortholog was introduced into the python ZRS').")

    # ---- ClinVar ---------------------------------------------------------
    inz = json.load(open("clinvar/in_zrs.json"))
    hseq_g0 = int(rec["human"]["coords"].split(":")[1].split("-")[0])
    human_core_g0 = hseq_g0 + rec["human"]["sequence"].find(aln["human"].replace("-", ""))
    cv = []
    for v in inz:
        if v["clin"] not in ("Pathogenic", "Likely pathogenic", "Pathogenic/Likely pathogenic"):
            continue
        off = v["start"] - human_core_g0
        if not (0 <= off < len(col_of["human"])):
            continue
        c0 = col_of["human"][off]
        cv.append(dict(accession=v["acc"], variant=v["name"], chr7_grch38_pos=v["start"],
                       classification=v["clin"], aln_col=c0, mouse_pos=mp[c0],
                       column_conservation=round(cons[c0], 3),
                       in_ets1_motif=any(h["aln_start"] <= c0 <= h["aln_end"] for h in ets["human"])))

    # ---- retrievals / summary -------------------------------------------
    retrievals, summary = [], []
    for k in ORDER + ["corn_snake"]:
        r = rec[k]
        retrievals.append(dict(
            species=r["species"], common_name=r["common_name"], key=k,
            accession=r["source_accession"], source_kind=r["source_kind"],
            url=r["url"], coords=r["coords"], http_status=r["http_status"],
            bytes=r["bytes"], sha256=r["sha256"], length_bp=r["length"],
            retrieved_at=r["retrieved_at"], read_level=r["read_level"],
            zrs_detected=r["detected"], anchor=r["anchor"],
            note=r.get("note")))
        if k in keys:
            core = aln[k].replace("-", "")
            pid, ident, nc = Z.pct_identity(aln["mouse"], aln[k])
            summary.append(dict(
                species=r["species"], common_name=r["common_name"], group=r["group"],
                knockin_phenotype_in_kvon2016=r["knockin_phenotype_in_kvon2016"],
                pct_identity_to_mouse=round(pid, 2),
                compared_columns=nc, core_length_bp=len(core),
                n_ets_motifs=len(ets[k]),
                has_e1_ets_site=e1["ets1_hit_in_block"][k]))
        else:
            summary.append(dict(
                species=r["species"], common_name=r["common_name"], group=r["group"],
                knockin_phenotype_in_kvon2016=r["knockin_phenotype_in_kvon2016"],
                pct_identity_to_mouse=None, compared_columns=0, core_length_bp=0,
                n_ets_motifs=None, has_e1_ets_site=None,
                note="no ZRS detected; excluded from the alignment"))

    out = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        method=METHOD,
        retrievals=retrievals,
        alignment=dict(
            n_species=len(keys), species=keys, length=L,
            aligner="MAFFT v7.525 L-INS-i (--localpair --maxiterate 1000 --nuc)",
            core_definition=core_def,
            mouse_core_mm10=f"chr5:{core_def['mm10'][0]:,}-{core_def['mm10'][1]:,}",
            identity_matrix=idm,
            per_column_conservation=[round(x, 4) for x in cons],
            per_column_depth=depth,
            per_column_mouse_position=mp,
            fasta="alignment.fasta"),
        ets_sites=ets,
        ets_scan=dict(matrix="JASPAR MA0098.3 (ETS1, Homo sapiens)",
                      matrix_url="https://jaspar.elixir.no/api/v1/matrix/MA0098.3/",
                      consensus=consensus, length=pwm.length,
                      p_value_threshold=P_THRESH,
                      log_odds_threshold_bits=round(thr, 4),
                      background="uniform 0.25 per base",
                      threshold_method="exact upper-tail of the score distribution by convolution",
                      note="Kvon et al. used FIMO with ETS1 PWMs at p<0.0032; this is the same "
                           "threshold and the same kind of model, but not the same software, and "
                           "the site numbering E0-E4 of that paper is NOT reproduced here because "
                           "their coordinates were not accessible. Every site is marked inferred."),
        e1_deletion=e1,
        clinvar_pathogenic_in_zrs=cv,
        summary_table=summary,
        limitations=LIMITATIONS,
        sources=SOURCES,
    )
    json.dump(out, open("zrs-analysis.json", "w"), indent=2)
    print("wrote zrs-analysis.json")
    print(f"  species aligned: {len(keys)}, columns {L}")
    print(f"  ETS1 motifs per species: " + ", ".join(f"{k}={len(ets[k])}" for k in keys))
    print(f"  E1 block absent (vs lizard) in: " +
          ", ".join(f"{k}:{v}" for k, v in e1["absent_in"].items() if v))
    print(f"  ClinVar pathogenic SNVs mapped: {len(cv)}")
    return out


METHOD = (
    "Goal: a comparative, sequence-level picture of the ZRS limb enhancer across species whose "
    "orthologs Kvon et al. (2016) swapped into the mouse, to see what distinguishes the orthologs "
    "that supported normal limbs from the one that truncated them.\n\n"
    "1. REFERENCE. The mouse ZRS was taken as the exact 1,324 bp interval Kvon et al. deleted by "
    "CRISPR, mm10 chr5:29,314,497-29,315,820 (their Figure S3), fetched from GRCm38.p6 "
    "NC_000071.6. Positive control that this is the right interval: the fetched sequence is "
    "exactly 1,324 bp and contains the paper's stated sgRNA recognition sequence "
    "(AGTACCATGCGTGTGTGTGA) on the minus strand at offset 16, i.e. 'in close proximity to its "
    "5-prime border' as the paper describes; a 1-nt mutated copy of that motif is absent.\n\n"
    "2. ORTHOLOG RETRIEVAL. Kvon et al. deposited NO GenBank accessions for the ZRS orthologs - "
    "the sequences are in supplementary Tables S2/S3 and the constructs were chemically "
    "synthesised - and those supplementary PDFs could not be retrieved (see limitations). "
    "Orthologs were therefore re-derived from public genomes: for each species the annotated "
    "LMBR1 locus (the ZRS lies in LMBR1 intron 5) was fetched with a 10 kb flank, and the ZRS was "
    "located inside it by unique 12-mer seeding from the mouse ZRS followed by local affine-gap "
    "alignment (Biopython PairwiseAligner). Where a snake had diverged so far from mouse that "
    "only a short block aligned, the Burmese python ZRS - itself mouse-anchored - was used as a "
    "bridging anchor; the anchor used is recorded per species. Human was taken from GRCh38 "
    "chromosome 7 and cross-checked against the dedicated RefSeq record NG_042169.2 ('Homo "
    "sapiens ZPA regulatory sequence (ZRS)'), which matches the fetched window exactly while a "
    "1-nt mutant of it does not. King cobra came from scaffold183.1 of assembly AZIM01, the same "
    "king cobra assembly Kvon et al. used.\n\n"
    "3. ALIGNMENT. All detected orthologs were aligned with MAFFT v7.525 L-INS-i, the same "
    "program and mode the paper used. The fetched 1.3 kb windows extend beyond the conserved "
    "enhancer, and in those flanks the sequences are not homologous at nucleotide resolution; "
    "MAFFT fills them with arbitrary gaps, which manufactures 'shared deletions' that are "
    "artefacts. (This was caught by eye: the non-snake blocks aligned there share no similarity "
    "with each other.) So, as Kvon et al. did with Gblocks, the alignment was trimmed to its "
    "alignable core and realigned: mouse positions were scored by column depth and conservation, "
    "smoothed over 31 positions, and the longest run with conservation >= 0.70 and depth >= 0.80 "
    "was kept. That core is mouse ZRS 398-1043 (646 bp), mm10 chr5:29,314,894-29,315,539. "
    "Every quantitative result below is computed on the realigned core.\n\n"
    "4. MOTIFS. Each species' core was scanned on both strands with the JASPAR ETS1 matrix "
    "MA0098.3 (consensus ACCGGAAGTG), using a log-odds threshold derived by exact convolution of "
    "the score distribution under a uniform background so that p < 0.0032 means what it means in "
    "FIMO - the threshold Kvon et al. state. Controls: the consensus scores 15.94 bits and "
    "passes; poly-G, poly-C and poly-A all fail.\n\n"
    "5. HUMAN DISEASE VARIANTS. All 694 ClinVar LMBR1 variants were fetched and filtered to those "
    "falling inside the human ZRS record's GRCh38 interval, then mapped through the alignment by "
    "coordinate arithmetic. No variant position was taken from memory or from prose."
)

LIMITATIONS = [
    "This is a correlational, post-hoc analysis of a handful of sequences. It is NOT a predictor. "
    "With two knock-in species that gave normal limbs and two that truncated, no statistic "
    "computed here has the power to establish that any sequence feature causes the phenotype; "
    "the causal evidence is Kvon et al.'s mouse knock-ins, not this alignment.",
    "The sequences analysed are NOT the sequences Kvon et al. knocked in. Theirs were synthesised "
    "from supplementary Tables S2/S3, which could not be retrieved. These were re-derived from "
    "reference genomes, so they may differ from the constructs by assembly errors, strain or "
    "individual polymorphism, and by window boundaries.",
    "Species substitutions were necessary and change what the comparison means: the paper used "
    "boa constrictor (Assemblathon 2 assembly, not in NCBI) and speckled rattlesnake Crotalus "
    "mitchellii (JPMF01); this analysis uses Eryx miliaris (dwarf sand boa, a different basal "
    "snake, from a dedicated GenBank ZRS record) and Crotalus tigris. Thamnophis elegans was "
    "added and is not in the paper at all. Viper (JTGP01) was not analysed.",
    "Percent identity depends heavily on how much flanking sequence is included, and there is no "
    "single correct number. Mouse-human is 88.3% over the trimmed core, 78.6% over the full 1.3 kb "
    "window, and 85-86% over the best-aligning block alone. Kvon et al. state 73% for human vs "
    "mouse; they do not define the metric, so these numbers are NOT directly comparable to theirs "
    "and the discrepancy is a definitional difference, not a contradiction of either result.",
    "The core boundaries (mouse 398-1043) come from thresholds on a smoothed conservation profile. "
    "The thresholds were chosen by reading the profile's shoulder, but they are choices, and the "
    "identity numbers shift if they move.",
    "ETS site numbering E0-E4 from Kvon et al. is NOT reproduced. Their site coordinates were in "
    "inaccessible supplementary material, so no site here is claimed to be 'the' E1, E2 etc. "
    "Every motif call is marked inferred. The one exception in strength of evidence is the 17 bp "
    "deletion block, which was located independently by alignment and which the paper also "
    "describes as overlapping an ETS site.",
    "A PWM hit is a sequence match, not a measurement of binding. No ChIP, EMSA or reporter data "
    "were used here, and FIMO itself was not run - an equivalent threshold was recomputed.",
    "The corn snake negative ('no ZRS detected') is scoped: the whole annotated LMBR1 locus plus "
    "10 kb either side was searched with 12-mer seeding and local alignment using BOTH the mouse "
    "and the Burmese python ZRS as queries. It does not exclude a ZRS remnant elsewhere in the "
    "corn snake genome, nor one too diverged for these queries to find.",
    "Rattlesnake could not be assessed at the 17 bp site: MAFFT places unrelated sequence in those "
    "columns rather than a gap, so it is reported as not assessable there rather than as retaining "
    "the site. Its ETS1 scan returns no hit in that block.",
    "Alignment of sequences this diverged is itself uncertain. Different aligners or parameters "
    "will move indel placement, and the snake columns are where that uncertainty is largest.",
    "Model fidelity is not biological validity: reproducing Kvon et al.'s observations says these "
    "sequence relationships are real, not that any interpretation of limb loss built on them is.",
]

SOURCES = [
    dict(cite="Kvon EZ, Kamneva OK, Melo US, et al. Progressive Loss of Function in a Limb "
              "Enhancer during Snake Evolution. Cell. 2016;167(3):633-642.e11.",
         pmid="27768887", pmcid="PMC5484524", doi="10.1016/j.cell.2016.09.028",
         url="https://doi.org/10.1016/j.cell.2016.09.028",
         read_level="full-text",
         note="Full text read via the PubMed Central full-text tool. Supplementary Tables S1-S6, "
              "which contain the actual ortholog and knock-in sequences, were NOT read: see "
              "limitations."),
    dict(cite="Kvon EZ, Zhu Y, Kelman G, et al. Comprehensive In Vivo Interrogation Reveals "
              "Phenotypic Impact of Human Enhancer Variants. Cell. 2020;180(6):1262-1271.e15.",
         pmid="32169219", pmcid="PMC7179509", doi="10.1016/j.cell.2020.02.031",
         url="https://doi.org/10.1016/j.cell.2020.02.031",
         read_level="abstract",
         note="Abstract and bibliographic record only. CORRECTION: the PMID supplied in the brief "
              "for this paper, 32169217, is a different article entirely ('Liquid-Liquid Phase "
              "Transition Drives Intra-chloroplast Cargo Sorting', Cell 180(6):1144-1159, doi "
              "10.1016/j.cell.2020.02.045). The correct PMID is 32169219. The journal/volume/page "
              "citation given in the brief (Cell 180:1262-1271) was correct. Nothing in this "
              "analysis depends on this paper."),
    dict(cite="NCBI Nucleotide / E-utilities: GRCm38.p6 NC_000071.6; GRCh38.p14 NC_000007.14; "
              "NG_042169.2; AZIM01000183.1; MW653933.1; and the annotated LMBR1 loci listed in "
              "'retrievals'.",
         url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/", read_level="full-text",
         note="Every sequence used was fetched directly; exact URLs, HTTP status, byte counts and "
              "sha256 of each sequence are in 'retrievals'."),
    dict(cite="NCBI ClinVar, LMBR1 gene query (694 variant records).",
         url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&term=LMBR1[gene]",
         read_level="full-text",
         note="Fetched 2026-11-01; classifications are ClinVar's germline classifications as of "
              "that date and are revised over time."),
    dict(cite="JASPAR 2024 matrix MA0098.3 (ETS1, Homo sapiens).",
         url="https://jaspar.elixir.no/api/v1/matrix/MA0098.3/", read_level="full-text"),
    dict(cite="Katoh K, Standley DM. MAFFT multiple sequence alignment software version 7.",
         url="https://mafft.cbrc.jp/alignment/software/", read_level="listing",
         note="Software used (v7.525), not a source read for claims."),
]

if __name__ == "__main__":
    main()
