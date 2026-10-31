# Paired fin-ray assurance experiment

This reuses the existing fin-mechanics beam solver. It measures numerical error,
parameter sensitivity and load-shape discrepancy in a declared linear model.
Empirical accuracy and biological success probability remain unknown.

- [x] Commit the protocol before producing assay outputs.
- [x] Separate source-context bluegill EI from assumed design EI.
- [x] Pair common correlated draws across three retained candidates.
- [x] Predeclare deflection/slope limits and preserve counterexamples.
- [x] Implement analytic, grid, null and altered-speed-law controls.
- [x] Run the committed code and render pinned numerical outputs.
- [ ] Obtain matched held-out measurements and biological transfer evidence.

`protocol.json` predeclares64 independent latent vectors, seed, transforms,
candidate dimensions, both-load-shape predicate, interval interpretation and stop
bounds. Weather/geometry inputs are correlated within draws. The same draws are
shared across candidates. Uniform versus same-total-tip loading and coarse versus
fine meshes are paired calculations, never extra independent trials. Local
sensitivity perturbs one physical input at a time; it is not biological causality
or a variance decomposition under the correlated sampling law.

Source context: Alben, Madden & Lauder, [doi:10.1098/rsif.2006.0181](https://pmc.ncbi.nlm.nih.gov/articles/PMC2359861/),
Section3.4 reports an approximate composite E range and average I yielding
EI~1e-6–1e-5N m². Sampling that envelope log-uniformly is our assumption, not an
empirical distribution. The target candidates use a separate assumed EI envelope.
The paper's Fig7 contains a measured1.98N/m slope under specific hemitrich clamps;
without a matched geometry/material/actuation tuple, it cannot validate this
single-beam surrogate. Neither that datum nor our own analytic solution is treated
as held-out biological validation. This session read the primary PMC text and
retrieved HTML, sha256342a3ee139d323c52227bf41915b95b20e3dde72190729e8580c7a1141853406.

The endpoint requires tip/L≤.1 and max slope≤.2rad under BOTH named load shapes.
Outside-envelope linear outputs remain saved as extrapolations. Uniform-versus-tip
difference is a model-choice sensitivity, not a calibrated physical error bound.
Static mechanics has no timestep; the variation video indexes ensemble members.
Regional fields identify pectoral fins only as UI annotations. A clamped-base zero
does not become high biological confidence.

Run `python -m engineering.assurance_experiments.experiment --output
artifacts/assurance-experiments` only after committing numerical code. The runner
verifies the protocol's git bytes and refuses dirty model/assay code. Use the
documented bounded systemd scope (4G, no swap, TasksMax128, RuntimeMaxSec600), and
BLAS/OpenMP threads≤2. CPU is appropriate; this sparse small-beam assay has no
useful GPU algorithm to dispatch merely for occupancy.

Every candidate receives `frontier.assurance.ensemble/1`, pinned per-run input and
protocol digests, saved metrics, numerator/denominator, and a conditional Wilson
interval over the declared sampling law. These are not biological success odds.
All three candidates remain available. Next steps measure EI(x), spatial loading,
and mass/lifting-area costs before selecting a design.
