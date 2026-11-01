# Murray's cubic law from a stated cost (Lean)

- Target: `thompson1917-ch15-13` (minimum effort); `thompson1917-ch16-03` is not about flow and
  is marked not-formalized here (it is covered by `ThompsonLaws.HollowTube`).
- Artifact: `claim-sources/thompson-growth-form/lean/ThompsonLaws/MurrayCubic.lean`, report
  `lean/reports/MurrayCubic.json`. Checked with `lake env lean`; no sorry; every theorem's
  `#print axioms` lists only `propext`, `Classical.choice`, `Quot.sound`.
- Proved: for cost `k Q²/r⁴ + m r²` the stationary radius (`m r⁶ = 2kQ²`) is the strict global
  minimizer over `r > 0`, any minimizer has `r³ = √(2k/m)·Q`, and at a junction with
  `Q₀ = Q₁ + Q₂` and shared constants `r₀³ = r₁³ + r₂³` (`murray_junction`).
- Generalized to cost `k Q^a/r^b + m r^c` (a, b, c > 0, real exponents): unique global
  minimizer, `r^((b+c)/a) ∝ Q`, and the junction law with exponent `(b+c)/a` (`junction_law`).
  The approach's `(b+2)/a` is the case `c = 2`; a wall-surface cost (`c = 1`) gives `5/2`.
- Correction to the approach: `(b+2)/a = 7/3` holds on the whole line `3b + 6 = 7a`, so the
  pair is not unique; `(3, 5)` and `(6, 12)` both give `7/3` (`seven_thirds_not_unique`).
  Over naturals the solutions are `a = 3t, b = 7t − 2`, `(3, 5)` the smallest.
- Uniqueness recovered from a stated friction law: Darcy–Weisbach power with friction factor
  `∝ Re^(−β)` equals `κ Q^(3−β)/r^(5−β)` (`darcyPower_eq`), and along that family the exponent
  `(7−β)/(3−β)` is `7/3` iff `β = 0` (Reynolds-independent, fully rough friction), i.e.
  `(a, b) = (3, 5)`. Laminar `β = 1` gives 3; Blasius `β = 1/4` gives 27/11, not 7/3.
- So the algebra does not support calling 7/3 "the turbulent exponent" in general: it needs
  a friction factor independent of Reynolds number, which smooth-pipe turbulence is not.
- Physical assumptions are hypotheses: shared constants across the junction, flow
  conservation, each vessel minimizing its own cost; branching angles are not treated.
- Does not settle the problem: whether real vasculature obeys exponent 3 (or 7/3) is the
  data test (approaches 2 and 3); this run only fixes what each hypothesis predicts.
- No data, no commits, nothing published.
