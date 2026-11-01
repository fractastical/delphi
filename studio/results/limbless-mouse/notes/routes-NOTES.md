# NOTES — cross-scale design-route map for "how would you make a limbless mouse?"

Written 2026-11-01, Seattle (PDT). Companion to `routes.json` in this directory.

`routes.json` holds **39 routes** across the page's **8 declared scales**, **68 sources**, all
PubMed-verified. This file records how they were found, what I could not check, and where I
think the existing dossier page (`docs/dossier/12-limbless-mouse.md`, 322 lines, fetched
HTTP 200 from `raw.githubusercontent.com/kganjam/delphi-frontier/main`) is **wrong or
overstated**.

**Scale keys and counts**, in the page's declared order — every pin on the schematic is live:

| key | routes |
|---|---|
| `molecular` | 7 |
| `gene` | 12 |
| `cell` | 4 |
| `tissue` | 1 |
| `pattern` | 2 |
| `timing` | 4 |
| `organism` | 4 |
| `invitro` | 5 |

`tissue` and `pattern` are deliberately split, per the two models the page runs: `tissue` holds
only the SHH–GREM1–FGF **maintenance loop** (an ODE; sets limb size and when outgrowth stops),
and `pattern` holds the BMP–SOX9–WNT **reaction–diffusion** rows (sets digit number and
spacing). `tissue` having a single route is not a gap — it is one circuit, and padding it would
mean putting pattern-formation rows where the ODE pin is.

**Study ids.** Each route carries a machine-readable `study` field (`zrs-conservation`,
`shh-grem1-fgf-loop`, `digit-turing`, or `null`) and names it in `what_we_would_run`. **12 of 39
routes have one** — 6 `zrs-conservation`, 4 `shh-grem1-fgf-loop`, 2 `digit-turing`; the other
**27 say so explicitly** rather than reaching for the nearest study. Two of the twelve are
qualified rather than clean: `mol-zrs-designed-hypomorph` is linked only on its
gain-of-function half (§3.1 below), and `org-cetacean-hindlimb` only because dolphin is one of
the 16 species in the ZRS reporter panel — no cetacean ZRS was taken to knock-in, so there is
no phenotype rung for it.

**Build integrity.** `build.py` assembles the file from `parts/`, derives `sources` from the
routes' own evidence entries (so a PMID cannot appear in the source list without a route using
it, and read-levels cannot drift between the two), and refuses on: a scale key not on the
page's list, any declared scale with zero routes, an unknown study id, a study set but not
named in the prose, a recommendation pointing at a missing route, a missing required field, a
bad `evidence_strength`, a bad read-level, duplicate ids, or a judge-gene `key_pmid` absent
from `sources`. Each of those refusals was tested against a case it must flag **and** an
unmutated control that must pass; all six trials behaved correctly.

---

## 1. Method

**Tooling.** PubMed only, via the `pubmed` MCP tools (`search_articles`,
`get_article_metadata`, `get_full_text_article`, `lookup_article_by_citation`). No web
search, no Consensus, no bioRxiv.

**Verification rule I applied.** A PMID appears in `routes.json` only if a PubMed record
for it was returned to me *in this session*. That includes the 17 PMIDs inherited from
the existing dossier page — I re-fetched every one rather than copying them, because a
PMID quoted from a summary is a claim about an article, not a reading of one. The build
script cross-checks this: 68 cited PMIDs, 0 unverified.

**Read levels, honestly.**

| level | count | what it means |
|---|---|---|
| `full-text` | 1 | Kvon et al. 2016, retrieved from PMC5484524 and read, including Figures S1–S5 legends and STAR Methods |
| `abstract` | 65 | PubMed record and abstract retrieved; body not read |
| `listing` | 2 | record resolves, **PubMed holds no abstract** — Summerbell 1974 (PMID 4463222) and Garavelli 2010 (PMID 21271649) |

The two `listing` sources matter and I have flagged them inside the routes. For Summerbell
I state only what the record itself shows (title + MeSH: Ectoderm, Extremities, Gestational
Age, Humerus, Radius, Ulna) and make **no quantitative claim** about the excision series.
The classical premise is restated independently by Lewandoski 2000, which I did read at
abstract level.

**A tooling gotcha worth recording.** PubMed's query parser ANDs every term, so long
natural-language queries return zero. `limb bud organoid pluripotent stem cell derived limb`
→ **0 results**; `limb bud organoid` → **27**. Several of my first-pass searches returned
zero for this reason and not because the literature is empty. Anyone repeating this should
use 2–4 content words. Also: `lookup_article_by_citation` returns the PMID in the **`key`**
field and the caller's key in **`pmid`** — the fields are swapped. I caught this because
the "pmid" values came back as my own labels (`sheth2012`), and I re-verified all six
through `get_article_metadata` before using them.

**Scope of negative searches** (these are absences in *my* search, not in the literature):

1. **No molecular mechanism for *Lerista* limb reduction.** `Lerista limb reduction skink
   evolution` → 4 records, all taxonomic, morphometric or macroevolutionary. The most-cited
   case of repeated limb loss in squamates has, as far as this search goes, no published
   sequence- or expression-level mechanism. I used *Hemiergis* (SHH duration, Shapiro 2003)
   and *Brachymeles* (clade-specific digit loss, Wagner 2018) instead and said so.
2. **No genetic AER ablation with diphtheria toxin.** `diphtheria toxin ablation apical
   ectodermal ridge genetic mouse` → 4 records, none an AER ablation. That route is marked
   `proposed` and cites the roof-plate (Lee 2000) and lens-placode (Zhang 2008) ablations
   only as *method* precedent.
3. **No auxin-inducible degron study in mouse embryos.** Searched; zero. The degron route
   cites dTAG/FKBP12-F36V work instead (Abuhashem 2022, Antczak 2026), which is validated
   in mouse embryos from zygote to mid-gestation.
4. **No limb field reported in gastruloids or trunk-like structures.** Searched PubMed only,
   which is the wrong place to look first for a 2026 result — this would appear on bioRxiv.
   I listed the gap rather than implying the capability exists.
5. **No published `Prx1-CreER;Fgf10-flox` limb series.** This is my own recommended route,
   and it is labelled `proposed` for exactly this reason.
6. **No recombinant-limb experiment using mesenchyme from a defined limb-loss genotype.**
7. **No long-term (adult, >2 week) husbandry or behavioural data for ZRS-null mice.**

---

## 2. What I added that the dossier does not have

Beyond re-organising by scale, four things are genuinely new and I think two of them are
important:

- **RSPO2 / RNF43 / ZNRF3 (PMID 29769720, Nature 2018).** An **allelic series** of recessive
  human *RSPO2* mutations causing tetra-amelia syndrome with lung aplasia and "a total absence
  of the four limbs", with severity correlated to measured binding defects — and the
  reciprocal, deleting *rnf43* and *znrf3* in *Xenopus*, "sufficient to trigger the outgrowth
  of **supernumerary** limbs". The authors call it "a master switch that governs limb
  specification". **This is absent from the dossier and it is arguably a stronger "gene for
  limblessness" candidate than WNT3** — more families, graded alleles, per-allele biochemistry,
  and a bidirectional mechanism. If the judge's work is recent human genetics, this is the
  one the dossier would have missed.
- **p63 (PMIDs 10227293, 10227294).** Mice lacking p63 are **born alive** with limbs "absent or
  truncated", from failure of the AER to **differentiate and be maintained**. That is a third
  mechanism class the dossier does not draw: not induction failure (Fgf10, Wnt3), not
  signalling-centre output failure (ZRS, Fgf4/8), but failure of the signalling centre's
  epithelium itself.
- **Budoids (PMIDs 41313763, 42729099).** mESC-derived 3-D organoids containing AER-like,
  surface-ectoderm and limb-mesoderm cells, with chondrogenesis-mediated symmetry breaking,
  >1,000 per differentiation, with a step-by-step protocol published 2026. This is the route a
  modern reviewer asks about first and the dossier has no in-vitro section at all.
- **Fgfr2b (PMID 10631169)** adds a fourth phenotypic class — structures that *initiate and then
  apoptose* — distinct from both amelia and truncation.

---

## 3. Where I think the existing dossier is wrong or overstated

Listed strongest first. Three of these are in the dossier's §4b "what we could do this week",
which is the section a judge is most likely to probe.

### 3.1 The Kvon 2020 benchmark points the wrong way (material)

Dossier §4b item 2 calls scoring the ~1,000-variant ZRS panel **"the single most informative
thing we could run"**, placed directly after item 1, which is the snake-ortholog
**loss-of-function** series. Read as a pair, that implies one benchmark for one question.

It is not. Kvon et al. 2020's own abstract describes an enhancer **"repeatedly linked to
polydactyly"**, and the knock-in confirmations were of variants that **"cause polydactyly in
knockin mice"** — i.e. *gain* of ectopic anterior activity, **extra digits**. The snake series
is *loss*. Scoring the 2020 panel tests whether a model has grip on this element at all; it is
**not** evidence that the model can rank limb-*reduction* alleles, and nothing I read establishes
that the two directions transfer.

**Fix:** keep the benchmark, relabel it as the gain-of-function direction, and say in the same
sentence that transfer to the loss direction is untested. I have done this in
`mol-zrs-designed-hypomorph`.

### 3.2 "Five of them were additionally taken to knock-in mice" is wrong (small, but checkable)

Dossier §4b item 1. The full text describes **four ortholog knock-ins** — human, coelacanth,
python, king cobra — plus **one synthetic allele**, the "resurrected python" (python ZRS + 17 bp
lizard sequence). That is four orthologs and five alleles. A reader counting orthologs in the
paper will not find five.

### 3.3 The "ordered series" silently mixes two assays (material for a model benchmark)

Dossier §3 gives: *mouse ≈ human ≈ coelacanth (normal) > boa (ZPA activity retained) > python
(weak residual Shh, 2–3 rudimentary digits) > cobra (no activity, full truncation)*, and calls it
"a measured cis-regulatory dose–response" and "a labelled dataset".

**Boa was never knocked in.** Boa's ZPA activity is a *transgenic reporter* result; python and
cobra are *knock-in skeletal phenotypes*. Four of the five rungs are one assay and one rung is a
different assay. If this series is going to be used as the labelled set a model is scored
against, the label type has to be uniform or the mixing has to be stated — otherwise a
rank-correlation number is computed over two incommensurable measurements.

### 3.4 The "six amelia" count does not survive reading the abstracts (material)

Dossier §2 asserts: *"**Six describe failure of a limb bud to form at all**, as opposed to
truncation of a bud that formed: `Fgf10` (Min 1998 and Sekine 1999), `WNT3` Q83X, Meis1/2-LPM,
`Tbx5` null (forelimb buds do not form) and `Tbx4` null (hindlimb buds fail to develop)."*

Two of the six contradict their own sources:

- **Tbx4 null.** Naiche & Papaioannou 2003: *"Induction of a hindlimb field occurs normally in
  Tbx4 mutants and **initial patterning of the hindlimb bud appears normal**. However, hindlimb
  buds from Tbx4 mutants fail to develop."* A bud that forms and then fails is not "failure of a
  limb bud to form at all". The dossier's own parenthetical ("hindlimb buds fail to develop")
  says this, and is then counted on the other side of the distinction it was drawn to support.
- **Fgf10.** The two founding papers **disagree**. Min 1998: *"Limb bud initiation was
  **abolished**."* Sekine 1999: *"limb bud formation **was initiated** but outgrowth of the limb
  buds did not occur."* The dossier cites both as amelia and does not flag the disagreement.
  Under the repo's own §1 rule 8 (preserve disagreement), that should be surfaced, not
  reconciled — and it decides whether the lesion is in induction or in maintenance, which is the
  whole axis of §2d distinction 1.

**Fix:** the count is defensible only for WNT3, Meis1/2-LPM and Tbx5 (whose source explicitly
says the limb field is intact but *no bud forms*). I have not reproduced the count.

### 3.5 "A *viable* limbless mouse ... the cis-regulatory route is the one that delivers it" overstates (material, and the judge will notice)

Dossier §2d point 2. I re-read the full text specifically to check this, and the **viability half
is right**: Figure S3E, *"Gross phenotypes of two week old ZRS(+/+) (top) and ZRS(−/−) (bottom)
mice. The body sizes are comparable, but ZRS(−/−) mice have truncated limbs."* Good — that claim
holds and I confirmed it independently.

But the sentence says **"a *viable* limbless mouse"**, and the dossier's own §1 correction says
ZRS mutants are **truncations, not amelia**. The ZRS route delivers a viable **limb-reduced**
mouse with a retained stylopod and girdle. **Nobody in this literature has published a viable
limbless mouse**, and the page should say so in that sentence rather than two sections earlier.

### 3.6 The Shh/Gli3 epistasis is missing, and it inverts the mechanism

Not an error, an omission with consequences. te Welscher 2002 (PMID 12215652): disrupting one or
both *Gli3* alleles in a *Shh*-null background **progressively restores** distal limb development
and digit formation — "SHH signaling counteracts GLI3-mediated repression". So the ZRS-null
truncation is a failure to **relieve repression**, not a failure to deliver a positive signal.

Any threshold law of the form "enhancer activity → distal element count" that treats SHH as an
instructive morphogen has **the sign of the mechanism wrong even when it fits the data**. That
matters directly for dossier §4b item 4 (the proposed Lean dose law), which is written as a
monotone map from activity to element count with no mention of the repressor it is actually
acting through. The law can still be stated — it is a law about a model — but the page should not
imply the model's variable corresponds to the biology's.

### 3.7 Smaller things

- §2a's Chan 2010 row says *"`Pitx1` null is lethal, the enhancer deletion is not"*. The source
  says *"Pitx1 null mutations are lethal in **laboratory animals**"* — which in the mouse is
  specifically contradicted a row later by the dossier's own §2b Lanctôt entry, where the Pitx1
  null is a **surviving** hindlimb-hypoplasia mutant. Both statements are faithful to their
  sources; together on one page they read as a contradiction and need a clause distinguishing
  which laboratory animal.
- §2c's cetacean row quotes Sun 2022 but omits **Thewissen 2006** (PMID 16717186), which is the
  developmental result: the dolphin hindlimb bud *forms an AER*, expresses *Fgf8* initially,
  fails to maintain either, has no *Shh*, and lacks *Hand2*. That is the mechanistically
  informative cetacean paper and it is the one that makes "maintenance failure" a distinct class.
- §7's negative-search note covers only a `Prrx1` snake-enhancer query. Six further negatives are
  listed in §1 above; a page that states one negative's scope and not the others invites the
  reading that the others were exhaustive.

---

## 4. What I could not verify

- **Any claim resting on an article body except Kvon 2016.** 65 of 68 sources are abstract-level.
  Where an author flags their own inference — Thewissen on the HAND2 association, the 41 Ma /
  34 Ma dates, Sun 2022 on cetacean ZRS activity — I attributed it to them rather than restating
  it as measurement.
- **Summerbell's numbers.** No abstract in PubMed, so the quantitative stage→truncation relation
  that the whole timing argument would ideally be calibrated on is not available to me. I did not
  invent a substitute.
- **Mouse *Rspo2* limb phenotype.** The human and *Xenopus* results are in the abstract; the mouse
  limb phenotype is not, and I did not state one.
- **Hand2 conditional limb skeletal phenotype.** Not retrieved; not stated.
- **Viability of any of the conditional crosses I recommend.** Including my own top
  recommendation. It is marked `proposed`.
- **Whether budoids form a true stratified AER or AER-*like* cells by marker.** The abstract says
  "AER properties". The distinction decides what a p63 experiment in budoids would mean.

---

## 5. One thing I'd push back on in the framing

The brief asked for "the many different ways one could get to a limbless mouse". After reading
39 of them, the honest headline is **narrower and more interesting than that**: at every scale,
*amelia* and *viability* pull against each other, and for a structural reason. The genes that
**start** a limb (Fgf10, Fgfr2b, Wnt3, RSPO2, Meis1/2, Grem1) also start lungs, kidneys,
pituitary, thyroid or the whole WNT system, so abolishing the bud reliably costs the animal.
The only two escapes are **tissue restriction** (Prx1-Cre) and **cis-regulation** (ZRS, the
stickleback *Pitx1* enhancer) — and cis-regulation, the route evolution independently found
*twice*, buys viability at the price of delivering **truncation rather than absence**.

That trade-off is the page's thesis, and it is better than "there is a design space", because it
is falsifiable and because it predicts where to look: the one combination nobody in this
literature has published is **tissue-restricted + stage-selected abolition of bud initiation**,
which is exactly `timing-prx1-creer-fgf10`.
