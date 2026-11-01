import Mathlib

/-!
# Darwin, *On the Origin of Species* (1859), Ch. III–IV: the struggle for existence and
natural selection

Mathematical cores of darwin1859-ch03-01, ch03-02, ch03-03, ch04-14 (with ch01-16) and
ch04-01 (with intro-02, ch02-01). Each `def` names the quantity Darwin argues about; each
`theorem` is the inference he draws, with his assumptions as hypotheses. What is proved is
that the conclusion follows from the assumptions, not that any population satisfies them.
-/

namespace DarwinLaws.Struggle

open Filter Topology

/-! ### darwin1859-ch03-01: geometrical increase versus a bounded world -/

/-- darwin1859-ch03-01: the number of individuals after `t` generations of unchecked
geometrical increase from `N₀` founders, each generation multiplying numbers by `r`. -/
noncomputable def geometricPopulation (N₀ r : ℝ) (t : ℕ) : ℝ := N₀ * r ^ t

/-- Malthus' premise: with `r > 1` the unchecked population exceeds any bound `K` (the
number the area can support) after finitely many generations. -/
theorem geometricPopulation_exceeds_bound (N₀ r K : ℝ) (hN : 0 < N₀) (hr : 1 < r) :
    ∃ t : ℕ, K < geometricPopulation N₀ r t := by
  obtain ⟨t, ht⟩ := pow_unbounded_of_one_lt (K / N₀) hr
  refine ⟨t, ?_⟩
  unfold geometricPopulation
  rwa [div_lt_iff₀ hN, mul_comm] at ht

/-- The surplus that cannot survive, `N₀ rᵗ − K`, grows without limit. -/
theorem surplus_tendsto_atTop (N₀ r K : ℝ) (hN : 0 < N₀) (hr : 1 < r) :
    Tendsto (fun t : ℕ => geometricPopulation N₀ r t - K) atTop atTop := by
  have h1 : Tendsto (fun t : ℕ => r ^ t) atTop atTop := tendsto_pow_atTop_atTop_of_one_lt hr
  have h2 : Tendsto (fun t : ℕ => N₀ * r ^ t) atTop atTop := h1.const_mul_atTop hN
  have h3 := tendsto_atTop_add_const_right atTop (-K) h2
  simpa [geometricPopulation, sub_eq_add_neg] using h3

/-- The fraction of those born that the area could possibly support, `K / (N₀ rᵗ)`,
tends to zero: almost all must perish. -/
theorem supportableFraction_tendsto_zero (N₀ r K : ℝ) (hN : 0 < N₀) (hr : 1 < r) :
    Tendsto (fun t : ℕ => K / geometricPopulation N₀ r t) atTop (𝓝 0) := by
  have h1 : Tendsto (fun t : ℕ => r ^ t) atTop atTop := tendsto_pow_atTop_atTop_of_one_lt hr
  have h2 : Tendsto (fun t : ℕ => N₀ * r ^ t) atTop atTop := h1.const_mul_atTop hN
  exact tendsto_const_nhds.div_atTop h2

/-- The population actually realised when, in generation `t`, only a fraction `s t ∈ [0,1]` of
the `r`-fold offspring survive to breed. -/
noncomputable def realisedPopulation (N₀ r : ℝ) (s : ℕ → ℝ) : ℕ → ℝ
  | 0 => N₀
  | t + 1 => r * s t * realisedPopulation N₀ r s t

theorem realisedPopulation_eq (N₀ r : ℝ) (s : ℕ → ℝ) (t : ℕ) :
    realisedPopulation N₀ r s t = geometricPopulation N₀ r t * ∏ i ∈ Finset.range t, s i := by
  induction t with
  | zero => simp [realisedPopulation, geometricPopulation]
  | succ n ih =>
    rw [realisedPopulation, ih, Finset.prod_range_succ]
    unfold geometricPopulation
    ring

/-- darwin1859-ch03-01, the struggle: if the realised population never exceeds the carrying
bound `K`, the cumulative survival fraction over `t` generations is at most `K / (N₀ rᵗ)`. -/
theorem survivalProduct_le (N₀ r K : ℝ) (s : ℕ → ℝ) (hN : 0 < N₀) (hr : 0 < r)
    (hK : ∀ t, realisedPopulation N₀ r s t ≤ K) (t : ℕ) :
    ∏ i ∈ Finset.range t, s i ≤ K / geometricPopulation N₀ r t := by
  have hpos : 0 < geometricPopulation N₀ r t := by unfold geometricPopulation; positivity
  rw [le_div_iff₀ hpos, mul_comm, ← realisedPopulation_eq]
  exact hK t

/-- Hence, with `r > 1`, the cumulative survival fraction tends to zero: a struggle for
existence (mortality in every long run of generations) is inevitable. -/
theorem survivalProduct_tendsto_zero (N₀ r K : ℝ) (s : ℕ → ℝ) (hN : 0 < N₀) (hr : 1 < r)
    (hs : ∀ i, 0 ≤ s i) (hK : ∀ t, realisedPopulation N₀ r s t ≤ K) :
    Tendsto (fun t => ∏ i ∈ Finset.range t, s i) atTop (𝓝 0) := by
  refine tendsto_of_tendsto_of_tendsto_of_le_of_le tendsto_const_nhds
    (supportableFraction_tendsto_zero N₀ r K hN hr) ?_ ?_
  · intro t
    exact Finset.prod_nonneg (fun i _ => hs i)
  · intro t
    exact survivalProduct_le N₀ r K s hN (zero_lt_one.trans hr) hK t

/-- In particular no bounded population can have every generation survive in full. -/
theorem not_all_survive (N₀ r K : ℝ) (s : ℕ → ℝ) (hN : 0 < N₀) (hr : 1 < r)
    (hK : ∀ t, realisedPopulation N₀ r s t ≤ K) : ¬ ∀ i, s i = 1 := by
  intro hall
  obtain ⟨t, ht⟩ := geometricPopulation_exceeds_bound N₀ r K hN hr
  have := hK t
  rw [realisedPopulation_eq] at this
  simp [hall] at this
  linarith

/-! ### darwin1859-ch03-03: a stationary population fixes the survival fraction -/

/-- darwin1859-ch03-03: if numbers are stationary (`r s N = N`) the survival fraction is
`1 / r`, whatever the fecundity: abundance is set by the destruction, fecundity only
determines how much destruction is compensated. -/
theorem stationary_survival_eq (r s N : ℝ) (hr : r ≠ 0) (hN : N ≠ 0) (h : r * s * N = N) :
    s = 1 / r := by
  have h1 : r * s = 1 := by
    have := mul_right_cancel₀ hN (h.trans (one_mul N).symm)
    exact this
  field_simp
  linarith

/-! ### darwin1859-ch03-02: lowered destruction, not raised fertility, gives rapid spread -/

/-- The realised per-generation multiplier when fecundity is `r` and survival `s`. -/
noncomputable def growthMultiplier (r s : ℝ) : ℝ := r * s

/-- darwin1859-ch03-02: at fixed fecundity, higher survival (fewer enemies in the new
country) gives a strictly higher growth multiplier. -/
theorem growthMultiplier_lt_of_survival_lt (r s s' : ℝ) (hr : 0 < r) (h : s < s') :
    growthMultiplier r s < growthMultiplier r s' := by
  unfold growthMultiplier
  exact mul_lt_mul_of_pos_left h hr

/-- darwin1859-ch03-02: once the multiplier `λ` exceeds one, any target size `M` is reached
within `log(M/N₀) / log λ` generations: increase is "extraordinarily rapid" in the sense of
needing only logarithmically many generations. -/
theorem geometricPopulation_reaches_in_log_time (N₀ lam M : ℝ) (hN : 0 < N₀) (hl : 1 < lam)
    (hM : N₀ ≤ M) (t : ℕ) (ht : Real.log (M / N₀) / Real.log lam ≤ t) :
    M ≤ geometricPopulation N₀ lam t := by
  have hlog : 0 < Real.log lam := Real.log_pos hl
  have hMpos : 0 < M := lt_of_lt_of_le hN hM
  have h1 : Real.log (M / N₀) ≤ t * Real.log lam := by
    rwa [div_le_iff₀ hlog] at ht
  rw [← Real.log_pow] at h1
  have hlampow : 0 < lam ^ t := pow_pos (zero_lt_one.trans hl) t
  rw [Real.log_le_log_iff (div_pos hMpos hN) hlampow, div_le_iff₀ hN] at h1
  unfold geometricPopulation
  linarith

/-! ### darwin1859-ch04-14 (and ch01-16): large numbers favour selection -/

/-- darwin1859-ch04-14: probability that at least one of `N` individuals presents a
profitable variation, when each does so independently with probability `p`. -/
noncomputable def probAnyFavourable (p : ℝ) (N : ℕ) : ℝ := 1 - (1 - p) ^ N

/-- More individuals give a strictly better chance of a profitable variation arising. -/
theorem probAnyFavourable_strictMono (p : ℝ) (hp0 : 0 < p) (hp1 : p < 1) {m n : ℕ}
    (hmn : m < n) : probAnyFavourable p m < probAnyFavourable p n := by
  unfold probAnyFavourable
  have h0 : 0 < 1 - p := by linarith
  have h1 : 1 - p < 1 := by linarith
  have := pow_lt_pow_right_of_lt_one₀ h0 h1 hmn
  linarith

/-- With enough individuals the chance approaches certainty. -/
theorem probAnyFavourable_tendsto_one (p : ℝ) (hp0 : 0 < p) (hp1 : p ≤ 1) :
    Tendsto (fun N => probAnyFavourable p N) atTop (𝓝 1) := by
  unfold probAnyFavourable
  have h := tendsto_pow_atTop_nhds_zero_of_lt_one (by linarith : (0 : ℝ) ≤ 1 - p)
    (by linarith : 1 - p < 1)
  simpa using h.const_sub 1

/-! ### darwin1859-ch04-01 (and intro-02, ch02-01): natural selection -/

/-- darwin1859-ch04-01: the frequency of a variant after one generation of selection, when
the variant has fitness `wA` and the rest of the population fitness `wB` (discrete-time
haploid selection). -/
noncomputable def selectedFrequency (p wA wB : ℝ) : ℝ :=
  p * wA / (p * wA + (1 - p) * wB)

/-- Any advantage, however slight (`wB < wA`), increases the variant's frequency. -/
theorem selectedFrequency_gt (p wA wB : ℝ) (hp0 : 0 < p) (hp1 : p < 1) (hB : 0 < wB)
    (hAB : wB < wA) : p < selectedFrequency p wA wB := by
  unfold selectedFrequency
  have hD : 0 < p * wA + (1 - p) * wB := by nlinarith
  rw [lt_div_iff₀ hD]
  nlinarith [mul_pos (mul_pos hp0 (sub_pos.2 hp1)) (sub_pos.2 hAB)]

/-- An injurious variation (`wA < wB`) decreases in frequency. -/
theorem selectedFrequency_lt (p wA wB : ℝ) (hp0 : 0 < p) (hp1 : p < 1) (hA : 0 < wA)
    (hAB : wA < wB) : selectedFrequency p wA wB < p := by
  unfold selectedFrequency
  have hD : 0 < p * wA + (1 - p) * wB := by nlinarith
  rw [div_lt_iff₀ hD]
  nlinarith [mul_pos (mul_pos hp0 (sub_pos.2 hp1)) (sub_pos.2 hAB)]

/-- Frequency of the variant after `t` generations of selection from initial frequency `p₀`. -/
noncomputable def selectedTrajectory (p₀ wA wB : ℝ) (t : ℕ) : ℝ :=
  p₀ * wA ^ t / (p₀ * wA ^ t + (1 - p₀) * wB ^ t)

/-- The trajectory is the iterate of one-generation selection. -/
theorem selectedTrajectory_succ (p₀ wA wB : ℝ) (hp0 : 0 < p₀) (hp1 : p₀ < 1) (hA : 0 < wA)
    (hB : 0 < wB) (t : ℕ) :
    selectedFrequency (selectedTrajectory p₀ wA wB t) wA wB = selectedTrajectory p₀ wA wB (t + 1) := by
  unfold selectedFrequency selectedTrajectory
  have hq : 0 < 1 - p₀ := by linarith
  have hDt : 0 < p₀ * wA ^ t + (1 - p₀) * wB ^ t := by positivity
  have hne : p₀ * wA ^ t + (1 - p₀) * wB ^ t ≠ 0 := hDt.ne'
  have h1 : 1 - p₀ * wA ^ t / (p₀ * wA ^ t + (1 - p₀) * wB ^ t)
      = (1 - p₀) * wB ^ t / (p₀ * wA ^ t + (1 - p₀) * wB ^ t) := by
    rw [eq_div_iff hne, sub_mul, div_mul_cancel₀ _ hne]
    ring
  rw [h1, div_mul_eq_mul_div, div_mul_eq_mul_div, ← add_div, div_div_div_cancel_right₀ hne]
  congr 1 <;> ring

/-- darwin1859-ch04-01, preservation of the favoured: under a constant advantage the favoured
variant's frequency tends to one (and so the less favoured is eliminated). -/
theorem selectedTrajectory_tendsto_one (p₀ wA wB : ℝ) (hp0 : 0 < p₀) (hp1 : p₀ < 1)
    (hB : 0 < wB) (hAB : wB < wA) :
    Tendsto (selectedTrajectory p₀ wA wB) atTop (𝓝 1) := by
  have hA : 0 < wA := hB.trans hAB
  have hratio0 : 0 ≤ wB / wA := div_nonneg hB.le hA.le
  have hratio1 : wB / wA < 1 := (div_lt_one hA).2 hAB
  have hform : ∀ t, selectedTrajectory p₀ wA wB t = p₀ / (p₀ + (1 - p₀) * (wB / wA) ^ t) := by
    intro t
    unfold selectedTrajectory
    have hAt : 0 < wA ^ t := pow_pos hA t
    rw [div_pow]
    field_simp
  rw [show selectedTrajectory p₀ wA wB = fun t => p₀ / (p₀ + (1 - p₀) * (wB / wA) ^ t) from
    funext hform]
  have h1 : Tendsto (fun t : ℕ => (wB / wA) ^ t) atTop (𝓝 0) :=
    tendsto_pow_atTop_nhds_zero_of_lt_one hratio0 hratio1
  have h2 : Tendsto (fun t : ℕ => p₀ + (1 - p₀) * (wB / wA) ^ t) atTop (𝓝 (p₀ + (1 - p₀) * 0)) :=
    tendsto_const_nhds.add (tendsto_const_nhds.mul h1)
  have hne : p₀ + (1 - p₀) * 0 ≠ 0 := by rw [mul_zero, add_zero]; exact hp0.ne'
  have h3 : Tendsto (fun t : ℕ => p₀ / (p₀ + (1 - p₀) * (wB / wA) ^ t)) atTop
      (𝓝 (p₀ / (p₀ + (1 - p₀) * 0))) := tendsto_const_nhds.div h2 hne
  rw [mul_zero, add_zero, div_self hp0.ne'] at h3
  exact h3

end DarwinLaws.Struggle
