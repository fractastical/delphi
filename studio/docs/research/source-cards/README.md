# Source cards — Frontier multiscale substrate

Cards for every source and connector behind `../frontier-multiscale-substrate.md`. One card = one
source, with its **read-level**, **primary URL / identifier**, **access & replay status**, the
**scale** it serves, what it supports, and a caveat. Read-levels: `full-text` | `abstract` |
`listing` | `search-summary` | `could-not-access`; **via fetch tool** marks a page read through
`WebFetch` (separate small model). Verified 2026-10-31 Seattle PDT unless noted.

**Single-reader (fable-lead), NOT Codex-reviewed.**

---

## A. Organism / organ scale — biomechanics (executable constraints live here)

### A1. Fish, F. E. (1990) — Wing design and scaling of flying fish
- **Cite:** *J. Zool. Lond.* 221: 391–403. **Primary URL:** author copy at West Chester Univ.
  (`health-sciences.wcupa.edu/.../1990JZWing design.pdf`, HTTP 200, 368 KB).
- **Read-level:** `full-text` (PDF extracted and read directly).
- **Access/replay:** read-only; numbers are r.m.a. coefficients, not raw specimen data.
- **Scale:** organism + organ. **Supports:** C1 (WL ≤ 209 N/m², n=199/33 spp/6 genera), C2
  (`V ∝ √WL`, Pennycuick 1972 via Fish), C5 (AR 3.0–16.9), C6 (taxiing launch, 63.1% hypocaudal
  lobe, <0.05 m juveniles do not fly).
- **Caveat:** two internal inconsistencies (AR 16.9 text vs 19.9 Table III; 0.001 vs 0.003 kg min
  mass) — state AR bound as a range. WL excludes ventral body area → biases C1 toward false failure
  for flattened *Cypselurus* bodies. L/D 11.0 is Shoulejkin's **calculation**, not measured.

### A2. Park, H. & Choi, H. (2010) — Aerodynamic characteristics of flying fish in gliding flight
- **Cite:** *J. Exp. Biol.* 213(19): 3269–3279. doi:10.1242/jeb.046052.
- **Read-level:** `full-text, via fetch tool` (two passes over JEB HTML).
- **Access/replay:** read-only; numeric L/D values live only in figures → **could-not-access**.
- **Scale:** organism + organ. **Supports:** independent AR 9.0–10.7 (confirms A1); >20% pelvic-fin
  lift; ground-effect drag reduction (14% water / 9% solid); max lift at α 30–35°.

### A3. Davenport, J. (1992) — Wing-loading, stability and morphometrics in flying fish
- **Cite:** *J. Mar. Biol. Assoc. UK* 72(1): 25–39.
- **Read-level:** `abstract, via fetch tool` (Cambridge Core extract; full text paywalled).
- **Scale:** organ. **Supports:** C3 (pectoral fin ≤ 78–79% SL or swimming impaired); C4 (CG-aft
  instability, **living witness *Oxyporhamphus micropterus***); four-wingers reach larger sizes;
  white-muscle launch.
- **Caveat:** abstract-grade only; no measured CG offset — C4 stays qualitative.

### A4. Davenport, J. (2003) — Allometric constraints on stability and maximum size
- **Cite:** *J. Fish Biol.* 62(2): 455–463. doi:10.1046/j.1095-8649.2003.00041.x.
- **Read-level:** `listing` (Crossref/Semantic Scholar bib confirmed) + `search-summary`. **Wiley
  Cloudflare-blocked** directly and via `r.jina.ai`. **Not read.**
- **Scale:** organism/organ/evolution. **Supports (unverified):** the size-limit stability argument;
  flight from surface-taxiing half-beaks, not ballistic leaps. **The paper the design problem most
  needs at full-text grade — blocker: paywall.**

---

## B. Evolution scale — phylogeny & fossils

### B1. Lovejoy, Iranpour & Collette (2004) — Phylogeny and jaw ontogeny of beloniform fishes
- **Cite:** *Integr. Comp. Biol.* 44(5): 366–377. PMID 21676722.
- **Read-level:** `abstract` (PubMed).
- **Scale:** evolution. **Supports:** C6a — **flyingfishes are nested within halfbeaks**; the
  ancestor is a surface beloniform with an elongated lower jaw. Single most important evolvability fact.

### B2. Xu, Zhao, Gao & Wu (2013) — Earliest over-water gliding vertebrate (*Potanichthys*)
- **Cite:** *Proc. R. Soc. B* 280(1750): 20122261. **Bib verified via Crossref.**
- **Read-level:** `listing` + `search-summary` (press/encyclopedia, not the paper).
- **Scale:** evolution. **Supports:** the four-winger configuration arose **convergently** ~240 Myr
  ago at ~15 cm — the configuration (and roughly the size) is an attractor; modern exocoetids are not
  descended from it. **Not in PubMed** (0 hits); Crossref has it.

### B3. Fish Tree of Life — `actinopt_12k_treePL.tre`
- **Cite:** Rabosky et al. **Primary URL:** `fishtreeoflife.org/downloads/actinopt_12k_treePL.tre.xz`
  (HTTP 200, 169,948 B → 483,035 B Newick).
- **Read-level:** `full-text` — **downloaded, decompressed, parsed**.
- **Access/replay:** **replayable**. 11,638 tips with branch lengths; 38 exocoetid tips
  (*Cheilopogon* 17, *Hirundichthys* 6, *Exocoetus* 4, *Cypselurus* 4, *Parexocoetus* 3, *Fodiator* 2,
  *Oxyporhamphus* 2) + 5 *Hemiramphus*. Medaka (`Oryzias_latipes`) not found under that spelling.
- **Scale:** evolution. **Supports:** C6a reachability — a design is placeable on a time-tree. The one
  dataset both public and immediately machine-readable.

---

## C. Molecule scale — genomes & sequence

### C1. NCBI Datasets v2alpha — Exocoetidae genome report
- **Primary URL:** `.../genome/taxon/Exocoetidae/dataset_report` (API read, 2026-10-31).
- **Read-level:** direct API read. **Access/replay:** read-only, counts confirmed.
- **Scale:** molecule. **Supports:** **the gliders are not sequenced** — `total_count = 1`:
  `GCA_018398805.1` *Hirundichthys speculiger*, **scaffold** level, 1.04 Gbp, contig N50 1.09 Mb,
  2021-05-19. Order Beloniformes = 75 assemblies; Hemiramphidae 11; Exocoetidae **1**. No
  chromosome-level exocoetid genome → comparative exocoetid genomics is unsupportable now.

### C2. NCBI E-utilities — SRA / nuccore
- **Read-level:** direct API read. **Scale:** molecule. **Supports:** SRA 53, nuccore 1,489 (mostly
  barcode/mitochondrial). A 2025 paper (PMID 40135747, `listing`) already mined public SRA for
  exocoetid mitogenomes.

### C3. Astyanax cavefish `oca2` loop (contrast / SOLVE template)
- **Cite:** Warren et al. 2021 *Nat Commun* (PMID 33664263, Europe PMC `fullTextXML`, 167,392 B,
  `full-text`); Protas et al. 2006 *Nat Genet* (PMID 16341223, `abstract` only, subscription).
- **Connectors:** EBI ENA `browser/api/fasta` ✓ (chr5, bp counts matched); NCBI Datasets whole-genome
  ✓ (GCA_023375845.1 Molino). **Access/replay: replayable** (`grep -F` on exact 24-mers, shuffled
  must-fail decoy).
- **Scale:** molecule→organism. **Supports:** a **closed** loss-of-form loop; the contrast that
  flying-fish gain-of-form has no equivalent. Full design in `messages/cavefish-loop.md`.

---

## D. Tissue / cell scale — mechanobiology model class (transfer candidate, parameters do NOT transfer)

### D1. Godivier et al. (2024) — Compressive stress gradients direct mechanoregulation of anisotropic growth in the zebrafish jaw joint
- **Cite:** *PLoS Comput Biol* doi:10.1371/journal.pcbi.1010940, PMC10880962.
  **Deposit:** Zenodo 7586155 (CC-BY-4.0).
- **Read-level:** `full-text` (Europe PMC `fullTextXML`, sha256 recorded); deposit workbook
  `full-text` (every cell of 3 sheets).
- **Access/replay:** **replayable** — workbook recomputes to largest rel. dev. **2e-16**; per-cell
  tracking tables ~0.5 MB, range-readable inside multi-GB archives; `LoadScaling.lean` homogeneity
  lemma. `zenodo.org/api/records/7586155` reachable.
- **Scale:** tissue + cell. **Supports:** the mechanoregulated anisotropic-growth **model class** for
  a skeletal element under cyclic load; one tunable per stimulus; a must-fail null (uniform scaling
  can't rank linear laws).
- **Caveat:** **zebrafish jaw cartilage, not an exocoetid fin.** Parameters (modulus from
  nanoindentation; point-load quasi-static BCs; ~57k jaw openings) do **not** transfer (note §4).
  Naming/unit discrepancies between README, paper, workbook recorded in
  `morphoswarm/.../zebrafish-jaw-joint-mechanoregulated-growth.md`. Cell-level conversion mechanism
  **open even in zebrafish**.

### D2. BioModels reproducibility set (Tiwari et al. 2021)
- **Cite:** *Mol Syst Biol* PMID 33620773, PMC7901289 (open access).
  **Primary URL:** `ebi.ac.uk/biomodels/reproducibility` (HTTP 200, 423,947 B, server-rendered).
- **Read-level:** `full-text` — 455 rows parsed (`scienceclaw/.../biomodels-reproducibility-455.tsv`).
- **Access/replay:** **replayable** index. Labels: **R 233, NRP 169, RMC 40, RAH 13**.
  Connector lesson: `zenodo.org/api/records/5786693` → **403**; the paper's own data-availability
  sentence names the EBI URL that serves the rows.
- **Scale:** tissue/cell (ODE systems biology). **Supports:** a library of replayable ODE models +
  a measured base rate (~233/455 replay as deposited). **No entry couples to any flying-fish scale.**

---

## E. Method / epistemics / coordination sources

### E1. Firat — Active Scientific Knowledge (ASK)
- **Cite:** SSRN DOI `10.2139/ssrn.7416579`. **Primary URL:** SSRN `Delivery.cfm?abstractid=7416579`
  (PDF, sha256 `cc709a9…`, 341,902 B). Local copy in morphoswarm repo.
- **Read-level:** `full-text`.
- **Scale:** method (epistemic/evidence + coordination). **Supports:** the six-dimension Activation
  Test mapped to Frontier primitives (note §2.4); scoring rule *"missing capacities must remain
  visible."* Full analysis: `morphoswarm/docs/research/active-scientific-knowledge-ask-model.md`.

### E2. Shenoy Lab — Multiscale Mechanobiology & Biomaterials
- **Primary URL:** `shenoy.engineering.upenn.edu` (301 from `shenoy.seas.upenn.edu`).
- **Read-level:** `via fetch tool`.
- **Scale:** method. **Supports:** the §1 scale ladder (nucleus→cell→tissue→organ, µm–cm) and the
  transferable-structure / organism-specific-parameter split (note §4/§6).

### E3. Virtual Agent Economies — Tomašev et al., Google DeepMind (2025)
- **Primary URL:** arXiv `2509.10147`.
- **Read-level:** `search-summary` (abstract fragments + mirrors; full PDF not parsed here).
- **Scale:** method (coordination). **Supports:** sandbox economy on origin × permeability;
  impermeable sandbox for higher-risk; equal endowment; auction allocation; **mission economies**
  (note §2.5).

### E4. Contributed compute & federation prior art
- **Primary file:** `morphoswarm/docs/research/contributed-compute-and-federation.md` (`full-text`).
- **Scale:** method (coordination). **Supports:** BOINC/Folding@home redundant verification;
  Petals/Hivemind; nanopub network; **Bittensor caution** — transferable reward incentivises
  fabricating artifacts that pass the paying check. → credit attaches to reviewed evidence (note §2.5).

### E5. Darwin, *Origin of Species* (1859/1860/1872)
- **Primary URL:** Project Gutenberg ids 1228 / 22764 / 2009. **Read-level:** `full-text` (parsed).
- **Scale:** method/framing. **Supports:** the flying-fish passage is a **conceivability argument**
  ("our imaginary illustration"), Chapter VI; Darwin writes "flying-fish", **never "Exocoetus"** in
  these three editions (a one-grep check against fabricated attribution). 1st-ed. page number
  **could-not-access**.

---

## F. Dead / blocked connectors (named with exact failure)

| Connector | Failure | Impact |
|---|---|---|
| `fishbase.ropensci.org` API | curl exit 000 on `/heartbeat` + query; 4 control hosts 200 | any pipeline depending on it is broken; scrape HTML instead |
| `zenodo.org/api/records/5786693` | HTTP 403 | use the paper's named EBI URL (D2) |
| Wiley (Davenport 2003) | Cloudflare "security verification" direct + via `r.jina.ai` | A4 stays `listing`/`search-summary` — the key size-limit paper is unread |
| `darwin-online.org.uk` F373 scan | 403 to WebFetch; image-only PDF, no text layer | 1859 page number uncitable; cite edition+chapter+opening words |
| rOpenSci raw-data pairing (fin area × mass) | no public deposit found (Dryad/Figshare/Zenodo/MorphoBank **not** yet searched by name) | **highest-value remaining search**; would move organ→organism from [EMP] to [EXEC] |
