import Mathlib

namespace ThompsonLaws.Magnitude

open Filter Topology

/-- thompson1917-ch02-01: the weight–length coefficient `k = W / L³`. -/
noncomputable def weightCoeff (W L : ℝ) : ℝ := W / L ^ 3

/-- With weight `W = ρ · (c L³)` (density `ρ`, shape factor `c`), the coefficient is `ρ c`. -/
theorem weightCoeff_eq (ρ c L : ℝ) (hL : L ≠ 0) :
    weightCoeff (ρ * (c * L ^ 3)) L = ρ * c := by
  unfold weightCoeff; field_simp

/-- thompson1917-ch02-01: at constant density, `k` stays constant during growth iff the
shape factor `c` (the general form) stays constant. -/
theorem weightCoeff_const_iff_form_const (ρ : ℝ) (hρ : ρ ≠ 0) (c L : ℝ → ℝ)
    (hL : ∀ t, L t ≠ 0) :
    (∀ t s, weightCoeff (ρ * (c t * L t ^ 3)) (L t) = weightCoeff (ρ * (c s * L s ^ 3)) (L s))
      ↔ (∀ t s, c t = c s) := by
  simp only [weightCoeff_eq _ _ _ (hL _)]
  constructor
  · intro h t s
    exact mul_left_cancel₀ hρ (h t s)
  · intro h t s
    rw [h t s]

/-- thompson1917-ch02-02: Greenhill's critical height for a self-supporting column of base
diameter `d`, `h_crit = C d^{2/3}` (`C` bundles stiffness, density, gravity and taper). -/
noncomputable def greenhillCriticalHeight (C d : ℝ) : ℝ := C * d ^ ((2 : ℝ) / 3)

/-- The minimum diameter that keeps a column of height `h` from buckling. -/
noncomputable def greenhillMinDiameter (C h : ℝ) : ℝ := (h / C) ^ ((3 : ℝ) / 2)

/-- thompson1917-ch02-02: a column of height `h` stands without buckling iff its diameter is
at least `(h / C)^{3/2}`, i.e. the required diameter grows as `h^{3/2}`. -/
theorem greenhill_stands_iff (C d h : ℝ) (hC : 0 < C) (hd : 0 ≤ d) (hh : 0 ≤ h) :
    h ≤ greenhillCriticalHeight C d ↔ greenhillMinDiameter C h ≤ d := by
  unfold greenhillCriticalHeight greenhillMinDiameter
  have hhC : 0 ≤ h / C := div_nonneg hh hC.le
  have hdp : 0 ≤ d ^ ((2 : ℝ) / 3) := Real.rpow_nonneg hd _
  have hback : (d ^ ((2 : ℝ) / 3)) ^ ((3 : ℝ) / 2) = d := by
    rw [← Real.rpow_mul hd]; norm_num
  conv_rhs => rw [← hback]
  rw [Real.rpow_le_rpow_iff hhC hdp (by norm_num), div_le_iff₀' hC]

/-- thompson1917-ch02-02: multiplying the height by `λ` multiplies the minimum diameter by
`λ^{3/2}`. -/
theorem greenhillMinDiameter_scale (C h lam : ℝ) (hh : 0 ≤ h) (hC : 0 < C) (hlam : 0 ≤ lam) :
    greenhillMinDiameter C (lam * h) = lam ^ ((3 : ℝ) / 2) * greenhillMinDiameter C h := by
  unfold greenhillMinDiameter
  rw [mul_div_assoc, Real.mul_rpow hlam (div_nonneg hh hC.le)]

/-- thompson1917-ch02-03: strength ∝ L², weight ∝ L³ ⇒ strength/weight ∝ 1/L. -/
noncomputable def strengthToWeight (a b L : ℝ) : ℝ := (a * L ^ 2) / (b * L ^ 3)

theorem strengthToWeight_eq (a b L : ℝ) (hb : b ≠ 0) (hL : L ≠ 0) :
    strengthToWeight a b L = (a / b) * L⁻¹ := by
  unfold strengthToWeight; field_simp

/-- thompson1917-ch02-03: if supporting the body needs strength/weight at least `r > 0`,
the linear size is bounded above by `a / (b r)`. -/
theorem strengthToWeight_size_bound (a b L r : ℝ) (hb : 0 < b) (hL : 0 < L) (hr : 0 < r) :
    r ≤ strengthToWeight a b L ↔ L ≤ a / (b * r) := by
  rw [strengthToWeight_eq a b L hb.ne' hL.ne', le_div_iff₀ (mul_pos hb hr)]
  rw [show a / b * L⁻¹ = a / (b * L) by field_simp, le_div_iff₀ (mul_pos hb hL)]
  constructor <;> intro h <;> nlinarith

/-- thompson1917-ch02-05: ratio of muscular capacity (`a L³`) to the rate of energy supply
through the respiratory surface (`b L²`). -/
noncomputable def burstToSupplyRatio (a b L : ℝ) : ℝ := (a * L ^ 3) / (b * L ^ 2)

theorem burstToSupplyRatio_eq (a b L : ℝ) (hb : b ≠ 0) (hL : L ≠ 0) :
    burstToSupplyRatio a b L = (a / b) * L := by
  unfold burstToSupplyRatio; field_simp

/-- thompson1917-ch02-05: for a larger animal (`L₁ < L₂`) its advantage in burst capacity,
`(L₂/L₁)³`, exceeds its advantage in sustained energy supply, `(L₂/L₁)²`. -/
theorem burst_advantage_exceeds_supply_advantage (a b L₁ L₂ : ℝ) (ha : 0 < a) (hb : 0 < b)
    (h₁ : 0 < L₁) (h₁₂ : L₁ < L₂) :
    (b * L₂ ^ 2) / (b * L₁ ^ 2) < (a * L₂ ^ 3) / (a * L₁ ^ 3) := by
  have h₂ : 0 < L₂ := h₁.trans h₁₂
  rw [div_lt_div_iff₀ (by positivity) (by positivity)]
  have : b * a * L₂ ^ 2 * L₁ ^ 2 * L₁ < b * a * L₂ ^ 2 * L₁ ^ 2 * L₂ :=
    mul_lt_mul_of_pos_left h₁₂ (by positivity)
  nlinarith

/-- thompson1917-ch02-06: flight speed fixed by the momentum balance `l² V² ∝ l³`,
`V = √(k l)`. -/
noncomputable def flightSpeed (k l : ℝ) : ℝ := Real.sqrt (k * l)

/-- thompson1917-ch02-06: work of flight `W = m V²` with air mass `m = c l² V`. -/
noncomputable def flightWork (c k l : ℝ) : ℝ := c * l ^ 2 * flightSpeed k l ^ 3

/-- thompson1917-ch02-06: momentum of the downthrust air (`c₂ l² V²`) balancing the weight
(`c₁ l³`) forces `V = √((c₁/c₂) l)`. -/
theorem flightSpeed_of_balance (c₁ c₂ l V : ℝ) (hc₂ : 0 < c₂) (hl : 0 < l) (hV : 0 ≤ V)
    (h : c₂ * l ^ 2 * V ^ 2 = c₁ * l ^ 3) : V = flightSpeed (c₁ / c₂) l := by
  unfold flightSpeed
  have hV2 : V ^ 2 = c₁ / c₂ * l := by
    field_simp
    have hl2 : 0 < l ^ 2 := by positivity
    nlinarith [h]
  rw [← hV2, Real.sqrt_sq hV]

/-- thompson1917-ch02-06: `W² = c² k³ l⁷`, i.e. the work of flight varies as `l^{7/2}`. -/
theorem flightWork_sq (c k l : ℝ) (hk : 0 ≤ k) (hl : 0 ≤ l) :
    flightWork c k l ^ 2 = c ^ 2 * k ^ 3 * l ^ 7 := by
  unfold flightWork flightSpeed
  have hs : Real.sqrt (k * l) ^ 2 = k * l := Real.sq_sqrt (mul_nonneg hk hl)
  calc (c * l ^ 2 * Real.sqrt (k * l) ^ 3) ^ 2
      = c ^ 2 * l ^ 4 * (Real.sqrt (k * l) ^ 2) ^ 3 := by ring
    _ = c ^ 2 * k ^ 3 * l ^ 7 := by rw [hs]; ring

/-- thompson1917-ch02-06: doubling `l` multiplies the work of flight by `2³ √2`. -/
theorem flightWork_double (c k l : ℝ) :
    flightWork c k (2 * l) = 2 ^ 3 * Real.sqrt 2 * flightWork c k l := by
  unfold flightWork flightSpeed
  rw [show k * (2 * l) = 2 * (k * l) by ring, Real.sqrt_mul (by norm_num)]
  have h2 : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  have h3 : Real.sqrt 2 ^ 3 = 2 * Real.sqrt 2 := by
    rw [pow_succ, h2]
  rw [mul_pow, mul_pow, h3]; ring

/-- thompson1917-ch02-06: with muscular work `μ l³`, the difficulty of flight
(required work / available work) grows by `√2 ≈ 1.4` per doubling of length. -/
theorem flightDifficulty_double (c k μ l : ℝ) (hc : 0 < c) (hk : 0 < k) (hμ : 0 < μ)
    (hl : 0 < l) :
    (flightWork c k (2 * l) / (μ * (2 * l) ^ 3)) / (flightWork c k l / (μ * l ^ 3))
      = Real.sqrt 2 ∧ 1.4 < Real.sqrt 2 ∧ Real.sqrt 2 < 1.42 := by
  have hW : 0 < flightWork c k l := by
    unfold flightWork flightSpeed
    have : 0 < Real.sqrt (k * l) := Real.sqrt_pos.mpr (mul_pos hk hl)
    positivity
  refine ⟨?_, ?_, ?_⟩
  · rw [flightWork_double c k l]
    field_simp
  · rw [Real.lt_sqrt (by norm_num)]; norm_num
  · rw [Real.sqrt_lt' (by norm_num)]; norm_num

/-- thompson1917-ch02-09: height of a leap with impulse `x` imparted to mass `M`:
`v₀ = x / M`, `h = v₀² / 2g`. -/
noncomputable def jumpHeight (x M g : ℝ) : ℝ := (x / M) ^ 2 / (2 * g)

/-- thompson1917-ch02-09: with impulse proportional to muscle volume and hence to mass
(`x = β M`, Borelli's law), the jump height `β² / 2g` does not depend on size. -/
theorem jumpHeight_borelli (β M g : ℝ) (hM : M ≠ 0) :
    jumpHeight (β * M) M g = β ^ 2 / (2 * g) := by
  unfold jumpHeight; field_simp

theorem jumpHeight_same_actual (β M₁ M₂ g : ℝ) (h₁ : M₁ ≠ 0) (h₂ : M₂ ≠ 0) :
    jumpHeight (β * M₁) M₁ g = jumpHeight (β * M₂) M₂ g := by
  rw [jumpHeight_borelli β M₁ g h₁, jumpHeight_borelli β M₂ g h₂]

/-- thompson1917-ch02-10: a speed law `V(L)` of the form `C √L` for all `L > 0`. -/
def VelocityScalesAsSqrt (V : ℝ → ℝ) : Prop := ∃ C : ℝ, ∀ L, 0 < L → V L = C * Real.sqrt L

/-- Swimming at a fixed Froude number `Fr = V / √(g L)`. -/
noncomputable def froudeSpeed (Fr g L : ℝ) : ℝ := Fr * Real.sqrt (g * L)

/-- Walking with the leg as a pendulum of length `L`: stride `a L` per period `2π √(L/g)`. -/
noncomputable def pendulumWalkSpeed (a g L : ℝ) : ℝ :=
  a * L / (2 * Real.pi * Real.sqrt (L / g))

theorem froudeSpeed_sqrt (Fr g : ℝ) (hg : 0 ≤ g) : VelocityScalesAsSqrt (froudeSpeed Fr g) :=
  ⟨Fr * Real.sqrt g, fun L _ => by
    unfold froudeSpeed; rw [Real.sqrt_mul hg]; ring⟩

theorem flightSpeed_sqrt (k : ℝ) (hk : 0 ≤ k) : VelocityScalesAsSqrt (flightSpeed k) :=
  ⟨Real.sqrt k, fun L _ => by unfold flightSpeed; rw [Real.sqrt_mul hk]⟩

theorem pendulumWalkSpeed_sqrt (a g : ℝ) (hg : 0 < g) :
    VelocityScalesAsSqrt (pendulumWalkSpeed a g) :=
  ⟨a * Real.sqrt g / (2 * Real.pi), fun L hL => by
    unfold pendulumWalkSpeed
    have hsL : 0 < Real.sqrt L := Real.sqrt_pos.mpr hL
    have hsg : 0 < Real.sqrt g := Real.sqrt_pos.mpr hg
    have hLL : Real.sqrt L ^ 2 = L := Real.sq_sqrt hL.le
    rw [Real.sqrt_div hL.le]
    field_simp
    rw [hLL]⟩

/-- thompson1917-ch02-10: swimming (Froude), flight (minimum speed) and walking (pendulum
leg) all give `V ∝ √L`. -/
theorem locomotion_speed_sqrt (Fr g k a : ℝ) (hg : 0 < g) (hk : 0 ≤ k) :
    VelocityScalesAsSqrt (froudeSpeed Fr g) ∧ VelocityScalesAsSqrt (flightSpeed k) ∧
      VelocityScalesAsSqrt (pendulumWalkSpeed a g) :=
  ⟨froudeSpeed_sqrt Fr g hg.le, flightSpeed_sqrt k hk, pendulumWalkSpeed_sqrt a g hg⟩

/-- thompson1917-ch02-12: surface-to-mass ratio with surface `σ L²` (`σ` encodes the
folding of the surface) and mass `ρ c L³`. -/
noncomputable def surfaceToMass (σ ρ c L : ℝ) : ℝ := (σ * L ^ 2) / (ρ * c * L ^ 3)

/-- thompson1917-ch02-12: for similar forms (fixed `σ`), `S/M ∝ 1/L`. -/
theorem surfaceToMass_similar (σ ρ c L : ℝ) (hρ : ρ ≠ 0) (hc : c ≠ 0) (hL : L ≠ 0) :
    surfaceToMass σ ρ c L = σ / (ρ * c) * L⁻¹ := by
  unfold surfaceToMass; field_simp

/-- thompson1917-ch02-12: keeping `S/M` at a constant `κ` requires the surface factor to
grow in proportion to size, `σ = κ ρ c L`, i.e. a change of form. -/
theorem surfaceToMass_const_iff (σ ρ c L κ : ℝ) (hρ : ρ ≠ 0) (hc : c ≠ 0) (hL : L ≠ 0) :
    surfaceToMass σ ρ c L = κ ↔ σ = κ * ρ * c * L := by
  unfold surfaceToMass
  rw [div_eq_iff (by positivity)]
  constructor
  · intro h
    have hL2 : L ^ 2 ≠ 0 := pow_ne_zero 2 hL
    apply mul_right_cancel₀ hL2
    linear_combination h
  · intro h; rw [h]; ring

/-- thompson1917-ch02-15: surface of a sphere of volume `V`, `(36π)^{1/3} V^{2/3}`. -/
noncomputable def sphereSurface (V : ℝ) : ℝ :=
  (36 * Real.pi) ^ ((1 : ℝ) / 3) * V ^ ((2 : ℝ) / 3)

/-- thompson1917-ch02-15: dividing a spherical cell of volume `V` into `n` equal spheres
multiplies the total surface by `n^{1/3}` at unchanged total volume. -/
theorem division_total_surface (V n : ℝ) (hV : 0 ≤ V) (hn : 0 < n) :
    n * sphereSurface (V / n) = n ^ ((1 : ℝ) / 3) * sphereSurface V := by
  unfold sphereSurface
  rw [Real.div_rpow hV hn.le]
  have key : n ^ ((1 : ℝ) / 3) * n ^ ((2 : ℝ) / 3) = n := by
    rw [← Real.rpow_add hn]; norm_num
  have hpos : 0 < n ^ ((2 : ℝ) / 3) := Real.rpow_pos_of_pos hn _
  calc n * ((36 * Real.pi) ^ ((1 : ℝ) / 3) * (V ^ ((2 : ℝ) / 3) / n ^ ((2 : ℝ) / 3)))
      = (n ^ ((1 : ℝ) / 3) * n ^ ((2 : ℝ) / 3)) *
          ((36 * Real.pi) ^ ((1 : ℝ) / 3) * (V ^ ((2 : ℝ) / 3) / n ^ ((2 : ℝ) / 3))) := by
        rw [key]
    _ = n ^ ((1 : ℝ) / 3) * ((36 * Real.pi) ^ ((1 : ℝ) / 3) * V ^ ((2 : ℝ) / 3)) := by
        field_simp

/-- thompson1917-ch02-15: cleavage into `n > 1` cells strictly increases total surface
(`V > 0` fixed). -/
theorem division_increases_surface (V n : ℝ) (hV : 0 < V) (hn : 1 < n) :
    sphereSurface V < n * sphereSurface (V / n) := by
  rw [division_total_surface V n hV.le (by linarith)]
  have hS : 0 < sphereSurface V := by
    unfold sphereSurface
    have := Real.pi_pos
    positivity
  have h1 : 1 < n ^ ((1 : ℝ) / 3) := Real.one_lt_rpow hn (by norm_num)
  nlinarith

/-- thompson1917-ch02-15: a cell that has doubled its volume to `2v` and divides in two
restores each daughter's surface-to-volume ratio to that of the original cell of volume `v`. -/
theorem division_restores_surface_ratio (v : ℝ) :
    sphereSurface (2 * v / 2) / (2 * v / 2) = sphereSurface v / v := by
  rw [mul_div_cancel_left₀ v two_ne_zero]

/-- thompson1917-ch03-07: weight of an organism of fixed form, `W = k L³`. -/
def weightOfLength (k L : ℝ) : ℝ := k * L ^ 3

/-- thompson1917-ch03-07: whatever the growth law `L(t)`, the weight ratio between two ages is
the cube of the length ratio. -/
theorem weightOfLength_ratio (k : ℝ) (hk : k ≠ 0) (L : ℝ → ℝ) (t s : ℝ) (hs : L s ≠ 0) :
    weightOfLength k (L t) / weightOfLength k (L s) = (L t / L s) ^ 3 := by
  unfold weightOfLength; field_simp

/-- thompson1917-ch03-07: the weight curve's growth rate is `3 k L² L'`, so its shape differs
from that of the length curve. -/
theorem weightOfLength_hasDerivAt (k : ℝ) (L : ℝ → ℝ) (L' t : ℝ) (hL : HasDerivAt L L' t) :
    HasDerivAt (fun t => weightOfLength k (L t)) (3 * k * L t ^ 2 * L') t := by
  unfold weightOfLength
  have := (hL.pow 3).const_mul k
  convert this using 1
  push_cast; ring

/-- thompson1917-ch03-21: van 't Hoff rate law `v(θ) = v₀ xᶿ` with temperature coefficient
`x` per degree. -/
noncomputable def vantHoffRate (v₀ x θ : ℝ) : ℝ := v₀ * x ^ θ

/-- thompson1917-ch03-21: a rise of `n` degrees multiplies the rate by `xⁿ`. -/
theorem vantHoffRate_shift (v₀ x θ n : ℝ) (hx : 0 < x) :
    vantHoffRate v₀ x (θ + n) = x ^ n * vantHoffRate v₀ x θ := by
  unfold vantHoffRate; rw [Real.rpow_add hx]; ring

/-- thompson1917-ch03-21: the ten-degree coefficient is `x^{10}`. -/
theorem vantHoffRate_q10 (v₀ x θ : ℝ) (hv : v₀ ≠ 0) (hx : 0 < x) :
    vantHoffRate v₀ x (θ + 10) / vantHoffRate v₀ x θ = x ^ (10 : ℝ) := by
  rw [vantHoffRate_shift v₀ x θ 10 hx]
  unfold vantHoffRate
  have : x ^ θ ≠ 0 := (Real.rpow_pos_of_pos hx θ).ne'
  field_simp

/-- thompson1917-ch03-23: growth curve with an annual sine term, `L̄(t) + A(t) sin(2πt)`
(`t` in years). -/
noncomputable def seasonalGrowth (Lbar A : ℝ → ℝ) (t : ℝ) : ℝ :=
  Lbar t + A t * Real.sin (2 * Real.pi * t)

/-- thompson1917-ch03-23: with amplitude proportional to the growth rate `r(t)`, the seasonal
fluctuation dies away as growth slows (a damped sine curve). -/
theorem seasonalGrowth_damped (Lbar A r : ℝ → ℝ) (c : ℝ) (hA : ∀ t, A t = c * r t)
    (hr : Tendsto r atTop (𝓝 0)) :
    Tendsto (fun t => seasonalGrowth Lbar A t - Lbar t) atTop (𝓝 0) := by
  have hA0 : Tendsto A atTop (𝓝 0) := by
    have := hr.const_mul c
    rw [mul_zero] at this
    exact this.congr (fun t => (hA t).symm)
  apply squeeze_zero_norm (a := fun t => ‖A t‖)
  · intro t
    unfold seasonalGrowth
    rw [add_sub_cancel_left, norm_mul]
    exact mul_le_of_le_one_right (norm_nonneg _) (by
      rw [Real.norm_eq_abs]; exact Real.abs_sin_le_one _)
  · exact (tendsto_zero_iff_norm_tendsto_zero).mp hA0

/-- thompson1917-ch03-23: the seasonal term has a period of one year. -/
theorem seasonalGrowth_annual (A : ℝ → ℝ) (t : ℝ) :
    A t * Real.sin (2 * Real.pi * (t + 1)) = A t * Real.sin (2 * Real.pi * t) := by
  rw [show 2 * Real.pi * (t + 1) = 2 * Real.pi * t + 2 * Real.pi by ring, Real.sin_add_two_pi]

/-- thompson1917-ch03-30: regenerative growth velocity with `V T² = C`. -/
noncomputable def regenVelocity (C T : ℝ) : ℝ := C / T ^ 2

/-- thompson1917-ch03-30: the family `V^m T^n = K` is a straight line in log–log coordinates,
`log V = (log K − n log T) / m`. -/
theorem regen_log_linear (V T K m n : ℝ) (hV : 0 < V) (hT : 0 < T) (hm : m ≠ 0)
    (h : V ^ m * T ^ n = K) : Real.log V = (Real.log K - n * Real.log T) / m := by
  have hK := congrArg Real.log h
  rw [Real.log_mul (Real.rpow_pos_of_pos hV m).ne' (Real.rpow_pos_of_pos hT n).ne',
    Real.log_rpow hV, Real.log_rpow hT] at hK
  rw [eq_div_iff hm]; linarith

/-- thompson1917-ch03-30: `regenVelocity` is the member `m = 1, n = 2` of that family. -/
theorem regenVelocity_family (C T : ℝ) (hT : 0 < T) :
    regenVelocity C T ^ (1 : ℝ) * T ^ (2 : ℝ) = C := by
  unfold regenVelocity
  rw [Real.rpow_one, Real.rpow_two]
  field_simp

/-- thompson1917-ch03-30: with `C > 0` the velocity falls as time since injury grows. -/
theorem regenVelocity_decreasing (C T₁ T₂ : ℝ) (hC : 0 < C) (h₁ : 0 < T₁) (h₁₂ : T₁ < T₂) :
    regenVelocity C T₂ < regenVelocity C T₁ := by
  unfold regenVelocity
  apply div_lt_div_of_pos_left hC (by positivity)
  exact pow_lt_pow_left₀ h₁₂ h₁.le two_ne_zero

end ThompsonLaws.Magnitude
