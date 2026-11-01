# We had ten H100-hours and measured that our problem does not need them

Nebius access was restored at 09:49 PDT and holds until 21:49. The honest readiness verdict is
that **we have no GPU-necessary problem**, and it was measured rather than asserted. Single-reader,
not Codex-reviewed.

## Three measurements, each of which alone would settle it

**1. The canonical bioelectric tissue model is not a GPU problem by orders of magnitude.**
Riol / Cervera / Levin / Mafe (2021) Eqs. (1)-(4), reimplemented in NumPy and timed on **one busy
core** of this shared 8-core box at `nice 19`: the paper's own **882-cell** geometry integrates a
full 100 ms membrane time constant in **0.718 s**. 100,000 cells takes **55.7 s**. A million-cell
aggregate extrapolates to about **9 minutes**. An H100 would sit idle. BETSE, the actual
bioelectric simulator (PyPI 1.5.0, 2025-04-15), is pure Python with no GPU path at all.

**2. The GPU speedup for the one computation that would need a GPU is about 3x, not 100x.**
NHR@FAU's GROMACS benchmark, read at full text: on an 80,289-atom membrane protein an A100 does
**247.1 ns/day** against **87.5 ns/day for a full 72-core Ice Lake node** — **2.82x**. One EPYC
7742 node beat a V100. Ten H100-hours buys roughly **150 ns** against a **millisecond** channel-
gating timescale: four to five orders short. Molecular dynamics on gating is not a candidate.

**3. Nothing public pairs a calibrated membrane voltage with an outcome.** Every candidate deposit
reports ΔF/F or dye intensity in arbitrary units. Silic 2022 contains **zero occurrences of
"mV"** in its full text. A simulated field cannot be scored against an uncalibrated reporter.

## What this is worth

A measured refusal to use free GPUs is a stronger result than a job run to have run one. The
failure mode it avoids is the one this project has spent all day refuting in other costumes: an
impressive-looking artifact that answers no question. We can say exactly what we would have had
to believe to justify the job, and show the number that was false.

## Corrections this produced

**`submit_stab_ddg` is a *binding* ΔΔG predictor, not folding stability.** Read live from the
Nebius catalogue (69 tools, HTTP 200): *"mutation-induced binding energy changes from a wild-type
PDB."* Any stability experiment planned on it is the wrong experiment.

**Future House's Millennium Problems in biology are real and were fetched, not recalled.**
`millenniumproblems.bio`, HTTP 200, 27,345 bytes, 12 problems verbatim, Rodriques & Hinks,
announced 2026-09-23. The structural observation matters more than the list: it is **selected for
wet-lab validability**. Problems 08, 09, 11 and 12 are exactly what RFdiffusion, BoltzGen or
Mosaic could attack — and for every one of them **we could produce the designs and could not
score them.** That is the same wall, stated by someone else's prize committee.

**NCA inverse design is a demo, not a benchmark.** NCAtorch (arXiv 2604.24990) is a reference
implementation for vision ablations, with no inverse-design task and no leaderboard. The one
genuinely bounded cellular-automaton inverse-design problem with published baselines is the 1978
**density classification** task (GKL 0.815; best coevolved 0.851/0.860 at N=149) — and it is CPU
work.

**Bioelectric nanofabrication: the field was not found** within one English-language web search.
What exists is exogenous electric-field-directed assembly (Heller's dielectrophoretic
microarrays), a different literature that shares vocabulary with Levin's endogenous V_mem
signalling. Scope: one search, English only — absence of evidence at that depth, not evidence of
absence.

## The one surviving candidate, and the cheap test that should precede it

KCNE1 trafficking predicted from interface ΔΔG on **PDB 9VEC** (KCNQ1-KCNE1-CaM cryo-EM, 2.7 Å),
scored against ProteinGym's `KCNE1_HUMAN_Muhammad_2023_expression` — **the worst-predicted channel
assay in that benchmark**: 98 published models sit at median Spearman **+0.111**, best **+0.288**,
ESM2-650M **+0.106**. The mechanism is sound (KCNQ1 co-expression raises KCNE1 surface delivery
**6.1-fold**), the controls are named by the source paper (L51H trafficking-null, D76N gating),
and the strong form is a crossing interaction across that paper's own 152-vs-422 trafficking/
gating split.

**Its GPU-necessity is access-based, not FLOP-based**, and the agent that proposed it said so
itself rather than being caught at it.

**And the sharpest finding argues against starting the GPU job at all:** the discriminating
analysis is already answerable from a **141 KB CSV**. On the Kir2.1 paired assay, Site-Independent
scores **+0.381 on surface** against **+0.256 on function**, while ESM2-650M is flat
(+0.352 / +0.382). Run the CSV first. It decides whether the GPU job is worth starting, and it
costs nothing.
