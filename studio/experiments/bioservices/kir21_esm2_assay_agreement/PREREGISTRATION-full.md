# Preregistration — full 6,789-variant Kir2.1 run

**Frozen before the run.** Authorized as an expanded follow-up to the 256-variant
evaluation. **The 256-variant verdict is retained, not replaced:** it stands as its
own completed result, and this run is reported beside it rather than overwriting it.

Parent protocol: [`PROTOCOL.md`](PROTOCOL.md). Parent result:
[`../../../results/bioservices/2026-10-31-kir21-esm2-assay-agreement-RESULT.md`](../../../results/bioservices/2026-10-31-kir21-esm2-assay-agreement-RESULT.md).

## 1. What changes, and what does not

| | 256 run | This run |
| --- | --- | --- |
| Variants | 256 hashed subset | **all 6,789 matched** |
| Distinct positions | 193 | **391** |
| Checkpoint, precision, threads, seeds | `esm2_t33_650M_UR50D`, fp32, 2, 0 | **identical** |
| Scoring operation | masked marginal | **identical** |
| Statistics, seeds, resample counts | `analyze.py`, 10,000, seed 0 | **identical code path** |
| Falsifier | CI on Δρ | **unchanged** |

Nothing about the evaluator is tuned here. The same functions run on more data.

## 2. The 193-position cache could not be reused, and why that is reported rather than quietly worked around

The honest position: **the 256 run persisted per-variant scores, not per-position
log-probability vectors.** The in-process cache held the vectors, the process
exited, and only `{mutant: score}` reached disk.

A per-variant score is `lp[mut] − lp[wt]` at one position. Recovering all 19
substitutions at a position needs the whole `lp` vector, and a handful of
differences cannot reconstruct it. So the 193 already-computed positions are
**recomputed**, not reused, and the run costs 391 forward passes rather than 198.

That recomputation is turned into evidence rather than waste:

- **Exact-reproduction control.** The 256 original variants are re-derived from the
  new position vectors and must match the committed values **bit-for-bit**. Any
  mismatch halts the run and is reported; a float difference would mean the scoring
  path is not deterministic across processes, which would also weaken the 256 result.
- **This run persists the log-probability vector for every position**, keyed by
  position and carrying a sha256 of the exact masked input tensor. A future
  extension to any variant at any of the 391 positions then costs no forward passes.

## 3. Compute: CPU, and why not the GPU that was offered

Measured per-position cost in the 256 run: 11.0, 6.0, 9.8 s across invocations,
load-dependent, roughly **8 s/position**. 391 positions ≈ **52 minutes**, inside the
60-minute CPU bound. Host load at freeze time is 2.4 on 8 cores, the quietest it has
been this session.

CPU is chosen over the authorized single H100 because it is **the same hardware,
checkpoint, precision and code path as the 256 run**, which is what makes the
exact-reproduction control in §2 meaningful, and because it needs no container
build, no weight transfer and no cross-session coordination. A GPU would be faster
in isolation and strictly worse as evidence. If the run exceeds 60 minutes it stops
and reports partial coverage rather than continuing.

Resumable across capped scopes exactly as before: `TasksMax=128 MemoryMax=4G
MemorySwapMax=0 RuntimeMaxSec=600`, 2 threads, `nice -n 19`, bounded work per
invocation, driver stops on any non-zero exit.

## 4. Preregistered prediction about precision — stated now because it is the point of the run

My own result document wrote that the full run would narrow the interval on Δρ by
"about √(6789/256) ≈ 5.2×". **That is an approximation that assumes variants are
independent, and they are not.** It is corrected here, before the run, rather than
after seeing whether it held.

| Interval | Effective units | 256 run half-width | Expected narrowing | Predicted half-width |
| --- | --- | --- | --- | --- |
| Variant-level bootstrap | 256 → 6,789 variants | 0.149 | ~**5.15×** | ~0.029 |
| **Position-clustered bootstrap** | 193 → 391 **positions** | 0.162 | ~**1.42×** | ~**0.114** |

The clustered interval is the one that respects the dependence between variants at
a position, and its effective sample size is the number of **positions**, which only
roughly doubles. So:

> **Prediction, recorded in advance: the variant-level interval will tighten enough
> to resolve a Δρ near the external reference's 0.03, and the position-clustered
> interval will not. If the clustered interval governs, the full run may well return
> UNDETERMINED again.**

That is a real possible outcome of this run and it is written down before it happens.
Reporting a narrowed variant-level interval as resolution, while the clustered
interval still spans zero, would be the error this section exists to prevent.

**Both intervals are reported. Where they disagree, the wider governs** — the rule
already fixed in the parent protocol after a positive control refuted my earlier
claim that clustering is automatically conservative.

## 5. Required sensitivity reporting

Beyond the two intervals:

1. **Cluster-count sensitivity.** The clustered bootstrap is recomputed on 193 and
   391 clusters so the change attributable to added positions is visible, rather than
   inferred from the √n rule in §4.
2. **Measured against predicted narrowing.** The realised half-widths are reported
   against the §4 predictions. A miss is a finding about the approximation.
3. **Subset-versus-full comparison.** ρ on the original 256 and on all 6,789, with the
   256 figures taken from the committed result and not recomputed into agreement.
4. **Per-position variance.** The number of variants per position and its spread, since
   an unbalanced design changes what cluster resampling does.

## 6. Verdict rule

Unchanged from the parent protocol. H1 is that ESM-2 agrees better with **surface
expression** than with **channel function**.

| Outcome | Rule |
| --- | --- |
| Falsified | 95% CI for Δρ entirely at or below 0 |
| Supported | 95% CI for Δρ entirely above 0 |
| Undetermined | CI spans 0 — not support |

Applied to the **governing** interval of §4, with both reported. The 256-variant
verdict (UNDETERMINED) is retained as a separate recorded result.

## 7. Acceptance for this run

- F1. All 391 positions scored, or partial coverage reported with the count.
- F2. The 256 original variants reproduce **bit-for-bit** from the new vectors.
- F3. All reference checks of the parent protocol pass again inside the run.
- F4. Both intervals, plus the four sensitivity items of §5.
- F5. Wall clock ≤ 60 minutes, or a reported stop.

## 8. Status of these results in Delphi Frontier

**Protocol acceptance is not independent review.** A1–A5 in the 256 result, and
F1–F5 here, are this harness checking its own run against criteria it fixed in
advance. Under SPEC-005 the executor cannot certify its own work, so both results
are **proposed contributions** carrying a self-assessment. They have not been
through Frontier's independent review, no reviewer other than this harness has
examined them, and nothing here should be read as a Frontier-accepted result.
