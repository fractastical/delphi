import ScaledThresholdIntervals
import Mathlib.Tactic
open ScaledThresholdIntervals

-- The unchanged parametric law twins must compile before any expected failure.
example {x y a b t : ℝ} (hx : 0 < x) (hy : 0 < y) (ht : 0 ≤ t)
    (hlo : a ≤ x) (hhi : y ≤ b) (hband : x ≤ t * y) : a ≤ t * b :=
  factor_band_forces_endpoint_bound hx hy ht hlo hhi hband
example {x y a b t : ℝ} (hx : 0 < x) (hy : 0 < y) (ht : 0 ≤ t)
    (hlo : a ≤ x) (hhi : y ≤ b) (hsep : t * b < a) : ¬ x ≤ t * y :=
  separated_intervals_reject_factor_band hx hy ht hlo hhi hsep

-- MUTATION-BEGIN reverse_lower
example {x y a b t : ℝ} (hx : 0 < x) (hy : 0 < y) (ht : 0 ≤ t)
    (hlo : x ≤ a) (hhi : y ≤ b) (hsep : t * b < a) : ¬ x ≤ t * y := by
  intro hband
  nlinarith [mul_le_mul_of_nonneg_left hhi ht]
-- MUTATION-END reverse_lower

-- MUTATION-BEGIN reverse_upper
example {x y a b t : ℝ} (hx : 0 < x) (hy : 0 < y) (ht : 0 ≤ t)
    (hlo : a ≤ x) (hhi : b ≤ y) (hsep : t * b < a) : ¬ x ≤ t * y := by
  intro hband
  nlinarith [mul_le_mul_of_nonneg_left hhi ht]
-- MUTATION-END reverse_upper

-- MUTATION-BEGIN nonstrict_separation
example {x y a b t : ℝ} (hx : 0 < x) (hy : 0 < y) (ht : 0 ≤ t)
    (hlo : a ≤ x) (hhi : y ≤ b) (hsep : t * b ≤ a) : ¬ x ≤ t * y := by
  intro hband
  have hbound := factor_band_forces_endpoint_bound hx hy ht hlo hhi hband
  linarith
-- MUTATION-END nonstrict_separation

-- MUTATION-BEGIN dropped_factor
example {x y a b t : ℝ} (hx : 0 < x) (hy : 0 < y) (ht : 0 ≤ t)
    (hlo : a ≤ x) (hhi : y ≤ b) (hband : x ≤ t * y) : a ≤ b := by
  have hbound := factor_band_forces_endpoint_bound hx hy ht hlo hhi hband
  nlinarith
-- MUTATION-END dropped_factor
