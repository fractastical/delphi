import Mathlib

/-! Red-team file for GSK-LeanBio @ 2d35f9f. Expected: exactly ONE error, at `mutated_flagship`. -/

namespace RedTeam

-- (1) Non-flagship `bsl certify` instance (fractional intervals): does the emitted proof close?
theorem revfrac_instance (kf kr X Y : ℝ)
    (hkf_lo : (1 / 2 : ℝ) ≤ kf) (hkf_hi : kf ≤ 3)
    (hkr_lo : (7 / 10 : ℝ) ≤ kr) (hkr_hi : kr ≤ (5 / 2 : ℝ))
    (hmass : X + Y = (73 / 10 : ℝ))
    (hss : kf * X = kr * Y) :
    (511 / 370 : ℝ) ≤ X ∧ X ≤ (73 / 12 : ℝ) ∧ (73 / 60 : ℝ) ≤ Y ∧ Y ≤ (219 / 37 : ℝ) := by
  have hpos : 0 < kf + kr := by linarith
  have hsum : (kf + kr) * X = (73 / 10 : ℝ) * kr := by linear_combination hss + kr * hmass
  have hAlo : (511 / 370 : ℝ) ≤ X := by nlinarith [hsum, hpos, hkf_lo, hkf_hi, hkr_lo, hkr_hi]
  have hAhi : X ≤ (73 / 12 : ℝ) := by nlinarith [hsum, hpos, hkf_lo, hkf_hi, hkr_lo, hkr_hi]
  refine ⟨hAlo, hAhi, ?_, ?_⟩ <;> linarith

-- (2) Mutation: tighten the flagship's upper bound 8 -> 7. MUST FAIL (k1=1,k2=4 gives A=8).
theorem mutated_flagship
    (k1 k2 A B : ℝ)
    (hk1lo : 1 ≤ k1) (hk1hi : k1 ≤ 2)
    (hk2lo : 3 ≤ k2) (hk2hi : k2 ≤ 4)
    (hmass : A + B = 10)
    (hss : k1 * A = k2 * B) :
    6 ≤ A ∧ A ≤ 7 ∧ 2 ≤ B ∧ B ≤ 4 := by
  have hpos : 0 < k1 + k2 := by linarith
  have hsum : (k1 + k2) * A = 10 * k2 := by linear_combination hss + k2 * hmass
  have hA6 : 6 ≤ A := by nlinarith [hsum, hpos, hk1hi, hk2lo]
  have hA8 : A ≤ 7 := by nlinarith [hsum, hpos, hk1lo, hk2hi]
  refine ⟨hA6, hA8, ?_, ?_⟩ <;> linarith

-- (3) The `bsl verify` obligation for int_gap.bsl, read over ℝ (fluxes are real quantities).
--     omega "discharged" it over Int. Over ℝ it is FALSE: witness (11, 5.5, 5.5).
theorem int_gap_false_over_reals :
    ¬ (∀ v_influx v_step v_efflux : ℝ,
        v_influx + (-2) * v_step = 0 →
        v_step + (-v_efflux) = 0 →
        11 ≤ v_influx → v_influx ≤ 11 →
        0 ≤ v_efflux ∧ v_efflux ≤ 0) := by
  intro h
  have := h 11 (11 / 2) (11 / 2) (by norm_num) (by norm_num) (by norm_num) (by norm_num)
  linarith [this.2]

end RedTeam
