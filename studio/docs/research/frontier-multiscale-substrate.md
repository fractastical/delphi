# Frontier multiscale substrate: what the sources and tools actually support

**Status:** research note (implementation-focused) · **Owner:** fable-lead · 2026-10-31 Seattle PDT
**Branch:** `work/frontier-specs` · writes under `docs/research/` only.
**Supports, does not write:** this note is input for **Root's normative `spec005`**. It states what
is retrievable, replayable, and executable *today*; the spec decides what is normative. Nothing here
is a de novo biology result.
**Reviewer status:** **single-reader (fable-lead), NOT Codex-reviewed.** Treat as a careful first
reading, not as accepted.

**Read-level key** (same convention as the flying-fish report and `morphoswarm/docs/research`):
`full-text` | `abstract` | `listing` | `search-summary` | `could-not-access`. Pages read through
`WebFetch` are marked **"via fetch tool"** — that tool answers a prompt against the page *with a
separate small model*, so its quotes are a weaker grade than text parsed directly.

---

## 0. The one finding that should shape spec005

**Flying fish is actionable at the organism / organ / evolution scales and unsolved at the
tissue / cell / molecule scales. Every cross-scale coupling below the organ is an open gap, not a
model we can replay.** The biomechanics and phylogeny are measured numbers and a downloadable
time-tree; the fin's development, its material properties, the cells that build it, and the genes
that enlarge it are — for exocoetids specifically — absent or single-sample. So `spec005` can make
the **organism-scale constraints executable** (arithmetic over declared numbers, C1–C6 below) and
must record **everything subcellular as an empirical assumption or an explicit cross-scale gap**,
never as a checked coupling. This is the same discipline the ASK paper calls "missing capacities
must remain visible" (§4).

The contrast that makes the point: the **cavefish `oca2` exon-21 loop is closed** molecule→organism
on public assemblies (`messages/cavefish-loop.md`) — a deletion you can find with `grep -F` on exact
24-mers, with a positive control and a must-fail decoy. The flying-fish gain-of-form direction has
**no equivalent closed molecular loop** and, with one scaffold-level genome for the whole family,
cannot acquire one from comparative genomics now.

---

## 1. The multiscale coupling map for flying fish

Scales after the Shenoy lab's own ladder — *"coupling of both small-scale (nucleus, cell) phenomena
and long-range (tissue, organ) interactions,"* micrometres to centimetres (homepage, **via fetch
tool**, 2026-10-31) — extended down to molecule and up to evolution, which is the axis the design
problem actually spans.

Legend: **[EXEC]** a constraint computable from declared numbers (→ constraint solver / Lean).
**[EMP]** an empirical assumption (sourced measurement, but not a checkable inequality on a design).
**[GAP]** a cross-scale coupling with no retrievable/replayable data for exocoetids. Source cards for
every row are in `source-cards/`.

| Scale | What is actionable now | Connector / model | Executable vs empirical | Coupling to next scale down |
|---|---|---|---|---|
| **Evolution** | Flyingfishes nested **within** halfbeaks; 38 exocoetid tips on a time-calibrated tree; convergent Triassic four-winger (*Potanichthys*) | Fish Tree of Life `.tre` (downloaded, parsed, 11,638 tips); Lovejoy 2004 (`abstract`); Xu 2013 (`listing`+`search-summary`) | **[EXEC]** C6a reachability: ancestor is a surface beloniform with an elongated lower jaw, not a generic fish — a design is placeable on the tree | organism ← evolution: **solved enough** (the ancestor is identified) |
| **Organism** | Wing loading 11.7–208.9 N/m²; AR 3.0–16.9; launch 10→16–20 m/s; family stops at 50 cm | Fish 1990 (`full-text`); Park & Choi 2010 (`full-text, via fetch`); Davenport 1992/2003 (`abstract`/`listing`); FishBase (scraped, 69/116 max-lengths); NCBI genome report | **[EXEC]** C1, C2, C5, C6b. **[EMP]** predator-escape pressure — 167 yr old, **never quantified**; do not threshold on it | organ ← organism: the body-scale number *is* a sum of organ contributions (pectoral 76–92% of wing area), so this coupling is **measured** |
| **Organ** (the fin/wing) | Pectoral fin ≤78–79% SL; CG-vs-centre-of-pressure stability; hypocaudal lobe = 63.1% launch motor; pelvic fins add >20% lift | Davenport 1992 (`abstract`); Fish 1990 (`full-text`); Park & Choi 2010 (physical-model lift) | **[EXEC]** C3 (fin-length geometry). **[EMP]/witness** C4 (qualitative, living witness *Oxyporhamphus*; **no measured CG offset** for any exocoetid) | tissue ← organ: **[GAP]** no measured map from fin-ray geometry + material to the organ-scale AR under growth |
| **Tissue** (lepidotrichia, cartilage, white muscle) | *Model class only*: mechanoregulated anisotropic growth under cyclic load | **Transfer candidate**, not exocoetid: zebrafish jaw-joint deposit (Zenodo 7586155, workbook recomputes to 2e-16; `LoadScaling.lean`) | **[GAP]** the model class transfers; **the parameters do not** (see §4) | cell ← tissue: **[GAP]** — the jaw-joint paper itself leaves the cell-level conversion mechanism open, in zebrafish; for exocoetids there is no data at all |
| **Cell** (chondrocyte / osteoblast orientation) | *Nothing exocoetid.* The generic question — how a cell converts a mechanical stimulus to oriented growth — is open even in the model organism | — (jaw-joint per-cell tables exist for zebrafish, ~0.5 MB, range-readable) | **[GAP]** | molecule ← cell: **[GAP]** |
| **Molecule** (genes enlarging paired fins) | One scaffold genome for the whole family; no comparative set; no candidate locus for fin enlargement | NCBI `GCA_018398805.1` *Hirundichthys speculiger* (scaffold, confirmed); SRA 53, nuccore 1,489 | **[GAP]** — contrast cavefish `oca2` exon-21, a **closed** molecule→organism loop | — |

**Reading for spec005:** the normative constraints live at the top three rows and are arithmetic.
The bottom three rows are where the register's "actionable" flag must stay *off* for any flying-fish
design claim that reaches below the organ — there is no evidence to review, so a claim there is a
curator statement, not a field-level open problem (the same distinction the register correction
drew: 148/250 unsourced are curator statements, not sourced open problems).

---

## 2. The substrate architecture, mapped to real sources and store primitives

The user named five layers the substrate must cover. Each is mapped to (a) a concrete connector or
tool that exists, and (b) the Frontier store primitive that already carries it (SPEC-001..004).

### 2.1 Data connectors / indexes
Retrieval surfaces with **verified** access/replay status (full table + how-verified in §5):
NCBI Datasets v2alpha ✓, NCBI E-utilities ✓, EBI ENA FASTA ✓, Fish Tree of Life ✓ (parsed),
FishBase HTML ✓ (scraped) / rOpenSci `fishbase.ropensci.org` **✗ dead**, BioModels reproducibility
index ✓ (served HTML) / `zenodo.org/api` **403**, Europe PMC `fullTextXML` ✓, Zenodo records API ✓
+ HTTP range reads ✓, SSRN delivery ✓, Crossref / OpenAlex / Semantic Scholar ✓ (bibliographic).
**Store primitive:** the content-addressed version store *is* the index; typed edges + `neighborhood`
are the graph; `source` provenance on each record is where a connector URL + read-level belongs.

### 2.2 Tools + skills
The reusable bounded procedures already demonstrated: the read-level discipline itself; the
`WebFetch` "separate small model" caveat; `systemd-run --user --scope` bounding; the cavefish
`grep -F` exact-24-mer matcher with a shuffled must-fail decoy; a FASTA exon extractor; a FishBase
max-length parser; a Newick parser. **Store primitive:** a skill is an `Action.code` value, and its
exact environment is pinned in the eight-dimension `cache_key` (`code`, `environment`, `parameters`).
A skill with a paired must-fail control is the unit `spec005` should require.

### 2.3 Parameters + units
Every measured quantity here carries a unit and most carry a source fit, not a bare number:
`WL` N/m², `V` m/s, `M` kg, `SL` m, `AR` dimensionless; Fish 1990's `WL = a·M^b` with `a` in N/m²
and `M` in kg per genus; the jaw-joint laws' `a = 3e9 m²N⁻¹s⁻¹`, `b = 5e10 m³N⁻¹s⁻¹`. **This is the
layer where executable and empirical divide:** a parameter with a sourced measurement *and* a unit
is checkable; one with neither (a CG offset for C4, a maximum body mass) is an assumption. **Store
gap for spec005:** `Action.parameters` is today a free string inside `cache_key` (SPEC-003 open
question 2). spec005 should make it **units-typed**, so "stop" and "check" are machine-readable
rather than prose.

### 2.4 Epistemic / evidence layer — ASK's six dimensions already have store homes
Firat's ASK model (SSRN `10.2139/ssrn.7416579`, `full-text` via `morphoswarm/docs/research`) supplies
a conformance test whose six dimensions map **one-to-one** onto Frontier primitives — which is the
strongest argument that the store is the right substrate and not a diagram:

| ASK dimension | Frontier primitive (spec) |
|---|---|
| Addressability | per-record `version = sha256(canonical)` (SPEC-001) |
| Evidential traceability | typed edges + append-only `events` (SPEC-001/002) |
| Conditional executability | `Action` + eight-dim `cache_key` + `acceptance_policy` (SPEC-003) |
| Version responsiveness | `predecessor`/`heads`, status **per exact version** (SPEC-001/002) |
| Context-preserving transferability | bundles that set `imported_unreviewed` and never grant authority (SPEC-004) |
| Contestable federation | fork-on-conflict + `disputed` as a first-class edge (SPEC-002/004) |

ASK's scoring rule — *"missing capacities must remain visible"* — **is** the refusal discipline, and
the read-level + confidence grade on every source card is its metadata. The seven Assessment
dimensions (SPEC-002) are the review instrument; `computational_replay_formal_check` is exactly where
a Lean or solver verdict lands.

### 2.5 Coordination / multiparty open science
Store primitives: atomic leases (don't-pay-twice), independent review (executor operator ≠ reviewer
operator), bundles + fork-on-conflict (federation with no central authority), digest = integrity,
**not** signature/timestamp/acceptance. Prior art already surveyed in
`morphoswarm/.../contributed-compute-and-federation.md`: BOINC / Folding@home (redundant
verification), Petals/Hivemind, the nanopublication network, and **Bittensor — whose transferable
reward creates a direct incentive to fabricate artifacts that pass the paying check** (avoid tying
credit to an automated gate). The **Virtual Agent Economies** paper (Google DeepMind, arXiv
`2509.10147`, `search-summary`) frames the design space as *origin × permeability* and argues for an
**impermeable sandbox first** for higher-risk sectors, equal per-agent endowment so compute-wealth is
not an unearned advantage, and **"mission economies"** that steer agents to a collective goal — which
is what the open-problem register is. The implementation reading: Frontier's agent economy should be
**impermeable** (coordination tokens buy leases and reviews, nothing transferable), and credit must
attach to **independently reviewed evidence**, never to passing an automated check.

---

## 3. Constraint solvers + Lean interoperability (P0): where it bites, where it is decoration

**Executable constraints** (each is a predicate returning `PASS` or the first violated inequality
with its witnessing number; each must ship with a paired mutant that *must* fail):

- **C1** `WL = Mg/S ≤ 209 N/m²` — witness: the computed `WL`.
- **C2** `V ≥ 16·√(WL/221)` m/s — witness: a declared launch speed below the bound.
- **C3** `pectoral fin length ≤ 0.79·SL` — witness: the ratio.
- **C5** `3.0 ≤ AR = b²/S ≤ 16.9` — witness: the AR.
- **C6b** `max length ≤ 0.50 m` — witness: the declared length vs the 69-species extant envelope.
- **C6c** no gliding stage below ~0.05 m body length — witness: a hatchling-glide claim.

These six are **linear/elementary arithmetic over rationals**: a trivial CSP that an SMT solver (Z3)
discharges and that Lean closes with `norm_num`/`decide`. **This is where Lean bites.** It also bites
on **structural lemmas about a model class** — the jaw-joint `LoadScaling.lean` proves each growth law
is positively homogeneous of degree one, so a uniform load scaling cannot separate two laws tuned on a
linear feature. That is a real theorem, provable once, true for all loads.

**Where Lean is decoration:**
- **C4** (CG vs centre of pressure) — no measured CG offset exists for any exocoetid; encoding it in
  Lean states the *form* of the condition but proves nothing about a design. Keep it qualitative,
  with the living witness *Oxyporhamphus*.
- Any constraint whose inputs are unsourced (a maximum body mass as a physical limit, the 400 m
  glide, predator-escape pressure). **Lean over an empirical assumption makes the assumption
  explicit; it does not make it true.** That is its correct, modest role: surface the assumption, do
  not launder it.

**Heed the Lean pre-run review** (`messages/codex-active-frontier-and-lean-review-ready.md`): the
current experiment accepted a **frozen `False` after a helper added an extra `False` assumption**
(elaborated type `False → False`, clean axiom audit) — *target weakening*, not a contradiction. The
P0 interop must therefore (i) state each constraint as a **concrete inequality over the design's own
numbers**, never a vacuous implication; (ii) ship the **paired must-fail mutant** beside it; (iii)
**pin the toolchain** and preregister. Only then does the `computational_replay_formal_check`
dimension have something real to assert.

---

## 4. BioModels — what retrieves and replays, and why the parameters do not transfer

**Retrievable + labelled for replay.** Tiwari et al. 2021 (*Mol Syst Biol*, PMC7901289, open access)
curated **455 ODE models** in BioModels with reproducibility labels, served at
`ebi.ac.uk/biomodels/reproducibility` (HTTP 200, parsed, 455 rows;
`scienceclaw/.../biomodels-reproducibility-455.tsv`). Label counts: **R 233** (reproducible),
**NRP 169** (not reproducible as published), **RMC 40** (reproducible with minor changes),
**RAH 13** (reproducible only with author help). So roughly **half (233/455) of published ODE
systems-biology models replay as deposited** — a usable library of *replayable artifacts* and a
measured base rate for "conditional executability." Note the connector lesson recorded in that file:
`zenodo.org/api/records/5786693` returns **403**, but the paper's own data-availability sentence
names the EBI URL that serves the rows — reading the paper beat three fetch attempts.

**Replayable and directly relevant to the tissue→organ coupling** (but **not** in BioModels): the
zebrafish jaw-joint deposit **Zenodo 7586155** (CC-BY-4.0). Its growth-law workbook **recomputes from
its own named values to a largest relative deviation of 2e-16**, the per-cell tracking tables are
~0.5 MB (range-readable inside multi-GB archives), and a `LoadScaling.lean` proves the homogeneity
lemma. This is the closest thing to a replayable mechanobiology model of a skeletal element growing
under cyclic mechanical load.

**Why the parameters do not transfer to a flying-fish fin:**
1. **Wrong organism and tissue.** The modulus comes from **nanoindentation of zebrafish larval jaw
   cartilage**; a fin ray (lepidotrichia, mineralised collagen) is a different material. No exocoetid
   fin modulus exists.
2. **Wrong boundary conditions.** The jaw model is quasi-static point loads on linear-elastic isotropic
   cartilage with a soft interzone — a joint, not a cantilevered aerodynamic surface under lift.
3. **Wrong load spectrum.** The jaw's stimulus is ~57,000 jaw openings over 12 h; a fin's relevant
   load is launch thrust + glide lift, unmeasured.
4. **What *does* transfer is the model class and the method** — a mechanoregulated anisotropic-growth
   law with one tunable per stimulus, a replayable workbook, a must-fail-style null (uniform scaling
   cannot rank linear laws), and a Lean homogeneity lemma. spec005 can adopt the **shape**; it must
   mark the **parameters** as a cross-scale `[GAP]` for exocoetids.

**No BioModels entry couples to any flying-fish scale.** Any claim that a retrieved ODE model predicts
a fin or a glide would be a false transfer.

---

## 5. Connector candidates — actual access and replay status (verified 2026-10-31)

Replay status: **replayable** = fetched *and* a deterministic artifact recomputed/parsed here;
**read-only** = fetched and read, no recompute; **dead/blocked** = named with its exact failure.

| Connector | Access | How verified | Replay status | Scale served |
|---|---|---|---|---|
| NCBI Datasets v2alpha `genome/taxon/.../dataset_report` | ✓ 200 | API read, 2026-10-31 | read-only (counts confirmed: Exocoetidae = 1 assembly) | molecule |
| NCBI E-utilities (SRA/nuccore/PubMed) | ✓ 200 | API read | read-only (SRA 53, nuccore 1,489) | molecule |
| EBI ENA `browser/api/fasta` | ✓ 200 | FASTA pulled + bp count matched NCBI (cavefish chr5) | **replayable** | molecule |
| Fish Tree of Life `actinopt_12k_treePL.tre.xz` | ✓ 200 | downloaded, decompressed, **parsed 11,638 tips** | **replayable** | evolution |
| FishBase species HTML | ✓ 200 | scraped 116 names, parsed 69 max-lengths | **replayable** (scrape) | organism |
| rOpenSci `fishbase.ropensci.org` API | **✗ dead** | curl exit 000 on `/heartbeat` + query; 4 control hosts 200 | — | organism |
| BioModels `ebi.ac.uk/biomodels/reproducibility` | ✓ 200 | served HTML parsed, 455 rows, label counts match paper | **replayable** (index) | tissue/cell (ODE) |
| `zenodo.org/api/records/<id>` | ✗ 403 (some) / ✓ (jaw-joint) | 5786693 → 403; 7586155 → readable + range reads | **replayable** where reachable | tissue/cell |
| Europe PMC `fullTextXML` | ✓ 200 | XML pulled + sha256 recorded (cavefish, jaw-joint) | **replayable** | all (literature) |
| SSRN `Delivery.cfm` | ✓ 200 | PDF pulled, sha256 recorded (ASK paper) | read-only | — (method) |
| Crossref / OpenAlex / Semantic Scholar | ✓ 200 | bibliographic confirmation (DOIs, no abstracts for some) | read-only | — (identity) |
| `shenoy.engineering.upenn.edu` | ✓ (301→) | **via fetch tool**; mission + 4 research areas | read-only | — (method) |
| arXiv `2509.10147` (Virtual Agent Economies) | ✓ | `search-summary` (abstract fragments + mirrors) | read-only | — (coordination) |

**Highest-value remaining search** (unchanged from the flying-fish report): a Dryad / Figshare /
Zenodo / MorphoBank deposit pairing **pectoral fin area with body mass** for exocoetids. Fish 1990
measured exactly that on 199 specimens but published only r.m.a. coefficients; raw data would move the
organ→organism coupling from [EMP] fits to [EXEC] per-specimen check.

---

## 6. External research inputs (implementation grade, not accepted)

- **Vivek Shenoy lab — multiscale mechanobiology** (`shenoy.engineering.upenn.edu`, **via fetch
  tool**). Mission: *"developing theoretical concepts and numerical methods to understand the basic
  principles"* of the *"coupling of both small-scale (nucleus, cell) phenomena and long-range
  (tissue, organ) interactions,"* µm–cm, via multiphysics continuum / mesoscale theories. Four areas:
  mechanobiology of the cell microenvironment, of tissue, of the cell, of the nucleus. **Implementation
  reading:** this is the scale ladder of §1 and the justification for a units-typed parameter layer
  (§2.3); it is also a warning — Shenoy-grade models are *continuum theories with transferable
  structure but organism-specific parameters*, exactly the transfer/no-transfer split of §4. Director's
  standing ruling still holds: **no GPU and no inference job for Frontier before a source-linked,
  bounded protocol exists.** Nothing here proposes running one.
- **Virtual Agent Economies** (Google DeepMind, arXiv `2509.10147`, 2025, `search-summary`): sandbox
  economy on *origin × permeability*; impermeable sandbox for higher-risk work; equal endowment;
  auction allocation; **mission economies**. → §2.5: Frontier = an impermeable mission economy over the
  register; credit attaches to reviewed evidence, not to a paying check (the Bittensor lesson).
- **Biology agent-economies**: the search surfaced an "Agentic Science" survey (arXiv `2508.14111`,
  `listing`), an Argonne cooperative-agent-federation vision (arXiv `2510.13081`, `listing`), and
  ScienceClaw+Infinite / Agentic-Economies items whose arXiv IDs the search engine itself flagged as
  **date-unverifiable** — **not cited as evidence**; recorded as leads only. A biology-specific agent
  *marketplace* paper was **not** confirmed to exist at primary grade.

---

## 7. What I would hand spec005 as normative, and what to keep out

**Normative-ready (executable):** C1, C2, C3, C5, C6a–c as arithmetic predicates with paired
mutants; the units-typed parameter record (§2.3); the ASK→primitive map (§2.4) as the conformance
frame; the connector table (§5) as the provenance vocabulary; the impermeable-mission-economy +
reviewed-credit rule (§2.5).

**Keep out of normative (empirical / gap):** C4 as anything but qualitative-with-witness; any
tissue/cell/molecule coupling for exocoetids (§1 bottom three rows); any transfer of jaw-joint or
BioModels parameters to a fin (§4); the 400 m glide and quantified predator-escape pressure; any
GPU/inference step. These belong in `spec005` as **Open questions / cross-scale gaps**, visible as
gaps — which is what both ASK and our own register correction require.
