/-
  GeometricSimilarity -- how wing loading and required (stall) speed scale under explicit
  geometric similarity with unchanged air density, lift coefficient and gravity.

  Setting (all over the real numbers; every symbol positive):
    m  mass [kg]      S  wing area [m^2]     g  gravity [m/s^2]
    rho air density [kg/m^3]                 C  lift coefficient [1] (assumed unchanged)
    k  length ratio, with area ratio k^2 and mass ratio k^3 (same body density) -- an ASSUMPTION
       of the model, stated as the hypotheses of `scaling_laws`, not derived here.

  What this file proves:  an exact scaling law of two defined formulas.
  What it does NOT prove:  that any organism can fly, that Fish's measured allometry
  (wing loading ~ M^0.36-0.53, steeper than the isometric 1/3) holds or is explained, or that
  C and rho are constant across sizes. Dimensional correspondence (kg, m, s) is checked in
  Python (engineering/constraints.py), not here.
-/
import Mathlib.Analysis.SpecialFunctions.Pow.Real
import Mathlib.Tactic

namespace FlyingFish

/-- Wing loading `m g / S`  [N/m^2]. -/
noncomputable def wingLoading (m g S : ℝ) : ℝ := m * g / S

/-- Level-flight proxy speed at lift coefficient `C` (L = W; a glide needs only W cos gamma): `sqrt (2 m g / (rho S C))` [m/s]. -/
noncomputable def stallSpeed (m g rho S C : ℝ) : ℝ := Real.sqrt (2 * m * g / (rho * S * C))

/-- Wing loading scales as `k`. -/
theorem wingLoading_scale {m g S k : ℝ} (hS : 0 < S) (hk : 0 < k) :
    wingLoading (k ^ 3 * m) g (k ^ 2 * S) = k * wingLoading m g S := by
  unfold wingLoading
  field_simp

/-- Squared stall speed scales as `k`. -/
theorem stallSpeed_sq_scale {m g rho S C k : ℝ} (hm : 0 < m) (hg : 0 < g) (hrho : 0 < rho)
    (hS : 0 < S) (hC : 0 < C) (hk : 0 < k) :
    stallSpeed (k ^ 3 * m) g rho (k ^ 2 * S) C ^ 2 = k * stallSpeed m g rho S C ^ 2 := by
  unfold stallSpeed
  have h1 : 0 ≤ 2 * (k ^ 3 * m) * g / (rho * (k ^ 2 * S) * C) := by positivity
  have h2 : 0 ≤ 2 * m * g / (rho * S * C) := by positivity
  rw [Real.sq_sqrt h1, Real.sq_sqrt h2]
  field_simp

/-- Stall speed scales as `sqrt k`. -/
theorem stallSpeed_scale {m g rho S C k : ℝ} (hm : 0 < m) (hg : 0 < g) (hrho : 0 < rho)
    (hS : 0 < S) (hC : 0 < C) (hk : 0 < k) :
    stallSpeed (k ^ 3 * m) g rho (k ^ 2 * S) C = Real.sqrt k * stallSpeed m g rho S C := by
  unfold stallSpeed
  have e : 2 * (k ^ 3 * m) * g / (rho * (k ^ 2 * S) * C) = k * (2 * m * g / (rho * S * C)) := by
    field_simp
  rw [e, Real.sqrt_mul hk.le]

/-- Isometric mass exponent: with mass ratio `mu = k^3`, `WL'^3 = mu * WL^3`, i.e. wing loading
    goes as mass^(1/3).  This is the isometric reference exponent 0.33 that Fish (1990) tests
    against; it is the null the data are compared with, not a claim about the data. -/
theorem wingLoading_mass_exponent {m g S k : ℝ} (hS : 0 < S) (hk : 0 < k) :
    wingLoading (k ^ 3 * m) g (k ^ 2 * S) ^ 3 = (k ^ 3) * wingLoading m g S ^ 3 := by
  rw [wingLoading_scale hS hk]; ring

/-- Bundle: the three scaling laws under the stated similarity hypotheses. -/
theorem scaling_laws {m g rho S C k : ℝ} (hm : 0 < m) (hg : 0 < g) (hrho : 0 < rho)
    (hS : 0 < S) (hC : 0 < C) (hk : 0 < k) :
    wingLoading (k ^ 3 * m) g (k ^ 2 * S) = k * wingLoading m g S ∧
    stallSpeed (k ^ 3 * m) g rho (k ^ 2 * S) C ^ 2 = k * stallSpeed m g rho S C ^ 2 ∧
    wingLoading (k ^ 3 * m) g (k ^ 2 * S) ^ 3 = (k ^ 3) * wingLoading m g S ^ 3 :=
  ⟨wingLoading_scale hS hk, stallSpeed_sq_scale hm hg hrho hS hC hk,
   wingLoading_mass_exponent hS hk⟩

/-- Wing-loading ceiling at a speed: if lift can carry the weight at speed `V`
    (`V^2 rho S C >= 2 m g`) then `2 * WL <= rho V^2 C`.  This is the universally quantified
    reason behind the solver's "wing loading too high for the speed cap" conflicts. -/
theorem wingLoading_ceiling {m g rho S C V : ℝ} (hS : 0 < S)
    (h : 2 * m * g ≤ V ^ 2 * rho * S * C) :
    2 * wingLoading m g S ≤ rho * V ^ 2 * C := by
  unfold wingLoading
  rw [← mul_div_assoc, div_le_iff₀ hS]
  nlinarith [h]

/-- A solver-emitted conflict certificate is valid when: the user wants wing loading at least
    `wlmin`, speed is capped at `vmax`, lift carries weight, and `rho vmax^2 C < 2 wlmin`. -/
theorem conflict_of_certificate {m g rho S C V wlmin vmax : ℝ} (hS : 0 < S) (hV0 : 0 ≤ V)
    (hrho : 0 < rho) (hC : 0 < C)
    (hwl : wlmin ≤ wingLoading m g S) (hV : V ≤ vmax)
    (hlift : 2 * m * g ≤ V ^ 2 * rho * S * C)
    (hcert : rho * vmax ^ 2 * C < 2 * wlmin) : False := by
  have h1 := wingLoading_ceiling (m := m) (g := g) (rho := rho) (S := S) (C := C) (V := V) hS hlift
  have h2 : V ^ 2 ≤ vmax ^ 2 := by nlinarith
  have h3 : rho * V ^ 2 * C ≤ rho * vmax ^ 2 * C := by
    have : 0 < rho * C := mul_pos hrho hC
    nlinarith
  linarith

end FlyingFish
