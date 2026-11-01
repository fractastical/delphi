
open UnitAlgebra

/- POSITIVE (must compile): positivity of the factor is necessary for interval mapping. -/
theorem interval_map_needs_positive_factor :
    ¬ (∀ lo hi x f : ℚ, lo ≤ x → x ≤ hi → lo * f ≤ x * f ∧ x * f ≤ hi * f) := by
  intro h
  have := h 0 2 1 (-1) (by norm_num) (by norm_num)
  norm_num at this

theorem dim_add_not_sub_refuted :
    ¬ (∀ a b : Dim, Dim.add a b = ⟨a.kg - b.kg, a.m - b.m, a.s - b.s⟩) := by
  intro h
  have := congrArg Dim.kg (h ⟨1, 0, 0⟩ ⟨1, 0, 0⟩)
  simp [Dim.add] at this

#print axioms UnitAlgebra.convert_comp
#print axioms UnitAlgebra.convert_inv
#print axioms UnitAlgebra.interval_map
#print axioms UnitAlgebra.dim_compose
#print axioms interval_map_needs_positive_factor
#print axioms dim_add_not_sub_refuted
