# ZRS comparative analysis — working notes

Artifact for the "how would you make a limbless mouse?" page. Everything here was fetched or
computed on 2026-11-01; nothing is quoted from memory. Outputs: `zrs-analysis.json`,
`zrs-conservation.png` / `.svg`, `alignment.fasta`, these notes.

**The honest one-line summary:** the single sequence feature that separates the ZRS orthologs
that supported normal limbs from the ones that truncated them is a 17 bp deletion carrying an
ETS1 binding site — present in all six limbed/finned vertebrates, absent in all five snakes.
Overall divergence from mouse does **not** separate them, and neither does total ETS motif count.
This is a correlational, post-hoc observation on eleven sequences and four knock-ins. It is not a
predictor.

---

## 1. What the headline numbers are

| species | knock-in result (Kvon 2016) | % identity to mouse (core) | ETS1 motifs | E1 site |
|---|---|---|---|---|
| *Mus musculus* (mouse) | reference | 100.00 | 8 | present |
| *Homo sapiens* | **normal limbs** | 88.34 | 6 | present |
| *Gallus gallus* (chicken) | not knocked in | 82.19 | 7 | present |
| *Anolis carolinensis* (green anole) | not knocked in | 78.91 | 9 | present |
| *Latimeria chalumnae* (coelacanth) | **normal limbs** | 75.32 | 7 | present |
| *Callorhinchus milii* (elephant shark) | not knocked in | 65.19 | 5 | present |
| *Eryx miliaris* (dwarf sand boa) | not knocked in | 74.75 | 7 | **absent** |
| *Python bivittatus* (Burmese python) | **severe truncation** | 76.05 | 5 | **absent** |
| *Ophiophagus hannah* (king cobra) | **truncation, both limb pairs** | 62.35 | 4 | **absent** |
| *Crotalus tigris* (tiger rattlesnake) | not knocked in | 64.42 | 7 | **absent** |
| *Thamnophis elegans* (garter snake) | not knocked in | 69.11 | 3 | **absent** |
| *Pantherophis guttatus* (corn snake) | not knocked in | — | — | no ZRS detected |

Read the table in this order:

1. **The E1 column splits 6/5 exactly along limbed-vs-snake.** Nothing else in the table does.
2. **Identity to mouse does not split it.** Python (76.05%) and coelacanth (75.32%) are
   effectively equally diverged from mouse — the 0.7 pp gap is well inside the uncertainty of
   window choice and alignment — yet the coelacanth ZRS supported normal mouse limbs and the
   python ZRS truncated them. That is the whole point: this enhancer's function does not degrade
   smoothly with sequence distance.
3. **Total ETS1 motif count does not split it either.** Elephant shark has 5 and is a finned
   vertebrate; python has 5 and truncated. Rattlesnake has 7. Counting motifs is the obvious
   thing to do and it does not work; *which* motif is lost is what matters.

## 2. The 17 bp deletion, recovered independently

This was not copied from the paper — it fell out of the alignment, and only then did it match
what Kvon et al. describe. Alignment columns 1002–1019; mouse ZRS positions 959–973;
**mm10 chr5:29,315,455–29,315,469**.

```
                 <-- identical flank -->                      <-- identical flank -->
lizard         CACCTGGCCTACCTAATTAAT------TAA GCAAGGAAGTTACCTCA GAATTTTTCTACCATTTGCTTTTATTAT
python         CACCTGGCCTACCTAATTAAT------TAA ----------------- AAATTTCGCTACCATTTGCTTTTATTAT
eryx           CACATGGCGTACCTGATTAAT------TAA ----------------- AAATTTTGCTACCACTTGCTTTTATTAT
king_cobra     TACCTACCTGCATCTATTCAC------TAC ----------------- CAAAGTCTTCTTATATTACCTGTACTAT
mouse          CACCTGGTCAGTGCAACTAAT------TAA GAGAGGAAGTGACCT-- CAGATTTTGTGCATTTTACTTTTATTAT
```

Counted against **lizard** — which is the comparison Kvon et al. made, since they reintroduced
"a 17 bp sequence from the lizard ZRS ortholog" into the python ZRS — the gap is **exactly 17 bp**
(`GCAAGGAAGTTACCTCA`), independently in python, in *Eryx* and in king cobra. Counted against
mouse it is 15 bp, because mouse itself carries a 2 bp gap at the block's right edge. Both numbers
are in `zrs-analysis.json`; the 17 is not a coincidence and not a fit.

The flanks either side are near-identical between lizard and python, so this is a clean deletion,
not an alignment artefact.

**The ETS1 PWM scan over the block, per species** (JASPAR MA0098.3, p < 0.0032):

```
mouse           AGAGGAAGTG  score 10.1      eryx           no hit
human           AAAGGAAGTT  score  7.9      python         no hit
chicken         CAAGGAAGTT  score  4.3      king_cobra     no hit
lizard          CAAGGAAGTT  score  4.3      rattlesnake    no hit
coelacanth      CAAGGAAGTT  score  4.3      garter_snake   no hit
elephant_shark  CAAGGAAATC  score  3.8
```

6/6 limbed or finned vertebrates, 0/5 snakes.

### 2a. Exactly what `has_e1_ets_site` is, and what it is not

This matters for how the page words the claim, so it is stated precisely.

**It is the inferred JASPAR MA0098.3 scan — the same scan used everywhere else in this analysis.
It does NOT come from Kvon et al.'s coordinates.** I never had their coordinates: the E0–E4 site
positions are in the supplementary material I could not retrieve (§5). Concretely,
`has_e1_ets_site` is true for a species when an ETS1 PWM hit at p < 0.0032 overlaps alignment
columns 1002–1019.

Both halves of the claim are independently derived:

- **The block's position** was found by alignment — the longest run of columns gapped in snakes and
  present in non-snakes — *before* comparing to the paper. It matches Kvon et al.'s description
  (17 bp against lizard, highly conserved, overlapping an ETS site), which is corroboration, not
  the source.
- **The ETS1 call inside it** is a PWM sequence match. It is not a measurement of binding, and no
  site here is asserted to be "the" E1 of that paper. Every motif in `ets_sites` carries
  `inferred: true`, and so does `e1_deletion`.

**The split, with the missing datum named.** 6 True / 5 False / **1 null**, over 12 rows:

| | n | species |
|---|---|---|
| `true` | 6 | mouse, human, chicken, green anole, coelacanth, elephant shark — i.e. all limbed/finned |
| `false` | 5 | dwarf sand boa, Burmese python, king cobra, tiger rattlesnake, garter snake — all snakes |
| `null` | 1 | **corn snake — no ZRS detected at all, so there is nothing to score** (§7) |

So it is a clean 6-vs-5 split **among species with data**, and the page should not call it 11/11 or
12/12: the corn snake is a twelfth species that drops out of this column entirely. (Arguably it is
the strongest case of enhancer loss in the set, but it cannot be scored on this feature.)

**One row needs a caveat if the page names species individually.** For four of the five snakes the
`false` is doubly supported — the 17 bp is deleted *and* no ETS1 motif scores. For
**tiger rattlesnake** only the motif evidence applies: MAFFT puts unrelated sequence in those
columns rather than a gap (`absent_in: 0`), so the deletion is *not assessable* there (§6). Its
`false` rests on the PWM scan alone.

## 3. What I actually fetched

Every sequence was fetched directly from NCBI; accession, exact URL, coordinates, HTTP status,
byte count, sha256 and UTC timestamp for each are in `zrs-analysis.json` → `retrievals`. The mouse
sha256 was independently re-fetched and re-hashed at write-up time and matches
(`0983f9cb9bce7543…`).

**Mouse reference** — the exact 1,324 bp Kvon et al. deleted, mm10 chr5:29,314,497–29,315,820
(their Figure S3), from GRCm38.p6:

```
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NC_000071.6\
&rettype=fasta&retmode=text&seq_start=29314497&seq_stop=29315820
```

*Positive control that this is the right interval, not just the right size:* the returned sequence
is exactly 1,324 bp **and** contains the paper's stated sgRNA recognition sequence
`AGTACCATGCGTGTGTGTGA` on the minus strand at offset 16 — i.e. "in close proximity to its
5′ border", exactly as the paper describes. A 1-nt-mutated copy of that motif is absent
(`-1`). Two independent facts had to line up and did.

**Human** — fetched from GRCh38.p14 chr7 (NC_000007.14:156,788,000–156,795,000) and pinned by
exact match to the dedicated RefSeq record **NG_042169.2** *"Homo sapiens ZPA regulatory sequence
(ZRS) on chromosome 7"*, which sits at **NC_000007.14:156,790,608–156,793,179**. Control: a
1-nt-mutated copy of NG_042169.2 does not match the window (`-1`).

**King cobra** — `AZIM01000183.1`, scaffold183.1 of assembly **AZIM01**, which is the same king
cobra assembly Kvon et al. used ("king cobra (version AZIM01, NCBI)").

**Dwarf sand boa** — `MW653933.1`, a dedicated GenBank record,
*"Eryx miliaris ZPA regulatory sequence ZRS genomic sequence"*, 956 bp.

**Others** (chicken, green anole, coelacanth, elephant shark, Burmese python, tiger rattlesnake,
garter snake, corn snake) — the ZRS lies in LMBR1 intron 5, so for each I fetched the annotated
LMBR1 locus ±10 kb via NCBI Gene → efetch, then located the ZRS inside it (method in §4).

## 4. Method, and why each step is there

**Localisation.** Unique 12-mers of the mouse ZRS were used to find the orthologous window inside
each 50–215 kb locus, then a local affine-gap alignment (Biopython `PairwiseAligner`) placed it.
*Controls:* against the human chr7 window the procedure lands 370 bp into NG_042169.2 with 253
seeds and 84.6% identity — consistent with the independent BLAST HSP, which starts at position 384
of the same record. A **shuffled** mouse ZRS against the same window gives 0 seeds and does not
localise. So the method both finds what is there and declines to find what is not.

**Bridging anchor.** Some snakes have diverged so far from mouse that only a short block aligns
(king cobra: 197 bp with a mouse query). For those, the *python* ZRS — itself mouse-anchored — was
used as the anchor, which recovers much more (king cobra: 549 bp). The anchor used is recorded per
species in `retrievals`. Anchoring only chooses the window; every identity number is recomputed
against mouse afterwards in the multiple alignment.

**Alignment.** MAFFT v7.525 L-INS-i (`--localpair --maxiterate 1000 --nuc`) — the same program and
mode Kvon et al. used. Installed via conda for this analysis.

**Core trimming, and a mistake worth recording.** My first alignment ran over the full 1.3 kb
windows and appeared to show several "deletions shared by all snakes". *They were artefacts.* The
fetched windows extend well beyond the conserved enhancer, and in those flanks the sequences are
not homologous at nucleotide resolution — MAFFT fills them with arbitrary gaps. I caught this by
looking at the supposedly aligned non-snake blocks and seeing that they share no similarity with
each other (mouse `TGAGTTCCTGCATGCATTCCAGATGTGCAA` vs chicken `CAGTACTGGGAATGGAATCCACATCCCAAG`
vs coelacanth `CAAGGTTATGATTGCTGGCTCTATACTTAA`). Had I reported those, I would have reported
nonsense that superficially resembled the paper's result.

So, as the paper did with Gblocks, the alignment was trimmed to its alignable core and realigned
from scratch. Mouse positions were scored by column depth and conservation, smoothed over 31
positions, and the longest run with conservation ≥ 0.70 and depth ≥ 0.80 kept (short dips of
≤ 30 positions do not end a block). **Core = mouse ZRS 398–1043, 646 bp, mm10
chr5:29,314,894–29,315,539.** The thresholds were set by reading the shoulder in the conservation
profile, not by tuning until the 17 bp block appeared — and note the trimming is what *removed*
the false deletions, not what produced the real one. The core's extent independently matches the
paper's "functionally critical ~800 bp core" and the BLAST HSP extent (query 395–1173).

**Motifs.** Both strands of each species' core scanned with JASPAR **MA0098.3** (ETS1, human;
consensus `ACCGGAAGTG`), threshold set so that p < 0.0032 — the threshold Kvon et al. state for
their FIMO scan — by exact convolution of the score distribution under a uniform background,
giving 1.120 bits. *Controls:* the consensus scores 15.94 bits and passes; poly-G (−21.63),
poly-C (−38.79) and poly-A (−22.81) all fail; the distribution sums to 1.000000.

**Human disease variants.** All 694 ClinVar LMBR1 records were fetched and filtered by GRCh38
coordinate to the human ZRS interval: **93 variants inside it, of which 17 are pathogenic or
likely pathogenic**, clustering tightly in NG_042169.2 offsets 526–1164 — i.e. the variants
independently mark out the enhancer. 13 of the 17 fall inside the trimmed core and are mapped to
alignment columns in `zrs-analysis.json` → `clinvar_pathogenic_in_zrs`. Several are the classic
preaxial-polydactyly alleles (VCV000004897–4906). No variant position was taken from prose.

## 5. What failed, and what I could not get

- **The authors' actual sequences are not available.** Kvon et al. deposited **no GenBank
  accessions** for the ZRS orthologs — the brief's assumption of "KX…" accessions is wrong. The
  sequences live in supplementary Tables S2 (reporter constructs) and S3 (knock-in constructs) and
  the constructs were "chemically synthetized by IDT". I tried three routes and all failed:
  - PMC supplementary PDFs (`NIHMS818450-supplement-2.pdf` … `-6.pdf`) → **reCAPTCHA challenge
    page**, not the PDF.
  - `r.jina.ai` fallback on the same URL → same CAPTCHA page.
  - EuropePMC `/PMC5484524/supplementaryFiles` → `"Article with id PMC5484524 is not open access
    one"`.

  **Consequence: the sequences analysed here are NOT the sequences that were knocked into mice.**
  They are re-derived from reference genomes and may differ by assembly error, strain/individual
  polymorphism and window boundaries. Read level for those tables: **could-not-access**.
- **Species substitutions were forced and they change what the comparison means.** The paper used
  *boa constrictor* (Assemblathon 2 assembly, not in NCBI — NCBI's only boa assembly,
  GCA_046270485.1, is a different and newer one) and speckled rattlesnake *Crotalus mitchellii*
  (JPMF01). I used *Eryx miliaris* (a different basal snake) and *Crotalus tigris*. *Thamnophis
  elegans* is mine, not in the paper. **Viper (JTGP01) was not analysed at all.**
- **BLAST cross-checks did not finish.** WGS BLAST searches for king cobra/boa (RID EF6SW5BE016)
  and coelacanth/anole/elephant shark (RID EF6EY9MY016) were still `Status=WAITING` at write-up;
  a Serpentes-wide search returned an estimated queue time of 18,259 s and was abandoned. The
  human/chicken search against `core_nt` (RID EF69R29F014) **did** complete and corroborates the
  human placement. Nothing in the result depends on the unfinished searches — they would have been
  a second opinion on windows I obtained by annotation instead.
- **The Kvon 2020 PMID in the brief is wrong.** 32169217 is *"Liquid-Liquid Phase Transition
  Drives Intra-chloroplast Cargo Sorting"*, Cell 180(6):1144–1159. The saturating ZRS mutagenesis
  paper is **PMID 32169219**, PMC7179509, doi 10.1016/j.cell.2020.02.031, Cell 180(6):1262–1271.e15
  — the journal/volume/pages in the brief were right. Read level: **abstract** (I did not read its
  full text; nothing here depends on it).
- **ETS site numbering E0–E4 is not reproduced.** Those coordinates are in the inaccessible
  supplementary material, so **no site here is claimed to be "the" E1**. Every motif call in the
  JSON carries `inferred: true`. The 17 bp block is the one case where my independently-located
  feature and the paper's description coincide closely enough to name together, and I say so
  rather than asserting identity.

## 6. Where my numbers disagree with the paper

Stated plainly rather than smoothed over.

- **Mouse–human identity.** Paper: 73%. Mine: **88.34%** over the trimmed core, **78.6%** over the
  full 1.3 kb window, **85–86%** over the best-aligning block alone. The paper does not define its
  metric, so these are not comparable and I am not claiming either is wrong — but it does mean
  **no single "% identity" here should be quoted against theirs.**
- **Coelacanth comparison — I do not reproduce the direction.** The paper says the coelacanth ZRS
  "shares less sequence similarity with the human ortholog than with the python ortholog (57% vs
  59%)". In my core alignment it is the other way round: human–coelacanth **80.47%**,
  python–coelacanth **79.71%**. The margin is 0.76 pp, which is smaller than the shift I get from
  moving the core boundaries, so I read this as "not resolved by my method" rather than as a
  contradiction. My absolute values differ from theirs by >20 pp anyway, for the metric reason
  above.
- **Rattlesnake at the 17 bp site is not assessable.** MAFFT places unrelated sequence
  (`CCACAGCAATAGCAC`) in those columns rather than a gap, so rattlesnake is reported as
  **not assessable there**, not as retaining the site. Its ETS1 scan returns no hit in that block,
  which is consistent with loss, but the deletion claim is not made for it.

## 7. The corn snake negative, with its scope

**No ZRS was detected in corn snake (*Pantherophis guttatus*)**, which matches the paper ("The only
snake genome in which no ZRS sequence was detected belonged to the corn snake").

Scope of that negative, stated so it can be checked: the whole annotated LMBR1 locus
**NC_142066.1:148,621,531–148,710,531 (89,001 bp, gene span ±10 kb)** was searched with unique
12-mer seeding plus local affine-gap alignment, using **both** the mouse ZRS and the Burmese python
ZRS as queries. Longest aligned block: **24 bp** with the mouse query, **120 bp** with the python
query. The threshold for claiming a ZRS is 150 bp.

*Positive control for that search, in the same run:* the identical procedure with the python query
recovers **1,047 bp** in tiger rattlesnake, **318 bp** in garter snake and **1,322 bp at 100%** in
python itself. So the search works on the same loci and the same query; corn snake is the one that
comes back empty. It does **not** exclude a remnant elsewhere in the corn snake genome, nor one too
diverged for these queries.

This also exposed a methodological trap worth stating: **mouse-anchored alignable extent conflates
divergence with absence.** With a mouse query the rattlesnake looks nearly as degraded as the corn
snake (347 bp vs 24 bp); with a snake query they separate decisively (1,047 bp vs 120 bp).

## 8. Limitations (the full list is in `zrs-analysis.json` → `limitations`)

The ones that matter most:

1. **Correlational, post-hoc, n=4 knock-ins.** Nothing computed here establishes causation. The
   causal evidence is Kvon et al.'s mouse genetics, not this alignment. With this design the E1
   split could not fail to look impressive, and a 6-vs-5 split on one feature chosen after seeing
   the data is weak evidence by itself.
2. **These are not the authors' constructs** (§5).
3. **Percent identity is metric-dependent** and ranges 65→88% for the same pair depending on
   window (§6).
4. **A PWM hit is a sequence match, not binding.** No ChIP, EMSA or reporter data here, and FIMO
   itself was not run — an equivalent threshold was recomputed.
5. **Alignment of sequences this diverged is itself uncertain**, and the snake columns are exactly
   where that uncertainty is largest.
6. **Model fidelity ≠ biological validity.** Reproducing Kvon et al.'s observations shows these
   sequence relationships are real; it does not validate any particular story about limb loss.

## 9. Files and how to re-run

| file | what |
|---|---|
| `zrs-analysis.json` | everything: method, retrievals with sha256, identity matrix, per-column conservation, ETS sites, E1 block, ClinVar mapping, limitations, sources |
| `zrs-conservation.png` / `.svg` | the figure (1400×700) |
| `alignment.fasta` | the **core** alignment actually analysed (11 species, 1,121 columns) |
| `alignment.full-window.fasta` | the untrimmed 1.3 kb alignment, kept so the trimming can be checked |
| `seqs/final_set.json` | per-species sequences + provenance |
| `seqs/input.fasta`, `seqs/core_input.fasta` | MAFFT inputs |

Scripts, in order: `eutils.py` (polite E-utilities client) → `fetch_orthologs.py` →
`build_set.py` → MAFFT → `core_trim.py` → `final_analysis.py` → `make_figure.py`.
`locate_zrs.py` runs its own positive/negative controls when executed directly;
`zrs_lib.py` holds the aligner and the PWM/p-value machinery.

MAFFT command used:

```
mafft --localpair --maxiterate 1000 --nuc --quiet --thread 2 seqs/core_input.fasta
```

(run under `systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 -p TasksMax=64`).

## 10. Sources and read levels

- **Kvon EZ, Kamneva OK, Melo US, et al.** Progressive Loss of Function in a Limb Enhancer during
  Snake Evolution. *Cell* 2016;167(3):633–642.e11. PMID 27768887, PMC5484524,
  doi [10.1016/j.cell.2016.09.028](https://doi.org/10.1016/j.cell.2016.09.028).
  **read level: full-text** (main text + STAR Methods + supplementary figure legends, via the
  PubMed Central full-text tool). **Supplementary Tables S1–S6: could-not-access.**
- **Kvon EZ, Zhu Y, Kelman G, et al.** Comprehensive In Vivo Interrogation Reveals Phenotypic
  Impact of Human Enhancer Variants. *Cell* 2020;180(6):1262–1271.e15. PMID 32169219, PMC7179509,
  doi [10.1016/j.cell.2020.02.031](https://doi.org/10.1016/j.cell.2020.02.031).
  **read level: abstract.**
- **NCBI Nucleotide / E-utilities** — every sequence listed in `retrievals`. **full-text**
  (i.e. the records themselves were retrieved, with URLs and checksums recorded).
- **NCBI ClinVar**, LMBR1 query, 694 records, fetched 2026-11-01. **full-text.** Classifications
  are ClinVar's germline classifications on that date and are revised over time.
- **JASPAR 2024**, matrix MA0098.3 (ETS1). **full-text.**
- **MAFFT v7.525** (Katoh & Standley). **listing** — software used, not a source read for claims.

Article metadata and full text in this analysis were retrieved from **PubMed / PubMed Central**.
