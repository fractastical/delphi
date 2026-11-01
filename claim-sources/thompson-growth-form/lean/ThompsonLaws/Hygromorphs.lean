import Mathlib

/-!
# Plant hygromorph mechanics

Formalizations of the mathematical core of the claims in
`claim-sources/plant-hygromorph-mechanics/claims/key-claims.json`. They live in the Thompson
Lake project only because Lean reports are keyed by claim id across projects and a second
Mathlib checkout would be large.
-/

namespace ThompsonLaws.Hygromorphs

noncomputable section

open Real

/-! ## hygromorph-bilayer-curvature -/

/-- hygromorph-bilayer-curvature: Timoshenko's geometric coefficient for a two-layer strip of
total thickness `h`, thickness ratio `m = h₁/h₂` and modulus ratio `n = E₁/E₂`. The curvature
is this coefficient times the swelling-strain mismatch. -/
def timoshenkoCoefficient (h m n : ℝ) : ℝ :=
  (1 / h) * (6 * (1 + m) ^ 2) / (3 * (1 + m) ^ 2 + (1 + m * n) * (m ^ 2 + 1 / (m * n)))

/-- Curvature of the bilayer under a swelling-strain mismatch `Δε` between its layers. -/
def bilayerCurvature (h m n Δε : ℝ) : ℝ := timoshenkoCoefficient h m n * Δε

/-- The curvature is proportional to the mismatch. -/
theorem bilayerCurvature_linear (h m n c Δε : ℝ) :
    bilayerCurvature h m n (c * Δε) = c * bilayerCurvature h m n Δε := by
  unfold bilayerCurvature; ring

/-- No mismatch, no curvature. -/
theorem bilayerCurvature_zero (h m n : ℝ) : bilayerCurvature h m n 0 = 0 := by
  simp [bilayerCurvature]

/-- Equal thicknesses and moduli (`m = n = 1`): `κ = (3/2) Δε / h`. -/
theorem bilayerCurvature_symmetric (h Δε : ℝ) (hh : h ≠ 0) :
    bilayerCurvature h 1 1 Δε = 3 / 2 * Δε / h := by
  unfold bilayerCurvature timoshenkoCoefficient
  field_simp
  ring

/-- For physical (positive) thickness and ratios the coefficient is positive. -/
theorem timoshenkoCoefficient_pos (h m n : ℝ) (hh : 0 < h) (hm : 0 < m) (hn : 0 < n) :
    0 < timoshenkoCoefficient h m n := by
  unfold timoshenkoCoefficient
  positivity

/-- Hence the curvature has the sign of the mismatch: the layer that swells more ends up
on the convex side. -/
theorem bilayerCurvature_sign (h m n Δε : ℝ) (hh : 0 < h) (hm : 0 < m) (hn : 0 < n) :
    (0 < Δε → 0 < bilayerCurvature h m n Δε) ∧
      (Δε < 0 → bilayerCurvature h m n Δε < 0) ∧
      (Δε = 0 → bilayerCurvature h m n Δε = 0) := by
  have hc := timoshenkoCoefficient_pos h m n hh hm hn
  unfold bilayerCurvature
  refine ⟨fun hε => mul_pos hc hε, fun hε => mul_neg_of_pos_of_neg hc hε, fun hε => ?_⟩
  simp [hε]

/-- Derivation of Timoshenko's formula from the equilibrium of a two-layer Euler–Bernoulli
strip (per unit width). Layer 1 (thickness `h₁`, modulus `E₁`, eigenstrain `ε₁`) sits on
top of layer 2 (`h₂`, `E₂`, `ε₂`); `P₁`, `P₂` are the resultant axial forces in the layers
and `κ` the common curvature, positive when the top is stretched. The hypotheses are:
force balance (`P₁ + P₂ = 0`); moment balance about the interface, the couple of the
axial forces against the layers' bending moments `Eᵢ hᵢ³ κ / 12`; and strain compatibility
at the bonded interface, where each layer's strain is its eigenstrain plus the membrane
strain `Pᵢ/(Eᵢ hᵢ)` plus the bending strain `κ y` at the interface's offset `y` from the
layer's own mid-plane (`−h₁/2` for the top layer, `+h₂/2` for the bottom one). The unique
curvature satisfying them is Timoshenko's. -/
theorem bilayerCurvature_ofEquilibrium (h₁ h₂ E₁ E₂ ε₁ ε₂ P₁ P₂ κ : ℝ)
    (hh₁ : 0 < h₁) (hh₂ : 0 < h₂) (hE₁ : 0 < E₁) (hE₂ : 0 < E₂)
    (hforce : P₁ + P₂ = 0)
    (hmoment : P₁ * (h₁ + h₂) / 2 + κ * (E₁ * h₁ ^ 3 / 12 + E₂ * h₂ ^ 3 / 12) = 0)
    (hcompat : ε₁ + P₁ / (E₁ * h₁) - κ * h₁ / 2 = ε₂ + P₂ / (E₂ * h₂) + κ * h₂ / 2) :
    κ = bilayerCurvature (h₁ + h₂) (h₁ / h₂) (E₁ / E₂) (ε₁ - ε₂) := by
  have hh : h₁ + h₂ ≠ 0 := by positivity
  have hP₂ : P₂ = -P₁ := by linarith
  subst hP₂
  have hP₁ : P₁ = -(2 * κ * (E₁ * h₁ ^ 3 / 12 + E₂ * h₂ ^ 3 / 12)) / (h₁ + h₂) := by
    rw [eq_div_iff hh]
    linear_combination 2 * hmoment
  subst hP₁
  -- the compatibility condition read as `Δε = κ · D`
  have hD : ε₁ - ε₂ = κ * ((h₁ + h₂) / 2
      + 2 * (E₁ * h₁ ^ 3 / 12 + E₂ * h₂ ^ 3 / 12) / (h₁ + h₂)
        * (1 / (E₁ * h₁) + 1 / (E₂ * h₂))) := by
    linear_combination hcompat
  -- Timoshenko's coefficient is `1 / D`
  have hcoef : timoshenkoCoefficient (h₁ + h₂) (h₁ / h₂) (E₁ / E₂) * ((h₁ + h₂) / 2
      + 2 * (E₁ * h₁ ^ 3 / 12 + E₂ * h₂ ^ 3 / 12) / (h₁ + h₂)
        * (1 / (E₁ * h₁) + 1 / (E₂ * h₂))) = 1 := by
    unfold timoshenkoCoefficient
    field_simp
    ring
  unfold bilayerCurvature
  rw [hD]
  linear_combination (-κ) * hcoef

/-! ## hygromorph-response-time -/

/-- hygromorph-response-time: the diffusive time scale `h² / D` for water to cross a layer
of thickness `h` with diffusivity `D`. -/
def diffusiveTime (h D : ℝ) : ℝ := h ^ 2 / D

/-- Doubling the thickness quadruples the response time: `τ(k h) = k² τ(h)`. -/
theorem diffusiveTime_scale (h D k : ℝ) :
    diffusiveTime (k * h) D = k ^ 2 * diffusiveTime h D := by
  unfold diffusiveTime; ring

/-- Decay rate of the slowest diffusion mode in a layer of thickness `h`. -/
def diffusiveRate (h D : ℝ) : ℝ := π ^ 2 * D / h ^ 2

/-- The slowest mode decays on the time `h² / (π² D)`, i.e. `τ / π²`. -/
theorem diffusiveRate_eq (h D : ℝ) : diffusiveRate h D = π ^ 2 / diffusiveTime h D := by
  unfold diffusiveRate diffusiveTime; rw [div_div_eq_mul_div]

/-- The slowest mode of the one-dimensional diffusion equation on `0 ≤ x ≤ h` with the
concentration held at the boundaries: `u(x, t) = exp(−π² D t / h²) · sin(π x / h)`. -/
def diffusionMode (h D x t : ℝ) : ℝ :=
  Real.exp (-diffusiveRate h D * t) * Real.sin (π / h * x)

theorem diffusionMode_hasDerivAt_time (h D x t : ℝ) :
    HasDerivAt (fun s => diffusionMode h D x s)
      (Real.exp (-diffusiveRate h D * t) * (-diffusiveRate h D * 1) * Real.sin (π / h * x)) t :=
  ((hasDerivAt_id' t).const_mul (-diffusiveRate h D)).exp.mul_const _

theorem diffusionMode_hasDerivAt_space (h D x t : ℝ) :
    HasDerivAt (fun z => diffusionMode h D z t)
      (Real.exp (-diffusiveRate h D * t) * (Real.cos (π / h * x) * (π / h * 1))) x :=
  (((hasDerivAt_id' x).const_mul (π / h)).sin).const_mul _

/-- First space derivative of the mode, as a function. -/
theorem diffusionMode_deriv_space (h D t : ℝ) :
    deriv (fun z => diffusionMode h D z t)
      = fun y => Real.exp (-diffusiveRate h D * t) * (π / h) * Real.cos (π / h * y) := by
  funext y
  rw [(diffusionMode_hasDerivAt_space h D y t).deriv]
  ring

/-- The mode satisfies the heat equation `∂u/∂t = D ∂²u/∂x²`. -/
theorem diffusionMode_heat (h D x t : ℝ) :
    deriv (fun s => diffusionMode h D x s) t
      = D * deriv (deriv (fun z => diffusionMode h D z t)) x := by
  rw [(diffusionMode_hasDerivAt_time h D x t).deriv, diffusionMode_deriv_space]
  have h2 : HasDerivAt
      (fun y => Real.exp (-diffusiveRate h D * t) * (π / h) * Real.cos (π / h * y))
      (Real.exp (-diffusiveRate h D * t) * (π / h) * (-Real.sin (π / h * x) * (π / h * 1))) x :=
    (((hasDerivAt_id' x).const_mul (π / h)).cos).const_mul _
  rw [h2.deriv]
  unfold diffusiveRate
  ring

/-- The mode vanishes at both faces of the layer, `x = 0` and `x = h`. -/
theorem diffusionMode_boundary (h D t : ℝ) (hh : h ≠ 0) :
    diffusionMode h D 0 t = 0 ∧ diffusionMode h D h t = 0 := by
  unfold diffusionMode
  constructor
  · simp
  · rw [div_mul_cancel₀ _ hh, Real.sin_pi, mul_zero]

/-- Decay of the mode: at any `x`, `u(x, t) = exp(−t / (τ/π²)) · u(x, 0)` with `τ = h²/D`,
so the mode relaxes on the diffusive time scale. -/
theorem diffusionMode_decay (h D x t : ℝ) :
    diffusionMode h D x t = Real.exp (-(π ^ 2 / diffusiveTime h D) * t) * diffusionMode h D x 0 := by
  unfold diffusionMode
  rw [← diffusiveRate_eq]
  simp

/-! ## hygromorph-antisymmetric-twist -/

/-- hygromorph-antisymmetric-twist: in-plane shear strain `ε₁₂` of a layer that swells by
`εL` along its fibres and `εT` across them, with the fibres at angle `φ` to the strip axis. -/
def shearStrain (εL εT φ : ℝ) : ℝ := 1 / 2 * (εL - εT) * Real.sin (2 * φ)

/-- Axial strain `ε₁₁` of the same layer along the strip axis. -/
def axialStrain (εL εT φ : ℝ) : ℝ := εL * (Real.cos φ) ^ 2 + εT * (Real.sin φ) ^ 2

/-- Layers at `+φ` and `−φ` have equal and opposite shear strains. -/
theorem shearStrain_neg (εL εT φ : ℝ) : shearStrain εL εT (-φ) = -shearStrain εL εT φ := by
  unfold shearStrain
  rw [mul_neg, Real.sin_neg]
  ring

/-- Layers at `+φ` and `−φ` have the same axial strain. -/
theorem axialStrain_neg (εL εT φ : ℝ) : axialStrain εL εT (-φ) = axialStrain εL εT φ := by
  unfold axialStrain
  rw [Real.cos_neg, Real.sin_neg, neg_sq]

/-- The through-thickness shear mismatch of the antisymmetric bilayer is
`Δε₁₂ = (εL − εT) sin 2φ`. -/
theorem shearStrain_mismatch (εL εT φ : ℝ) :
    shearStrain εL εT φ - shearStrain εL εT (-φ) = (εL - εT) * Real.sin (2 * φ) := by
  rw [shearStrain_neg]
  unfold shearStrain
  ring

/-- The axial mismatch vanishes, so there is no bending, only twist. -/
theorem axialStrain_mismatch (εL εT φ : ℝ) :
    axialStrain εL εT φ - axialStrain εL εT (-φ) = 0 := by
  rw [axialStrain_neg, sub_self]

/-- Rotation of the plane by `φ`. -/
def rotation (φ : ℝ) : Matrix (Fin 2) (Fin 2) ℝ :=
  !![Real.cos φ, -Real.sin φ; Real.sin φ, Real.cos φ]

/-- The layer's strain tensor in the strip axes: the principal strain tensor `diag(εL, εT)`
of the fibre frame, rotated by the fibre angle as a rank-2 tensor, `R ε Rᵀ`. -/
def strainInStripAxes (εL εT φ : ℝ) : Matrix (Fin 2) (Fin 2) ℝ :=
  rotation φ * !![εL, 0; 0, εT] * (rotation φ).transpose

/-- Mohr's circle: the `(1,1)` and `(1,2)` entries of the rotated tensor are the axial and
shear strains above. -/
theorem strainInStripAxes_entries (εL εT φ : ℝ) :
    strainInStripAxes εL εT φ 0 0 = axialStrain εL εT φ ∧
      strainInStripAxes εL εT φ 0 1 = shearStrain εL εT φ := by
  unfold strainInStripAxes rotation axialStrain shearStrain
  simp [Matrix.mul_apply, Fin.sum_univ_two, Real.sin_two_mul]
  constructor <;> ring

/-! ## flytrap-snap-geometry -/

/-- flytrap-snap-geometry: the dimensionless parameter `α = L⁴ κ² / h²` of a shallow shell
of size `L`, thickness `h` and natural curvature `κ`. -/
def snapParameter (L κ h : ℝ) : ℝ := L ^ 4 * κ ^ 2 / h ^ 2

/-- `α` is dimensionless: rescaling lengths by `s` (so curvature by `1/s`) leaves it fixed. -/
theorem snapParameter_dimensionless (L κ h s : ℝ) (hs : s ≠ 0) :
    snapParameter (s * L) (κ / s) (s * h) = snapParameter L κ h := by
  unfold snapParameter
  field_simp

/-- At fixed curvature and thickness, `α` grows with leaf size. -/
theorem snapParameter_mono_size (L₁ L₂ κ h : ℝ) (h₀ : 0 ≤ L₁) (hL : L₁ ≤ L₂) :
    snapParameter L₁ κ h ≤ snapParameter L₂ κ h := by
  unfold snapParameter
  gcongr

/-- At fixed size and curvature, `α` falls as the leaf thickens. -/
theorem snapParameter_anti_thickness (L κ h₁ h₂ : ℝ) (h₀ : 0 < h₁) (hh : h₁ ≤ h₂) :
    snapParameter L κ h₂ ≤ snapParameter L κ h₁ := by
  unfold snapParameter
  gcongr

/-- Whatever the (empirical) threshold `αc`, if a leaf of size `L₁` is above it then so is
every larger leaf of the same curvature and thickness: the snapping regime is upward-closed
in size. -/
theorem snapParameter_threshold_mono (L₁ L₂ κ h αc : ℝ) (h₀ : 0 ≤ L₁) (hL : L₁ ≤ L₂)
    (hsnap : αc ≤ snapParameter L₁ κ h) : αc ≤ snapParameter L₂ κ h :=
  hsnap.trans (snapParameter_mono_size L₁ L₂ κ h h₀ hL)

/-- Poroelastic time scale `μ L² / (k E)` of a leaf of size `L`, permeability `k`, modulus
`E` and fluid viscosity `μ`. -/
def poroelasticTime (μ L k E : ℝ) : ℝ := μ * L ^ 2 / (k * E)

/-- The snap time scales as the square of leaf size. -/
theorem poroelasticTime_scale (μ L k E s : ℝ) :
    poroelasticTime μ (s * L) k E = s ^ 2 * poroelasticTime μ L k E := by
  unfold poroelasticTime; ring

/-! ## stimulus-response-systems-category -/

/-- stimulus-response-systems-category: a stimulus–response system is a state space `X`
(a real normed space, standing in for the finite-dimensional manifold), a stimulus space
`E` and an evolution law `f`, read as the vector field of `ẋ = f(x, e)`. -/
structure StimulusResponseSystem where
  X : Type
  E : Type
  [normed : NormedAddCommGroup X]
  [space : NormedSpace ℝ X]
  f : X → E → X

attribute [instance] StimulusResponseSystem.normed StimulusResponseSystem.space

/-- A morphism `(α, αE)` of stimulus–response systems: a differentiable map on states and
a map on stimuli satisfying the simulation condition `dα_x (f(x, e)) = g(α x, αE e)`. -/
structure StimulusResponseHom (S T : StimulusResponseSystem) where
  α : S.X → T.X
  αE : S.E → T.E
  differentiable : Differentiable ℝ α
  simulation : ∀ x e, fderiv ℝ α x (S.f x e) = T.f (α x) (αE e)

namespace StimulusResponseHom

/-- The identity pair satisfies the simulation condition. -/
def id (S : StimulusResponseSystem) : StimulusResponseHom S S where
  α := fun x => x
  αE := fun e => e
  differentiable := differentiable_id
  simulation := by
    intro x e
    rw [fderiv_fun_id]
    rfl

/-- The simulation condition is closed under composition: this is the chain rule applied to
the two simulation conditions. -/
theorem comp_simulation {S T U : StimulusResponseSystem}
    (ψ : StimulusResponseHom T U) (φ : StimulusResponseHom S T) (x : S.X) (e : S.E) :
    fderiv ℝ (ψ.α ∘ φ.α) x (S.f x e) = U.f (ψ.α (φ.α x)) (ψ.αE (φ.αE e)) := by
  rw [fderiv_comp x (ψ.differentiable.differentiableAt) (φ.differentiable.differentiableAt),
    ContinuousLinearMap.comp_apply, φ.simulation, ψ.simulation]

/-- Composition of morphisms. -/
def comp {S T U : StimulusResponseSystem}
    (ψ : StimulusResponseHom T U) (φ : StimulusResponseHom S T) : StimulusResponseHom S U where
  α := ψ.α ∘ φ.α
  αE := ψ.αE ∘ φ.αE
  differentiable := ψ.differentiable.comp φ.differentiable
  simulation := comp_simulation ψ φ

theorem id_comp {S T : StimulusResponseSystem} (φ : StimulusResponseHom S T) :
    comp (id T) φ = φ := rfl

theorem comp_id {S T : StimulusResponseSystem} (φ : StimulusResponseHom S T) :
    comp φ (id S) = φ := rfl

theorem comp_assoc {S T U V : StimulusResponseSystem} (χ : StimulusResponseHom U V)
    (ψ : StimulusResponseHom T U) (φ : StimulusResponseHom S T) :
    comp (comp χ ψ) φ = comp χ (comp ψ φ) := rfl

/-- What the simulation condition buys: a morphism carries solutions of `ẋ = f(x, e(t))`
to solutions of `ẏ = g(y, αE(e(t)))`, i.e. it commutes with time evolution. -/
theorem mapsSolutions {S T : StimulusResponseSystem} (φ : StimulusResponseHom S T)
    (γ : ℝ → S.X) (e : ℝ → S.E) (hγ : ∀ t, HasDerivAt γ (S.f (γ t) (e t)) t) (t : ℝ) :
    HasDerivAt (φ.α ∘ γ) (T.f (φ.α (γ t)) (φ.αE (e t))) t := by
  have h := (φ.differentiable.differentiableAt.hasFDerivAt).comp_hasDerivAt t (hγ t)
  rwa [φ.simulation] at h

end StimulusResponseHom

/-- Stimulus–response systems and simulation-preserving pairs form a category. -/
instance stimulusResponseCategory : CategoryTheory.Category StimulusResponseSystem where
  Hom := StimulusResponseHom
  id := StimulusResponseHom.id
  comp φ ψ := StimulusResponseHom.comp ψ φ
  id_comp _ := rfl
  comp_id _ := rfl
  assoc _ _ _ := rfl

open CategoryTheory in
/-- In the category, composing two morphisms gives a morphism whose state map is the
composite and which again satisfies the simulation condition. -/
theorem stimulusResponseCategory_comp_simulation {S T U : StimulusResponseSystem}
    (φ : S ⟶ T) (ψ : T ⟶ U) (x : S.X) (e : S.E) :
    fderiv ℝ (φ ≫ ψ).α x (S.f x e) = U.f (ψ.α (φ.α x)) (ψ.αE (φ.αE e)) :=
  StimulusResponseHom.comp_simulation ψ φ x e

end

end ThompsonLaws.Hygromorphs
