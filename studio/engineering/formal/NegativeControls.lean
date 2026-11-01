
/- Appended after GeometricSimilarity.lean.  EVERY block below must FAIL to compile; the harness
   checks that an error is reported inside each labelled block and nowhere else.
   Each block uses the real law's proof (or a corrupted certificate) against a mutated statement. -/
open FlyingFish

-- NEG:wl_k2 BEGIN
theorem neg_wl_k2 {m g S k : ℝ} (hS : 0 < S) (hk : 0 < k) :
    wingLoading (k ^ 3 * m) g (k ^ 2 * S) = k ^ 2 * wingLoading m g S := by
  unfold wingLoading
  field_simp
-- NEG:wl_k2 END

-- NEG:mass_exponent BEGIN
theorem neg_mass_exponent {m g S k : ℝ} (hS : 0 < S) (hk : 0 < k) :
    wingLoading (k ^ 3 * m) g (k ^ 2 * S) ^ 3 = (k ^ 4) * wingLoading m g S ^ 3 := by
  rw [wingLoading_scale hS hk]; ring
-- NEG:mass_exponent END

-- NEG:stall_k2 BEGIN
theorem neg_stall_k2 {m g rho S C k : ℝ} (hm : 0 < m) (hg : 0 < g) (hrho : 0 < rho)
    (hS : 0 < S) (hC : 0 < C) (hk : 0 < k) :
    stallSpeed (k ^ 3 * m) g rho (k ^ 2 * S) C ^ 2 = k ^ 2 * stallSpeed m g rho S C ^ 2 := by
  unfold stallSpeed
  have h1 : 0 ≤ 2 * (k ^ 3 * m) * g / (rho * (k ^ 2 * S) * C) := by positivity
  have h2 : 0 ≤ 2 * m * g / (rho * S * C) := by positivity
  rw [Real.sq_sqrt h1, Real.sq_sqrt h2]
  field_simp
-- NEG:stall_k2 END

-- NEG:corrupted_certificate BEGIN
@@CORRUPTED_CERTIFICATE@@
-- NEG:corrupted_certificate END
