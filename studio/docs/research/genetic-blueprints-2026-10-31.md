# Genetic implementation blueprints for fish traits (zebrafish evidence only)

Date: 2026-10-31. Status: PROPOSED designs and a sourced comparison. Nothing was executed, imported or reviewed, and no site file was edited.
Data package: `artifacts/genetic-blueprints/` (`blueprints.json`, `sources.json`, `manifest.json`, `check.py`).

## Question

What would a source-grounded, reporter-first genetic implementation look like for cell-specific expression in the fin, with the cargo, the carrier, the delivery and the integration kept apart, and where do the sources stop?

## Sources, with read-levels

| id | source | read-level | what was read |
|---|---|---|---|
| tree2016 | Nature 2016 doi:10.1038/nature17644 (TREE, lepb) | full-text | PMC author manuscript PMC4844022; abstract, lepb and LEN-module sections, discussion. The publisher page returned only references. |
| fin-multiome2025 | Genome Research 35(1):202 | full-text | abstract, enhancer-validation discussion, F0 reporter figure legends, methods; supplementary coordinates not read |
| fin-epigenome2020 | PMC7047409 | abstract | abstract only |
| promoter-compat2023 | PMC10211259 | full-text | abstract, Results on promoter leak in larval heart, eye and fin fold, ZSP, discussion; supplementary tables unread |
| bac-tol2-2011 | Nature Protocols doi:10.1038/nprot.2011.416 | abstract | subscription preview; protocol unread |
| piglet2024 | pIGLET, PMC11152119 (published; preprint PMC10723424 not used) | abstract | abstract and introduction opening |
| bac-plasmids2016 | BAC plasmid set, PMC4825653 | abstract | abstract and methods opening |
| hac2024 | Human artificial chromosomes, PMC11059994 | abstract | abstract and results opening; HUMAN cells only |
| knockin-cre2021 | Sci Rep doi:10.1038/s41598-021-81239-y | full-text | introduction, design legend, F0 and germline results |

Response bytes are not in the repository; their sha256 values are pinned in `sources.json`. The root research map (`bff3828`, sha256 `f7782821…`) and the native metadata audit (`1b77f81`, RESULTS.md only) are reused.

## What the designs are

Revision 2. Four proposed records: (1) a regeneration-enhancer reporter on a Tol2 plasmid; (2) the same architecture read in the developing pectoral fin field and the regenerating fin, to expose the gap; (3) an endogenous 2A-reporter knock-in at a locus to be chosen; (4) a reporter in a BAC clone integrated with Tol2. Design 1 uses a source-named candidate (the LEN enhancer from the TREE paper, with the lepb 2 kb promoter and EGFP; see the named-candidate section), with coordinates and sequence null because Methods and the supplement were not read. Design 2's comparator enhancers are root proposals. The knock-in locus (design 3) and the BAC clone (design 4) are left UNSPECIFIED because no source read names one for a fin trait. Effectors are none. No Evo2 call was made or rerouted.

## Comparison (not a ranking)

- **Tol2 plasmid.** Authors of the knock-in paper list multicopy integration, position effects and silencing as limits. Some minimal promoters leak (fos and DSCP) and enhancer-promoter pairs differ (full text of PMC10211259, larval assays; supplementary tables unread).
- **BAC transgenesis.** A BAC with an iTol2 cassette is a cargo carrier integrated by the transposon (about 15% germline transmission in the abstract). It is not an autonomous fish chromosome.
- **Endogenous knock-in.** Short-homology (48 bp) integration worked at three brain loci, with germline transmission of 100%, 10% and 20%. No fin locus was tested.
- **Transient delivery.** No source read covers it as a design. Stated as a gap.
- **Landing-site integration (pIGLET).** phiC31 attP sites with reported 25-50% germline transmission (abstract only); fin behaviour unread.
- **Truly autonomous artificial chromosome.** No source read describes one in fish. The single source read is a ~750 kb human artificial chromosome in human cells, delivered by yeast spheroplast fusion; it says nothing about fish.

## The named candidate (revision 2)

`bp-1` now instantiates one source-named natural element: **LEN**, the lepb-linked enhancer of the TREE paper, an isolated 1.3 kb sequence from the H3K27ac-rich region about 7 kb upstream of lepb, with fragments 1–850, 450–1000, 450–850 and 660–850 reported active from the lepb 2 kb promoter in fin regeneration. The construct is **LEN-P2:EGFP** (the name used in a PMC10211259 supplementary caption, where it is tested in adult F0 caudal fin; that figure was not read). Coordinates, assembly and sequence are **null**: they are in Methods or the supplement, which were not read. Every choice in `provenance_of_choices` is marked sourced or root proposal; no cell specificity is inferred for LEN (the blastemal observations are about reporter lines, and 'blastemal mesenchyme' is about the lepb:eGFP BAC reporter).

Each design is bound to a named map cell program with validation status unknown, and three cell-program blueprints (fin mesenchyme/ray, epithelium, neural/muscle observation interface) group them. The map has no neural or muscle row, so that program binds to none and says so.

## Specificity, off-target coverage, kinetics

Each design now carries `cell_stage_specificity`, `off_target_coverage`, `expression_kinetics` and `markers_status`. The only off-target data read are larval heart, eye and tail fin fold for promoters with a regeneration enhancer (e.g. 61% of LEN-fos larvae expressed in the fin fold, n=85; no larvae expressed with E1b, P0.8 or P2, n=227, 234, 402). Adult tissues and fin cell programs are not covered. Kinetics are UNKNOWN. Markers from the map are source-only, not validated drivers.

## Gaps stated first

1. **Developmental fin versus regeneration (scoped to the fish-fin trait bridge).** PMC10211259 tests developmental and regeneration enhancers in larval tissues (103runx1EN is described as acting in both modes; gata2a-i4 is developmental, endothelial). No source read shows any enhancer driving expression in the developing paired fin, or tying any enhancer to fin shape or stiffness.
2. Reporter expression is not control of a trait.
3. The metadata audit leaves replicate independence of the multiome and epigenome series unconfirmed.
4. Everything is *Danio rerio*; flying-fish transfer is unknown.
5. Most sources are abstract-only; the BAC protocols, pIGLET results and per-pair promoter tables are unread.

## Regulatory actors and claim-use ledger (revision 3)

`regulatory_actors` in blueprints.json separates role (TF, enhancer, promoter, marker; no signal was found in any source read) from evidence class (measured, inferred, causal perturbation, proposed). Only fosl1a and lef1 carry a TF role. fosl1a has a motif-enrichment inference and a mutant with delayed whole-fin regeneration (PMC7047409, full-text passages; locator "full text"); lef1 is a TF by the multiome paper's GRN degree-centrality ranking only, an inference. sp7, msx1b, prrx1b, cldni and fras1 are cluster markers or labelling handles. tbx5a and hand2 are absent from every source read and stay marker-only from the root map row. `claim_use_ledger` has one row per citation: statement, read depth, evidence class, designs using it, and the missing bridge. Source passages are quoted briefly with a locator; the ledger paraphrases scope rather than expanding quotes.

## Revisions

2026-10-31: first version.
2026-10-31 (later): revision 1 additions: added pIGLET, the 2016 BAC plasmid set and the human artificial chromosome source; read the full text of PMC10211259; added the specificity, off-target and kinetics fields.
2026-10-31 (revision 2): named the source LEN candidate with null coordinates; separated sourced from root-proposed choices; scoped the developmental-versus-regeneration negative; corrected read-level wording for PMC10211259 (full text read; the earlier text said abstract only); bound designs to map cell programs.
2026-10-31 (revision 3): fixed the design summary sentence that said every enhancer was unspecified (contradicted the named LEN candidate); added regulatory actors and the claim-use ledger; PMC7047409 raised to full-text with a scoped read_scope (passages searched, body not fully read).
