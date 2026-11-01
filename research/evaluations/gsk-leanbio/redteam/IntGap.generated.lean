/- Auto-generated conservation obligations for IntGap by GSK-LeanBio. -/
/- Flux-abstract stoichiometric conservation, checked by `omega` (Lean core, no Mathlib). -/
namespace BSL.IntGap.Verify

theorem absurd (v_influx v_step v_efflux : Int)
    (hs_A : v_influx + (-2) * v_step = 0)
    (hs_B : v_step + (-v_efflux) = 0)
    (hin_lo_influx : 11 ≤ v_influx)
    (hin_hi_influx : v_influx ≤ 11) :
    0 ≤ v_efflux ∧ v_efflux ≤ 0 := by
  omega

end BSL.IntGap.Verify
