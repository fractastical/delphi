import Mathlib.Tactic

/-! Cantilever small-deformation guard, universally quantified over the parameters (a parameterized theorem, not a numeric instance).

Statement as proposed for the Euler-Bernoulli end-load law `3 E I d = P L^3` with the repository's declared guard `d <= L/10`:
the guard holds for EVERY positive P, L, E, I whenever the bending stiffness satisfies `10 P L^2 <= 3 E I`.
This checks the algebra of the stated statement only. It does not show the law is the right model of a fin ray (single Euler-Bernoulli beam),
nor that any real stiffness satisfies the hypothesis. -/

theorem cantilever_guard {P L E I d : ℝ} (hP : 0 < P) (hL : 0 < L) (hE : 0 < E) (hI : 0 < I)
    (law : 3 * E * I * d = P * L ^ 2) (stiff : 10 * P * L ^ 2 ≤ 3 * E * I) : d ≤ L / 10 := by
  have hEI : 0 < E * I := mul_pos hE hI
  have h1 : (3 * (E * I)) * d ≤ (3 * (E * I)) * (L / 10) := by
    have e : P * L ^ 2 = (P * L ^ 2) := by ring
    nlinarith [mul_le_mul_of_nonneg_right stiff hL.le]
  exact le_of_mul_le_mul_left h1 (by positivity)

