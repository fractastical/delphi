
/- Appended after GeometricSimilarity.lean.  These must COMPILE: each shows a mutated law is false,
   by exhibiting a concrete instance where the hypotheses hold and the mutated conclusion fails.
   (Instances are witnesses of falsity of a universal claim, not evidence for the real law.) -/
open FlyingFish

/-- mutant 1: wing loading would scale as k^2 (area-ratio exponent confusion). -/
theorem mutant_wl_k2_refuted :
    ¬ (∀ m g S k : ℝ, 0 < S → 0 < k →
        wingLoading (k ^ 3 * m) g (k ^ 2 * S) = k ^ 2 * wingLoading m g S) := by
  intro h
  have := h 1 1 1 2 (by norm_num) (by norm_num)
  unfold wingLoading at this
  norm_num at this

/-- mutant 2: wing loading would scale as the mass exponent 1/2, i.e. WL'^3 = k^(9/2) WL^3 ; stated as
    WL'^3 = k^4 WL^3. -/
theorem mutant_wl_mass_exponent_refuted :
    ¬ (∀ m g S k : ℝ, 0 < S → 0 < k →
        wingLoading (k ^ 3 * m) g (k ^ 2 * S) ^ 3 = (k ^ 4) * wingLoading m g S ^ 3) := by
  intro h
  have := h 1 1 1 2 (by norm_num) (by norm_num)
  unfold wingLoading at this
  norm_num at this

/-- mutant 3: squared stall speed would scale as k^2 (speed proportional to k, no square root). -/
theorem mutant_stall_k2_refuted :
    ¬ (∀ m g rho S C k : ℝ, 0 < m → 0 < g → 0 < rho → 0 < S → 0 < C → 0 < k →
        stallSpeed (k ^ 3 * m) g rho (k ^ 2 * S) C ^ 2 = k ^ 2 * stallSpeed m g rho S C ^ 2) := by
  intro h
  have h2 := h 1 1 1 1 1 2 (by norm_num) (by norm_num) (by norm_num) (by norm_num) (by norm_num) (by norm_num)
  rw [stallSpeed_sq_scale (by norm_num) (by norm_num) (by norm_num) (by norm_num) (by norm_num)
    (by norm_num)] at h2
  have hpos : 0 < stallSpeed 1 1 1 1 1 := by unfold stallSpeed; positivity
  nlinarith [sq_pos_of_pos hpos]

#print axioms FlyingFish.scaling_laws
#print axioms FlyingFish.wingLoading_ceiling
#print axioms FlyingFish.conflict_of_certificate
#print axioms mutant_wl_k2_refuted
#print axioms mutant_wl_mass_exponent_refuted
#print axioms mutant_stall_k2_refuted
