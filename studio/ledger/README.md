# The refutation ledger

One team, one day, a large agent fleet and good tools. **Every candidate headline we generated was
refuted, nulled, or found to have a predecessor.** This file is the record, because the ratio is
the most interesting number we produced.

Each row names the witness. A list of mistakes without receipts is a confession; with receipts it
is a measurement.

| # | Claim | How it died | Witness |
|---|---|---|---|
| 1 | first machine-checked formal biology | prior art | Rashid et al. HOL Light, PLOS ONE 2017; `lean-bio`; `crnt-lean`; Ripple v2 |
| 2 | a shared lemma commons is our mechanism | prior art **+ negative replication** | LEGO-Prover, LeanAgent, Prove Together; **Berlot-Attwell 2025** found no reuse and no compute-matched gain |
| 3 | Turing needs diffusion ratio ≥ 10 | **Lean counterexample** | unstable at ratio 1.1, `J=[[1,-1],[1011/1000,-101/100]]`, `L=5π`, mode 1 det `−21/25000` |
| 4 | real proteins can't reach the required ratio | prior art | **Kuhn et al. 2022**: Nodal and Lefty free diffusion is *comparable*; the difference is retention, not size |
| 5 | "physics knows where its equations stop, biology doesn't" | prior art | finite-domain RD scope is established literature |
| 6 | our own `finite_domain_stable` theorem | **it was `not_lt`** | compiled, passed the axiom audit, said nothing; caught by independent review, not by us |
| 7 | an operationalization-fidelity benchmark | prior art | ShadowBench; DriftBench; Benchmarking Agentic Review Systems |
| 8 | Thompson's 3/2 refuted by a Tallo regression | **scope error + prior art** | it is a buckling envelope; Tallo 2022 already tested 2/3 with mixed models |
| 9 | agents hallucinate past scope conditions | **measurement** | 24 systems, 12 traps, exact truth: gemini-4-argon 24/24, claude-opus-5 24/24 |
| 10 | the robustness tax as a headline | partial prior art | Marcon 2016; the 2024 network-size work covers the neighbourhood |
| 11 | no machine-checked biology library with scope conditions exists | **prior art, five hours old** | `facebookresearch/atlas-lean` `MathlibExt/Biology/`, 56 files, zero `sorry`, commits to 2026-10-31 04:32 UTC |
| 12 | our replacement citation for the finite-domain caveat | **we hadn't read it** | both arXiv abstracts fetched; neither supports the claim |
| 13 | Thompson's 3/2 confirmed by upper-quantile regression | **refuted** | peaks at **0.652 at q=0.90**, *below* 2/3, then falls; non-monotone with an interior maximum |
| 14 | …and the original OLS refutation doesn't hold either | **retracted** | RMA slope 0.780, so 2/3 sits *between* OLS and RMA; cluster bootstrap over 69 studies gives [0.503, 0.697], containing 2/3 |

| 15 | our own four-arm checker is sound | **reproduced defect** | it accepts a frozen `False` once helper text adds a second `False` assumption; elaborated type is `False → False`, with a **clean axiom audit**. Target weakening, not a Lean inconsistency. |

Four killed by prior art, three by counterexample or direct refutation, three by measurement, and
several of our own by our own checks. **Entries 3, 5, 6, 12 and 14 were mine.**

### Why #15 is the most useful row in this table

Earlier today I warned the experiment's owner, in writing, that *"compiles plus clean axioms is
not a sufficient success criterion, because an agent optimising for green will produce
tautologies."* That was a prediction. Within two hours an independent reviewer **reproduced it
offline** against our own runner: the checker accepts `False → False` and the axiom audit comes
back clean.

So the failure mode is no longer theoretical, and the mitigation is no longer a suggestion. **An
arm may score a statement only if its paired mutant was also rejected.** Three further defects in
the same review would each have corrupted the comparison: pending token checks permit 60 + 60
against a cap of 100 because reservations are not atomic, which breaks the matched-budget claim
outright; proof dependencies are inferred from source-name regexes rather than from the compiled
artifact; and the historical 19 integer targets are not the 21-record experiment that was
requested. The experiment is correctly on hold until all four are fixed.

## The one that settled #13, because the mechanism matters

The pooled quantile slope *rises* with quantile, which looks like an envelope. It is a
**between-group composition effect**. Within a single study the slope **falls** with quantile — 8
of 44 studies go the other way, sign test p = 2.5e-5; within a single species, 14 of 56,
p = 2.3e-4. Species-demeaning makes the ladder monotonically decreasing. The literal boundary line
from binned maxima has slope **0.51**, *shallower* than the conditional mean of 0.588. Every
independent envelope estimator points the wrong way. The within-population signature is height
saturating at large diameter — the standard forestry curve, not a power-law ceiling.

And the asymptotic confidence intervals were **overconfident by roughly thirtyfold** once studies
are treated as the sampling unit. That is what retracted our own first finding.

## Prior art we should have checked before claiming any of it

- **Mangalam et al. 2024**, *Sci Rep* 14:19957 — already ran quantile regression of log height on
  log diameter **on Tallo**, explicitly against elastic similarity's 2/3, centiles 2 to 98, with
  the same mixed result.
- **McMahon 1973**, *Science* 179:1201 — "2/3 is a ceiling, not a mean" is his own wording:
  *"there are no data points to the left of the solid line"*. He fitted no slope.
- **Price et al. 2009**, *Ecol Lett* 12:641 — a 2/3 slope cannot discriminate elastic similarity
  from metabolic scaling; they make identical predictions here.

## The one candidate that survived the day

**A per-tree Greenhill safety factor across a global individual-tree database.** A scan of all
**120 OpenAlex works citing Tallo** found nobody doing it.

Measured: between **0.068% and 3.24%** of trees exceed critical buckling height depending on the
taper assumption; median safety factor **1.8 to 2.9**. The result is dominated by taper (1.57×)
rather than wood properties, since the cube root crushes a 2× spread in E/ρ to 1.26×. Caveat
stated: Tallo's diameter is DBH at 1.3 m, not basal, which overstates the ratio by about 13%.

Provenance: Zenodo 10.5281/zenodo.6637599, Tallo v1.0.0, CC-BY-4.0; local md5 matches Zenodo's
published checksum. Positive control: pooled OLS reproduced to **14 significant figures** against
the earlier independent probe.
