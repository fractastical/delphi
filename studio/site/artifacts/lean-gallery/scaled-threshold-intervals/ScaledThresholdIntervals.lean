import Mathlib.Tactic

/-!
A conditional interval certificate for the epithelial sweep's scaled threshold lambda/J.
Theorem inputs are interval premises, not observations certified by Lean. The rational
instances are bound by source-witnesses.json to the fixed StopTime=1000 returned-model audit.
This file proves neither a CPM threshold nor biology, monotonicity, PDEs or infinite-time arrest.
-/
namespace ScaledThresholdIntervals

/-- A factor-t band forces its bounding interval endpoints to obey the same inequality.
Positivity of x,y states the intended threshold domain; the algebra only needs t >= 0. -/
theorem factor_band_forces_endpoint_bound {x y a b t : ℝ}
    (_hx : 0 < x) (_hy : 0 < y) (ht : 0 ≤ t)
    (hlo : a ≤ x) (hhi : y ≤ b) (hband : x ≤ t * y) : a ≤ t * b := by
  exact hlo.trans (hband.trans (mul_le_mul_of_nonneg_left hhi ht))

/-- Strictly separated endpoints exclude a factor-t band for every positive pair satisfying
these bounds. The source audit, not Lean, must establish the relevant interval premises. -/
theorem separated_intervals_reject_factor_band {x y a b t : ℝ}
    (hx : 0 < x) (hy : 0 < y) (ht : 0 ≤ t)
    (hlo : a ≤ x) (hhi : y ≤ b) (hsep : t * b < a) : ¬ x ≤ t * y := by
  intro hband
  exact (not_le_of_gt hsep) (factor_band_forces_endpoint_bound hx hy ht hlo hhi hband)

/-- Actual k=4 seed-1 endpoint bounds, at J35 and J560, exclude the frozen tolerance 2.
x and y remain universally quantified; no midpoint or fitted threshold is substituted. -/
theorem k4_recorded_intervals_reject_factor_two {x y : ℝ}
    (hx : 0 < x) (hy : 0 < y)
    (hlo : (2 : ℝ) / 175 ≤ x) (hhi : y ≤ (1 : ℝ) / 350) : ¬ x ≤ 2 * y := by
  exact separated_intervals_reject_factor_band hx hy (by norm_num) hlo hhi (by norm_num)

/-- Actual k=7 seed-1 endpoint bounds similarly exclude tolerance 2. -/
theorem k7_recorded_intervals_reject_factor_two {x y : ℝ}
    (hx : 0 < x) (hy : 0 < y)
    (hlo : (1 : ℝ) / 175 ≤ x) (hhi : y ≤ (1 : ℝ) / 1400) : ¬ x ≤ 2 * y := by
  exact separated_intervals_reject_factor_band hx hy (by norm_num) hlo hhi (by norm_num)

/-- The full k=4 interval premises have positive joint witnesses. Only adding the rejected
factor-two hypothesis creates a contradiction; these are not impossible interval premises. -/
theorem k4_interval_premises_nonempty :
    ∃ x y : ℝ, 0 < x ∧ 0 < y ∧
      (2 : ℝ) / 175 ≤ x ∧ x ≤ (4 : ℝ) / 175 ∧
      (1 : ℝ) / 700 ≤ y ∧ y ≤ (1 : ℝ) / 350 := by
  refine ⟨2 / 175, 1 / 350, ?_⟩
  norm_num

/-- The full k=7 interval premises also have positive joint witnesses. -/
theorem k7_interval_premises_nonempty :
    ∃ x y : ℝ, 0 < x ∧ 0 < y ∧
      (1 : ℝ) / 175 ≤ x ∧ x ≤ (2 : ℝ) / 175 ∧
      (1 : ℝ) / 2800 ≤ y ∧ y ≤ (1 : ℝ) / 1400 := by
  refine ⟨1 / 175, 1 / 1400, ?_⟩
  norm_num

/-- A rational counterexample to reversing the lower endpoint premise. -/
theorem reverse_lower_counterexample :
    ∃ x y a b t : ℝ, 0 < x ∧ 0 < y ∧ 0 ≤ t ∧
      x ≤ a ∧ y ≤ b ∧ t * b < a ∧ x ≤ t * y := by
  refine ⟨1, 1, 3, 1, 2, ?_⟩
  norm_num

/-- A rational counterexample to reversing the upper endpoint premise. -/
theorem reverse_upper_counterexample :
    ∃ x y a b t : ℝ, 0 < x ∧ 0 < y ∧ 0 ≤ t ∧
      a ≤ x ∧ b ≤ y ∧ t * b < a ∧ x ≤ t * y := by
  refine ⟨3, 2, 3, 1, 2, ?_⟩
  norm_num

/-- A rational counterexample to replacing strict separation by equality-or-greater. -/
theorem nonstrict_separation_counterexample :
    ∃ x y a b t : ℝ, 0 < x ∧ 0 < y ∧ 0 ≤ t ∧
      a ≤ x ∧ y ≤ b ∧ t * b ≤ a ∧ x ≤ t * y := by
  refine ⟨2, 1, 2, 1, 2, ?_⟩
  norm_num

/-- A factor t cannot be dropped from the endpoint conclusion. -/
theorem dropped_factor_counterexample :
    ∃ x y a b t : ℝ, 0 < x ∧ 0 < y ∧ 0 ≤ t ∧
      a ≤ x ∧ y ≤ b ∧ x ≤ t * y ∧ b < a := by
  refine ⟨2, 1, 2, 1, 2, ?_⟩
  norm_num

#print axioms factor_band_forces_endpoint_bound
#print axioms separated_intervals_reject_factor_band
#print axioms k4_recorded_intervals_reject_factor_two
#print axioms k7_recorded_intervals_reject_factor_two
#print axioms k4_interval_premises_nonempty
#print axioms k7_interval_premises_nonempty
#print axioms reverse_lower_counterexample
#print axioms reverse_upper_counterexample
#print axioms nonstrict_separation_counterexample
#print axioms dropped_factor_counterexample

end ScaledThresholdIntervals
