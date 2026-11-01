# Natural fin sequence references and functional-context boundaries

This is public-source curation and executed reference-identity checking, not a new
functional assay. The frozen [protocol](../../artifacts/sequence-evidence/PROTOCOL.json)
precedes this ledger. The [ledger](../../artifacts/sequence-evidence/ledger.json)
contains 36 sequence records, 44 direction/context entries and four dependency
bridges; [checks](../../artifacts/sequence-evidence/checks.json) pin the actual
code and outputs. No new inference or wetlab action was performed.

## What is available

| Artifact | Exact identity | What it establishes |
| --- | --- | --- |
| fgf20a genomic DNA | NC_141021.1:17857305–17859368, minus, GRCz13ab | 2,064 reference bases, not the experimental dob allele or tested construct |
| fgf20a transcript | NM_001037103.2, 1,433 bases | Reference transcript; differs from spliced genome at transcript positions 627, 772, 803 |
| kcnh2a genomic DNA | NC_141022.1:27732334–27832956, plus, GRCz13ab | 100,623 reference bases, not the longfin regulatory inversion |
| kcnh2a transcript | NM_001042722.2, 6,703 bases | GenBank annotates substitutions and indels against genomic reference; exact allele equivalence is false |
| Existing Evo2 outputs | 32 unique 1,000-base outputs, original hashes retained | Computational candidates for eight original target labels; no expression assay |

Coordinates are one-based inclusive. NCBI genomic records are M-AB strain;
transcripts cite Tuebingen. Neither is silently identified with the EK experimental
fish. Genomic references currently resolve to **GRCz13ab**, not the GRCz11 assembly
of GSE261907. No liftover was performed. The kcnh2a comparison reports 3,447
unaligned position-wise differences, **not** 3,447 substitutions: indels can shift
alignment even with equal total lengths. Alignment was not attempted. Raw
NCBI annotations, strand conversions, FASTA bytes and hashes are retained.

The reused Evo2 labels are elavl3, fabp10a, gata1a, krt4, myl7, myod1, neurod1 and
sox10. They are not LEN/lepb, kcnh2a or fgf20a candidates. The original score table
contains 89 rows: nine natural continuation controls, 32 generated, 32 dinucleotide
shuffles and 16 GC-random controls. Only one natural row is marked fully held out.
All 32 outputs have their original likelihood score; likelihood is not function.
Previously stopped provider calls remain stopped.

## What the primary experiments support

[Kang et al., Nature 2016](https://doi.org/10.1038/nature17644), Figures 2/4 and
Extended Data 7–9, report injury-responsive LEN/P2 reporter activity in adult
zebrafish caudal fins. P2-only lacked adult caudal induction, while larval fin-fold
induction was reported: it is a context-specific negative control. Fragment and
promoter context change the output; weak long-exposure expression must not be
rounded to an absolute negative. Figure 5 reports context-specific fgf20a rescue
of regeneration in the mutant background. Current reference transcripts are not
the source constructs by assumption.

[Development 2020](https://doi.org/10.1242/dev.191262), Figure 6, reports loss of
injury-induced lepb expression after LEN deletion while fin regeneration remained
normal. This contradicts the inference that this expression response is necessary
for regrowth. [The promoter compatibility study](https://doi.org/10.1016/j.ydbio.2022.09.007)
also makes context transfer a question rather than a default.

[Daane et al., Current Biology 2021](https://doi.org/10.1016/j.cub.2021.08.054),
Figures 3/4, supports allele-dependent fin proportion effects in zebrafish, not
flight or a working flying zebrafish. The supplement/orthology-supported lat4a →
slc43a2a mapping is retained with its unresolved residue-numbering/isoform issue.
No mutant sequence was invented.

Exact source-defined LEN genomic interval/strand and full construct sequence
remain **unknown** here. The original study used Zv9. Article text was retrieved,
but supplement attempts returned a browser challenge, an empty Jina response,
an unavailable EuropePMC attachment, or timed-out browser download. A later
patent's ambiguous assembly/coordinate wording was not used as a substitute.
The full text's relative LEN fragment coordinates are not genomic coordinates.

## Forward and inverse contracts

`forward_evidence` carries the source species, allele, tissue, injury, stage and
promoter context with the measured readout. `reference_only` does not attach a
functional phenotype to a reference sequence. `inverse_proposal` holds a desired
readout and candidates or an explicit blocked/empty candidate set; it cannot carry
a demonstrated effect. The [validation plan](../../artifacts/sequence-evidence/validation-contract.json)
requires independently informative context-matched observations, not a model's
own likelihood or a forward/inverse round trip. Assay noise, sample size and
functional tolerances remain null until justified by measurements.

The next bounded questions are:

- Can the original LEN/P2 positive and adult P2-only control be assigned exact
  source-defined sequences and GRCz11 coordinates without guessed liftover?
- For independently source-resolved GSE261907 controls, is library-level interval
  accessibility injury-associated? Two libraries per timepoint without cell labels
  cannot establish cell-specific expression or candidate function.
- Which allele/context-specific expression effect explains the source fin-growth
  phenotype, and which measurement would connect it to material or geometry?

There is no calibrated expression → cell program → growth/material → geometry →
mechanics → flight path in this ledger. Changing upstream sequence/context must
invalidate dependent hypotheses, while independently pinned mechanical models can
remain valid within their own assumed inputs.

## Reproduction and scope of checks

Install `connectors/sequence_evidence/requirements.txt` (BioPython 1.88), then run
`python -m connectors.sequence_evidence.build --root .`. It uses pinned local
inputs, never a network/model call. Run `pytest tests/test_sequence_evidence.py -q`
and focused Ruff. Tests exercise actual references, mutations, source identity,
strand/assembly conversion, missing contexts, false function promotion and path
escape. These checks do not independently replicate the cited biology.

## Article redistribution and clean delivery

The three retrieved full PMC HTML responses are **not included** in this public
delivery. No Creative Commons redistribution grant was found in those exact
cached responses; permissions/copyright notices were read, with scope recorded in
`artifacts/sequence-evidence/article-source-receipts.json`. Public accessibility
is not a redistribution grant. Original full-text bytes remain in the private
source cache and original task branch; no user data was deleted and no pushed
history rewritten. The clean delivery branch has a new root-lineage base, not the
full-article commits as ancestors. URL, response byte count/hash, section/figure
locators, curated claim records and a GET/hash retrieval recipe remain. NCBI
sequence reference records are separate from the article full-text responses.
