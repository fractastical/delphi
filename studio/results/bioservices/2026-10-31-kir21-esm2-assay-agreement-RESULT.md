# Result — ESM-2 masked marginals against two Kir2.1 assays

**Kind:** computational replication/evaluation on public data. Not new channel
biology. Nothing here is a claim about organism-level behaviour, about any
design, or about fin morphology. A prediction remains a prediction.

**Protocol:** [`experiments/bioservices/kir21_esm2_assay_agreement/PROTOCOL.md`](../../experiments/bioservices/kir21_esm2_assay_agreement/PROTOCOL.md),
frozen at commit `87526b7` before any model output existed.
**Verdict on H1: UNDETERMINED.**

## The question and the answer

Does an ESM-2 masked-marginal ranking agree better with Kir2.1 **surface
expression** than with **channel function**, on identical variants?

| Predictor | ρ surface | ρ function | Δρ (surface − function) | H1 |
| --- | --- | --- | --- | --- |
| **ESM-2 650M masked marginal** | **+0.299** [+0.179, +0.410] | **+0.334** [+0.220, +0.439] | **−0.035** [−0.188, +0.114] | **undetermined** |
| BLOSUM62 (label-free baseline) | +0.161 [+0.036, +0.283] | +0.085 [−0.037, +0.208] | +0.076 [−0.069, +0.222] | undetermined |

n = 256 matched variants over 193 positions. Intervals are 95% paired bootstrap
by variant, 10,000 resamples, seed 0.

Supporting tests on the ESM-2 arm, all agreeing that Δρ is not distinguishable
from zero here:

- Position-clustered bootstrap: Δρ 95% CI **[−0.196, +0.128]** (193 clusters).
- Paired permutation on rank-transformed assays: **p = 0.65**.
- Williams' test for dependent correlations: t = −0.493, df = 253, **p = 0.62**.

Both ESM-2 correlations are individually far from zero (permutation p < 1e-4 for
each, 10,000 permutations). What is undetermined is the *difference* between them.

## The honest headline: this design could not have answered its own question

The subset resolves a difference of about **|Δρ| ≥ 0.15** (the bootstrap SD of Δρ
is 0.076). The external reference registered in the protocol before the run —
ProteinGym's published full-dataset ESM-2 (650M) values, 0.352 surface and 0.382
function — implies a true difference near **0.03**.

So the evaluation was underpowered for its own question by roughly **fivefold**,
and that was fixed by the protocol's 256-variant cap before any data was seen.
A reader should take "undetermined" as a statement about this design, not as
evidence that the two agreements are equal.

This is the most useful thing the run produced. The pipeline is correct, the
controls pass, and the answer is that 256 variants cannot settle it.

## Agreement with the external reference

| | surface | function | Δρ |
| --- | --- | --- | --- |
| ProteinGym v1.3 table, full datasets (~6.9k variants) | 0.352 | 0.382 | −0.030 |
| This run, 256-variant hashed subset | 0.299 | 0.334 | −0.035 |

The **difference** reproduces closely (−0.035 against −0.030) and, notably, has
the same sign: both point to ESM-2 agreeing marginally *better* with function,
the opposite of the direction H1 proposed. With a CI of ±0.15 that agreement
could be coincidence, and it is reported as consistency rather than as
confirmation.

Both absolute correlations here sit about 0.05 **below** ProteinGym's. Plausible
causes, none of them checked: a 256-variant subset against ~6,900; ProteinGym's
scoring pipeline differing from this one in masking scheme or sequence context.
**This is a question to investigate, not a correction issued to ProteinGym.**
Their numbers were read from a table; their pipeline was not re-run.

## ESM-2 against the baseline

ESM-2 beats BLOSUM62 on both assays, and the gap is largest where BLOSUM62 fails
entirely: on channel function BLOSUM62 reaches ρ = +0.085 with permutation
p = 0.18, which is not distinguishable from zero, while ESM-2 reaches +0.334.
So the model is contributing something a substitution matrix does not — that
part of the evaluation is not undetermined.

## Assay-to-assay correlation, and what it does to the main caveat

The two assays correlate with each other at **ρ = +0.270** on this subset. ESM-2
therefore tracks *each* assay about as closely as the two assays track each other.

An independent critique had warned that channel function is measured downstream
of surface expression — a variant that never reaches the membrane cannot conduct
— so the function assay must carry the trafficking signal inside it. That remains
true as biology, and it means these are not independent readouts. But ρ = 0.270
is **lower than that relationship alone would suggest**: the two assays share
roughly 7% of rank variance here. The concern is weakened by the measurement
without being eliminated, and the number is reported so a reader can judge it.

## Sample coverage

| | value |
| --- | --- |
| Matched variants (both assays) | 6,789 over 391 positions |
| Evaluated subset | 256 variants over **193 distinct positions** (49.4% of matched positions) |
| Position span | residues 3–392 of 428 |
| Residue coverage | all **20/20** wild-type residues, all **20** mutant residues |
| Dropped as incomplete | **0** |

The subset tracks the full matched set closely, so it is not visibly skewed:

| distribution | n | mean | sd | median |
| --- | --- | --- | --- | --- |
| surface, subset | 256 | −0.694 | 2.217 | −0.227 |
| surface, all matched | 6,789 | −0.759 | 2.163 | −0.149 |
| function, subset | 256 | +0.092 | 0.617 | +0.122 |
| function, all matched | 6,789 | +0.012 | 0.591 | +0.044 |

## Acceptance

| Criterion | Result |
| --- | --- |
| A1 — four pilot controls behave as specified | **PASS** (both positives, both refusals) |
| A2 — ≥ 200 of 256 usable | **PASS** (256/256) |
| A3 — all six reference checks pass inside the run | **PASS** (8 recorded checks, all pass) |
| A4 — intervals for ρ_surface, ρ_function, Δρ | **PASS** |
| A5 — combined wall ≤ 60 min | **PASS** (29.2 min: pilot 118 s + scoring 1,636 s) |

The run is accepted. The hypothesis is undetermined. Those are different things,
and both are recorded.

## Receipts

| Artifact | Path |
| --- | --- |
| Pilot receipt | `results/bioservices/kir21_pilot_receipt.json` |
| Scores and per-invocation record | `results/bioservices/kir21_scores_checkpoint.json` |
| Analysis receipt | `results/bioservices/kir21_analysis.json` (sha256 `50b86f32…7434`) |
| Predictions vs measurements | `results/bioservices/kir21_predictions_vs_measurements.csv` |
| Figure | `results/bioservices/kir21_predictions_vs_measurements.svg` |
| Independent audit | `results/bioservices/gemini_audit*/`, ledger `gemini_usage_ledger.json` |

Checksums: ProteinGym archive `3a837662…b921` (43,021,128 B); surface assay
`9d36f571…c92d`; function assay `75f07fa6…2b92`; reference sequence
`88bfbcdd…b575`, byte-identical to UniProtKB P35561 (SV=1).
Checkpoint `facebook/esm2_t33_650M_UR50D`, fp32, CPU, 2 threads, seed 0; no
step-down was triggered. Own Spearman matches `scipy.stats.spearmanr` to four
decimals on both assays.

## What would actually answer the question

Score the **full 6,789 matched variants**. That is 391 distinct positions rather
than 193 — only about twice the forward passes, because masked marginals cost one
pass per *position* and not per variant, so roughly 40 minutes of the same CPU
work. At that n the interval on Δρ narrows by about √(6789/256) ≈ 5.2×, to
roughly ±0.03, which is the scale the external reference implies. A single
H100 would make it minutes rather than an hour.

The 256 cap came from the brief, not from the science, and it was the binding
constraint on this result.
