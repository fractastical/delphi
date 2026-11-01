import Mathlib

namespace ThompsonLaws.LimbBoneSimilarity

/-- Cross-sectional area of a circular limb bone from its diameter. -/
noncomputable def areaFromDiameter (diameter : ℝ → ℝ) (mass : ℝ) : ℝ :=
  Real.pi / 4 * diameter mass ^ 2

/-- Circumference of a circular limb bone from its diameter. -/
noncomputable def circumferenceFromDiameter (diameter : ℝ → ℝ) (mass : ℝ) : ℝ :=
  Real.pi * diameter mass

/-- A physical quantity follows a mass power law with the stated exponent. -/
def ScalesWithMass (quantity : ℝ → ℝ) (exponent : ℝ) : Prop :=
  ∃ coefficient > 0, ∀ mass > 0, quantity mass = coefficient * mass ^ exponent

/-- Squaring a diameter power law doubles its exponent in cross-sectional area. -/
theorem area_scales_from_diameter (diameter : ℝ → ℝ) (p k : ℝ) (hk : 0 < k)
    (hdiameter : ∀ mass > 0, diameter mass = k * mass ^ p) :
    ScalesWithMass (areaFromDiameter diameter) (2 * p) := by
  refine ⟨Real.pi / 4 * k ^ 2, by positivity, ?_⟩
  intro mass hmass
  unfold areaFromDiameter
  rw [hdiameter mass hmass, mul_pow, ← Real.rpow_natCast, ← Real.rpow_mul hmass.le]
  ring

/-- A circumference has the same mass exponent as its diameter. -/
theorem circumference_scales_from_diameter (diameter : ℝ → ℝ) (p k : ℝ) (hk : 0 < k)
    (hdiameter : ∀ mass > 0, diameter mass = k * mass ^ p) :
    ScalesWithMass (circumferenceFromDiameter diameter) p := by
  refine ⟨Real.pi * k, by positivity, ?_⟩
  intro mass hmass
  unfold circumferenceFromDiameter
  rw [hdiameter mass hmass]
  ring

/-- thompson1917-ch02-03: under geometric similarity, diameter is proportional to
`mass^(1/3)`, hence area and circumference have exponents `2/3` and `1/3`.
This corrects the approach by making circular cross-sections and positive mass explicit. -/
theorem geometric_similarity_exponents (diameter : ℝ → ℝ) (k : ℝ) (hk : 0 < k)
    (hdiameter : ∀ mass > 0, diameter mass = k * mass ^ ((1 : ℝ) / 3)) :
    ScalesWithMass (areaFromDiameter diameter) ((2 : ℝ) / 3) ∧
      ScalesWithMass (circumferenceFromDiameter diameter) ((1 : ℝ) / 3) := by
  constructor
  · convert area_scales_from_diameter diameter ((1 : ℝ) / 3) k hk hdiameter using 1 <;>
      norm_num
  · exact circumference_scales_from_diameter diameter ((1 : ℝ) / 3) k hk hdiameter

/-- Under McMahon's elastic-similarity assumption `diameter ∝ mass^(3/8)`, area and
circumference have exponents `3/4` and `3/8`. The length exponent `1/4` is independent
of these two consequences and is therefore not added as an unused hypothesis. -/
theorem elastic_similarity_exponents (diameter : ℝ → ℝ) (k : ℝ) (hk : 0 < k)
    (hdiameter : ∀ mass > 0, diameter mass = k * mass ^ ((3 : ℝ) / 8)) :
    ScalesWithMass (areaFromDiameter diameter) ((3 : ℝ) / 4) ∧
      ScalesWithMass (circumferenceFromDiameter diameter) ((3 : ℝ) / 8) := by
  constructor
  · convert area_scales_from_diameter diameter ((3 : ℝ) / 8) k hk hdiameter using 1 <;>
      norm_num
  · exact circumference_scales_from_diameter diameter ((3 : ℝ) / 8) k hk hdiameter

/-- Under stress similarity, constant stress and force proportional to mass require area
proportional to mass. A circular section therefore has diameter and circumference
proportional to `mass^(1/2)`; that circular-shape hypothesis is explicit here. -/
theorem stress_similarity_exponents (diameter : ℝ → ℝ) (k : ℝ) (hk : 0 < k)
    (hdiameter : ∀ mass > 0, diameter mass = k * mass ^ ((1 : ℝ) / 2)) :
    ScalesWithMass (areaFromDiameter diameter) 1 ∧
      ScalesWithMass (circumferenceFromDiameter diameter) ((1 : ℝ) / 2) := by
  constructor
  · convert area_scales_from_diameter diameter ((1 : ℝ) / 2) k hk hdiameter using 1 <;>
      norm_num
  · exact circumference_scales_from_diameter diameter ((1 : ℝ) / 2) k hk hdiameter

/-- The geometric, elastic and stress-similarity area exponents are pairwise distinct. -/
theorem area_exponents_distinct :
    Pairwise (fun x y : ℝ => x ≠ y) [((2 : ℝ) / 3), ((3 : ℝ) / 4), 1] := by
  simp
  norm_num

/-- Effective mechanical advantage proportional to `mass^γ`. -/
noncomputable def mechanicalAdvantage (e mass γ : ℝ) : ℝ := e * mass ^ γ

/-- Area required to keep bone stress `stress` constant when body force is `w * mass`
and posture supplies the effective mechanical advantage. -/
noncomputable def postureRequiredArea (w e stress mass γ : ℝ) : ℝ :=
  (w * mass / mechanicalAdvantage e mass γ) / stress

/-- The posture correction: if effective mechanical advantage scales as `mass^γ`, constant
stress requires area proportional to `mass^(1-γ)`. The approach omitted the needed
positivity/nonzero assumptions on mass, advantage coefficient and stress; they are explicit. -/
theorem posture_area_exponent (w e stress mass γ : ℝ) (hmass : 0 < mass)
    (he : e ≠ 0) (hstress : stress ≠ 0) :
    postureRequiredArea w e stress mass γ =
      (w / (e * stress)) * mass ^ (1 - γ) := by
  unfold postureRequiredArea mechanicalAdvantage
  rw [Real.rpow_sub hmass.le, Real.rpow_one]
  have hp : mass ^ γ ≠ 0 := (Real.rpow_pos_of_pos hmass γ).ne'
  field_simp
  ring

end ThompsonLaws.LimbBoneSimilarity
