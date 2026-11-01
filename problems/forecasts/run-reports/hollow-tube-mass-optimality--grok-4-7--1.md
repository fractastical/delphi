# Hollow tube mass at fixed bending stiffness (Lean)

- Target: `thompson1917-ch16-03` (hollow tubes resist bending). `thompson1917-ch16-04` is
  marked not-formalized here: its thickness–moment law is already in `ThompsonLaws.Mechanics`.
- Artifact: `claim-sources/thompson-growth-form/lean/ThompsonLaws/HollowTube.lean`, report
  `lean/reports/HollowTube.json`. Checked with `lake env lean`; no sorry; every theorem's
  `#print axioms` lists only `propext`, `Classical.choice`, `Quot.sound`.
- Model: outer radius R, ratio k = r_in/R in [0, 1), second moment I = (π/4)R⁴(1 − k⁴) held
  fixed, wall density ρ, core density qρ.
- Proved: wall area at fixed I equals `√(4πI)·√((1−k²)/(1+k²))` (`tubeArea_fixedStiffness`),
  the factor is strictly decreasing on [0, 1] (`gasCoreAreaFactor_strictAntiOn`), so of two
  equally stiff tubes the hollower one has less wall, and with a gas core no k in [0, 1) is a
  minimum (`gasCore_no_interior_min`). The approach's formula was correct as stated.
- Core density: mass = `ρ√(4πI)·μ(k)` with `μ(k) = (1 − k² + qk²)/√(1 − k⁴)`
  (`tubeMass_fixedStiffness`). Derivative proved as
  `μ'(k) = 2k(k² − (1 − q))/((1 − k⁴)√(1 − k⁴))` (`massFactor_hasDerivAt`).
- Stationarity: for 0 < k < 1, `μ'(k) = 0 ⇔ k² = 1 − q`. An interior critical point exists
  iff `0 < q < 1` (`interior_critical_exists_iff`); the interval is open at both ends.
- It is a minimum: for 0 < q < 1, `k* = √(1 − q)` is the unique global minimizer on [0, 1),
  with `μ(k*) = √(q(2 − q))`; proof via `(1−pk²)² − (1−p²)(1−k⁴) = (k² − p)²`, p = 1 − q.
  For q ≥ 1 the solid rod (k = 0) is optimal.
- Buckling as `t/R = 1 − k ≥ λ` (λ = Cσ/E, C left a parameter): the constrained optimum is
  `min(√(1 − q), 1 − λ)` (`constrained_optimum`); with a gas core it is the boundary 1 − λ.
- The approach's failure signature did not occur: the critical point exists and is a minimum.
- Does not settle the problem: whether bones, culms and rachises sit at k*, at the buckling
  bound, or elsewhere needs the pre-registered morphometry comparison; C and q are empirical.
- No data, no commits, nothing published.
