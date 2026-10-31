# Protocol — ESM-2 masked marginals against two Kir2.1 assays

**Status:** frozen before any model output exists. **Owner:** bioservices harness.
**Kind:** computational replication/evaluation on public data. It is not new channel
biology, and it says nothing about fin morphology, organism behaviour or any
design. A prediction here remains a prediction.

## 1. Question

On the *same* public Kir2.1 (KCNJ2) variants, does an ESM-2 masked-marginal ranking
agree better with **surface expression** than with **channel function**?

Both outcomes come from one multiparametric deep mutational scan, so the two assays
share a reference sequence and largely share a variant set. That is what makes the
comparison paired rather than two unrelated benchmarks.

## 2. Source data — version, licence, checksums

| Item | Value |
| --- | --- |
| Archive | `https://marks.hms.harvard.edu/proteingym/ProteinGym_v1.3/DMS_ProteinGym_substitutions.zip` |
| Archive version | ProteinGym v1.3, DMS substitutions |
| Archive size | 43,021,128 bytes |
| Archive sha256 | `3a83766254ac9ac9984ec25cb73c6e010ea4418f5e35f143933e6b6e6473b921` |
| Licence | MIT (ProteinGym curation). The measurements belong to the source publication. |
| Source publication | Coyote-Maestas et al. 2022, multiparametric deep mutational scanning of Kir2.1 (the assay id names it; the paper was not re-read for this protocol) |

| Assay | Member sha256 | Rows |
| --- | --- | --- |
| `KCNJ2_MOUSE_Coyote-Maestas_2022_surface` | `9d36f57185d11ad98aa3f69ca014c15682dbdb33c4c3c0d1ec0b3ea28ed8c92d` | 6,917 |
| `KCNJ2_MOUSE_Coyote-Maestas_2022_function` | `75f07fa60b83f41d92ac42738cc6a3dfc7605cde6605add499efd400f4882b92` | 6,963 |

Row counts agree with ProteinGym's own reference table (6,917 / 6,963), which is a
check on the archive, not an independent measurement.

## 3. Reference sequence and assay-mismatch checks

Each assay's reference is **reconstructed from its own rows** and then checked
against an independent source. Every single-substitution row constrains the
reference at every position, so the reconstruction is over-determined and any
internal inconsistency is an error rather than something to resolve silently.

Checks that must pass before scoring, each of which stops the run on failure:

1. `mutated_sequence` lengths are uniform within an assay. *(measured: 428)*
2. For every row, the mutated position holds the declared mutant residue.
3. All non-mutated positions agree across all rows of an assay.
4. The declared wild-type residue agrees with the reconstructed reference.
5. The two assays reconstruct to the **same** reference sequence.
6. The reconstructed reference equals **UniProtKB P35561** (`KCNJ2_MOUSE`, SV=1).

Measured before freezing: all six pass. Reconstructed reference is 428 aa with
sha256 `88bfbcddd595e33da25f5ab224ce2b41cfaeacf488c7a7a51178d24d24e3b575`, byte-identical
to P35561. Matching the UniProt entry establishes which protein the assay is about;
it does not establish that the published measurements are correct.

A variant whose declared wild-type residue disagrees with the reference is
**refused**, never scored. The pilot exercises this.

## 4. Matched variant set and deterministic subset

Matched set: variants present in both assays, which requires the shared reference
of check 5. Measured before freezing: **6,789 matched variants over 391 distinct
positions, positions 2–392** of 428.

The evaluation subset is fixed by hashing the variant name only — never by any
measured value:

```
salt   = "delphi-frontier/kir21-esm2-assay-agreement/v1"
key(m) = sha256(f"{salt}|{m}").hexdigest()
subset = first 256 matched variants sorted by (key(m), m)
```

Size: **256**, the brief's cap. Coverage is reported, not assumed: distinct
positions and their span, wild-type and mutant residue composition against the full
matched set, and the subset-versus-full distribution of each assay's score. A subset
that turns out unrepresentative is reported as such; it is not reselected.

## 5. Model, checkpoint, operation

| Field | Value |
| --- | --- |
| Operation | ESM-2 masked marginal, `log p(mut \| x_masked at i) − log p(wt \| x_masked at i)` |
| Target checkpoint | `facebook/esm2_t33_650M_UR50D` |
| Precision / device | fp32, CPU |
| Threads | 2 |
| Determinism | `torch.set_grad_enabled(False)`, seed 0, fixed batch composition |

One forward pass per *distinct position*, batched 4 positions at a time. Token index
`p` must hold reference position `p`; this is asserted at three positions and the run
stops if it does not hold, because an off-by-one would produce plausible wrong numbers.

**Checkpoint step-down rule, fixed here in advance.** Median batched-forward latency is
measured in the pilot. If the projected scoring time exceeds **25 minutes**, step down to
`facebook/esm2_t30_150M_UR50D`, re-measure, and report which checkpoint produced the
numbers. This rule reads a wall clock and never reads a measured assay value.

Exactly one scoring configuration is run and reported. Discovering what a catalogue
contains is not inference and is not reported as a result.

## 6. No learning, no test-label leakage

- The model is frozen and zero-shot. Nothing is trained, fitted or calibrated.
- `Esm2MaskedMarginalScorer` cannot accept an assay value; its API has no such
  argument. That is the structural form of the guarantee, not a promise.
- The subset is selected by hash of the variant name alone.
- No threshold, weight or model choice depends on any measured outcome.
- The analysis runs once. If it is re-run for any reason, every run is reported.

## 7. Baselines and uncertainty

**Baselines** (both label-free, computed on the same subset):

1. **BLOSUM62** substitution score for `wt → mut`. A biochemical-similarity baseline
   with no model and no structure.
2. **Permutation null.** Scores shuffled 10,000 times, seed 0, giving the noise floor
   and a two-sided p-value for each ρ.

**External reference, stated before the run so the outcome cannot be re-framed
afterwards.** ProteinGym v1.3's published table reports ESM-2 (650M) Spearman
**0.352 on surface** and **0.382 on function**, over the *full* datasets with
ProteinGym's own scoring code. That is Δρ ≈ **−0.030**, which points *against* the
hypothesis in §8. Those numbers are a lead, not a verified input: they were read from
the table, their pipeline was not re-run, and this protocol scores a 256-variant
subset with its own code, so a difference is expected and is not by itself evidence
of an error on either side.

**Uncertainty.** Spearman ρ is computed for each assay on the identical subset.
The paired statistic is Δρ = ρ_surface − ρ_function. A **paired bootstrap** resamples
*variants* with replacement — the same resampled indices for both assays, which is
what makes it paired — 10,000 times with seed 0, recomputing ρ_surface, ρ_function and
Δρ on each resample. Reported: point estimates and 95% percentile intervals for all
three. The pairing matters: the two assays are strongly dependent, so an unpaired
comparison of two independent intervals would overstate the uncertainty on Δρ.

Score orientation is verified against `DMS_score_bin` before correlating, so a sign
error cannot be mistaken for a finding.

## 8. Hypothesis, acceptance and falsifier

**H1.** ESM-2 masked-marginal ranking agrees better with Kir2.1 **surface expression**
than with **channel function** on matched variants.

| Outcome | Rule |
| --- | --- |
| **Falsified** | 95% CI for Δρ lies entirely at or below 0 |
| **Supported** | 95% CI for Δρ lies entirely above 0 |
| **Undetermined** | CI spans 0 — reported as undetermined, never as support |

**Run acceptance**, which is about the evaluation executing correctly and is
deliberately independent of which way H1 goes:

- A1. All four pilot controls behave as specified in §9.
- A2. At least 200 of the 256 subset variants carry a finite ESM-2 score and both
  measured outcomes.
- A3. All six reference checks in §3 pass inside the run, not only here.
- A4. Point estimates and bootstrap intervals exist for ρ_surface, ρ_function and Δρ.
- A5. Combined wall clock ≤ 60 minutes.

A null or inconclusive result that meets A1–A5 is a completed evaluation and is kept.

## 9. Validation pilot — run before the batch

| # | Case | Required behaviour |
| --- | --- | --- |
| P1 | Wild-type "substitution" (`X{i}X`) | Score exactly 0.0 — the same log-probability subtracted from itself |
| P2 | A real matched variant | Finite score; reconstructed mutant sequence equals the CSV's `mutated_sequence` |
| N1 | Declared wild-type residue wrong for the position | **Refused** with `ReferenceMismatch` |
| N2 | Position outside 1..428 | **Refused** with `ReferenceMismatch` |

N1 and N2 must raise. A pilot where the negative controls pass silently has not
tested anything, so a non-raising N1 or N2 fails the pilot and stops the run.

## 10. Resource limits and stop rules

- Every step runs under `systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G
  -p MemorySwapMax=0 -p RuntimeMaxSec=600`. `MemorySwapMax=0` is required: this host
  has large swap, so `MemoryMax` alone bounds residency and not the job.
- At most 2 torch threads.
- Combined wall bound **60 minutes**. On exceeding it, stop and report what finished.
- At most **one** retry per network fetch, then stop. A persistent failure or a schema
  mismatch is reviewed and reported, never retried in a loop.
- **No raw GPU job is submitted** from this harness. The evaluation is CPU-local. If a
  GPU became necessary, a request would be written to the shared message directory for
  `dx-gpuops-r1` to submit, and this protocol would be amended first.
- Sponsor service usage is recorded only for a toolkit, service or machine that
  actually executed work.

## 11. Amendments after independent critique

An independent critique of §1–§11 was obtained from Gemini (`gemini-3.1-pro-preview`,
and an earlier accidental call to an image model — see the audit receipts). Its output
is model opinion and every point below was checked here before being acted on.

**When.** The critique arrived while scoring was still running, with 61 of 256 variants
scored and **`analyze.py` never yet executed**: no ρ, no Δρ and no correlation of any
kind existed. So none of these changes could have been chosen to suit an outcome.
**The falsifier in §8 is unchanged**, and the pre-registered variant-level bootstrap
remains the primary interval.

| Raised | Checked | Action |
| --- | --- | --- |
| Batching 4 positions may compute a joint multi-mask marginal | **Refuted.** The code repeats the sequence into 4 rows and masks one position per row. A test now asserts exactly one mask per row against the tensor handed to the model | Test added, no code change |
| Token index off by one because ESM-2 prepends a token *(raised by the image model)* | **Refuted.** §5 states the mapping in 1-based terms, and `_verify_position_mapping` asserts it at three positions; the pilot passed. The later text model agreed the mapping is right | None |
| The orientation check might flip a sign using the data | **Refuted.** It compares mean score by `DMS_score_bin` and returns pass/fail. Nothing in the pipeline flips a sign; the expected sign is positive for both assays | None |
| No null was defined for Δρ, only for each ρ | **Valid.** Both critique runs raised it independently | Added a paired permutation test: rank-transform each assay, then exchange a variant's two values at random. Reported beside the interval |
| A variant-level bootstrap understates variance, since variants at one position are dependent | **Valid and the best point made.** They share a residue, an environment and one forward pass | Added a bootstrap clustered on position. It is the more conservative of the two, so it cannot manufacture support; where they disagree the wider interval governs |
| A step-down to the 150M checkpoint would void the comparison with ProteinGym's 650M reference | **Valid in principle, did not bind.** The pilot projected 21.3 min against a 25-minute threshold, so no step-down occurred and the reported numbers are 650M | Recorded; had it triggered, the external reference would have been void |
| A two-sided 95% interval tests a directional hypothesis at an effective α of 0.025 | **Valid, cosmetic.** | Recorded, not changed. Altering a pre-registered decision rule mid-run is worse than an over-strict one |
| Ties in the assay scores are not addressed | Already handled: ranks use average-tie `rankdata`, cross-checked against `scipy.stats.spearmanr` | Stated |
| What happens to a variant with a missing value is unspecified | **Valid gap.** §8's floor says how many must survive, not what to do with the rest | Rule stated: complete cases only — prediction and *both* outcomes finite — applied identically to both assays, with the dropped list reported |
| Function is biologically downstream of surface expression | **Valid and important.** A channel cannot conduct if it is not at the membrane | Added to §12 as a limitation on interpretation |
| Institutional URL without a DOI; UniProt entries can be revised; the HF checkpoint could move | Valid replication risks | Checksums are recorded for the archive and both members, the UniProt sequence version (`SV=1`) is in the receipt, and the checkpoint id is pinned |

The data-access audit returned `UNVERIFIABLE` for the archive URL and for ProteinGym's
published ESM-2 numbers, which is the honest answer from a model working from memory.
Both were checked here directly instead: the URL returned HTTP 206 with a 43,021,128-byte
archive, and the two reference values were read from the repository's own copy of
ProteinGym's table.

## 12. What this cannot establish

- **The two assays are not independent faculties of the protein.** Channel function is
  measured downstream of surface expression: a variant that never reaches the membrane
  cannot conduct, so the function assay carries the trafficking signal inside it. This
  design therefore cannot separate "the model predicts gating" from "the model predicts
  trafficking, which gating inherits". A difference in ρ between the two assays is
  evidence about the two *measurements*, not about two separable capabilities. Any
  reading of the result that treats function as a clean gating readout is wrong, and
  the assay-to-assay correlation is reported so the dependence is visible.
- Agreement between a sequence model and an assay is not a mechanism, and neither
  assay outcome is a claim about a whole organism.
- The surface and function assays measure different things with different dynamic
  ranges and different noise. A difference in ρ can come from assay precision rather
  than from what the model does or does not represent.
- A 256-variant subset bounds precision. Intervals will be wide and are reported wide.
- Scoring on one protein says nothing general about protein language models.
- ProteinGym's own numbers were read from a table, not reproduced. Any disagreement
  with them is a question to investigate, not a correction issued to ProteinGym.
