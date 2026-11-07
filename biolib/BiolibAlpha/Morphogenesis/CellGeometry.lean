/-
# Cell geometry: Plateau's junction rules, the hexagon, the twelve pentagons, the bee's cell
and hexagonal packing

Thompson, *On Growth and Form* (1917), chapters V, VII and VIII, and Plateau's rules for soap films
(1873). The first four results are ports of the Lean-checked Thompson claims in
`claim-sources/thompson-growth-form/lean/ThompsonLaws/Cells.lean` and `TwelvePentagons.lean`
(claims thompson1917-ch07-04, -06, -09, -11 and ch16-14); the junction theorems are stated for any
real inner-product space, so they also cover films meeting along a line in three dimensions. The
last three are new: Plateau's second rule (four films meet at the tetrahedral angle), the Euler
bookkeeping behind "hexagonal on average" (thompson1917-ch07-08 and -10, an `identity`-kind claim), and
the density of the hexagonal lattice packing of discs.

## What is proved

* `tripleJunction_120`: three walls of equal positive tension balanced at a point meet pairwise
  at exactly 120°; the sizes of the cells never enter. `junction_inner` is the general Neumann
  triangle `T₃² = T₁² + T₂² + 2 T₁ T₂ cos ∠(u, v)`.
* `hexagon_of_120`: a straight-walled cell whose every corner is a 120° junction has exactly six
  sides, with the two one-sided inequalities (fewer than six sides force a sharper mean corner,
  more than six a blunter one).
* `pentagons_eq_twelve`: a trivalent closed lattice of pentagons and hexagons has exactly twelve
  pentagons, whatever the material.
* `average_sides`: in any trivalent closed lattice the mean number of sides per face is
  `6 - 12/F`, strictly below six and tending to six as the number of faces grows.
* `beeCellArea_min`: a hexagonal prism closed by three rhombi has least surface exactly when
  `cos θ = 1/√3`; `beeCell_rhombus_angle` gives the rhombus angle `cos = -1/3` (the angle of the
  rhombic dodecahedron, 109° 28′).
* `tetrahedralJunction_angle`: four walls of equal positive tension balanced at a point, meeting
  one another at equal angles, meet at `arccos (-1/3)`, which lies strictly between 90° and the
  120° of a triple junction; `quadJunction_inner_sum` is the unsymmetric statement, the six pairwise
  cosines sum to `-2`.
* `hex_denser_than_square`: equal discs on the hexagonal (triangular) lattice fill `π / (2√3)`
  of the plane, between 0.9068 and 0.9070, and more than the square lattice's `π/4`.

## What is assumed, not proved

* Walls are fluid films of uniform tension in static equilibrium; the force balance at a junction
  is the whole model. Nothing is said about how a tissue reaches equilibrium or whether a given
  epithelium is one.
* `hexagon_of_120` is about a single convex polygon with straight sides; curved walls between
  unequal cells (`partitionCurvature` in the Thompson module) are outside it.
* `hex_denser_than_square` compares two lattice arrangements. It does **not** prove that the
  hexagonal arrangement is the densest of all packings of equal discs (Thue 1910, Fejes Tóth 1940);
  that theorem is not formalised here.
* `average_sides` and `pentagons_eq_twelve` are consequences of Euler's formula and handshaking:
  true of every such lattice and therefore uninformative about which lattice an organism builds.
-/
import Mathlib
/-!
## Biolib · Morphogenesis: how cells, tissues and shells take their form

Origin: `lean/Delphi/CellGeometry.lean` in fractastical/delphi_private at `ffdc528e4f95`, copied by
`biolib/scripts/sync-from-delphi.py`. Edit it there; this copy is regenerated.
Registry laws: `bee-cell-rhombic-closure` (candidate, v1.0.0), `hexagon-of-120` (candidate, v1.0.0), `hexagonal-lattice-density` (candidate, v1.0.0), `hexagonal-on-average` (candidate, v1.0.0), `plateau-tetrahedral-angle` (candidate, v1.0.0), `plateau-triple-junction-120` (candidate, v1.0.0), `twelve-pentagons` (candidate, v1.0.0).
Lean-checked claims: none.
-/


open Real

namespace Delphi.CellGeometry

variable {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℝ V]

/-! ## Junctions of three walls (Plateau's first rule) -/

/-- Equilibrium of a junction where three walls of tensions `T₁, T₂, T₃` pull along the unit
directions `u, v, w` (Neumann's triangle of forces). -/
def junctionBalanced (T₁ T₂ T₃ : ℝ) (u v w : V) : Prop :=
  T₁ • u + T₂ • v + T₃ • w = 0

/-- At a balanced junction the tensions fix the angle between the walls `u, v`:
`T₃² = T₁² + T₂² + 2 T₁ T₂ cos ∠(u, v)`. -/
theorem junction_inner (T₁ T₂ T₃ : ℝ) (u v w : V)
    (hu : ‖u‖ = 1) (hv : ‖v‖ = 1) (hw : ‖w‖ = 1) (h : junctionBalanced T₁ T₂ T₃ u v w) :
    T₃ ^ 2 = T₁ ^ 2 + T₂ ^ 2 + 2 * T₁ * T₂ * inner ℝ u v := by
  unfold junctionBalanced at h
  have h' : T₃ • w = -(T₁ • u + T₂ • v) := by
    rw [eq_neg_iff_add_eq_zero, add_comm]; exact h
  have hn := congrArg (fun x => ‖x‖ ^ 2) h'
  simp only [norm_neg, norm_add_sq_real, norm_smul, Real.norm_eq_abs, mul_pow, sq_abs, hu, hv,
    hw, real_inner_smul_left, real_inner_smul_right] at hn
  linarith

theorem cos_two_pi_div_three : Real.cos (2 * π / 3) = -(1 / 2) := by
  rw [show 2 * π / 3 = π - π / 3 by ring, Real.cos_pi_sub, Real.cos_pi_div_three]

-- @law plateau-triple-junction-120
/-- **Plateau's first rule.** Three walls of equal positive tension meeting at a point are in
equilibrium only if each pair meets at 120°. Cell size does not enter. -/
theorem tripleJunction_120 (T : ℝ) (hT : 0 < T) (u v w : V)
    (hu : ‖u‖ = 1) (hv : ‖v‖ = 1) (hw : ‖w‖ = 1) (h : junctionBalanced T T T u v w) :
    InnerProductGeometry.angle u v = 2 * π / 3 ∧ InnerProductGeometry.angle v w = 2 * π / 3 ∧
      InnerProductGeometry.angle u w = 2 * π / 3 := by
  have key : ∀ x y z : V, ‖x‖ = 1 → ‖y‖ = 1 → ‖z‖ = 1 →
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

/-- Non-vacuity: the three unit vectors at 0°, 120° and 240° in the plane are balanced under
equal tension. -/
theorem tripleJunction_120_witness : ∃ u v w : EuclideanSpace ℝ (Fin 2),
    ‖u‖ = 1 ∧ ‖v‖ = 1 ∧ ‖w‖ = 1 ∧ junctionBalanced 1 1 1 u v w := by
  have h3 : √3 ^ 2 = 3 := Real.sq_sqrt (by norm_num)
  refine ⟨!₂[1, 0], !₂[-(1 / 2), √3 / 2], !₂[-(1 / 2), -(√3 / 2)], ?_, ?_, ?_, ?_⟩
  · rw [EuclideanSpace.norm_eq]; simp [Fin.sum_univ_two]
  · rw [EuclideanSpace.norm_eq]
    simp [Fin.sum_univ_two, div_pow, h3]
    norm_num
  · rw [EuclideanSpace.norm_eq]
    simp [Fin.sum_univ_two, div_pow, h3]
    norm_num
  · unfold junctionBalanced
    ext i; fin_cases i <;> simp
    ring

/-! ## The hexagon -/

/-- Interior-angle sum of a convex polygon with `n` sides. -/
noncomputable def polygonAngleSum (n : ℕ) : ℝ := ((n : ℝ) - 2) * π

-- @law hexagon-of-120
/-- A cell bounded by straight walls whose every corner is a 120° junction has exactly six sides;
with fewer sides the corners must on average be sharper than 120°, with more they must be
blunter. -/
theorem hexagon_of_120 (n : ℕ) :
    (polygonAngleSum n = n * (2 * π / 3) ↔ n = 6) ∧
      (n < 6 → polygonAngleSum n < n * (2 * π / 3)) ∧
      (6 < n → (n : ℝ) * (2 * π / 3) < polygonAngleSum n) := by
  unfold polygonAngleSum
  have hπ := Real.pi_pos
  refine ⟨⟨fun h => ?_, fun h => ?_⟩, fun h => ?_, fun h => ?_⟩
  · have h' : ((n : ℝ) - 6) * π = 0 := by linarith
    have : (n : ℝ) = 6 := by
      rcases mul_eq_zero.mp h' with h0 | h0
      · linarith
      · exact absurd h0 Real.pi_ne_zero
    exact_mod_cast this
  · subst h; push_cast; ring
  · have : (n : ℝ) < 6 := by exact_mod_cast h
    nlinarith
  · have : (6 : ℝ) < n := by exact_mod_cast h
    nlinarith

/-- Non-vacuity: the regular hexagon has corners of 120°. -/
theorem hexagon_of_120_witness : polygonAngleSum 6 = 6 * (2 * π / 3) := by
  unfold polygonAngleSum; push_cast; ring

/-! ## Euler bookkeeping: twelve pentagons, and six sides on average -/

/-- A trivalent closed lattice (a map on the sphere with three edges at every vertex): Euler's
formula and vertex–edge handshaking. -/
structure TrivalentSphere where
  vertices : ℤ
  edges : ℤ
  faces : ℤ
  euler : vertices - edges + faces = 2
  trivalent : 2 * edges = 3 * vertices
  faces_pos : 0 < faces

-- @law hexagonal-on-average
/-- **Hexagonal on average.** In a trivalent closed lattice the mean number of sides per face is
`6 - 12/F`: strictly below six, and approaching six as the number of faces grows. A consequence
of Euler's formula alone, so it says nothing about which lattice an organism builds. -/
theorem average_sides (S : TrivalentSphere) :
    (2 * S.edges : ℝ) / S.faces = 6 - 12 / S.faces ∧ (2 * S.edges : ℝ) / S.faces < 6 := by
  have h : 2 * S.edges = 6 * S.faces - 12 := by
    have := S.euler; have := S.trivalent; omega
  have hr : (2 * S.edges : ℝ) = 6 * S.faces - 12 := by exact_mod_cast h
  have hF : (0 : ℝ) < S.faces := by exact_mod_cast S.faces_pos
  rw [hr]
  constructor
  · field_simp
  · rw [div_lt_iff₀ hF]; linarith

/-- Non-vacuity: the dodecahedron (20 vertices, 30 edges, 12 faces). -/
theorem average_sides_witness : ∃ S : TrivalentSphere, S.faces = 12 :=
  ⟨⟨20, 30, 12, by norm_num, by norm_num, by norm_num⟩, rfl⟩

/-- A trivalent closed lattice whose faces are pentagons and hexagons: Euler's formula,
vertex–edge handshaking and face–edge handshaking. -/
structure PentagonHexagonSphere where
  vertices : ℤ
  edges : ℤ
  pentagons : ℤ
  hexagons : ℤ
  euler : vertices - edges + (pentagons + hexagons) = 2
  trivalent : 2 * edges = 3 * vertices
  faces : 2 * edges = 5 * pentagons + 6 * hexagons

-- @law twelve-pentagons
/-- A trivalent closed lattice made only of pentagons and hexagons has exactly twelve pentagons,
however many hexagons it has and whatever it is made of. A topological consequence, not a proof
of Thompson's empirical claim that lattice-shell form is independent of biomineral composition. -/
theorem pentagons_eq_twelve (S : PentagonHexagonSphere) : S.pentagons = 12 := by
  have := S.euler; have := S.trivalent; have := S.faces; omega

/-- Non-vacuity: the truncated icosahedron (60 vertices, 90 edges, 12 pentagons, 20 hexagons). -/
theorem pentagons_eq_twelve_witness : ∃ S : PentagonHexagonSphere, S.hexagons = 20 :=
  ⟨⟨60, 90, 12, 20, by norm_num, by norm_num, by norm_num⟩, rfl⟩

/-! ## The bee's cell -/

/-- Surface of a hexagonal cell of side `s` and height `h` closed by three rhombi inclined at
angle `θ` to the axis (the Maraldi–Koenig problem); the enclosed volume does not depend on `θ`. -/
noncomputable def beeCellArea (s h θ : ℝ) : ℝ :=
  6 * s * h - 3 / 2 * s ^ 2 * (Real.cos θ / Real.sin θ) + 3 * √3 / 2 * s ^ 2 / Real.sin θ

-- @law bee-cell-rhombic-closure
/-- Among such cells the surface is least, `6sh + (3√2/2) s²`, exactly when `cos θ = 1/√3`. -/
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

/-- Non-vacuity: the optimum `θ = arccos (1/√3)` lies strictly inside `(0, π/2)`. -/
theorem beeCellArea_min_witness : ∃ θ : ℝ, 0 < θ ∧ θ < π / 2 ∧ √3 * Real.cos θ = 1 := by
  have hs3 : 1 < √3 := by rw [Real.lt_sqrt (by norm_num)]; norm_num
  have hpos : 0 < 1 / √3 := by positivity
  have hlt : 1 / √3 < 1 := by rw [div_lt_one (by positivity)]; exact hs3
  refine ⟨Real.arccos (1 / √3), Real.arccos_pos.mpr hlt, Real.arccos_lt_pi_div_two.mpr hpos, ?_⟩
  rw [Real.cos_arccos (by linarith) hlt.le]
  field_simp

/-- Cosine of the angle of a rhombus at the ends of its diagonal `d₂`, the other diagonal
being `d₁`. -/
noncomputable def rhombusCos (d₁ d₂ : ℝ) : ℝ := (d₂ ^ 2 - d₁ ^ 2) / (d₁ ^ 2 + d₂ ^ 2)

/-- At the optimum `cos θ = 1/√3` each closing rhombus has diagonals `s√3` and `s / sin θ`, and
its angle at the apex of the cell has cosine `-1/3` (109° 28′, the angle of the rhombic
dodecahedron, and the tetrahedral angle of `tetrahedralJunction_angle` below). -/
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

/-! ## Junctions of four walls (Plateau's second rule) -/

/-- Equilibrium of a point where four walls of equal tension `T` pull along the unit directions
`a, b, c, d`. -/
def quadJunctionBalanced (T : ℝ) (a b c d : V) : Prop :=
  T • a + T • b + T • c + T • d = 0

/-- At a balanced four-wall junction of equal positive tension the six pairwise cosines sum to
`-2`, whatever the individual angles. -/
theorem quadJunction_inner_sum (T : ℝ) (hT : 0 < T) (a b c d : V)
    (ha : ‖a‖ = 1) (hb : ‖b‖ = 1) (hc : ‖c‖ = 1) (hd : ‖d‖ = 1)
    (h : quadJunctionBalanced T a b c d) :
    inner ℝ a b + inner ℝ a c + inner ℝ a d + inner ℝ b c + inner ℝ b d + inner ℝ c d = -2 := by
  unfold quadJunctionBalanced at h
  have h0 : a + b + c + d = 0 := by
    have : T • (a + b + c + d) = 0 := by rw [smul_add, smul_add, smul_add]; exact h
    exact (smul_eq_zero.mp this).resolve_left hT.ne'
  have hn := congrArg (fun x => ‖x‖ ^ 2) h0
  simp only [norm_zero, zero_pow two_ne_zero, norm_add_sq_real, ha, hb, hc, hd,
    inner_add_left] at hn
  linarith

-- @law plateau-tetrahedral-angle
/-- **Plateau's second rule.** Four walls of equal positive tension balanced at a point and
meeting one another at equal angles meet at `arccos (-1/3)` (109° 28′): more than a right angle
and less than the 120° of a triple junction. -/
theorem tetrahedralJunction_angle (T : ℝ) (hT : 0 < T) (a b c d : V)
    (ha : ‖a‖ = 1) (hb : ‖b‖ = 1) (hc : ‖c‖ = 1) (hd : ‖d‖ = 1)
    (h : quadJunctionBalanced T a b c d) (c₀ : ℝ)
    (hab : inner ℝ a b = c₀) (hac : inner ℝ a c = c₀) (had : inner ℝ a d = c₀)
    (hbc : inner ℝ b c = c₀) (hbd : inner ℝ b d = c₀) (hcd : inner ℝ c d = c₀) :
    c₀ = -(1 / 3) ∧ InnerProductGeometry.angle a b = Real.arccos (-(1 / 3)) ∧
      π / 2 < InnerProductGeometry.angle a b ∧ InnerProductGeometry.angle a b < 2 * π / 3 := by
  have hsum := quadJunction_inner_sum T hT a b c d ha hb hc hd h
  rw [hab, hac, had, hbc, hbd, hcd] at hsum
  have hc₀ : c₀ = -(1 / 3) := by linarith
  have hang : InnerProductGeometry.angle a b = Real.arccos (-(1 / 3)) := by
    unfold InnerProductGeometry.angle
    rw [ha, hb, hab, hc₀, mul_one, div_one]
  refine ⟨hc₀, hang, ?_, ?_⟩
  · rw [hang, ← Real.arccos_zero]
    exact Real.arccos_lt_arccos (by norm_num) (by norm_num) (by norm_num)
  · have h23 : 2 * π / 3 = Real.arccos (-(1 / 2)) := by
      rw [← cos_two_pi_div_three, Real.arccos_cos (by positivity) (by linarith [Real.pi_pos])]
    rw [hang, h23]
    exact Real.arccos_lt_arccos (by norm_num) (by norm_num) (by norm_num)

/-- Non-vacuity: the four unit vectors toward the vertices of a regular tetrahedron,
`(±1, ±1, ±1)/√3` with an even number of minus signs, are balanced and pairwise at cosine `-1/3`. -/
theorem tetrahedralJunction_angle_witness : ∃ a b c d : EuclideanSpace ℝ (Fin 3),
    ‖a‖ = 1 ∧ ‖b‖ = 1 ∧ ‖c‖ = 1 ∧ ‖d‖ = 1 ∧ quadJunctionBalanced 1 a b c d ∧
      inner ℝ a b = -(1 / 3) ∧ inner ℝ a c = -(1 / 3) ∧ inner ℝ a d = -(1 / 3) ∧
      inner ℝ b c = -(1 / 3) ∧ inner ℝ b d = -(1 / 3) ∧ inner ℝ c d = -(1 / 3) := by
  have h3 : √3 ^ 2 = 3 := Real.sq_sqrt (by norm_num)
  have hs3 : 0 < √3 := by positivity
  set k : ℝ := 1 / √3 with hk
  have hk2 : k ^ 2 = 1 / 3 := by rw [hk, div_pow, h3, one_pow]
  have hnorm : ∀ x y z : ℝ, x ^ 2 = k ^ 2 → y ^ 2 = k ^ 2 → z ^ 2 = k ^ 2 →
      ‖(!₂[x, y, z] : EuclideanSpace ℝ (Fin 3))‖ = 1 := by
    intro x y z hx hy hz
    rw [EuclideanSpace.norm_eq]
    simp only [Fin.sum_univ_three, Real.norm_eq_abs, sq_abs]
    simp [hx, hy, hz, hk2]
    norm_num
  have hneg : (-k) ^ 2 = k ^ 2 := by ring
  refine ⟨!₂[k, k, k], !₂[k, -k, -k], !₂[-k, k, -k], !₂[-k, -k, k],
    hnorm _ _ _ rfl rfl rfl, hnorm _ _ _ rfl hneg hneg, hnorm _ _ _ hneg rfl hneg,
    hnorm _ _ _ hneg hneg rfl, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩
  · unfold quadJunctionBalanced
    ext i; fin_cases i <;> simp
  all_goals
    simp only [EuclideanSpace.inner_eq_star_dotProduct, Fin.sum_univ_three, dotProduct]
    simp
    nlinarith [hk2]

/-! ## Hexagonal packing of discs -/

/-- Area of a disc of radius `r`. -/
noncomputable def discArea (r : ℝ) : ℝ := π * r ^ 2

/-- Area of the fundamental cell of the hexagonal (triangular) lattice packing of discs of radius
`r`: a rhombus of side `2r` and angle 60°, holding one disc. -/
noncomputable def hexCellArea (r : ℝ) : ℝ := 2 * √3 * r ^ 2

/-- Area of the fundamental cell of the square lattice packing: a square of side `2r`, one disc. -/
noncomputable def squareCellArea (r : ℝ) : ℝ := (2 * r) ^ 2

-- @law hexagonal-lattice-density
/-- Equal discs on the hexagonal lattice cover `π / (2√3)` of the plane, between 0.9068 and
0.9070; on the square lattice they cover `π / 4`; the hexagonal lattice is the denser. This is a
comparison of two lattice arrangements, not the optimality theorem of Thue and Fejes Tóth. -/
theorem hex_denser_than_square (r : ℝ) (hr : 0 < r) :
    discArea r / hexCellArea r = π / (2 * √3) ∧ discArea r / squareCellArea r = π / 4 ∧
      discArea r / squareCellArea r < discArea r / hexCellArea r ∧
      0.9068 < discArea r / hexCellArea r ∧ discArea r / hexCellArea r < 0.9070 := by
  have hs3 : 0 < √3 := by positivity
  have hlo : 1.7320508 < √3 := by rw [Real.lt_sqrt (by norm_num)]; norm_num
  have hhi : √3 < 1.7320509 := by rw [Real.sqrt_lt' (by norm_num)]; norm_num
  have hπlo := Real.pi_gt_d6
  have hπhi := Real.pi_lt_d6
  have hhex : discArea r / hexCellArea r = π / (2 * √3) := by
    unfold discArea hexCellArea; field_simp
  have hsq : discArea r / squareCellArea r = π / 4 := by
    unfold discArea squareCellArea; field_simp; ring
  rw [hhex, hsq]
  refine ⟨rfl, rfl, ?_, ?_, ?_⟩
  · rw [div_lt_div_iff_of_pos_left Real.pi_pos (by norm_num) (by positivity)]; linarith
  · rw [lt_div_iff₀ (by positivity)]; nlinarith
  · rw [div_lt_iff₀ (by positivity)]; nlinarith

/-- Non-vacuity: a disc of positive radius. -/
theorem hex_denser_than_square_witness : ∃ r : ℝ, 0 < r := ⟨1, by norm_num⟩

end Delphi.CellGeometry
