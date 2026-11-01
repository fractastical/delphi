import Mathlib

/-!
# Murray's cubic law from a minimum-work cost

Thompson (ch. XV) states the principle that blood-vessels are arranged so that the
circulation proceeds with a minimum of effort. Murray (1926) turned the principle into a
cost: the power to drive flow `Q` through a vessel of radius `r` against Poiseuille
resistance, plus the metabolic cost of keeping the vessel's blood volume. This module proves
that the cost is minimized exactly when `r³ ∝ Q`, hence the cubic junction law
`r₀³ = r₁³ + r₂³`, and then the general junction exponent `(b + c) / a` for a cost
`k Q^a / r^b + m r^c`.

On the turbulent exponent `7/3`: the equation `(b + 2) / a = 7/3` holds on the whole line
`3 b + 6 = 7 a`, so no unique pair `(a, b)` gives `7/3` in the unrestricted family (the
approach's "unique (a, b)" is corrected here). Uniqueness does hold inside the one-parameter
family produced by the Darcy–Weisbach law with friction factor `f ∝ Re^(-β)`, where
`(a, b) = (3 - β, 5 - β)`: the exponent is `7/3` only for `β = 0`, a Reynolds-independent
(fully rough) friction factor, giving `(a, b) = (3, 5)`. Laminar flow (`f = 64/Re`, `β = 1`)
gives back `3`. Whether any real vascular bed is in that regime is not a mathematical question.
-/

namespace ThompsonLaws.MurrayCubic

noncomputable section

open Real

/-! ## Poiseuille pumping plus blood volume -/

/-- thompson1917-ch15-13: Murray's cost per unit length of keeping flow `Q` through a vessel
of radius `r`: the Poiseuille pumping power `k Q² / r⁴` (`k = 8 η / π` for blood viscosity
`η`) plus the cost of maintaining the blood volume, `m r²` (`m` = π × metabolic cost per
unit volume of blood). -/
def poiseuilleCost (k m Q r : ℝ) : ℝ := k * Q ^ 2 / r ^ 4 + m * r ^ 2

/-- A radius `s` with `m s⁶ = 2 k Q²` (the stationarity condition) gives a strictly lower
cost than every other positive radius. -/
theorem poiseuilleCost_lt_of_stationary (k m Q r s : ℝ) (hm : 0 < m) (hr : 0 < r)
    (hs : 0 < s) (hopt : m * s ^ 6 = 2 * k * Q ^ 2) (hne : r ≠ s) :
    poiseuilleCost k m Q s < poiseuilleCost k m Q r := by
  unfold poiseuilleCost
  have hkQ : k * Q ^ 2 = m * s ^ 6 / 2 := by linarith
  rw [hkQ]
  have hr4 : 0 < r ^ 4 := by positivity
  have hs4 : 0 < s ^ 4 := by positivity
  have hsq : r ^ 2 ≠ s ^ 2 := by
    intro h
    exact hne (by nlinarith [sq_nonneg (r - s), sq_nonneg (r + s)])
  have hkey : 0 < (r ^ 2 - s ^ 2) ^ 2 * (2 * r ^ 2 + s ^ 2) := by
    have : 0 < (r ^ 2 - s ^ 2) ^ 2 := by
      have : r ^ 2 - s ^ 2 ≠ 0 := sub_ne_zero.mpr hsq
      positivity
    positivity
  rw [div_add' _ _ _ hs4.ne', div_add' _ _ _ hr4.ne', div_lt_div_iff₀ hs4 hr4]
  nlinarith [mul_pos hm hkey, mul_pos (mul_pos hm hkey) hs4]

/-- The stationarity condition has a positive solution for every flow. -/
theorem poiseuille_stationary_exists (k m Q : ℝ) (hk : 0 < k) (hm : 0 < m) (hQ : 0 < Q) :
    ∃ s : ℝ, 0 < s ∧ m * s ^ 6 = 2 * k * Q ^ 2 := by
  refine ⟨(2 * k * Q ^ 2 / m) ^ ((6 : ℕ)⁻¹ : ℝ), by positivity, ?_⟩
  rw [Real.rpow_inv_natCast_pow (by positivity) (by norm_num)]
  field_simp

/-- thompson1917-ch15-13 (Murray's law for one vessel): the radius that minimizes the
Poiseuille-plus-volume cost satisfies `r³ = √(2k/m) · Q`, so `r³ ∝ Q`. -/
theorem murray_cube_prop (k m Q s : ℝ) (hk : 0 < k) (hm : 0 < m) (hQ : 0 < Q) (hs : 0 < s)
    (hmin : ∀ r, 0 < r → poiseuilleCost k m Q s ≤ poiseuilleCost k m Q r) :
    s ^ 3 = Real.sqrt (2 * k / m) * Q := by
  obtain ⟨s₀, hs₀, hopt⟩ := poiseuille_stationary_exists k m Q hk hm hQ
  have hss : s = s₀ := by
    by_contra hne
    have := poiseuilleCost_lt_of_stationary k m Q s s₀ hm hs hs₀ hopt hne
    linarith [hmin s₀ hs₀]
  subst hss
  have h6 : (s ^ 3) ^ 2 = (2 * k / m) * Q ^ 2 := by field_simp; linarith
  rw [← Real.sqrt_sq (by positivity : (0 : ℝ) ≤ s ^ 3), h6,
    Real.sqrt_mul (by positivity), Real.sqrt_sq hQ.le]

/-- thompson1917-ch15-13 (Murray's cubic junction law): if a parent vessel carrying
`Q₀ = Q₁ + Q₂` and its two daughters each have the cost-minimizing radius, with the same
viscosity and volume-cost constants, then `r₀³ = r₁³ + r₂³`. -/
theorem murray_junction (k m Q₁ Q₂ r₀ r₁ r₂ : ℝ) (hk : 0 < k) (hm : 0 < m)
    (hQ₁ : 0 < Q₁) (hQ₂ : 0 < Q₂) (hr₀ : 0 < r₀) (hr₁ : 0 < r₁) (hr₂ : 0 < r₂)
    (h₀ : ∀ r, 0 < r → poiseuilleCost k m (Q₁ + Q₂) r₀ ≤ poiseuilleCost k m (Q₁ + Q₂) r)
    (h₁ : ∀ r, 0 < r → poiseuilleCost k m Q₁ r₁ ≤ poiseuilleCost k m Q₁ r)
    (h₂ : ∀ r, 0 < r → poiseuilleCost k m Q₂ r₂ ≤ poiseuilleCost k m Q₂ r) :
    r₀ ^ 3 = r₁ ^ 3 + r₂ ^ 3 := by
  rw [murray_cube_prop k m _ r₀ hk hm (by linarith) hr₀ h₀,
    murray_cube_prop k m _ r₁ hk hm hQ₁ hr₁ h₁, murray_cube_prop k m _ r₂ hk hm hQ₂ hr₂ h₂]
  ring

/-! ## General exponents -/

/-- Generalized minimum-work cost per unit length: a dissipation term `k Q^a / r^b` (flow
exponent `a`, resistance exponent `b`) plus a maintenance cost `m r^c` (`c = 2` for blood
volume, `c = 1` for wall surface). -/
def vesselCost (k m a b c Q r : ℝ) : ℝ := k * Q ^ a / r ^ b + m * r ^ c

/-- The radius solving the stationarity condition `b k Q^a = c m r^(b+c)`. -/
def optimalRadius (k m a b c Q : ℝ) : ℝ := (b * k * Q ^ a / (c * m)) ^ (1 / (b + c))

/-- The junction exponent `(b + c) / a`. -/
def junctionExponent (a b c : ℝ) : ℝ := (b + c) / a

/-- With `a = 2`, `b = 4`, `c = 2` the general cost is Murray's Poiseuille cost. -/
theorem vesselCost_poiseuille (k m Q r : ℝ) :
    vesselCost k m 2 4 2 Q r = poiseuilleCost k m Q r := by
  unfold vesselCost poiseuilleCost
  have h2 : ∀ x : ℝ, x ^ (2 : ℝ) = x ^ (2 : ℕ) := fun x => by
    exact_mod_cast Real.rpow_natCast x 2
  have h4 : ∀ x : ℝ, x ^ (4 : ℝ) = x ^ (4 : ℕ) := fun x => by
    exact_mod_cast Real.rpow_natCast x 4
  rw [h2, h4, h2]

theorem optimalRadius_pos (k m a b c Q : ℝ) (hk : 0 < k) (hm : 0 < m) (hb : 0 < b)
    (hc : 0 < c) (hQ : 0 < Q) : 0 < optimalRadius k m a b c Q := by
  unfold optimalRadius
  have : 0 < Q ^ a := Real.rpow_pos_of_pos hQ a
  positivity

/-- The optimal radius satisfies the stationarity condition. -/
theorem optimalRadius_stationary (k m a b c Q : ℝ) (hk : 0 < k) (hm : 0 < m) (hb : 0 < b)
    (hc : 0 < c) (hQ : 0 < Q) :
    optimalRadius k m a b c Q ^ (b + c) = b * k * Q ^ a / (c * m) := by
  unfold optimalRadius
  have : 0 < Q ^ a := Real.rpow_pos_of_pos hQ a
  rw [one_div, Real.rpow_inv_rpow (by positivity) (by linarith)]

/-- `e^x > 1 + x` for `x ≠ 0` gives the strict inequality behind the minimum: if
`b P = c R` then `P + R < P e^(-bL) + R e^(cL)` for every `L ≠ 0`. -/
theorem exp_balance_lt (P R b c L : ℝ) (hP : 0 < P) (hR : 0 < R) (hb : 0 < b) (hc : 0 < c)
    (hbal : b * P = c * R) (hL : L ≠ 0) :
    P + R < P * Real.exp (-(b * L)) + R * Real.exp (c * L) := by
  have h1 : -(b * L) + 1 < Real.exp (-(b * L)) :=
    Real.add_one_lt_exp (by
      intro h; apply hL; nlinarith [mul_eq_zero.mp (neg_eq_zero.mp h)] )
  have h2 : c * L + 1 < Real.exp (c * L) :=
    Real.add_one_lt_exp (mul_ne_zero hc.ne' hL)
  have e1 := mul_lt_mul_of_pos_left h1 hP
  have e2 := mul_lt_mul_of_pos_left h2 hR
  have hbalL : b * P * L = c * R * L := by rw [hbal]
  linear_combination e1 + e2 + hbalL

/-- thompson1917-ch15-13 (general form): for positive exponents `b`, `c` and constants, the
stationary radius is the strict global minimizer of the cost over positive radii. -/
theorem vesselCost_lt (k m a b c Q r : ℝ) (hk : 0 < k) (hm : 0 < m) (hb : 0 < b)
    (hc : 0 < c) (hQ : 0 < Q) (hr : 0 < r) (hne : r ≠ optimalRadius k m a b c Q) :
    vesselCost k m a b c Q (optimalRadius k m a b c Q) < vesselCost k m a b c Q r := by
  set s := optimalRadius k m a b c Q with hs_def
  have hs : 0 < s := optimalRadius_pos k m a b c Q hk hm hb hc hQ
  have hstat := optimalRadius_stationary k m a b c Q hk hm hb hc hQ
  rw [← hs_def] at hstat
  have hA : 0 < k * Q ^ a := mul_pos hk (Real.rpow_pos_of_pos hQ a)
  set L := Real.log r - Real.log s with hL_def
  have hL : L ≠ 0 := by
    intro h
    apply hne
    have : Real.log r = Real.log s := by linarith
    exact Real.log_injOn_pos (Set.mem_Ioi.mpr hr) (Set.mem_Ioi.mpr hs) this
  have hrs : r = s * Real.exp L := by
    rw [hL_def, Real.exp_sub, Real.exp_log hr, Real.exp_log hs]
    field_simp
  have hpow : ∀ y : ℝ, r ^ y = s ^ y * Real.exp (y * L) := fun y => by
    rw [hrs, Real.mul_rpow hs.le (Real.exp_pos L).le, ← Real.exp_mul, mul_comm L y]
  have hsb : 0 < s ^ b := Real.rpow_pos_of_pos hs b
  have hsc : 0 < s ^ c := Real.rpow_pos_of_pos hs c
  have hbal : b * (k * Q ^ a / s ^ b) = c * (m * s ^ c) := by
    have hsbc : s ^ (b + c) = s ^ b * s ^ c := Real.rpow_add hs b c
    rw [hsbc] at hstat
    field_simp
    have : b * k * Q ^ a = c * m * (s ^ b * s ^ c) := by
      rw [hstat]; field_simp
    linarith
  have key := exp_balance_lt (k * Q ^ a / s ^ b) (m * s ^ c) b c L (by positivity)
    (by positivity) hb hc hbal hL
  unfold vesselCost
  rw [hpow b, hpow c, Real.exp_neg] at *
  calc k * Q ^ a / s ^ b + m * s ^ c
      < k * Q ^ a / s ^ b * (Real.exp (b * L))⁻¹ + m * s ^ c * Real.exp (c * L) := key
    _ = k * Q ^ a / (s ^ b * Real.exp (b * L)) + m * (s ^ c * Real.exp (c * L)) := by
        field_simp

/-- A positive radius that minimizes the cost is the stationary radius. -/
theorem eq_optimalRadius_of_isMin (k m a b c Q s : ℝ) (hk : 0 < k) (hm : 0 < m)
    (hb : 0 < b) (hc : 0 < c) (hQ : 0 < Q) (hs : 0 < s)
    (hmin : ∀ r, 0 < r → vesselCost k m a b c Q s ≤ vesselCost k m a b c Q r) :
    s = optimalRadius k m a b c Q := by
  by_contra hne
  have := vesselCost_lt k m a b c Q s hk hm hb hc hQ hs hne
  linarith [hmin _ (optimalRadius_pos k m a b c Q hk hm hb hc hQ)]

/-- The optimal radius raised to the junction exponent is proportional to the flow:
`r^((b+c)/a) = (b k / (c m))^(1/a) · Q`. -/
theorem optimalRadius_rpow_junctionExponent (k m a b c Q : ℝ) (hk : 0 < k) (hm : 0 < m)
    (ha : 0 < a) (hb : 0 < b) (hc : 0 < c) (hQ : 0 < Q) :
    optimalRadius k m a b c Q ^ junctionExponent a b c = (b * k / (c * m)) ^ (1 / a) * Q := by
  have hs := optimalRadius_pos k m a b c Q hk hm hb hc hQ
  have hstat := optimalRadius_stationary k m a b c Q hk hm hb hc hQ
  unfold junctionExponent
  rw [div_eq_mul_one_div (b + c) a, Real.rpow_mul hs.le, hstat,
    show b * k * Q ^ a / (c * m) = b * k / (c * m) * Q ^ a by ring,
    Real.mul_rpow (by positivity) (Real.rpow_pos_of_pos hQ a).le, one_div,
    Real.rpow_rpow_inv hQ.le ha.ne']

/-- thompson1917-ch15-13 (general junction law): at a junction `Q₀ = Q₁ + Q₂` where every
vessel minimizes the cost `k Q^a / r^b + m r^c` with shared constants, the radii obey
`r₀^α = r₁^α + r₂^α` with `α = (b + c) / a`. -/
theorem junction_law (k m a b c Q₁ Q₂ r₀ r₁ r₂ : ℝ) (hk : 0 < k) (hm : 0 < m) (ha : 0 < a)
    (hb : 0 < b) (hc : 0 < c) (hQ₁ : 0 < Q₁) (hQ₂ : 0 < Q₂)
    (hr₀ : 0 < r₀) (hr₁ : 0 < r₁) (hr₂ : 0 < r₂)
    (h₀ : ∀ r, 0 < r → vesselCost k m a b c (Q₁ + Q₂) r₀ ≤ vesselCost k m a b c (Q₁ + Q₂) r)
    (h₁ : ∀ r, 0 < r → vesselCost k m a b c Q₁ r₁ ≤ vesselCost k m a b c Q₁ r)
    (h₂ : ∀ r, 0 < r → vesselCost k m a b c Q₂ r₂ ≤ vesselCost k m a b c Q₂ r) :
    r₀ ^ junctionExponent a b c = r₁ ^ junctionExponent a b c + r₂ ^ junctionExponent a b c := by
  rw [eq_optimalRadius_of_isMin k m a b c _ r₀ hk hm hb hc (by linarith) hr₀ h₀,
    eq_optimalRadius_of_isMin k m a b c _ r₁ hk hm hb hc hQ₁ hr₁ h₁,
    eq_optimalRadius_of_isMin k m a b c _ r₂ hk hm hb hc hQ₂ hr₂ h₂,
    optimalRadius_rpow_junctionExponent k m a b c _ hk hm ha hb hc (by linarith),
    optimalRadius_rpow_junctionExponent k m a b c _ hk hm ha hb hc hQ₁,
    optimalRadius_rpow_junctionExponent k m a b c _ hk hm ha hb hc hQ₂]
  ring

/-- Poiseuille dissipation with a volume cost (`a = 2`, `b = 4`, `c = 2`) gives the cube. -/
theorem junctionExponent_poiseuille : junctionExponent 2 4 2 = 3 := by
  norm_num [junctionExponent]

/-- Poiseuille dissipation with a wall-surface cost instead (`c = 1`) gives `5/2`. -/
theorem junctionExponent_wallSurface : junctionExponent 2 4 1 = 5 / 2 := by
  norm_num [junctionExponent]

/-! ## Which exponents give 7/3 -/

/-- With a volume cost, the junction exponent is `7/3` exactly on the line `3 b + 6 = 7 a`. -/
theorem junctionExponent_eq_seven_thirds_iff (a b : ℝ) (ha : a ≠ 0) :
    junctionExponent a b 2 = 7 / 3 ↔ 3 * b + 6 = 7 * a := by
  unfold junctionExponent
  rw [div_eq_iff ha]
  constructor <;> intro h <;> linarith

/-- Hence the pair is not unique: `(3, 5)` and `(6, 12)` both give `7/3`. -/
theorem seven_thirds_not_unique :
    junctionExponent 3 5 2 = 7 / 3 ∧ junctionExponent 6 12 2 = 7 / 3 := by
  norm_num [junctionExponent]

/-- Among natural-number exponents the solutions are `a = 3t`, `b = 7t - 2`, and `(3, 5)` is
the smallest. -/
theorem seven_thirds_nat (a b : ℕ) (h : 3 * (b + 2) = 7 * a) :
    (∃ t, a = 3 * t ∧ b + 2 = 7 * t) ∧ 3 ≤ a ∧ (a = 3 → b = 5) := by
  refine ⟨⟨a / 3, by omega, by omega⟩, by omega, fun h3 => by omega⟩

/-- Darcy–Weisbach pumping power per unit length with friction factor `f ∝ Re^(-β)`: the
Reynolds number scales as `Q / r`, the mean velocity as `Q / r²`, and the pressure gradient as
`f v² / r`; the power is `Q` times the gradient (`κ` collects density, viscosity and numerical
factors). -/
def darcyPower (κ β Q r : ℝ) : ℝ := Q * (κ * (Q / r) ^ (-β) * (Q / r ^ 2) ^ 2 / r)

/-- The friction law yields the dissipation term of `vesselCost` with `a = 3 - β`,
`b = 5 - β`. -/
theorem darcyPower_eq (κ β Q r : ℝ) (hQ : 0 < Q) (hr : 0 < r) :
    darcyPower κ β Q r = κ * Q ^ (3 - β) / r ^ (5 - β) := by
  unfold darcyPower
  rw [Real.div_rpow hQ.le hr.le, Real.rpow_neg hQ.le, Real.rpow_neg hr.le,
    Real.rpow_sub hQ, Real.rpow_sub hr]
  have h3 : Q ^ (3 : ℝ) = Q ^ (3 : ℕ) := by exact_mod_cast Real.rpow_natCast Q 3
  have h5 : r ^ (5 : ℝ) = r ^ (5 : ℕ) := by exact_mod_cast Real.rpow_natCast r 5
  rw [h3, h5]
  have hQb : 0 < Q ^ β := Real.rpow_pos_of_pos hQ β
  have hrb : 0 < r ^ β := Real.rpow_pos_of_pos hr β
  field_simp

/-- Along the friction-law family the junction exponent is `(7 - β) / (3 - β)`; laminar
flow (`f = 64 / Re`, `β = 1`) gives `3`. -/
theorem junctionExponent_laminar : junctionExponent (3 - 1) (5 - 1) 2 = 3 := by
  norm_num [junctionExponent]

/-- The Blasius friction law (`β = 1/4`) gives `27/11`, not `7/3`. -/
theorem junctionExponent_blasius :
    junctionExponent (3 - 1 / 4) (5 - 1 / 4) 2 = 27 / 11 := by
  norm_num [junctionExponent]

/-- Within the friction-law family, the junction exponent is `7/3` if and only if `β = 0`
(a Reynolds-independent friction factor), i.e. `(a, b) = (3, 5)`: the unique pair. -/
theorem junctionExponent_friction_seven_thirds_iff (β : ℝ) (hβ : β < 3) :
    junctionExponent (3 - β) (5 - β) 2 = 7 / 3 ↔ β = 0 := by
  rw [junctionExponent_eq_seven_thirds_iff _ _ (by linarith)]
  constructor <;> intro h <;> linarith

end

end ThompsonLaws.MurrayCubic
