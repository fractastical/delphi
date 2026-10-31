# Frontier multiscale substrate: what the sources and tools actually support

**Status:** research note (implementation-focused) · **Owner:** fable-lead · 2026-10-31 Seattle PDT
**Branch:** `work/frontier-specs` · writes under `docs/research/` only.
**Supports, does not write:** this note is input for **Root's normative `spec005`**
(`SPEC-005-agentic-engineering-demo`). It states what is retrievable, replayable, and executable
*today*; the spec decides what is normative. Nothing here is a de novo biology result.
**Reviewer status:** **single-reader (fable-lead), NOT Codex-reviewed.** A careful first reading, not
accepted.

> **Correction log (2026-10-31, after root review).** This note's first version made three claims I
> have withdrawn: (1) that the molecule scale was a gap with "no candidate locus" and that
> "comparative genomics is unsupportable" — **false**: Daane et al. 2021 (PMC9172250) is genome-wide
> across 35 species and gives a `lat4a`×`kcnh2a` fin-proportion candidate (§1, §4b); (2) that the
> cavefish `oca2` work was a "closed molecule→organism loop" — it is an **independent rerun of a
> sequence-level fact**, not a demonstrated causal mechanism (§0); (3) "ancestor identified /
> reachability solved" — the ancestor is **reconstructed** (a hypothesis), not proven reachable
> (§1). Unbounded "no public deposit" absence claims are now bounded, dated searches (§5).

**Read-level key:** `full-text` (parsed directly) | `full-text via r.jina.ai` (actual rendered page
text through the public read proxy, parsed by me) | `abstract` | `listing` | `search-summary` |
`could-not-access`. Pages read through `WebFetch` are marked **via fetch tool** (answered by a
separate small model — a weaker grade). Evidence-kind tags per spec005: **measured**, **fitted**,
**assumed**, **design-selected**, plus the provenance distinctions **cited source claim**,
**independent rerun**, **inference**, **missing bridge**.

---

## 0. The finding that should shape spec005

**Flying fish is best-supported at the organism / organ / evolution scales (measured biomechanics, a
downloadable time-tree → executable constraints C1–C6) and thinnest at the tissue and cell scales.
The molecule scale is NOT empty** — Daane et al. 2021 give a comparative-genomic + functional
candidate (`lat4a`×`kcnh2a`) for fin **proportion**. **But the couplings from that genetics up to an
aerodynamic fin are unbuilt bridges, not replayable models**, and **no flight is demonstrated by the
genetics.** So `spec005` can make the organism-scale constraints executable (arithmetic over declared
numbers, C1–C6 below), should record the molecular candidate as a **sourced claim with its evidence**,
and must mark everything between as an **explicit cross-scale gap**, never a checked coupling — the
ASK discipline of "missing capacities must remain visible" (§2.4).

On the cavefish contrast, corrected: the `oca2` exon-21 work (`messages/cavefish-loop.md`) is an
**independent rerun of a sequence-level claim** — the exon is absent from the Molino assembly and
present in the surface assembly, found by `grep -F` on exact 24-mers with a positive control and a
must-fail decoy. It reproduces a **sequence fact**, not a causal molecule→(pigment/eye) mechanism;
the causal link is Protas et al.'s association (abstract-only, not reproduced here). It is a good
template for *falsifiable sequence checks*, not a claim that genotype→phenotype is closed.

---

## 1. The multiscale coupling map for flying fish

Scales are the **eleven levels of `SPEC-026` / `spec005`** (molecular, macromolecular, subcellular,
cellular, tissue, organ, neural/control, whole-organism, developmental, collective, ecological). The
flying-fish design problem occupies a subset; showing a scale never claims an executable model exists
there (spec005). Rows below are the occupied scales.

Legend: **[EXEC]** computable from declared numbers (→ constraint solver / Lean). **[FIT/EMP]** a
measured fit or empirical envelope, not a checkable inequality on a design. **[CLAIM]** a sourced
scientific claim (cite it; do not treat as a checked coupling). **[GAP/bridge]** a cross-scale
coupling with no replayable exocoetid model. Source cards for every row: `source-cards/` and the
machine-readable `../../data/research/flying-fish-source-cards.json`.

| Scale (SPEC-026 #) | What is actionable now | Connector / source | Kind | Coupling downward |
|---|---|---|---|---|
| **Ecological / evolution (11/evo)** | Flyingfishes nested within halfbeaks; 38 exocoetid tips on a time-calibrated tree; convergent Triassic four-winger | Fish Tree of Life `.tre` (parsed, 11,638 tips); Lovejoy 2004 (`abstract`); Xu 2013 (`listing`) | **[EXEC]** C6a places a design on the tree; ancestor **reconstructed** as a surface beloniform, elongated lower jaw — a hypothesis, **not** demonstrated reachability | organism←evo: ancestor **reconstructed, not proven reachable** |
| **Whole-organism (8)** | Wing loading 11.7–208.9 N/m²; AR 3.0–16.9; launch 10→16–20 m/s; family stops at 50 cm | Fish 1990 (`full-text`); Park & Choi 2010 (`abstract/relayed`); Davenport 1992/2003; FishBase (scraped, 69/116) | **[EXEC]** C1,C2,C5,C6b · **[CLAIM]** predator-escape pressure, 167 yr old, **never quantified** (do not threshold) | organ←organism: pectoral = 76–92% of wing area (**measured**) |
| **Organ (6)** — the fin/wing | Pectoral fin ≤78–79% SL; CG-vs-CoP stability; hypocaudal lobe 63.1% launch motor; pelvic fins >20% lift | Davenport 1992 (`abstract`); Fish 1990 (`full-text`); Park & Choi 2010 | **[EXEC]** C3 · **[CLAIM]/witness** C4 (qualitative; **no numeric CG retrieved in the sources read**; witness *Oxyporhamphus*; stability is **configuration-dependent** and trades against lift — Saro-Cortes 2022 robotic, Park & Choi 2010 physical — so C4's static CG-sign is narrower than it reads, yet the *Oxyporhamphus* refutation survives: CG-aft is a body-plan fact) | tissue←organ: **[GAP/bridge]** no measured map from fin-ray geometry+material to organ-scale AR under growth |
| **Tissue (5)** — lepidotrichia, cartilage, white muscle | *Model class + bioelectric mechanism (zebrafish), not exocoetid* | Jaw-joint deposit Zenodo 7586155 (`LoadScaling.lean`, workbook to 2e-16); bioelectric-fin refs | **[CLAIM]** model class transfers; **[GAP/bridge]** exocoetid parameters do not (§4a) | cell←tissue: open even in the model organism |
| **Cellular (4)** — fin-bud cells: Vmem + mechanics | *Model-organism candidate:* Vmem/K⁺ (`kcnh2a`,`kcnk5b`) + calcineurin sets zebrafish fin size; nothing exocoetid-specific | Daane 2018 (PMC6039437), Stewart 2021, Jiang 2024 (`full-text`); jaw-joint per-cell tables (zebrafish, ~0.5 MB) | **[CLAIM]** in zebrafish · **[GAP/bridge]** for exocoetid | molecule←cell: `kcnh2a` links the two **in zebrafish**; unbuilt for exocoetid |
| **Molecular (1)** — genes shaping paired-fin proportion | Genome-wide signatures across **35 beloniform species**; `lat4a`×`kcnh2a` **phenocopy flying-fish fin proportion in zebrafish**; 48/17,937 genes convergent rate-shift; >300,000 loci | **Daane 2021** (`full-text`, NOAA repository PDF, 47 pp + Europe PMC `abstract`); NCBI `GCA_018398805.1` (scaffold) | **[CLAIM]** candidate for fin **size/proportion**; **no flight demonstrated by the genetics**; flying-fish side is phylogenomic **association**, functional test is **in zebrafish** | — |

**Reading for spec005:** the executable constraints live at the top three rows and are arithmetic.
Below the organ, the molecule scale carries a **sourced candidate** (Daane 2021) that spec005 should
record as a claim with its evidence, while the cell and tissue couplings **to an exocoetid fin**
remain unbuilt bridges. A statement that the genetics *produce flight*, or that the mechanism is
demonstrated *in an exocoetid*, would be a curator statement dressed as a result — exactly what the
register correction warned against (148/250 unsourced are curator statements, not sourced field-level
open problems). **Evidence contest is first-class: none of these rows asserts a domain impossibility.**

---

## 2. The substrate architecture, mapped to real sources and store primitives

Five layers the substrate must cover (user steering), each mapped to (a) a connector/tool that
exists and (b) the spec005 object + store primitive that carries it.

### 2.1 Data connectors / indexes
Verified surfaces (full table + how-verified in §5): NCBI Datasets v2alpha ✓, E-utilities ✓, EBI ENA
FASTA ✓, Fish Tree of Life ✓ (parsed), FishBase HTML ✓ / rOpenSci API ✗ dead, BioModels
reproducibility index ✓, Europe PMC `fullTextXML` ✓ (500 for one non-OA record) + `search` JSON ✓,
`r.jina.ai` public proxy ✓ (Daane full text, Darwin variorum), Zenodo records API ✓, SSRN ✓,
Crossref/OpenAlex/Semantic Scholar ✓. **Spec005 `Connector`** distinguishes *discovered / accessible
/ retrieved / replayed / validated* — the §5 table reports which state each reached. **Store
primitive:** the content-addressed version store is the index; `source` provenance on each record
holds the connector URL + read-level + state.

### 2.2 Tools + skills
Reusable bounded procedures demonstrated: the read-level discipline; the `r.jina.ai` 403-fallback; the
`WebFetch` separate-small-model caveat; `systemd-run --user --scope` bounding; the cavefish `grep -F`
exact-24-mer matcher with a shuffled must-fail decoy; FASTA exon extractor; FishBase parser; Newick
parser; the repository-search probes of §5. **Spec005 `Tool/skill`:** capability manifest + I/O
schema + observed success/failure receipts; a skill with a paired must-fail control is the unit to
require. Maps to `Action.code` + `cache_key[code,environment,parameters]`.

### 2.3 Parameters + units
Measured quantities carry units and mostly a source fit: `WL` N/m², `V` m/s, `M` kg, `SL` m, `AR`
dimensionless; Fish 1990 `WL=a·M^b` (a in N/m², M in kg) per genus; jaw-joint `a=3e9 m²N⁻¹s⁻¹`,
`b=5e10 m³N⁻¹s⁻¹`; Daane fin-length/standard-length allometry (measured across the clade, Fig 1B —
numeric values in figures, not extracted). **The executable/empirical divide lives here:** a parameter
with a sourced measurement *and* a unit is checkable; one without (a CG offset for C4, a maximum body
mass) is **assumed**. **Spec005 `Parameter`** already encodes exactly this: value/range or explicit
unknown, source locator, `measured|fitted|assumed|design-selected`, organism/context, uncertainty and
transfer limits. (This replaces the free-string parameter of SPEC-003.)

### 2.4 Epistemic / evidence layer — ASK's six dimensions have store homes
Firat's ASK model (SSRN `10.2139/ssrn.7416579`, `full-text`) supplies a conformance test whose six
dimensions map one-to-one onto Frontier primitives:

| ASK dimension | Frontier primitive (spec) |
|---|---|
| Addressability | per-record `version = sha256(canonical)` (SPEC-001) |
| Evidential traceability | typed edges + append-only `events` (SPEC-001/002) |
| Conditional executability | `Action` + eight-dim `cache_key` + `acceptance_policy` (SPEC-003) |
| Version responsiveness | `predecessor`/`heads`, status per exact version (SPEC-001/002) |
| Context-preserving transferability | bundles set `imported_unreviewed`, never grant authority (SPEC-004) |
| Contestable federation | fork-on-conflict + `disputed` first-class (SPEC-002/004) |

ASK's rule *"missing capacities must remain visible"* **is** the refusal discipline; read-level +
confidence grade on each card is its metadata. The seven Assessment dimensions (SPEC-002) are the
review instrument; `computational_replay_formal_check` is where a Lean/solver verdict lands.

### 2.5 Coordination / multiparty open science
Store primitives: atomic leases (don't-pay-twice), independent review (executor operator ≠ reviewer
operator), bundles + fork-on-conflict (federation, no central authority), digest = integrity (not
signature/timestamp/acceptance). Prior art (`morphoswarm/.../contributed-compute-and-federation.md`):
BOINC/Folding@home redundant verification; Petals/Hivemind; nanopub network; **Bittensor — transferable
reward incentivises fabricating artifacts that pass the paying check (avoid)**. **Virtual Agent
Economies** (DeepMind, arXiv `2509.10147`, `search-summary`): sandbox economy on *origin × permeability*;
impermeable sandbox for higher-risk; equal endowment; auction allocation; **mission economies**. →
Frontier = an **impermeable mission economy** over the register; credit attaches to **reviewed
evidence**, never to passing an automated check.

---

## 3. Constraint solvers + Lean interoperability (P0): where it bites, where it is decoration

**Executable constraints** — each a predicate returning `PASS` or the first violated inequality with
its witnessing number; each shipped with a paired mutant that *must* fail. These are already
implemented in codex-03's checker (`messages/flying-fish-checker.md`, 8 constraints, 71 tests) and the
guilds solver (`6612af6`) — **this note does not re-derive or duplicate them**; it records which are
executable and feeds the source cards their parameter locators.

- **C1** `WL=Mg/S ≤ 209 N/m²`; **C2** `V ≥ 16·√(WL/205.5)` m/s; **C3** `pectoral length ≤ 0.79·SL`;
  **C5** pectoral-fin AR `3.0 ≤ AR ≤ 16.9` (**individual pectoral fin**, Fish 1990 p.395; `16.9–19.9`
  band undetermined — §4c); **C6b** `max length ≤ 0.50 m`; **C6c** no gliding stage below ~0.05 m.

These six are elementary arithmetic over rationals — a trivial CSP (Z3) that Lean closes with
`norm_num`/`decide`. They test whether a design's own numbers fall inside **provenance-scoped
empirical envelopes**; leaving an envelope raises an engineering question and demands a stated
mechanism — it is **not** a universal infeasibility verdict, and the goal is the next measurement, not
a pass/fail gate. **Lean also bites on model-class lemmas** — the jaw-joint `LoadScaling.lean`
proves each growth law is positively homogeneous of degree one, so uniform load scaling cannot
separate two laws tuned on a linear feature: a real theorem, true for all loads.

**Where Lean is decoration:** C4 (no numeric CG was retrieved in the sources read, and Saro-Cortes 2022 +
Park & Choi 2010 show longitudinal stability is configuration-dependent and trades against lift — so C4
is qualitative-with-witness, narrower than a static CG-sign; the *Oxyporhamphus* refutation still holds); any constraint whose inputs are unsourced (max body mass as a physical limit, the
400 m glide, quantified predator-escape pressure). **Lean over an empirical assumption surfaces the
assumption; it does not make it true.** That is its correct, modest role.

**Heed the Lean pre-run review** (`messages/codex-active-frontier-and-lean-review-ready.md`): the
current experiment accepted a frozen `False` after a helper added an extra `False` assumption
(`False → False`, clean axiom audit) — *target weakening*, not a contradiction. P0 interop must (i)
state each constraint as a concrete inequality over the design's own numbers, never a vacuous
implication; (ii) ship the paired must-fail mutant; (iii) pin the toolchain and preregister. spec005's
"Solver and Lean boundary" §1–5 already says exactly this (satisfiable/unsat/unknown/timeout not
collapsed; certificate + a mutant that fails; "no blanket Lean-verified biology").

---

## 4. Models, transfer, and the AR contradiction

### 4a. BioModels + the jaw-joint model class — retrievable, replayable, non-transferring
Tiwari et al. 2021 (PMC7901289, open access) labelled **455 ODE BioModels** at
`ebi.ac.uk/biomodels/reproducibility` (parsed, 455 rows): **R 233, NRP 169, RMC 40, RAH 13** — a
library of replayable ODE models and a measured base rate (~half replay as deposited). Connector
lesson: `zenodo.org/api/records/5786693` → 403, but the paper's own data-availability sentence names
the EBI URL that serves the rows. The zebrafish jaw-joint deposit **Zenodo 7586155** (not in
BioModels) **replays** (workbook recomputes to 2e-16; `LoadScaling.lean`). **Parameters do not
transfer to a fin:** wrong organism/tissue (jaw cartilage modulus from nanoindentation ≠ fin-ray
lepidotrichia), wrong BCs (joint point-loads ≠ cantilevered aerofoil), wrong load spectrum (~57k jaw
openings ≠ launch+glide). The **model class and method** transfer; the **parameters** are a
cross-scale `[GAP]`. **No BioModels entry couples to any flying-fish scale.**

### 4b. The molecule→form candidate (Daane 2021) — what it shows and what it does NOT
Cited source claim (`full-text`, NOAA repository PDF 47 pp, + Europe PMC `abstract`; non-OA — short quote
briefly, attribute): phylogenomics across **35 species** of flying fishes and relatives found coding
+ regulatory signatures for **convergently increased paired fin size**; intersecting with zebrafish
fin-size mutants identified **`lat4a`** (L-type amino-acid transporter) and **`kcnh2a`** (K⁺ channel);
their **interaction in zebrafish phenocopies flying-fish fin proportion** ("a combination of alleles
from both genes is sufficient to reproduce the flying fish fin bauplan in the distantly related
zebrafish"); `kcnh2a` ectopic expression is sufficient to drive fin overgrowth; 48/17,937 genes show
convergent rate shifts; >300,000 loci sampled. **This is a molecule→organ(fin-proportion) candidate
bridge via bioelectric + amino-acid-transport signaling — NOT flight.** The functional test is in
**zebrafish**; the exocoetid side is **association** (phylogenomic signatures), not an exocoetid
functional experiment. Numeric fin-ratio values live in figures I could not parse — recorded as a
measurement open problem (`FF-Q09`). This is the evidence that makes "precursor-inspired" forms a
*modern hypothesis*, not merely a Darwinian metaphor (§6).

### 4c. The aspect-ratio definition, reconciled against the readable primary
Fish 1990 (p.394) defines AR generically as `wing span² / wing area`, but the measured range
**3.0–16.9 is of INDIVIDUAL PECTORAL FINS** (p.395: "The aspect ratios (AR) of individual flying fish
pectoral fins range from 3.0 to 16.9"); Table III lists *Exocoetus* to **19.9**. Park & Choi's
**9.0–10.7 is the same quantity** (pectoral-fin AR), corroborating it — **not** a second definition.
The real cautions are therefore: (i) text 16.9 vs Table III 19.9 is unresolved (the checker returns
**CANNOT-EVALUATE** in `16.9 < AR ≤ 19.9`); and (ii) applying the **pectoral-fin** AR bound to a
candidate's **whole-wing** `b²/S` (pectoral+pelvic+body, the area used for WL) is a **flagged
modelling choice** (guilds "correspondence"), not an identity — the denominators differ. spec005's
`Constraint` must carry the exact definition, the band, and the correspondence flag. (Re-read from the
Fish 1990 PDF this session + guilds' primary re-read, not imported memory.)

---

## 5. Connector candidates — actual access/replay state (verified 2026-10-31)

State per spec005 `Connector`: **validated** (deterministic artifact recomputed), **replayed** (parsed
here), **retrieved** (fetched, read), **accessible** (reachable), **discovered** (named only).

| Connector | State reached | How verified | Scale |
|---|---|---|---|
| NCBI Datasets v2alpha / E-utilities | retrieved | API read (Exocoetidae = 1 assembly; SRA 53; nuccore 1,489) | molecular |
| EBI ENA `browser/api/fasta` | validated | FASTA pulled + bp count matched (cavefish chr5) | molecular |
| Fish Tree of Life `.tre.xz` | replayed | decompressed, parsed 11,638 tips | evolution |
| FishBase species HTML | replayed | scraped 116 names, parsed 69 max-lengths | organism |
| rOpenSci `fishbase.ropensci.org` | **dead** | curl exit 000; 4 control hosts 200 | organism |
| BioModels `.../reproducibility` | replayed | 455 rows parsed; counts match paper | tissue/cell (ODE) |
| Europe PMC `search` JSON | retrieved | Daane abstract + metadata (isOA=N, inPMC=Y) | all (lit) |
| Europe PMC `fullTextXML` | **accessible (500 for non-OA)** | PMC9172250 → HTTP 500; OA records serve XML | all (lit) |
| `r.jina.ai` public proxy | retrieved | Daane full text (127 KB); Darwin variorum (403→recovered) | all (lit) |
| Zenodo records API | retrieved/replayed | jaw-joint 7586155 readable; 5786693 → 403 | tissue/cell |
| SSRN `Delivery.cfm` | retrieved | ASK PDF + sha256 | method |
| Crossref/OpenAlex/Semantic Scholar | retrieved | DOI confirmation | identity |
| `shenoy.engineering.upenn.edu` | retrieved (via fetch) | mission + 4 research areas | method |
| arXiv `2509.10147` | discovered | search-summary | coordination |

**Bounded raw-morphometrics search (deliverable 3), 2026-10-31 UTC** — queries + per-repo results in
`../../data/research/README.md`. Short form: **Dryad** `Exocoetidae` → 0 (the one `flying fish
morphometrics` hit is a bird-blowfly dataset); **Zenodo** `Exocoetidae` → 353, **all taxonomic
treatments**, no per-specimen fin-area×mass; **Figshare** `search_for=Exocoetidae` → unrelated
results (**inconclusive, not a clean negative**); **MorphoBank** API → **403, not accessed**. Result:
**no downloadable per-specimen paired pectoral-fin-area + body-mass dataset found on those four
repositories on that date** — searched-not-found, **not** universal absence. This is the highest-value
remaining search; raw data would move the organ→organism coupling from `[FIT/EMP]` to `[EXEC]`.

---

## 6. External research inputs (implementation grade, not accepted)

- **Shenoy lab — multiscale mechanobiology** (`shenoy.engineering.upenn.edu`, **via fetch tool**):
  *"coupling of both small-scale (nucleus, cell) phenomena and long-range (tissue, organ)
  interactions,"* µm–cm, multiphysics continuum/mesoscale. → the §1 scale ladder and the
  transferable-structure / organism-specific-parameter split (§4a). Director's ruling stands: **no
  GPU/inference for Frontier before a source-linked bounded protocol exists.** Nothing here runs one.
- **Virtual Agent Economies** (arXiv `2509.10147`, `search-summary`) → §2.5 (impermeable mission
  economy; reviewed-credit, not paying-check credit).
- **Biology agent-economies**: "Agentic Science" survey (arXiv `2508.14111`, `listing`), Argonne
  cooperative-federation vision (arXiv `2510.13081`, `listing`); other items' arXiv IDs the search
  flagged date-unverifiable — **leads only, not cited**.
- **Modern precursor hypotheses (lead for the narrative, before any Darwin expansion):** the living
  **halfbeak** grade and the "non-flying flying fish" ***Oxyporhamphus*** are the real extant
  reference forms; Daane 2021's bioelectric fin-proportion mechanism is the modern, *testable*
  statement of "how a bigger paired fin is made" that a precursor-inspired design should cite —
  **with no flight claim attached.**

---

## 7. What I would hand spec005 as normative, and what to keep out

**Normative-ready (executable):** C1,C2,C3,C5,C6a–c as arithmetic predicates with paired mutants
(already in the checker); the units-typed `Parameter` (§2.3); the ASK→primitive map (§2.4); the
`Connector` state vocabulary (§5); the impermeable-mission-economy + reviewed-credit rule (§2.5).

**Keep out of normative (claim / gap, visible as such):** C4 as anything but qualitative-with-witness;
the Daane genetics as a **sourced claim about fin proportion, never flight or an exocoetid functional
result**; any tissue/cell/molecule→exocoetid-fin coupling (unbuilt bridges); transfer of jaw-joint or
BioModels parameters to a fin; the 400 m glide and quantified predator-escape pressure; any
GPU/inference step. **No domain impossibility is asserted anywhere** — only bounded, dated absences.
