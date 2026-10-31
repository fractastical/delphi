import Mathlib

namespace ThompsonLaws.Mechanics

noncomputable section

/-- thompson1917-ch16-04: in a thin-walled tube of mean radius `r` and wall thickness `t`
the section modulus is `π r² t`, so the peak bending stress under moment `M` is
`M / (π r² t)`. The wall thickness that keeps this stress at a fixed working value `σ₀`
everywhere along the shaft is `M / (π r² σ₀)`. -/
def uniformStressThickness (σ₀ r M : ℝ) : ℝ := M / (Real.pi * r ^ 2 * σ₀)

/-- Bending moment at distance `x` along a simply supported beam of length `L` carrying a
uniform load `w` per unit length. -/
def uniformLoadMoment (w L x : ℝ) : ℝ := w * x * (L - x) / 2

/-- The uniform-stress wall thickness gives exactly the working stress `σ₀`. -/
theorem uniformStressThickness_stress (σ₀ r M : ℝ) (hσ : 0 < σ₀) (hr : 0 < r) (hM : 0 < M) :
    M / (Real.pi * r ^ 2 * uniformStressThickness σ₀ r M) = σ₀ := by
  unfold uniformStressThickness
  have hpi : 0 < Real.pi := Real.pi_pos
  field_simp

/-- The uniform-stress wall thickness is proportional to the bending moment. -/
theorem uniformStressThickness_prop (σ₀ r M : ℝ) :
    uniformStressThickness σ₀ r M = (1 / (Real.pi * r ^ 2 * σ₀)) * M := by
  unfold uniformStressThickness; ring

/-- Under a uniform load the wall thickness is greatest at mid-shaft. -/
theorem uniformStressThickness_max_mid (σ₀ r w L x : ℝ) (hσ : 0 < σ₀) (hr : 0 < r)
    (hw : 0 ≤ w) :
    uniformStressThickness σ₀ r (uniformLoadMoment w L x)
      ≤ uniformStressThickness σ₀ r (uniformLoadMoment w L (L / 2)) := by
  unfold uniformStressThickness uniformLoadMoment
  have hpi : 0 < Real.pi := Real.pi_pos
  have hden : 0 < Real.pi * r ^ 2 * σ₀ := by positivity
  apply div_le_div_of_nonneg_right _ hden.le
  have : w * x * (L - x) ≤ w * (L / 2) * (L - L / 2) := by
    have h : x * (L - x) ≤ (L / 2) * (L - L / 2) := by nlinarith [sq_nonneg (x - L / 2)]
    nlinarith [mul_le_mul_of_nonneg_left h hw]
  linarith

/-- thompson1917-ch16-05: a plane stress state is a symmetric tensor
`[[a, b], [b, c]]`; this is its action on a vector `(u₁, u₂)`. Principal stress directions
are its eigenvectors. -/
def stressAction (a b c u₁ u₂ : ℝ) : ℝ × ℝ := (a * u₁ + b * u₂, b * u₁ + c * u₂)

/-- Principal stress directions belonging to distinct principal stresses `λ ≠ μ`
(compression and tension) are perpendicular, so trajectories following them cross at 90°. -/
theorem principalDirections_orthogonal (a b c u₁ u₂ v₁ v₂ lam mu : ℝ) (hne : lam ≠ mu)
    (hu : stressAction a b c u₁ u₂ = (lam * u₁, lam * u₂))
    (hv : stressAction a b c v₁ v₂ = (mu * v₁, mu * v₂)) :
    u₁ * v₁ + u₂ * v₂ = 0 := by
  simp only [stressAction, Prod.mk.injEq] at hu hv
  obtain ⟨hu₁, hu₂⟩ := hu
  obtain ⟨hv₁, hv₂⟩ := hv
  have h : (lam - mu) * (u₁ * v₁ + u₂ * v₂) = 0 := by
    linear_combination u₁ * hv₁ + u₂ * hv₂ - v₁ * hu₁ - v₂ * hu₂
  rcases mul_eq_zero.mp h with h | h
  · exact absurd (sub_eq_zero.mp h) hne
  · exact h

/-- thompson1917-ch16-10: in the vertebral girder an upper tie (ligament) and a lower
compression member (vertebral bodies), each carrying at most the force `F₀`, are held
apart by the web (spines). The depth needed to resist bending moment `M` is `M / F₀`. -/
def spineHeight (F₀ M : ℝ) : ℝ := M / F₀

/-- The flange couple `F₀ · h` at the required depth balances the bending moment. -/
theorem spineHeight_balances (F₀ M : ℝ) (hF : F₀ ≠ 0) : F₀ * spineHeight F₀ M = M := by
  unfold spineHeight; field_simp

/-- Spine heights at two points stand in the ratio of the bending moments there. -/
theorem spineHeight_ratio (F₀ M₁ M₂ : ℝ) (hF : F₀ ≠ 0) (hM : M₂ ≠ 0) :
    spineHeight F₀ M₁ / spineHeight F₀ M₂ = M₁ / M₂ := by
  unfold spineHeight; field_simp

/-- thompson1917-ch16-14: three equal struts along unit vectors at 120° to one another,
`(1, 0)`, `(-1/2, √3/2)`, `(-1/2, -√3/2)`. Their contribution to bending stiffness about
the direction `(n₁, n₂)` is the sum of squared projections onto it. -/
def threeStrutStiffness (n₁ n₂ : ℝ) : ℝ :=
  n₁ ^ 2 + (-(1 / 2) * n₁ + Real.sqrt 3 / 2 * n₂) ^ 2
    + (-(1 / 2) * n₁ - Real.sqrt 3 / 2 * n₂) ^ 2

/-- At 120° spacing the stiffness is the same in every direction: `(3/2)|n|²`. -/
theorem threeStrutStiffness_isotropic (n₁ n₂ : ℝ) :
    threeStrutStiffness n₁ n₂ = 3 / 2 * (n₁ ^ 2 + n₂ ^ 2) := by
  unfold threeStrutStiffness
  have h3 : Real.sqrt 3 ^ 2 = 3 := Real.sq_sqrt (by norm_num)
  linear_combination (n₂ ^ 2 / 2) * h3

/-- The stiffness about every unit direction is equal. -/
theorem threeStrutStiffness_uniform (n₁ n₂ m₁ m₂ : ℝ) (hn : n₁ ^ 2 + n₂ ^ 2 = 1)
    (hm : m₁ ^ 2 + m₂ ^ 2 = 1) :
    threeStrutStiffness n₁ n₂ = threeStrutStiffness m₁ m₂ := by
  rw [threeStrutStiffness_isotropic, threeStrutStiffness_isotropic, hn, hm]

/-- thompson1917-ch17-06: the sheep's cannon-bone is the ox's stretched along the length
axis by `s`: `(breadth, length) ↦ (breadth, s · length)`. -/
def lengthStretch (s : ℝ) (p : ℝ × ℝ) : ℝ × ℝ := (p.1, s * p.2)

/-- Rescaled uniformly to the ox's length, the stretched bone is the ox's bone with
breadth multiplied by `c = 1/s` and length unchanged. -/
theorem lengthStretch_equalLength (s : ℝ) (hs : s ≠ 0) (p : ℝ × ℝ) :
    (s⁻¹ * (lengthStretch s p).1, s⁻¹ * (lengthStretch s p).2) = (s⁻¹ * p.1, p.2) := by
  simp only [lengthStretch, Prod.mk.injEq, true_and]
  field_simp

/-- Thompson's ratios: stretch 3/2 (sheep) gives breadth 2/3, stretch 3 (giraffe) gives 1/3. -/
theorem lengthStretch_sheep_giraffe (p : ℝ × ℝ) :
    (3 / 2 : ℝ)⁻¹ * (lengthStretch (3 / 2) p).1 = 2 / 3 * p.1 ∧
      (3 : ℝ)⁻¹ * (lengthStretch 3 p).1 = 1 / 3 * p.1 := by
  simp only [lengthStretch]
  constructor <;> ring

/-- thompson1917-ch17-08: the second half of the begonia leaf, in radial coordinates, is
the first half `r = f θ` with angles multiplied by `k`: `r = f (θ / k)`. -/
def unequalHalf (f : ℝ → ℝ) (k θ : ℝ) : ℝ := f (θ / k)

/-- If the first half's radius is injective in the angle, then points at equal radii on
the two halves have angles in the constant ratio `k`. -/
theorem unequalHalf_equalRadii (f : ℝ → ℝ) (hf : Function.Injective f) (k θ θ' : ℝ)
    (hk : k ≠ 0) (h : unequalHalf f k θ' = f θ) : θ' = k * θ := by
  unfold unequalHalf at h
  have := hf h
  field_simp at this
  linarith

/-- thompson1917-ch17-18: a fish of length `L`, depth `D`, thickness `T`, density `ρ` and
fixed shape factor `c` weighs `ρ c L D T`; its length-weight coefficient is `W / L³`. -/
def lengthWeightCoeff (ρ c L D T : ℝ) : ℝ := ρ * c * L * D * T / L ^ 3

/-- Scaling depth by `a` and thickness by `b` multiplies `k` by `a b`. -/
theorem lengthWeightCoeff_scale (ρ c L D T a b : ℝ) :
    lengthWeightCoeff ρ c L (a * D) (b * T) = a * b * lengthWeightCoeff ρ c L D T := by
  unfold lengthWeightCoeff; ring

/-- Inverse variation (depth × a, thickness × 1/a, e.g. a = 2) leaves `k` unchanged. -/
theorem lengthWeightCoeff_inverse (ρ c L D T a : ℝ) (ha : a ≠ 0) :
    lengthWeightCoeff ρ c L (a * D) (a⁻¹ * T) = lengthWeightCoeff ρ c L D T := by
  rw [lengthWeightCoeff_scale, mul_inv_cancel₀ ha, one_mul]

end

end ThompsonLaws.Mechanics
