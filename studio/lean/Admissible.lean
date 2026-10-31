/-
  Admissible — finite-domain admissibility for diffusion-driven (Turing) instability.

  Formalised over ℝ with Mathlib.  The point of this file is the gap between the
  CONTINUUM Turing conditions (stated over all real wavenumbers) and what a FINITE
  domain with zero-flux boundaries actually admits (a discrete set of modes).
-/
import Mathlib.Analysis.SpecialFunctions.Pow.Real
import Mathlib.Tactic

namespace Admissible

/-- A two-species reaction-diffusion linearisation: Jacobian `![![a,b],![c,d]]`
    at a spatially uniform steady state, with diffusivities `Du, Dv > 0`. -/
structure System where
  a : ℝ
  b : ℝ
  c : ℝ
  d : ℝ
  Du : ℝ
  Dv : ℝ
  hDu : 0 < Du
  hDv : 0 < Dv

variable (S : System)

/-- Trace of the mode-`q` growth matrix `J - q·diag(Du,Dv)`. -/
def T (q : ℝ) : ℝ := (S.a + S.d) - (S.Du + S.Dv) * q

/-- Determinant of the mode-`q` growth matrix: a quadratic in `q`. -/
def D (q : ℝ) : ℝ := S.Du * S.Dv * q^2 - (S.Dv * S.a + S.Du * S.d) * q + (S.a * S.d - S.b * S.c)

/-- The determinant is the product form used throughout the literature. -/
theorem D_eq (q : ℝ) :
    D S q = (S.Du * q - S.a) * (S.Dv * q - S.d) - S.b * S.c := by
  unfold D; ring

/-- A mode `q` is *unstable* when the growth determinant is negative: the quadratic
    `λ² - T λ + D` then has one positive real root regardless of the sign of `T`. -/
def Unstable (q : ℝ) : Prop := D S q < 0

/-- ONE direction only: with a negative trace, a positive root of the mode polynomial forces `D q < 0`.
    (Renamed from `unstable_iff_pos_eigenvalue`, which promised an "iff" it did not prove; the converse is
    `exists_pos_eigenvalue_of_unstable` below, and the real iff is `unstable_iff_exists_pos_eigenvalue`.) -/
theorem unstable_of_pos_eigenvalue (q lam : ℝ) (hT : T S q < 0)
    (hroot : lam^2 - T S q * lam + D S q = 0) (hpos : 0 < lam) : Unstable S q := by
  unfold Unstable
  nlinarith [sq_nonneg lam, sq_nonneg (lam - T S q)]

/-- The converse, with NO trace hypothesis: `D q < 0` always yields a positive real root of
    `lam^2 - T lam + D = 0`, namely `(T + sqrt (T^2 - 4 D)) / 2`. -/
theorem exists_pos_eigenvalue_of_unstable (q : ℝ) (h : Unstable S q) :
    ∃ lam : ℝ, 0 < lam ∧ lam^2 - T S q * lam + D S q = 0 := by
  unfold Unstable at h
  have hdisc : 0 ≤ T S q ^ 2 - 4 * D S q := by nlinarith [sq_nonneg (T S q)]
  refine ⟨(T S q + Real.sqrt (T S q ^ 2 - 4 * D S q)) / 2, ?_, ?_⟩
  · have hsq : Real.sqrt (T S q ^ 2 - 4 * D S q) ^ 2 = T S q ^ 2 - 4 * D S q := Real.sq_sqrt hdisc
    have hs0 : 0 ≤ Real.sqrt (T S q ^ 2 - 4 * D S q) := Real.sqrt_nonneg _
    have hlt : |T S q| < Real.sqrt (T S q ^ 2 - 4 * D S q) := by
      apply abs_lt_of_sq_lt_sq _ hs0
      nlinarith
    have := neg_abs_le (T S q)
    linarith [abs_lt.mp hlt]
  · have hsq : Real.sqrt (T S q ^ 2 - 4 * D S q) ^ 2 = T S q ^ 2 - 4 * D S q := Real.sq_sqrt hdisc
    nlinarith [hsq]

/-- **The honest iff.** With a negative trace, the mode is unstable exactly when the mode polynomial has a
    positive real root. The trace hypothesis is necessary: see `trace_hypothesis_needed`. -/
theorem unstable_iff_exists_pos_eigenvalue (q : ℝ) (hT : T S q < 0) :
    Unstable S q ↔ ∃ lam : ℝ, 0 < lam ∧ lam^2 - T S q * lam + D S q = 0 := by
  constructor
  · exact exists_pos_eigenvalue_of_unstable S q
  · rintro ⟨lam, hpos, hroot⟩
    exact unstable_of_pos_eigenvalue S q lam hT hroot hpos

/-- Why `hT` cannot be dropped: with trace `3 > 0` and determinant `2 > 0` the polynomial `lam^2 - 3 lam + 2`
    has the positive root `1`, yet the determinant is not negative. -/
theorem trace_hypothesis_needed :
    ∃ T D lam : ℝ, 0 < T ∧ 0 < D ∧ 0 < lam ∧ lam^2 - T * lam + D = 0 :=
  ⟨3, 2, 1, by norm_num, by norm_num, by norm_num, by norm_num⟩

/-- **Uniform-state stability**: with no diffusion the steady state is stable. -/
def WellMixedStable : Prop := S.a + S.d < 0 ∧ 0 < S.a * S.d - S.b * S.c

/-- The classical continuum condition for diffusion-driven instability: the minimum of the
    determinant over all real `q ≥ 0` is negative. -/
def ContinuumTuring : Prop :=
  0 < S.Dv * S.a + S.Du * S.d ∧
  (S.Dv * S.a + S.Du * S.d)^2 > 4 * (S.Du * S.Dv) * (S.a * S.d - S.b * S.c)

/-- Zero-flux (Neumann) modes on `[0, L]` are `q_n = (n π / L)²`. -/
noncomputable def neumannMode (L : ℝ) (n : ℕ) : ℝ := ((n : ℝ) * Real.pi / L)^2

/-- The admissible modes are nonnegative. -/
theorem neumannMode_nonneg (L : ℝ) (n : ℕ) : 0 ≤ neumannMode L n := by
  unfold neumannMode; positivity

/-- Linear asymptotic stability of a 2x2 mode: negative trace and positive determinant.
    This is the real stability predicate; `¬ Unstable` alone is strictly weaker. -/
def ModeStable (q : ℝ) : Prop := T S q < 0 ∧ 0 < D S q

/-- The trace is negative at EVERY nonnegative mode whenever the well-mixed trace is.
    Not vacuous: it uses `Du + Dv > 0` and `q ≥ 0`. -/
theorem trace_neg_of_wellmixed (hwm : WellMixedStable S) {q : ℝ} (hq : 0 ≤ q) :
    T S q < 0 := by
  have hD : 0 < S.Du + S.Dv := by have := S.hDu; have := S.hDv; linarith
  have h1 : S.a + S.d < 0 := hwm.1
  have h2 : 0 ≤ (S.Du + S.Dv) * q := by positivity
  unfold T; linarith

/-- **The finite-domain theorem, stated as actual linear stability.**
    If the well-mixed state is stable and every admissible Neumann mode has STRICTLY POSITIVE
    growth determinant, then every admissible mode is linearly asymptotically stable — both
    eigenvalues have negative real part.  The determinant hypothesis is a genuine assumption
    about the mode set, and the trace conclusion is derived, not assumed. -/
theorem finite_domain_linearly_stable (L : ℝ)
    (hwm : WellMixedStable S)
    (hdet : ∀ n : ℕ, 0 < D S (neumannMode L n)) :
    ∀ n : ℕ, ModeStable S (neumannMode L n) := by
  intro n
  exact ⟨trace_neg_of_wellmixed S hwm (neumannMode_nonneg L n), hdet n⟩

/-- Both eigenvalues of a 2x2 matrix with negative trace and positive determinant have
    negative real part: any real eigenvalue is negative.  This is what `ModeStable` buys. -/
theorem real_eigenvalue_neg_of_modeStable {q lam : ℝ} (h : ModeStable S q)
    (hroot : lam^2 - T S q * lam + D S q = 0) : lam < 0 := by
  obtain ⟨hT, hDpos⟩ := h
  by_contra hge
  push_neg at hge
  nlinarith [sq_nonneg lam]

/-- The worked instance: `J = ![![1,-2],![2,-3]]`, `Du = 1`, `Dv = 10`. -/
noncomputable def worked : System :=
  { a := 1, b := -2, c := 2, d := -3, Du := 1, Dv := 10, hDu := by norm_num, hDv := by norm_num }

/-- Its determinant factors as `(5q-1)(2q-1)`, so the instability band is `1/5 < q < 1/2`. -/
theorem worked_D (q : ℝ) : D worked q = (5*q - 1) * (2*q - 1) := by
  simp only [D, worked]
  ring

/-- The well-mixed state is stable: trace `-2 < 0`, determinant `1 > 0`. -/
theorem worked_wellmixed : WellMixedStable worked := by
  simp only [WellMixedStable, worked]
  norm_num

/-- The continuum Turing conditions DO hold for the worked system:
    `Dv·a + Du·d = 7 > 0` and `49 > 4·10·1 = 40`. -/
theorem worked_continuum : ContinuumTuring worked := by
  simp only [ContinuumTuring, worked]
  norm_num

/-- A mode is unstable exactly when it lies strictly inside `(1/5, 1/2)`. -/
theorem worked_unstable_iff (q : ℝ) : Unstable worked q ↔ (1/5 < q ∧ q < 1/2) := by
  unfold Unstable
  rw [worked_D]
  constructor
  · intro h; constructor <;> nlinarith
  · rintro ⟨h1, h2⟩; nlinarith

/-- On `L = π` the admissible modes are `q = n²`. -/
theorem neumannMode_pi (n : ℕ) : neumannMode Real.pi n = (n : ℝ)^2 := by
  have hpi : (0:ℝ) < Real.pi := Real.pi_pos
  unfold neumannMode
  field_simp

/-- On `L = 2π` the admissible modes are `q = (n/2)²`; mode `n = 1` is `q = 1/4`. -/
theorem neumannMode_two_pi_one : neumannMode (2 * Real.pi) 1 = 1/4 := by
  have hpi : (0:ℝ) < Real.pi := Real.pi_pos
  unfold neumannMode
  field_simp
  norm_num

/-- **On `L = π`, NO admissible mode is unstable** (labelled honestly: this is `¬ Unstable`, i.e. `D ≥ 0`,
    which by itself allows the marginal `D = 0`; the strict statement is `worked_modeStable_on_pi`).
    (Renamed from `worked_stable_on_pi`.) -/
theorem worked_not_unstable_on_pi (n : ℕ) : ¬ Unstable worked (neumannMode Real.pi n) := by
  rw [worked_unstable_iff]
  rintro ⟨h1, h2⟩
  rw [neumannMode_pi] at h1 h2
  -- n² < 1/2 forces n = 0, but then n² = 0 which is not > 1/5
  have hn : (n : ℝ) = 0 := by
    by_contra hne
    have h1n : (1:ℝ) ≤ (n:ℝ) := by
      have : 1 ≤ n := Nat.one_le_iff_ne_zero.mpr (by exact_mod_cast hne)
      exact_mod_cast this
    nlinarith
  rw [hn] at h1; norm_num at h1

/-- Strictly positive determinant at every admissible mode of `L = π` (`D(n²) = (5n²-1)(2n²-1) > 0`). -/
theorem worked_D_pos_on_pi (n : ℕ) : 0 < D worked (neumannMode Real.pi n) := by
  rw [worked_D, neumannMode_pi]
  by_cases h0 : n = 0
  · subst h0; norm_num
  · have h1 : (1:ℝ) ≤ (n:ℝ) := by exact_mod_cast Nat.one_le_iff_ne_zero.mpr h0
    have hx : (1:ℝ) ≤ (n:ℝ)^2 := by nlinarith
    exact mul_pos (by linarith) (by linarith)

/-- **On `L = π` every admissible mode is linearly asymptotically stable** (negative trace AND positive
    determinant), obtained by instantiating `finite_domain_linearly_stable` for the worked system. -/
theorem worked_modeStable_on_pi (n : ℕ) : ModeStable worked (neumannMode Real.pi n) :=
  finite_domain_linearly_stable worked Real.pi worked_wellmixed worked_D_pos_on_pi n

/-- **On `L = 2π`, mode `n = 1` (`q = 1/4`) has determinant `-1/8`.** -/
theorem worked_D_two_pi_one : D worked (neumannMode (2 * Real.pi) 1) = -1/8 := by
  rw [worked_D, neumannMode_two_pi_one]
  norm_num

/-- **On `L = 2π` the admissible mode `n = 1` is unstable** (determinant `-1/8 < 0`). -/
theorem worked_unstable_on_two_pi : Unstable worked (neumannMode (2 * Real.pi) 1) := by
  unfold Unstable
  rw [worked_D_two_pi_one]
  norm_num

/-- ... and it is therefore not linearly stable. -/
theorem worked_not_modeStable_on_two_pi : ¬ ModeStable worked (neumannMode (2 * Real.pi) 1) := by
  rintro ⟨_, hD⟩
  rw [worked_D_two_pi_one] at hD
  norm_num at hD

/-- **On `L = 2π` there is an actual growing eigenvalue** for mode `n = 1`: a positive real root of
    `lam^2 - T lam + D`, with `T = -19/4 < 0` (so the trace hypothesis of the iff holds). -/
theorem worked_growth_on_two_pi :
    ∃ lam : ℝ, 0 < lam ∧ lam^2 - T worked (neumannMode (2 * Real.pi) 1) * lam
      + D worked (neumannMode (2 * Real.pi) 1) = 0 :=
  exists_pos_eigenvalue_of_unstable worked _ worked_unstable_on_two_pi

end Admissible

section AxiomAudit
open Admissible
#print axioms D_eq
#print axioms unstable_of_pos_eigenvalue
#print axioms exists_pos_eigenvalue_of_unstable
#print axioms unstable_iff_exists_pos_eigenvalue
#print axioms trace_hypothesis_needed
#print axioms finite_domain_linearly_stable
#print axioms trace_neg_of_wellmixed
#print axioms real_eigenvalue_neg_of_modeStable
#print axioms worked_continuum
#print axioms worked_unstable_iff
#print axioms worked_not_unstable_on_pi
#print axioms worked_modeStable_on_pi
#print axioms worked_D_two_pi_one
#print axioms worked_unstable_on_two_pi
#print axioms worked_not_modeStable_on_two_pi
#print axioms worked_growth_on_two_pi
end AxiomAudit
