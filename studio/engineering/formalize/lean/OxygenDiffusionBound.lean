import Mathlib.Tactic

/-!
Steady, constant-consumption oxygen bounds for two ideal geometries.

The spherical coefficient 6 is the algebraic limit in Grimes et al. (2014),
Eq. 2.6, after converting the paper's boundary partial pressure p_o to its
oxygen-content variable C_0 = p_o / Ω. The slab coefficient 2 is the
one-dimensional, no-flux-center analogue derived from D C'' = a. These are
conditional transport bounds in those equations, not a cell-viability or
organism-level result.
-/
namespace OxygenDiffusion

noncomputable def sphereCenterOxygen (D a C0 R : ℝ) : ℝ := C0 - (a * R ^ 2) / (6 * D)

noncomputable def slabCenterOxygen (D a C0 L : ℝ) : ℝ := C0 - (a * L ^ 2) / (2 * D)

/-- Under the stated positive diffusion/consumption and nonnegative boundary
oxygen and radius premises, the spherical model's center is nonnegative exactly
when a R² ≤ 6 D C0. -/
theorem sphere_center_oxygen_bound
    {D a C0 R : ℝ}
    (hD : 0 < D) (_ha : 0 < a) (_hC0 : 0 ≤ C0) (_hR : 0 ≤ R) :
    0 ≤ sphereCenterOxygen D a C0 R ↔ a * R ^ 2 ≤ 6 * D * C0 := by
  have hden : 0 < 6 * D := by positivity
  constructor
  · intro hcenter
    have hfrac : a * R ^ 2 / (6 * D) ≤ C0 := by
      dsimp [sphereCenterOxygen] at hcenter
      linarith
    have hmul : a * R ^ 2 ≤ C0 * (6 * D) := (div_le_iff₀ hden).mp hfrac
    nlinarith [hmul]
  · intro hbound
    have hmul : a * R ^ 2 ≤ C0 * (6 * D) := by nlinarith [hbound]
    have hfrac : a * R ^ 2 / (6 * D) ≤ C0 := (div_le_iff₀ hden).mpr hmul
    dsimp [sphereCenterOxygen]
    linarith

/-- Under the same domain conditions, the one-sided slab model's center is
nonnegative exactly when a L² ≤ 2 D C0. L is the distance from the no-flux
mid-plane to the supplied boundary; a two-sided slab has total thickness 2L. -/
theorem slab_center_oxygen_bound
    {D a C0 L : ℝ}
    (hD : 0 < D) (_ha : 0 < a) (_hC0 : 0 ≤ C0) (_hL : 0 ≤ L) :
    0 ≤ slabCenterOxygen D a C0 L ↔ a * L ^ 2 ≤ 2 * D * C0 := by
  have hden : 0 < 2 * D := by positivity
  constructor
  · intro hcenter
    have hfrac : a * L ^ 2 / (2 * D) ≤ C0 := by
      dsimp [slabCenterOxygen] at hcenter
      linarith
    have hmul : a * L ^ 2 ≤ C0 * (2 * D) := (div_le_iff₀ hden).mp hfrac
    nlinarith [hmul]
  · intro hbound
    have hmul : a * L ^ 2 ≤ C0 * (2 * D) := by nlinarith [hbound]
    have hfrac : a * L ^ 2 / (2 * D) ≤ C0 := (div_le_iff₀ hden).mpr hmul
    dsimp [slabCenterOxygen]
    linarith

/-- A zero-size spherical domain retains the supplied boundary value. -/
theorem sphere_zero_radius_boundary (D a C0 : ℝ) :
    sphereCenterOxygen D a C0 0 = C0 := by
  simp [sphereCenterOxygen]

/-- A zero-thickness slab retains the supplied boundary value. -/
theorem slab_zero_thickness_boundary (D a C0 : ℝ) :
    slabCenterOxygen D a C0 0 = C0 := by
  simp [slabCenterOxygen]

/-- At equality, the idealized spherical center is exactly oxygen-depleted. -/
theorem sphere_at_diffusion_limit
    {D a C0 R : ℝ} (hD : 0 < D)
    (heq : a * R ^ 2 = 6 * D * C0) :
    sphereCenterOxygen D a C0 R = 0 := by
  dsimp [sphereCenterOxygen]
  rw [heq]
  field_simp [ne_of_gt hD]
  ring

/-- At equality, the idealized slab center is exactly oxygen-depleted. -/
theorem slab_at_diffusion_limit
    {D a C0 L : ℝ} (hD : 0 < D)
    (heq : a * L ^ 2 = 2 * D * C0) :
    slabCenterOxygen D a C0 L = 0 := by
  dsimp [slabCenterOxygen]
  rw [heq]
  field_simp [ne_of_gt hD]
  ring

#print axioms sphere_center_oxygen_bound
#print axioms slab_center_oxygen_bound
#print axioms sphere_zero_radius_boundary
#print axioms slab_zero_thickness_boundary
#print axioms sphere_at_diffusion_limit
#print axioms slab_at_diffusion_limit

end OxygenDiffusion
