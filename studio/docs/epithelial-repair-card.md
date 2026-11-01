# Epithelial gap closure: a cell-to-tissue repair testbed

A confluent Cellular Potts monolayer with a hole cut in it, used to ask which modelled
mechanism closes the hole and under what conditions it fails to. It is a **mechanism
testbed**, not a treatment, not a therapy and not a viable engineered organism. Nothing
here is calibrated to a patient, a cell line or a measured tissue.

Engine: Morpheus v2.3.9, binary `3d9a6e5a…f0f94d5ad`, built as 12 named exactly-once edits
on the pinned upstream `Examples/CPM/Protrusion_2D.xml`
(`da2a27c8…92737db2`). The builder refuses if any edit matches a number of times other
than one.

Frozen protocol [revision 1](../artifacts/epithelial/protocol.json) (commit `5293180`) and
[revision 2](../artifacts/epithelial/protocol-r2.json) (commit `d0f7864`), both committed
before their own arms ran. Results: [revision 1](../artifacts/epithelial/results.json),
[both revisions](../artifacts/epithelial/results-r2.json). 36 arms, all exit 0.

---

## 1. What this reuses, and what it does not

| Source | Read level | What is taken | What is **not** taken |
|---|---|---|---|
| [Bai & Zeng 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10110613/), Sci Rep 13:6265, CC BY 4.0 | full text (PMC page; plus a local read-only cache `epithelial-source-jina.txt`, sha256 `76c090cb…b8c2a2efd`, fetched by Root) | the **geometric construction only**: Voronoi-tessellated monolayer, wound made by removing cells from the middle, no proliferation; and the scale anchor, 26 µm mean cell diameter | their mechanics. Theirs is a 3D continuum finite-element model with cohesive-zone traction–separation laws at cell–cell and cell–substrate interfaces, elastic cells at 0.2 kPa / ν 0.45. A CPM implements none of those equations. **This is not a reproduction of that paper.** |
| [Lee & Wolgemuth 2011](https://pubmed.ncbi.nlm.nih.gov/21423710/), PLoS Comput Biol 7(3):e1002007 | PubMed record (abstract and page content); full text not read | the hypothesis under test — that crawling alone can close a wound — and the existence of a motility-dependent failure regime | their model, their MDCK parameters, and their Δ>50 µm ablation-annulus threshold. No annulus experiment was run here. |
| [Noppe et al. 2015](https://pubs.rsc.org/en/content/articlelanding/2015/ib/c5ib00053j), Integr Biol 7(10):1253–1264 — CPM wound closure | **search-summary only.** Paywalled; publisher HTML, the publisher's author-version PDF and the CORE mirror each returned Cloudflare challenges through both WebFetch and `r.jina.ai` | nothing. It is recorded because it is the closest prior work and a reader should know it exists | every parameter. No value in this testbed is attributed to it. |
| [Niculescu, Textor & de Boer 2015](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1004280), PLoS Comput Biol 11(10):e1004280 | cited by the upstream example's own `<Details>`; not read here | the Act protrusion model, inherited through the pinned Morpheus example, at its upstream values | any claim that its calibration survives the cell-size change below |
| [Odagiri et al. 2022](https://arxiv.org/abs/2209.01354), arXiv, CC BY-SA 4.0 | abstract | that CPM wound closure is an established published approach | parameters; the ATP/Ca²⁺ coupling is not modelled here |
| [Morpheus m0032](https://morpheus.gitlab.io/model/m0032/) | not used | nothing | it is a vascular CPM-PDE model, not a wound model. No algorithm was taken from it. |

No full-text copy of any paywalled article is mirrored in this repository.

## 2. Scale mapping — declared, not fitted

The model requests 64 seeds on a 200×200 lattice, giving a **VolumeConstraint target of 625
nodes per cell**. That target is equated to the area of a 26 µm disc, the average cell
diameter Bai & Zeng take from experimental measurement. Hence **1 node = 0.84949 µm²**, node
length 0.92168 µm, and the lattice is 184.3 × 184.3 µm — smaller than their 400 × 400 µm sheet.

**625 is the target, not the realised mean.** `InitDistribute` actually places **65** cells,
so the realised mean cell area on an unwounded sheet is 40 000/65 = **615.38 nodes**, and the
cells sit about 1.5% below target. Anchoring the same 26 µm disc on the realised mean instead
would give 1 node = 0.86275 µm² and gaps of 539 / 2 157 / 3 775 µm² for *k* = 1 / 4 / 7 —
still inside Bai & Zeng's studied 400–4 900 µm² range, like the figures in the table below.
**Every µm² figure in this card therefore carries about ±1.6% from this choice of anchor**,
which is far smaller than the uncalibrated-model caveats in §8 and is recorded rather than
hidden. The published artifacts use the target-anchored mapping throughout.

*(Corrected 2026-10-31 after independent review read the raw runs. This section previously
said "mean cell area of 625 nodes by construction", conflating the target with the mean, and
gave the nominal 64 rather than the 65 cells actually placed. The logger and the TIFF agree
on 65 living IDs in the unwounded arm, so the two channels were never in conflict — the
error was in the card's description, not in the measurement.)*

Wounds are made by removing *k* central cells, exactly as Bai & Zeng describe. Every removed
cell is exactly 625 nodes, so initial gap areas are exact:

| *k* | gap (nodes) | gap (µm²) | inside Bai & Zeng's studied 400–4900 µm²? |
|---|---|---|---|
| 1 | 625 | 531 | yes |
| 4 | 2500 | 2124 | yes |
| 7 | 4375 | 3717 | yes |

Everything else — contact energies, constraint strengths, Metropolis temperature, protrusion
strength — is in **model units** inherited from the upstream example. None is a force, a
stress or a time in minutes. The upstream Act parameters were tuned for 2500-node cells and
are used here at 625; that transfer is **not** re-validated, and the protrusion sweep in §5
is the sensitivity probe for it.

## 3. The measurement, and why it can be trusted

`gap_nodes(t) = 40000 − Σ cell.volume(t)`, from the per-cell log.

Two gates check the instrument before any result is read:

- **G1b is INCOMPLETE, not a pass.** It compares the gap against an **independent channel** —
  counting medium pixels in the lattice images Morpheus' `TiffPlotter` writes, which shares no
  code with the logger. The frozen rule is *"every arm and **every** TIFF frame"*. Only
  **756 of 1 476 frames (51.2%)** are evaluable at all: the logger samples every 10 model time
  units and the TIFF every 25, so only their common multiples line up, and 20 of each arm's 41
  frames have no logger sample to compare against. **Zero of the 756 disagree** — consistent
  everywhere it can be checked, which is useful evidence — but 720 frames cannot be checked
  with the data that exists, so the frozen rule is unmet rather than satisfied.

  | | |
  |---|---|
  | **Reported** at `9429a21` and `edc1e10` | G1b **passed**, "0 frames disagree" |
  | **Independently assessed** (2026-10-31) | G1b **INCOMPLETE** — frozen rule unevaluable on 48.8% of frames |

  Both are kept. The reported status is the historical record and is not rewritten; the
  assessment supersedes it going forward. *Two errors of mine produced this: the card first
  claimed agreement over "every written frame" when the gate silently skipped 720, and then —
  worse — I narrowed the criterion to the shared times and kept the PASS. **That is relaxing
  an acceptance to make it pass**, which the protocol forbids outright. The frozen rule text
  is unchanged; only the verdict is corrected, and no threshold was moved to accept anything.*
- **G3** confirms every initial gap is exactly 625·*k*. **G5** confirms an unwounded sheet
  reads exactly 0 at every logged time — a gap measure that cannot report zero cannot report
  closure. **G2** confirms no cell is created or destroyed after wounding.

All four pass.

## 4. The floor: 22% of "closure" is not repair

**G10 failed, and this is the most important number here.** With *both* drives off — no
cell–medium interface energy and no protrusion — the gap still shrinks by **22.0%**.

That is arithmetic, not biology. After removing 4 cells, 61 survivors at a 625-node target
can claim at most 38 125 of 40 000 nodes, which leaves **1 875 nodes of residual gap**. So
the most the hole can be filled by cells relaxing into volume they were already short of is
2 500 − 1 875 = **625 nodes, i.e. 25.0%**. Measured is 551 nodes, 22.0%, just under that
ceiling because the surface constraint holds cells slightly below target.

**The ceiling is 625 nodes at every gap size, and 22% is NOT a constant to subtract.**
`InitDistribute` places **65** cells, so the population targets 65 × 625 = 40 625 nodes on a
40 000-node lattice — over-subscribed by exactly one cell's worth. Whatever is removed, the
survivors can collectively absorb exactly **625 extra nodes**. As a fraction of the wound
that is wildly different:

| *k* | survivors | gap (nodes) | residual at target | passive ceiling | **as % of this gap** |
|---|---|---|---|---|---|
| 1 | 64 | 625 | **0** | 625 | **100%** |
| 4 | 61 | 2 500 | 1 875 | 625 | 25.0% |
| 7 | 58 | 4 375 | 3 750 | 625 | 14.3% |

**This confounds the *k*=1 arm outright: a one-cell wound can close completely by passive
volume relaxation, with no mechanism at all.** That is the explanation for §6's finding that
*k*=1 never arrests at any λ_V — it was never a mechanism test. It is also why the *k*=1
rung is excluded from the rule's domain, and the exclusion is now mechanistic rather than
merely empirical.

The passive arm was measured **only at *k*=4**. The 22.0% is that arm's number; the 100% and
14.3% entries above are the *arithmetic ceilings*, not measurements, and no passive arm was
run at *k*=1 or *k*=7. So "subtract 22 points" is wrong everywhere except *k*=4, and even
there it is a **hypothesis about the cause** of the first quarter of closure — consistent
with the measurement, not proven to be its mechanism.

*(Added 2026-10-31 after independent review read the raw runs. The card previously implied
one universal floor.)*

*(Corrected 2026-10-31 after independent review of `edc1e10`. An earlier version of this
paragraph called 1 875 the number of nodes **filled**. It is the residual, and the filled
quantity is 625. The 25.0% and 22.0% figures were right; the label on 1 875 was not.
`check_card.py` now pins filled and residual separately, since pinning only 1 875 could not
tell the two apart.)*

**Every closure figure at *k*=4 must be read against this 22% floor.** The first revision's
negative control (G4) turned off only interface energy and was therefore mis-specified; it
failed, it is recorded as failed, and no bound was relaxed.

## 5. What closes the gap

At *k*=4, λ_V=0.3. "Closed fraction" is relative to the initial gap; the no-drive floor is
0.220.

| arm | protrusion | J(cell,medium) | λ_S | closed | outcome | sweeps to close |
|---|---|---|---|---|---|---|
| F1 no drive (control) | 0 | 0 | 5 | 0.220 | arrested | — |
| A2 motility off | 0 | 140 | 5 | 0.450 | arrested | — |
| A4 tension off | 80 | 0 | 5 | 1.000 | **closed** | 290 |
| A1 baseline | 80 | 140 | 5 | 1.000 | **closed** | 240 |
| A3 contractility off | 80 | 140 | 0 | 1.000 | **closed** | 180 |

Reading, strictly as model statements:

1. **Act-model protrusion is sufficient on its own.** Interface energy at zero still closes
   the gap. This is the model-level counterpart of Lee & Wolgemuth's claim that crawling
   cells close wounds without purse strings. It is agreement between a model and a published
   model-based claim — **not** experimental validation of either.
2. **Interface tension alone is not sufficient.** It arrests at 0.450, i.e. 23 points above
   the floor, never reaching closure.
3. **The two together are faster than either** (240 sweeps vs 290).
4. **The aspherity/perimeter constraint opposes closure** — removing it is fastest (180
   sweeps). No actomyosin purse-string is modelled, and this term should not be read as one.

**Protrusion dose-response (G11, passes).** On a gap that otherwise arrests (*k*=4, λ_V=1):

| protrusion | 0 | 20 | 40 | 80 | 160 |
|---|---|---|---|---|---|
| closed fraction | 0.316 | 0.409 | 0.548 | 0.684 | **1.000** |

Strictly monotone, and at 160 an arrested gap closes completely. Bai & Zeng report the same
ordering from their finite-element model over an assumed 0.2–10 pN range. A CPM protrusion
strength is not a force in piconewtons; this is an ordering shared by two models.

**Closure curve shape separates the mechanisms.** Fitting the closing phase both ways:
baseline is **linear** (R² 0.955 vs 0.689 exponential); crawling alone, with interface
energy off, is **exponential** (R² 0.938 vs 0.806). Bai & Zeng report a roughly linear
decrease and attribute a linear experimental decrease to Anon et al. The agreement is in
curve shape between models. It is not validation.

## 6. The reusable rule, its domain, and where it breaks

Derived from the CPM energy, never fitted: closure requires the interface energy the tissue
can shed to outweigh the volume-constraint cost of the stretch that fills the hole, giving

```
Phi = lambda_V * A_gap^2 / (N_cells * J_cell_medium * P_gap),   P_gap = 2*sqrt(pi*A_gap)
```

**Held-out test (G9, passes) — one conditional bracket check, not a verified scaling law.**
Φ is linear in λ_V and inverse in J, so doubling J must double the threshold. Revision 1
bracketed the *k*=4 threshold at λ_V ∈ (0.3, 1.0) with J=140, predicting (0.6, 2.0) at
J=280. Observed at J=280: closes at 0.3, 0.6, 1; arrests at 2, 4. The **observed bracketing
interval is (1, 2)**, whose geometric-mean summary is **1.414** — inside the predicted
interval. **No J=280 measurement entered the prediction.**

What that is and is not: 1.414 is a **summary statistic of the bracket**, not a directly
measured point threshold; the true threshold is somewhere in (1, 2) and the sweep spacing is
all that is known about it. This is **one doubling at one gap size**. It was not repeated at
*k*=7, and it does not establish exact linear proportionality in J — only that one
out-of-sample bracket fell where the group said it would. The packet sweep in the infra
handoff exists precisely because one doubling is one test.

**Where it breaks (G12, fails).**

- *k*=1 **never arrests**, at any λ_V tried up to 5 000, where Φ ≈ 2 460 — while *k*=4
  already arrests by Φ ≈ 4.13. The group does not govern a single-cell wound at all, and
  **§4 now gives the reason: at *k*=1 the passive ceiling is 100% of the wound**, so a
  one-cell gap can close with no mechanism acting. That arm cannot discriminate between
  closure mechanisms in either direction, and the Φ failure at *k*=1 is a confound rather
  than a refutation of the group there.
- *k*=4 and *k*=7 share the bracket (0.3, 1.0), while Φ predicts their thresholds should
  differ by 2.4×. Φ* is 2.26 and 5.51 — a spread ratio of 2.43, not a constant.

**Stated domain.** The rule is usable as *"at a fixed gap geometry in this CPM, the
closure threshold in λ_V scales linearly with the cell–medium contact energy J"*, verified
out of sample at one doubling, for multi-cell gaps of 4–7 cells (2124–3717 µm² under the
declared scale), at the upstream Act parameters, on a 200×200 periodic hexagonal lattice at
temperature 20. It is **not** a law about gap size, **not** valid for single-cell wounds,
and **not** a statement about any tissue. One doubling is one test; nothing here establishes
the scaling over a wider range of J.

## 7. Numerical controls

**Strict tally: 7 pass, 3 fail, 1 descriptive (G6), 2 incomplete or unevaluable (G1b, G8)** —
13 in all. Only the 7 are passes. **G6 is descriptive**: declared with no threshold, because
three seeds of one model are not independent samples, and no bound is invented for it now.
**G8 is unevaluable** and **G1b is incomplete** — neither is a pass, and neither is a fail.

| status | gates | count |
|---|---|---|
| pass | G1, G2, G3, G5, G7, G9, G11 | **7** |
| fail | G4, G10, G12 | **3** |
| descriptive, no verdict declared | G6 | 1 |
| incomplete / unevaluable | G1b, G8 | 2 |

*(Two corrections after independent review. At `edc1e10` this was stated as 9 pass by
counting descriptive G6 among the passes; the intermediate correction said 8, which still
counted G1b as a pass on a criterion I had narrowed to make it fit. The reported statuses at
`9429a21` and `edc1e10` are preserved in `results-r2.json` beside the assessment.)*

| gate | result | |
|---|---|---|
| G1 area conservation | **pass** | gap is an exact integer complement at every sample |
| G1b independent TIFF channel | **INCOMPLETE** | frozen rule is *every* frame; 756/1476 (51.2%) evaluable, 0 of those disagree. Reported as a pass at `9429a21`/`edc1e10`; that status is retained as history, not as a verdict |
| G2 cell count constant | **pass** | |
| G3 initial gap = 625·k | **pass** | |
| G4 one-drive negative control | **FAIL** | mis-specified; see §4. Retained, not relabelled |
| G5 unwounded reads zero | **pass** | |
| G6 seed spread | reported | closed fraction 1.000 across seeds 1, 2, 3; SD 0. Three seeds of one model are not independent biological samples |
| G7 Monte-Carlo step refinement | **pass** | and the stronger unplanned result below |
| G8 held-out, revision 1 | not evaluable | *k*=1 had no threshold bracket; replaced by G9, not widened |
| G9 held-out J scaling | **pass** | §6 |
| G10 no-drive negative control | **FAIL** | the 22% floor; see §4 |
| G11 protrusion monotonicity | **pass** | §5 |
| G12 complete gap ladder | **FAIL** | *k*=1 never arrests; see §6 |

**Sweep invariance (unplanned, stronger than G7's declared bound).** Halving `MCSDuration`
halves the model time to closure — 240 → 120 — while closure measured in **Monte-Carlo
sweeps is identical at 240**. CPM dynamics advance per sweep, not per model time unit.
Closure *time* in model units is therefore a statement about the sampler; closure in sweeps
is not. All times in this card are reported in sweeps.

## 8. Model mechanism vs experimental validation — the gap, stated

Everything above is a statement about a Cellular Potts Model. Specifically **not** established:

- That any of it describes a real epithelium. No measurement from any cell line or species
  was compared against any output. The only empirical quantity used anywhere is a 26 µm mean
  cell diameter, used to set a length scale, not to test anything.
- That CPM protrusion strength corresponds to lamellipodial traction force, that λ_V
  corresponds to cell compressibility, or that J corresponds to an adhesion energy in J/m².
  None of these mappings is calibrated, and §6's rule is in model units on both sides.
- That agreeing with Bai & Zeng on protrusion ordering, or with Lee & Wolgemuth on
  crawling sufficiency, is evidence either is right. Two models agreeing is model-level
  agreement; it raises neither one's evidence level.
- Purse-string actomyosin closure, which is not modelled at all, and which the sources
  describe as dominant for small wounds late in closure. The §5 contractility arm is a CPM
  perimeter constraint and is **not** a purse string.
- Proliferation, signalling, substrate stiffness, ECM, and the 3D monolayer thickness
  (3–15 µm per Bai & Zeng) — all absent. This is 2D.

**What would move any of this toward validation**: a measured gap-area-vs-time trace from a
named cell line with its wound geometry, compared against a run whose length and time scales
were fixed before the comparison. That needs data this project does not hold. It is a stated
missing job, not a defaulted assumption.

## 9. Artifacts

- Frozen protocols: [revision 1](../artifacts/epithelial/protocol.json),
  [revision 2](../artifacts/epithelial/protocol-r2.json)
- Results: [revision 1](../artifacts/epithelial/results.json),
  [both](../artifacts/epithelial/results-r2.json)
- Per-arm provenance (model sha256, the 12 edits, exit, wall time): `artifacts/epithelial/arms/`
- Run logs: `runs-revision1.log`, `runs-revision2.log`
- Spatial movies of the actual CPM lattice with the actual logged cell tracks drawn on it,
  plus posters taken from the videos themselves:
  [baseline, closes](../artifacts/epithelial/media/A1-baseline.mp4) ·
  [motility off, arrests](../artifacts/epithelial/media/A2-motility-off.mp4)
- Code: `engineering/epithelial/{build_model,protocol,run_arms,analyze,render}.py`

All 36 arms ran on CPU under `CPUQuota=200% MemoryMax=2G MemorySwapMax=0 TasksMax=256
RuntimeMaxSec=600`, one thread each; the slowest arm took 31.3 s.
