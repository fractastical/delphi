# Closing one loop on *Astyanax mexicanus*: the oca2 exon-21 deletion in Molino cavefish

Status: **PREREGISTERED — analysis not yet run at the time these lines were written.**
Everything above the `RESULT` heading was written before any assembly sequence was downloaded.

## 0. What this is

One narrow, falsifiable question, tested against public genome assemblies, with a
positive control and a must-fail control beside it.

## 1. The claim under test

Warren et al. 2021, *Nat Commun*, "A chromosome-level genome of *Astyanax mexicanus*
surface fish for comparing population-specific genetic differences contributing to trait
evolution." PMID 33664263 / PMC7933363. **Read-level: full-text** (Europe PMC
`fullTextXML`, 167,392 bytes, retrieved today).

Verbatim from that full text:

> "Consistent with the laboratory strains, exon 21 of oca2 is absent in all Molino
> cavefish samples ( n = 9, Supplementary Fig. 8 ). None of the other sequenced
> population samples harbor the same deletion of exon 21; however, we found smaller
> heterozygous or homozygous deletions in exon 21 in some wild samples of Pachón
> ( n = 5/9), Río Choy ( n = 1/9), and Tinaja (5/9) fish"

and

> "exon 24 is missing in Pachón"

The original source of the two-population albinism result is Protas et al. 2006,
*Nat Genet* 38(1):107-11, PMID 16341223, doi 10.1038/ng1700. **Read-level: abstract
only** — Europe PMC reports `isOpenAccess = N`, `inPMC = N`, sole full-text URL
"Subscription required". Its abstract says "We found different deletions in Oca2 in
each population" and **does not name the populations or the exons**. I therefore do
not quote exon numbers in Protas's voice; the exon numbers above are Warren et al.'s.

## 2. Why this is an independent test and not a re-read of the same evidence

Warren et al.'s exon-21 statement was made by aligning **short reads from wild-caught
fish** to the *Astyanax mexicanus* 2.0 **surface** reference. The chromosome-level
**de novo** assemblies `AstMex3_Molino` (GCA_023375845.1, BioSample SAMN26927110) and
`AstMex3_Tinaja` (GCA_023375835.1, SAMN26927012) are different data: single
laboratory fish, assembled independently, BioSamples registered after that paper.
Asking whether the exon-21 deletion is present in the Molino *assembly* is therefore a
test of the claim on data that did not produce it.

## 3. Preregistered design

**Question.** Is oca2 exon 21 — as annotated on the RefSeq surface assembly — absent
from the de novo Molino cave assembly, while present in the surface assembly?

**Method.** Extract every annotated oca2 exon from the surface assembly. For each
exon, emit its set of 24-mers (both strands). Search each target assembly's oca2-
bearing chromosome for exact 24-mer hits with `grep -F`. Report, per exon per
assembly, the fraction of that exon's 24-mers found. Exact 24-mers are used because
within-species divergence here is low, so a present exon should retain a large
fraction of exact 24-mers, and a deleted exon should retain none.

**Acceptance criterion (the loop closes POSITIVE if all three hold).**
1. Exon 21 has **0 of its 24-mers** found in the AstMex3_Molino assembly.
2. Exon 21 has a **non-zero and high** 24-mer fraction in the AstMex3_surface
   assembly — concretely, ≥ 0.50.
3. The flanking exons 20 and 22 are **present in Molino** at ≥ 0.50, so that the
   absence is exon-21-specific and not a failure to find the locus at all.

**Falsifier (the loop closes NEGATIVE, and I report that).** Exon 21's 24-mer
fraction in Molino is ≥ 0.50, i.e. the exon is plainly there. A value strictly
between 0 and 0.50 for exon 21 in Molino is **INCONCLUSIVE** by this design and will
be reported as inconclusive, not argued either way.

**Positive control.** The complete set of oca2 exons must be recoverable from the
surface assembly itself at a high fraction. If the pipeline cannot find surface exons
in the surface genome, the pipeline is broken and no absence claim may be made.

**Must-fail control.** For each real exon I also generate a length-matched,
base-composition-matched **shuffled** decoy sequence. Decoys must score **0** in every
assembly. If a decoy scores above 0, the matcher cannot come back empty and the
negative result is worthless.

**Second control (Tinaja), stated with its limitation.** Tinaja is a cave population
that is **not** albino. Warren et al. report exon 21 present in Tinaja but also report
"smaller heterozygous or homozygous deletions in exon 21 in some wild samples of
... Tinaja (5/9)". Tinaja is therefore a *weak* control and I preregister no pass/fail
threshold on it; I will report its number and nothing more.

**Stop rule.** If the oca2 locus cannot be located in the Molino assembly (exons 20
and 22 both below 0.50), I stop and report "could not test" rather than reporting an
absence. If total download exceeds ~2 GB or the wall clock on analysis exceeds
roughly 40 minutes, I stop and report where it stopped.

**Scope of any negative I report.** A "0 of N 24-mers" result is scoped to the
sequence I actually searched, which I will name by accession. It is not a statement
about the whole Molino genome unless I say I searched the whole Molino genome.

**Compute.** Every job under
`systemd-run --user --scope -p TasksMax=64 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=900`.

_Preregistration written at 2026-10-31 10:25 PDT. Host load at start: 7.82 10.08 12.27_
