# Preregistration — KCNE1 surface expression from KCNE1–KCNQ1 interface binding ΔΔG

Committed **before the job is submitted**. The commit timestamp is the evidence.

## The precondition, which passed, and is why this job is justified rather than decorative

Published ProteinGym per-assay Spearman table, `DMS_substitutions_Spearman_DMS_level.csv`,
HTTP 200, **141,235 bytes**, sha256
`f432423b87f79ac9778dfac86e3d95be041d246bc618dc0a406b35b0b7466437`. Must-fail control: a bogus
path on the same host returns **404**, so the endpoint can come back empty.

On the Kir2.1 pair — `KCNJ2_MOUSE_Coyote-Maestas_2022_surface` (6,917) and `..._function` (6,963),
the same variants scored for both by the same lab — ranking all **96** real models by
ρ(surface) − ρ(function):

| rank | model | surface | function | Δ |
|---|---|---|---|---|
| 1–6 | **all six ProSST configurations** (structure-aware) | up to +0.371 | up to +0.221 | **+0.131 to +0.177** |
| 7 | Site-Independent (conservation only) | +0.381 | +0.256 | **+0.125** |
| 54 | ESM2 (650M) | +0.352 | +0.382 | −0.030 |

**Structure-aware and conservation-only methods are systematically better at trafficking than at
gating; sequence language models are not.** Six named models taking the top six of 96 is about
1 in 9×10⁸ by chance. Only 32 of 96 models are better at surface than function at all.

Caveat, stated: these are ProteinGym's *published* numbers, read not recomputed. `full-text`
evidence of what ProteinGym reports; `source-only` as to whether each number is right.

## The test

**Claim.** KCNE1 reaches the cell surface by assembling with KCNQ1 — the source paper measures a
**6.1-fold** increase in surface expression on KCNQ1 co-expression. So the physical quantity that
should govern KCNE1 surface expression is the **binding free energy of the KCNE1–KCNQ1
interface**.

**Computation.** Nebius hosted `submit_stab_ddg` — verbatim from the live catalogue,
*"mutation-induced binding energy changes from a wild-type PDB"* — on the KCNE1 chain of
**PDB 9VEC** (human KCNQ1–KCNE1–CaM, cryo-EM, 2.7 Å). **Not 9A06**, which is Rosetta docking
models, i.e. a prediction rather than a measurement.

**Scored against** ProteinGym `KCNE1_HUMAN_Muhammad_2023_expression` (N = 2,339 missense).
Primary deposit MaveDB `urn:mavedb:00000674-a`.

**Baseline, already published and already downloaded — nothing to compute:** best of 98 models
**+0.288** (ProSST K=2048), median **+0.111**, ESM2-650M **+0.106**. This is the worst-predicted
ion-channel assay in ProteinGym.

## Acceptance, falsifier, stop rules — fixed here, before any result

- **Acceptance**: Spearman ρ(predicted ΔΔG, measured surface expression) over variants resolved in
  9VEC, with a 10,000-sample bootstrap CI whose **lower bound exceeds +0.288**.
- **Falsifier**: the bootstrap CI **includes +0.288**. That is a null and is reported as one.
- **Inconclusive**: coverage below 75% of assay variants — a correlation over a biased subset is
  not a result, and the coverage is reported either way.
- **Positive controls, named by the source paper, checked BEFORE the full run**: **L51H** is a
  known trafficking-null and must rank destabilising; **D76N** is a known gating variant with
  near-WT surface expression and must not. **If these two are not separated, stop. Nothing
  downstream is worth reading.**
- **The strong form, a double dissociation**: run the same ΔΔG against the *function* arm, where
  the field does well (best +0.642, median +0.488, ESM2-650M +0.525). The prediction is that ΔΔG
  **beats** the language models on expression and **loses** to them on function. A generic
  "my score is good" artifact cannot produce a crossing interaction. The mechanism supports it:
  of 574 loss-of-function variants, only **152 (26.5%)** had reduced surface expression, and
  **422 (73.5%)** are gating variants.
- **Hard stop**: 6 hours wall clock. One GPU. The pool is shared with other teams.

## What this cannot show

A binding ΔΔG that correlates with surface expression supports the *mechanism*; it does not
measure trafficking, and it is not an experiment. Nothing here is evidence about a patient, a
cardiac phenotype, or any variant's clinical significance.
