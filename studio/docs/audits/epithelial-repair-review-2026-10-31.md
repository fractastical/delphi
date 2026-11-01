# Epithelial-repair independent review

Reviewed original `edc1e107493ece8c6295dabe384b77ea79933f92` and corrected
`66f2b950449fae311ddacf0911eff3fdd5698ad5`. This is a reviewer in the same agent
fleet, not external biological replication. No native solver was rerun and the proposed
240-arm cloud assay was not run or assessed here.

**Disposition:** the count, arithmetic, threshold-bracket and frozen-rule coverage blockers
are corrected in the latter commit. Suitable for a scoped computational project artifact,
with the limitations below. The original runs, failed gates and historical G1b pass remain
available; this review does not convert them into biological evidence.

## What was checked

- [x] Read both frozen protocols, analysis/build/run modules, source/context card and handoff.
- [x] Read all 36 native logger files and 1,476 TIFF frames from the owner's retained
  `.scratch/runs`, rather than relying on the handoff counts. Compared each native model,
  build/run receipt and binary pin against the committed assay; all 36 returned exit 0.
- [x] Recomputed initial cell IDs, volume/gap histories, closure classes and first sampled
  closure times; compared logged gap with medium pixels at every available common time.
- [x] Checked corrected results against the original: every top-level field other than
  `gates` is identical; within gates only G1b changes. Both protocols and all 72 native
  build/run receipt files are byte-identical.
- [x] Ran the corrected owner's focused card checker under 1 CPU, 2 GiB, 128-task bounds:
  **63/63 pins match**, exit 0. This checks published numbers, not prose semantics.

Replay code and native per-file hashes are in
[`audit.py`](../../artifacts/audits/epithelial/audit.py) and
[`source-edc1e10/audit.json`](../../artifacts/audits/epithelial/source-edc1e10/audit.json).
The separate [corrected-source receipt](../../artifacts/audits/epithelial/corrected-source-check.json)
pins the final code/results/card. Raw logs and TIFFs remain in the owner's retained native
run directory; hashes alone are not a substitute for keeping those files backed up.

## Corrected release findings

| Finding | Native/source result | Correct interpretation |
|---|---|---|
| Gate tally | Original JSON: 8 true, 3 false, 2 null; original handoff said 9 passes | Corrected strict tally: **7 pass, 3 fail, G6 descriptive, G1b incomplete, G8 unevaluable** |
| G1b every-frame rule | 756/1,476 frames comparable; 720 lack same-time logger samples; zero shared-time disagreements | Original pass retained as history; full frozen rule **incomplete**, not narrowed to make it pass |
| Actual initialization | Unwounded logger and TIFF contain **65** nonzero cell IDs; 40000/65 = 615.3846 nodes mean | 64 intended seeds and target area 625 do not establish 64 actual cells or a measured mean of 625 |
| Passive control F1 | Gap 2500→1949: **551 nodes / 22.04% filled** | Condition-specific no-J/no-protrusion result with other CPM terms active |
| Passive arithmetic | 61×625 targets imply 38125 occupied / **1875 residual**, **625 filled** nodes | Idealized 25% fill is arithmetic, not a demonstrated mechanism or universal correction |
| J-doubling check G9 | At J=280,k=4, sampled λ=1 closes and λ=2 does not: bracket **[1,2]** | 1.414 is its geometric-mean summary, not a measured point threshold; prior predicted interval [0.6,2] is compatible |

The counts and passive figures above were directly recomputed. Volume-target relaxation is
**consistent with** F1, but no separate causal apportionment was measured: volume, perimeter
and stochastic Metropolis terms remain active. Do not subtract 22 percentage points from
all other arms or describe it as a universal floor. The nominal 26 μm/625-node mapping is
an assumed target-area anchor, not measured cell-size calibration. An alternate mapping
using the realized mean produces a deterministic scale shift, not a measurement confidence
interval.

## Limits that must remain beside the result

- **Model:** an adapted Morpheus 2D Cellular Potts/Act example, not a reproduction of Bai's
  continuum finite-element model or a calibrated epithelial wound. No purse-string cable,
  clinical response, gene program or tissue-to-fish bridge is established. The source card
  distinguishes full-text, abstract-only and inherited/unread sources; retain those levels.
- **Controls:** G1 is gap-complement arithmetic plus integer/nonnegative checks, not an
  independent area-conservation experiment. G1b compares two readout channels of the same
  engine, not independent model/biology. G4, G10 and G12 remain failed; G6 has no threshold.
- **Prediction:** G9 is one internal held-out *parameter setting* at k=4, seed 1, using a prior
  simulated bracket. It does not validate exact proportionality over J, k=7 transfer or an
  observed biological law. The balance argument is a heuristic for a CPM with other terms.
- **Gap-size failure:** k=1 still closes at λ=5000, so its absent arrest bracket and the
  declared G12 failure remain. The k=4 and k=7 Φ bracket intervals overlap
  (3.016–4.129); their 2.43 midpoint ratio alone cannot establish incompatibility of those
  two intervals. Preserve the actual k=1 counterevidence rather than rescuing the criterion.
- **Time:** A1 first logged closure at model time 240 with mcs_duration=1 and C3 at 120 with
  mcs_duration=0.5 both correspond to 240 sweeps. This is sampled model-time
  reparameterization, not a physical-minute calibration or standard time-step convergence.
  CLOSED means reaching zero by the 1000-model-unit horizon; ARRESTED is operational
  nonclosure by that horizon, not proof of permanent arrest.
- **Outputs:** curve-shape R² is model-curve agreement, not an observed-data fit. The
  `mechanical_cost` field is a CPM energy proxy, not measured stress, force, ATP or work.

No remaining release blocker was found in the corrected count/bracket/arithmetic/coverage
items. These scope qualifications govern captions and graph claims; passing the numerical
checks cannot supply missing biological validation.

## Integrated visual bundle

Also inspected owner06 integration `5b623ceadc4f09bd978225001de92df77da1d1d8`:
all 19 epithelial source/renderer/media size and SHA pins match actual Git bytes. Its typed
summary preserves 7 passes, 3 failures, descriptive G6, incomplete G1b, unevaluable G8,
original history, [1,2] observed bracket and 22.04% matched-condition control. The reading
note carries the finite-horizon and overlapping-interval qualifications. This is a source
and manifest check, not a browser/movie replay of that commit. No additional scientific
release blocker found. Minor wording polish: replace the passive summary's causal “as
surviving cells relax” with “consistent with surviving-cell relaxation”; the final sentence
already says no isolated mechanism contribution was measured. Its stale “25% arithmetic
under review” note can now point to the corrected filled/residual distinction.
