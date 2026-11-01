import Mathlib

/-!
# Hollow tubes at fixed bending stiffness

A circular tube of outer radius `R` and inner radius `k R` (`0 ≤ k < 1`) has cross-sectional
area `π R² (1 - k²)` and second moment of area `I = (π/4) R⁴ (1 - k⁴)`. Holding the bending
stiffness (`I`) fixed, this module proves:

* with a weightless (gas-filled) core the wall area is `√(4πI) · √((1 - k²)/(1 + k²))`, and
  that factor is strictly decreasing in `k`, so there is no interior optimum: the lightest
  tube for a given stiffness is the thin-wall limit, cut off only by another constraint;
* with a core of density `q` times the wall's, the mass is `√(4πI) · ρ · μ(k)` with
  `μ(k) = (1 - k² + q k²)/√(1 - k⁴)`; `μ'(k) = 2k (k² - (1 - q)) / ((1 - k⁴)^{3/2})`, so the
  stationarity condition is `k² = 1 - q`. A critical point in `(0, 1)` exists exactly for
  `0 < q < 1`, and it is then the unique global minimum, `k* = √(1 - q)`, with
  `μ(k*) = √(q (2 - q))`. For `q ≥ 1` the solid rod (`k = 0`) is optimal.
* with local buckling as the symbolic bound `t/R = 1 - k ≥ λ` (`λ = C σ / E`, `C` a free
  constant), the constrained optimum is `min(k*, 1 - λ)`.

These are statements about the model; whether bones, quills and stems sit at these optima is
left to measurement.
-/

namespace ThompsonLaws.HollowTube

noncomputable section

open Real

/-- Cross-sectional area of a tube with outer radius `R` and inner/outer radius ratio `k`. -/
def tubeArea (R k : ℝ) : ℝ := π * R ^ 2 * (1 - k ^ 2)

/-- Second moment of area of the same tube about a diameter (its bending stiffness per unit
modulus). -/
def tubeSecondMoment (R k : ℝ) : ℝ := π / 4 * R ^ 4 * (1 - k ^ 4)

/-- thompson1917-ch16-03: the wall area of a tube of fixed second moment `I`, in units of
`√(4πI)` (the solid rod's area at `k = 0`). -/
def gasCoreAreaFactor (k : ℝ) : ℝ := √((1 - k ^ 2) / (1 + k ^ 2))

/-- At fixed stiffness the area of a tube is `√(4πI)` times the gas-core area factor. -/
theorem tubeArea_fixedStiffness (R k I : ℝ) (hR : 0 < R) (hk1 : k < 1) (hk0 : 0 ≤ k)
    (hI : tubeSecondMoment R k = I) :
    tubeArea R k = √(4 * π * I) * gasCoreAreaFactor k := by
  subst hI
  unfold tubeArea tubeSecondMoment gasCoreAreaFactor
  have h1 : 0 ≤ 1 - k ^ 2 := by nlinarith
  have h2 : 0 < 1 + k ^ 2 := by positivity
  have e : 4 * π * (π / 4 * R ^ 4 * (1 - k ^ 4)) = (π * R ^ 2) ^ 2 * ((1 - k ^ 2) * (1 + k ^ 2)) := by
    ring
  rw [e, Real.sqrt_mul (sq_nonneg _), Real.sqrt_sq (by positivity), Real.sqrt_mul h1,
    Real.sqrt_div h1]
  have hs : 0 < √(1 + k ^ 2) := Real.sqrt_pos.mpr h2
  field_simp
  rw [Real.sq_sqrt h1]

/-- thompson1917-ch16-03: the gas-core area factor is strictly decreasing in `k` on `[0, 1]`:
at fixed stiffness, the hollower the tube, the less wall material it needs. -/
theorem gasCoreAreaFactor_strictAntiOn : StrictAntiOn gasCoreAreaFactor (Set.Icc 0 1) := by
  intro k₁ hk₁ k₂ hk₂ hlt
  obtain ⟨h₁0, h₁1⟩ := hk₁
  obtain ⟨h₂0, h₂1⟩ := hk₂
  unfold gasCoreAreaFactor
  apply Real.sqrt_lt_sqrt
  · apply div_nonneg <;> nlinarith
  · rw [div_lt_div_iff₀ (by positivity) (by positivity)]
    nlinarith [mul_lt_mul_of_pos_left hlt (by linarith : (0 : ℝ) < k₁ + k₂)]

/-- Two tubes of equal stiffness: the one with the larger inner/outer ratio has strictly less
wall area. -/
theorem tubeArea_lt_of_sameStiffness (R₁ R₂ k₁ k₂ I : ℝ) (hR₁ : 0 < R₁) (hR₂ : 0 < R₂)
    (hk₁ : 0 ≤ k₁) (hlt : k₁ < k₂) (hk₂ : k₂ < 1) (hI : 0 < I)
    (h₁ : tubeSecondMoment R₁ k₁ = I) (h₂ : tubeSecondMoment R₂ k₂ = I) :
    tubeArea R₂ k₂ < tubeArea R₁ k₁ := by
  rw [tubeArea_fixedStiffness R₁ k₁ I hR₁ (by linarith) hk₁ h₁,
    tubeArea_fixedStiffness R₂ k₂ I hR₂ hk₂ (by linarith) h₂]
  have hpos : 0 < √(4 * π * I) := Real.sqrt_pos.mpr (by positivity)
  exact mul_lt_mul_of_pos_left
    (gasCoreAreaFactor_strictAntiOn ⟨hk₁, by linarith⟩ ⟨by linarith, hk₂.le⟩ hlt) hpos

/-- With a weightless core no ratio `k ∈ [0, 1)` minimizes the area at fixed stiffness: there
is no interior optimum, only the thin-wall limit. -/
theorem gasCore_no_interior_min (k : ℝ) (hk0 : 0 ≤ k) (hk1 : k < 1) :
    ∃ k' : ℝ, 0 ≤ k' ∧ k' < 1 ∧ gasCoreAreaFactor k' < gasCoreAreaFactor k :=
  ⟨(k + 1) / 2, by linarith, by linarith,
    gasCoreAreaFactor_strictAntiOn ⟨hk0, hk1.le⟩ ⟨by linarith, by linarith⟩ (by linarith)⟩

/-! ## A core of density `q` times the wall's -/

/-- Mass per unit length of a tube whose wall has density `ρ` and whose core has density
`q ρ`. -/
def tubeMass (ρ q R k : ℝ) : ℝ := ρ * (π * R ^ 2 * (1 - k ^ 2) + q * (π * R ^ 2 * k ^ 2))

/-- thompson1917-ch16-03: mass per unit length at fixed stiffness, in units of `ρ √(4πI)`. -/
def massFactor (q k : ℝ) : ℝ := (1 - k ^ 2 + q * k ^ 2) / √(1 - k ^ 4)

/-- At fixed stiffness the mass is `ρ √(4πI)` times the mass factor. -/
theorem tubeMass_fixedStiffness (ρ q R k I : ℝ) (hR : 0 < R) (hk0 : 0 ≤ k) (hk1 : k < 1)
    (hI : tubeSecondMoment R k = I) :
    tubeMass ρ q R k = ρ * √(4 * π * I) * massFactor q k := by
  subst hI
  unfold tubeMass tubeSecondMoment massFactor
  have h1 : 0 < 1 - k ^ 4 := by
    linarith [pow_lt_one₀ hk0 hk1 (by norm_num : (4 : ℕ) ≠ 0)]
  have e : 4 * π * (π / 4 * R ^ 4 * (1 - k ^ 4)) = (π * R ^ 2) ^ 2 * (1 - k ^ 4) := by ring
  rw [e, Real.sqrt_mul (sq_nonneg _), Real.sqrt_sq (by positivity)]
  have hs : 0 < √(1 - k ^ 4) := Real.sqrt_pos.mpr h1
  field_simp

/-- A weightless core (`q = 0`) recovers the gas-core area factor. -/
theorem massFactor_zero (k : ℝ) (hk0 : 0 ≤ k) (hk1 : k < 1) :
    massFactor 0 k = gasCoreAreaFactor k := by
  unfold massFactor gasCoreAreaFactor
  have h1 : 0 ≤ 1 - k ^ 2 := by nlinarith
  have h2 : 0 < 1 + k ^ 2 := by positivity
  have e : 1 - k ^ 4 = (1 - k ^ 2) * (1 + k ^ 2) := by ring
  rw [e, Real.sqrt_mul h1, Real.sqrt_div h1]
  have hs : 0 < √(1 + k ^ 2) := Real.sqrt_pos.mpr h2
  rcases h1.lt_or_eq with h1 | h1
  · have hs1 : 0 < √(1 - k ^ 2) := Real.sqrt_pos.mpr h1
    field_simp
    linarith [Real.sq_sqrt h1.le]
  · rw [← h1]; simp

/-- The derivative of the mass factor:
`μ'(k) = 2k (k² - (1 - q)) / ((1 - k⁴) √(1 - k⁴))`. -/
theorem massFactor_hasDerivAt (q k : ℝ) (hk : k ^ 4 < 1) :
    HasDerivAt (massFactor q) (2 * k * (k ^ 2 - (1 - q)) / ((1 - k ^ 4) * √(1 - k ^ 4))) k := by
  have hu : 0 < 1 - k ^ 4 := by linarith
  have hs : 0 < √(1 - k ^ 4) := Real.sqrt_pos.mpr hu
  have hN : HasDerivAt (fun x : ℝ => 1 - x ^ 2 + q * x ^ 2)
      (-(↑2 * k ^ (2 - 1)) + q * (↑2 * k ^ (2 - 1))) k :=
    ((hasDerivAt_pow 2 k).const_sub 1).add ((hasDerivAt_pow 2 k).const_mul q)
  have hD : HasDerivAt (fun x : ℝ => √(1 - x ^ 4)) (-(↑4 * k ^ (4 - 1)) / (2 * √(1 - k ^ 4))) k :=
    ((hasDerivAt_pow 4 k).const_sub 1).sqrt hu.ne'
  have h := hN.div hD hs.ne'
  unfold massFactor
  convert h using 1
  have hs2 : √(1 - k ^ 4) ^ 2 = 1 - k ^ 4 := Real.sq_sqrt hu.le
  rw [div_eq_div_iff (by positivity) (by positivity)]
  field_simp
  push_cast
  rw [hs2]
  ring

/-- thompson1917-ch16-03 (stationarity condition): for `0 < k < 1`, `μ'(k) = 0` if and only if
`k² = 1 - q`. -/
theorem massFactor_deriv_eq_zero_iff (q k : ℝ) (hk0 : 0 < k) (hk1 : k < 1) :
    deriv (massFactor q) k = 0 ↔ k ^ 2 = 1 - q := by
  have hk4 : k ^ 4 < 1 := by nlinarith [pow_lt_one₀ hk0.le hk1 (by norm_num : (4 : ℕ) ≠ 0)]
  have hu : 0 < 1 - k ^ 4 := by linarith
  have hs : 0 < √(1 - k ^ 4) := Real.sqrt_pos.mpr hu
  rw [(massFactor_hasDerivAt q k hk4).deriv, div_eq_zero_iff]
  constructor
  · rintro (h | h)
    · rcases mul_eq_zero.mp h with h | h
      · linarith
      · linarith
    · nlinarith [mul_pos hu hs]
  · intro h; left; rw [h]; ring

/-- thompson1917-ch16-03: an interior critical point `k ∈ (0, 1)` exists if and only if the
core is lighter than the wall but not weightless, `0 < q < 1`. -/
theorem interior_critical_exists_iff (q : ℝ) :
    (∃ k, 0 < k ∧ k < 1 ∧ deriv (massFactor q) k = 0) ↔ 0 < q ∧ q < 1 := by
  constructor
  · rintro ⟨k, hk0, hk1, hd⟩
    have h := (massFactor_deriv_eq_zero_iff q k hk0 hk1).mp hd
    constructor <;> nlinarith
  · rintro ⟨hq0, hq1⟩
    have h1 : 0 < 1 - q := by linarith
    have hk0 : 0 < √(1 - q) := Real.sqrt_pos.mpr h1
    have hk1 : √(1 - q) < 1 := by
      rw [Real.sqrt_lt' one_pos]; linarith
    refine ⟨√(1 - q), hk0, hk1, ?_⟩
    rw [massFactor_deriv_eq_zero_iff q _ hk0 hk1, Real.sq_sqrt h1.le]

/-- The minimum value: `μ(√(1 - q)) = √(q (2 - q))`. -/
theorem massFactor_at_optimum (q : ℝ) (hq0 : 0 < q) (hq1 : q < 1) :
    massFactor q √(1 - q) = √(q * (2 - q)) := by
  unfold massFactor
  have h1 : 0 ≤ 1 - q := by linarith
  have hk2 : √(1 - q) ^ 2 = 1 - q := Real.sq_sqrt h1
  have hk4 : √(1 - q) ^ 4 = (1 - q) ^ 2 := by
    rw [show (4 : ℕ) = 2 * 2 from rfl, pow_mul, hk2]
  rw [hk4, hk2]
  have e1 : 1 - (1 - q) + q * (1 - q) = q * (2 - q) := by ring
  have e2 : 1 - (1 - q) ^ 2 = q * (2 - q) := by ring
  rw [e1, e2]
  have hp : 0 < q * (2 - q) := by nlinarith
  rw [div_eq_iff (Real.sqrt_pos.mpr hp).ne', Real.mul_self_sqrt hp.le]

/-- thompson1917-ch16-03 (interior minimum): for `0 < q < 1`, `k* = √(1 - q)` is the unique
minimizer of the mass at fixed stiffness over `[0, 1)`. -/
theorem massFactor_lt_of_ne_optimum (q k : ℝ) (hq0 : 0 < q) (hq1 : q < 1) (hk0 : 0 ≤ k)
    (hk1 : k < 1) (hne : k ≠ √(1 - q)) :
    massFactor q √(1 - q) < massFactor q k := by
  rw [massFactor_at_optimum q hq0 hq1]
  unfold massFactor
  have hk4 : k ^ 4 < 1 := by nlinarith [pow_lt_one₀ hk0 hk1 (by norm_num : (4 : ℕ) ≠ 0)]
  have hu : 0 < 1 - k ^ 4 := by linarith
  have hs : 0 < √(1 - k ^ 4) := Real.sqrt_pos.mpr hu
  have hN : 0 < 1 - k ^ 2 + q * k ^ 2 := by nlinarith [pow_lt_one₀ hk0 hk1 (by norm_num : (2 : ℕ) ≠ 0)]
  have hx : k ^ 2 ≠ 1 - q := by
    intro h; apply hne
    rw [← h, Real.sqrt_sq hk0]
  have hq2 : 0 < q * (2 - q) := by nlinarith
  rw [lt_div_iff₀ hs, ← Real.sqrt_mul hq2.le, ← Real.sqrt_sq hN.le]
  apply Real.sqrt_lt_sqrt (mul_nonneg hq2.le hu.le)
  have : 0 < (k ^ 2 - (1 - q)) ^ 2 := by
    have : k ^ 2 - (1 - q) ≠ 0 := sub_ne_zero.mpr hx
    positivity
  nlinarith

/-- For `q ≥ 1` (a core at least as dense as the wall) the solid rod is optimal. -/
theorem massFactor_solid_optimal (q k : ℝ) (hq : 1 ≤ q) (hk0 : 0 ≤ k) (hk1 : k < 1) :
    massFactor q 0 ≤ massFactor q k := by
  unfold massFactor
  have hk4 : k ^ 4 < 1 := by nlinarith [pow_lt_one₀ hk0 hk1 (by norm_num : (4 : ℕ) ≠ 0)]
  have hu : 0 < 1 - k ^ 4 := by linarith
  have hs : 0 < √(1 - k ^ 4) := Real.sqrt_pos.mpr hu
  have hs1 : √(1 - k ^ 4) ≤ 1 := Real.sqrt_le_one.mpr (by nlinarith [pow_nonneg hk0 4])
  norm_num
  rw [le_div_iff₀ hs]
  nlinarith [mul_nonneg (by linarith : (0 : ℝ) ≤ q - 1) (sq_nonneg k)]

/-- Below the optimum the mass strictly decreases as the tube gets hollower. -/
theorem massFactor_strictAntiOn (q : ℝ) (hq0 : 0 < q) (hq1 : q < 1) :
    StrictAntiOn (massFactor q) (Set.Icc 0 √(1 - q)) := by
  have h1 : 0 < 1 - q := by linarith
  have hk1 : √(1 - q) < 1 := by rw [Real.sqrt_lt' one_pos]; linarith
  have hlt4 : ∀ x ∈ Set.Icc 0 √(1 - q), x ^ 4 < 1 := fun x hx => by
    nlinarith [pow_lt_one₀ hx.1 (lt_of_le_of_lt hx.2 hk1) (by norm_num : (4 : ℕ) ≠ 0)]
  apply strictAntiOn_of_deriv_neg (convex_Icc _ _)
  · intro x hx
    exact (massFactor_hasDerivAt q x (hlt4 x hx)).continuousAt.continuousWithinAt
  · intro x hx
    rw [interior_Icc] at hx
    have hx4 := hlt4 x (Set.Ioo_subset_Icc_self hx)
    rw [(massFactor_hasDerivAt q x hx4).deriv]
    have hu : 0 < 1 - x ^ 4 := by linarith
    have hs : 0 < √(1 - x ^ 4) := Real.sqrt_pos.mpr hu
    have hx2 : x ^ 2 < 1 - q := by
      have := hx.2
      have h0 := hx.1
      nlinarith [Real.sq_sqrt h1.le, Real.sqrt_nonneg (1 - q)]
    apply div_neg_of_neg_of_pos _ (by positivity)
    nlinarith [hx.1]

/-! ## Local buckling as a lower bound on wall thickness -/

/-- thompson1917-ch16-03 (constrained optimum): with the buckling bound `t/R = 1 - k ≥ λ`
(`λ = C σ / E`, `0 < λ ≤ 1`), the admissible ratio `min(√(1 - q), 1 - λ)` minimizes the mass
at fixed stiffness: the unconstrained optimum when it satisfies the bound, the boundary
otherwise. -/
theorem constrained_optimum (q lam k : ℝ) (hq0 : 0 < q) (hq1 : q < 1) (hlam0 : 0 < lam)
    (hlam1 : lam ≤ 1) (hk0 : 0 ≤ k) (hbuck : lam ≤ 1 - k) :
    lam ≤ 1 - min √(1 - q) (1 - lam) ∧
      massFactor q (min √(1 - q) (1 - lam)) ≤ massFactor q k := by
  refine ⟨by linarith [min_le_right √(1 - q) (1 - lam)], ?_⟩
  rcases le_total √(1 - q) (1 - lam) with h | h
  · rw [min_eq_left h]
    rcases eq_or_ne k √(1 - q) with hk | hk
    · rw [hk]
    · exact (massFactor_lt_of_ne_optimum q k hq0 hq1 hk0 (by linarith) hk).le
  · rw [min_eq_right h]
    exact (massFactor_strictAntiOn q hq0 hq1).antitoneOn ⟨hk0, by linarith⟩
      ⟨by linarith, h⟩ (by linarith)

/-- With a weightless core and the same buckling bound, the optimum is the boundary
`k = 1 - λ`: the thinnest wall that does not buckle. -/
theorem gasCore_constrained_optimum (lam k : ℝ) (hlam0 : 0 < lam) (hlam1 : lam ≤ 1)
    (hk0 : 0 ≤ k) (hbuck : lam ≤ 1 - k) :
    gasCoreAreaFactor (1 - lam) ≤ gasCoreAreaFactor k :=
  gasCoreAreaFactor_strictAntiOn.antitoneOn ⟨hk0, by linarith⟩ ⟨by linarith, by linarith⟩
    (by linarith)

end

end ThompsonLaws.HollowTube
