import Mathlib

/-!
# Horns, leaf arrangements, eggs and blood vessels (Thompson 1917, chapters XIII–XV)

Horn growth: a horn grows at its base, one side (length `s`, the slower side) at rate `s'`
and the opposite side at rate `ρ * s'`, both measured per unit of total turning `θ` of the
horn's axis. Bending a strip of width `w` through `dθ` makes the outer side longer than the
inner by `w dθ`, so `(ρ - 1) s' = w`. If the horn widens in proportion to its length
(`w = β s`, a cone of fixed taper), the length grows exponentially in the turning angle,
`s = s₀ e^{θ cot α}` with `cot α = β / (ρ - 1)`: the intrinsic (Whewell) equation of a
logarithmic spiral of constant angle `α`.
-/

namespace ThompsonLaws.HornsLeavesEggs

open Real Filter Topology

/-- Spiral constant `cot α = β / (ρ - 1)` of a horn whose two opposite sides grow in the
constant ratio `ρ` and whose width is `β` times the length of its slower side. -/
noncomputable def hornSpiralRate (ρ β : ℝ) : ℝ := β / (ρ - 1)

/-- thompson1917-ch13-01: constant ratio `ρ` of anterior to posterior growth, with width
proportional to length, makes the horn's length grow as `s₀ e^{θ cot α}` in its turning
angle `θ`: a logarithmic spiral. -/
theorem hornLength_eq_exp (ρ β : ℝ) (s sOut w : ℝ → ℝ) (hρ : 1 < ρ)
    (hs : Differentiable ℝ s)
    (hratio : ∀ θ, deriv sOut θ = ρ * deriv s θ)
    (hbend : ∀ θ, deriv sOut θ - deriv s θ = w θ)
    (hwidth : ∀ θ, w θ = β * s θ) :
    ∀ θ, s θ = s 0 * Real.exp (hornSpiralRate ρ β * θ) := by
  set k := hornSpiralRate ρ β
  have hρ1 : ρ - 1 ≠ 0 := by linarith
  have hds : ∀ θ, deriv s θ = k * s θ := by
    intro θ
    have h := hbend θ
    rw [hratio θ, hwidth θ] at h
    have : (ρ - 1) * deriv s θ = β * s θ := by linarith
    simp only [k, hornSpiralRate]
    field_simp
    linarith
  let g : ℝ → ℝ := fun θ => s θ * Real.exp (-(k * θ))
  have hg : ∀ θ, HasDerivAt g (deriv s θ * Real.exp (-(k * θ)) +
      s θ * (Real.exp (-(k * θ)) * (-(k * 1)))) θ := by
    intro θ
    have h1 := (hs θ).hasDerivAt
    have h2 : HasDerivAt (fun x => Real.exp (-(k * x))) (Real.exp (-(k * θ)) * (-(k * 1))) θ :=
      ((hasDerivAt_id θ).const_mul k).neg.exp
    exact h1.mul h2
  have hg0 : ∀ θ, deriv g θ = 0 := by
    intro θ
    rw [(hg θ).deriv, hds θ]
    ring
  have hgd : Differentiable ℝ g := fun θ => (hg θ).differentiableAt
  intro θ
  have hc := is_const_of_deriv_eq_zero hgd hg0 θ 0
  simp only [g, mul_zero, neg_zero, Real.exp_zero, mul_one] at hc
  have he : Real.exp (-(k * θ)) * Real.exp (k * θ) = 1 := by
    rw [← Real.exp_add]; simp
  calc s θ = s θ * Real.exp (-(k * θ)) * Real.exp (k * θ) := by rw [mul_assoc, he, mul_one]
    _ = s 0 * Real.exp (k * θ) := by rw [hc]

/-- thompson1917-ch13-03: while the ratio `ρ` of growth on opposite sides stays constant,
every further turning through `φ` multiplies the horn by the same factor `e^{φ cot α}`,
whatever stage of growth it starts from: a continuous, self-similar logarithmic spiral. -/
theorem hornLength_selfSimilar (ρ β : ℝ) (s sOut w : ℝ → ℝ) (hρ : 1 < ρ)
    (hs : Differentiable ℝ s)
    (hratio : ∀ θ, deriv sOut θ = ρ * deriv s θ)
    (hbend : ∀ θ, deriv sOut θ - deriv s θ = w θ)
    (hwidth : ∀ θ, w θ = β * s θ) (θ φ : ℝ) :
    s (θ + φ) = Real.exp (hornSpiralRate ρ β * φ) * s θ := by
  have h := hornLength_eq_exp ρ β s sOut w hρ hs hratio hbend hwidth
  rw [h (θ + φ), h θ, mul_add, Real.exp_add]
  ring

/-- thompson1917-ch13-03: the more nearly equal the growth on the two sides (`ρ` closer
to 1), the larger the spiral constant `cot α`, i.e. the straighter the horn. -/
theorem hornSpiralRate_antitone (β ρ₁ ρ₂ : ℝ) (hβ : 0 < β) (h1 : 1 < ρ₁) (h12 : ρ₁ < ρ₂) :
    hornSpiralRate ρ₂ β < hornSpiralRate ρ₁ β := by
  unfold hornSpiralRate
  exact div_lt_div_of_pos_left hβ (by linarith) (by linarith)

/-- thompson1917-ch13-13: a claw, beak or tooth grown by permanent increments with constant
unequal growth has turned through only `θ = tan α · log (s / s₀)` by the time it reaches
length `s`, so its spiral is conspicuous only once it is long. -/
theorem accretionTurning_eq_log (ρ β : ℝ) (s sOut w : ℝ → ℝ) (hρ : 1 < ρ) (hβ : 0 < β)
    (hs : Differentiable ℝ s) (hs0 : 0 < s 0)
    (hratio : ∀ θ, deriv sOut θ = ρ * deriv s θ)
    (hbend : ∀ θ, deriv sOut θ - deriv s θ = w θ)
    (hwidth : ∀ θ, w θ = β * s θ) (θ : ℝ) :
    θ = (ρ - 1) / β * Real.log (s θ / s 0) := by
  have h := hornLength_eq_exp ρ β s sOut w hρ hs hratio hbend hwidth θ
  rw [h, mul_div_cancel_left₀ _ hs0.ne', Real.log_exp]
  unfold hornSpiralRate
  have hρ1 : ρ - 1 ≠ 0 := by linarith
  field_simp

/-- Cross product (axial component) of the unit directions `φ₁`, `φ₂` of fastest and
slowest growth around the horn's basal annulus; zero iff both lie in one plane through the
horn's axis. -/
noncomputable def growthDirectionsCross (φ₁ φ₂ : ℝ) : ℝ :=
  Real.cos φ₁ * Real.sin φ₂ - Real.sin φ₁ * Real.cos φ₂

/-- thompson1917-ch13-06: the directions of maximal and minimal growth (distinct points of
the basal annulus) lie in a single plane through the axis, the condition for a plane
spiral, iff they are diametrically opposite (`cos Δφ = -1`). -/
theorem growthDirections_coplanar_iff_opposite (φ₁ φ₂ : ℝ)
    (hdistinct : Real.cos φ₁ * Real.cos φ₂ + Real.sin φ₁ * Real.sin φ₂ ≠ 1) :
    growthDirectionsCross φ₁ φ₂ = 0 ↔
      Real.cos φ₁ * Real.cos φ₂ + Real.sin φ₁ * Real.sin φ₂ = -1 := by
  unfold growthDirectionsCross
  set c := Real.cos φ₁ * Real.cos φ₂ + Real.sin φ₁ * Real.sin φ₂
  have hid : (Real.cos φ₁ * Real.sin φ₂ - Real.sin φ₁ * Real.cos φ₂) ^ 2 + c ^ 2 = 1 := by
    have h1 := Real.sin_sq_add_cos_sq φ₁
    have h2 := Real.sin_sq_add_cos_sq φ₂
    simp only [c]
    linear_combination (Real.sin φ₂ ^ 2 + Real.cos φ₂ ^ 2) * h1 + h2
  clear_value c
  constructor
  · intro h
    rw [h] at hid
    have : (c - 1) * (c + 1) = 0 := by linear_combination hid
    rcases mul_eq_zero.mp this with h' | h'
    · exact absurd (by linarith) hdistinct
    · linarith
  · intro h
    rw [h] at hid
    have : (Real.cos φ₁ * Real.sin φ₂ - Real.sin φ₁ * Real.cos φ₂) ^ 2 = 0 := by linarith
    exact pow_eq_zero_iff (n := 2) (by norm_num) |>.mp this

/-- Tait's reduction of a parastichy pair `(m, n)` (leaf `O` reached by `m` and `n` steps)
to the pair `(n, m - n)` found in the same system. -/
def taitStep (p : ℕ × ℕ) : ℕ × ℕ := (p.2, p.1 - p.2)

/-- thompson1917-ch14-07: Tait's step takes a consecutive Fibonacci pair to the next lower
pair. -/
theorem taitStep_fib (k : ℕ) :
    taitStep (Nat.fib (k + 2), Nat.fib (k + 1)) = (Nat.fib (k + 1), Nat.fib k) := by
  simp only [taitStep, Nat.fib_add_two, Prod.mk.injEq, true_and]
  omega

/-- thompson1917-ch14-07: starting from the pair `(F_{i+j+2}, F_{i+j+1})`, `j` applications
of Tait's step give the lower pair `(F_{i+2}, F_{i+1})`, so every lower pair is present. -/
theorem taitStep_iterate_fib (j i : ℕ) :
    taitStep^[j] (Nat.fib (i + j + 2), Nat.fib (i + j + 1)) =
      (Nat.fib (i + 2), Nat.fib (i + 1)) := by
  induction j generalizing i with
  | zero => simp
  | succ j ih =>
    rw [Function.iterate_succ_apply,
      show i + (j + 1) + 2 = (i + j + 1) + 2 by ring,
      show i + (j + 1) + 1 = (i + j + 1) + 1 by ring, taitStep_fib]
    exact ih i

/-- thompson1917-ch14-07: any Fibonacci pair `(F_{k+2}, F_{k+1})` reduces to `(1, 1)`. -/
theorem taitStep_reaches_one_one (k : ℕ) :
    taitStep^[k] (Nat.fib (k + 2), Nat.fib (k + 1)) = (1, 1) := by
  have h := taitStep_iterate_fib k 0
  simp only [zero_add] at h
  rw [h]; rfl

/-- Parastichy series generated from the lowest pair `(1, t)` by Tait's step run upward,
`(m, n) ↦ (m + n, m)`: `1, t, t + 1, 2t + 1, …`. -/
def phyllotaxisSeries (t : ℕ) : ℕ → ℕ
  | 0 => 1
  | 1 => t
  | n + 2 => phyllotaxisSeries t n + phyllotaxisSeries t (n + 1)

/-- thompson1917-ch14-08: with between two and three leaves per turn of the genetic spiral
(`t = 2`) the parastichy numbers are the Fibonacci series `1, 2, 3, 5, 8, …`. -/
theorem phyllotaxisSeries_two (n : ℕ) : phyllotaxisSeries 2 n = Nat.fib (n + 2) := by
  induction n using Nat.strong_induction_on with
  | _ n ih =>
    match n, ih with
    | 0, _ => rfl
    | 1, _ => rfl
    | n + 2, ih =>
      rw [phyllotaxisSeries, ih n (by omega), ih (n + 1) (by omega), Nat.fib_add_two (n := n + 2)]

/-- thompson1917-ch14-08: `t = 3` gives a different series `1, 3, 4, 7, 11, …`, which
leaves the Fibonacci numbers (4 is not one). -/
theorem phyllotaxisSeries_three_not_fib : phyllotaxisSeries 3 2 = 4 ∧ ∀ n, Nat.fib n ≠ 4 := by
  refine ⟨rfl, fun n => ?_⟩
  rcases Nat.lt_or_ge n 6 with h | h
  · interval_cases n <;> decide
  · have : Nat.fib 6 ≤ Nat.fib n := Nat.fib_mono h
    have h6 : Nat.fib 6 = 8 := rfl
    omega

/-- Phyllotactic fraction `F_n / F_{n+1}` (1/2, 2/3, 3/5, 5/8, …). -/
noncomputable def phyllotacticFraction (n : ℕ) : ℝ := (Nat.fib n : ℝ) / Nat.fib (n + 1)

/-- thompson1917-ch14-10: the phyllotactic fractions converge to the golden mean
`(√5 - 1) / 2 ≈ 0.618`. -/
theorem phyllotacticFraction_tendsto_goldenMean :
    Tendsto phyllotacticFraction atTop (𝓝 ((√5 - 1) / 2)) := by
  have h : (√5 - 1) / 2 = -Real.goldenConj := by unfold Real.goldenConj; ring
  rw [h]
  exact tendsto_fib_div_fib_succ_atTop

/-- Total curvature term `T (1/r + 1/r')` of a membrane with tension `T` and principal radii
of curvature `r`, `r'`. -/
noncomputable def membraneCurvaturePressure (T r r' : ℝ) : ℝ := T * (1 / r + 1 / r')

/-- thompson1917-ch15-06: with unequal tensions the general equation
`p_n + T/r + T'/r' = P` reduces to the egg equation `p_n + T(1/r + 1/r') = P` when `T = T'`. -/
theorem eggEquation_equalTensions (pn T T' r r' P : ℝ) (hT : T' = T)
    (h : pn + T / r + T' / r' = P) : pn + membraneCurvaturePressure T r r' = P := by
  unfold membraneCurvaturePressure
  rw [hT] at h
  linarith [show T * (1 / r + 1 / r') = T / r + T / r' by ring]

/-- thompson1917-ch15-06: in the egg equation, at two points of the same membrane (same `T`,
internal pressure `P`), the point under greater external pressure `p_n` has the smaller
total curvature: the oviduct's pressure shapes the egg. -/
theorem egg_flatter_where_pressed (T P p₁ p₂ r₁ r₁' r₂ r₂' : ℝ) (hT : 0 < T)
    (h₁ : p₁ + membraneCurvaturePressure T r₁ r₁' = P)
    (h₂ : p₂ + membraneCurvaturePressure T r₂ r₂' = P) (hp : p₂ < p₁) :
    1 / r₁ + 1 / r₁' < 1 / r₂ + 1 / r₂' := by
  unfold membraneCurvaturePressure at h₁ h₂
  have : T * (1 / r₁ + 1 / r₁') < T * (1 / r₂ + 1 / r₂') := by linarith
  exact lt_of_mul_lt_mul_left this hT.le

/-- thompson1917-ch15-06: under uniform external pressure and tension the egg equation forces
the same total curvature everywhere (a sphere-like form). -/
theorem egg_uniformPressure_constCurvature (T P pn r₁ r₁' r₂ r₂' : ℝ) (hT : 0 < T)
    (h₁ : pn + membraneCurvaturePressure T r₁ r₁' = P)
    (h₂ : pn + membraneCurvaturePressure T r₂ r₂' = P) :
    1 / r₁ + 1 / r₁' = 1 / r₂ + 1 / r₂' := by
  unfold membraneCurvaturePressure at h₁ h₂
  exact mul_left_cancel₀ hT.ne' (by linarith)

/-- Wall thickness `t = P R / σ` a cylindrical vessel of radius `R` needs to carry pressure
`P` when its tension is `σ` per unit wall thickness. -/
noncomputable def vesselWallThickness (P R σ : ℝ) : ℝ := P * R / σ

/-- thompson1917-ch15-10: from `P = T / R` and tension proportional to wall thickness
(`T = σ t`), the wall thickness is `t = (P / σ) R`, proportional to the radius at constant
pressure. -/
theorem vesselWall_eq (P T R σ t : ℝ) (hR : 0 < R) (hσ : 0 < σ)
    (hP : P = T / R) (hT : T = σ * t) :
    t = vesselWallThickness P R σ ∧ vesselWallThickness P R σ = (P / σ) * R := by
  unfold vesselWallThickness
  subst hP hT
  constructor <;> field_simp

/-- thompson1917-ch15-10: where pressure has fallen (`P₂ < P₁`, smaller vessels), the wall is
thinner relative to the radius than in the larger vessel. -/
theorem vesselWall_relThinner (P₁ P₂ R₁ R₂ σ : ℝ) (hR₁ : 0 < R₁) (hR₂ : 0 < R₂) (hσ : 0 < σ)
    (hP : P₂ < P₁) :
    vesselWallThickness P₂ R₂ σ / R₂ < vesselWallThickness P₁ R₁ σ / R₁ := by
  unfold vesselWallThickness
  have e : ∀ P R : ℝ, 0 < R → P * R / σ / R = P / σ := by
    intro P R hR; field_simp
  rw [e P₂ R₂ hR₂, e P₁ R₁ hR₁]
  exact (div_lt_div_iff_of_pos_right hσ).mpr hP

/-- Wall thickness `t = P / (σ (1/r + 1/r'))` of a heart chamber at a point of principal
radii `r`, `r'`, under chamber pressure `P` and tension `σ` per unit thickness. -/
noncomputable def heartWallThickness (P σ r r' : ℝ) : ℝ := P / (σ * (1 / r + 1 / r'))

/-- thompson1917-ch15-11: with uniform pressure `P` in a cavity, Laplace's law
`P = T (1/r + 1/r')` and `T = σ t` give `t (1/r + 1/r') = P / σ`, the same constant `C`
at every point of the wall. -/
theorem heartWall_mul_curvature (P σ t₁ t₂ r₁ r₁' r₂ r₂' : ℝ) (hσ : 0 < σ)
    (h₁ : P = σ * t₁ * (1 / r₁ + 1 / r₁')) (h₂ : P = σ * t₂ * (1 / r₂ + 1 / r₂')) :
    t₁ * (1 / r₁ + 1 / r₁') = P / σ ∧ t₁ * (1 / r₁ + 1 / r₁') = t₂ * (1 / r₂ + 1 / r₂') := by
  have e₁ : t₁ * (1 / r₁ + 1 / r₁') = P / σ := by
    rw [h₁]; field_simp
  have e₂ : t₂ * (1 / r₂ + 1 / r₂') = P / σ := by
    rw [h₂]; field_simp
  exact ⟨e₁, e₁.trans e₂.symm⟩

/-- thompson1917-ch15-11: the more curved part of a chamber wall (e.g. the apex of the left
ventricle) is the thinner. -/
theorem heartWall_thinner_where_curved (P σ r₁ r₁' r₂ r₂' : ℝ) (hP : 0 < P) (hσ : 0 < σ)
    (hH₂ : 0 < 1 / r₂ + 1 / r₂') (hH : 1 / r₂ + 1 / r₂' < 1 / r₁ + 1 / r₁') :
    heartWallThickness P σ r₁ r₁' < heartWallThickness P σ r₂ r₂' := by
  unfold heartWallThickness
  apply div_lt_div_of_pos_left hP (by positivity)
  exact mul_lt_mul_of_pos_left hH hσ

/-- thompson1917-ch15-12: when both ventricles are dilated to the same curvature, the ratio of
wall thicknesses equals the ratio of dilating pressures, `t_L / t_R = P_L / P_R`. -/
theorem ventricleThickness_ratio (P_L P_R σ r r' : ℝ) (hσ : 0 < σ)
    (hH : 0 < 1 / r + 1 / r') (hPR : 0 < P_R) :
    heartWallThickness P_L σ r r' / heartWallThickness P_R σ r r' = P_L / P_R := by
  unfold heartWallThickness
  have : σ * (1 / r + 1 / r') ≠ 0 := by positivity
  field_simp

/-- Energy lost by blood that runs `D - u` along a trunk (loss `L` per unit length) and then
through a branch to a point at remaining axial distance `u` and lateral distance `h`
(loss `L'` per unit length, branch length `√(u² + h²)`). -/
noncomputable def branchEnergyLoss (L L' D h u : ℝ) : ℝ := L * (D - u) + L' * √(u ^ 2 + h ^ 2)

/-- Cosine `u / √(u² + h²)` of the angle at which the branch leaves the trunk. -/
noncomputable def branchAngleCos (h u : ℝ) : ℝ := u / √(u ^ 2 + h ^ 2)

/-- thompson1917-ch15-15: moving the branching point changes the energy loss at rate
`-L + L' cos x`, trunk loss saved against extra branch loss. -/
theorem branchEnergyLoss_hasDerivAt (L L' D h u : ℝ) (hh : h ≠ 0) :
    HasDerivAt (branchEnergyLoss L L' D h) (-L + L' * branchAngleCos h u) u := by
  have hpos : 0 < u ^ 2 + h ^ 2 := by positivity
  have hq : HasDerivAt (fun x => x ^ 2 + h ^ 2) (2 * u) u := by
    simpa using (hasDerivAt_pow 2 u).add_const (h ^ 2)
  have hs := hq.sqrt hpos.ne'
  have ht : HasDerivAt (fun x => L * (D - x)) (-L) u := by
    simpa using ((hasDerivAt_id u).const_sub D).const_mul L
  have := ht.add (hs.const_mul L')
  unfold branchEnergyLoss branchAngleCos
  convert this using 1
  have : √(u ^ 2 + h ^ 2) ≠ 0 := (Real.sqrt_pos.mpr hpos).ne'
  field_simp

/-- thompson1917-ch15-15: the energy loss is stationary in the branching point exactly when
the cosine of the branching angle equals `L / L'`. -/
theorem branchEnergyLoss_stationary_iff (L L' D h u : ℝ) (hh : h ≠ 0) (hL' : 0 < L') :
    deriv (branchEnergyLoss L L' D h) u = 0 ↔ branchAngleCos h u = L / L' := by
  rw [(branchEnergyLoss_hasDerivAt L L' D h u hh).deriv]
  constructor
  · intro h0; field_simp; linarith
  · intro h0; rw [h0]; field_simp; ring

end ThompsonLaws.HornsLeavesEggs
