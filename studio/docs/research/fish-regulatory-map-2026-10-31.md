# Fish cell programs and regulatory evidence: applicability map

Status: source-only literature/data applicability review, October 31, 2026. No new
genomic model inference, sequence generation, biological experiment or dataset
reanalysis was performed. Reported experiments below belong to their authors.
The previously provider-stopped Evo2 work remains stopped; this review does not
authorize replay, rerouting or an alternative generation service.

The useful next bridge is **measured zebrafish cell state to a testable regulatory
hypothesis**. None of these sources supplies a whole-organism genome design or a
validated DNA-to-fin-geometry simulator. Accessibility, expression, cell behavior,
matrix properties and adult flight require separate evidence.

## What Evo2 and Pinglay actually established

| Source and location | Evidence reported | Applicability boundary |
| --- | --- | --- |
| [Evo2, Nature 2026](https://www.nature.com/articles/s41586-026-10176-5), Fig. 6e–k; generative epigenomics results; author contributions | Fig. 6 combines Enformer/Borzoi-guided sequence generation with experimental ATAC-seq after genomic integration. Mouse ESC designs produced measured accessibility patterns; human HEK293T/K562 experiments include common and cell-specific patterns. Sudarshan Pinglay and Zachary Amador are credited with the mESC experimental validation. | This is experimental chromatin evidence, not merely a model score. It does not establish the corresponding expression program, fish-cell activity, developmental anatomy or flight. Predictors use human/mouse contexts; their calibration in fish is unknown. |
| [Few-shot regulatory sequence design](https://doi.org/10.64898/2026.10.28.762639), abstract, posted October 30 | Reports cell-type-specific enhancer expression in three human cell lines and labeling of mouse cortical layer-5 extratelencephalic neurons using human regulatory examples. | Preprint; abstract read, full methods not obtained in this review. Replicates, assay denominators, negatives and generalization require full-text/supplement inspection before quantitative reuse. Neither fish cells nor fin development is established. |
| [Efficient biological design via genomic in-context learning](https://doi.org/10.64898/2026.10.28.762643), abstract, posted October 29 | Reports genomic in-context learning and computational sequence-quality/diversity results. | This companion abstract does not establish experimental fish regulatory activity. Its other sequence-design applications are outside this task; no reproduction is proposed here. |
| [Arc report, October 29](https://arcinstitute.org/news/evo-2-in-context-learning), prediction and mouse-brain sections | Connects the two preprints and describes rewards supplied by sequence-to-function predictors separately from reported mouse expression observations. | Institutional report, not an additional independent experiment. Do not count predictor rewards as measurements or count the report and paper as independent evidence. |

## Cell and developmental map

The first five rows use [Chen et al., Genome Research](https://genome.cshlp.org/content/35/1/202),
Figs. 1, 5–6 and Methods, with [GSE261907](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE261907).
It measures paired nuclear RNA/accessibility in adult **caudal regeneration** at
0/1/2/4/6 days post-amputation, two biological replicates per time point,
GRCz11/Ensembl104. GEO metadata were fetched directly; sequencing matrices were
not downloaded. Marker lists are identification aids, not control recipes.

| Fish compartment | Existing program/data | Tool or assay; missing phenotype bridge |
| --- | --- | --- |
| Basal epithelium | cldni/fras1; candidate regulator lef1 | Paired RNA/ATAC, motif and peak–gene analysis; epithelial state does not specify fin outgrowth. |
| Superficial/intermediate epithelium | krt1-19d/cldn23a; cldna/tp63 | Cell-state annotation; boundary signaling and geometry remain uncalibrated. |
| Mesenchymal fibroblast states | prrx1b/msx1b; fibroblast subclusters | Paired measurements; inferred trajectories are not lineage tracing or an ECM modulus. |
| Osteoblast/joint states | sp7/bglap; lmx1ba/pthlha/evx1 | Measured state markers; inferred GRNs/CellOracle perturbations need causal tests. Mineralization, ray segmentation and stiffness need independent measurements. |
| Hematopoietic compartment | ptprc/mpeg1.1; spi1 | Injury-associated state; immune participation does not prove developmental growth control. |
| Embryonic pectoral fin field | tbx5a–fgf24; hand2-labeled lateral plate mesoderm | [Single-cell fate mapping/live tracking](https://pmc.ncbi.nlm.nih.gov/articles/PMC4689218/), abstract and Figs. 2–4, links signaling to fin-field convergence experimentally. This is a developmental mechanism, not a single-cell ATAC atlas; quantitative transfer to adult flying-fish allometry is missing. |
| Other organism compartments | [Daniocell/GSE223922](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE223922), whole-embryo/larval RNA atlas | [Published developmental analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC11181902/), Methods/data access: reference for muscle, neural, vascular and mesenchymal states. Whole-body sampling does not guarantee adequate pectoral-fin subtype coverage; inspect annotations and per-sample counts first. No paired ATAC is implied. |

Additional measured layers must remain distinct:

- [Lee et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC7047409/), Figs. 1–3/data access,
  measures accessible chromatin, RNA and DNA methylation, including sp7-sorted
  cells. [GSE126703](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE126703)
  links ATAC GSE126700, RNA GSE126701 and WGBS GSE126702. Stable lineage-associated
  methylation alongside changing accessibility argues against treating
  “epigenetic state” as one scalar knob; bulk/sorted assays are not single-cell.
- [GSE251828](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE251828) provides
  reporter-enriched scRNA data for epidermal, osteoblast and blastemal populations.
  Enrichment is a sampling bias, not whole-fin cell abundance.
- [Adult-fin CUT&Tag study](https://link.springer.com/article/10.1186/s13072-024-00547-5),
  abstract/results, reports H3K4me3 changes resembling embryonic patterns.
  Histone-mark enrichment is a separate observable from accessibility or RNA;
  this review has not checked its raw-data accession or cell-type resolution.

## The bridge closest to actual flying fishes

[Daane et al. 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC9172250/), comparative
results and Figs. 2–4, combines flying-fish/relative comparative genomics with
zebrafish fin-size genetics involving lat4a and kcnh2a. That is stronger relevance
than assuming a mammalian enhancer works in fish. Comparative signatures,
zebrafish phenocopy and cell-specific causal regulatory elements remain different
claims. It supplies neither a measured voltage-to-growth transfer function nor a
validated expression-to-pectoral-shape map. Channel conductance, transport,
expression location/timing, cell proliferation, ECM deposition and body loading
cannot be substituted for each other. Adult caudal regeneration is also not
embryonic paired-fin development.

## Bounded next computational questions, in priority order

These are proposed actions, not executed results or authorization for generation.

1. **Can the public data support the desired cell comparison?** Download only
   sample/processed-file manifests for GSE261907, GSE126703 and GSE223922; pin
   checksums, genome/annotation versions, donor/replicate/stage identifiers and
   supplied cell labels. Output a coverage/missingness table, including pectoral
   versus caudal scope. CPU, under one hour; stop on unresolved sample identity.
2. **Which existing natural regulatory associations reproduce across replicates?**
   First freeze a small basal-epithelial versus mesenchymal analysis. Use supplied
   processed matrices, donor/replicate-level pseudobulk and matched stage; report
   effect sizes, uncertainty and failed comparisons. Keep chromosomes/loci and
   biological replicates separate across any fitting/evaluation split. With only
   two replicates, cells are not independent biological repeats. CPU, bounded
   four hours after input-size admission; no new DNA generation or Evo2 call.
3. **Does a sequence-only predictor add information beyond simple baselines on
   existing measured fish elements?** Only after assay labels/full methods and
   permitted model use are available, preregister an evaluation on existing
   natural elements with held-out loci and GC/motif baselines. Separate ATAC from
   reporter-expression targets and assay context. A failed species-transfer test
   is useful; no fish success threshold is inherited from human/mouse AUROC.
4. **Where do growth hypotheses meet mechanics?** Connect measured cell-state
   observations to explicit unknown ports: expression→channel density/conductance;
   voltage/transport→proliferation; osteoblast/fibroblast state→mineral/ECM
   deposition; deposition→ray geometry/EI. Reuse existing bioelectric/fin models
   only with labeled assumed inputs. Next evidence is a context-matched assay or
   source measurement, not a fabricated coupling coefficient.

## Review checklist and access record

- [x] Read full Nature Fig. 6/results/contribution passages and full fish multiome,
  epigenome and pectoral fate-map text through public Jina mirrors.
- [x] Read Arc official page and both preprint abstracts; `.full` mirror requests
  still returned abstract pages. No full-methods claim is made for those preprints.
- [x] Fetch GEO text records; retain local response hashes in the source manifest.
- [x] Keep measured, inferred and proposed claims separate; preserve provider stop.
- [ ] Download/reanalyze sequencing matrices, verify experimental effect sizes,
  establish flying-fish cell types or measure any DNA-to-organism transfer.

Nature direct access redirected to authentication; bioRxiv/Genome Research web
fetches returned403, and PMC/GEO browser fetches showed a challenge. Public Jina
HTTP fetches recovered the texts listed above; direct GEO text export worked.
ScienceDirect's Jina response was a challenge despite HTTP200 and was excluded;
the flying-fish primary PMC paper was used instead. Response hashes record fetched
bytes, not correctness, dataset integrity or independent experimental replication.
