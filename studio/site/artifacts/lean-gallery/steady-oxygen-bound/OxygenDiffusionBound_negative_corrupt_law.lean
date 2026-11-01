import OxygenDiffusionBound
import Mathlib.Tactic

/-! Expected-failure controls: changing either geometry coefficient must break
the frozen parametric center-oxygen threshold. The correct-law twins compile;
the two mutant equivalence proofs must be rejected. -/
open OxygenDiffusion

noncomputable def mutatedSphereCenterOxygen (D a C0 R : ℝ) : ℝ :=
  C0 - (a * R ^ 2) / (5 * D) -- corrupted 6 -> 5

noncomputable def mutatedSlabCenterOxygen (D a C0 L : ℝ) : ℝ :=
  C0 - (a * L ^ 2) / D -- corrupted 2 -> 1

-- These parametric positive twins compile by reusing the frozen rule.
example {D a C0 R : ℝ} (hD : 0 < D) (ha : 0 < a)
    (hC0 : 0 ≤ C0) (hR : 0 ≤ R) :
    0 ≤ sphereCenterOxygen D a C0 R ↔ a * R ^ 2 ≤ 6 * D * C0 :=
  sphere_center_oxygen_bound hD ha hC0 hR

example {D a C0 L : ℝ} (hD : 0 < D) (ha : 0 < a)
    (hC0 : 0 ≤ C0) (hL : 0 ≤ L) :
    0 ≤ slabCenterOxygen D a C0 L ↔ a * L ^ 2 ≤ 2 * D * C0 :=
  slab_center_oxygen_bound hD ha hC0 hL

-- MUTANT-SPHERE: the claimed original threshold cannot characterize the 5-law.
example {D a C0 R : ℝ} (hD : 0 < D) (ha : 0 < a)
    (hC0 : 0 ≤ C0) (hR : 0 ≤ R) :
    0 ≤ mutatedSphereCenterOxygen D a C0 R ↔ a * R ^ 2 ≤ 6 * D * C0 := by
  have hden : 0 < 5 * D := by positivity
  constructor
  · intro hcenter
    have hfrac : a * R ^ 2 / (5 * D) ≤ C0 := by
      dsimp [mutatedSphereCenterOxygen] at hcenter
      linarith
    have hmul : a * R ^ 2 ≤ C0 * (5 * D) := (div_le_iff₀ hden).mp hfrac
    nlinarith [hmul]
  · intro hbound
    have hmul : a * R ^ 2 ≤ 6 * D * C0 := hbound
    have hfrac : a * R ^ 2 / (5 * D) ≤ C0 := by
      -- This is the mutated step: the frozen 6-threshold is too weak for 5.
      nlinarith [hD, ha, hC0, hR, hmul]
    dsimp [mutatedSphereCenterOxygen]
    linarith

-- MUTANT-SLAB: the claimed original threshold cannot characterize the 1-law.
example {D a C0 L : ℝ} (hD : 0 < D) (ha : 0 < a)
    (hC0 : 0 ≤ C0) (hL : 0 ≤ L) :
    0 ≤ mutatedSlabCenterOxygen D a C0 L ↔ a * L ^ 2 ≤ 2 * D * C0 := by
  have hden : 0 < D := hD
  constructor
  · intro hcenter
    have hfrac : a * L ^ 2 / D ≤ C0 := by
      dsimp [mutatedSlabCenterOxygen] at hcenter
      linarith
    have hmul : a * L ^ 2 ≤ C0 * D := (div_le_iff₀ hden).mp hfrac
    nlinarith [hmul]
  · intro hbound
    have hmul : a * L ^ 2 ≤ 2 * D * C0 := hbound
    have hfrac : a * L ^ 2 / D ≤ C0 := by
      -- This is the mutated step: the frozen 2-threshold is too weak for 1.
      nlinarith [hD, ha, hC0, hL, hmul]
    dsimp [mutatedSlabCenterOxygen]
    linarith

-- Concrete rational witnesses make the parametric counterexamples explicit.
example : 0 ≤ mutatedSphereCenterOxygen 1 1 (6 / 5) (5 / 2) := by
  norm_num [mutatedSphereCenterOxygen]

example : 0 ≤ mutatedSlabCenterOxygen 1 1 3 2 := by
  norm_num [mutatedSlabCenterOxygen]
