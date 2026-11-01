# SPEC-012 — Genetic implementation blueprints across scales

Status: user-directed design and implementation layer, October 31, 2026.
Blueprints are versioned proposals linked to evidence, not demonstrated organisms.

## Required design object

Use existing Project, Claim, Problem, Action, Evidence and Artifact records. A
blueprint artifact must connect desired function → organ geometry/material →
cell behavior → target cell state → regulatory program → construct/carrier →
delivery and maintenance → observable validation. A missing link is a first-class
Problem, never an invented coefficient or sequence.

Each version records parent, species/strain, genome/annotation assembly, tissue,
cell state, developmental or regenerative stage, spatial domain, desired timing
and dosage, target and off-target expression, source/read depth, model assumptions,
candidate alternatives, measurements needed and exact artifact/record references.

Keep these engineering choices separate:

| Layer | Required content and evidence boundary |
| --- | --- |
| Regulation | Enhancer, promoter compatibility, silencers, untranslated regions, termination, chromatin context and optional temporal/intersectional logic. A marker or accessible peak is not automatically a specific driver. |
| Cargo | Reporter/effector role, size and provenance; existing natural sequence or proposed design. Unknown sequences/coordinates are null. Reporter specificity does not establish an effector's phenotype. |
| Carrier | Plasmid, BAC or other construct architecture and capacity in the cited context. A BAC is propagated as a bacterial construct; BAC transgenesis is not an autonomous fish chromosome. |
| Delivery | Which cells receive which material at which stage; delivery evidence, mosaicism and uptake uncertainty. Delivery to a cell does not imply expression or stable maintenance. |
| Integration/maintenance | Transient versus stable, random transposition versus targeted locus/landing site, copy number, locus effects, silencing, inheritance and intended somatic/germline scope. |
| Autonomous chromosome | Separate research option requiring fish-compatible centromere/segregation, replication, dosage, stability and delivery evidence. Mammalian demonstrations do not establish fish feasibility. |
| Validation | Context-matched expression distribution, off-target tissues, mosaicism, burden/viability, lineage/stability and downstream function. Separate discovery data from validation specimens/loci. |

## Quantitative interfaces

Show expression kinetics as an explicit conditional model, for example
`dm/dt = k_tx(c, stage, enhancer, promoter, locus) - gamma_m m` and
`dp/dt = k_tl m - gamma_p p`. Parameter units, provenance and uncertainty are
mandatory; unknown rates stay unknown. This model does not infer `k_tx` from a
sequence or predict cell fate by itself. Chromatin accessibility, RNA, protein,
activity and phenotype remain separate observables.

Keep proposed bridges explicit: expression → membrane abundance/conductance;
voltage/transport → proliferation; cell state → matrix/mineral deposition;
deposition → ray geometry/modulus; geometry/material → flight mechanics. An
expression slider cannot silently become a fin-length or flight-speed slider.
Lean/solver checks may constrain units, ranges, construct compatibility and
declared model consequences. They cannot prove unmeasured biological premises.

Cell specificity needs a declared target population and comparison populations,
stage, assay threshold and biological replicate structure. Report coverage and
off-target distributions; do not equate specificity with average target signal.
Cell counts are not independent animal replicates. Context-mismatched datasets
cannot be joined by gene names alone or without assembly/orthology checks.

## First implementation and acceptance checklist

- [ ] Three or more source-backed proposals spanning fin mesenchyme/ray cells,
  epithelium and a neural/muscle observation interface. Marker candidates are
  labeled identification aids until driver activity is supported.
- [ ] Compare plasmid/Tol2, BAC, endogenous-locus targeting and landing-site
  approaches with transient delivery and autonomous chromosome research options.
- [ ] Include a reporter-first regulatory characterization step and separate
  causal perturbation/phenotype gates; a reporter alone cannot complete the design.
- [ ] Readable construct block diagrams, alternatives, target/off-target cell
  context and validation gates in Studio; source, equation and artifact drill-down.
- [ ] Machine-readable blueprints with provenance, explicit unknowns and revisions;
  source Claims and proposed Actions available through existing Frontier surfaces.
- [ ] Evidence/uncertainty visible at every bridge, including organism feasibility.
  No generated sequence, model call, experiment or successful expression is
  counted unless there is its corresponding execution/measurement receipt.

The first data package is `artifacts/genetic-blueprints/blueprints.json` (owner
claude-14); site integration belongs to claude-02. Reuse the regulatory map and
metadata coverage audit. Previously provider-stopped Evo2 work remains stopped;
this blueprint work is not authorization to reroute or replay it.

## Source anchors

- [Fin multiome study](https://genome.cshlp.org/content/35/1/202): measured adult
  caudal regeneration, distinct from embryonic paired-fin development.
- [Enhancer–promoter compatibility](https://pmc.ncbi.nlm.nih.gov/articles/PMC10211259/):
  primary text available; compatibility is a design variable, not an assumed wire.
- [BAC transgenesis](https://pmc.ncbi.nlm.nih.gov/articles/PMC4825653/): indexed
  primary abstract; full-text fetch was challenged and needs public-mirror recovery.
- [pIGLET](https://pmc.ncbi.nlm.nih.gov/articles/PMC11152119/): primary indexed
  results on zebrafish landing sites; detailed applicability review pending.
- [Single-copy human artificial chromosomes](https://pmc.ncbi.nlm.nih.gov/articles/PMC11059994/):
  primary indexed results in human cells; fish implementation is an open problem.
- [Evo2](https://www.nature.com/articles/s41586-026-10176-5): previously read
  Fig. 6 chromatin-design results; fish expression and phenotype are not established.
