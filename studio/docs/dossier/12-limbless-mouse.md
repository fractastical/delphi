# 12. "Could you create a limbless mouse?" — what the literature already says, and what we would add

Written 2026-11-01, Seattle (PST), in answer to a question a hackathon judge put to the team.
The judge said he had worked on this problem and had identified a gene for it.

Every factual claim below carries a PMID or a DOI and a **read-level**: `full-text` (the
article body was retrieved and read), `abstract` (the PubMed record and abstract were
retrieved; the body was not), `listing`, `search-summary`, `could-not-access`. Bibliographic
records were retrieved from **PubMed** (NCBI) on 2026-11-01; the DOI of every cited article is
given in [§7](#7-sources-with-read-levels). One source (DART-Eval) was reached through a
Consensus search and the arXiv landing page.

No claim on this page is a result of ours. Section 4 is the only part that describes our own
system, and it is explicit about what has been run and what has not.

---

## 0. Corrections to this page, and where the work continued

This page was written first and then checked against the sources again while building the
**design space** that supersedes it: **[13-limbless-mouse-design-space.md](13-limbless-mouse-design-space.md)**,
live at <https://studio.morphoswarm.ai/#/studio/limbless-mouse> with 39 sourced routes across
eight scales and three computed studies. That re-check found seven problems here. They are
listed rather than edited away, because a reader who has already read this page needs to know
what changed.

1. **§4b item 2 points the wrong way.** Scoring the ~1,000-variant ZRS panel (Kvon et al. 2020)
   is called "the single most informative thing we could run", directly after the snake
   loss-of-function series. That panel assayed an enhancer *"repeatedly linked to polydactyly"*
   and its knock-in confirmations were of variants that **cause polydactyly** — the *gain*
   direction. The snake series is *loss*. The benchmark is still worth running; it tests whether
   a model has grip on this element at all. It is not evidence that a model can rank
   limb-*reduction* alleles, and nothing we read establishes that the two directions transfer.
2. **§4b item 1 says "five of them were additionally taken to knock-in mice".** The full text
   describes **four ortholog knock-ins** — human, coelacanth, python, king cobra — plus one
   synthetic allele, the "resurrected python". Four orthologs, five alleles.
3. **The §3 "ordered series" mixes two assays.** Boa was never knocked in: its retained ZPA
   activity is a transgenic *reporter* result, while python and cobra are knock-in *skeletal
   phenotypes*. Used as a labelled set for a rank correlation, four rungs would be one
   measurement and one rung another.
4. **The §2 "six amelia" count fails on two of six.** Naiche & Papaioannou state that in *Tbx4*
   mutants a hindlimb field is induced normally and *"initial patterning of the hindlimb bud
   appears normal"* before the bud fails — which is not failure of a bud to form. And the two
   founding *Fgf10* papers **disagree**: Min et al. 1998 say limb-bud initiation was abolished,
   Sekine et al. 1999 that bud formation was initiated but outgrowth did not occur. This page
   cites both as amelia without flagging the disagreement, which the repository's own rules say
   to preserve rather than reconcile — and it is the disagreement that decides whether the
   lesion is in induction or in maintenance.
5. **§2d calls the ZRS route "a viable limbless mouse".** The viability half checks out and was
   re-read in the full text: Figure S3E shows two-week-old ZRS−/− mice of comparable body size
   with truncated limbs. But this page's own §1 correction says ZRS mutants are truncations, not
   amelia. The route delivers a viable **limb-reduced** mouse with a retained stylopod and
   girdle. **Nobody in this literature has published a viable limbless mouse.**
6. **The *Shh*/*Gli3* epistasis is missing, and it inverts the mechanism.** SHH acts by relieving
   GLI3 repression, so removing *Gli3* from a *Shh*-null background progressively restores distal
   limb development (te Welscher et al. 2002, PMID 12215652). A proposed Lean law mapping SHH
   activity monotonically to element count has the sign of the mechanism wrong.
7. Smaller: two rows here contradict each other on *Pitx1* lethality; Thewissen et al. 2006 is
   missing from the cetacean row; and only one negative search states its scope.

---

## 1. Short answer

**Yes — limbless and near-limbless mice already exist, by at least four mechanistically
independent routes, and have since 1998.** The question that is still open is not *can it be
done* but *can the phenotype be predicted from sequence before the mouse is made*. That second
question is where we think we have something to contribute, and it is a much narrower claim.

We want to be precise about one thing first, because it bears directly on the judge's own work.
"A gene for limblessness" and "an enhancer for limblessness" are different answers to the same
question, and the field has both:

- **The coding route.** Knock out a gene whose product is required to start or sustain the limb
  bud, and the limb never forms. `Fgf10`-null mice are born with **no forelimbs and no
  hindlimbs at all** and survive to birth (Min et al. 1998, PMID 9784490; Sekine et al. 1999,
  PMID 9916808; both `abstract`). In humans the equivalent is tetra-amelia from a homozygous
  nonsense mutation in `WNT3` (Niemann et al. 2004, PMID 14872406, `abstract`).
- **The cis-regulatory route.** Leave every protein intact and change only a regulatory element.
  Kvon et al. replaced the mouse **ZRS** — the limb enhancer of *Shh*, ~1 Mb from its promoter —
  with the orthologous sequence from king cobra, and got complete loss of limb *Shh* expression
  and a severely truncated limb phenotype in **both fore- and hindlimbs**, indistinguishable
  from deleting the enhancer outright (Kvon et al. 2016, Cell, PMID 27768887, `full-text`).

If the judge's gene is **ZRS / *Shh* / `Lmbr1`**, Kvon et al. 2016 is almost certainly the paper
in play, and it is the strongest precedent in the field for "a regulatory change, not a
knockout, removing limbs from a mouse". We treat it that way throughout.

**One correction we would offer respectfully, because it matters for how the result is quoted:**
the ZRS knock-ins are **truncations, not amelia**. The ZRS-null mouse retains a proximal
skeleton — in the Kvon et al. CRISPR deletion line the humerus, radius and ulna appear fused
and no recognisable autopod is present; the hindlimb zeugopod is severely reduced and the
autopod is a single rudimentary digit (Kvon et al. 2016, Figure S3E–F, `full-text`). A mouse
with **no limb buds at all** is the `Fgf10`-null, not the ZRS mutant. If the judge's phenotype
was complete amelia, the mechanism is upstream of *Shh*.

---

## 2. The routes, with phenotypes

Rows are grouped by layer. "Both" means fore- and hindlimb. Read-levels are per source.

### 2a. Cis-regulatory routes (no protein changed)

| Element | Perturbation | Phenotype | Limbs | Species | Reference | Read-level |
|---|---|---|---|---|---|---|
| **ZRS** (*Shh* limb enhancer, `Lmbr1` intron 5) | 1.3 kb core replaced with **king cobra** ortholog, CRISPR knock-in | Complete loss of limb-bud *Shh*; severe truncation, indistinguishable from enhancer deletion | Both | Mouse | Kvon 2016, PMID 27768887 | `full-text` |
| **ZRS** | Same, **Burmese python** ortholog | Slightly milder: most elements distal to the stylopod–zeugopod junction severely affected; 2–3 rudimentary forelimb digits; very weak residual *Shh* | Both | Mouse | Kvon 2016, PMID 27768887 | `full-text` |
| **ZRS** | **Human** or **coelacanth** ortholog knock-in | **Normal limbs.** 400 Myr of divergence is tolerated; snake divergence is not | Both | Mouse | Kvon 2016, PMID 27768887 | `full-text` |
| **ZRS** | 17 bp lizard sequence (overlapping the **E1 ETS** site) reintroduced into the python allele | **Rescues normal limb development.** A single binding site is the switch | Both | Mouse | Kvon 2016, PMID 27768887 | `full-text` |
| **ZRS** | Targeted deletion of the conserved intronic module | Complete loss of limb-specific *Shh*; degeneration of elements distal to the stylopod/zeugopod junction | Both | Mouse | Sagai 2005, PMID 15677727 | `abstract` |
| **ZRS** | ~1,000 human variants assayed in vivo; combinatorial and single-nucleotide saturation | 71% of rare non-coding variants previously called causal drove a pathogenic-pattern reporter; confirmed polydactyly in knock-in mice | — | Mouse (human variants) | Kvon 2020, PMID 32169219 | `abstract` |
| **CTCF sites** in the *SHH* locus (12 kb, within `LMBR1`, near ZRS) | Homozygous deletion in patients; three CTCF sites mediate ZRS↔*SHH* promoter contact, substituted by centromeric sites in disease | **Acheiropodia** — congenital limb truncation | Both | **Human** | Ushiki 2021, PMID 33863876 | `abstract` |
| Same 12 kb, **orthologous mouse** sequence | Knockout | **No apparent abnormality** — the mouse does not model the human CTCF alteration | — | Mouse | Ushiki 2021, PMID 33863876 | `abstract` |
| *Pitx1* pelvic enhancer | Recurrent natural deletion in wild stickleback populations | Pelvic (hindlimb-homologue) loss, under positive selection; *Pitx1* null is lethal, the enhancer deletion is not | Hind | Stickleback | Chan 2010, PMID 20007865 | `abstract` |

### 2b. Coding / loss-of-function routes

| Gene | Perturbation | Phenotype | Limbs | Species | Reference | Read-level |
|---|---|---|---|---|---|---|
| **Fgf10** | Germline null | Limb bud initiation **abolished**; fetuses develop to birth with **complete absence of both fore- and hindlimbs**; AER never forms; perinatal lethal from absent lungs | Both | Mouse | Min 1998, PMID 9784490 | `abstract` |
| **Fgf10** | Germline null (independent line) | Complete truncation of fore- and hindlimbs; buds initiate but do not grow out; **neither AER nor ZPA forms**; clavicle unaffected | Both | Mouse | Sekine 1999, PMID 9916808 | `abstract` |
| **Wnt3** (ectoderm) / **β-catenin** (conditional) | Wnt3 loss; β-catenin removed from ventral ectoderm | AER fails to be established; removing β-catenin after induction makes an existing AER disappear | Both | Mouse | Barrow 2003, PMID 12569130 | `abstract` |
| **WNT3** | Homozygous **Q83X** nonsense, consanguineous family | **Tetra-amelia** — complete absence of all four limbs, with craniofacial and urogenital defects | Both | **Human** | Niemann 2004, PMID 14872406 | `abstract` |
| **Meis1 + Meis2** | Inactivation in the **lateral plate mesoderm** | **Limb agenesis.** Meis co-binds extensively with Tbx and co-regulates *Fgf10* enhancers; three deleted alleles give proximal hypoplasia and posterior agenesis via failure of the AP prepattern needed for *Shh* | Both | Mouse | Delgado 2021, PMID 34035267 | `abstract` |
| **Tbx5** | Germline null | **Forelimb buds do not form**; limb-field patterning is intact; FGF/Wnt loops never start; Tbx5 directly activates *Fgf10* through a conserved site | Fore | Mouse | Agarwal 2003, PMID 12490567 | `abstract` |
| **Tbx5** | Conditional deletion in the forelimb | Forelimb bud development fails; also required later for continued outgrowth | Fore | Mouse | Rallis 2003, PMID 12736217 | `abstract` |
| **Tbx4** | Germline null | Hindlimb field induced and initially patterned, but **buds fail to develop** and do not maintain *Fgf10*; embryos die by E10.5 from chorioallantoic failure | Hind | Mouse | Naiche 2003, PMID 12736212 | `abstract` |
| **Pitx1** (*Ptx1*) | Germline null | Hindlimb development **severely impaired, not abolished** — ilium and knee cartilage absent, long bones underdeveloped, *Tbx4* reduced | Hind | Mouse | Lanctôt 1999, PMID 10101115 | `abstract` |
| **Fgf4 + Fgf8** | Inactivated in AER cells or their precursors | In the complete absence of both activities, **limb development fails**; FGFs act on bud cell number and survival | Both | Mouse | Sun 2002, PMID 12152071 | `abstract` |
| **Grem1** | Germline null | Mesenchymal Grem1 is required to establish a functional AER and the SHH/FGF feedback loop; core limb-bud mesenchyme is eliminated by apoptosis; neonatal lethal (no kidneys) | Both | Mouse | Michos 2004, PMID 15201225 | `abstract` |

### 2c. Comparative / evolutionary evidence (not mouse engineering)

| System | Finding | Reference | Read-level |
|---|---|---|---|
| Python hindlimb | Hindlimb development **arrests**; mutations abolish TF binding sites in the SHH limb enhancer, so SHH is weak and transient; HOXD digit enhancers are conserved and the bud reaches a distal phase with transient tibia/fibula/footplate condensations | Leal & Cohn 2016, PMID 27773569 | `abstract` |
| Cetaceans | ZRS regulatory activity **significantly lower than mouse**, consistent with cessation of hindlimb-bud SHH; accelerated *TBX5*; a convergent FGF10 site (D42G) and a rapidly evolving GREM1 CNE in marine mammals | Sun 2022, PMID 36460960 | `abstract` |

**Count: 20 cited perturbations across 10 distinct loci** — 9 cis-regulatory rows and 11
coding rows; 2 of the 20 are human conditions rather than engineered mice. **Six describe
failure of a limb bud to form at all**, as opposed to truncation of a bud that formed: `Fgf10`
(Min 1998 and Sekine 1999), `WNT3` Q83X (tetra-amelia), Meis1/2-LPM (agenesis), `Tbx5` null
(forelimb buds do not form) and `Tbx4` null (hindlimb buds fail to develop).

### 2d. The three distinctions that decide what "limbless" means

1. **Amelia vs truncation.** `Fgf10`-null, `Wnt3`-Q83X and Meis1/2-LPM give *no limb*. ZRS
   knock-in/knockout gives a *stump*: the stylopod forms, the autopod does not. These are not
   the same phenotype and they are not the same layer of the network.
2. **Viability.** Several routes are lethal for reasons unrelated to limbs: `Fgf10`-null dies
   perinatally from lung agenesis (Min 1998, `abstract`), `Tbx4`-null by E10.5 from allantoic
   failure (Naiche 2003, `abstract`), `Grem1`-null neonatally from absent kidneys (Michos 2004,
   `abstract`). A *viable* limbless mouse is a stricter ask than a limbless embryo, and the
   cis-regulatory route is the one that delivers it — the ZRS-null mice in Kvon et al. were
   photographed at two weeks of age (Figure S3E, `full-text`).
3. **Species transfer is not safe.** Ushiki et al. deleted the mouse sequence orthologous to the
   human acheiropodia interval and saw **no apparent abnormality**, attributing it to inherent
   CTCF motif differences between species (PMID 33863876, `abstract`). Any sequence-level
   prediction that ignores this will be confidently wrong.

---

## 3. Why this is a genuinely good test case for a system like ours

We care about this question because it is a *better* benchmark than the problem our own demo is
built on, and we would rather say so than defend the demo.

- **It is a removal, not an addition.** Our flying-fish goal asks for a capability no organism in
  the design envelope has, so there is **no ground truth to score against**. Limb loss has
  ground truth in both directions: dozens of published genotype→phenotype pairs in mouse, and
  three independent natural experiments (snakes, cetaceans, stickleback pelvis) where evolution
  already ran the ablation.
- **The network is unusually well mapped.** Tbx5 → *Fgf10* → AER → Fgf8 → Shh (ZPA) → Grem1 →
  back to the AER is one of the few developmental circuits where the wiring, the epistasis
  (*Fgf10* acts upstream of *Fgf8*; Min 1998, `abstract`) and the loss-of-function phenotype of
  almost every node are published.
- **The readout is unambiguous and scoreable.** A skeletal preparation either has an autopod or
  it does not. Compare that with "does this fish glide further", which depends on a coupling we
  have formally **refused** (§4).
- **There is a measured cis-regulatory dose–response.** Kvon et al. 2016 gives an ordered series
  — mouse ≈ human ≈ coelacanth (normal) > boa (ZPA activity retained) > python (weak residual
  *Shh*, 2–3 rudimentary digits) > cobra (no activity, full truncation) — and Kvon et al. 2020
  gives ~1,000 single-nucleotide and combinatorial variants of the same element scored in vivo.
  **That is a labelled dataset over exactly the object a genome language model emits a score
  for**, which is rare.
- **It is therefore a falsifiable test of the one thing we would be adding.** Score the ZRS
  ortholog series and the Kvon 2020 variant panel with a sequence model; ask whether the model's
  ranking reproduces the measured ranking. If it does not, we have learned something real and
  cheap. We have not run this.

**The honest counterweight:** published benchmarks find that DNA language models are
*inconsistent* on regulatory DNA and do not clearly beat ab-initio baselines on counterfactual
variant-effect prediction, despite much higher compute (Patel et al., DART-Eval,
arXiv:2412.05430, `abstract`). Evo 2 itself reports accurate functional-impact prediction for
non-coding pathogenic and BRCA1 variants without fine-tuning (Brixi et al. 2026, Nature,
PMID 41781614, `abstract`) — but a BRCA1 saturation panel and a 1.3 kb limb enhancer are not the
same task, and we would not assume transfer.

---

## 4. How we would actually attack it — and what is already built

This section separates **what exists and has been run** from **what we would have to build**.
MorphoSwarm Studio is the system the judge saw; the Frontier pages are the same system.

### 4a. What already exists, with receipts

| Component | State today | Would it help here? |
|---|---|---|
| **Lean 4 proof base** (4.35.0, pinned Mathlib) — 5 families, 37 definitions and theorems, 17 of 17 hand-written mutants rejected, all families `current` | Built and receipted | **Indirectly.** There is **no limb law in Lean today.** The reusable pieces are unit algebra (7 statements) and *scaled threshold intervals* (10), which is the right shape for a dose/threshold argument but is currently instantiated on a simulation-interval comparison, not on enhancer activity |
| **Typed cross-scale coupling** (`frontier.model.interface/1`): ports carry quantity, unit, dimension, scale, context, regime, provenance and bounds; verdicts `composable` / `scenario` / `refused`. Current manifest **4 composable, 5 scenario, 4 refused** | Built | **Yes, mainly by refusing.** A bridge from "enhancer occupancy" (molecular) to "skeletal element present/absent" (organ) is exactly the kind our layer refuses: scale change, context change, no registered calibration |
| **Registered calibrations** | **NONE** | This is the binding constraint. Every cross-scale bridge in the system is refused or assumption-level, and the limb problem would be no exception on day one |
| **Evo 2 pipeline** (Evo 2 7B via Nebius H100) | Run. `results/compute/evo2zf/manifest-fevo2zf1.json`: one H100 job, `rc 0`, 496 s wall, `COMPLETED`. Two arms, 16 + 16 = **32 distinct 1,000 bp candidates** over regulatory windows of 8 zebrafish genes (`elavl3`, `fabp10a`, `gata1a`, `krt4`, `myl7`, `myod1`, `neurod1`, `sox10`) on **GRCz11**, Ensembl coordinates only. Score table has **89 rows: 9 real held-out, 32 generated, 32 dinucleotide shuffles, 16 GC-matched random controls** (`results/resources/evo2-reuse-audit.json`) | **Yes — this is the piece that transfers.** The machinery for "take a regulatory window, score real vs generated vs shuffled vs GC-matched controls, hash everything" exists and has produced a real paired result |
| **Reaction–diffusion / pattern simulators** | 12 tissue-scale and 4 developmental-scale runs recorded, each with a manifest, numerical checks, input hashes and a verified figure, each labelled *simulated, not observed* | Partly. The AER–FGF–SHH–GREM1 loop is a classic activator–inhibitor-plus-feedback system, and we can run it. We cannot calibrate it |

**Limits we will not paper over on the Evo 2 side**, taken from our own audit file: only **one**
natural row is marked fully held out; **likelihood under the generator is not function**; no
expression assay was performed; the candidate set is zebrafish and has nothing to do with limb
enhancers. Independent cross-checks against UCSC succeeded for 3 of 8 symbols and failed on
provider errors or timeouts for the rest (`evo2_zebrafish/.../input_set.json`).

### 4b. What we could do this week — four bounded, falsifiable jobs

1. **Score the Kvon 2016 ortholog series.** ZRS orthologs from 16 species were assayed by
   reporter in that paper; five of them were additionally taken to knock-in mice, where human
   and coelacanth gave **normal limbs**, python gave a **milder truncation with 2–3 rudimentary
   digits**, and cobra gave **full truncation** (mouse being wild type). Ask Evo 2 for
   per-sequence likelihood **and** for the effect of the 17 bp E1-overlapping indel in both
   directions (python → python + 17 bp). Controls: dinucleotide shuffles and GC-matched random
   windows, as in the run we already did. **Pre-register the prediction before scoring.** Pass
   criterion: the model separates the two knock-in-normal orthologs (human, coelacanth) from
   cobra, places python between them, and moves the python score in the direction the mouse
   moved when the 17 bp is reintroduced. There is a real chance it does not, and DART-Eval is
   the reason to expect that.
2. **Score the Kvon 2020 variant panel** (~1,000 in-vivo-assayed ZRS variants) and report rank
   correlation against the published in-vivo calls. This is a genuine held-out benchmark, and it
   is the single most informative thing we could run.
3. **Encode the Ushiki discordance as a refusal.** Human CTCF deletion → acheiropodia; mouse
   orthologous deletion → nothing. Our coupling layer should **refuse** a human→mouse transfer of
   a CTCF-motif-dependent claim and say why, rather than scoring it. This is a one-record change
   and it is the kind of thing the layer is for.
4. **State the dose law in Lean, as a law about the model, not about mice.** Something of the
   form: *given an enhancer-activity variable a with a stated threshold band, and a monotone map
   from a to a distal-element-count, the ordered activity series implies an ordered phenotype
   series.* Then mutate it (flip the monotonicity, change the threshold) and show Lean rejects
   the mutants, as we do for the other five families. **What this would prove is that our
   reasoning is consistent — not that the threshold exists in a mouse.** The anti-triviality
   requirement applies: the theorem must mention the actual activity parameter and must fail
   under a mutated law.

### 4c. What needs a wet lab, and is not ours

Everything after the score. Transgenic reporter assay at E11.5, CRISPR knock-in on a matched
littermate design, whole-mount in-situ for *Shh* at E10.5, Alcian blue/Alizarin red skeletal
preparation at E18.5 — the exact protocol in Kvon et al. 2016 (`full-text`). We have no animal
facility, no IACUC protocol, and no wet-lab arm. A prediction we cannot test is a hypothesis,
and we would label it as one.

### 4d. The gaps, stated plainly

- **No registered calibration exists anywhere in our system**, so no quantitative bridge from
  a sequence score to a skeletal phenotype can be composable today. The best we can emit is a
  *ranking* claim over sequences, which is weaker and honest.
- **No limb law in Lean.** It would have to be written, and it would be a law about a threshold
  model, not about development.
- **No functional validation of any Evo 2 output we have produced.** Our own audit file says so
  in those words.
- **We have never scored a limb enhancer.** Everything in §4b is proposed, not done.

---

## 5. What we would not claim

- **We did not invent this.** Limb loss in mouse is a developmental-biology result that is
  decades old. `Fgf10`-null limbless mice were published in 1998. If anything we would be late
  to the problem by 28 years.
- **No organism was built.** No mouse, no embryo, no cell. No wet-lab experiment of any kind has
  been run by this team.
- **No biological validation.** Every simulation in the system is labelled *simulated, not
  observed*, and every cross-scale coupling is refused or assumption-level.
- **A sequence score is not a phenotype.** Likelihood under a genome model is not transcription,
  and transcription is not a skeleton. We will not round one into the other.
- **Model fidelity is not biological validity.** If our ranking matched Kvon et al.'s ordering
  perfectly, that would mean our model agrees with that experiment. It would say nothing about
  whether the threshold interpretation is correct.
- **We would not claim novelty for the mechanism.** The novel part we would claim, if it
  survives the test, is narrow: *that the phenotypic ordering of a limb enhancer series is
  recoverable from sequence alone, with pre-registered predictions and stated controls.* If it
  does not survive, we would publish that.

---

## 6. Questions we would ask the judge

These are the questions whose answers would change what we built, and they are also the
questions that show which paper we think he is describing.

1. **Which element, and at what resolution?** The ZRS has at least three distinguishable
   "regions" in play in the literature: the **1.3 kb functional core** that Kvon et al. replaced,
   the **E0–E4 ETS binding sites** (of which E1 sits in the 17 bp snake-specific deletion), and
   the **12 kb CTCF block** ~centromeric to it that Ushiki et al. mapped for acheiropodia. Was
   your element inside the core, or in the CTCF/contact layer?
2. **Amelia or truncation, and which pair?** Was there no limb bud at all (the `Fgf10`/`Wnt3`/
   Meis1-2 phenotype), or a proximal stump with no autopod (the ZRS phenotype)? Forelimb,
   hindlimb, or both? These separate the layers of the network cleanly, and the answer tells us
   whether to model initiation or outgrowth.
3. **Germline or conditional, and did the animals live?** A germline `Fgf10` null is perinatally
   lethal for lung reasons that have nothing to do with limbs; `Tbx4` nulls die at E10.5 from
   the allantois. If your mice were viable and limbless, that is a strong hint of a
   limb-restricted cis-regulatory lesion — or of a conditional driver, in which case: which?
4. **Was there a dose–response, or was it binary?** Kvon et al. got an ordered series across
   orthologs and a full rescue from reintroducing **17 bp**. Did you see graded skeletal loss
   tracking graded enhancer activity? That ordering is precisely what a sequence model would have
   to reproduce, and if you have unpublished intermediate alleles, that is the dataset we would
   most want to test against.
5. **Did you hit cross-species discordance?** Ushiki et al.'s mouse deletion of the orthologous
   acheiropodia interval produced **no apparent abnormality**. Did your element behave the same
   way in mouse and human, and if not, did you attribute it to motif turnover?

---

## 7. Sources, with read-levels

Bibliographic records in this table were retrieved from **PubMed** on 2026-11-01. One article
(Kvon et al. 2016) was additionally retrieved in full from PubMed Central (PMC5484524) and read;
every other mouse/human genetics source below was read at **abstract** level only, and nothing
on this page is written in the voice of having read those bodies.

| Source | DOI | Read-level |
|---|---|---|
| Kvon et al. 2016, *Cell* 167:633–642.e11, "Progressive Loss of Function in a Limb Enhancer during Snake Evolution" (PMID 27768887) | [10.1016/j.cell.2016.09.028](https://doi.org/10.1016/j.cell.2016.09.028) | **full-text** (PMC5484524, incl. Figures S3–S5 legends and STAR Methods) |
| Kvon et al. 2020, *Cell* 180:1262–1271.e15, "Comprehensive In Vivo Interrogation Reveals Phenotypic Impact of Human Enhancer Variants" (PMID 32169219) | [10.1016/j.cell.2020.02.031](https://doi.org/10.1016/j.cell.2020.02.031) | abstract |
| Sagai et al. 2005, *Development* 132:797–803 (PMID 15677727) | [10.1242/dev.01613](https://doi.org/10.1242/dev.01613) | abstract |
| Ushiki et al. 2021, *Nat Commun* 12:2282 (PMID 33863876) | [10.1038/s41467-021-22470-z](https://doi.org/10.1038/s41467-021-22470-z) | abstract |
| Delgado et al. 2021, *Nat Commun* 12:3086 (PMID 34035267) | [10.1038/s41467-021-23373-9](https://doi.org/10.1038/s41467-021-23373-9) | abstract |
| Min et al. 1998, *Genes Dev* 12:3156–61 (PMID 9784490) | [10.1101/gad.12.20.3156](https://doi.org/10.1101/gad.12.20.3156) | abstract |
| Sekine et al. 1999, *Nat Genet* 21:138–41 (PMID 9916808) | [10.1038/5096](https://doi.org/10.1038/5096) | abstract |
| Barrow et al. 2003, *Genes Dev* 17:394–409 (PMID 12569130) | [10.1101/gad.1044903](https://doi.org/10.1101/gad.1044903) | abstract |
| Niemann et al. 2004, *Am J Hum Genet* 74:558–63 (PMID 14872406) | [10.1086/382196](https://doi.org/10.1086/382196) | abstract |
| Agarwal et al. 2003, *Development* 130:623–33 (PMID 12490567) | [10.1242/dev.00191](https://doi.org/10.1242/dev.00191) | abstract |
| Rallis et al. 2003, *Development* 130:2741–51 (PMID 12736217) | [10.1242/dev.00473](https://doi.org/10.1242/dev.00473) | abstract |
| Naiche & Papaioannou 2003, *Development* 130:2681–93 (PMID 12736212) | [10.1242/dev.00504](https://doi.org/10.1242/dev.00504) | abstract |
| Lanctôt et al. 1999, *Development* 126:1805–10 (PMID 10101115) | [10.1242/dev.126.9.1805](https://doi.org/10.1242/dev.126.9.1805) | abstract |
| Sun, Mariani & Martin 2002, *Nature* 418:501–8 (PMID 12152071) | [10.1038/nature00902](https://doi.org/10.1038/nature00902) | abstract |
| Michos et al. 2004, *Development* 131:3401–10 (PMID 15201225) | [10.1242/dev.01251](https://doi.org/10.1242/dev.01251) | abstract |
| Chan et al. 2010, *Science* 327:302–5 (PMID 20007865) | [10.1126/science.1182213](https://doi.org/10.1126/science.1182213) | abstract |
| Leal & Cohn 2016, *Curr Biol* 26:2966–73 (PMID 27773569) | [10.1016/j.cub.2016.09.020](https://doi.org/10.1016/j.cub.2016.09.020) | abstract |
| Sun et al. 2022, *BMC Genomics* 23:797 (PMID 36460960) | [10.1186/s12864-022-09024-3](https://doi.org/10.1186/s12864-022-09024-3) | abstract |
| Brixi et al. 2026, *Nature* 652:1349–61, "Genome modelling and design across all domains of life with Evo 2" (PMID 41781614) | [10.1038/s41586-026-10176-5](https://doi.org/10.1038/s41586-026-10176-5) | abstract |
| Patel, Singhal, Wang, Pampari, Kasowski & Kundaje, "DART-Eval: A Comprehensive DNA Language Model Evaluation Benchmark on Regulatory DNA", arXiv:2412.05430 | [10.48550/arXiv.2412.05430](https://doi.org/10.48550/arXiv.2412.05430) | abstract (Consensus record + arXiv landing page; body not read) |

**Scope of the negative searches.** PubMed was searched for `Prrx1` limb enhancers in snakes and
returned nothing usable at the query used, so **no Prrx1 claim appears on this page**; that is an
absence in our search, not an absence in the literature. We did not search non-English sources,
patents, or theses. The cetacean and stickleback rows are comparative genomics and population
genetics respectively, not engineered mouse phenotypes, and are labelled as such.

**Internal receipts cited in §4a**, all in this repository:
`results/compute/evo2zf/manifest-fevo2zf1.json`, `results/resources/evo2-reuse-audit.json`,
`evo2_zebrafish/pinned/experiments/bioservices/zebrafish_evo2_regulatory_candidates/input_set.json`,
`docs/dossier/05-lean-for-biology.md`, `docs/dossier/06-simulations-across-scales.md`.

---

*Per PubMed's terms of use: bibliographic records and abstracts on this page were retrieved from
PubMed (NCBI), and the DOI of every cited article is given above.*
