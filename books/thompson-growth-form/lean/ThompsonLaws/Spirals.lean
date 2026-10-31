import Mathlib

namespace ThompsonLaws.Spirals

open scoped Real InnerProductSpace

noncomputable section

/-! ## Spicules and cell junctions (chapter IX) -/

section Spicules

variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]

/-- thompson1917-ch09-08: a spicule growing "straight" while confined to the wall of a
spherical cell follows a great circle `cos t • u + sin t • v` (u, v orthonormal). -/
def greatCircle (u v : E) (t : ℝ) : E := Real.cos t • u + Real.sin t • v

/-- Velocity of `greatCircle`. -/
def greatCircleVel (u v : E) (t : ℝ) : E := (-Real.sin t) • u + Real.cos t • v

theorem greatCircle_norm (u v : E) (hu : ‖u‖ = 1) (hv : ‖v‖ = 1) (huv : ⟪u, v⟫_ℝ = 0)
    (t : ℝ) : ‖greatCircle u v t‖ = 1 := by
  have hvu : ⟪v, u⟫_ℝ = 0 := by rw [real_inner_comm]; exact huv
  have hu' : ⟪u, u⟫_ℝ = 1 := by rw [real_inner_self_eq_norm_sq, hu]; norm_num
  have hv' : ⟪v, v⟫_ℝ = 1 := by rw [real_inner_self_eq_norm_sq, hv]; norm_num
  have h : ‖greatCircle u v t‖ ^ 2 = 1 := by
    rw [← real_inner_self_eq_norm_sq]
    simp only [greatCircle, inner_add_left, inner_add_right, real_inner_smul_left,
      real_inner_smul_right, hu', hv', huv, hvu]
    linear_combination Real.cos_sq_add_sin_sq t
  nlinarith [norm_nonneg (greatCircle u v t)]

theorem greatCircle_hasDerivAt (u v : E) (t : ℝ) :
    HasDerivAt (greatCircle u v) (greatCircleVel u v t) t := by
  unfold greatCircle greatCircleVel
  exact ((Real.hasDerivAt_cos t).smul_const u).add ((Real.hasDerivAt_sin t).smul_const v)

/-- The great circle is a geodesic of the sphere (κ_g = 0): it stays on the unit sphere and
its acceleration is `-γ(t)`, i.e. along the sphere's normal, with no tangential part. -/
theorem greatCircle_isGeodesic (u v : E) (hu : ‖u‖ = 1) (hv : ‖v‖ = 1)
    (huv : ⟪u, v⟫_ℝ = 0) (t : ℝ) :
    ‖greatCircle u v t‖ = 1 ∧
      HasDerivAt (greatCircleVel u v) (-greatCircle u v t) t := by
  refine ⟨greatCircle_norm u v hu hv huv t, ?_⟩
  have := ((Real.hasDerivAt_sin t).neg.smul_const u).add
    ((Real.hasDerivAt_cos t).smul_const v)
  unfold greatCircle greatCircleVel
  convert this using 1
  simp only [neg_add, neg_smul]

/-- thompson1917-ch09-10: resultant of the partition tensions meeting at a cell junction. -/
def junctionForce (a b c : E) : E := a + b + c

theorem arccos_neg_half : Real.arccos (-1 / 2) = 2 * π / 3 := by
  have h : Real.cos (2 * π / 3) = -1 / 2 := by
    have : 2 * π / 3 = π - π / 3 := by ring
    rw [this, Real.cos_pi_sub, Real.cos_pi_div_three]; norm_num
  rw [← h, Real.arccos_cos] <;> linarith [Real.pi_pos]

/-- Three equal partition tensions in equilibrium meet at 120°: rays of a triradiate spicule. -/
theorem triradiate_angle (a b c : E) (ha : ‖a‖ = 1) (hb : ‖b‖ = 1) (hc : ‖c‖ = 1)
    (heq : junctionForce a b c = 0) :
    InnerProductGeometry.angle a b = 2 * π / 3 := by
  have hc' : c = -(a + b) := eq_neg_of_add_eq_zero_right heq
  have h1 : ‖a + b‖ ^ 2 = 1 := by rw [← norm_neg, ← hc', hc]; norm_num
  rw [norm_add_sq_real, ha, hb] at h1
  have hab : ⟪a, b⟫_ℝ = -1 / 2 := by linarith
  rw [InnerProductGeometry.angle, hab, ha, hb]
  simpa using arccos_neg_half

/-- Four equal tensions in equilibrium, symmetric in pairs (a solid group of four equal cells),
meet at the tetrahedral angle `arccos (-1/3) ≈ 109° 28'`. -/
theorem tetraradiate_angle (v : Fin 4 → E) (k : ℝ) (hv : ∀ i, ‖v i‖ = 1)
    (hk : ∀ i j, i ≠ j → ⟪v i, v j⟫_ℝ = k) (hsum : ∑ i, v i = 0) (i j : Fin 4)
    (hij : i ≠ j) :
    k = -1 / 3 ∧ InnerProductGeometry.angle (v i) (v j) = Real.arccos (-1 / 3) := by
  have hself : ∀ i, ⟪v i, v i⟫_ℝ = 1 := fun i => by
    rw [real_inner_self_eq_norm_sq, hv i]; norm_num
  have h0 : ⟪∑ i, v i, ∑ i, v i⟫_ℝ = 0 := by rw [hsum, inner_zero_left]
  rw [Fin.sum_univ_four] at h0
  simp only [inner_add_left, inner_add_right, hself,
    hk 0 1 (by decide), hk 0 2 (by decide), hk 0 3 (by decide), hk 1 0 (by decide),
    hk 1 2 (by decide), hk 1 3 (by decide), hk 2 0 (by decide), hk 2 1 (by decide),
    hk 2 3 (by decide), hk 3 0 (by decide), hk 3 1 (by decide), hk 3 2 (by decide)] at h0
  have hk3 : k = -1 / 3 := by linarith
  refine ⟨hk3, ?_⟩
  rw [InnerProductGeometry.angle, hk i j hij, hv i, hv j, hk3]
  norm_num

/-- thompson1917-ch09-16: component of the edge direction `v j` orthogonal to the edge `v i`,
for a tetrahedral group of four cells; it spans the interface through edges i and j. -/
def interfaceDirection (v : Fin 4 → E) (i j : Fin 4) : E := v j + (1 / 3 : ℝ) • v i

/-- In the tetrahedral film system the three plane interfaces meeting along each edge make
dihedral angles of 120° with one another (their directions orthogonal to the edge are at 120°). -/
theorem tetrahedral_interfaces_120 (v : Fin 4 → E) (hv : ∀ i, ‖v i‖ = 1)
    (hk : ∀ i j, i ≠ j → ⟪v i, v j⟫_ℝ = -1 / 3) (i j l : Fin 4) (hij : i ≠ j) (hil : i ≠ l)
    (hjl : j ≠ l) :
    ⟪interfaceDirection v i j, v i⟫_ℝ = 0 ∧
      InnerProductGeometry.angle (interfaceDirection v i j) (interfaceDirection v i l) =
        2 * π / 3 := by
  have hself : ∀ i, ⟪v i, v i⟫_ℝ = 1 := fun i => by
    rw [real_inner_self_eq_norm_sq, hv i]; norm_num
  have hji := hk j i (Ne.symm hij)
  have hli := hk l i (Ne.symm hil)
  have hjl' := hk j l hjl
  have hil' := hk i l hil
  have hij' := hk i j hij
  refine ⟨?_, ?_⟩
  · simp only [interfaceDirection, inner_add_left, real_inner_smul_left, hji, hself]
    norm_num
  have hin : ⟪interfaceDirection v i j, interfaceDirection v i l⟫_ℝ = -4 / 9 := by
    simp only [interfaceDirection, inner_add_left, inner_add_right, real_inner_smul_left,
      real_inner_smul_right, hjl', hji, hil', hself]
    norm_num
  have hn : ∀ m, i ≠ m → ‖interfaceDirection v i m‖ ^ 2 = 8 / 9 := fun m him => by
    rw [← real_inner_self_eq_norm_sq]
    simp only [interfaceDirection, inner_add_left, inner_add_right, real_inner_smul_left,
      real_inner_smul_right, hk m i (Ne.symm him), hk i m him, hself]
    norm_num
  have hj := hn j hij
  have hl := hn l hil
  have hprod : ‖interfaceDirection v i j‖ * ‖interfaceDirection v i l‖ = 8 / 9 := by
    have h0 := norm_nonneg (interfaceDirection v i j)
    have h1 := norm_nonneg (interfaceDirection v i l)
    have hsq : (‖interfaceDirection v i j‖ * ‖interfaceDirection v i l‖) ^ 2 = (8 / 9) ^ 2 := by
      rw [mul_pow, hj, hl]; norm_num
    nlinarith [mul_nonneg h0 h1]
  rw [InnerProductGeometry.angle, hin, hprod]
  have : (-4 / 9 : ℝ) / (8 / 9) = -1 / 2 := by norm_num
  rw [this, arccos_neg_half]

end Spicules

/-! ## Geodesics on cylinders and cones (chapter X) -/

/-- thompson1917-ch10-01: helix `(r cos ωt, r sin ωt, a t)` on the cylinder of radius r;
`a = 0` gives the parallel rings, `ω = 0` the longitudinal lines. -/
def cylinderHelix (r ω a t : ℝ) : ℝ × ℝ × ℝ :=
  (r * Real.cos (ω * t), r * Real.sin (ω * t), a * t)

/-- Velocity of `cylinderHelix`. -/
def cylinderHelixVel (r ω a t : ℝ) : ℝ × ℝ × ℝ :=
  (-(r * ω) * Real.sin (ω * t), r * ω * Real.cos (ω * t), a)

theorem cylinderHelix_hasDerivAt (r ω a t : ℝ) :
    HasDerivAt (cylinderHelix r ω a) (cylinderHelixVel r ω a t) t := by
  have hl : HasDerivAt (fun t => ω * t) ω t := by
    simpa using (hasDerivAt_id t).const_mul ω
  have hx : HasDerivAt (fun t => r * Real.cos (ω * t)) (r * (-Real.sin (ω * t) * ω)) t :=
    ((Real.hasDerivAt_cos (ω * t)).comp t hl).const_mul r
  have hy : HasDerivAt (fun t => r * Real.sin (ω * t)) (r * (Real.cos (ω * t) * ω)) t :=
    ((Real.hasDerivAt_sin (ω * t)).comp t hl).const_mul r
  have hz : HasDerivAt (fun t => a * t) a t := by simpa using (hasDerivAt_id t).const_mul a
  have := hx.prodMk (hy.prodMk hz)
  convert this using 1
  · rfl
  simp only [cylinderHelixVel, Prod.mk.injEq]
  refine ⟨by ring, by ring, trivial⟩

/-- Every helix, ring and longitudinal line lies on the cylinder and is a geodesic of it:
its acceleration `-ω² (x, y, 0)` is along the cylinder's normal. -/
theorem cylinderHelix_isGeodesic (r ω a t : ℝ) :
    (cylinderHelix r ω a t).1 ^ 2 + (cylinderHelix r ω a t).2.1 ^ 2 = r ^ 2 ∧
      HasDerivAt (cylinderHelixVel r ω a)
        ((-ω ^ 2) • ((cylinderHelix r ω a t).1, (cylinderHelix r ω a t).2.1, (0 : ℝ))) t := by
  refine ⟨?_, ?_⟩
  · simp only [cylinderHelix]
    linear_combination r ^ 2 * Real.cos_sq_add_sin_sq (ω * t)
  have hl : HasDerivAt (fun t => ω * t) ω t := by
    simpa using (hasDerivAt_id t).const_mul ω
  have hx : HasDerivAt (fun t => -(r * ω) * Real.sin (ω * t))
      (-(r * ω) * (Real.cos (ω * t) * ω)) t :=
    ((Real.hasDerivAt_sin (ω * t)).comp t hl).const_mul (-(r * ω))
  have hy : HasDerivAt (fun t => r * ω * Real.cos (ω * t))
      (r * ω * (-Real.sin (ω * t) * ω)) t :=
    ((Real.hasDerivAt_cos (ω * t)).comp t hl).const_mul (r * ω)
  have hz : HasDerivAt (fun _ : ℝ => a) 0 t := hasDerivAt_const t a
  have := hx.prodMk (hy.prodMk hz)
  convert this using 1
  · rfl
  simp only [cylinderHelix, Prod.smul_mk, smul_eq_mul, Prod.mk.injEq]
  refine ⟨by ring, by ring, by ring⟩

/-- thompson1917-ch10-02: sine of the angle ψ between a cone geodesic and the generator through
the point. Unrolled, the geodesic is the straight line `(t, p)` at distance `p` from the apex,
and the point at parameter `t` lies at distance `√(t² + p²)` from the apex. -/
def coneGeodesicSin (p t : ℝ) : ℝ := p / Real.sqrt (t ^ 2 + p ^ 2)

/-- Clairaut's relation on a cone of half-angle β: radius from the axis `ρ = sin β · s` times
`sin ψ` is constant along the geodesic. -/
theorem coneGeodesic_clairaut (β p t : ℝ) (hp : 0 < p) :
    (Real.sin β * Real.sqrt (t ^ 2 + p ^ 2)) * coneGeodesicSin p t = p * Real.sin β := by
  have hs : 0 < Real.sqrt (t ^ 2 + p ^ 2) := Real.sqrt_pos.mpr (by positivity)
  unfold coneGeodesicSin
  field_simp

/-- As the cone narrows (the point nears the apex), the geodesic makes a larger angle with the
generators, i.e. it coils more and more closely. -/
theorem coneGeodesic_coils_closer (p t₁ t₂ : ℝ) (hp : 0 < p) (h₁ : 0 ≤ t₁) (h : t₁ < t₂) :
    coneGeodesicSin p t₂ < coneGeodesicSin p t₁ := by
  unfold coneGeodesicSin
  have hs : 0 < Real.sqrt (t₁ ^ 2 + p ^ 2) := Real.sqrt_pos.mpr (by positivity)
  apply div_lt_div_of_pos_left hp hs
  apply Real.sqrt_lt_sqrt (by positivity)
  nlinarith

/-- thompson1917-ch10-04: length of a path in the development (unrolled surface) of a tube,
given its velocity `γ'`. -/
def pathLength (γ' : ℝ → EuclideanSpace ℝ (Fin 2)) (a b : ℝ) : ℝ :=
  ∫ t in a..b, ‖γ' t‖

/-- Unrolling the cylinder of radius r preserves speed: the map `(s, z) ↦ (r cos(s/r),
r sin(s/r), z)` sends a velocity `(s', z')` to one of the same length. -/
theorem cylinder_development_speed (r s s' z' : ℝ) (hr : r ≠ 0) :
    (-(r * Real.sin (s / r)) * (s' / r)) ^ 2 + (r * Real.cos (s / r) * (s' / r)) ^ 2 + z' ^ 2 =
      s' ^ 2 + z' ^ 2 := by
  field_simp
  linear_combination s' ^ 2 * Real.sin_sq_add_cos_sq (s / r)

/-- A fibre fixed at P and Q pulls itself to the shortest path: every path from P to Q in the
development is at least as long as the straight chord, which is attained by the straight
segment (a ring, longitudinal line or helix on the tube). -/
theorem fibre_shortest_path (γ γ' : ℝ → EuclideanSpace ℝ (Fin 2)) (a b : ℝ) (hab : a ≤ b)
    (hγ : ∀ t ∈ Set.uIcc a b, HasDerivAt γ (γ' t) t)
    (hint : IntervalIntegrable γ' MeasureTheory.volume a b) :
    ‖γ b - γ a‖ ≤ pathLength γ' a b ∧
      pathLength (fun _ => γ b - γ a) 0 1 = ‖γ b - γ a‖ := by
  refine ⟨?_, ?_⟩
  · rw [pathLength, ← intervalIntegral.integral_eq_sub_of_hasDerivAt hγ hint]
    exact intervalIntegral.norm_integral_le_integral_norm hab
  · simp [pathLength]

/-! ## The logarithmic spiral (chapter XI) -/

/-- thompson1917-ch11-01: the logarithmic spiral `r = a e^{kθ}`, with `k = cot α`. -/
def logSpiral (a k θ : ℝ) : ℝ := a * Real.exp (k * θ)

/-- The constant angle α between radius and tangent, defined by `cot α = k`. -/
def constantAngle (k : ℝ) : ℝ := π / 2 - Real.arctan k

theorem logSpiral_hasDerivAt (a k θ : ℝ) :
    HasDerivAt (logSpiral a k) (k * logSpiral a k θ) θ := by
  have hl : HasDerivAt (fun θ => k * θ) k θ := by
    simpa using (hasDerivAt_id θ).const_mul k
  have := (hl.exp).const_mul a
  unfold logSpiral
  convert this using 1
  ring

theorem constantAngle_tan (k : ℝ) : Real.tan (constantAngle k) = k⁻¹ := by
  rw [constantAngle, Real.tan_pi_div_two_sub, Real.tan_arctan]

/-- Equiangular property: at every point the tangent of the angle between radius and tangent,
`r / (dr/dθ)`, equals `tan α`, the same everywhere. -/
theorem logSpiral_equiangular (a k θ : ℝ) (ha : a ≠ 0) :
    logSpiral a k θ / deriv (logSpiral a k) θ = Real.tan (constantAngle k) := by
  rw [(logSpiral_hasDerivAt a k θ).deriv, constantAngle_tan]
  have : logSpiral a k θ ≠ 0 := mul_ne_zero ha (Real.exp_pos _).ne'
  by_cases hk : k = 0
  · simp [hk]
  · field_simp

/-- thompson1917-ch11-03: a curve whose radial growth `dr/dθ` bears the constant ratio k to its
transverse growth `r` is a logarithmic spiral. -/
theorem eq_logSpiral_of_constant_growth_ratio (r : ℝ → ℝ) (k : ℝ)
    (h : ∀ θ, HasDerivAt r (k * r θ) θ) (θ : ℝ) : r θ = logSpiral (r 0) k θ := by
  set g : ℝ → ℝ := fun θ => r θ * Real.exp (θ * -k) with hg
  have hd : ∀ θ, HasDerivAt g 0 θ := fun θ => by
    have := (h θ).mul (hasDerivAt_mul_const (-k) |>.exp)
    convert this using 1
    ring
  have hc := is_const_of_deriv_eq_zero (fun θ => (hd θ).differentiableAt)
    (fun θ => (hd θ).deriv) θ 0
  simp only [hg, zero_mul, Real.exp_zero, mul_one] at hc
  have he : Real.exp (θ * -k) * Real.exp (k * θ) = 1 := by
    rw [← Real.exp_add]; simp [mul_comm]
  unfold logSpiral
  rw [← hc, mul_assoc, he, mul_one]

/-- Limiting case: ratio zero (α = 90°) gives the circle. -/
theorem constant_growth_ratio_zero_circle (r : ℝ → ℝ) (h : ∀ θ, HasDerivAt r (0 * r θ) θ)
    (θ : ℝ) : r θ = r 0 := by
  rw [eq_logSpiral_of_constant_growth_ratio r 0 h θ, logSpiral]; simp

/-- thompson1917-ch11-04: tip of the n-th shoot of a scorpioid cyme whose shoots shrink by
the ratio q and turn by the constant angle φ, with `w = q e^{iφ}` and first shoot `l₀`. -/
def cymeVertex (l₀ : ℝ) (w : ℂ) (n : ℕ) : ℂ :=
  ∑ j ∈ Finset.range n, (l₀ : ℂ) * w ^ j

/-- The pole of the cyme spiral. -/
def cymePole (l₀ : ℝ) (w : ℂ) : ℂ := l₀ / (1 - w)

theorem cymeVertex_sub_pole (l₀ : ℝ) (w : ℂ) (hw : w ≠ 1) (n : ℕ) :
    cymeVertex l₀ w n - cymePole l₀ w = (l₀ / (w - 1)) * w ^ n := by
  have h1 : w - 1 ≠ 0 := sub_ne_zero.mpr hw
  have h2 : 1 - w ≠ 0 := sub_ne_zero.mpr hw.symm
  rw [cymeVertex, ← Finset.mul_sum, geom_sum_eq hw, cymePole]
  field_simp
  ring

/-- The shoot tips lie on a logarithmic spiral about the pole: each is carried to the next by
the same spiral similarity `z ↦ w z` (rotation by φ, scaling by q), and their distances from
the pole fall in the geometric progression `q^n`. -/
theorem cyme_logSpiral (l₀ q φ : ℝ) (hq : 0 ≤ q) (hw : (q : ℂ) * Complex.exp (φ * Complex.I) ≠ 1)
    (n : ℕ) :
    let w := (q : ℂ) * Complex.exp (φ * Complex.I)
    cymeVertex l₀ w (n + 1) - cymePole l₀ w = w * (cymeVertex l₀ w n - cymePole l₀ w) ∧
      ‖cymeVertex l₀ w n - cymePole l₀ w‖ = ‖cymeVertex l₀ w 0 - cymePole l₀ w‖ * q ^ n := by
  intro w
  have hnw : ‖w‖ = q := by
    simp only [w, norm_mul, Complex.norm_exp_ofReal_mul_I, mul_one, Complex.norm_real,
      Real.norm_eq_abs, abs_of_nonneg hq]
  refine ⟨?_, ?_⟩
  · rw [cymeVertex_sub_pole l₀ w hw, cymeVertex_sub_pole l₀ w hw]; ring
  · rw [cymeVertex_sub_pole l₀ w hw, cymeVertex_sub_pole l₀ w hw, norm_mul, norm_pow, hnw,
      pow_zero, mul_one]

/-- thompson1917-ch11-05: rotating the logarithmic spiral by φ is the same as enlarging it by
`e^{kφ}`, so terminal growth leaves its shape unchanged. -/
theorem logSpiral_rotate (a k θ φ : ℝ) :
    logSpiral a k (θ + φ) = Real.exp (k * φ) * logSpiral a k θ := by
  unfold logSpiral
  rw [mul_add, Real.exp_add]; ring

/-- Conversely, a smooth curve `r(θ)` whose every rotation is an enlargement of itself is a
logarithmic spiral: no other curve has this property. -/
theorem eq_logSpiral_of_selfSimilar (r : ℝ → ℝ) (hr : Differentiable ℝ r) (h0 : r 0 ≠ 0)
    (s : ℝ → ℝ) (h : ∀ θ φ, r (θ + φ) = s φ * r θ) (θ : ℝ) :
    r θ = logSpiral (r 0) (deriv r 0 / r 0) θ := by
  have hs : ∀ φ, s φ = r φ / r 0 := fun φ => by
    have := h 0 φ; rw [zero_add] at this; field_simp; linarith
  have hode : ∀ θ, HasDerivAt r (deriv r 0 / r 0 * r θ) θ := fun θ => by
    have h1 : HasDerivAt (fun φ => r (θ + φ)) (deriv r θ) 0 := by
      apply HasDerivAt.comp_const_add; rw [add_zero]; exact (hr θ).hasDerivAt
    have hfun : (fun φ => r (θ + φ)) = fun φ => r θ / r 0 * r φ := by
      funext φ; rw [h θ φ, hs φ]; ring
    rw [hfun] at h1
    have h2 := ((hr 0).hasDerivAt).const_mul (r θ / r 0)
    have hd := (hr θ).hasDerivAt
    rw [h1.unique h2] at hd
    convert hd using 1
    ring
  exact eq_logSpiral_of_constant_growth_ratio r _ hode θ

/-- thompson1917-ch11-06: the shell up to angle T, generated by sweeping a cross-section C
(any set in the plane) along the logarithmic spiral `e^{(k+i)θ}`. -/
def spiralShell (k : ℝ) (C : Set ℂ) (T : ℝ) : Set ℂ :=
  {z | ∃ θ : ℝ, θ ≤ T ∧ ∃ c ∈ C, z = Complex.exp ((k + Complex.I) * θ) * c}

/-- The increment of growth added between angles T and T + φ. -/
def spiralGnomon (k : ℝ) (C : Set ℂ) (T φ : ℝ) : Set ℂ :=
  {z | ∃ θ : ℝ, T < θ ∧ θ ≤ T + φ ∧ ∃ c ∈ C, z = Complex.exp ((k + Complex.I) * θ) * c}

/-- Spiral similarity: rotation by φ combined with enlargement by `e^{kφ}`. -/
def spiralSimilarity (k φ : ℝ) (z : ℂ) : ℂ :=
  Complex.exp ((k + Complex.I) * φ) * z

theorem exp_spiral_add (k θ φ : ℝ) :
    Complex.exp ((k + Complex.I) * φ) * Complex.exp ((k + Complex.I) * θ) =
      Complex.exp ((k + Complex.I) * ((θ + φ : ℝ) : ℂ)) := by
  rw [← Complex.exp_add]; congr 1; push_cast; ring

/-- thompson1917-ch12-04: the older shell is the younger shell enlarged and rotated, i.e. the
spiral shell keeps its shape (continued similarity). -/
theorem spiralShell_image (k φ T : ℝ) (C : Set ℂ) :
    spiralSimilarity k φ '' spiralShell k C T = spiralShell k C (T + φ) := by
  ext z
  constructor
  · rintro ⟨y, ⟨θ, hθ, c, hc, rfl⟩, rfl⟩
    refine ⟨θ + φ, by linarith, c, hc, ?_⟩
    rw [spiralSimilarity, ← mul_assoc, exp_spiral_add]
  · rintro ⟨θ, hθ, c, hc, rfl⟩
    refine ⟨Complex.exp ((k + Complex.I) * ((θ - φ : ℝ) : ℂ)) * c,
      ⟨θ - φ, by linarith, c, hc, rfl⟩, ?_⟩
    rw [spiralSimilarity, ← mul_assoc, exp_spiral_add, sub_add_cancel]

/-- Each increment of growth is a gnomon: shell plus increment is similar to the shell. -/
theorem spiralShell_gnomon (k φ T : ℝ) (C : Set ℂ) (hφ : 0 ≤ φ) :
    spiralShell k C T ∪ spiralGnomon k C T φ = spiralSimilarity k φ '' spiralShell k C T := by
  rw [spiralShell_image]
  ext z
  constructor
  · rintro (⟨θ, hθ, c, hc, rfl⟩ | ⟨θ, -, hθ, c, hc, rfl⟩)
    · exact ⟨θ, by linarith, c, hc, rfl⟩
    · exact ⟨θ, hθ, c, hc, rfl⟩
  · rintro ⟨θ, hθ, c, hc, rfl⟩
    by_cases h : θ ≤ T
    · exact Or.inl ⟨θ, h, c, hc, rfl⟩
    · exact Or.inr ⟨θ, lt_of_not_ge h, hθ, c, hc, rfl⟩

/-- thompson1917-ch11-08: breadth of the n-th whorl along the ray at angle θ. -/
def whorlBreadth (a k θ : ℝ) (n : ℕ) : ℝ :=
  logSpiral a k (θ + 2 * π * (n + 1)) - logSpiral a k (θ + 2 * π * n)

/-- Successive whorl breadths along a radius are in geometric progression, ratio `e^{2π k}`. -/
theorem whorlBreadth_succ (a k θ : ℝ) (n : ℕ) :
    whorlBreadth a k θ (n + 1) = Real.exp (2 * π * k) * whorlBreadth a k θ n := by
  unfold whorlBreadth
  have e1 : θ + 2 * π * ((↑(n + 1) : ℝ) + 1) = (θ + 2 * π * (n + 1)) + 2 * π := by
    push_cast; ring
  have e2 : θ + 2 * π * ((↑(n + 1) : ℝ)) = (θ + 2 * π * n) + 2 * π := by
    push_cast; ring
  rw [e1, e2, logSpiral_rotate a k (θ + 2 * π * (n + 1)) (2 * π),
    logSpiral_rotate a k (θ + 2 * π * n) (2 * π), mul_comm k]; ring

/-- thompson1917-ch11-10: ratio of the breadths of successive whorls, `e^{2π cot α}`. -/
def whorlRatio (k : ℝ) : ℝ := Real.exp (2 * π * k)

theorem whorlRatio_eq (a k θ : ℝ) (n : ℕ) :
    whorlBreadth a k θ (n + 1) = whorlRatio k * whorlBreadth a k θ n :=
  whorlBreadth_succ a k θ n

theorem cot_of_whorlRatio (k ρ : ℝ) (h : whorlRatio k = ρ) :
    k = Real.log ρ / (2 * π) := by
  rw [← h, whorlRatio, Real.log_exp]; field_simp

theorem tan_lt_of_bounds (y k : ℝ) (hy : 0 < y) (hy1 : y < 1) (hk : y < k * (1 - y ^ 2 / 2)) :
    Real.tan y < k := by
  have hc : 0 < Real.cos y :=
    Real.cos_pos_of_mem_Ioo ⟨by linarith [Real.pi_gt_three], by linarith [Real.pi_gt_three]⟩
  have hs := Real.sin_lt hy
  have hcb := Real.one_sub_sq_div_two_le_cos (x := y)
  have hpos : 0 < 1 - y ^ 2 / 2 := by nlinarith
  have hk0 : 0 < k := by
    by_contra hneg
    nlinarith [mul_le_mul_of_nonneg_right (not_lt.mp hneg) hpos.le]
  rw [Real.tan_eq_sin_div_cos, div_lt_iff₀ hc]
  nlinarith [mul_le_mul_of_nonneg_left hcb hk0.le]

theorem angle_bounds (k lo hi : ℝ) (hlo : 0 < lo) (hlo2 : lo < π / 2) (hhi : hi < π / 2)
    (h1 : k < hi) (h2 : Real.tan lo < k) :
    π / 2 - hi < constantAngle k ∧ constantAngle k < π / 2 - lo := by
  have hhi0 : 0 < hi := by
    have := Real.lt_tan hlo hlo2
    linarith
  unfold constantAngle
  constructor
  · have : Real.arctan k < hi := by
      calc Real.arctan k < Real.arctan (Real.tan hi) :=
            Real.arctan_strictMono (lt_trans h1 (Real.lt_tan hhi0 hhi))
        _ = hi := Real.arctan_tan (by linarith) hhi
    linarith
  · have : lo < Real.arctan k := by
      calc lo = Real.arctan (Real.tan lo) := (Real.arctan_tan (by linarith) hlo2).symm
        _ < Real.arctan k := Real.arctan_strictMono h2
    linarith

/-- Nautilus: whorls each three times as broad as the last give a constant angle of about 80°
(strictly between 79° and 81°). -/
theorem nautilus_constantAngle (k : ℝ) (h : whorlRatio k = 3) :
    79 * π / 180 < constantAngle k ∧ constantAngle k < 81 * π / 180 := by
  have hk := cot_of_whorlRatio k 3 h
  have hp1 := Real.pi_gt_d2
  have hp2 := Real.pi_lt_d4
  have hlog_lo : 1 < Real.log 3 := by
    rw [Real.lt_log_iff_exp_lt (by norm_num)]; linarith [Real.exp_one_lt_d9]
  have hlog_hi : Real.log 3 < 6 / 5 := by
    rw [Real.log_lt_iff_lt_exp (by norm_num)]
    have he : Real.exp (6 / 5) = Real.exp 1 * Real.exp (1 / 5) := by
      rw [← Real.exp_add]; norm_num
    have h15 := Real.add_one_le_exp (1 / 5 : ℝ)
    rw [he]; nlinarith [Real.exp_one_gt_d9, Real.exp_pos (1 / 5 : ℝ)]
  have hpi : 0 < π := Real.pi_pos
  have hkhi : k < 11 * π / 180 := by
    rw [hk, div_lt_iff₀ (by positivity)]; nlinarith
  have hklo : Real.tan (π / 20) < k := by
    apply tan_lt_of_bounds _ _ (by positivity) (by linarith)
    rw [hk]
    have hk1 : 1 / (2 * π) < Real.log 3 / (2 * π) := by
      apply div_lt_div_of_pos_right hlog_lo (by positivity)
    have hpos : 0 < 1 - (π / 20) ^ 2 / 2 := by nlinarith
    have : π / 20 < 1 / (2 * π) * (1 - (π / 20) ^ 2 / 2) := by
      rw [div_mul_eq_mul_div, one_mul, lt_div_iff₀ (by positivity)]; nlinarith
    nlinarith
  have := angle_bounds k (π / 20) (11 * π / 180) (by positivity) (by linarith) (by linarith) hkhi hklo
  constructor <;> linarith [this.1, this.2]

/-! ## Lines of growth on bivalve shells (chapter XI) -/

/-- thompson1917-ch11-16: point of the growth line at time t in direction θ from the umbo,
when growth rate depends on direction through `f`: `r(θ, t) = t f(θ)`. -/
def growthLine (f : ℝ → ℝ) (t θ : ℝ) : ℝ × ℝ :=
  (t * f θ * Real.cos θ, t * f θ * Real.sin θ)

/-- Successive growth lines are enlargements of one another about the umbo. -/
theorem growthLine_similar (f : ℝ → ℝ) (t θ : ℝ) :
    growthLine f t θ = t • growthLine f 1 θ := by
  simp only [growthLine, Prod.smul_mk, smul_eq_mul, one_mul]
  refine Prod.ext ?_ ?_ <;> simp only <;> ring

/-- With `f = cos`, the growth lines are coaxial circles of diameter t through the umbo,
centred on the axis at `(t/2, 0)`. -/
theorem growthLine_cos_circle (t θ : ℝ) :
    ((growthLine Real.cos t θ).1 - t / 2) ^ 2 + (growthLine Real.cos t θ).2 ^ 2 = (t / 2) ^ 2 ∧
      growthLine Real.cos t (π / 2) = (0, 0) := by
  refine ⟨?_, ?_⟩
  · simp only [growthLine]
    linear_combination (t ^ 2 * Real.cos θ ^ 2) * Real.sin_sq_add_cos_sq θ
  · simp [growthLine]

/-! ## Foraminifera (chapter XII) -/

/-- thompson1917-ch12-05: Fusulina, whorl ratio 1.5, gives a constant angle of about 86°
(strictly between 85° and 87°). -/
theorem fusulina_constantAngle (k : ℝ) (h : whorlRatio k = 3 / 2) :
    85 * π / 180 < constantAngle k ∧ constantAngle k < 87 * π / 180 := by
  have hk := cot_of_whorlRatio k (3 / 2) h
  have hp1 := Real.pi_gt_d2
  have hp2 := Real.pi_lt_d4
  have hpi : 0 < π := Real.pi_pos
  have hlog_lo : 1 / 3 ≤ Real.log (3 / 2) := by
    have := Real.one_sub_inv_le_log_of_pos (x := 3 / 2) (by norm_num); norm_num at this ⊢
    linarith
  have hlog_hi : Real.log (3 / 2) < 1 / 2 := by
    rw [Real.log_lt_iff_lt_exp (by norm_num)]
    have := Real.add_one_lt_exp (x := 1 / 2) (by norm_num); linarith
  have hkhi : k < 5 * π / 180 := by
    rw [hk, div_lt_iff₀ (by positivity)]; nlinarith
  have hklo : Real.tan (π / 60) < k := by
    apply tan_lt_of_bounds _ _ (by positivity) (by linarith)
    rw [hk]
    have hk1 : 1 / 3 / (2 * π) ≤ Real.log (3 / 2) / (2 * π) := by
      apply div_le_div_of_nonneg_right hlog_lo (by positivity)
    have hpos : 0 < 1 - (π / 60) ^ 2 / 2 := by nlinarith
    have : π / 60 < 1 / 3 / (2 * π) * (1 - (π / 60) ^ 2 / 2) := by
      rw [div_mul_eq_mul_div, lt_div_iff₀ (by positivity)]; nlinarith
    nlinarith
  have := angle_bounds k (π / 60) (5 * π / 180) (by positivity) (by linarith) (by linarith) hkhi hklo
  constructor <;> linarith [this.1, this.2]

/-- thompson1917-ch12-06: volume of the n-th chamber, the mass added between the formation of
successive chambers at equal time intervals τ. -/
def chamberVolume (M : ℝ → ℝ) (τ : ℝ) (n : ℕ) : ℝ := M ((n + 1) * τ) - M (n * τ)

/-- If the rate of increase is proportional to the whole existing mass, `dM/dt = c M`, each
chamber bears the constant ratio `e^{cτ}` to the one before. -/
theorem chamberVolume_ratio (M : ℝ → ℝ) (c τ : ℝ) (h : ∀ t, HasDerivAt M (c * M t) t)
    (n : ℕ) : chamberVolume M τ (n + 1) = Real.exp (c * τ) * chamberVolume M τ n := by
  have hM := eq_logSpiral_of_constant_growth_ratio M c h
  unfold chamberVolume
  have e1 : ((↑(n + 1) : ℝ) + 1) * τ = (n + 1) * τ + τ := by push_cast; ring
  have e2 : ((↑(n + 1) : ℝ)) * τ = n * τ + τ := by push_cast; ring
  rw [e1, e2, hM ((n + 1) * τ + τ), hM (n * τ + τ), hM ((n + 1) * τ), hM (n * τ),
    logSpiral_rotate _ c ((n + 1) * τ) τ, logSpiral_rotate _ c (n * τ) τ]; ring

end

end ThompsonLaws.Spirals
