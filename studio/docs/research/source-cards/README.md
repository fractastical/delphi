# Source cards — Frontier multiscale substrate (human-readable companion)

**The authoritative, machine-readable source cards are
[`../../../data/research/flying-fish-source-cards.json`](../../../data/research/flying-fish-source-cards.json)**
(stable ids, locators, read-levels, licenses, evidence kinds, parameters, constraints, connectors,
bounded searches, and the eleven-scale map). This file is the readable companion, **corrected
2026-10-31 after root review** (see the correction note at the end).

Read-levels: `full-text` | `full-text via r.jina.ai` | `via fetch tool` | `abstract` | `listing` |
`search-summary` | `could-not-access`. **Single-reader (fable-lead), NOT Codex-reviewed.**
All measured ranges are **provenance-scoped envelopes, not feasibility laws.**

---

## A. Organism / organ — biomechanics (envelopes behind the checker constraints)

### A1. Fish, F. E. (1990) — Wing design and scaling of flying fish
- *J. Zool. Lond.* 221:391–403. `full-text` (PDF re-read this session via pdftotext, 368 KB).
- **Definitions, quoted:** wing loading "given in N/m² and calculated as the specimen weight divided
  by the wing area" (p.394); **wing area** "defined as the combined areas of the pectoral and pelvic
  fins continuous through the body" (Methods); AR "calculated as the wing span squared divided by the
  wing area" (p.394). **The measured AR range 3.0–16.9 is of INDIVIDUAL PECTORAL FINS** — "The aspect
  ratios (AR) of individual flying fish pectoral fins range from 3.0 to 16.9" (p.395); Table III to
  19.9 for *Exocoetus*.
- **Supports:** C1 (WL 11.7–208.9 N/m², envelope over 199 specimens / 33 spp / 6 genera), C2
  (V ∝ √WL, Pennycuick 1972 relayed), C5 (pectoral-fin AR 3.0–16.9), hypocaudal lobe 63.1% launch
  motor, pectoral 76–92% of wing area, juveniles <0.05 m do not glide.
- **Caveats:** AR 16.9 (text) vs 19.9 (Table III) unresolved; applying the **pectoral-fin** AR bound
  to a candidate's **whole-wing** b²/S is a flagged modelling choice (guilds "correspondence"), not
  an identity — the denominators differ. These are envelopes of a sample, not limits.

### A2. Park & Choi (2010) — Aerodynamic characteristics in gliding flight
- *J. Exp. Biol.* 213:3269–3279. `full-text, via fetch tool`. Pectoral-fin AR **9.0–10.7** (same
  quantity as A1's pectoral range, corroborating it); pelvic fins >20% lift; ground-effect drag 14%
  water / 9% solid. Numeric L/D only in figures (`could-not-access`).

### A3. Davenport (1992) — Wing-loading, stability, morphometrics
- *J. Mar. Biol. Assoc. UK* 72:25–39. `abstract, via fetch tool`. **Reports** (abstract-grade): a
  pectoral-fin-length limit of ~78–79% SL ("swimming will be impaired"); CG-aft longitudinal
  instability with the living witness *Oxyporhamphus micropterus*; four-wingers' pelvic fins **act as
  a stabilising tailplane**; white-muscle launch. Treat each as a reported envelope/claim, not a law.

### A4. Davenport (2003) — Allometric constraints on stability and maximum size
- *J. Fish Biol.* 62:455–463. `listing` + `search-summary`. **UNREAD** — Wiley Cloudflare block
  (direct + r.jina.ai). The size-limit paper the problem most needs at full text; an **access
  blocker, not an absence** (open problem FF-Q10).

---

## B. Evolution — phylogeny & fossils

- **B1. Lovejoy, Iranpour & Collette (2004)**, *Integr. Comp. Biol.* 44:366–377, PMID 21676722
  (`abstract`): flyingfishes **nested within halfbeaks** — ancestor a surface beloniform with an
  elongated lower jaw. A **reconstruction/hypothesis**, not demonstrated reachability.
- **B2. Xu et al. (2013)**, *Proc. R. Soc. B* 280:20122261 (`listing`+`search-summary`, Crossref-
  verified): convergent Triassic four-winger *Potanichthys* ~15 cm; configuration is an attractor,
  not an ancestor of modern flying fish.
- **B3. Fish Tree of Life** `actinopt_12k_treePL.tre` (`full-text`, downloaded+parsed): 11,638 tips,
  38 exocoetid tips; CC BY 4.0. Basis for C6a placement. The one immediately machine-readable dataset.

---

## C. Molecule / cell — the molecule→form candidate (corrected: NOT a gap)

### C1. Daane et al. (2021) — Modulation of bioelectric cues in the evolution of flying fishes
- *Curr. Biol.* 31(24):5052–5061, DOI 10.1016/j.cub.2021.08.054, **PMC9172250**.
  `full-text via r.jina.ai` (127 KB) + `abstract` (Europe PMC core). Non-OA; Europe PMC license
  "None".
- **Supports (cited source claim):** phylogenomics across **35 species**; >300,000 loci; 48/17,937
  genes with convergent evolutionary-rate shifts; **`lat4a`** (L-type amino-acid transporter) ×
  **`kcnh2a`** (K⁺ channel) interaction **phenocopies flying-fish fin proportion in zebrafish**;
  `kcnh2a` ectopic expression sufficient to drive fin overgrowth (Fig 3); fin-length-vs-SL allometry
  measured across the clade (Fig 1B).
- **Hard limits of the claim:** this is fin **PROPORTION/size**, **NOT flight** — no flight is
  demonstrated by the genetics. The functional test is in **zebrafish**; the flying-fish side is
  **association**. Applying the phenocopy to a halfbeak/exocoetid is an **UNESTABLISHED
  cross-organism transfer**. Exact Fig 4 ratio numbers **not extracted** — `daanelab.org` DNS-
  unresolvable here, PMC/Europe PMC XML blocked for non-OA (access failure, open problem FF-Q07).

### C2. Bioelectric fin-size mechanism (model-organism basis)
- Daane et al. 2018 (PMC6039437, `full-text`, CC BY): bioelectric/calcineurin sets zebrafish fin
  size; fin-length/standard-length readout. Stewart et al. 2021 (`full-text`): `kcnh2a` ectopic
  expression prolongs fin outgrowth. Jiang et al. 2024 (PMC11018282, `full-text`): pectoral fin-bud
  scaling via intercellular K⁺. All **zebrafish**; the cellular-scale candidate, not exocoetid data.

### C3. Astyanax cavefish `oca2` (contrast — corrected)
- Warren et al. 2021 (PMC7933363, `full-text`); Protas et al. 2006 (PMID 16341223, `abstract`).
- **Corrected supports:** an **independent rerun of a sequence-level claim** — exon 21 absent from
  the Molino assembly, present in surface, via `grep -F` on exact 24-mers with a positive control and
  a must-fail decoy (`messages/cavefish-loop.md`). It reproduces a **sequence fact**, **not** a
  demonstrated causal molecule→(pigment/eye) loop (the causal link is Protas's association,
  abstract-only, not reproduced). A template for falsifiable sequence checks, not a closed
  genotype→phenotype loop.

### C4. NCBI Exocoetidae genome — context, not a limit
- NCBI Datasets v2alpha: `GCA_018398805.1` *Hirundichthys speculiger*, scaffold, 1.04 Gbp
  (`full-text`, API). One scaffold-level assembly — but comparative genomics across the clade **is**
  done by Daane 2021 via targeted sequencing of 35 species, so "comparative genomics impossible" was
  **wrong** and is withdrawn.

---

## D. Tissue model class & systems-biology library

- **D1. Godivier et al. (2024)** jaw-joint mechanoregulated growth (PMC10880962; Zenodo 7586155,
  CC BY 4.0; `full-text`): the growth-law **model class** transfers (workbook replays to 2e-16;
  `LoadScaling.lean`); the **zebrafish jaw-cartilage parameters do NOT** transfer to a fin ray
  (organism/tissue/BC/load-spectrum mismatch).
- **D2. BioModels reproducibility set** (Tiwari et al. 2021, PMC7901289, `full-text`, CC BY): 455 ODE
  models, R 233 / NRP 169 / RMC 40 / RAH 13 — a replayable library; **no entry couples to a
  flying-fish scale.**

---

## E. Method / epistemics / coordination

- **E1. Firat, ASK** (SSRN 10.2139/ssrn.7416579, `full-text`): six-dimension Activation Test → maps
  1:1 onto Frontier primitives; "missing capacities must remain visible."
- **E2. Shenoy Lab** (`shenoy.engineering.upenn.edu`, `via fetch tool`): nucleus→organ, µm–cm;
  transferable structure, organism-specific parameters.
- **E3. Virtual Agent Economies** (arXiv 2509.10147, `search-summary`): impermeable mission economy;
  equal endowment; auction allocation.
- **E4. Contributed compute & federation** (`morphoswarm/.../contributed-compute-and-federation.md`):
  Bittensor caution — transferable reward incentivises fabricating artifacts that pass the paying
  check; credit attaches to reviewed evidence.
- **E5. Darwin, *Origin* ch. VI** (Gutenberg + Darwin Online variorum, `full-text` / `full-text via
  r.jina.ai`, public domain): conceivability argument; see `../darwin-flying-fish.md`.

---

## F. Access state of connectors (verified 2026-10-31)

| Connector | State | Note |
|---|---|---|
| NCBI Datasets / E-utilities, EBI ENA, Fish Tree of Life, FishBase HTML, BioModels index | retrieved→validated/replayed | all read/parsed this session |
| rOpenSci `fishbase.ropensci.org` | **dead** | curl exit 000; 4 control hosts 200 |
| Europe PMC `search` JSON | retrieved | Daane abstract + metadata |
| Europe PMC `fullTextXML` (PMC9172250) | **HTTP 500** | non-OA; OA records serve XML. Not an absence |
| `r.jina.ai` proxy | retrieved | Daane full text; Darwin variorum (recovered from 403) |
| `daanelab.org` (author host) | **dead here** | DNS no-answer; Jina 422. Exact Fig 4 ratios not extracted — **access failure, not absence** (FF-Q07) |
| Zenodo records API | retrieved/replayed | jaw-joint 7586155 readable; 5786693 → 403 |

**Bounded morphometrics search (2026-10-31 UTC)** — per-specimen paired pectoral-fin-area + body-mass:
**Dryad** `Exocoetidae`→0 (one `flying fish morphometrics` hit is a bird-blowfly dataset); **Zenodo**
`Exocoetidae`→353, all taxonomic treatments; **Figshare** `search_for=Exocoetidae`→unrelated results
(**inconclusive, not a clean negative**); **MorphoBank** API→**403, not accessed**. Result:
**searched-not-found on those four repositories on that date, NOT universal absence** (open problem
FF-Q06). Fish 1990 measured fin-area×mass on 199 specimens but published only r.m.a. coefficients.

---

## Correction note (2026-10-31, after root review)
Withdrawn from the first version of these cards: (1) "comparative genomics impossible / no candidate
locus" — **false**, Daane 2021 (C1); (2) cavefish as a "closed molecule→organism loop" — it is an
**independent rerun of a sequence-level fact** (C3); (3) "no public deposit" as universal absence —
replaced by the **bounded, dated** search (§F); (4) "AR 3.0–16.9" as whole-wing — it is **individual
pectoral-fin AR** (A1). Envelopes are not feasibility laws; organism-context transfers are labelled.
