# Closing one loop on *Astyanax mexicanus*: the oca2 exon-21 deletion in Molino cavefish

**Final status: loop CLOSED, result POSITIVE. The preregistered criterion was met as
written and was not revised. Bottom line in section 11.**

*(This three-line banner and everything from the `# RESULT` heading down were added
after the analysis ran. Sections 0-3 below are verbatim as written beforehand.)*

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

---

# RESULT

Everything above this line was written before any assembly sequence was downloaded.
Nothing above it has been edited since.

## 4. Data actually obtained

| What | Accession | Source | Bytes on disk | Check |
|---|---|---|---|---|
| Surface chr5 | CM041913.1 (= NC_064412.1) | EBI ENA `browser/api/fasta` | 59,268,951 | 58,297,222 bp, matches NCBI sequence report |
| Molino chr5 | CM041831.1 | same | 60,919,223 | 59,920,421 bp, matches |
| Tinaja chr5 | CM041856.1 | same | 60,642,572 | 59,648,305 bp, matches |
| Molino whole genome | GCA_023375845.1 | NCBI Datasets v2alpha | 402,778,100 (zip), 1.3 GB extracted | 1,361,196,561 bp expected |
| Surface oca2 locus, annotated | NC_064412.1:18,405,444-18,589,784 | NCBI `efetch` GenBank | 283,632 | 184,341 bp |

Every download byte-count was checked against the length NCBI's sequence report
states, not assumed from a zero exit code. The ENA FASTA header for CM041831.1
self-identifies as `isolate ESR-SI-002 ecotype Molino cave`, which is the Molino
label arriving from the data rather than from my filename.

**Reachability:** all anonymous HTTP. No credentials, no login, no controlled access.

## 5. The locus

The curated RefSeq transcript `NM_001320209.1` (oca2, *Astyanax mexicanus*) has
**24 exons**, mRNA 2,671 bp, on the minus strand of chromosome 5. Exons were
numbered in **transcript** order, i.e. reversed relative to genomic coordinates,
because the gene is on the minus strand — exon 1 is at the highest coordinate.
Exon 21 is **105 bp**, at NC_064412.1:18,464,523-18,464,627.

## 6. Controls, reported before the result they qualify

**Positive control — can the method find an exon that is there?**
All 24 oca2 exons were recovered from the surface assembly at **frac 1.000**, each
in a single tight locus, in strictly descending coordinate order from exon 1
(18,569,731) to exon 24, spanning 18,451,218-18,569,761. The pipeline finds exons.

**Must-fail control — can the method come back empty?**
Four length- and base-composition-matched **shuffled** decoys (of exons 20, 21, 22,
24) scored **0 in all three assemblies**. The matcher can return zero.

**Assembly-gap control — could a run of Ns masquerade as a deletion?**
The exon-20-to-exon-22 interval contains **0 N bases** in all three assemblies
(surface 15,988 bp / 0 N; Molino 11,573 bp / 0 N; Tinaja 12,656 bp / 0 N). The
Molino absence is not an assembly gap. This check was added after preregistration
and can only ever turn a positive into an inconclusive, never the reverse.

**Search-endpoint controls.** SRA organism query: 4,351 real / 0 for a fake taxon.
Europe PMC: 9 hits for the real query / 0 for the same query plus a nonsense token.
ENA FASTA: 200 + sequence for CM041831.1 / HTTP 404 for `ZZ999999.9`.

## 7. The measurement

Fraction of each exon's exact 24-mers found anywhere on chromosome 5:

| oca2 exon | Surface (AstMex3_surface) | **Molino (AstMex3_Molino)** | Tinaja (AstMex3_Tinaja) |
|---|---|---|---|
| 19 | 105/105 = 1.000 | 105/105 = 1.000 | 105/105 = 1.000 |
| 20 | 37/37 = 1.000 | 37/37 = 1.000 | 37/37 = 1.000 |
| **21** | **82/82 = 1.000** | **0/82 = 0.000** | **82/82 = 1.000** |
| 22 | 71/71 = 1.000 | 71/71 = 1.000 | 47/71 = 0.662 |
| 23 | 71/71 = 1.000 | 71/71 = 1.000 | 71/71 = 1.000 |

**Breakpoint localisation.** Anchoring on the exon-22 and exon-20 hits in each
assembly and mapping every uniquely-occurring 24-mer of the surface interval onto
the Molino interval: 9,890 of 15,965 surface 24-mers anchor uniquely. The offset
starts at 0 and ends at **-4,415**.

The profile is not a single step, and I state that precisely rather than rounding
it to one. Three jumps exceed 50 bp:

| offset jump | between surface positions | note |
|---|---|---|
| **-4,588 bp** | 18,464,458 and 18,469,069 | the dominant event |
| +144 bp | 18,460,612 and 18,460,660 | small intronic indel |
| +54 bp | 18,459,849 and 18,459,858 | small intronic indel |

Those three sum to -4,390; the remaining -25 is spread over indels below the 50 bp
threshold I used. The interval therefore differs by several independent indels, one
of which is two orders of magnitude larger than the rest.

**Exon 21 (18,464,523-18,464,627) lies inside the -4,588 bp jump**, near its
low-coordinate end. Exon 20 (18,469,728-18,469,787) and exon 22 lie outside it and
score 1.000 in Molino.

So the Molino assembly carries a **deletion of roughly 4.6 kb that removes oca2
exon 21 and adjacent intron, leaving the flanking exons untouched**, against a
background of ordinary small intronic indel polymorphism. The net difference across
the whole exon-20-to-22 interval is 4,415 bp; the deletion is the ~4.6 kb component
of that, bounded by the last anchoring 24-mer on each side rather than sequenced to
its exact breakpoints.

## 8. Verdict against the preregistered criterion

| Preregistered condition | Required | Observed | |
|---|---|---|---|
| 1. exon 21 k-mers in Molino | 0 | **0 of 82** | PASS |
| 2. exon 21 in surface | >= 0.50 | **1.000** | PASS |
| 3. flanking exons 20, 22 in Molino | >= 0.50 | **1.000, 1.000** | PASS |
| Must-fail decoys | 0 everywhere | **0 everywhere** | PASS |
| Positive control | surface exons found | **24/24 at 1.000** | PASS |

**The loop closes POSITIVE. The claim reproduces.**

Warren et al.'s "exon 21 of oca2 is absent in all Molino cavefish samples", made by
aligning short reads from wild-caught fish to the surface reference, is confirmed
on an independent de novo chromosome-level assembly of a laboratory Molino fish,
and the deletion is resolved to ~4.4 kb with its flanks intact.

## 8b. Independent validation that my "exon 21" is the literature's exon 21

The whole result hinges on an exon number, and mine came from the RefSeq transcript
`NM_001320209.1`, not from the papers. A one-off numbering difference would have
invalidated it silently. So I checked it against published oligonucleotides.

Ma et al. 2015, *PLoS ONE*, "Genome editing using TALENs in blind Mexican Cavefish",
PMC4361574, **read-level: full-text**, states:

> "The exon 24 Pachón and the exon 21 Molino deletions are indicated in red."
> "We designed two TALENs surrounding exon 21 ... These TALENs were designed at the
> exon-intron boundaries of exon 21"

I took their six published exon-21 TALEN oligos and searched the 58,297,222 bp
surface chromosome 5 (both strands):

| Published oligo (Ma et al. 2015) | Hits in surface chr5 | Position | Relative to my exon 21 | In Molino chr5 |
|---|---|---|---|---|
| TALEN1 left `AACATGTTTGTGTTGTT` | 1 | 18,464,642 | 15 bp outside, 3' side | **no** |
| TALEN1 right `CCGCCTCTGGCACAG` | 1 | 18,464,612 | inside | **no** |
| TALEN1 spacer `ATCTCCTCTGTCAGG` | 1 | 18,464,627 | at the boundary | **no** |
| TALEN2 left `AGACAACATCCCCTTCA` | 1 | 18,464,534 | inside | **no** |
| TALEN2 right `GTGTGACACAAAGCTTT` | 1 | 18,464,502 | 5 bp outside, 5' side | **no** |
| TALEN2 spacer `CCGCCACCATGGTAA` | 1 | 18,464,519 | at the boundary | **no** |
| *control* exon 9 TALEN left `GGTCCCTCTCTCGAT` | 1 | 18,545,991 | 81 kb away, at exon 9 | **yes** |
| *control* exon 21 PCR reverse primer | 1 | 18,464,198 | 306 bp outside, 5' side | **yes** |
| *must-fail* `TTTTGGGGCCCCAAAATTTT` | **0** | — | — | **no** |

Two things follow, and the second was not something I designed for.

1. **The numbering is confirmed.** Six oligos a different group designed "at the
   exon-intron boundaries of exon 21" each occur exactly once in 58 Mb, and all six
   land on the boundaries of the exon my RefSeq-derived numbering calls exon 21.
   My exon 21 is their exon 21.

2. **The deletion is confirmed a second time, with someone else's reagents.** All
   six exon-21 oligos are absent from Molino. The exon-9 TALEN oligo, 81 kb away in
   the same gene, is present in Molino — so this is not a failure to find oca2. And
   the exon-21 PCR *reverse* primer, which sits 306 bp outside the breakpoint I
   computed independently, **is** present in Molino. That primer's position agrees
   with the breakpoint interval (18,464,458-18,469,069) derived from the k-mer
   offset profile, by two separate routes.

**One honest negative in that table.** Ma et al.'s exon-21 PCR *forward* primer
`GAGAGTTTACCCAAAGCAGAGTG` has **0** hits in the surface assembly, on either strand.
I do not know why; candidates are a strain difference from the 2015 laboratory fish,
an assembly difference, or a transcription error in the paper. I report it rather
than dropping it. It does not bear on the result: the other seven oligos all map
uniquely and consistently, and the must-fail oligo scores 0, so the search works.

## 9. What this does NOT show, and one defect in my own metric

**A defect in my metric, which I am reporting because it is mine.** The fraction is
`distinct matched strings / forward k-mer count`, and matched strings include
reverse-complement forms. For an exon whose sequence occurs on both strands
somewhere — i.e. a repeat — the fraction can exceed 1. Exon 24 reports **1.075 in
surface and 1.068 in Molino**, with hits scattered from position 84,559 to
58,252,200, which is the signature of repetitive sequence, not of a 185 bp exon.
Consequences:
- The defect can only ever **inflate** a count. It cannot manufacture a zero.
  The exon-21 result (0/82 in Molino) and the flanking 1.000s are unaffected.
- **I therefore draw no conclusion whatever about exon 24.** I did not test the
  Pachón exon-24 claim and the exon-24 numbers above must not be read as evidence
  about it.

**n = 1 per population.** Each assembly is a single laboratory fish. This shows the
deletion in one Molino individual. It is not a population frequency and says nothing
about the 9/9 count Warren et al. report for wild-caught Molino fish — that count
I have not checked.

**Interval length alone is not diagnostic, and the Tinaja number shows why.** The
exon-20-to-22 interval is 15,988 bp in surface, 12,656 bp in Tinaja and 11,573 bp in
Molino. Tinaja is **3,332 bp shorter than surface and still has exon 21 at 82/82**.
There is independent indel polymorphism in these introns. Only the exon-21
presence/absence is the measurement; the span length is context.

**Tinaja was a weak control and I preregistered it as such.** Warren et al. report
"smaller heterozygous or homozygous deletions in exon 21 in some wild samples of ...
Tinaja (5/9)". I set no threshold on Tinaja and set none afterwards. Its 82/82 is
reported, not scored.

**Exact 24-mer matching is strict.** Tinaja exon 22 scores 0.662 purely from
sequence divergence while plainly being present. So a *low but nonzero* value is
genuinely ambiguous — which is why the preregistration declared 0 < frac < 0.50
INCONCLUSIVE rather than negative. Molino exon 21 landed at exactly 0, not in that
band.

**This says nothing about causation.** That the exon-21 deletion causes loss of
OCA2 function, and that this causes albinism, is Protas et al.'s cell-based assay and
Warren et al.'s cross. I tested neither. I tested whether the lesion is in the
assembly.

**Read-levels, stated so nothing is quoted above its evidence.**
- Warren et al. 2021, PMC7933363 — **full-text** (Europe PMC XML, 167,392 bytes).
  All exon-number quotes are from this.
- Protas et al. 2006, PMID 16341223 — **abstract only**; Europe PMC
  `isOpenAccess = N`, `inPMC = N`, only full-text URL "Subscription required". Its
  abstract names neither population nor exon. I have not quoted it as if I read it.
- Warren et al. Supplementary Figs. 7 and 8, which carry the underlying per-sample
  evidence for the exon-21 statement — **could-not-access**. I did not open them.
- NCBI/ENA records (BioSample, sequence reports, assembly reports) — **full record**,
  fetched directly, not via a summary.

**Scope of the negative.** See section 10.

## 10. Scope of the negative

The finding is an absence, so the scope matters more than the number.

**What was searched.** Every position of three complete chromosomes, both strands,
for exact 24-mers: surface chr5 CM041913.1 (58,297,222 bp), Molino chr5 CM041831.1
(59,920,421 bp), Tinaja chr5 CM041856.1 (59,648,305 bp). Plus the Ma et al. oligos
over surface and Molino chr5.

**What that search could not have found.**
- **Exon 21 somewhere else in the Molino assembly.** Chromosome 5 is 59.9 Mb of the
  assembly's 1,361,196,561 bp across 108 sequences. A copy of exon 21 on another
  chromosome or an unplaced scaffold would not appear in the chr5 scan. (Extended
  below.)
- **A diverged copy.** Exact 24-mer matching finds nothing with a substitution
  every <24 bp. A heavily diverged paralogue of exon 21 would read as absent.
- **A heterozygous state.** These are haploid assemblies (`assembly_type: haploid`).
  A heterozygous deletion could be collapsed to one allele. I cannot distinguish
  homozygous from heterozygous from an assembly.
- **Anything about other Molino individuals, or about wild Molino fish.** n = 1.
- **Anything about Pachón.** No Pachón chromosome-level assembly was used. The one
  candidate in the NCBI list, GCA_004802775.1 (`Astyanax_mexicanus-1.0.2`,
  BioSample SAMN11404277), is scaffold-level and I did not verify its population
  label or search it. The exon-24 claim is untested here.
- **Anything about expression or protein.** Only genomic sequence was examined.

### 10a. The negative extended to the whole Molino genome

The chromosome-scoped negative was then widened. The complete `AstMex3_Molino`
assembly was downloaded from NCBI Datasets (402,778,100 byte zip, 1.3 GB extracted)
and every base of it searched: **108 records, 1,361,196,561 bp**, which matches the
assembly total NCBI reports exactly. Searched as exact 24-mers, both strands.

| label | patterns | records containing any hit | grep exit |
|---|---|---|---|
| **exon 21 (the test)** | 164 | **0** | 1 (no match) |
| exon 20 (positive control) | 74 | 1 | 0 |
| exon 22 (positive control) | 142 | 1 | 0 |
| shuffled decoy of exon 21 (must-fail) | 164 | **0** | 1 (no match) |

So **oca2 exon 21 is absent from the entire Molino assembly**, not merely from
chromosome 5, while its two flanking exons are each found in exactly one place —
the single-copy locus on chromosome 5.

**A broken run the controls caught, reported because it nearly became a result.**
The first genome-wide attempt timed out at its 900 s cap having covered
1,274,665,077 of 1,361,196,561 bp, and printed no tallies — and the shell reported
`exited with code 0`, which was the exit status of the `tail` at the end of the
pipeline, not of the scan. The second attempt completed but returned only **5**
distinct matched k-mers across all four labels. That number is uninterpretable, and
the positive control is what said so: exons 20 and 22 are *known* present in Molino
at 37/37 and 71/71 on chromosome 5, so a method returning 5 was not measuring what
I thought. The cause is that `grep -o` here is ugrep 7.8.4 and reports only
**non-overlapping** matches; consecutive 24-mers of one exon overlap by 23 bp, so
after each hit the scanner skips past the next. The 5 hits are exactly the
maximum number of non-overlapping 24-mers in a 60 bp and a 94 bp exon (2 + 3).
The table above therefore reports **presence/absence per label**, which
non-overlapping matching answers correctly, rather than a k-mer count, which it
does not. An independent single-pattern check in Python over the same 1,361,203,941
bytes agreed: exon 20's and exon 22's leading 24-mers occur once each (on the
reverse strand, as expected for a minus-strand gene) and exon 21's occurs zero times
on either strand.

Had I shipped the count without the positive control, I would have reported "5
k-mers found" as if it meant something.

---

## 11. Bottom line

**One loop, closed, positive.**

A specific published claim — Warren et al. 2021, "exon 21 of oca2 is absent in all
Molino cavefish samples", made from short reads of wild-caught fish aligned to the
surface reference — **reproduces on an independent de novo chromosome-level assembly
of a laboratory Molino fish released 14 months later**. Exon 21 is absent from all
1,361,196,561 bp of that assembly. The flanking exons 20 and 22 are intact. The
lesion is a deletion of roughly 4.6 kb. Six TALEN oligonucleotides another group
published as targeting the exon-21 boundaries all map uniquely to the boundaries of
the exon my numbering calls 21, and all six are absent from Molino, while their
exon-9 oligo is present.

Every number above was measured on data named by accession. The preregistered
criterion was met as written and was not revised. Positive and must-fail controls
accompany every search, and one of them caught a broken run before it became a
finding.

What this does **not** establish is in section 9: n = 1 per population, no causal
claim, no test of the Pachón exon-24 claim, and no statement about wild populations.

---

## 12. Appendix A — the N-gap check, specific to exon 21

*(Added after the result, at the team lead's request. It can only weaken the
finding, never strengthen it: a run of Ns over the exon-21 position would make the
absence an assembly gap rather than a deletion, and would move the verdict to
inconclusive. It did not.)*

An assembly gap is the one alternative explanation the preregistered criterion
cannot distinguish by itself, so the N-detector needs its own positive control —
otherwise "0 Ns" and "my N-counter is broken" read identically.

**Positive control: do these assemblies contain detectable N-runs at all?**

| assembly | chr5 length | total N | N-runs | longest run |
|---|---|---|---|---|
| surface CM041913.1 | 58,297,222 | **0** | 0 | 0 |
| **Molino CM041831.1** | 59,920,421 | **2,000** | **4** | 500 bp |
| Tinaja CM041856.1 | 59,648,305 | 500 | 1 | 500 bp |

The control passes **on the assembly that matters**. Molino is where the absence is
claimed, and Molino chromosome 5 does contain N-gaps, four of them, which the same
counter finds. So a zero from this counter on Molino is a measurement, not a
silence.

Note the asymmetry honestly: **surface chr5 contains no N at all**, so on surface
the N-detector has no positive control. That does not matter here, because surface
is where exon 21 is *present* at 82/82; an assembly gap is not a competing
explanation for finding something.

**The measurement.**

| region | length | N |
|---|---|---|
| surface, exon 21 itself, 18,464,523-18,464,627 | 105 bp | **0** |
| surface, the deletion window 18,464,458-18,469,069 | 4,612 bp | **0** |
| surface, exon 21 +/- 5 kb | 10,105 bp | **0** |
| **Molino, the whole exon-20-to-22 interval 19,325,244-19,336,816** | **11,573 bp** | **0** |
| Tinaja, exon 21 +/- 5 kb | 10,082 bp | **0** |

**Where Molino's four N-runs actually are**, since "0 in the window" is only
meaningful with their positions:

| N-run on Molino chr5 | length | distance to the oca2 locus |
|---|---|---|
| 7,065,125 - 7,065,624 | 500 bp | 12,259,620 bp |
| 18,330,723 - 18,331,222 | 500 bp | **994,022 bp** (nearest) |
| 36,064,757 - 36,065,256 | 500 bp | 16,727,941 bp |
| 47,595,632 - 47,596,131 | 500 bp | 28,258,816 bp |

The nearest gap in the Molino assembly is **994 kb** from the locus. The contracted
interval is contiguous sequence. **The absence of exon 21 is not an assembly gap.**

## 13. Appendix B — exact reproduction

Accessions and the byte lengths they returned, so a mismatch is visible rather than
assumed:

| file | accession | bp | bytes |
|---|---|---|---|
| `chr5_surface.fa` | CM041913.1 (= NC_064412.1) | 58,297,222 | 59,268,951 |
| `chr5_molino.fa` | CM041831.1 | 59,920,421 | 60,919,223 |
| `chr5_tinaja.fa` | CM041856.1 | 59,648,305 | 60,642,572 |
| `molino_wg.zip` | GCA_023375845.1 | 1,361,196,561 (108 records) | 402,778,100 |
| `oca2_surface_locus.gb` | NC_064412.1:18,405,444-18,589,784 | 184,341 | 283,632 |

```sh
# 1. the three chromosomes (EBI ENA; a bogus accession returns HTTP 404, so this
#    endpoint can come back empty)
for p in CM041913.1:surface CM041831.1:molino CM041856.1:tinaja; do
  systemd-run --user --scope -p TasksMax=64 -p MemoryMax=4G -p MemorySwapMax=0 \
    -p RuntimeMaxSec=900 \
    curl -sS --max-time 880 -o "chr5_${p##*:}.fa" \
      "https://www.ebi.ac.uk/ena/browser/api/fasta/${p%%:*}"
done

# 2. the annotated surface oca2 locus, padded 20 kb each side
curl -sS "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore\
&id=NC_064412.1&seq_start=18405444&seq_stop=18589784&rettype=gbwithparts&retmode=text" \
  -o oca2_surface_locus.gb

# 3. exons in TRANSCRIPT order (the gene is on the minus strand, so exon 1 is the
#    HIGHEST coordinate and the join() interval list must be reversed), plus the
#    shuffled must-fail decoys
python3 -I parse_exons.py            # -> exons.json ; 24 exons, mRNA 2,671 bp

# 4. the measurement
python3 -I scan.py surface molino tinaja     # -> scan_results.json
python3 -I breakpoint.py                     # offset profile / deletion window
python3 -I numbering_check.py                # Ma et al. 2015 oligos vs my exon 21
python3 -I ngap.py                           # Appendix A

# 5. genome-wide. NOTE: `grep -o` here is ugrep 7.8.4 and reports only
#    NON-OVERLAPPING matches, so a k-mer COUNT from it is wrong. Use presence/
#    absence per label, which it answers correctly.
curl -sS -L -o molino_wg.zip "https://api.ncbi.nlm.nih.gov/datasets/v2alpha/genome/\
accession/GCA_023375845.1/download?include_annotation_type=GENOME_FASTA"
python3 -I wg2_prep.py <the .fna> flat.txt pats.txt    # 4 MB chunks, 23 bp overlap
for L in exon21_TEST exon20_POSCTRL exon22_POSCTRL DECOY21_MUSTFAIL; do
  grep -c -F -f "pats_$L.txt" flat.txt; echo "rc=$?"
done
# expected: exon21_TEST 0 (rc 1), exon20 1 (rc 0), exon22 1 (rc 0), DECOY 0 (rc 1)
```

Scripts are in
`/tmp/claude-1000/-home-ubuntu-git-morphoswarm/9fd16842-507d-49d0-a92a-82363be6489e/scratchpad/cavefish/`
(`parse_exons.py`, `scan.py`, `breakpoint.py`, `numbering_check.py`, `wg2_prep.py`,
`ngap.py`). They are session-scratch and will not survive; the commands above
reconstruct them from the accessions, which are the durable part.

Every job ran under
`systemd-run --user --scope -p TasksMax=64 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=900`.

---

## 14. Appendix C — the Tinaja arm: provenance of "not albino", and the one non-unity cave number

*(Added after the result, at the team lead's request, who flagged that this is the
claim that would most improve the finding and therefore the one to distrust most.
He was right to ask: at preregistration time it was recall.)*

### 14.1 Provenance, stated plainly

When I wrote "Tinaja is a cave population that is **not** albino" into the
preregistration, that was **background knowledge, not retrieved**. What I had
actually retrieved at that moment was BioSample SAMN26927012's `/ecotype="Tinaja
cave"`, which establishes *cave* and says nothing about pigment. The claim was
unsourced for the whole run.

**It has a retrieved source now.** Jeffery WR, "*Astyanax* surface and cave fish
morphs", *EvoDevo* 2020, PMID 32676179, PMC7353729, open access CC BY.
**Read-level: full-text.** Verbatim:

> "The loss of melanin pigmentation is caused by differentiation of fewer
> melanophores, reduced melanin synthesis, which leads to brown coloration in some
> cavefish populations (e.g., Tinaja), and the complete loss of melanin, which
> results in albinism in other cavefish populations (e.g., Pachón and Molino)"

That sentence contrasts the two cases explicitly and puts Tinaja on the brown,
non-albino side and Molino on the albino side. Two further qualifications, because
they bound what it supports: it is a **review**, and it attributes that sentence to
its own reference [23], which I did **not** open — so this is a review's
characterisation, read at full text, not the primary measurement. And it describes
the populations, not the two specific laboratory individuals these assemblies were
built from.

### 14.2 Does Tinaja carry a *different* oca2 lesion? My data answers this directly

This was the lead's decisive objection: if Tinaja has some other oca2 lesion, then
82/82 at exon 21 is unremarkable and the specificity framing collapses. I had
reported only exons 19-23. The full table:

| exon | surface | Molino | Tinaja |   | exon | surface | Molino | Tinaja |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.000 | 1.000 | 1.000 | | 13 | 1.000 | 1.000 | 1.000 |
| 2 | 1.000 | 0.991 | 1.000 | | 14 | 1.000 | 0.793 | 1.000 |
| 3 | 1.000 | 1.000 | 0.959 | | 15 | 1.000 | 1.000 | 1.000 |
| 4 | 1.000 | 1.000 | 1.000 | | 16 | 1.000 | 1.000 | 1.000 |
| 5 | 1.000 | 1.000 | 1.000 | | 17 | 1.000 | 1.000 | 1.000 |
| 6 | 1.000 | 1.000 | 1.000 | | 18 | 1.000 | 1.000 | 1.000 |
| 7 | 1.000 | 0.822 | 0.726 | | 19 | 1.000 | 1.000 | 1.000 |
| 8 | 1.000 | 1.000 | 1.000 | | 20 | 1.000 | 1.000 | 1.000 |
| 9 | 1.000 | 1.000 | 1.000 | | **21** | **1.000** | **0.000** | **1.000** |
| 10 | 1.000 | 1.000 | 1.000 | | 22 | 1.000 | 1.000 | 0.662 |
| 11 | 1.000 | 0.814 | 0.814 | | 23 | 1.000 | 1.000 | 1.000 |
| 12 | 1.000 | 1.000 | 1.000 | | 24 | *1.075* | *1.068* | *0.913* |

**No oca2 exon is absent in Tinaja. All 24 are present.** Exon 21 in Molino is the
only zero in the entire table, and the next lowest value anywhere is 0.662.
(Exon 24's values above 1 are the metric defect of section 9; no conclusion is drawn
from that row.)

### 14.3 The 0.662, which I had not explained

Tinaja exon 22 reads 47 of 71. By direct alignment of the Tinaja genomic sequence
against the surface exon, that interval contains **exactly one mismatch**: surface
`G` to Tinaja `A`, at position 49 of the 94 bp exon.

A single interior substitution destroys every 24-mer window spanning it, which is 24
of them. Predicted survivors: **47 of 71**. Observed: **47 of 71**. The arithmetic
reproduces the number exactly.

The same check on the other non-unity value I could test, Molino exon 7 at 0.822:
one mismatch, surface `T` to Molino `C` at position 124 of 158; predicted 111 of
135; observed 111 of 135.

So the reduced values are **point substitutions, not lesions**, and the metric is
behaving exactly as a k-mer metric must under single-base divergence. This is also
the answer to the lead's third point: the metric defect inflates and cannot produce
a zero, and 0.662 is neither — it is simply one SNP.

**What I did not determine:** whether that G-to-A substitution changes the OCA2
protein. I did not translate it and I make no claim about it. For what it is worth
from the literature rather than from my data, Ma et al. 2015 (PMC4361574,
**full-text**) state: "Two cavefish populations contain coding deletions in oca2
when compared to the surface population. Exon 21 is deleted in Molino fish, and a
portion of exon 24 is deleted in Pachón cavefish" — naming two, not three.

### 14.4 What the Tinaja arm now supports, and what it does not

**Supports:** within these three assemblies, the oca2 exon-21 deletion is present in
the albino cave population and absent from the brown cave population and from
surface. It therefore tracks albinism rather than cave-dwelling. That is a stronger
statement than the preregistered one.

**Does not support:** anything with n > 1 per population. Three fish. The
pigmentation phenotypes come from a review describing populations, not from these
individuals, which were not phenotyped by me and whose BioSamples record ecotype
but not pigment. And the Tinaja exon-22 SNP is uncharacterised. **This is a
suggestive specificity observation, not a tested hypothesis** — it was not
preregistered, and it must not be reported with the same confidence as the exon-21
result, which was.
