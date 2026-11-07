/-
# Turing (1952): the linear condition for diffusion-driven instability

Claim `turing-ddi` in `claim-sources/math-bio-claims/claims/key-claims.json`:

> A homogeneous steady state of two reacting chemicals that is stable without diffusion can become
> unstable to spatial perturbations when the chemicals diffuse at different rates, spontaneously
> producing a pattern.
> With tr J < 0 and det J > 0, instability at some wavenumber k iff D_v f_u + D_u g_v > 2 √(D_u D_v det J),
> which requires D_u ≠ D_v.

Source: Turing, A. M. (1952). The chemical basis of morphogenesis. Phil. Trans. R. Soc. B 237, 37–72.
doi:10.1098/rstb.1952.0012.

## What is proved here, and from what

The model is the linearisation of a two-species reaction–diffusion system about a spatially uniform
steady state: Jacobian `J = ![![a, b], ![c, d]]` and diffusivities `Du, Dv > 0`. A spatial mode with
squared wavenumber `q ≥ 0` grows according to the matrix `J - q · diag(Du, Dv)`, whose determinant is
the quadratic

  `D(q) = Du·Dv·q² − (Dv·a + Du·d)·q + (a·d − b·c)`.

When the uniform state is stable without diffusion (`a + d < 0`, `a·d − b·c > 0`, `WellMixedStable`),
the mode matrix has negative trace for every `q ≥ 0`, so the mode is linearly unstable exactly when
`D(q) < 0` (one real eigenvalue is then positive). Theorem `turing_instability_iff` is Turing's
condition in that form:

  `WellMixedStable S → ((∃ q > 0, D S q < 0) ↔ 2·√(Du·Dv·(a·d − b·c)) < Dv·a + Du·d)`.

The proof is the minimum of the quadratic: at `q* = (Dv·a + Du·d)/(2·Du·Dv)` its value is
`(a·d − b·c) − (Dv·a + Du·d)²/(4·Du·Dv)`, negative iff the right-hand side holds (the sign condition on
`Dv·a + Du·d` is forced because `q* > 0` is needed).

Corollary `no_instability_of_equal_diffusivity`: with `Du = Dv` and the uniform state stable, no mode
is unstable. This is the "requires D_u ≠ D_v" clause of the claim, and it is a **two-species** result: with
three or more species Turing instability with equal diffusivities is possible (Marcon et al. 2016,
doi:10.7554/eLife.14022), so this corollary must not be applied to larger networks.

`Instance` bundles a concrete system (`J = ![![1, −2], ![2, −3]]`, `Du = 1`, `Dv = 10`) that is stable
without diffusion and unstable at `q = 1/4`; `witness` shows the hypotheses of the theorem are satisfiable
and the instability side is realised.

## What is not proved here

* Nothing about organisms: that a tissue is governed by such a system, or which chemicals `u, v` are, is
  the empirical question of the `turing-1952-*` instance claims and `turing-morphogen-hypothesis`.
* Nothing nonlinear: existence, selection and stability of the finite-amplitude pattern are model-specific
  and outside this file (the claim's `formalization.note` says they are not a reading of `turing-ddi`).
* Nothing about finite domains: on a bounded domain only a discrete set of `q` is admissible, so the
  continuum condition proved here is necessary and not sufficient for a pattern on a given domain
  (see `studio/lean/Admissible.lean`).

No `sorry`, no additional axioms: see `lean/Delphi/Audit.lean` and the build report.
-/
import Mathlib
/-!
## Biolib · Morphogenesis: how cells, tissues and shells take their form

Origin: `lean/Delphi/Turing.lean` in fractastical/delphi_private at `ffdc528e4f95`, copied by
`biolib/scripts/sync-from-delphi.py`. Edit it there; this copy is regenerated.
Registry laws: `turing-ddi-linear-condition` (candidate, v1.0.0).
Lean-checked claims: none.
-/


namespace Delphi.Turing

/-- The linearisation of a two-species reaction–diffusion system at a uniform steady state:
Jacobian `![![a, b], ![c, d]]` and diffusivities `Du, Dv > 0`. -/
structure TuringSystem where
  a : ℝ
  b : ℝ
  c : ℝ
  d : ℝ
  Du : ℝ
  Dv : ℝ
  hDu : 0 < Du
  hDv : 0 < Dv

variable (S : TuringSystem)

/-- Determinant of the mode-`q` growth matrix `J - q · diag(Du, Dv)`, a quadratic in `q`. -/
def D (q : ℝ) : ℝ := S.Du * S.Dv * q ^ 2 - (S.Dv * S.a + S.Du * S.d) * q + (S.a * S.d - S.b * S.c)

/-- Trace of the mode-`q` growth matrix. -/
def T (q : ℝ) : ℝ := (S.a + S.d) - (S.Du + S.Dv) * q

/-- Stability of the uniform state without diffusion: negative trace, positive determinant. -/
def WellMixedStable : Prop := S.a + S.d < 0 ∧ 0 < S.a * S.d - S.b * S.c

/-- With the uniform state stable, every mode `q ≥ 0` has negative trace, so a mode is unstable exactly
when its determinant is negative. -/
theorem trace_neg_of_wellMixed (h : WellMixedStable S) {q : ℝ} (hq : 0 ≤ q) : T S q < 0 := by
  have hD : 0 < S.Du + S.Dv := by have := S.hDu; have := S.hDv; linarith
  have : 0 ≤ (S.Du + S.Dv) * q := by positivity
  unfold T; linarith [h.1]

/-- A mode with negative determinant has a positive real growth rate (a positive root of the
characteristic polynomial `λ² − T·λ + D`). -/
theorem exists_pos_growth_of_D_neg {q : ℝ} (h : D S q < 0) :
    ∃ lam : ℝ, 0 < lam ∧ lam ^ 2 - T S q * lam + D S q = 0 := by
  have hdisc : 0 ≤ T S q ^ 2 - 4 * D S q := by nlinarith [sq_nonneg (T S q)]
  refine ⟨(T S q + Real.sqrt (T S q ^ 2 - 4 * D S q)) / 2, ?_, ?_⟩
  · have hsq := Real.sq_sqrt hdisc
    have hs0 := Real.sqrt_nonneg (T S q ^ 2 - 4 * D S q)
    have hlt : |T S q| < Real.sqrt (T S q ^ 2 - 4 * D S q) := by
      apply abs_lt_of_sq_lt_sq _ hs0
      nlinarith
    have := neg_abs_le (T S q)
    linarith [abs_lt.mp hlt]
  · have hsq := Real.sq_sqrt hdisc
    nlinarith [hsq]

/-- **Turing's condition** (1952, §6–8; Murray's `(D_v f_u + D_u g_v)² > 4 D_u D_v det J` with the sign
condition). With the uniform state stable, some mode `q > 0` is unstable iff
`2·√(Du·Dv·det J) < Dv·a + Du·d`. -/
theorem turing_instability_iff (h : WellMixedStable S) :
    (∃ q : ℝ, 0 < q ∧ D S q < 0) ↔
      2 * Real.sqrt (S.Du * S.Dv * (S.a * S.d - S.b * S.c)) < S.Dv * S.a + S.Du * S.d := by
  obtain ⟨_, hdet⟩ := h
  have hm : 0 < S.Du * S.Dv := mul_pos S.hDu S.hDv
  have hmd : 0 ≤ S.Du * S.Dv * (S.a * S.d - S.b * S.c) := by positivity
  set P := S.Dv * S.a + S.Du * S.d with hP
  set m := S.Du * S.Dv with hmdef
  set Δ := S.a * S.d - S.b * S.c with hΔ
  have hDq : ∀ q, D S q = m * q ^ 2 - P * q + Δ := fun q => rfl
  constructor
  · rintro ⟨q, hq, hneg⟩
    rw [hDq] at hneg
    -- P > 0, since m q² + Δ > 0 and P q exceeds it.
    have hPpos : 0 < P := by
      by_contra hle; push Not at hle
      have : 0 ≤ -P * q := by nlinarith
      nlinarith [sq_nonneg q]
    -- discriminant: 4 m D(q) = (2 m q − P)² − (P² − 4 m Δ) < 0
    have hdisc : 4 * m * Δ < P ^ 2 := by nlinarith [sq_nonneg (2 * m * q - P)]
    -- √(mΔ) < P/2
    have : Real.sqrt (m * Δ) < P / 2 := by
      rw [Real.sqrt_lt' (by linarith)]
      nlinarith
    linarith
  · intro hlt
    have hs0 := Real.sqrt_nonneg (m * Δ)
    have hPpos : 0 < P := by linarith
    have hsq := Real.sq_sqrt hmd
    have hdisc : 4 * m * Δ < P ^ 2 := by nlinarith
    refine ⟨P / (2 * m), by positivity, ?_⟩
    rw [hDq]
    have h2m : (2 * m) ≠ 0 := by positivity
    have : m * (P / (2 * m)) ^ 2 - P * (P / (2 * m)) + Δ = Δ - P ^ 2 / (4 * m) := by
      field_simp; ring
    rw [this]
    have : P ^ 2 / (4 * m) > Δ := by
      rw [gt_iff_lt, lt_div_iff₀ (by positivity)]; linarith
    linarith

/-- **Equal diffusivities never destabilise a stable uniform state (two species).** With `Du = Dv` the
mode determinant is `Du²·q² − Du·(a+d)·q + det J`, every term of which is nonnegative for `q ≥ 0`
and the last positive. This is the "requires `D_u ≠ D_v`" clause of `turing-ddi`; it does **not** extend
to three or more species. -/
theorem no_instability_of_equal_diffusivity (h : WellMixedStable S) (heq : S.Du = S.Dv) {q : ℝ}
    (hq : 0 ≤ q) : 0 < D S q := by
  obtain ⟨htr, hdet⟩ := h
  have hDu := S.hDu
  unfold D
  rw [← heq]
  have h1 : 0 ≤ S.Du * S.Du * q ^ 2 := by positivity
  have h2 : 0 ≤ -(S.Du * S.a + S.Du * S.d) * q := by
    have : -(S.Du * S.a + S.Du * S.d) * q = (S.Du * q) * (-(S.a + S.d)) := by ring
    rw [this]
    exact mul_nonneg (mul_nonneg hDu.le hq) (by linarith)
  nlinarith

/-- A concrete system satisfying the hypotheses of `turing_instability_iff` together with an unstable
mode: `J = ![![1, −2], ![2, −3]]`, `Du = 1`, `Dv = 10`, `q = 1/4`. -/
structure Instance where
  S : TuringSystem
  stable : WellMixedStable S
  q : ℝ
  q_pos : 0 < q
  unstable : D S q < 0

/-- The worked system of Turing's §10-style example: trace `−2`, determinant `1`, and
`D(1/4) = 10/16 − 7/4 + 1 = −1/8`. -/
noncomputable def worked : TuringSystem :=
  { a := 1, b := -2, c := 2, d := -3, Du := 1, Dv := 10, hDu := by norm_num, hDv := by norm_num }

/-- Non-vacuity witness: the hypotheses of `turing_instability_iff` are satisfiable and the unstable side
is realised. -/
theorem witness : Nonempty Instance :=
  ⟨{ S := worked
     stable := by simp only [WellMixedStable, worked]; norm_num
     q := 1 / 4
     q_pos := by norm_num
     unstable := by simp only [D, worked]; norm_num }⟩

/-- The witness also satisfies the right-hand side of the iff, as it must: `2·√10 < 7`. -/
theorem witness_condition :
    2 * Real.sqrt (worked.Du * worked.Dv * (worked.a * worked.d - worked.b * worked.c)) <
      worked.Dv * worked.a + worked.Du * worked.d := by
  have hwm : WellMixedStable worked := by simp only [WellMixedStable, worked]; norm_num
  exact (turing_instability_iff worked hwm).mp ⟨1 / 4, by norm_num, by simp only [D, worked]; norm_num⟩

end Delphi.Turing
