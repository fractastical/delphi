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

Four proposed records: (1) a regeneration-enhancer reporter on a Tol2 plasmid; (2) the same architecture read in the developing pectoral fin field and the regenerating fin, to expose the gap; (3) an endogenous 2A-reporter knock-in at a locus to be chosen; (4) a reporter in a BAC clone integrated with Tol2. Every enhancer, locus, BAC clone, reporter and effector is left UNSPECIFIED because no source read supplies one. No Evo2 call was made or rerouted.

## Comparison (not a ranking)

- **Tol2 plasmid.** Authors of the knock-in paper list multicopy integration, position effects and silencing as limits. Some minimal promoters leak and promoter-enhancer pairs differ (abstract only).
- **BAC transgenesis.** A BAC with an iTol2 cassette is a cargo carrier integrated by the transposon (about 15% germline transmission in the abstract). It is not an autonomous fish chromosome.
- **Endogenous knock-in.** Short-homology (48 bp) integration worked at three brain loci, with germline transmission of 100%, 10% and 20%. No fin locus was tested.
- **Transient delivery.** No source read covers it as a design. Stated as a gap.
- **Landing-site integration (pIGLET).** phiC31 attP sites with reported 25-50% germline transmission (abstract only); fin behaviour unread.
- **Truly autonomous artificial chromosome.** No source read describes one in fish. The single source read is a ~750 kb human artificial chromosome in human cells, delivered by yeast spheroplast fusion; it says nothing about fish.

## Specificity, off-target coverage, kinetics

Each design now carries `cell_stage_specificity`, `off_target_coverage`, `expression_kinetics` and `markers_status`. The only off-target data read are larval heart, eye and tail fin fold for promoters with a regeneration enhancer (e.g. 61% of LEN-fos larvae expressed in the fin fold, n=85; no larvae expressed with E1b, P0.8 or P2, n=227, 234, 402). Adult tissues and fin cell programs are not covered. Kinetics are UNKNOWN. Markers from the map are source-only, not validated drivers.

## Gaps stated first

1. **Developmental fin versus regeneration.** Every enhancer item read is from regenerating adult fin. The TREE authors only suspect development-and-injury elements. Nothing shows the same element works in fin development, or sets fin shape.
2. Reporter expression is not control of a trait.
3. The metadata audit leaves replicate independence of the multiome and epigenome series unconfirmed.
4. Everything is *Danio rerio*; flying-fish transfer is unknown.
5. Most sources are abstract-only; the BAC protocols, pIGLET results and per-pair promoter tables are unread.

## Revisions

2026-10-31: first version.
2026-10-31 (later): added pIGLET, the 2016 BAC plasmid set and the human artificial chromosome source; read the full text of PMC10211259; added the specificity, off-target and kinetics fields.
