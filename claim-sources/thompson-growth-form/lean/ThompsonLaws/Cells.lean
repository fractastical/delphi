import Mathlib

/-!
# Thompson, *On Growth and Form* (1917), chapters V, VII and VIII: cells, tissues and
cell division

Laplace pressure of cell surfaces, the stability of liquid cylinders, triple junctions of
cell walls, the bee's cell, and Errera's law of minimal partitions.
-/

open Real
namespace ThompsonLaws.Cells

/-! ## Laplace pressure of cylinders and spheres -/

/-- Excess pressure across a fluid surface of uniform tension `T` with principal curvatures
`κ₁, κ₂` (Laplace): `p = T (1/r₁ + 1/r₂)`. -/
def laplacePressure (T κ₁ κ₂ : ℝ) : ℝ := T * (κ₁ + κ₂)

/-- Height of a spherical cap of radius `ρ` standing on a circle of radius `R`. -/
noncomputable def capHeight (ρ R : ℝ) : ℝ := ρ - √(ρ ^ 2 - R ^ 2)

/-- thompson1917-ch05-11: a cylinder of radius `R` capped by a sphere of radius `ρ` under the
same wall tension and internal pressure has `ρ = 2R`; the cap meets the cylinder at a
half-angle of 30° (a cone of 60°) and its height is `R (2 - √3)`. -/
theorem cylinderCap_geometry (T R ρ : ℝ) (hT : 0 < T) (hR : 0 < R) (hρ : 0 < ρ)
    (hp : laplacePressure T (1 / ρ) (1 / ρ) = laplacePressure T (1 / R) 0) :
    ρ = 2 * R ∧ Real.arcsin (R / ρ) = π / 6 ∧ capHeight ρ R = R * (2 - √3) := by
  unfold laplacePressure at hp
  have hρ2 : ρ = 2 * R := by
    have h1 : 1 / ρ + 1 / ρ = 1 / R + 0 := by
      have := mul_left_cancel₀ hT.ne' hp
      linarith
    field_simp at h1
    linarith
  refine ⟨hρ2, ?_, ?_⟩
  · rw [hρ2, show R / (2 * R) = 1 / 2 by field_simp]
    rw [← Real.sin_pi_div_six]
    exact Real.arcsin_sin (by linarith [Real.pi_pos]) (by linarith [Real.pi_pos])
  · unfold capHeight
    rw [hρ2, show (2 * R) ^ 2 - R ^ 2 = 3 * R ^ 2 by ring, Real.sqrt_mul (by norm_num),
      Real.sqrt_sq hR.le]
    ring

/-- thompson1917-ch05-11: the cap height `R (2 - √3)` lies between `R/4` (one-eighth of the
cylinder's diameter) and `0.27 R`. -/
theorem capHeight_bounds (R : ℝ) (hR : 0 < R) :
    R / 4 < R * (2 - √3) ∧ R * (2 - √3) < 0.27 * R := by
  have h3 : √3 < 1.75 := by
    rw [Real.sqrt_lt' (by norm_num)]; norm_num
  have h3' : 1.73 < √3 := by
    rw [Real.lt_sqrt (by norm_num)]; norm_num
  constructor <;> nlinarith

/-! ## Stability of a liquid cylinder (Plateau–Rayleigh) -/

/-- Upper bound on the lateral area of one wavelength `L` of a liquid cylinder of radius
`r₀` deformed to `r(z) = a + ε cos (2π z / L)` at constant volume, so that
`a = √(r₀² - ε²/2)`. Using `√(1 + r'²) ≤ 1 + r'²/2`, the area
`∫ 2π r √(1 + r'²) dz` is at most `2π L a (1 + ε² k² / 4)` with `k = 2π / L`. -/
noncomputable def undulatedAreaBound (r₀ ε L : ℝ) : ℝ :=
  2 * π * L * √(r₀ ^ 2 - ε ^ 2 / 2) * (1 + ε ^ 2 * (2 * π / L) ^ 2 / 4)

/-- thompson1917-ch05-12: a liquid cylinder of radius `r₀` is unstable to a varicose
undulation of wavelength `L` longer than its circumference `2π r₀`: the undulated surface,
enclosing the same volume, has less area than the cylinder's `2π r₀ L`. -/
theorem liquidCylinder_unstable (r₀ ε L : ℝ) (hr : 0 < r₀) (hε : 0 < ε)
    (hε2 : ε ^ 2 < 2 * r₀ ^ 2) (hL : 2 * π * r₀ < L) :
    undulatedAreaBound r₀ ε L < 2 * π * r₀ * L := by
  unfold undulatedAreaBound
  have hLpos : 0 < L := by nlinarith [Real.pi_pos]
  set k := 2 * π / L with hk
  have hkpos : 0 < k := by positivity
  have hkr : k * r₀ < 1 := by
    rw [hk, div_mul_eq_mul_div, div_lt_one hLpos]; linarith
  set a := √(r₀ ^ 2 - ε ^ 2 / 2) with ha
  set b := r₀ - ε ^ 2 / (4 * r₀) with hb
  have hbpos : 0 < b := by
    rw [hb, sub_pos, div_lt_iff₀ (by positivity)]; nlinarith
  have hab : a < b := by
    rw [ha, Real.sqrt_lt' hbpos, hb]
    have : (r₀ - ε ^ 2 / (4 * r₀)) ^ 2 = r₀ ^ 2 - ε ^ 2 / 2 + (ε ^ 2 / (4 * r₀)) ^ 2 := by
      field_simp; ring
    rw [this]; nlinarith [sq_pos_of_pos (show 0 < ε ^ 2 / (4 * r₀) by positivity)]
  have ha0 : 0 ≤ a := Real.sqrt_nonneg _
  have hfac : 0 < 1 + ε ^ 2 * k ^ 2 / 4 := by positivity
  have key : b * (1 + ε ^ 2 * k ^ 2 / 4) < r₀ := by
    have hexp : b * (1 + ε ^ 2 * k ^ 2 / 4)
        = r₀ - ε ^ 2 / (4 * r₀) * (1 - (k * r₀) ^ 2) - ε ^ 4 * k ^ 2 / (16 * r₀) := by
      rw [hb]; field_simp; ring
    rw [hexp]
    have h1 : 0 < ε ^ 2 / (4 * r₀) * (1 - (k * r₀) ^ 2) := by
      apply mul_pos (by positivity)
      nlinarith [mul_pos hkpos hr]
    have h2 : 0 < ε ^ 4 * k ^ 2 / (16 * r₀) := by positivity
    linarith
  have : a * (1 + ε ^ 2 * k ^ 2 / 4) < r₀ :=
    lt_of_le_of_lt (mul_le_mul_of_nonneg_right hab.le hfac.le) key
  have hpos : 0 < 2 * π * L := by positivity
  calc 2 * π * L * a * (1 + ε ^ 2 * k ^ 2 / 4)
      = 2 * π * L * (a * (1 + ε ^ 2 * k ^ 2 / 4)) := by ring
    _ < 2 * π * L * r₀ := mul_lt_mul_of_pos_left this hpos
    _ = 2 * π * r₀ * L := by ring

/-- thompson1917-ch05-24: at the rim of a biconcave corpuscle both principal curvatures are
positive and in the dimple both are negative, so no single internal pressure balances a
uniform surface tension: the corpuscle is not a fluid drop in Laplace equilibrium. -/
theorem biconcave_not_equilibrium (T κA₁ κA₂ κC₁ κC₂ : ℝ) (hT : 0 < T)
    (hA₁ : 0 < κA₁) (hA₂ : 0 < κA₂) (hC₁ : κC₁ < 0) (hC₂ : κC₂ < 0) :
    laplacePressure T κA₁ κA₂ ≠ laplacePressure T κC₁ κC₂ := by
  unfold laplacePressure
  have h1 : 0 < T * (κA₁ + κA₂) := by positivity
  have h2 : T * (κC₁ + κC₂) < 0 := mul_neg_of_pos_of_neg hT (by linarith)
  linarith

/-! ## Junctions of cell walls -/

/-- Tangential force exerted along a rigid wall by a fluid partition of tension `T` meeting
it at angle `θ`. -/
noncomputable def tangentialPull (T θ : ℝ) : ℝ := T * Real.cos θ

/-- thompson1917-ch07-02 (Sachs's rule): a fluid partition whose foot can slide along a
rigid wall is in equilibrium only when its tangential pull vanishes, i.e. when it meets the
wall at a right angle, making equal angles on both sides. -/
theorem sachsRule (T θ : ℝ) (hT : 0 < T) (hθ0 : 0 < θ) (hθπ : θ < π)
    (heq : tangentialPull T θ = 0) : θ = π / 2 ∧ θ = π - θ := by
  unfold tangentialPull at heq
  have hc : Real.cos θ = 0 := (mul_eq_zero.mp heq).resolve_left hT.ne'
  have h : θ = π / 2 :=
    Real.injOn_cos ⟨hθ0.le, hθπ.le⟩ ⟨by positivity, by linarith [Real.pi_pos]⟩
      (by rw [hc, Real.cos_pi_div_two])
  exact ⟨h, by linarith⟩

/-- Equilibrium of a junction where three walls of tensions `T₁, T₂, T₃` pull along the unit
directions `u, v, w` (Neumann's triangle of forces). -/
def junctionBalanced (T₁ T₂ T₃ : ℝ) (u v w : EuclideanSpace ℝ (Fin 2)) : Prop :=
  T₁ • u + T₂ • v + T₃ • w = 0

/-- thompson1917-ch07-04, thompson1917-ch07-06: at a balanced junction the tensions fix the
angle between the walls `u, v`: `T₃² = T₁² + T₂² + 2 T₁ T₂ cos ∠(u, v)`. -/
theorem junction_inner (T₁ T₂ T₃ : ℝ) (u v w : EuclideanSpace ℝ (Fin 2))
    (hu : ‖u‖ = 1) (hv : ‖v‖ = 1) (hw : ‖w‖ = 1) (h : junctionBalanced T₁ T₂ T₃ u v w) :
    T₃ ^ 2 = T₁ ^ 2 + T₂ ^ 2 + 2 * T₁ * T₂ * inner ℝ u v := by
  unfold junctionBalanced at h
  have h' : T₃ • w = -(T₁ • u + T₂ • v) := by
    rw [eq_neg_iff_add_eq_zero, add_comm]; exact h
  have hn := congrArg (fun x => ‖x‖ ^ 2) h'
  simp only [norm_neg, norm_add_sq_real, norm_smul, Real.norm_eq_abs, mul_pow, sq_abs, hu, hv,
    hw, real_inner_smul_left, real_inner_smul_right] at hn
  linarith

/-- thompson1917-ch07-04: `cos 120° = -1/2`. -/
theorem cos_two_pi_div_three : Real.cos (2 * π / 3) = -(1 / 2) := by
  rw [show 2 * π / 3 = π - π / 3 by ring, Real.cos_pi_sub, Real.cos_pi_div_three]

/-- thompson1917-ch07-04: three walls of equal tension meeting at a point are in equilibrium
only if each pair meets at 120°. Cell size does not enter. -/
theorem tripleJunction_120 (T : ℝ) (hT : T ≠ 0) (u v w : EuclideanSpace ℝ (Fin 2))
    (hu : ‖u‖ = 1) (hv : ‖v‖ = 1) (hw : ‖w‖ = 1) (h : junctionBalanced T T T u v w) :
    InnerProductGeometry.angle u v = 2 * π / 3 ∧ InnerProductGeometry.angle v w = 2 * π / 3 ∧
      InnerProductGeometry.angle u w = 2 * π / 3 := by
  have key : ∀ x y z : EuclideanSpace ℝ (Fin 2), ‖x‖ = 1 → ‖y‖ = 1 → ‖z‖ = 1 →
      junctionBalanced T T T x y z → InnerProductGeometry.angle x y = 2 * π / 3 := by
    intro x y z hx hy hz hj
    have hi := junction_inner T T T x y z hx hy hz hj
    have hxy : inner ℝ x y = -(1 / 2) := by
      have hT2 : 0 < T ^ 2 := by positivity
      nlinarith
    unfold InnerProductGeometry.angle
    rw [hx, hy, hxy, mul_one, div_one, ← cos_two_pi_div_three]
    exact Real.arccos_cos (by positivity) (by linarith [Real.pi_pos])
  refine ⟨key u v w hu hv hw h, key v w u hv hw hu ?_, key u w v hu hw hv ?_⟩
  · unfold junctionBalanced at h ⊢; rw [← h]; abel
  · unfold junctionBalanced at h ⊢; rw [← h]; abel

/-- Curvature of the wall between two cells of radii `r₁, r₂` in plane section, under equal
wall tension `T` (Laplace pressure `T / r` in each cell): `κ = (p₁ - p₂) / T`. -/
noncomputable def partitionCurvature (T r₁ r₂ : ℝ) : ℝ := (T / r₁ - T / r₂) / T

/-- thompson1917-ch07-04: the relative sizes of neighbouring cells set only the curvature of
their common wall, `1/r₁ - 1/r₂`, which vanishes exactly when the cells are equal. -/
theorem partitionCurvature_eq (T r₁ r₂ : ℝ) (hT : T ≠ 0) (h₁ : 0 < r₁) (h₂ : 0 < r₂) :
    partitionCurvature T r₁ r₂ = 1 / r₁ - 1 / r₂ ∧
      (partitionCurvature T r₁ r₂ = 0 ↔ r₁ = r₂) := by
  have hc : partitionCurvature T r₁ r₂ = 1 / r₁ - 1 / r₂ := by
    unfold partitionCurvature; field_simp
  refine ⟨hc, ?_⟩
  rw [hc, sub_eq_zero, one_div, one_div, inv_inj]

/-- thompson1917-ch07-06: two cells in a medium with cell–medium tensions `T₁, T₂` along `u, v`
and cell–cell tension `T₃` along `w`. If `T₃` exceeds both `T₁` and `T₂`, the external angle
between `u` and `v` is less than 120°. -/
theorem external_angle_lt_120 (T₁ T₂ T₃ : ℝ) (h₁ : 0 < T₁) (h₂ : 0 < T₂)
    (h31 : T₁ < T₃) (h32 : T₂ < T₃) (u v w : EuclideanSpace ℝ (Fin 2))
    (hu : ‖u‖ = 1) (hv : ‖v‖ = 1) (hw : ‖w‖ = 1) (h : junctionBalanced T₁ T₂ T₃ u v w) :
    InnerProductGeometry.angle u v < 2 * π / 3 := by
  have hi := junction_inner T₁ T₂ T₃ u v w hu hv hw h
  have hcos : -(1 / 2) < inner ℝ u v := by
    have hT : T₁ ^ 2 + T₂ ^ 2 - T₁ * T₂ < T₃ ^ 2 := by
      rcases le_total T₁ T₂ with hle | hle <;> nlinarith
    nlinarith [mul_pos h₁ h₂]
  have hang : Real.cos (InnerProductGeometry.angle u v) = inner ℝ u v := by
    rw [InnerProductGeometry.cos_angle, hu, hv, mul_one, div_one]
  by_contra hge
  push Not at hge
  have := Real.cos_le_cos_of_nonneg_of_le_pi (by positivity)
    (InnerProductGeometry.angle_le_pi u v) hge
  rw [cos_two_pi_div_three, hang] at this
  linarith

/-- thompson1917-ch07-06: if the cell–cell tension is at least the sum of the two cell–medium
tensions, equilibrium forces it to equal that sum with the two outer surfaces coincident
(external angle 0): the cells touch only at a point. -/
theorem contact_at_point (T₁ T₂ T₃ : ℝ) (h₁ : 0 < T₁) (h₂ : 0 < T₂) (h3 : T₁ + T₂ ≤ T₃)
    (u v w : EuclideanSpace ℝ (Fin 2))
    (hu : ‖u‖ = 1) (hv : ‖v‖ = 1) (hw : ‖w‖ = 1) (h : junctionBalanced T₁ T₂ T₃ u v w) :
    T₃ = T₁ + T₂ ∧ InnerProductGeometry.angle u v = 0 := by
  have hi := junction_inner T₁ T₂ T₃ u v w hu hv hw h
  have hle : inner ℝ u v ≤ 1 := by
    have := real_inner_le_norm u v; rw [hu, hv] at this; linarith
  have hsq : (T₁ + T₂) ^ 2 ≤ T₃ ^ 2 := by nlinarith
  have h12 : 0 < T₁ * T₂ := mul_pos h₁ h₂
  have hone : inner ℝ u v = 1 := by nlinarith
  refine ⟨by nlinarith, ?_⟩
  unfold InnerProductGeometry.angle
  rw [hu, hv, hone]; simp

/-- Interior-angle sum of a convex polygon with `n` sides. -/
noncomputable def polygonAngleSum (n : ℕ) : ℝ := ((n : ℝ) - 2) * π

/-- thompson1917-ch07-09: a cell bounded by straight walls whose every corner is a triple
junction of 120° has exactly six sides, hence six neighbours. -/
theorem hexagon_of_120 (n : ℕ) (h : polygonAngleSum n = n * (2 * π / 3)) : n = 6 := by
  unfold polygonAngleSum at h
  have h' : ((n : ℝ) - 6) * π = 0 := by linarith
  have : (n : ℝ) = 6 := by
    rcases mul_eq_zero.mp h' with h0 | h0
    · linarith
    · exact absurd h0 Real.pi_ne_zero
  exact_mod_cast this

/-! ## The bee's cell -/

/-- Surface of a hexagonal cell of side `s` and height `h` closed by three rhombi inclined at
angle `θ` to the axis (the classical Maraldi–Koenig problem); the enclosed volume does not
depend on `θ`. -/
noncomputable def beeCellArea (s h θ : ℝ) : ℝ :=
  6 * s * h - 3 / 2 * s ^ 2 * (Real.cos θ / Real.sin θ) + 3 * √3 / 2 * s ^ 2 / Real.sin θ

/-- thompson1917-ch07-11: among such cells the area is least, `6sh + (3√2/2) s²`, exactly when
`cos θ = 1/√3`. -/
theorem beeCellArea_min (s h θ : ℝ) (hs : 0 < s) (hθ0 : 0 < θ) (hθ : θ < π / 2) :
    6 * s * h + 3 * √2 / 2 * s ^ 2 ≤ beeCellArea s h θ ∧
      (beeCellArea s h θ = 6 * s * h + 3 * √2 / 2 * s ^ 2 ↔ √3 * Real.cos θ = 1) := by
  have hsin : 0 < Real.sin θ := Real.sin_pos_of_pos_of_lt_pi hθ0 (by linarith [Real.pi_pos])
  have hcos : 0 < Real.cos θ := Real.cos_pos_of_mem_Ioo ⟨by linarith, hθ⟩
  have hpy := Real.sin_sq_add_cos_sq θ
  have h3 : √3 ^ 2 = 3 := Real.sq_sqrt (by norm_num)
  have h2 : √2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  have hs3 : 0 < √3 := by positivity
  have hs2 : 0 < √2 := by positivity
  have harea : beeCellArea s h θ
      = 6 * s * h + 3 / 2 * s ^ 2 * ((√3 - Real.cos θ) / Real.sin θ) := by
    unfold beeCellArea; field_simp; ring
  rw [harea]
  set c := Real.cos θ
  set n := Real.sin θ
  have hc1 : c < √3 := by nlinarith
  have hsq : (√2 * n) ^ 2 ≤ (√3 - c) ^ 2 := by nlinarith [sq_nonneg (√3 * c - 1)]
  have hge : √2 * n ≤ √3 - c := by
    by_contra hlt; push Not at hlt
    nlinarith [mul_pos hs2 hsin]
  have hs2' : 0 < 3 / 2 * s ^ 2 := by positivity
  constructor
  · have : √2 ≤ (√3 - c) / n := by rw [le_div_iff₀ hsin]; linarith
    nlinarith
  · constructor
    · intro he
      have he' : (√3 - c) / n = √2 :=
        mul_left_cancel₀ hs2'.ne' (by linarith)
      rw [div_eq_iff hsin.ne'] at he'
      have : (√3 - c) ^ 2 = (√2 * n) ^ 2 := by rw [he']
      nlinarith [sq_nonneg (√3 * c - 1)]
    · intro he
      have hc : c = 1 / √3 := by field_simp; linarith
      have hn2 : n ^ 2 = 2 / 3 := by
        rw [hc] at hpy; field_simp at hpy; nlinarith
      have hn : n = √2 / √3 := by
        have : (√2 / √3) ^ 2 = 2 / 3 := by rw [div_pow, h2, h3]
        have hpos : 0 < √2 / √3 := by positivity
        nlinarith [sq_nonneg (n - √2 / √3), sq_nonneg (n + √2 / √3)]
      rw [hn, hc]; field_simp; nlinarith

/-- Cosine of the angle of a rhombus at the ends of its diagonal `d₂`, the other diagonal
being `d₁`. -/
noncomputable def rhombusCos (d₁ d₂ : ℝ) : ℝ := (d₂ ^ 2 - d₁ ^ 2) / (d₁ ^ 2 + d₂ ^ 2)

/-- thompson1917-ch07-11: at the optimum `cos θ = 1/√3`, each closing rhombus has diagonals
`s√3` and `s / sin θ`, and its angle at the apex of the cell has cosine `-1/3`
(109° 28′, the angle of the rhombic dodecahedron). -/
theorem beeCell_rhombus_angle (s θ : ℝ) (hs : 0 < s) (hθ0 : 0 < θ) (hθ : θ < π / 2)
    (hopt : √3 * Real.cos θ = 1) :
    rhombusCos (s * √3) (s / Real.sin θ) = -(1 / 3) := by
  have hsin : 0 < Real.sin θ := Real.sin_pos_of_pos_of_lt_pi hθ0 (by linarith [Real.pi_pos])
  have h3 : √3 ^ 2 = 3 := Real.sq_sqrt (by norm_num)
  have hpy := Real.sin_sq_add_cos_sq θ
  have hc2 : Real.cos θ ^ 2 = 1 / 3 := by
    have : (√3 * Real.cos θ) ^ 2 = 1 := by rw [hopt]; norm_num
    rw [mul_pow, h3] at this; linarith
  have hn2 : Real.sin θ ^ 2 = 2 / 3 := by linarith
  unfold rhombusCos
  rw [div_pow, hn2, mul_pow, h3]
  field_simp
  ring

/-! ## Errera's law of minimal partitions -/

/-- Area of the plane wall that bisects a box of edges `d 0, d 1, d 2` across axis `i`. -/
noncomputable def boxCutArea (d : Fin 3 → ℝ) (i : Fin 3) : ℝ := (d 0 * d 1 * d 2) / d i

/-- thompson1917-ch08-01: the bisecting plane wall across the longest axis has the least
area. -/
theorem boxCut_longest_minimal (d : Fin 3 → ℝ) (hd : ∀ j, 0 < d j) (i : Fin 3)
    (hi : ∀ j, d j ≤ d i) : ∀ j, boxCutArea d i ≤ boxCutArea d j := by
  intro j
  unfold boxCutArea
  have hV : 0 < d 0 * d 1 * d 2 := by have := hd 0; have := hd 1; have := hd 2; positivity
  exact div_le_div_of_nonneg_left hV.le (hd j) (hi j)

/-- thompson1917-ch08-01: a box `a × b × c` with `c ≤ b ≤ a ≤ 2b` is first bisected across
axis 0 (its longest); each daughter `a/2 × b × c` then has its least bisecting wall across
axis 1, at right angles to the first wall. -/
theorem successive_bisection_perpendicular (a b c : ℝ) (hc : 0 < c) (hcb : c ≤ b)
    (hba : b ≤ a) (ha2 : a ≤ 2 * b) :
    (∀ j, boxCutArea ![a, b, c] 0 ≤ boxCutArea ![a, b, c] j) ∧
      (∀ j, boxCutArea ![a / 2, b, c] 1 ≤ boxCutArea ![a / 2, b, c] j) := by
  constructor
  · apply boxCut_longest_minimal
    · intro j; fin_cases j <;> norm_num <;> linarith
    · intro j; fin_cases j <;> norm_num <;> linarith
  · apply boxCut_longest_minimal
    · intro j; fin_cases j <;> norm_num <;> linarith
    · intro j; fin_cases j <;> norm_num <;> linarith

/-- thompson1917-ch08-02: Sachs's rule is a case of Errera's: a bisecting wall of least area
among the plane cuts of a box must run across its longest axis. -/
theorem errera_implies_sachs (d : Fin 3 → ℝ) (hd : ∀ j, 0 < d j) (i : Fin 3)
    (hmin : ∀ j, boxCutArea d i ≤ boxCutArea d j) : ∀ j, d j ≤ d i := by
  intro j
  have hV : 0 < d 0 * d 1 * d 2 := by have := hd 0; have := hd 1; have := hd 2; positivity
  have := hmin j
  unfold boxCutArea at this
  exact (div_le_div_iff_of_pos_left hV (hd i) (hd j)).mp this

/-- Wall area and enclosed volume of a quarter-cylinder of radius `r` along an edge of a unit
cube. -/
noncomputable def quarterCylArea (r : ℝ) : ℝ := π * r / 2
noncomputable def quarterCylVolume (r : ℝ) : ℝ := π * r ^ 2 / 4

/-- Wall area and enclosed volume of a spherical octant of radius `r` in a corner of a unit
cube. -/
noncomputable def octantArea (r : ℝ) : ℝ := π * r ^ 2 / 2
noncomputable def octantVolume (r : ℝ) : ℝ := π * r ^ 3 / 6

/-- thompson1917-ch08-03: in a unit cube, a quarter-cylinder cutting off a corner has less
area than a plane wall (area 1) exactly when it encloses less than `1/π ≈ 0.32` of the
volume. -/
theorem quarterCyl_lt_plane (r : ℝ) (hr : 0 < r) :
    quarterCylArea r < 1 ↔ quarterCylVolume r < 1 / π := by
  unfold quarterCylArea quarterCylVolume
  have hπ := Real.pi_pos
  rw [div_lt_one (by norm_num), lt_div_iff₀ hπ]
  constructor
  · intro h; nlinarith [mul_pos hπ hr]
  · intro h; nlinarith [mul_pos hπ hr]

/-- thompson1917-ch08-03: for the same cut-off volume `v`, a spherical octant has less wall
area than a quarter-cylinder exactly when `v < 4π/81 ≈ 0.155`. -/
theorem octant_lt_quarterCyl (v rc rs : ℝ) (hc : 0 < rc) (hs : 0 < rs)
    (hvc : quarterCylVolume rc = v) (hvs : octantVolume rs = v) :
    octantArea rs < quarterCylArea rc ↔ v < 4 * π / 81 := by
  unfold quarterCylVolume at hvc
  unfold octantVolume at hvs
  unfold octantArea quarterCylArea
  have hπ := Real.pi_pos
  have step1 : π * rs ^ 2 / 2 < π * rc / 2 ↔ rs ^ 2 < rc := by
    constructor <;> intro h <;> nlinarith
  have step2 : rs ^ 2 < rc ↔ rs ^ 4 < rc ^ 2 := by
    constructor
    · intro h; nlinarith [sq_nonneg rs]
    · intro h; nlinarith [sq_nonneg (rs ^ 2 - rc), sq_nonneg (rs ^ 2 + rc)]
  have step3 : rs ^ 4 < rc ^ 2 ↔ rs < 2 / 3 := by
    have hrc2 : rc ^ 2 = 2 / 3 * rs ^ 3 := by nlinarith
    rw [hrc2]
    constructor
    · intro h; nlinarith [pow_pos hs 3]
    · intro h; nlinarith [pow_pos hs 3]
  have step4 : rs < 2 / 3 ↔ v < 4 * π / 81 := by
    rw [← hvs]
    constructor
    · intro h
      have : rs ^ 3 < (2 / 3) ^ 3 := by gcongr
      nlinarith
    · intro h
      by_contra hge; push Not at hge
      have : (2 / 3) ^ 3 ≤ rs ^ 3 := by gcongr
      nlinarith
  rw [step1, step2, step3, step4]

/-- thompson1917-ch08-03: numerical values of the two thresholds, "about three-tenths" and
"about 0.15" of the volume. -/
theorem corner_thresholds : 0.31 < 1 / π ∧ 1 / π < 0.32 ∧ 0.15 < 4 * π / 81 ∧
    4 * π / 81 < 0.16 := by
  have h1 := Real.pi_gt_d2
  have h2 := Real.pi_lt_d2
  have hπ := Real.pi_pos
  refine ⟨?_, ?_, ?_, ?_⟩
  · rw [lt_div_iff₀ hπ]; nlinarith
  · rw [div_lt_iff₀ hπ]; nlinarith
  · linarith
  · linarith

/-! ## Division of a quadrant and of a sector -/

/-- Area (radius 1) cut off from a quadrant `OAB` by a circular arc `MP` meeting the side `OA`
and the periphery at right angles, the tangent at `P` making angle `θ` with `OA`
(Thompson's Fig. 146): `½ (π/2 − θ + θ cot² θ − cot θ)`. -/
noncomputable def anticlinalCutArea (θ : ℝ) : ℝ :=
  (π / 2 - θ + θ * (Real.cos θ / Real.sin θ) ^ 2 - Real.cos θ / Real.sin θ) / 2

/-- Length `θ cot θ` of that anticlinal arc. -/
noncomputable def anticlinalArcLength (θ : ℝ) : ℝ := θ * (Real.cos θ / Real.sin θ)

/-- Length of the concentric (periclinal) arc bisecting a sector of angle `α` and radius 1:
it lies at radius `1/√2`. -/
noncomputable def periclinalLength (α : ℝ) : ℝ := α / √2

/-- thompson1917-ch08-04: some orthogonal arc bisects the unit quadrant, with `θ` strictly
between 30° and 45°, so it cuts off between 45° and 60° of the quadrant's arc. -/
theorem quadrant_bisected :
    ∃ θ ∈ Set.Ioo (π / 6) (π / 4), anticlinalCutArea θ = π / 8 := by
  have hπ := Real.pi_pos
  have h6 : anticlinalCutArea (π / 6) = (5 * π / 6 - √3) / 2 := by
    unfold anticlinalCutArea
    rw [Real.cos_pi_div_six, Real.sin_pi_div_six]
    have h3 : √3 ^ 2 = 3 := Real.sq_sqrt (by norm_num)
    field_simp; rw [h3]; ring
  have h4 : anticlinalCutArea (π / 4) = (π / 2 - 1) / 2 := by
    unfold anticlinalCutArea
    rw [Real.cos_pi_div_four, Real.sin_pi_div_four]
    have h2 : (√2 / 2) / (√2 / 2) = (1 : ℝ) := div_self (by positivity)
    rw [h2]; ring
  have hs3 : √3 < 1.75 := by rw [Real.sqrt_lt' (by norm_num)]; norm_num
  have hlo : anticlinalCutArea (π / 4) < π / 8 := by
    rw [h4]; linarith [Real.pi_lt_d2]
  have hhi : π / 8 < anticlinalCutArea (π / 6) := by
    rw [h6]; linarith [Real.pi_gt_d2]
  have hcont : ContinuousOn anticlinalCutArea (Set.Icc (π / 6) (π / 4)) := by
    have hsin : ∀ x ∈ Set.Icc (π / 6) (π / 4), Real.sin x ≠ 0 := by
      intro x hx
      exact (Real.sin_pos_of_pos_of_lt_pi (by linarith [hx.1]) (by linarith [hx.2])).ne'
    unfold anticlinalCutArea
    apply ContinuousOn.div_const
    apply ContinuousOn.sub
    · apply ContinuousOn.add (by fun_prop)
      apply ContinuousOn.mul (by fun_prop)
      exact (ContinuousOn.div (by fun_prop) (by fun_prop) hsin).pow 2
    · exact ContinuousOn.div (by fun_prop) (by fun_prop) hsin
  obtain ⟨θ, hθ, hval⟩ := intermediate_value_Icc' (by linarith) hcont ⟨hlo.le, hhi.le⟩
  refine ⟨θ, ⟨?_, ?_⟩, hval⟩
  · rcases eq_or_lt_of_le hθ.1 with h | h
    · rw [← h] at hval; linarith
    · exact h
  · rcases eq_or_lt_of_le hθ.2 with h | h
    · rw [h] at hval; linarith
    · exact h

/-- thompson1917-ch08-04: any such anticlinal arc is shorter than a radial wall (length 1),
which in turn is shorter than the periclinal arc bisecting the quadrant (`π / (2√2)`). -/
theorem anticlinal_shortest (θ : ℝ) (h0 : 0 < θ) (h1 : θ < π / 2) :
    anticlinalArcLength θ < 1 ∧ 1 < periclinalLength (π / 2) := by
  have hsin : 0 < Real.sin θ := Real.sin_pos_of_pos_of_lt_pi h0 (by linarith [Real.pi_pos])
  have hcos : 0 < Real.cos θ := Real.cos_pos_of_mem_Ioo ⟨by linarith, h1⟩
  constructor
  · unfold anticlinalArcLength
    have ht := Real.lt_tan h0 h1
    rw [Real.tan_eq_sin_div_cos, lt_div_iff₀ hcos] at ht
    rw [← mul_div_assoc, div_lt_one hsin]; exact ht
  · unfold periclinalLength
    have hs2 : √2 < 1.415 := by rw [Real.sqrt_lt' (by norm_num)]; norm_num
    rw [lt_div_iff₀ (by positivity)]
    linarith [Real.pi_gt_d2]

/-- thompson1917-ch08-05: the concentric (periclinal) arc at radius `1/√2` bisects a sector of
any angle `α`, and its length is `α / √2`. -/
theorem periclinal_bisects (α : ℝ) :
    α * (1 / √2) ^ 2 / 2 = (α / 2) / 2 ∧ α * (1 / √2) = periclinalLength α := by
  have h2 : √2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  constructor
  · rw [div_pow, h2]; ring
  · unfold periclinalLength; ring

/-- thompson1917-ch08-05: in a sector whose angle of arc is at least `√2` rad (about 81°),
an anticlinal bisecting arc is always shorter than the periclinal one. -/
theorem anticlinal_lt_periclinal (θ α : ℝ) (h0 : 0 < θ) (h1 : θ < π / 2) (hα : √2 ≤ α) :
    anticlinalArcLength θ < periclinalLength α := by
  have hlt := (anticlinal_shortest θ h0 h1).1
  have : 1 ≤ periclinalLength α := by
    unfold periclinalLength; rw [le_div_iff₀ (by positivity)]; linarith
  linarith

/-- Radius to which a uniformly growing unit disc must grow for a cell bordering an arc of
angle `φ` to add, as a sector margin, its own original area `π/8` (half a quadrant):
`(φ/2) (R² − 1) = π/8`. -/
noncomputable def doublingRadius (φ : ℝ) : ℝ := √(1 + π / (4 * φ))

/-- thompson1917-ch08-06: at radius `doublingRadius φ` the cell's added margin equals its
original area. -/
theorem doublingRadius_spec (φ : ℝ) (hφ : 0 < φ) :
    φ / 2 * (doublingRadius φ ^ 2 - 1) = π / 8 := by
  unfold doublingRadius
  rw [Real.sq_sqrt (by positivity)]
  field_simp; ring

/-- thompson1917-ch08-06: after a quadrant is bisected by an anticlinal arc with
`θ < 45°`, the triangular cell (arc `π/2 − θ`) reaches double size before the disc radius
reaches `√2`, while the quadrilateral cell (arc `θ`) does so only after: uniform growth of the
disc gives unequal growth of its cells. -/
theorem triangular_divides_first (θ : ℝ) (h0 : 0 < θ) (h1 : θ < π / 4) :
    doublingRadius (π / 2 - θ) < √2 ∧ √2 < doublingRadius θ := by
  have hπ := Real.pi_pos
  unfold doublingRadius
  constructor
  · have hpos : 0 < π / 2 - θ := by linarith
    apply Real.sqrt_lt_sqrt (by positivity)
    have : π / (4 * (π / 2 - θ)) < 1 := by
      rw [div_lt_one (by linarith)]; linarith
    linarith
  · apply Real.sqrt_lt_sqrt (by norm_num)
    have : 1 < π / (4 * θ) := by
      rw [one_lt_div (by positivity)]; linarith
    linarith

/-! ## Eight-celled aggregates -/

/-- thompson1917-ch08-09: a disc divided into `n ≥ 2` cells that all reach the boundary, with
walls meeting three at a time. With `j` interior triple junctions and `e` interior wall
segments, Euler's formula (`V − E + F = 2`, the outside counted as a face) and the
degree count (every vertex has degree 3) force `j = n − 2`, `e = 2n − 3`, and so
`e − n = n − 3` partitions that do not reach the boundary. -/
theorem intermediatePartitions (n j e : ℤ)
    (heuler : (j + n) - (n + e) + (n + 1) = 2) (hdeg : 3 * (j + n) = 2 * (n + e)) :
    j = n - 2 ∧ e = 2 * n - 3 ∧ e - n = n - 3 := by
  omega

end ThompsonLaws.Cells
