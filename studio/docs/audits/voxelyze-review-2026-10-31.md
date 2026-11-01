# Independent bounded Voxelyze review

Reviewed original CPU outputs at `e6f10331a8cf69aed88d490efe5f926ebfbff818`
and corrected reporting at **1be6dcb6d8b31ce2507efb194b5827525d1658a7**.
No owner files, frozen thresholds or original outputs were changed by this
reviewer. The protocol bytes match frozen commit `7b9bd5d`; it explicitly records
earlier developmental settling observations. GPU-probe work is outside scope.

## Result and required corrections

No numerical-data blocker was found in these checks. The required scale,
normalization, post-hoc and rendering qualifications are present in corrected
`1be6dcb`. Only the summary changed within the audited output/driver tree; raw
trajectories, control records, driver source and protocol remain byte-identical.
The artifact may be linked as a **generic numerical mechanics tool** to the
proposed microcarrier project. It supplies no tissue calibration or biological
transfer, and does not establish a project-specific biological runner.

| Post-hoc travelling comparison | Coarse | Fine |
| --- | ---: | ---: |
| Horizontal COM displacement | 14.577281 mm | 16.847525 mm |
| Stored normalization, center span | 40 mm | 45 mm |
| Center-span-normalized displacement | 0.364432 | 0.374389 |
| Nominal outer envelope | 50×30×30 mm | 50×30×30 mm |
| Nominal mass at assumed density | 45 g | 45 g |

The earlier approximately 2.74% comparison used changing denominators; using the
stored six-decimal normalized values gives 2.7322%. Raw SI displacement differs
**15.5739% relative to coarse**. A common 50 mm denominator preserves that same
15.5739% difference. The corrected summary withdraws the earlier agreement claim.
Neither comparison establishes spatial convergence. This is a 45 g soft-voxel
ground-contact benchmark, not a Xenopus-scale construct, tissue or microcarrier.
Material values come from a generic example; prescribed thermal expansion is not
measured cellular contractility.

## Executed checks

- Read and arithmetically checked **24 simulation JSON records** (23 analysis
  runs plus one animation repeat) and **11 analytic records**. JSON endpoints,
  normalization, finite sampled states, frame counts/times and horizontal sampled
  path lengths agree within bounds derived from printed precision.
- Checked **241×45 saved voxel centers** against saved COM. Maximum component
  difference between their arithmetic mean and recorded COM is `5.78e-10 m`.
- Freshly built upstream Voxelyze
  `4287e365e11416dd108f2f361e9ec4c5a011a16c` with the committed recipe: exit 0,
  12.60 s, g++ 13.3.0. No system packages or GPU were used; binaries stay private.
- Independently reran **P1, P2, M1, M2, M3, D and E** in approximately 1.26 s.
  All seven numeric records match originals exactly; D/E comparisons exclude
  output-path metadata only. The positive analytic controls pass; three wrong
  analytic-reference controls fail while settled. These mutants change reference
  expectations, not the upstream engine implementation.
- E still **fails** its frozen bound: 0.017479 center-span units versus 0.01.
  Process exit 0 means simulation completion, not passing that scientific check.
  Removing gravity did not remove actuation-induced floor reaction/friction.
- G retains a large spatial discrepancy: 8.16× in its changing center-span
  normalization, 7.25× in raw SI displacement. It remains unresolved; its protocol
  predicted no convergence rather than declaring a convergence-pass threshold.
  The three longer settling diagnostics remain unsettled, not passed controls.

The frictionless D trace has zero sampled horizontal range at nine-decimal
precision while vertical COM varies 1.050384 mm and imposed drive spans 19.9902
degrees C. This is an active run, not a dead control. The
[pinned engine force code](https://github.com/jonhiller/Voxelyze/blob/4287e365e11416dd108f2f361e9ec4c5a011a16c/src/VX_Voxel.cpp)
uses absolute-frame `-C*v` damping. With homogeneous nominal mass/coefficient,
no horizontal contact friction and zero initial COM velocity, the horizontal COM
limit is consistent with that source law. It is not swimming or a fluid model.

## Interpretation qualifications, not new acceptance criteria

These do not invalidate the saved numerical states, but stronger summary wording
must not be repeated as an established result:

- Six-pattern displacement spread is **4.2277 orders**, about `1.69e4`, rather
  than approximately five orders.
- The parity series also changes body length, mass and total damping. It supports
  a layout/parity-associated diagnostic; it does not isolate the causal fraction
  of G's discrepancy. Travelling is only one post-hoc pattern on two grids.
- Fine-grid displacement first decreases between damping 0 and 0.025, then
  increases. The trend is not strictly monotonic. Higher travel under damping
  does not mean `-C*v` is not drag; it contradicts only the simple account that
  additional damping alone explains the grid gap. At fixed dimensionless damping,
  summed global damping also changes from 9 to 18 kg/s across these grids.

No mechanical work/energy or force history was saved, so no efficiency or
mechanism-contribution fraction is established. No extra graph Claim-consumption
event, empirical validation or independent biological replication is inferred.

## Rendering and licensing

CSV fields contain **centers and imposed temperature**, not voxel orientations,
deformed surfaces, forces, tractions or cellular state. Render actual centers,
links or clearly nominal glyphs with SI scale; do not create cell textures or
tissue boundaries. The exact JSON measurement window is approximately
0.24997285–1.49993836 s; saved measurement frames span 0.255442–1.495026 s.
The trace omits exact endpoints. Keep full-run JSON metrics separate from the
last sampled frame; do not interpolate or teleport states to match a headline.

All **24 top-level upstream CPP/H files** checked declare LGPL-3.0-or-later;
the pinned repository has no root LICENSE file. The separate project code site
[noncommercial notice](https://cdorgs.github.io/code) and pinned
[voxcraft-sim CC0 file](https://github.com/voxcraft/voxcraft-sim/blob/dd8668f99ff74fb2fc2ee60deb91287a3b519d8f/LICENSE)
were both retrieved. Preserve their distinct scopes/conflict; do not flatten the
compiled Voxelyze library into CC0. Other vendored dependencies were not audited.
No linked binary is published by this review; source caches remain private.

Exact source/output hashes, replay arguments, fresh binary hashes and licence
readings are under `artifacts/audits/xenobot/`. Checks ran under 1 CPU, 2 GiB,
128 tasks and 600-second tree bounds. Focused Ruff passed; no full assay, full
test suite, model inference or cloud job was run. Dollars remain unknown.
