import Mathlib.Tactic

/-! Cantilever small-deformation guard, universally quantified over the parameters (a parameterized theorem, not a numeric instance).

Statement as proposed for the Euler-Bernoulli end-load law `3 E I d = P L^3` with the repository's declared guard `d <= L/10`:
the guard holds for EVERY positive P, L, E, I whenever the bending stiffness satisfies `10 P L^2 <= 3 E I`.
This checks the algebra of the stated statement only. It does not show the law is the right model of a fin ray (single Euler-Bernoulli beam),
nor that any real stiffness satisfies the hypothesis. -/

theorem cantilever_guard {P L E I d : ℝ} (hP : 0 < P) (hL : 0 < L) (hE : 0 < E) (hI : 0 < I)
    (law : 3 * E * I * d = P * L ^ 3) (stiff : 10 * P * L ^ 2 ≤ 3 * E * I) : d ≤ L / 10 := by
  have hEI : 0 < E * I := mul_pos hE hI
  have h1 : (3 * (E * I)) * d ≤ (3 * (E * I)) * (L / 10) := by
    have e : P * L ^ 3 = (P * L ^ 2) * L := by ring
    nlinarith [mul_le_mul_of_nonneg_right stiff hL.le]
  exact le_of_mul_le_mul_left h1 (by positivity)

/-- The hypotheses are jointly satisfiable, so the theorem is not vacuous. -/
theorem cantilever_guard_hypotheses_satisfiable :
    ∃ P L E I d : ℝ, 0 < P ∧ 0 < L ∧ 0 < E ∧ 0 < I ∧ 3 * E * I * d = P * L ^ 3 ∧ 10 * P * L ^ 2 ≤ 3 * E * I := by
  refine ⟨1, 1, 100, 1, 1 / 300, by norm_num, by norm_num, by norm_num, by norm_num, by norm_num, by norm_num⟩

/-- The stiffness hypothesis is needed: without it the guard fails (P = L = E = 1, I = 1/100, d = 100/3). -/
theorem cantilever_guard_needs_stiffness :
    ¬ (∀ P L E I d : ℝ, 0 < P → 0 < L → 0 < E → 0 < I → 3 * E * I * d = P * L ^ 3 → d ≤ L / 10) := by
  intro h
  have := h 1 1 1 (1 / 100) (100 / 3) (by norm_num) (by norm_num) (by norm_num) (by norm_num) (by norm_num)
  norm_num at this

#print axioms cantilever_guard
#print axioms cantilever_guard_hypotheses_satisfiable
#print axioms cantilever_guard_needs_stiffness
