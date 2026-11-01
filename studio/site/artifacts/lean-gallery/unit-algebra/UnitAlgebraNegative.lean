
open UnitAlgebra

-- NEG:comp_adds BEGIN
theorem neg_comp_adds (x f g : ℚ) : (x * f) * g = x * (f + g) := by ring
-- NEG:comp_adds END

-- NEG:interval_no_positivity BEGIN
theorem neg_interval {lo hi x f : ℚ} (h1 : lo ≤ x) (h2 : x ≤ hi) :
    lo * f ≤ x * f ∧ x * f ≤ hi * f :=
  ⟨mul_le_mul_of_nonneg_right h1 (by norm_num), mul_le_mul_of_nonneg_right h2 (by norm_num)⟩
-- NEG:interval_no_positivity END

-- NEG:inverse_without_nonzero BEGIN
theorem neg_inverse {x f : ℚ} : (x * f) * f⁻¹ = x := by
  field_simp
-- NEG:inverse_without_nonzero END

-- NEG:dim_sub BEGIN
theorem neg_dim {src dst dst2 f g : Dim} (h1 : dst = src.add f) (h2 : dst2 = dst.add g) :
    dst2 = src.add ⟨f.kg - g.kg, f.m - g.m, f.s - g.s⟩ := by
  subst h1 h2
  ext <;> simp [Dim.add] <;> ring
-- NEG:dim_sub END
